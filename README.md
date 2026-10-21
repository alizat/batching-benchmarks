# Joint Order Selection, Allocation, Batching and Picking 

This project contains accompanying code for Zalando Team BART's (Batching Algorithms) publication [Joint Order Selection, Allocation, Batching and Picking for Large Scale Warehouses](https://arxiv.org/abs/2401.04563).
The instances used to create results in the paper are stored in `instances.zip`.

## How to use

1. Clone this project and copy the files into your own project
2. Generate batching instances via `python generate_instances.py` (any Python 3.6+ works). For each generated instance (per default in the `instances` folder) four files will be created: `{articles, orders, parameters, warehouse_items}.json`. 
3. Run the Distance Greedy Algorithm (DGA) via `python solve_instances.py`. Two files will be stored per instance under `instances/<instance>/dga/`: `batches.json` and `statistics.json`. The runtime in `statistics.json` covers the algorithm only, not reading the instance from disk.
4. Run the Randomized DGA via `python solve_instances.py -a rdga`. Optionally add `--random-sample-size <N>` (default `1`) to sample `N` random orders per step and take the best of them. Results are written to `instances/<instance>/rdga_sample<N>/`, e.g. `python solve_instances.py -a rdga --random-sample-size 50` writes to `instances/<instance>/rdga_sample50/`.
5. Write your own solver to outperform these baseline algorithms :)

Run the tests with `python -m unittest discover`.


## Changes from the upstream repository

This fork adds two changes on top of the upstream implementation:

### 1. Generalized Randomized DGA (`--random-sample-size`)

The original Randomized DGA (RDGA) built each batch by repeatedly picking **one** random order from the remaining pool and adding it as-is, with no comparison against alternatives. This fork generalizes that single random pick into picking **the best order out of a random sample** of configurable size:

- `distance_greedy_algorithm/solver.py`'s `greedy_solver()` now takes a `random_sample_size: int = None` parameter (replacing the old `choose_random_order: bool` flag). `random_sample_size=None` is plain DGA: deterministic, evaluates every remaining order at each step, unchanged from before. `random_sample_size=<int>` is RDGA: at each step, `min(random_sample_size, pool size)` orders are sampled uniformly at random, without replacement, from the remaining pool, and the best of that sample (by the same cost function DGA uses to compare candidates) is picked. `random_sample_size=1` reproduces the original RDGA behavior.
- `solve_instances.py` exposes this as a new `--random-sample-size` CLI flag (default `1`, ignored when `-a dga`): `python solve_instances.py -a rdga --random-sample-size 50` samples 50 random orders per step and takes the best of them. Results go to `instances/<instance>/rdga_sample<N>/` (e.g. `rdga_sample50/`), one folder per sample size, so runs with different sizes don't overwrite each other.
- This makes the random sample size a tunable quality/speed dial sitting between RDGA's original speed (size 1) and DGA's quality (large sizes).
- The random-order-picking implementation changed under the hood (from `random.randrange` to `random.sample`), but this does *not* break reproducibility: CPython's `random.sample(range(n), 1)` reduces to a single `random._randbelow(n)` call internally, exactly like `random.randrange(n)` does, so it consumes the RNG identically. Verified directly: replaying the pre-fork RDGA code (`choose_random_order=True`) against the current `random_sample_size=1` path under the same seed produces byte-identical order sequences and objective values, across multiple seeds and instance sizes. `-a rdga --random-sample-size 1` (and `-a dga`, unaffected either way) remain bit-for-bit reproducible against pre-fork runs.

#### Experimental results: generalized RDGA (random sample size)

Measured via `python solve_instances.py -a rdga --random-sample-size <N>` on the `medium-0` and `large-0` demo instances, compared against the DGA baseline (`-a dga`), i.e. with the default per-pair distance arithmetic (no `-distmatrix`; see [section 2](#2-precomputed-location-distance-matrix--distmatrix) for timings with it). DGA is deterministic (single run); RDGA is randomized, so each sample size was run with RNG seeds 1 through 10 and the results averaged. All runs were executed one at a time. Times cover the algorithm only, not reading the instance. These numbers were measured after merging upstream's same-aisle distance fix, so objective values are lower than in earlier versions of this README.

**medium-0** (5,000 orders, item goal 2,628):

| Algorithm | Avg. time | Avg. # picklists | Avg. objective (total distance) |
|---|---:|---:|---:|
| dga         | 231.0s | 804   | 60,158    |
| rdga, sample size 500 | 20.1s  | 835.8 | 63,610.4  |
| rdga, sample size 50  | 2.07s  | 898.3 | 75,708.8  |
| rdga, sample size 1   | 0.12s  | 910.2 | 135,773.4 |

**large-0** (50,000 orders, item goal 26,500):

| Algorithm | Avg. time | Avg. # picklists | Avg. objective (total distance) |
|---|---:|---:|---:|
| dga          | 17,002s (4h 43m) | 10,225   | 528,700     |
| rdga, sample size 5000 | 1,895.6s (~32m)  | 10,693.3 | 560,574.2   |
| rdga, sample size 500  | 179.3s (2m 59s)  | 11,777.7 | 675,170.0   |
| rdga, sample size 50   | 18.6s            | 13,584.9 | 845,738.6   |
| rdga, sample size 1    | 1.44s            | 14,221.0 | 1,495,518.4 |

Observations:
- Quality improves and runtime grows with the sample size on both instances, converging toward DGA's result:
   - on `medium-0`, sample size 500 (10% of its order pool) lands within ~5.7% of DGA's objective while running ~11x faster than DGA
   - on `large-0`, sample size 5000 (10% of its order pool) lands within ~6.0% of DGA's objective while running ~9x faster.
- On `large-0`, runtime scales roughly linearly with the sample size (500->5000 is a 10x increase in sample size for a ~10.6x increase in runtime).
- The gap to DGA at a fixed sample size widens as the order pool grows, since a fixed sample size covers a shrinking fraction of a bigger pool (sample size 500 is 10% of `medium-0`'s 5,000-order pool but only 1% of `large-0`'s 50,000-order pool: ~5.7% vs ~27.7% above DGA).
- All 70 RDGA runs (2 instances x sample sizes {1, 50, 500} plus `large-0`'s sample size 5000, x 10 seeds) and both DGA runs are feasible (`Instance.check_feasibility()` passes). Variance across seeds is tight at every sample size (e.g. `large-0`'s sample-size-5000 objective ranges 558,382-563,206 across seeds). Picklist counts shrink toward DGA's as the sample size grows on `large-0`; on `medium-0`, sample size 1 averaged slightly more picklists than sample size 50.

### 2. Precomputed location distance matrix (`-distmatrix`)

A **precomputed location distance matrix** speeds up `Instance.distance()` in `batching_problem/definitions.py`:

- Every `(row, aisle)` warehouse location allowed by an instance's `parameters` is enumerated once per instance (a 101x101 grid = 10,201 locations for the generator's default 100x100 warehouse), and a full location-to-location distance matrix (10,201 x 10,201) is precomputed by `Instance.build_distance_matrix()`, called once by `Instance.read()` when the instance is created with `use_distance_matrix=True` (which is what `-distmatrix` sets; see below).
- `Instance.location_index(row, aisle)` translates any `(row, aisle)` location into its flat index into that matrix.
- `Instance.distance(u, v)` now looks up this precomputed matrix instead of recomputing `row_distance` + `aisle_distance` from scratch for every pair of items. Since all zones share the same row/aisle extent, a single matrix is reused across every zone rather than building one per zone.
- The matrix is stored as a flat Python list rather than a numpy array: profiling showed numpy's per-call scalar-indexing overhead exceeds the cost of a plain list index at the call volumes this solver produces (millions of `distance()` calls per solve), so a flat list measured faster despite numpy being used to build the matrix itself.
- This is opt-in via `solve_instances.py`'s `-distmatrix` flag; the default (no flag) stays the original per-pair arithmetic. It's a pure speed optimization -- it changes nothing but wall time.

#### Experimental results: distance matrix speedup

Every run from the RDGA results above (DGA plus RNG seeds 1-10 for each sample size, on both instances) was also run with `-distmatrix`, using the same seeds. The "original arithmetic" column repeats the times from section 1.

| Instance | Algorithm | Avg. time, original arithmetic | Avg. time, `-distmatrix` | Speedup |
|---|---|---:|---:|---:|
| medium-0 | dga          | 231.0s             | 140.9s             | 1.64x   |
| medium-0 | rdga, sample size 500  | 20.1s              | 15.4s              | 1.30x   |
| medium-0 | rdga, sample size 50   | 2.07s              | 1.67s              | 1.24x   |
| large-0  | dga          | 17,002s (4h 43m)   | 12,418s (3h 27m)   | 1.37x   |
| large-0  | rdga, sample size 5000 | 1,895.6s (~32m)    | 1,486.8s (~25m)    | 1.28x   |
| large-0  | rdga, sample size 500  | 179.3s (2m 59s)    | 151.8s (2m 32s)    | 1.18x   |
| large-0  | rdga, sample size 50   | 18.6s              | 16.8s              | 1.11x   |

Sample size 1 is omitted: its runs already take less than 2s, so no point in speeding it up.

The matrix pays off most for DGA, which evaluates every remaining order at every step and so makes the most `distance()` calls; for RDGA the speedup shrinks as the sample size gets smaller.

**The objective value is unchanged.** All 72 runs (2 DGA runs plus 70 seeded RDGA runs) produced exactly the same objective value (total picking distance), number of picklists and number of picklist items with and without `-distmatrix`, seed for seed, and all of them are feasible. This is expected: the matrix only precomputes the same distance formula, so it changes lookup speed, not the values `distance()` returns.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our process for submitting pull requests to us, and please ensure
you follow the [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).


## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

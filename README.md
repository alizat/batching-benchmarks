# Joint Order Selection, Allocation, Batching and Picking 

This project contains accompanying code for Zalando Team BART's (Batching Algorithms) publication [Joint Order Selection, Allocation, Batching and Picking for Large Scale Warehouses](https://arxiv.org/abs/2401.04563).
The instances used to create results in the paper are stored in `instances.zip`.

## How to use

1. Clone this project and copy the files into your own project
2. Generate batching instances via `python generate_instances.py` (any Python 3.6+ works). For each generated instance (per default in the `instances` folder) four files will be created: `{articles, orders, parameters, warehouse_items}.json`. 
3. Run the Distance Greedy Algorithm (DGA) via `python solve_instances.py`. Two files will be stored in the respective instance folders: `batches.json` and `statistics.json`.
4. Run the Randomized DGA via `python solve_instances.py -a rdga`, optionally with `-k <N>` (default `1`) to sample `N` random orders per step and take the best of them, e.g. `python solve_instances.py -a rdga -k 50`.
5. Write your own solver to outperform these baseline algorithms :)


## Changes from the upstream repository

This fork adds two changes on top of the upstream implementation:

### 1. Precomputed location distance matrix

A **precomputed location distance matrix** speeds up `Instance.distance()` in `batching_problem/definitions.py`:

- Every `(row, aisle)` warehouse location allowed by an instance's `parameters` is enumerated once per instance (a 101x101 grid = 10,201 locations for the generator's default 100x100 warehouse), and a full location-to-location distance matrix (10,201 x 10,201) is precomputed by `Instance.build_distance_matrix()`, called once when an instance is read via `Instance.read()`.
- `Instance.location_index(row, aisle)` translates any `(row, aisle)` location into its flat index into that matrix.
- `Instance.distance(u, v)` now looks up this precomputed matrix instead of recomputing `row_distance` + `aisle_distance` from scratch for every pair of items. Since all zones share the same row/aisle extent, a single matrix is reused across every zone rather than building one per zone.
- The matrix is stored as a flat Python list rather than a numpy array: profiling showed numpy's per-call scalar-indexing overhead exceeds the cost of a plain list index at the call volumes this solver produces (millions of `distance()` calls per solve), so a flat list measured faster despite numpy being used to build the matrix itself.
- This is opt-in via `solve_instances.py`'s `-distmatrix` flag; the default (no flag) stays the original per-pair arithmetic.

#### Experimental results: distance matrix

Measured via controlled, same-process, interleaved A/B timing (original arithmetic vs. matrix lookup, run back-to-back on identical instance data to cancel out system-load noise), using the DGA baseline solver on the `small`/`medium`/`large` demo instances:

| Instance | Orders | Speedup |
|---|---:|---:|
| small-0 | 500 | ~18-20% faster |
| medium-0 | 5,000 | ~23-33% faster |
| large-0 | 50,000 | ~16-19% faster |

The total picking distance (objective value) is unaffected by this change -- the matrix only changes lookup speed, not the values `distance()` returns.

`large-0` was additionally run to full completion end-to-end (not a bounded/extrapolated sample) with each variant, confirming both the speedup and the correctness of the matrix at full scale:

| Variant | Wall time | Objective value | Picklists | Feasible |
|---|---:|---:|---:|---|
| Original arithmetic | 16,419s (4h 33m) | 605,888 | 10,882 | yes |
| Distance matrix | 13,811s (3h 50m) | 605,888 | 10,882 | yes |

Both variants produced an identical objective value and identical batch/picklist/item counts, as expected since the matrix only memoizes the same distance formula -- the matrix run finished ~2,608s (~43 min) faster.

### 2. Generalized Randomized DGA (`-k`)

The original Randomized DGA (RDGA) built each batch by repeatedly picking **one** random order from the remaining pool and adding it as-is, with no comparison against alternatives. This fork generalizes that single random pick into a **best-of-`k` random sample**:

- `distance_greedy_algorithm/solver.py`'s `greedy_solver()` now takes a `k: int = None` parameter (replacing the old `choose_random_order: bool` flag). `k=None` is plain DGA: deterministic, evaluates every remaining order at each step, unchanged from before. `k=<int>` is RDGA: at each step, `min(k, pool size)` orders are sampled uniformly at random, without replacement, from the remaining pool, and the best of that sample (by the same cost function DGA uses to compare candidates) is picked. `k=1` reproduces the original RDGA behavior.
- `solve_instances.py` exposes this as a new `-k` CLI flag (default `1`, ignored when `-a dga`): `python solve_instances.py -a rdga -k 50` samples 50 random orders per step and takes the best of them.
- This makes `k` a tunable quality/speed dial sitting between RDGA's original speed (`k=1`) and DGA's quality (large `k`).
- **Caveat**: the random-order-picking implementation changed under the hood (from `random.randrange` to `random.sample`), so `-a rdga` (or `-a rdga -k 1`) under a fixed seed no longer draws the exact same sequence of orders as before this change, even though both are a uniform single pick each step -- old RDGA run artifacts are not bit-for-bit reproducible against the new code. `-a dga` is unaffected and remains bit-identical.

#### Experimental results: generalized RDGA (`k`)

Measured via `python solve_instances.py -a rdga -k <K>` (and `-distmatrix` throughout, per the previous section) on the `medium-0` and `large-0` demo instances, compared against the existing DGA baseline:

**medium-0** (5,000 orders, item goal 2,659):

| Algorithm | Time | # Picklist items | # Picklists | Objective (total distance) |
|---|---:|---:|---:|---:|
| dga | 176s | 2,659 | 825 | 65,410 |
| rdga, k=500 | 20s | 2,659 | 889 | 69,022 |
| rdga, k=50 | 2s | 2,661 | 935 | 80,060 |
| rdga, k=1 | 1s | 2,659 | 894 | 136,912 |

**large-0** (50,000 orders, item goal 26,349; all `rdga` runs below use `-distmatrix`):

| Algorithm | Time | # Picklist items | # Picklists | Objective (total distance) |
|---|---:|---:|---:|---:|
| dga, original arithmetic | 16,419s (4h 33m) | 26,351 | 10,882 | 605,888 |
| dga, distance matrix | 13,811s (3h 50m) | 26,351 | 10,882 | 605,888 |
| rdga, k=500 | 155s (2m 35s) | 26,349 | 12,168 | 712,248 |
| rdga, k=50 | 26s | 26,350 | 13,680 | 859,622 |
| rdga, k=1 | 12s | 26,349 | 14,195 | 1,490,538 |

Observations:
- Quality improves and runtime grows monotonically with `k` on both instances, converging toward DGA's result: on `medium-0`, `k=500` lands within ~5.5% of DGA's objective while running ~9x faster than DGA; on `large-0`, `k=500` lands within ~17.6% of DGA's objective while running ~90-106x faster (155s vs. DGA's ~13,800-16,400s).
- The gap to DGA at a fixed `k` widens as the order pool grows, since a fixed sample size covers a shrinking fraction of a bigger pool (`k=500` is 10% of `medium-0`'s 5,000-order pool but only 1% of `large-0`'s 50,000-order pool).
- All runs are feasible (`Instance.check_feasibility()` passes) and land at or very near the requested item goal; picklist counts shrink toward DGA's as `k` grows, reflecting better order sequencing at higher `k`.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our process for submitting pull requests to us, and please ensure
you follow the [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).


## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

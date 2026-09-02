# Joint Order Selection, Allocation, Batching and Picking 

This project contains accompanying code for Zalando Team BART's (Batching Algorithms) publication [Joint Order Selection, Allocation, Batching and Picking for Large Scale Warehouses](https://arxiv.org/abs/2401.04563).
The instances used to create results in the paper are stored in `instances.zip`.

## How to use

1. Clone this project and copy the files into your own project
2. Generate batching instances via `python generate_instances.py` (any Python 3.6+ works). For each generated instance (per default in the `instances` folder) four files will be created: `{articles, orders, parameters, warehouse_items}.json`. 
3. Run the Distance Greedy Algorithm (DGA) via `python solve_instances.py`. Two files will be stored in the respective instance folders: `batches.json` and `statistics.json`.
4. Run the Randomized DGA via `python solve_instances.py -a rdga`
5. Write your own solver to outperform these baseline algorithms :)


## Changes from the upstream repository

This fork adds a **precomputed location distance matrix** to speed up `Instance.distance()` in `batching_problem/definitions.py`:

- Every `(row, aisle)` warehouse location allowed by an instance's `parameters` is enumerated once per instance (a 101x101 grid = 10,201 locations for the generator's default 100x100 warehouse), and a full location-to-location distance matrix (10,201 x 10,201) is precomputed by `Instance.build_distance_matrix()`, called once when an instance is read via `Instance.read()`.
- `Instance.location_index(row, aisle)` translates any `(row, aisle)` location into its flat index into that matrix.
- `Instance.distance(u, v)` now looks up this precomputed matrix instead of recomputing `row_distance` + `aisle_distance` from scratch for every pair of items. Since all zones share the same row/aisle extent, a single matrix is reused across every zone rather than building one per zone.
- The matrix is stored as a flat Python list rather than a numpy array: profiling showed numpy's per-call scalar-indexing overhead exceeds the cost of a plain list index at the call volumes this solver produces (millions of `distance()` calls per solve), so a flat list measured faster despite numpy being used to build the matrix itself.

### Experimental results

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

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our process for submitting pull requests to us, and please ensure
you follow the [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).


## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

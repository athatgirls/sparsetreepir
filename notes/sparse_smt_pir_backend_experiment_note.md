# Sparse SMT Concrete PIR Backend Experiment

This note summarizes the strong-baseline and executable-backend experiment run by:

```powershell
python .\run_sparse_smt_pir_backend_experiment.py
```

## Setup

- Full sparse SMT height: `10`
- Sparsities: `0.2, 0.5, 0.8`
- Trials per sparsity: `20`
- Direct strategies:
  - `weighted`
  - `count_balanced`
  - `hybrid`
  - `profile_balanced`
- Strong baseline:
  - `perfectized_treepir`
  - This baseline stores the full perfect-tree non-root levels and uses level-wise subdatabases.
- Executable backends:
  - `two_server_xor_pir`
  - A replicated two-server XOR-PIR microbenchmark with `32-byte` records
  - `single_server_matrix_pir_surrogate`
  - A single-server matrix-linear retrieval backend that is not claimed secure, but is computationally closer to SealPIR / Spiral than XOR-PIR

## Overall Results: XOR Backend

- `perfectized_treepir`
  - `protocol_colors = 10.00`
  - `stored_nodes = 2046.0`
  - `storage_ratio = 1.000`
  - `query_bytes = 514.0`
  - `server_parallel = 0.028 ms`
- `weighted`
  - `protocol_colors = 9.95`
  - `stored_nodes = 1022.0`
  - `storage_ratio = 0.500`
  - `query_bytes = 264.1`
  - `server_parallel = 0.013 ms`
- `count_balanced`
  - `protocol_colors = 9.95`
  - `stored_nodes = 1022.0`
  - `storage_ratio = 0.500`
  - `query_bytes = 260.1`
  - `server_parallel = 0.017 ms`
- `hybrid`
  - `protocol_colors = 9.95`
  - `stored_nodes = 1022.0`
  - `storage_ratio = 0.500`
  - `query_bytes = 264.1`
  - `server_parallel = 0.012 ms`
- `profile_balanced`
  - `protocol_colors = 9.95`
  - `stored_nodes = 1022.0`
  - `storage_ratio = 0.500`
  - `query_bytes = 264.9`
  - `server_parallel = 0.012 ms`

## Overall Results: Matrix Backend

- `perfectized_treepir`
  - `protocol_colors = 10.00`
  - `mat_query_bytes = 432.0`
  - `mat_response_bytes = 3392.0`
  - `mat_server_parallel = 0.013 ms`
- `weighted`
  - `protocol_colors = 9.95`
  - `mat_query_bytes = 405.3`
  - `mat_response_bytes = 3084.8`
  - `mat_server_parallel = 0.013 ms`
- `count_balanced`
  - `protocol_colors = 9.95`
  - `mat_query_bytes = 331.7`
  - `mat_response_bytes = 2525.3`
  - `mat_server_parallel = 0.011 ms`
- `hybrid`
  - `protocol_colors = 9.95`
  - `mat_query_bytes = 397.7`
  - `mat_response_bytes = 3034.1`
  - `mat_server_parallel = 0.012 ms`
- `profile_balanced`
  - `protocol_colors = 9.95`
  - `mat_query_bytes = 411.9`
  - `mat_response_bytes = 3098.1`
  - `mat_server_parallel = 0.011 ms`

## Sparsity-Specific Observation

At sparsity `0.8`:

- `perfectized_treepir` still stores `2046` nodes
- `perfectized_treepir` still uses the fixed batch width `h = 10`
- each direct strategy stores only about `408` nodes
- each direct strategy uses only about `m = 9.85` active colors on average
- the storage ratio drops to about `0.199`
- `weighted` lowers XOR query bytes to about `110.5`
- `count_balanced` lowers XOR query bytes to about `106.0`
- `profile_balanced` lowers XOR query bytes to about `114.8` while reducing the size gap to about `1`
- direct strategies reduce XOR parallel server time to about `0.009-0.011 ms`

This is the cleanest setting showing why direct storage of active proof-bearing nodes matters on sparse SMTs.

## Main Takeaways

- Compared with a perfectized TreePIR-style organization, the direct virtual-swapped design substantially reduces storage on sparse SMTs.
- The direct scheme also uses the exact minimum active batch width `m` instead of padding to the full tree height `h`.
- These storage savings translate into concrete reductions in query bytes and server work under an executable replicated PIR backend.
- On the matrix backend, `count_balanced` gives the smallest query bytes; the parallel times remain in a similarly small range across direct strategies.
- `profile_balanced` is now included in the backend-shaped runs. It is the strongest structural balancer, but it is not always the byte-minimizing layout for the matrix surrogate, which confirms that exact-width structural balance and backend-specific packing cost are related but distinct objectives.
- These executable backends should be read as a bridge between cost proxies and future production SealPIR / Spiral integration, not as a replacement for those systems.

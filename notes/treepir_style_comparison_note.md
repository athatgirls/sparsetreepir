# TreePIR-style comparison matrix

This note reorganizes the current experiments in the same spirit as TreePIR's evaluation section: separate the structural organization cost, the client-side batch width, the color-store balance, and the concrete PIR API measurements.

## Representative setting: h=24, 99.95% empty leaves

| Scheme | Stored records | Digest KB | Public index/metadata KB | Width | Max bucket | Gap | Full SimplePIR online KB | Backend status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Perfectized-TreePIR | 33,554,430 | 1,048,575.94 | 0 | 24 | - | - | - | structural-only |
| PBC-active | 50,328 | 1,572.75 | 786.38 | 26 | 1,974 | - | - | PBC formula |
| Flat-normal-PIR-m | 16,776 | 524.25 | 393.19 | 17 | 16,776 | 0 | 276.78 | full-simplepir-api |
| Pruned-TreePIR-h | 16,776 | 524.25 | 393.19 | 24 | 3,312 | 3,310 | 59 | full-simplepir-api |
| Profile-balanced | 16,776 | 524.25 | 393.19 | 17 | 992 | 26 | 67.47 | full-simplepir-api |

## Aggregate observations over the full SimplePIR settings

- Profile-balanced reduces full SimplePIR online communication versus flat normal PIR by 63.79% to 75.62% (mean 70.82%).
- Profile-balanced reduces the query width versus Pruned-TreePIR-h by 29.17% to 55% (mean 41.53%).
- Its online communication compared with Pruned-TreePIR-h ranges from -14.35% reduction to 26.17% reduction (mean 3.98%). Negative values mean a parameter-tiering loss.
- The profile-balanced maximum bucket is within a factor 1--1.019 of the equal-split ideal N/m on these settings.

## How this mirrors TreePIR's evaluation logic

- Perfectized-TreePIR is kept as a structural baseline because materializing a full h-level SMT is too large for a fair full API run.
- PBC-active adapts TreePIR's main generic-batch-code foil to the active proof-object database: three replicated records, about 1.5m buckets, and bucket size about 2N/m. It is formula-only here, matching TreePIR's high-level accounting rather than a concrete backend run.
- Flat-normal-PIR-m is the ordinary PIR baseline: it keeps one active-node database and pays for m independent proof positions.
- Pruned-TreePIR-h is not an original TreePIR baseline. It is an adversarial pruning-only ablation designed to answer the reviewer question, 'is this just TreePIR after deleting empty nodes?'
- Profile-balanced is our final organization: active-node storage, exact active width m, served-interval lookup, and balanced color stores.

The most defensible claim is therefore not that profile-balanced always has the smallest SimplePIR byte count under every parameter tier. The stronger and more stable claim is that it turns SMT proof retrieval into a compact exact-width interface, keeps the bucket profile close to the ideal split, and substantially reduces the cost of a flat normal-PIR proof retrieval.

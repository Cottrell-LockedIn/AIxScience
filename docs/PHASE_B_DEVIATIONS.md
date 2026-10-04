# Phase B implementation deviations

Recorded before generating any `results/stats/*.csv` or `results/verdicts/*.json`.
`docs/PHASE_B_PREREGISTRATION.md` and `configs/stats_v1.yaml` remain unchanged.

## Distance-matrix applicability

The requested `distance_matrix.csv` lists every table × statistic combination, but the
pre-registration defines `rms_z` for KPI, feature and covariate tables, and energy distance
and MMD² for embeddings only. To avoid adding unregistered statistics, the CSV contains the
full requested Cartesian layout with an `applicable` flag. Undefined combinations have
`NaN` values off the diagonal; diagonal values are zero. Defined statistics retain the
pre-registered formulas and permutation tests.

## Pair-specific permutation seeds

The pre-registration supplies base seed `20261003`; the handoff requires a fixed seed
derivation per ordered pair. The implementation uses `base_seed + pair_index`, where
`pair_index` is zero-based in the pre-registered order:
`Batch_1/Batch_2`, `Batch_1/Batch_3`, `Batch_2/Batch_3`. The resulting seeds are
20261003, 20261004 and 20261005. Each pair's permutation priority matrix is shared by its
feature, aggregate, embedding, residualised and leave-one-out permutation statistics.

## ETD reference sample size

The embedding index has 14 Batch_3 ETD images, while the registered reference split size
is 7 + 10. ETD is not pooled with SE; therefore the ETD null uses 7 + 7 (all 14 available
Batch_3 ETD images), and ETD covariate residualisation fits only its 27 available images
using covariates standardised from all 31 image rows.
Other scalar, BSE and Inlens null splits retain the registered 7 + 10 sizes and their
residualisation uses all 31 images.

## Covariate aggregate BH display

The four preregistered BH families define covariate feature tests, while the requested
distance matrix also asks for a BH-adjusted p-value on aggregate covariate `rms_z`.
That display-only aggregate value is BH-adjusted across the three ordered pair tests;
acquisition-drift decisions continue to use the preregistered covariate-feature family.

## Residualised distance-matrix adjustment

Residualised permutation p-values are displayed with a BH adjustment performed separately
within the same corresponding test family. Raw p-values and their pre-registered BH
adjustments remain unchanged and are the values used by G1 and verdict rules. G2 continues
to use the pre-registered unadjusted residualised p-value.

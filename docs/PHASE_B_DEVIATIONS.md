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

## Verdict acquisition-range flags

For each batch covariate, the requested `flag` is true only when that batch's image-level
median is strictly below the Batch_3 5th percentile or strictly above its 95th percentile.
This descriptive range flag is separate from `acquisition_drift_suspected`, which continues
to use the pre-registered BH-adjusted covariate tests. Batch_3's own median is compared with
the same Batch_3 training percentiles.

## Verdict driver tie order

Drivers are sorted by descending absolute effect size, then ascending feature name to make
ties deterministic. If no feature contrast has BH p < 0.05, the requested top-five fallback
uses the same ordering and the reason sentence explicitly states that none is significant.

## Reference-batch verdict evidence

Acquisition drift is defined only for a pair against Batch_3, so the Batch_3 verdict records
`acquisition_drift_suspected: false` as the reference and cites the Batch_1-vs-Batch_3 drift
row for provenance. Its embedding evidence reports the Batch_3 diagonal self-distance rows
(energy and MMD² are descriptive zeros with the diagonal p-values); they do not affect the
Batch_3 label, which uses only the registered reference leave-one-out rule.

## Code made literal to prereg (found by independent review)

Recorded before regenerating any statistics or verdict outputs. The RBF kernel bandwidth is
now calculated once per embedding channel and per raw/residualised variant from all images
of that channel, then reused for the observed MMD², its label permutations and the
split-half null. Raw bandwidth uses the L2-normalised vectors; residualised bandwidth uses
the unnormalised residual vectors. This corrects the prior pair-subset bandwidth and is
expected to change Batch_2-vs-Batch_3 raw BSE MMD² from approximately 0.12245 to 0.11663.

All Batch_3 splits are enumerated for display when the number of combinations is at most
50,000 (19,448 splits for 7+10 and 3,432 selections for ETD 7+7). The `band95`/`band99`
fields and all decisions continue to use the registered 1,000-split plan. Exact bands and
`frac_splits_exceeding` are display-only. In `null_bands.csv`, exact fractions are
pair-specific: the fraction of exact null statistics greater than or equal to that pair's
observed absolute feature z, aggregate RMS z, or embedding statistic. Non-reference pairs
and structurally inapplicable comparisons have no exact comparison.

## Exploratory acquisition-confound probe

Recorded before generating `exploratory_confound_probe.csv`; this is post-hoc and is not
used by any registered gate, label or verdict rule. It was added in response to the
independent review's request to inspect single-covariate and random-covariate residualisation
as a confound sensitivity. Single-covariate BSE energy/MMD² and the covariate-on-batch OLS
use the existing 2,000-permutation plan for each ordered vs-Batch_3 pair. The random
Gaussian probe uses 200 eight-column draws from `default_rng(20264003)` and reports the
median and 5th percentile of energy. These exploratory values are reported as observed and
are not tuned to reviewer estimates.

## Empty LOO-set serialization

Recorded before regenerating contrast outputs. Rows with zero leave-one-out outliers now
write the literal `none` in `loo_outlier_ids`, so CSV readers preserve an explicit empty
set instead of converting an empty field to `NaN`. The statistics and verdict parsers map
`none` back to an empty list; gate definitions are unchanged.

# Validation of `features_f01_f11`

Inputs: results/features/features_f01_f11.parquet (sha256 bfe253c224c0), covariates from results/artefacts_per_image.parquet, acquisition groups from results/audit/images.csv, threshold sensitivity from results/kpi_sensitivity.parquet. Config de199d6c8d69, git eca6fa7, seed 0, 1000 bootstrap resamples, 10000 permutations.

## Headline

- Decisions: {'investigate': 11}. Confounded with acquisition group: F05_c2_count_density_per_Mpx, F06_c2_clark_evans_R.
- Raw batch effects with q < 0.05 (vs Batch_3, all images): none. After residualising on the covariates: none.
- Batch classifier accuracy (chance = majority 0.548): LOIO 0.452 / LOGO 0.323 without covariates; LOIO 0.645 / LOGO 0.677 with covariates. LOIO - LOGO gap +0.129 (without) / -0.032 (with); with - without covariates gap +0.194 (LOIO) / +0.355 (LOGO).
- Batch_3 images flagged by leave-one-out (|z| > 3.0): 0grcilhi (F01_c0_area_fraction z=+4.4, F07_c2_solidity_area_weighted_median z=-3.2, F08_c0_local_thickness_median_px z=+4.3), hzumfsms (F01_c0_area_fraction z=+4.9, F03_c2_eqdiam_median_px z=-3.3, F08_c0_local_thickness_median_px z=+4.3, F10_c0_fraction_iqr_512px z=+8.3), mgxahqnk (F10_c0_fraction_iqr_512px z=+3.7), tuy3zymq (F03_c2_eqdiam_median_px z=+3.3, F07_c2_solidity_area_weighted_median z=-4.3), vc2whyaq (F09_c0_chord_anisotropy_h_over_v z=+3.1), x77cy643 (F04_c2_eqdiam_p90_px z=+4.5), xgj4xftb (F03_c2_eqdiam_median_px z=+3.3).

## Hard rules applied

- The image (8-character id) is the independent unit: n = 31 images (Batch_1 7, Batch_2 7, Batch_3 17). Tiles are pseudo-replicates and never enter any resample, permutation or fold here; every statistic below is image-level.
- Acquisition group = (image height, XResolution tag) from the audit: 13 groups; leave-one-acquisition-group-out keeps every image of a group (all its detector views) on one side of the split.
- Scaling, imputation and the classifier are fitted inside each fold only.
- Phase identities (class 2 bright = silicon, class 1 mid = graphite, class 0 dark = void/pore) are stated by Polaron, not image-verified; Si vs SiOx is indistinguishable in BSE; binder/additive is lumped into class 0/1. No further chemistry claims.
- Units are pixels. nm values would hold only if 25 nm/px is true (tag written by software, unconfirmed).
- Batch_3 is the reference batch but not error-free: the leave-one-out check on this table flags 0grcilhi, hzumfsms, mgxahqnk, tuy3zymq, vc2whyaq, x77cy643, xgj4xftb; batch tests are reported with and without them.
- Acquisition covariates (noise, sharpness, curtaining, stripe, edge charging, mean grey) are measured and kept as covariates; images are never altered.
- p-values are image-level permutation p with the effect size next to them; `investigate` is a first-class outcome.

## Decision table (pre-declared rule)

keep if rank-stability >= 0.7 AND not acquisition_confounded AND threshold sensitivity < 0.5 x Batch_3 MAD; drop if degenerate; otherwise investigate. A feature without a threshold-sensitivity measurement cannot satisfy the third condition and is `investigate`.

| feature                               | decision    |   rank_stability | acquisition_confounded   |   threshold_sensitivity |   mad_Batch_3 |   sens_over_mad | reasons                                                                                                                                               | notes                                                                                   |
|:--------------------------------------|:------------|-----------------:|:-------------------------|------------------------:|--------------:|----------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------|
| F01_c0_area_fraction                  | investigate |            0.691 | False                    |                     nan |      0.00888  |             nan | rank-stability 0.69 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F02_c2_area_fraction                  | investigate |            0.539 | False                    |                     nan |      0.0331   |             nan | rank-stability 0.54 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F03_c2_eqdiam_median_px               | investigate |            0.628 | False                    |                     nan |      0.117    |             nan | rank-stability 0.63 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F04_c2_eqdiam_p90_px                  | investigate |            0.427 | False                    |                     nan |      3.95     |             nan | rank-stability 0.43 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F05_c2_count_density_per_Mpx          | investigate |            0.437 | True                     |                     nan |     83.6      |             nan | rank-stability 0.44 < 0.7; acquisition_confounded (z_group 3.5 > z_batch -0.7, p_group 0.0002); no threshold-sensitivity measurement for this feature |                                                                                         |
| F06_c2_clark_evans_R                  | investigate |            0.746 | True                     |                     nan |      0.0621   |             nan | acquisition_confounded (z_group 2.5 > z_batch 1.8, p_group 0.0080); no threshold-sensitivity measurement for this feature                             | abs(rho) >= 0.5 with mean_grey (rho +0.53); compare raw vs residualised batch tests     |
| F07_c2_solidity_area_weighted_median  | investigate |            0.561 | False                    |                     nan |      0.0636   |             nan | rank-stability 0.56 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F08_c0_local_thickness_median_px      | investigate |          nan     | False                    |                     nan |      2.97     |             nan | rank-stability nan < 0.7; no threshold-sensitivity measurement for this feature                                                                       |                                                                                         |
| F09_c0_chord_anisotropy_h_over_v      | investigate |            0.225 | False                    |                     nan |      0.0299   |             nan | rank-stability 0.22 < 0.7; no threshold-sensitivity measurement for this feature                                                                      | abs(rho) >= 0.5 with hstripe_score (rho +0.55); compare raw vs residualised batch tests |
| F10_c0_fraction_iqr_512px             | investigate |            0.244 | False                    |                     nan |      0.00697  |             nan | rank-stability 0.24 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F11_c2_perimeter_fraction_adjacent_c0 | investigate |            0.39  | False                    |                     nan |      0.000555 |             nan | rank-stability 0.39 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |

Counts: {'investigate': 11}

## Stability (stability.csv)

rank_stability = mean Spearman between the observed ranking of batch medians and the ranking in each image-level bootstrap resample (resampling images within batch); rank_order_preserved_frac = share of resamples with the identical order. cv_Batch_3 = sd/mean over Batch_3 images; threshold_sensitivity = median over images of the largest |change| under +/-10 % threshold scaling (only measured for the class fractions).

| feature                               |   rank_stability |   rank_order_preserved_frac |   median_Batch_1 |   median_Batch_2 |   median_Batch_3 |   cv_Batch_3 |   mad_Batch_3 |   threshold_sensitivity | degenerate   |
|:--------------------------------------|-----------------:|----------------------------:|-----------------:|-----------------:|-----------------:|-------------:|--------------:|------------------------:|:-------------|
| F01_c0_area_fraction                  |            0.691 |                       0.45  |         0.0909   |          0.101   |         0.102    |       0.16   |      0.00888  |                     nan | False        |
| F02_c2_area_fraction                  |            0.539 |                       0.483 |         0.0891   |          0.0971  |         0.101    |       0.231  |      0.0331   |                     nan | False        |
| F03_c2_eqdiam_median_px               |            0.628 |                       0.264 |         8.14     |          7.98    |         8.14     |       0.0329 |      0.117    |                     nan | False        |
| F04_c2_eqdiam_p90_px                  |            0.427 |                       0.481 |        23.9      |         24.7     |        26.6      |       0.161  |      3.95     |                     nan | False        |
| F05_c2_count_density_per_Mpx          |            0.437 |                       0.378 |       116        |        109       |       131        |       0.405  |     83.6      |                     nan | False        |
| F06_c2_clark_evans_R                  |            0.746 |                       0.551 |         0.734    |          0.678   |         0.724    |       0.0629 |      0.0621   |                     nan | False        |
| F07_c2_solidity_area_weighted_median  |            0.561 |                       0.425 |         0.869    |          0.87    |         0.824    |       0.103  |      0.0636   |                     nan | False        |
| F08_c0_local_thickness_median_px      |          nan     |                       0.22  |        26        |         26       |        26        |       0.167  |      2.97     |                     nan | False        |
| F09_c0_chord_anisotropy_h_over_v      |            0.225 |                       0.188 |         1.16     |          1.14    |         1.16     |       0.0345 |      0.0299   |                     nan | False        |
| F10_c0_fraction_iqr_512px             |            0.244 |                       0.298 |         0.0403   |          0.0487  |         0.0476   |       0.293  |      0.00697  |                     nan | False        |
| F11_c2_perimeter_fraction_adjacent_c0 |            0.39  |                       0.308 |         0.000708 |          0.00099 |         0.000569 |       0.801  |      0.000555 |                     nan | False        |

## Acquisition confounding (confound.csv)

Spearman rho with each covariate (BSE channel; edge charging from Inlens). Association with acquisition group vs with batch: Kruskal-Wallis H with an image-level permutation null; z = (H - mean null) / sd null makes the two comparable despite the different number of levels. acquisition_confounded = z_group > z_batch and p_group < 0.05. p_group_within_batch: do groups still explain the feature after centring on batch medians (labels shuffled within batch)?

| feature                               |   rho_noise_sigma |   rho_sharpness |   rho_curtaining_score |   rho_hstripe_score |   rho_edge_charging_inlens |   rho_mean_grey |   z_group |   p_group |   z_batch |   p_batch |   p_group_within_batch | acquisition_confounded   | covariate_correlated   |
|:--------------------------------------|------------------:|----------------:|-----------------------:|--------------------:|---------------------------:|----------------:|----------:|----------:|----------:|----------:|-----------------------:|:-------------------------|:-----------------------|
| F01_c0_area_fraction                  |           -0.276  |         -0.259  |                 0.208  |              0.174  |                   -0.183   |          -0.34  |    0.205  |    0.409  |    2.14   |    0.0417 |                 0.353  | False                    | False                  |
| F02_c2_area_fraction                  |           -0.175  |         -0.174  |                 0.375  |              0.0742 |                    0.163   |           0.331 |    0.757  |    0.225  |   -0.943  |    0.899  |                 0.413  | False                    | False                  |
| F03_c2_eqdiam_median_px               |           -0.232  |         -0.241  |                 0.0334 |              0.0976 |                    0.278   |           0.163 |    1.26   |    0.111  |   -0.799  |    0.799  |                 0.0615 | False                    | False                  |
| F04_c2_eqdiam_p90_px                  |           -0.139  |         -0.169  |                -0.188  |              0.106  |                   -0.0919  |          -0.355 |    0.997  |    0.164  |    0.0227 |    0.37   |                 0.101  | False                    | False                  |
| F05_c2_count_density_per_Mpx          |           -0.177  |         -0.167  |                 0.267  |              0.073  |                    0.448   |           0.472 |    3.5    |    0.0002 |   -0.674  |    0.706  |                 0.0009 | True                     | False                  |
| F06_c2_clark_evans_R                  |           -0.173  |         -0.169  |                 0.262  |             -0.0129 |                    0.398   |           0.534 |    2.54   |    0.008  |    1.8    |    0.0622 |                 0.0944 | True                     | True                   |
| F07_c2_solidity_area_weighted_median  |            0.153  |          0.162  |                -0.101  |             -0.0214 |                   -0.307   |          -0.148 |    1.65   |    0.058  |   -0.539  |    0.631  |                 0.24   | False                    | False                  |
| F08_c0_local_thickness_median_px      |            0.0772 |          0.0753 |                -0.049  |             -0.0494 |                   -0.238   |          -0.381 |    0.188  |    0.414  |   -1.01   |    0.949  |                 0.419  | False                    | False                  |
| F09_c0_chord_anisotropy_h_over_v      |           -0.267  |         -0.275  |                -0.324  |              0.553  |                    0.00887 |           0.192 |    1.7    |    0.0508 |   -0.806  |    0.79   |                 0.195  | False                    | True                   |
| F10_c0_fraction_iqr_512px             |            0.0317 |          0.05   |                 0.0726 |             -0.148  |                   -0.138   |          -0.175 |   -0.0468 |    0.502  |   -0.454  |    0.577  |                 0.468  | False                    | False                  |
| F11_c2_perimeter_fraction_adjacent_c0 |            0.0914 |          0.0758 |                 0.0746 |             -0.215  |                    0.0254  |           0.188 |    1.68   |    0.056  |   -0.92   |    0.877  |                 0.0074 | False                    | False                  |

covariate_correlated (informational, not part of the keep rule) = some abs(rho) >= 0.5 with p < 0.05; for such features compare the raw and residualised batch tests below.

## Batch tests (batch_tests.csv)

Effect = (median test batch - median Batch_3) / MAD(Batch_3, scaled 1.4826); p = image-level permutation p of the median difference; q = Benjamini-Hochberg across features within each comparison.

Raw features, all Batch_3 images:

| feature                               | comparison         |   n_test |   n_ref |   effect_shift_over_mad |   p_perm |   q_bh |
|:--------------------------------------|:-------------------|---------:|--------:|------------------------:|---------:|-------:|
| F01_c0_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      17 |                 -1.24   |    0.047 |  0.517 |
| F02_c2_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.348  |    0.574 |  1     |
| F03_c2_eqdiam_median_px               | Batch_1_vs_Batch_3 |        7 |      17 |                  0      |    1     |  1     |
| F04_c2_eqdiam_p90_px                  | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.676  |    0.218 |  0.909 |
| F05_c2_count_density_per_Mpx          | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.173  |    0.69  |  1     |
| F06_c2_clark_evans_R                  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.158  |    0.844 |  1     |
| F07_c2_solidity_area_weighted_median  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.706  |    0.331 |  0.909 |
| F08_c0_local_thickness_median_px      | Batch_1_vs_Batch_3 |        7 |      17 |                  0      |    1     |  1     |
| F09_c0_chord_anisotropy_h_over_v      | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.213  |    0.623 |  1     |
| F10_c0_fraction_iqr_512px             | Batch_1_vs_Batch_3 |        7 |      17 |                 -1.05   |    0.288 |  0.909 |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_1_vs_Batch_3 |        7 |      17 |                  0.25   |    0.841 |  1     |
| F01_c0_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.0625 |    1     |  1     |
| F02_c2_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.106  |    0.692 |  0.951 |
| F03_c2_eqdiam_median_px               | Batch_2_vs_Batch_3 |        7 |      17 |                 -1.36   |    0.399 |  0.732 |
| F04_c2_eqdiam_p90_px                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.487  |    0.142 |  0.732 |
| F05_c2_count_density_per_Mpx          | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.256  |    0.488 |  0.768 |
| F06_c2_clark_evans_R                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.74   |    0.119 |  0.732 |
| F07_c2_solidity_area_weighted_median  | Batch_2_vs_Batch_3 |        7 |      17 |                  0.714  |    0.335 |  0.732 |
| F08_c0_local_thickness_median_px      | Batch_2_vs_Batch_3 |        7 |      17 |                  0      |    1     |  1     |
| F09_c0_chord_anisotropy_h_over_v      | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.68   |    0.273 |  0.732 |
| F10_c0_fraction_iqr_512px             | Batch_2_vs_Batch_3 |        7 |      17 |                  0.16   |    1     |  1     |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_2_vs_Batch_3 |        7 |      17 |                  0.759  |    0.321 |  0.732 |

Raw features, Batch_3 without 0grcilhi, hzumfsms, mgxahqnk, tuy3zymq, vc2whyaq, x77cy643, xgj4xftb:

| feature                               | comparison         |   n_test |   n_ref |   effect_shift_over_mad |   p_perm |   q_bh |
|:--------------------------------------|:-------------------|---------:|--------:|------------------------:|---------:|-------:|
| F01_c0_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      10 |                 -0.795  |    0.238 |  1     |
| F02_c2_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      10 |                 -0.236  |    0.735 |  1     |
| F03_c2_eqdiam_median_px               | Batch_1_vs_Batch_3 |        7 |      10 |                  0      |    1     |  1     |
| F04_c2_eqdiam_p90_px                  | Batch_1_vs_Batch_3 |        7 |      10 |                 -0.768  |    0.424 |  1     |
| F05_c2_count_density_per_Mpx          | Batch_1_vs_Batch_3 |        7 |      10 |                 -0.206  |    0.668 |  1     |
| F06_c2_clark_evans_R                  | Batch_1_vs_Batch_3 |        7 |      10 |                  0.335  |    0.836 |  1     |
| F07_c2_solidity_area_weighted_median  | Batch_1_vs_Batch_3 |        7 |      10 |                  0.281  |    0.772 |  1     |
| F08_c0_local_thickness_median_px      | Batch_1_vs_Batch_3 |        7 |      10 |                  0      |    1     |  1     |
| F09_c0_chord_anisotropy_h_over_v      | Batch_1_vs_Batch_3 |        7 |      10 |                 -0.15   |    0.857 |  1     |
| F10_c0_fraction_iqr_512px             | Batch_1_vs_Batch_3 |        7 |      10 |                 -0.585  |    0.532 |  1     |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_1_vs_Batch_3 |        7 |      10 |                  0.716  |    0.502 |  1     |
| F01_c0_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      10 |                 -0.0153 |    0.988 |  1     |
| F02_c2_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      10 |                  0.0932 |    0.991 |  1     |
| F03_c2_eqdiam_median_px               | Batch_2_vs_Batch_3 |        7 |      10 |                 -1.37   |    0.526 |  0.826 |
| F04_c2_eqdiam_p90_px                  | Batch_2_vs_Batch_3 |        7 |      10 |                 -0.501  |    0.451 |  0.826 |
| F05_c2_count_density_per_Mpx          | Batch_2_vs_Batch_3 |        7 |      10 |                 -0.314  |    0.378 |  0.826 |
| F06_c2_clark_evans_R                  | Batch_2_vs_Batch_3 |        7 |      10 |                 -0.755  |    0.102 |  0.826 |
| F07_c2_solidity_area_weighted_median  | Batch_2_vs_Batch_3 |        7 |      10 |                  0.289  |    0.723 |  0.994 |
| F08_c0_local_thickness_median_px      | Batch_2_vs_Batch_3 |        7 |      10 |                  0      |    1     |  1     |
| F09_c0_chord_anisotropy_h_over_v      | Batch_2_vs_Batch_3 |        7 |      10 |                 -1.02   |    0.35  |  0.826 |
| F10_c0_fraction_iqr_512px             | Batch_2_vs_Batch_3 |        7 |      10 |                  0.303  |    0.519 |  0.826 |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_2_vs_Batch_3 |        7 |      10 |                  1.54   |    0.304 |  0.826 |

Residualised on the acquisition covariates, all Batch_3 images:

| feature                               | comparison         |   n_test |   n_ref |   effect_shift_over_mad |   p_perm |   q_bh |
|:--------------------------------------|:-------------------|---------:|--------:|------------------------:|---------:|-------:|
| F01_c0_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.0671 |   1      |  1     |
| F02_c2_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.39   |   0.471  |  0.799 |
| F03_c2_eqdiam_median_px               | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.0958 |   0.835  |  1     |
| F04_c2_eqdiam_p90_px                  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.424  |   0.439  |  0.799 |
| F05_c2_count_density_per_Mpx          | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.795  |   0.299  |  0.799 |
| F06_c2_clark_evans_R                  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.042  |   1      |  1     |
| F07_c2_solidity_area_weighted_median  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.434  |   0.58   |  0.799 |
| F08_c0_local_thickness_median_px      | Batch_1_vs_Batch_3 |        7 |      17 |                  0.511  |   0.357  |  0.799 |
| F09_c0_chord_anisotropy_h_over_v      | Batch_1_vs_Batch_3 |        7 |      17 |                  1.03   |   0.208  |  0.799 |
| F10_c0_fraction_iqr_512px             | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.266  |   0.581  |  0.799 |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.71   |   0.46   |  0.799 |
| F01_c0_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.221  |   0.84   |  1     |
| F02_c2_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.4    |   0.463  |  1     |
| F03_c2_eqdiam_median_px               | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.164  |   0.764  |  1     |
| F04_c2_eqdiam_p90_px                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -1.13   |   0.0188 |  0.207 |
| F05_c2_count_density_per_Mpx          | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.0327 |   1      |  1     |
| F06_c2_clark_evans_R                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.378  |   0.241  |  1     |
| F07_c2_solidity_area_weighted_median  | Batch_2_vs_Batch_3 |        7 |      17 |                  0.569  |   0.369  |  1     |
| F08_c0_local_thickness_median_px      | Batch_2_vs_Batch_3 |        7 |      17 |                  0.542  |   0.717  |  1     |
| F09_c0_chord_anisotropy_h_over_v      | Batch_2_vs_Batch_3 |        7 |      17 |                  0.0127 |   1      |  1     |
| F10_c0_fraction_iqr_512px             | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.246  |   0.469  |  1     |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.393  |   0.614  |  1     |

## Session-leakage evidence: LOIO vs LOGO (loio_logo.csv)

Logistic regression (balanced class weights, median imputation + standardisation fitted inside each fold) predicting batch from the 11 features, with and without the 6 acquisition covariates as extra inputs. chance_majority = accuracy of always predicting the largest batch.

| model   | split   | covariates   |   n_images |   n_folds |   n_features |   accuracy |   balanced_accuracy |   chance_majority |   recall_Batch_1 |   recall_Batch_2 |   recall_Batch_3 |
|:--------|:--------|:-------------|-----------:|----------:|-------------:|-----------:|--------------------:|------------------:|-----------------:|-----------------:|-----------------:|
| logreg  | LOIO    | without      |         31 |        31 |           11 |      0.452 |               0.359 |             0.548 |            0.143 |            0.286 |            0.647 |
| logreg  | LOIO    | with         |         31 |        31 |           17 |      0.645 |               0.56  |             0.548 |            0.286 |            0.571 |            0.824 |
| logreg  | LOGO    | without      |         31 |        13 |           11 |      0.323 |               0.224 |             0.548 |            0     |            0.143 |            0.529 |
| logreg  | LOGO    | with         |         31 |        13 |           17 |      0.677 |               0.608 |             0.548 |            0.429 |            0.571 |            0.824 |

Gaps (accuracy): loio_minus_logo_without_cov = +0.129; loio_minus_logo_with_cov = -0.032; with_minus_without_cov_loio = +0.194; with_minus_without_cov_logo = +0.355

Reading: a positive LOIO - LOGO gap means part of the LOIO accuracy comes from images of the same acquisition session being in the training set; a positive with - without gap means the covariates themselves carry batch information. Both are evidence that acquisition, not only material, separates the batches.

## Reference batch leave-one-out (reference_loo.csv), |z| > 3.0

| sample_id   | flags                                                                                                                                  |
|:------------|:---------------------------------------------------------------------------------------------------------------------------------------|
| 0grcilhi    | F01_c0_area_fraction z=+4.4, F07_c2_solidity_area_weighted_median z=-3.2, F08_c0_local_thickness_median_px z=+4.3                      |
| hzumfsms    | F01_c0_area_fraction z=+4.9, F03_c2_eqdiam_median_px z=-3.3, F08_c0_local_thickness_median_px z=+4.3, F10_c0_fraction_iqr_512px z=+8.3 |
| mgxahqnk    | F10_c0_fraction_iqr_512px z=+3.7                                                                                                       |
| tuy3zymq    | F03_c2_eqdiam_median_px z=+3.3, F07_c2_solidity_area_weighted_median z=-4.3                                                            |
| vc2whyaq    | F09_c0_chord_anisotropy_h_over_v z=+3.1                                                                                                |
| x77cy643    | F04_c2_eqdiam_p90_px z=+4.5                                                                                                            |
| xgj4xftb    | F03_c2_eqdiam_median_px z=+3.3                                                                                                         |

Flagged on this table (excluded in the `excl_loo_flagged` rows of batch_tests.csv): 0grcilhi, hzumfsms, mgxahqnk, tuy3zymq, vc2whyaq, x77cy643, xgj4xftb.

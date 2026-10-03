# Validation of `kpi_per_image`

Inputs: results/kpi_per_image.parquet (sha256 bbf2e8cd28d2), covariates from results/artefacts_per_image.parquet, acquisition groups from results/audit/images.csv, threshold sensitivity from results/kpi_sensitivity.parquet. Config 1bec114301c3, git d593ac3, seed 0, 1000 bootstrap resamples, 10000 permutations.

## Headline

- Decisions: {'investigate': 8}. Confounded with acquisition group: c2_count_density_per_Mpx, c2_eqdiam_median_px, c2_eqdiam_p90_px, c0_region_area_mean_px.
- Raw batch effects with q < 0.05 (vs Batch_3, all images): c0_region_eqdiam_median_px Batch_1_vs_Batch_3 effect -1.96 MAD (p 0.004, q 0.032). After residualising on the covariates: none.
- Batch classifier accuracy (chance = majority 0.548): LOIO 0.581 / LOGO 0.452 without covariates; LOIO 0.613 / LOGO 0.581 with covariates. LOIO - LOGO gap +0.129 (without) / +0.032 (with); with - without covariates gap +0.032 (LOIO) / +0.129 (LOGO).
- Batch_3 images flagged by leave-one-out (|z| > 3.0): 0grcilhi (frac_c0 z=+3.0), cfe5vt7s (c2_eqdiam_median_px z=+3.3), hzumfsms (frac_c0 z=+3.7), ufdvpb81 (c2_eqdiam_median_px z=+6.7), vc2whyaq (c2_eqdiam_median_px z=+10.8).

## Hard rules applied

- The image (8-character id) is the independent unit: n = 31 images (Batch_1 7, Batch_2 7, Batch_3 17). Tiles are pseudo-replicates and never enter any resample, permutation or fold here; every statistic below is image-level.
- Acquisition group = (image height, XResolution tag) from the audit: 13 groups; leave-one-acquisition-group-out keeps every image of a group (all its detector views) on one side of the split.
- Scaling, imputation and the classifier are fitted inside each fold only.
- Phase identities (class 2 bright = silicon, class 1 mid = graphite, class 0 dark = void/pore) are stated by Polaron, not image-verified; Si vs SiOx is indistinguishable in BSE; binder/additive is lumped into class 0/1. No further chemistry claims.
- Units are pixels. nm values would hold only if 25 nm/px is true (tag written by software, unconfirmed).
- Batch_3 is the reference batch but not error-free: the leave-one-out check flags vc2whyaq, ufdvpb81, hzumfsms; batch tests are reported with and without them.
- Acquisition covariates (noise, sharpness, curtaining, stripe, edge charging, mean grey) are measured and kept as covariates; images are never altered.
- p-values are image-level permutation p with the effect size next to them; `investigate` is a first-class outcome.

## Decision table (pre-declared rule)

keep if rank-stability >= 0.7 AND not acquisition_confounded AND threshold sensitivity < 0.5 x Batch_3 MAD; drop if degenerate; otherwise investigate. A feature without a threshold-sensitivity measurement cannot satisfy the third condition and is `investigate`.

| feature                    | decision    |   rank_stability | acquisition_confounded   |   threshold_sensitivity |   mad_Batch_3 |   sens_over_mad | reasons                                                                                                                                               | notes                                                                                      |
|:---------------------------|:------------|-----------------:|:-------------------------|------------------------:|--------------:|----------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------|
| frac_c0                    | investigate |            0.726 | False                    |                  0.0146 |        0.0118 |            1.24 | threshold sensitivity 0.0146 >= 0.5 x Batch_3 MAD 0.0118                                                                                              |                                                                                            |
| frac_c1                    | investigate |            0.584 | False                    |                  0.0337 |        0.0198 |            1.7  | rank-stability 0.58 < 0.7; threshold sensitivity 0.0337 >= 0.5 x Batch_3 MAD 0.0198                                                                   | abs(rho) >= 0.5 with curtaining_score (rho -0.54); compare raw vs residualised batch tests |
| frac_c2                    | investigate |            0.44  | False                    |                  0.0431 |        0.0269 |            1.61 | rank-stability 0.44 < 0.7; threshold sensitivity 0.0431 >= 0.5 x Batch_3 MAD 0.0269                                                                   |                                                                                            |
| c2_count_density_per_Mpx   | investigate |            0.381 | True                     |                nan      |       81      |          nan    | rank-stability 0.38 < 0.7; acquisition_confounded (z_group 3.1 > z_batch -1.0, p_group 0.0010); no threshold-sensitivity measurement for this feature |                                                                                            |
| c2_eqdiam_median_px        | investigate |            0.514 | True                     |                nan      |        0.202  |          nan    | rank-stability 0.51 < 0.7; acquisition_confounded (z_group 1.8 > z_batch -0.1, p_group 0.0392); no threshold-sensitivity measurement for this feature |                                                                                            |
| c2_eqdiam_p90_px           | investigate |            0.362 | True                     |                nan      |       18.4    |          nan    | rank-stability 0.36 < 0.7; acquisition_confounded (z_group 2.9 > z_batch -0.3, p_group 0.0025); no threshold-sensitivity measurement for this feature |                                                                                            |
| c0_region_eqdiam_median_px | investigate |            0.843 | False                    |                nan      |        0.281  |          nan    | no threshold-sensitivity measurement for this feature                                                                                                 | abs(rho) >= 0.5 with noise_sigma (rho -0.63); compare raw vs residualised batch tests      |
| c0_region_area_mean_px     | investigate |            0.747 | True                     |                nan      |      182      |          nan    | acquisition_confounded (z_group 2.2 > z_batch 0.9, p_group 0.0173); no threshold-sensitivity measurement for this feature                             |                                                                                            |

Counts: {'investigate': 8}

## Stability (stability.csv)

rank_stability = mean Spearman between the observed ranking of batch medians and the ranking in each image-level bootstrap resample (resampling images within batch); rank_order_preserved_frac = share of resamples with the identical order. cv_Batch_3 = sd/mean over Batch_3 images; threshold_sensitivity = median over images of the largest |change| under +/-10 % threshold scaling (only measured for the class fractions).

| feature                    |   rank_stability |   rank_order_preserved_frac |   median_Batch_1 |   median_Batch_2 |   median_Batch_3 |   cv_Batch_3 |   mad_Batch_3 |   threshold_sensitivity | degenerate   |
|:---------------------------|-----------------:|----------------------------:|-----------------:|-----------------:|-----------------:|-------------:|--------------:|------------------------:|:-------------|
| frac_c0                    |            0.726 |                       0.478 |           0.0951 |           0.0976 |           0.102  |       0.151  |        0.0118 |                  0.0146 | False        |
| frac_c1                    |            0.584 |                       0.546 |           0.829  |           0.811  |           0.804  |       0.0313 |        0.0198 |                  0.0337 | False        |
| frac_c2                    |            0.44  |                       0.439 |           0.0894 |           0.0922 |           0.0974 |       0.216  |        0.0269 |                  0.0431 | False        |
| c2_count_density_per_Mpx   |            0.381 |                       0.363 |         119      |         113      |         138      |       0.412  |       81      |                nan      | False        |
| c2_eqdiam_median_px        |            0.514 |                       0.397 |           8.39   |           8.42   |           8.26   |       0.0704 |        0.202  |                nan      | False        |
| c2_eqdiam_p90_px           |            0.362 |                       0.364 |          33.4    |          39.7    |          41.8    |       0.366  |       18.4    |                nan      | False        |
| c0_region_eqdiam_median_px |            0.843 |                       0.714 |           9.95   |          10.3    |          10.5    |       0.0276 |        0.281  |                nan      | False        |
| c0_region_area_mean_px     |            0.747 |                       0.688 |         758      |         986      |         868      |       0.222  |      182      |                nan      | False        |

## Acquisition confounding (confound.csv)

Spearman rho with each covariate (BSE channel; edge charging from Inlens). Association with acquisition group vs with batch: Kruskal-Wallis H with an image-level permutation null; z = (H - mean null) / sd null makes the two comparable despite the different number of levels. acquisition_confounded = z_group > z_batch and p_group < 0.05. p_group_within_batch: do groups still explain the feature after centring on batch medians (labels shuffled within batch)?

| feature                    |   rho_noise_sigma |   rho_sharpness |   rho_curtaining_score |   rho_hstripe_score |   rho_edge_charging_inlens |   rho_mean_grey |   z_group |   p_group |   z_batch |   p_batch |   p_group_within_batch | acquisition_confounded   | covariate_correlated   |
|:---------------------------|------------------:|----------------:|-----------------------:|--------------------:|---------------------------:|----------------:|----------:|----------:|----------:|----------:|-----------------------:|:-------------------------|:-----------------------|
| frac_c0                    |           -0.355  |         -0.34   |                 0.252  |             0.181   |                    -0.124  |         -0.304  |     1.38  |    0.09   |     2.11  |    0.0443 |                 0.0698 | False                    | False                  |
| frac_c1                    |            0.31   |          0.304  |                -0.537  |            -0.0577  |                    -0.0859 |         -0.202  |     1.61  |    0.063  |    -0.39  |    0.543  |                 0.17   | False                    | True                   |
| frac_c2                    |           -0.192  |         -0.192  |                 0.369  |             0.0625  |                     0.157  |          0.292  |     0.608 |    0.273  |    -1.02  |    0.958  |                 0.448  | False                    | False                  |
| c2_count_density_per_Mpx   |           -0.17   |         -0.158  |                 0.368  |            -0.00887 |                     0.38   |          0.445  |     3.1   |    0.001  |    -0.958 |    0.914  |                 0.0035 | True                     | False                  |
| c2_eqdiam_median_px        |            0.284  |          0.26   |                -0.263  |            -0.101   |                    -0.158  |         -0.386  |     1.84  |    0.0392 |    -0.145 |    0.434  |                 0.115  | True                     | False                  |
| c2_eqdiam_p90_px           |           -0.0534 |         -0.0738 |                -0.136  |             0.262   |                    -0.357  |         -0.478  |     2.93  |    0.0025 |    -0.311 |    0.503  |                 0.0032 | True                     | False                  |
| c0_region_eqdiam_median_px |           -0.633  |         -0.623  |                 0.34   |             0.329   |                    -0.0238 |         -0.0129 |     2.53  |    0.0085 |     2.85  |    0.0199 |                 0.253  | False                    | True                   |
| c0_region_area_mean_px     |           -0.16   |         -0.14   |                 0.0456 |             0.208   |                    -0.407  |         -0.469  |     2.22  |    0.0173 |     0.934 |    0.151  |                 0.0584 | True                     | False                  |

covariate_correlated (informational, not part of the keep rule) = some abs(rho) >= 0.5 with p < 0.05; for such features compare the raw and residualised batch tests below.

## Batch tests (batch_tests.csv)

Effect = (median test batch - median Batch_3) / MAD(Batch_3, scaled 1.4826); p = image-level permutation p of the median difference; q = Benjamini-Hochberg across features within each comparison.

Raw features, all Batch_3 images:

| feature                    | comparison         |   n_test |   n_ref |   effect_shift_over_mad |   p_perm |   q_bh |
|:---------------------------|:-------------------|---------:|--------:|------------------------:|---------:|-------:|
| frac_c0                    | Batch_1_vs_Batch_3 |        7 |      17 |                  -0.579 |   0.171  |  0.456 |
| frac_c1                    | Batch_1_vs_Batch_3 |        7 |      17 |                   1.27  |   0.0837 |  0.335 |
| frac_c2                    | Batch_1_vs_Batch_3 |        7 |      17 |                  -0.299 |   0.635  |  0.642 |
| c2_count_density_per_Mpx   | Batch_1_vs_Batch_3 |        7 |      17 |                  -0.225 |   0.642  |  0.642 |
| c2_eqdiam_median_px        | Batch_1_vs_Batch_3 |        7 |      17 |                   0.647 |   0.495  |  0.642 |
| c2_eqdiam_p90_px           | Batch_1_vs_Batch_3 |        7 |      17 |                  -0.457 |   0.596  |  0.642 |
| c0_region_eqdiam_median_px | Batch_1_vs_Batch_3 |        7 |      17 |                  -1.96  |   0.004  |  0.032 |
| c0_region_area_mean_px     | Batch_1_vs_Batch_3 |        7 |      17 |                  -0.602 |   0.246  |  0.492 |
| frac_c0                    | Batch_2_vs_Batch_3 |        7 |      17 |                  -0.366 |   0.528  |  0.721 |
| frac_c1                    | Batch_2_vs_Batch_3 |        7 |      17 |                   0.375 |   0.408  |  0.721 |
| frac_c2                    | Batch_2_vs_Batch_3 |        7 |      17 |                  -0.194 |   0.584  |  0.721 |
| c2_count_density_per_Mpx   | Batch_2_vs_Batch_3 |        7 |      17 |                  -0.303 |   0.636  |  0.721 |
| c2_eqdiam_median_px        | Batch_2_vs_Batch_3 |        7 |      17 |                   0.802 |   0.498  |  0.721 |
| c2_eqdiam_p90_px           | Batch_2_vs_Batch_3 |        7 |      17 |                  -0.113 |   0.721  |  0.721 |
| c0_region_eqdiam_median_px | Batch_2_vs_Batch_3 |        7 |      17 |                  -0.585 |   0.259  |  0.721 |
| c0_region_area_mean_px     | Batch_2_vs_Batch_3 |        7 |      17 |                   0.653 |   0.311  |  0.721 |

Raw features, Batch_3 without vc2whyaq, ufdvpb81, hzumfsms:

| feature                    | comparison         |   n_test |   n_ref |   effect_shift_over_mad |   p_perm |   q_bh |
|:---------------------------|:-------------------|---------:|--------:|------------------------:|---------:|-------:|
| frac_c0                    | Batch_1_vs_Batch_3 |        7 |      14 |                  -0.517 |   0.207  | 0.553  |
| frac_c1                    | Batch_1_vs_Batch_3 |        7 |      14 |                   1.38  |   0.0627 | 0.251  |
| frac_c2                    | Batch_1_vs_Batch_3 |        7 |      14 |                  -0.375 |   0.643  | 0.734  |
| c2_count_density_per_Mpx   | Batch_1_vs_Batch_3 |        7 |      14 |                  -0.384 |   0.339  | 0.646  |
| c2_eqdiam_median_px        | Batch_1_vs_Batch_3 |        7 |      14 |                   0.775 |   0.403  | 0.646  |
| c2_eqdiam_p90_px           | Batch_1_vs_Batch_3 |        7 |      14 |                  -0.276 |   0.963  | 0.963  |
| c0_region_eqdiam_median_px | Batch_1_vs_Batch_3 |        7 |      14 |                  -2.27  |   0.0062 | 0.0496 |
| c0_region_area_mean_px     | Batch_1_vs_Batch_3 |        7 |      14 |                  -0.496 |   0.568  | 0.734  |
| frac_c0                    | Batch_2_vs_Batch_3 |        7 |      14 |                  -0.299 |   0.661  | 0.661  |
| frac_c1                    | Batch_2_vs_Batch_3 |        7 |      14 |                   0.396 |   0.334  | 0.547  |
| frac_c2                    | Batch_2_vs_Batch_3 |        7 |      14 |                  -0.271 |   0.53   | 0.607  |
| c2_count_density_per_Mpx   | Batch_2_vs_Batch_3 |        7 |      14 |                  -0.478 |   0.202  | 0.538  |
| c2_eqdiam_median_px        | Batch_2_vs_Batch_3 |        7 |      14 |                   0.96  |   0.342  | 0.547  |
| c2_eqdiam_p90_px           | Batch_2_vs_Batch_3 |        7 |      14 |                   0.261 |   0.531  | 0.607  |
| c0_region_eqdiam_median_px | Batch_2_vs_Batch_3 |        7 |      14 |                  -0.86  |   0.183  | 0.538  |
| c0_region_area_mean_px     | Batch_2_vs_Batch_3 |        7 |      14 |                   1.18  |   0.0971 | 0.538  |

Residualised on the acquisition covariates, all Batch_3 images:

| feature                    | comparison         |   n_test |   n_ref |   effect_shift_over_mad |   p_perm |   q_bh |
|:---------------------------|:-------------------|---------:|--------:|------------------------:|---------:|-------:|
| frac_c0                    | Batch_1_vs_Batch_3 |        7 |      17 |                  0.259  |   0.845  |  0.966 |
| frac_c1                    | Batch_1_vs_Batch_3 |        7 |      17 |                  0.673  |   0.298  |  0.487 |
| frac_c2                    | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.672  |   0.33   |  0.487 |
| c2_count_density_per_Mpx   | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.808  |   0.365  |  0.487 |
| c2_eqdiam_median_px        | Batch_1_vs_Batch_3 |        7 |      17 |                  0.0715 |   1      |  1     |
| c2_eqdiam_p90_px           | Batch_1_vs_Batch_3 |        7 |      17 |                  0.874  |   0.203  |  0.487 |
| c0_region_eqdiam_median_px | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.942  |   0.333  |  0.487 |
| c0_region_area_mean_px     | Batch_1_vs_Batch_3 |        7 |      17 |                 -1.43   |   0.0784 |  0.487 |
| frac_c0                    | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.278  |   0.557  |  1     |
| frac_c1                    | Batch_2_vs_Batch_3 |        7 |      17 |                  0.454  |   0.314  |  1     |
| frac_c2                    | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.459  |   0.463  |  1     |
| c2_count_density_per_Mpx   | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.0153 |   1      |  1     |
| c2_eqdiam_median_px        | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.112  |   1      |  1     |
| c2_eqdiam_p90_px           | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.12   |   0.684  |  1     |
| c0_region_eqdiam_median_px | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.0416 |   1      |  1     |
| c0_region_area_mean_px     | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.757  |   0.273  |  1     |

## Session-leakage evidence: LOIO vs LOGO (loio_logo.csv)

Logistic regression (balanced class weights, median imputation + standardisation fitted inside each fold) predicting batch from the 8 features, with and without the 6 acquisition covariates as extra inputs. chance_majority = accuracy of always predicting the largest batch.

| model   | split   | covariates   |   n_images |   n_folds |   n_features |   accuracy |   balanced_accuracy |   chance_majority |   recall_Batch_1 |   recall_Batch_2 |   recall_Batch_3 |
|:--------|:--------|:-------------|-----------:|----------:|-------------:|-----------:|--------------------:|------------------:|-----------------:|-----------------:|-----------------:|
| logreg  | LOIO    | without      |         31 |        31 |            8 |      0.581 |               0.493 |             0.548 |            0.571 |            0.143 |            0.765 |
| logreg  | LOIO    | with         |         31 |        31 |           14 |      0.613 |               0.569 |             0.548 |            0.571 |            0.429 |            0.706 |
| logreg  | LOGO    | without      |         31 |        13 |            8 |      0.452 |               0.359 |             0.548 |            0.429 |            0     |            0.647 |
| logreg  | LOGO    | with         |         31 |        13 |           14 |      0.581 |               0.521 |             0.548 |            0.571 |            0.286 |            0.706 |

Gaps (accuracy): loio_minus_logo_without_cov = +0.129; loio_minus_logo_with_cov = +0.032; with_minus_without_cov_loio = +0.032; with_minus_without_cov_logo = +0.129

Reading: a positive LOIO - LOGO gap means part of the LOIO accuracy comes from images of the same acquisition session being in the training set; a positive with - without gap means the covariates themselves carry batch information. Both are evidence that acquisition, not only material, separates the batches.

## Reference batch leave-one-out (reference_loo.csv), |z| > 3.0

| sample_id   | flags                       |
|:------------|:----------------------------|
| 0grcilhi    | frac_c0 z=+3.0              |
| cfe5vt7s    | c2_eqdiam_median_px z=+3.3  |
| hzumfsms    | frac_c0 z=+3.7              |
| ufdvpb81    | c2_eqdiam_median_px z=+6.7  |
| vc2whyaq    | c2_eqdiam_median_px z=+10.8 |

Expected from the C4 check: vc2whyaq, ufdvpb81, hzumfsms.

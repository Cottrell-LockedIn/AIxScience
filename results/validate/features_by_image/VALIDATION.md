# Validation of `features_by_image`

Inputs: results/features/features_by_image.parquet (sha256 85dccfe1258b), covariates from results/artefacts_per_image.parquet, acquisition groups from results/audit/images.csv, threshold sensitivity from results/kpi_sensitivity.parquet. Config de199d6c8d69, git f1ea178, seed 0, 1000 bootstrap resamples, 10000 permutations.

## Headline

- Decisions: {'investigate': 24, 'drop': 3}. Confounded with acquisition group: F05_c2_count_density_per_Mpx, F06_c2_clark_evans_R, F09_c0_chord_anisotropy_h_over_v, analysed_px, img_h, n_c2_particles, n_c2_particles_interior, n_c2_particles_border, n_c0_chords_h, n_c0_chords_v, n_windows, seconds.
- Raw batch effects with q < 0.05 (vs Batch_3, all images): none. After residualising on the covariates: none.
- Batch classifier accuracy (chance = majority 0.548): LOIO 0.581 / LOGO 0.419 without covariates; LOIO 0.548 / LOGO 0.516 with covariates. LOIO - LOGO gap +0.161 (without) / +0.032 (with); with - without covariates gap -0.032 (LOIO) / +0.097 (LOGO).
- Batch_3 images flagged by leave-one-out (|z| > 3.0): 0grcilhi (F01_c0_area_fraction z=+4.4, F07_c2_solidity_area_weighted_median z=-3.2, F08_c0_local_thickness_median_px z=+4.3, F08_c0_local_thickness_median_nm_if25 z=+4.3, analysed_px z=-5.2, img_h z=-5.4, seconds z=+3.8), hawkfj64 (analysed_px z=-5.2, img_h z=-5.4), hzumfsms (F01_c0_area_fraction z=+4.9, F03_c2_eqdiam_median_px z=-3.3, F03_c2_eqdiam_median_nm_if25 z=-3.3, F08_c0_local_thickness_median_px z=+4.3, F08_c0_local_thickness_median_nm_if25 z=+4.3, F10_c0_fraction_iqr_512px z=+8.3, seconds z=+6.1), mgxahqnk (F10_c0_fraction_iqr_512px z=+3.7, analysed_px z=-5.2, img_h z=-5.4), pl8uabbv (analysed_px z=+6.0, img_h z=+6.0), ptg8lmto (analysed_px z=-14.8, img_h z=-15.2), tuy3zymq (F03_c2_eqdiam_median_px z=+3.3, F03_c2_eqdiam_median_nm_if25 z=+3.3, F07_c2_solidity_area_weighted_median z=-4.3), vc2whyaq (F09_c0_chord_anisotropy_h_over_v z=+3.1), x77cy643 (F04_c2_eqdiam_p90_px z=+4.5, F04_c2_eqdiam_p90_nm_if25 z=+4.5), xgj4xftb (F03_c2_eqdiam_median_px z=+3.3, F03_c2_eqdiam_median_nm_if25 z=+3.3, analysed_px z=-14.8, img_h z=-15.2).

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

| feature                               | decision    |   rank_stability | acquisition_confounded   |   threshold_sensitivity |   mad_Batch_3 |   sens_over_mad | reasons                                                                                                                                               | notes                                                                                   |
|:--------------------------------------|:------------|-----------------:|:-------------------------|------------------------:|--------------:|----------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------|
| F01_c0_area_fraction                  | investigate |            0.691 | False                    |                     nan |      0.00888  |             nan | rank-stability 0.69 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F02_c2_area_fraction                  | investigate |            0.539 | False                    |                     nan |      0.0331   |             nan | rank-stability 0.54 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F03_c2_eqdiam_median_px               | investigate |            0.628 | False                    |                     nan |      0.117    |             nan | rank-stability 0.63 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F03_c2_eqdiam_median_nm_if25          | investigate |            0.628 | False                    |                     nan |      2.91     |             nan | rank-stability 0.63 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F04_c2_eqdiam_p90_px                  | investigate |            0.427 | False                    |                     nan |      3.95     |             nan | rank-stability 0.43 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F04_c2_eqdiam_p90_nm_if25             | investigate |            0.427 | False                    |                     nan |     98.7      |             nan | rank-stability 0.43 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F05_c2_count_density_per_Mpx          | investigate |            0.437 | True                     |                     nan |     83.6      |             nan | rank-stability 0.44 < 0.7; acquisition_confounded (z_group 3.5 > z_batch -0.7, p_group 0.0003); no threshold-sensitivity measurement for this feature |                                                                                         |
| F06_c2_clark_evans_R                  | investigate |            0.746 | True                     |                     nan |      0.0621   |             nan | acquisition_confounded (z_group 2.5 > z_batch 1.8, p_group 0.0070); no threshold-sensitivity measurement for this feature                             | abs(rho) >= 0.5 with mean_grey (rho +0.53); compare raw vs residualised batch tests     |
| F07_c2_solidity_area_weighted_median  | investigate |            0.561 | False                    |                     nan |      0.0636   |             nan | rank-stability 0.56 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F08_c0_local_thickness_median_px      | investigate |          nan     | False                    |                     nan |      2.97     |             nan | rank-stability nan < 0.7; no threshold-sensitivity measurement for this feature                                                                       |                                                                                         |
| F08_c0_local_thickness_median_nm_if25 | investigate |          nan     | False                    |                     nan |     74.1      |             nan | rank-stability nan < 0.7; no threshold-sensitivity measurement for this feature                                                                       |                                                                                         |
| F09_c0_chord_anisotropy_h_over_v      | investigate |            0.225 | True                     |                     nan |      0.0299   |             nan | rank-stability 0.22 < 0.7; acquisition_confounded (z_group 1.7 > z_batch -0.8, p_group 0.0498); no threshold-sensitivity measurement for this feature | abs(rho) >= 0.5 with hstripe_score (rho +0.55); compare raw vs residualised batch tests |
| F10_c0_fraction_iqr_512px             | investigate |            0.244 | False                    |                     nan |      0.00697  |             nan | rank-stability 0.24 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F11_c2_perimeter_fraction_adjacent_c0 | investigate |            0.39  | False                    |                     nan |      0.000555 |             nan | rank-stability 0.39 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| F06_c2_clark_evans_z                  | investigate |            0.936 | False                    |                     nan |      2.78     |             nan | no threshold-sensitivity measurement for this feature                                                                                                 |                                                                                         |
| analysed_px                           | investigate |            0.713 | True                     |                     nan |      2.9e+05  |             nan | acquisition_confounded (z_group 5.0 > z_batch 0.7, p_group 0.0001); no threshold-sensitivity measurement for this feature                             | abs(rho) >= 0.5 with noise_sigma (rho +0.51); compare raw vs residualised batch tests   |
| coverage                              | drop        |          nan     | False                    |                     nan |      0        |             nan | degenerate (constant, all-NaN or zero MAD in reference batch)                                                                                         |                                                                                         |
| img_h                                 | investigate |            0.702 | True                     |                     nan |     41.5      |             nan | acquisition_confounded (z_group 5.1 > z_batch 0.6, p_group 0.0001); no threshold-sensitivity measurement for this feature                             | abs(rho) >= 0.5 with noise_sigma (rho +0.51); compare raw vs residualised batch tests   |
| img_w                                 | drop        |          nan     | False                    |                     nan |      0        |             nan | degenerate (constant, all-NaN or zero MAD in reference batch)                                                                                         |                                                                                         |
| n_c2_particles                        | investigate |            0.261 | True                     |                     nan |      1.02e+03 |             nan | rank-stability 0.26 < 0.7; acquisition_confounded (z_group 3.4 > z_batch -0.9, p_group 0.0004); no threshold-sensitivity measurement for this feature |                                                                                         |
| n_c2_particles_interior               | investigate |            0.26  | True                     |                     nan |      1e+03    |             nan | rank-stability 0.26 < 0.7; acquisition_confounded (z_group 3.4 > z_batch -0.9, p_group 0.0005); no threshold-sensitivity measurement for this feature |                                                                                         |
| n_c2_particles_border                 | investigate |            0.214 | True                     |                     nan |     19.3      |             nan | rank-stability 0.21 < 0.7; acquisition_confounded (z_group 1.8 > z_batch -1.0, p_group 0.0440); no threshold-sensitivity measurement for this feature |                                                                                         |
| n_c0_chords_h                         | investigate |            0.559 | True                     |                     nan |      7.1e+03  |             nan | rank-stability 0.56 < 0.7; acquisition_confounded (z_group 2.0 > z_batch 0.4, p_group 0.0255); no threshold-sensitivity measurement for this feature  |                                                                                         |
| n_c0_chords_v                         | investigate |            0.694 | True                     |                     nan |      7.04e+03 |             nan | rank-stability 0.69 < 0.7; acquisition_confounded (z_group 1.7 > z_batch 1.4, p_group 0.0479); no threshold-sensitivity measurement for this feature  |                                                                                         |
| n_windows                             | drop        |            0.509 | True                     |                     nan |      0        |             nan | degenerate (constant, all-NaN or zero MAD in reference batch)                                                                                         |                                                                                         |
| n_c2_boundary_px                      | investigate |            0.61  | False                    |                     nan |      8.16e+04 |             nan | rank-stability 0.61 < 0.7; no threshold-sensitivity measurement for this feature                                                                      |                                                                                         |
| seconds                               | investigate |            0.702 | True                     |                     nan |      0.801    |             nan | acquisition_confounded (z_group 2.0 > z_batch 0.3, p_group 0.0302); no threshold-sensitivity measurement for this feature                             |                                                                                         |

Counts: {'investigate': 24, 'drop': 3}

## Stability (stability.csv)

rank_stability = mean Spearman between the observed ranking of batch medians and the ranking in each image-level bootstrap resample (resampling images within batch); rank_order_preserved_frac = share of resamples with the identical order. cv_Batch_3 = sd/mean over Batch_3 images; threshold_sensitivity = median over images of the largest |change| under +/-10 % threshold scaling (only measured for the class fractions).

| feature                               |   rank_stability |   rank_order_preserved_frac |   median_Batch_1 |   median_Batch_2 |   median_Batch_3 |   cv_Batch_3 |   mad_Batch_3 |   threshold_sensitivity | degenerate   |
|:--------------------------------------|-----------------:|----------------------------:|-----------------:|-----------------:|-----------------:|-------------:|--------------:|------------------------:|:-------------|
| F01_c0_area_fraction                  |            0.691 |                       0.45  |         0.0909   |         0.101    |         0.102    |      0.16    |      0.00888  |                     nan | False        |
| F02_c2_area_fraction                  |            0.539 |                       0.483 |         0.0891   |         0.0971   |         0.101    |      0.231   |      0.0331   |                     nan | False        |
| F03_c2_eqdiam_median_px               |            0.628 |                       0.264 |         8.14     |         7.98     |         8.14     |      0.0329  |      0.117    |                     nan | False        |
| F03_c2_eqdiam_median_nm_if25          |            0.628 |                       0.264 |       203        |       199        |       203        |      0.0329  |      2.91     |                     nan | False        |
| F04_c2_eqdiam_p90_px                  |            0.427 |                       0.481 |        23.9      |        24.7      |        26.6      |      0.161   |      3.95     |                     nan | False        |
| F04_c2_eqdiam_p90_nm_if25             |            0.427 |                       0.481 |       598        |       617        |       665        |      0.161   |     98.7      |                     nan | False        |
| F05_c2_count_density_per_Mpx          |            0.437 |                       0.378 |       116        |       109        |       131        |      0.405   |     83.6      |                     nan | False        |
| F06_c2_clark_evans_R                  |            0.746 |                       0.551 |         0.734    |         0.678    |         0.724    |      0.0629  |      0.0621   |                     nan | False        |
| F07_c2_solidity_area_weighted_median  |            0.561 |                       0.425 |         0.869    |         0.87     |         0.824    |      0.103   |      0.0636   |                     nan | False        |
| F08_c0_local_thickness_median_px      |          nan     |                       0.22  |        26        |        26        |        26        |      0.167   |      2.97     |                     nan | False        |
| F08_c0_local_thickness_median_nm_if25 |          nan     |                       0.22  |       650        |       650        |       650        |      0.167   |     74.1      |                     nan | False        |
| F09_c0_chord_anisotropy_h_over_v      |            0.225 |                       0.188 |         1.16     |         1.14     |         1.16     |      0.0345  |      0.0299   |                     nan | False        |
| F10_c0_fraction_iqr_512px             |            0.244 |                       0.298 |         0.0403   |         0.0487   |         0.0476   |      0.293   |      0.00697  |                     nan | False        |
| F11_c2_perimeter_fraction_adjacent_c0 |            0.39  |                       0.308 |         0.000708 |         0.00099  |         0.000569 |      0.801   |      0.000555 |                     nan | False        |
| F06_c2_clark_evans_z                  |            0.936 |                       0.912 |       -19.2      |       -23.6      |       -21.1      |      0.102   |      2.78     |                     nan | False        |
| analysed_px                           |            0.713 |                       0.478 |         1.49e+07 |         1.44e+07 |         1.43e+07 |      0.0855  |      2.9e+05  |                     nan | False        |
| coverage                              |          nan     |                       1     |         1        |         1        |         1        |      0       |      0        |                     nan | True         |
| img_h                                 |            0.702 |                       0.42  |         2.13e+03 |         2.06e+03 |         2.04e+03 |      0.0855  |     41.5      |                     nan | False        |
| img_w                                 |          nan     |                       0.882 |         6.98e+03 |         6.98e+03 |         6.98e+03 |      0.00019 |      0        |                     nan | True         |
| n_c2_particles                        |            0.261 |                       0.339 |         1.59e+03 |         1.7e+03  |         1.88e+03 |      0.385   |      1.02e+03 |                     nan | False        |
| n_c2_particles_interior               |            0.26  |                       0.339 |         1.52e+03 |         1.63e+03 |         1.83e+03 |      0.391   |      1e+03    |                     nan | False        |
| n_c2_particles_border                 |            0.214 |                       0.348 |        68        |        57        |        64        |      0.285   |     19.3      |                     nan | False        |
| n_c0_chords_h                         |            0.559 |                       0.442 |         5.66e+04 |         6.22e+04 |         6.1e+04  |      0.121   |      7.1e+03  |                     nan | False        |
| n_c0_chords_v                         |            0.694 |                       0.494 |         6.34e+04 |         7.06e+04 |         6.96e+04 |      0.111   |      7.04e+03 |                     nan | False        |
| n_windows                             |            0.509 |                       0.494 |        52        |        52        |        39        |      0.148   |      0        |                     nan | True         |
| n_c2_boundary_px                      |            0.61  |                       0.533 |         1.06e+05 |         1.72e+05 |         1.64e+05 |      0.4     |      8.16e+04 |                     nan | False        |
| seconds                               |            0.702 |                       0.608 |         4.01     |         4.51     |         4.36     |      0.308   |      0.801    |                     nan | False        |

## Acquisition confounding (confound.csv)

Spearman rho with each covariate (BSE channel; edge charging from Inlens). Association with acquisition group vs with batch: Kruskal-Wallis H with an image-level permutation null; z = (H - mean null) / sd null makes the two comparable despite the different number of levels. acquisition_confounded = z_group > z_batch and p_group < 0.05. p_group_within_batch: do groups still explain the feature after centring on batch medians (labels shuffled within batch)?

| feature                               |   rho_noise_sigma |   rho_sharpness |   rho_curtaining_score |   rho_hstripe_score |   rho_edge_charging_inlens |   rho_mean_grey |   z_group |   p_group |   z_batch |   p_batch |   p_group_within_batch | acquisition_confounded   | covariate_correlated   |
|:--------------------------------------|------------------:|----------------:|-----------------------:|--------------------:|---------------------------:|----------------:|----------:|----------:|----------:|----------:|-----------------------:|:-------------------------|:-----------------------|
| F01_c0_area_fraction                  |           -0.276  |         -0.259  |                 0.208  |              0.174  |                   -0.183   |        -0.34    |    0.205  |    0.409  |   2.14    |    0.0417 |                 0.353  | False                    | False                  |
| F02_c2_area_fraction                  |           -0.175  |         -0.174  |                 0.375  |              0.0742 |                    0.163   |         0.331   |    0.757  |    0.225  |  -0.943   |    0.899  |                 0.413  | False                    | False                  |
| F03_c2_eqdiam_median_px               |           -0.232  |         -0.241  |                 0.0334 |              0.0976 |                    0.278   |         0.163   |    1.26   |    0.111  |  -0.799   |    0.799  |                 0.0615 | False                    | False                  |
| F03_c2_eqdiam_median_nm_if25          |           -0.232  |         -0.241  |                 0.0334 |              0.0976 |                    0.278   |         0.163   |    1.3    |    0.102  |  -0.803   |    0.798  |                 0.0593 | False                    | False                  |
| F04_c2_eqdiam_p90_px                  |           -0.139  |         -0.169  |                -0.188  |              0.106  |                   -0.0919  |        -0.355   |    0.97   |    0.173  |   0.00182 |    0.378  |                 0.0979 | False                    | False                  |
| F04_c2_eqdiam_p90_nm_if25             |           -0.139  |         -0.169  |                -0.188  |              0.106  |                   -0.0919  |        -0.355   |    0.991  |    0.163  |   0.00784 |    0.376  |                 0.0926 | False                    | False                  |
| F05_c2_count_density_per_Mpx          |           -0.177  |         -0.167  |                 0.267  |              0.073  |                    0.448   |         0.472   |    3.48   |    0.0003 |  -0.672   |    0.707  |                 0.0006 | True                     | False                  |
| F06_c2_clark_evans_R                  |           -0.173  |         -0.169  |                 0.262  |             -0.0129 |                    0.398   |         0.534   |    2.54   |    0.007  |   1.76    |    0.0639 |                 0.0939 | True                     | True                   |
| F07_c2_solidity_area_weighted_median  |            0.153  |          0.162  |                -0.101  |             -0.0214 |                   -0.307   |        -0.148   |    1.65   |    0.0577 |  -0.545   |    0.626  |                 0.244  | False                    | False                  |
| F08_c0_local_thickness_median_px      |            0.0772 |          0.0753 |                -0.049  |             -0.0494 |                   -0.238   |        -0.381   |    0.179  |    0.419  |  -1.01    |    0.947  |                 0.421  | False                    | False                  |
| F08_c0_local_thickness_median_nm_if25 |            0.0772 |          0.0753 |                -0.049  |             -0.0494 |                   -0.238   |        -0.381   |    0.174  |    0.418  |  -1.01    |    0.948  |                 0.409  | False                    | False                  |
| F09_c0_chord_anisotropy_h_over_v      |           -0.267  |         -0.275  |                -0.324  |              0.553  |                    0.00887 |         0.192   |    1.72   |    0.0498 |  -0.803   |    0.802  |                 0.194  | True                     | True                   |
| F10_c0_fraction_iqr_512px             |            0.0317 |          0.05   |                 0.0726 |             -0.148  |                   -0.138   |        -0.175   |   -0.0748 |    0.516  |  -0.459   |    0.579  |                 0.475  | False                    | False                  |
| F11_c2_perimeter_fraction_adjacent_c0 |            0.0914 |          0.0758 |                 0.0746 |             -0.215  |                    0.0254  |         0.188   |    1.64   |    0.0577 |  -0.908   |    0.868  |                 0.0069 | False                    | False                  |
| F06_c2_clark_evans_z                  |            0.0345 |          0.0371 |                 0.0298 |             -0.111  |                   -0.0234  |         0.00323 |   -0.41   |    0.64   |   3.01    |    0.0156 |                 0.312  | False                    | False                  |
| analysed_px                           |            0.511  |          0.472  |                -0.0597 |             -0.335  |                   -0.246   |        -0.132   |    5.04   |    0.0001 |   0.717   |    0.191  |                 0.0001 | True                     | True                   |
| coverage                              |          nan      |        nan      |               nan      |            nan      |                  nan       |       nan       |  nan      |  nan      | nan       |  nan      |               nan      | False                    | False                  |
| img_h                                 |            0.51   |          0.471  |                -0.0534 |             -0.343  |                   -0.243   |        -0.138   |    5.06   |    0.0001 |   0.619   |    0.207  |                 0.0001 | True                     | True                   |
| img_w                                 |           -0.164  |         -0.166  |                 0.0506 |              0.197  |                    0.195   |         0.175   |    1.49   |    0.101  |   0.384   |    0.235  |                 0.138  | False                    | False                  |
| n_c2_particles                        |           -0.147  |         -0.149  |                 0.299  |              0.0169 |                    0.421   |         0.434   |    3.41   |    0.0004 |  -0.888   |    0.859  |                 0.0006 | True                     | False                  |
| n_c2_particles_interior               |           -0.143  |         -0.144  |                 0.295  |              0.0101 |                    0.415   |         0.431   |    3.36   |    0.0005 |  -0.907   |    0.876  |                 0.0004 | True                     | False                  |
| n_c2_particles_border                 |           -0.085  |         -0.0712 |                 0.295  |             -0.273  |                    0.358   |         0.251   |    1.78   |    0.044  |  -1.01    |    0.941  |                 0.0657 | True                     | False                  |
| n_c0_chords_h                         |           -0.067  |         -0.0722 |                 0.367  |             -0.15   |                   -0.124   |        -0.0879  |    2.04   |    0.0255 |   0.412   |    0.258  |                 0.0133 | True                     | False                  |
| n_c0_chords_v                         |           -0.144  |         -0.156  |                 0.216  |             -0.0177 |                   -0.114   |        -0.0778  |    1.74   |    0.0479 |   1.44    |    0.0907 |                 0.0286 | True                     | False                  |
| n_windows                             |            0.468  |          0.424  |                -0.183  |             -0.292  |                   -0.387   |        -0.27    |    5.08   |    0.0001 |  -0.101   |    0.428  |                 0.0019 | True                     | False                  |
| n_c2_boundary_px                      |           -0.124  |         -0.124  |                 0.276  |             -0.108  |                    0.271   |         0.225   |    1.37   |    0.0909 |  -0.498   |    0.608  |                 0.055  | False                    | False                  |
| seconds                               |           -0.112  |         -0.103  |                 0.326  |             -0.0228 |                   -0.203   |        -0.345   |    1.99   |    0.0302 |   0.283   |    0.297  |                 0.0156 | True                     | False                  |

covariate_correlated (informational, not part of the keep rule) = some abs(rho) >= 0.5 with p < 0.05; for such features compare the raw and residualised batch tests below.

## Batch tests (batch_tests.csv)

Effect = (median test batch - median Batch_3) / MAD(Batch_3, scaled 1.4826); p = image-level permutation p of the median difference; q = Benjamini-Hochberg across features within each comparison.

Raw features, all Batch_3 images:

| feature                               | comparison         |   n_test |   n_ref |   effect_shift_over_mad |   p_perm |   q_bh |
|:--------------------------------------|:-------------------|---------:|--------:|------------------------:|---------:|-------:|
| F01_c0_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      17 |                 -1.24   |   0.0499 |  0.6   |
| F02_c2_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.348  |   0.58   |  1     |
| F03_c2_eqdiam_median_px               | Batch_1_vs_Batch_3 |        7 |      17 |                  0      |   1      |  1     |
| F03_c2_eqdiam_median_nm_if25          | Batch_1_vs_Batch_3 |        7 |      17 |                  0      |   1      |  1     |
| F04_c2_eqdiam_p90_px                  | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.676  |   0.199  |  0.758 |
| F04_c2_eqdiam_p90_nm_if25             | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.676  |   0.199  |  0.758 |
| F05_c2_count_density_per_Mpx          | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.173  |   0.68   |  1     |
| F06_c2_clark_evans_R                  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.158  |   0.845  |  1     |
| F07_c2_solidity_area_weighted_median  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.706  |   0.327  |  0.803 |
| F08_c0_local_thickness_median_px      | Batch_1_vs_Batch_3 |        7 |      17 |                  0      |   1      |  1     |
| F08_c0_local_thickness_median_nm_if25 | Batch_1_vs_Batch_3 |        7 |      17 |                  0      |   1      |  1     |
| F09_c0_chord_anisotropy_h_over_v      | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.213  |   0.617  |  1     |
| F10_c0_fraction_iqr_512px             | Batch_1_vs_Batch_3 |        7 |      17 |                 -1.05   |   0.288  |  0.803 |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_1_vs_Batch_3 |        7 |      17 |                  0.25   |   0.848  |  1     |
| F06_c2_clark_evans_z                  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.688  |   0.225  |  0.758 |
| analysed_px                           | Batch_1_vs_Batch_3 |        7 |      17 |                  2.12   |   0.0846 |  0.6   |
| coverage                              | Batch_1_vs_Batch_3 |        7 |      17 |                nan      |   1      |  1     |
| img_h                                 | Batch_1_vs_Batch_3 |        7 |      17 |                  2.12   |   0.0889 |  0.6   |
| img_w                                 | Batch_1_vs_Batch_3 |        7 |      17 |                nan      |   1      |  1     |
| n_c2_particles                        | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.282  |   0.845  |  1     |
| n_c2_particles_interior               | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.302  |   0.767  |  1     |
| n_c2_particles_border                 | Batch_1_vs_Batch_3 |        7 |      17 |                  0.208  |   0.646  |  1     |
| n_c0_chords_h                         | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.624  |   0.156  |  0.758 |
| n_c0_chords_v                         | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.879  |   0.0726 |  0.6   |
| n_windows                             | Batch_1_vs_Batch_3 |        7 |      17 |                nan      |   0.663  |  1     |
| n_c2_boundary_px                      | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.703  |   0.409  |  0.92  |
| seconds                               | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.437  |   0.327  |  0.803 |
| F01_c0_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.0625 |   1      |  1     |
| F02_c2_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.106  |   0.689  |  1     |
| F03_c2_eqdiam_median_px               | Batch_2_vs_Batch_3 |        7 |      17 |                 -1.36   |   0.39   |  0.964 |
| F03_c2_eqdiam_median_nm_if25          | Batch_2_vs_Batch_3 |        7 |      17 |                 -1.36   |   0.393  |  0.964 |
| F04_c2_eqdiam_p90_px                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.487  |   0.146  |  0.964 |
| F04_c2_eqdiam_p90_nm_if25             | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.487  |   0.142  |  0.964 |
| F05_c2_count_density_per_Mpx          | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.256  |   0.493  |  1     |
| F06_c2_clark_evans_R                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.74   |   0.121  |  0.964 |
| F07_c2_solidity_area_weighted_median  | Batch_2_vs_Batch_3 |        7 |      17 |                  0.714  |   0.346  |  0.964 |
| F08_c0_local_thickness_median_px      | Batch_2_vs_Batch_3 |        7 |      17 |                  0      |   1      |  1     |
| F08_c0_local_thickness_median_nm_if25 | Batch_2_vs_Batch_3 |        7 |      17 |                  0      |   1      |  1     |
| F09_c0_chord_anisotropy_h_over_v      | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.68   |   0.262  |  0.964 |
| F10_c0_fraction_iqr_512px             | Batch_2_vs_Batch_3 |        7 |      17 |                  0.16   |   1      |  1     |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_2_vs_Batch_3 |        7 |      17 |                  0.759  |   0.322  |  0.964 |
| F06_c2_clark_evans_z                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.894  |   0.14   |  0.964 |
| analysed_px                           | Batch_2_vs_Batch_3 |        7 |      17 |                  0.482  |   0.232  |  0.964 |
| coverage                              | Batch_2_vs_Batch_3 |        7 |      17 |                nan      |   1      |  1     |
| img_h                                 | Batch_2_vs_Batch_3 |        7 |      17 |                  0.482  |   0.255  |  0.964 |
| img_w                                 | Batch_2_vs_Batch_3 |        7 |      17 |                nan      |   1      |  1     |
| n_c2_particles                        | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.179  |   0.681  |  1     |
| n_c2_particles_interior               | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.197  |   0.684  |  1     |
| n_c2_particles_border                 | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.363  |   0.667  |  1     |
| n_c0_chords_h                         | Batch_2_vs_Batch_3 |        7 |      17 |                  0.173  |   0.841  |  1     |
| n_c0_chords_v                         | Batch_2_vs_Batch_3 |        7 |      17 |                  0.15   |   0.768  |  1     |
| n_windows                             | Batch_2_vs_Batch_3 |        7 |      17 |                nan      |   0.657  |  1     |
| n_c2_boundary_px                      | Batch_2_vs_Batch_3 |        7 |      17 |                  0.0961 |   0.763  |  1     |
| seconds                               | Batch_2_vs_Batch_3 |        7 |      17 |                  0.187  |   0.489  |  1     |

Raw features, Batch_3 without vc2whyaq, ufdvpb81, hzumfsms:

| feature                               | comparison         |   n_test |   n_ref |   effect_shift_over_mad |   p_perm |   q_bh |
|:--------------------------------------|:-------------------|---------:|--------:|------------------------:|---------:|-------:|
| F01_c0_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.958  |   0.103  |  0.759 |
| F02_c2_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.363  |   0.603  |  0.937 |
| F03_c2_eqdiam_median_px               | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.336  |   0.991  |  1     |
| F03_c2_eqdiam_median_nm_if25          | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.336  |   0.99   |  1     |
| F04_c2_eqdiam_p90_px                  | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.985  |   0.163  |  0.759 |
| F04_c2_eqdiam_p90_nm_if25             | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.985  |   0.161  |  0.759 |
| F05_c2_count_density_per_Mpx          | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.406  |   0.395  |  0.889 |
| F06_c2_clark_evans_R                  | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.0954 |   0.791  |  1     |
| F07_c2_solidity_area_weighted_median  | Batch_1_vs_Batch_3 |        7 |      14 |                  0.725  |   0.259  |  0.776 |
| F08_c0_local_thickness_median_px      | Batch_1_vs_Batch_3 |        7 |      14 |                  0      |   1      |  1     |
| F08_c0_local_thickness_median_nm_if25 | Batch_1_vs_Batch_3 |        7 |      14 |                  0      |   1      |  1     |
| F09_c0_chord_anisotropy_h_over_v      | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.0841 |   0.888  |  1     |
| F10_c0_fraction_iqr_512px             | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.738  |   0.377  |  0.889 |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_1_vs_Batch_3 |        7 |      14 |                  0.583  |   0.578  |  0.937 |
| F06_c2_clark_evans_z                  | Batch_1_vs_Batch_3 |        7 |      14 |                  0.838  |   0.244  |  0.776 |
| analysed_px                           | Batch_1_vs_Batch_3 |        7 |      14 |                  2.47   |   0.169  |  0.759 |
| coverage                              | Batch_1_vs_Batch_3 |        7 |      14 |                nan      |   1      |  1     |
| img_h                                 | Batch_1_vs_Batch_3 |        7 |      14 |                  2.47   |   0.169  |  0.759 |
| img_w                                 | Batch_1_vs_Batch_3 |        7 |      14 |                nan      |   1      |  1     |
| n_c2_particles                        | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.359  |   0.473  |  0.924 |
| n_c2_particles_interior               | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.381  |   0.479  |  0.924 |
| n_c2_particles_border                 | Batch_1_vs_Batch_3 |        7 |      14 |                  0.193  |   0.578  |  0.937 |
| n_c0_chords_h                         | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.502  |   0.254  |  0.776 |
| n_c0_chords_v                         | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.807  |   0.121  |  0.759 |
| n_windows                             | Batch_1_vs_Batch_3 |        7 |      14 |                nan      |   0.659  |  0.937 |
| n_c2_boundary_px                      | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.789  |   0.311  |  0.84  |
| seconds                               | Batch_1_vs_Batch_3 |        7 |      14 |                 -0.506  |   0.655  |  0.937 |
| F01_c0_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      14 |                  0.159  |   0.816  |  1     |
| F02_c2_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      14 |                 -0.127  |   0.705  |  0.999 |
| F03_c2_eqdiam_median_px               | Batch_2_vs_Batch_3 |        7 |      14 |                 -1.7    |   0.329  |  0.742 |
| F03_c2_eqdiam_median_nm_if25          | Batch_2_vs_Batch_3 |        7 |      14 |                 -1.7    |   0.33   |  0.742 |
| F04_c2_eqdiam_p90_px                  | Batch_2_vs_Batch_3 |        7 |      14 |                 -0.659  |   0.264  |  0.714 |
| F04_c2_eqdiam_p90_nm_if25             | Batch_2_vs_Batch_3 |        7 |      14 |                 -0.659  |   0.261  |  0.714 |
| F05_c2_count_density_per_Mpx          | Batch_2_vs_Batch_3 |        7 |      14 |                 -0.51   |   0.145  |  0.714 |
| F06_c2_clark_evans_R                  | Batch_2_vs_Batch_3 |        7 |      14 |                 -1.43   |   0.0287 |  0.714 |
| F07_c2_solidity_area_weighted_median  | Batch_2_vs_Batch_3 |        7 |      14 |                  0.732  |   0.152  |  0.714 |
| F08_c0_local_thickness_median_px      | Batch_2_vs_Batch_3 |        7 |      14 |                  0      |   1      |  1     |
| F08_c0_local_thickness_median_nm_if25 | Batch_2_vs_Batch_3 |        7 |      14 |                  0      |   1      |  1     |
| F09_c0_chord_anisotropy_h_over_v      | Batch_2_vs_Batch_3 |        7 |      14 |                 -0.572  |   0.487  |  0.851 |
| F10_c0_fraction_iqr_512px             | Batch_2_vs_Batch_3 |        7 |      14 |                  0.138  |   0.808  |  1     |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_2_vs_Batch_3 |        7 |      14 |                  1.25   |   0.202  |  0.714 |
| F06_c2_clark_evans_z                  | Batch_2_vs_Batch_3 |        7 |      14 |                 -0.846  |   0.146  |  0.714 |
| analysed_px                           | Batch_2_vs_Batch_3 |        7 |      14 |                  0.562  |   0.161  |  0.714 |
| coverage                              | Batch_2_vs_Batch_3 |        7 |      14 |                nan      |   1      |  1     |
| img_h                                 | Batch_2_vs_Batch_3 |        7 |      14 |                  0.562  |   0.224  |  0.714 |
| img_w                                 | Batch_2_vs_Batch_3 |        7 |      14 |                nan      |   1      |  1     |
| n_c2_particles                        | Batch_2_vs_Batch_3 |        7 |      14 |                 -0.243  |   0.416  |  0.802 |
| n_c2_particles_interior               | Batch_2_vs_Batch_3 |        7 |      14 |                 -0.262  |   0.413  |  0.802 |
| n_c2_particles_border                 | Batch_2_vs_Batch_3 |        7 |      14 |                 -0.337  |   0.504  |  0.851 |
| n_c0_chords_h                         | Batch_2_vs_Batch_3 |        7 |      14 |                  0.226  |   0.648  |  0.991 |
| n_c0_chords_v                         | Batch_2_vs_Batch_3 |        7 |      14 |                  0.183  |   0.74   |  0.999 |
| n_windows                             | Batch_2_vs_Batch_3 |        7 |      14 |                nan      |   0.66   |  0.991 |
| n_c2_boundary_px                      | Batch_2_vs_Batch_3 |        7 |      14 |                  0.0153 |   0.869  |  1     |
| seconds                               | Batch_2_vs_Batch_3 |        7 |      14 |                  0.699  |   0.129  |  0.714 |

Residualised on the acquisition covariates, all Batch_3 images:

| feature                               | comparison         |   n_test |   n_ref |   effect_shift_over_mad |   p_perm |   q_bh |
|:--------------------------------------|:-------------------|---------:|--------:|------------------------:|---------:|-------:|
| F01_c0_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.0671 |   1      |  1     |
| F02_c2_area_fraction                  | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.39   |   0.466  |  0.826 |
| F03_c2_eqdiam_median_px               | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.0958 |   0.843  |  0.949 |
| F03_c2_eqdiam_median_nm_if25          | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.0958 |   0.841  |  0.949 |
| F04_c2_eqdiam_p90_px                  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.424  |   0.438  |  0.826 |
| F04_c2_eqdiam_p90_nm_if25             | Batch_1_vs_Batch_3 |        7 |      17 |                  0.424  |   0.432  |  0.826 |
| F05_c2_count_density_per_Mpx          | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.795  |   0.306  |  0.826 |
| F06_c2_clark_evans_R                  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.042  |   1      |  1     |
| F07_c2_solidity_area_weighted_median  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.434  |   0.578  |  0.826 |
| F08_c0_local_thickness_median_px      | Batch_1_vs_Batch_3 |        7 |      17 |                  0.511  |   0.348  |  0.826 |
| F08_c0_local_thickness_median_nm_if25 | Batch_1_vs_Batch_3 |        7 |      17 |                  0.511  |   0.348  |  0.826 |
| F09_c0_chord_anisotropy_h_over_v      | Batch_1_vs_Batch_3 |        7 |      17 |                  1.03   |   0.205  |  0.826 |
| F10_c0_fraction_iqr_512px             | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.266  |   0.582  |  0.826 |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.71   |   0.459  |  0.826 |
| F06_c2_clark_evans_z                  | Batch_1_vs_Batch_3 |        7 |      17 |                  0.648  |   0.314  |  0.826 |
| analysed_px                           | Batch_1_vs_Batch_3 |        7 |      17 |                  0.27   |   0.689  |  0.846 |
| coverage                              | Batch_1_vs_Batch_3 |        7 |      17 |                  0.674  |   1      |  1     |
| img_h                                 | Batch_1_vs_Batch_3 |        7 |      17 |                  0.296  |   0.684  |  0.846 |
| img_w                                 | Batch_1_vs_Batch_3 |        7 |      17 |                  0.512  |   0.516  |  0.826 |
| n_c2_particles                        | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.827  |   0.363  |  0.826 |
| n_c2_particles_interior               | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.783  |   0.391  |  0.826 |
| n_c2_particles_border                 | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.477  |   0.546  |  0.826 |
| n_c0_chords_h                         | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.699  |   0.309  |  0.826 |
| n_c0_chords_v                         | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.428  |   0.391  |  0.826 |
| n_windows                             | Batch_1_vs_Batch_3 |        7 |      17 |                  0.451  |   0.641  |  0.846 |
| n_c2_boundary_px                      | Batch_1_vs_Batch_3 |        7 |      17 |                 -0.36   |   0.506  |  0.826 |
| seconds                               | Batch_1_vs_Batch_3 |        7 |      17 |                  0.761  |   0.282  |  0.826 |
| F01_c0_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.221  |   0.84   |  1     |
| F02_c2_area_fraction                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.4    |   0.464  |  1     |
| F03_c2_eqdiam_median_px               | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.164  |   0.763  |  1     |
| F03_c2_eqdiam_median_nm_if25          | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.164  |   0.763  |  1     |
| F04_c2_eqdiam_p90_px                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -1.13   |   0.0159 |  0.17  |
| F04_c2_eqdiam_p90_nm_if25             | Batch_2_vs_Batch_3 |        7 |      17 |                 -1.13   |   0.0189 |  0.17  |
| F05_c2_count_density_per_Mpx          | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.0327 |   1      |  1     |
| F06_c2_clark_evans_R                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.378  |   0.242  |  1     |
| F07_c2_solidity_area_weighted_median  | Batch_2_vs_Batch_3 |        7 |      17 |                  0.569  |   0.361  |  1     |
| F08_c0_local_thickness_median_px      | Batch_2_vs_Batch_3 |        7 |      17 |                  0.542  |   0.721  |  1     |
| F08_c0_local_thickness_median_nm_if25 | Batch_2_vs_Batch_3 |        7 |      17 |                  0.542  |   0.715  |  1     |
| F09_c0_chord_anisotropy_h_over_v      | Batch_2_vs_Batch_3 |        7 |      17 |                  0.0127 |   1      |  1     |
| F10_c0_fraction_iqr_512px             | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.246  |   0.466  |  1     |
| F11_c2_perimeter_fraction_adjacent_c0 | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.393  |   0.612  |  1     |
| F06_c2_clark_evans_z                  | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.974  |   0.0657 |  0.443 |
| analysed_px                           | Batch_2_vs_Batch_3 |        7 |      17 |                  0.347  |   0.559  |  1     |
| coverage                              | Batch_2_vs_Batch_3 |        7 |      17 |                  0      |   1      |  1     |
| img_h                                 | Batch_2_vs_Batch_3 |        7 |      17 |                  0.361  |   0.609  |  1     |
| img_w                                 | Batch_2_vs_Batch_3 |        7 |      17 |                  1.74   |   0.0071 |  0.17  |
| n_c2_particles                        | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.126  |   1      |  1     |
| n_c2_particles_interior               | Batch_2_vs_Batch_3 |        7 |      17 |                 -0.0922 |   1      |  1     |
| n_c2_particles_border                 | Batch_2_vs_Batch_3 |        7 |      17 |                  0.126  |   1      |  1     |
| n_c0_chords_h                         | Batch_2_vs_Batch_3 |        7 |      17 |                  0.0393 |   1      |  1     |
| n_c0_chords_v                         | Batch_2_vs_Batch_3 |        7 |      17 |                  0.074  |   0.839  |  1     |
| n_windows                             | Batch_2_vs_Batch_3 |        7 |      17 |                  0.211  |   0.683  |  1     |
| n_c2_boundary_px                      | Batch_2_vs_Batch_3 |        7 |      17 |                  0.0288 |   0.839  |  1     |
| seconds                               | Batch_2_vs_Batch_3 |        7 |      17 |                  0.523  |   0.523  |  1     |

## Session-leakage evidence: LOIO vs LOGO (loio_logo.csv)

Logistic regression (balanced class weights, median imputation + standardisation fitted inside each fold) predicting batch from the 27 features, with and without the 6 acquisition covariates as extra inputs. chance_majority = accuracy of always predicting the largest batch.

| model   | split   | covariates   |   n_images |   n_folds |   n_features |   accuracy |   balanced_accuracy |   chance_majority |   recall_Batch_1 |   recall_Batch_2 |   recall_Batch_3 |
|:--------|:--------|:-------------|-----------:|----------:|-------------:|-----------:|--------------------:|------------------:|-----------------:|-----------------:|-----------------:|
| logreg  | LOIO    | without      |         31 |        31 |           27 |      0.581 |               0.549 |             0.548 |            0.286 |            0.714 |            0.647 |
| logreg  | LOIO    | with         |         31 |        31 |           33 |      0.548 |               0.473 |             0.548 |            0.286 |            0.429 |            0.706 |
| logreg  | LOGO    | without      |         31 |        13 |           27 |      0.419 |               0.367 |             0.548 |            0.143 |            0.429 |            0.529 |
| logreg  | LOGO    | with         |         31 |        13 |           33 |      0.516 |               0.426 |             0.548 |            0     |            0.571 |            0.706 |

Gaps (accuracy): loio_minus_logo_without_cov = +0.161; loio_minus_logo_with_cov = +0.032; with_minus_without_cov_loio = -0.032; with_minus_without_cov_logo = +0.097

Reading: a positive LOIO - LOGO gap means part of the LOIO accuracy comes from images of the same acquisition session being in the training set; a positive with - without gap means the covariates themselves carry batch information. Both are evidence that acquisition, not only material, separates the batches.

## Reference batch leave-one-out (reference_loo.csv), |z| > 3.0

| sample_id   | flags                                                                                                                                                                                                                                     |
|:------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0grcilhi    | F01_c0_area_fraction z=+4.4, F07_c2_solidity_area_weighted_median z=-3.2, F08_c0_local_thickness_median_px z=+4.3, F08_c0_local_thickness_median_nm_if25 z=+4.3, analysed_px z=-5.2, img_h z=-5.4, seconds z=+3.8                         |
| hawkfj64    | analysed_px z=-5.2, img_h z=-5.4                                                                                                                                                                                                          |
| hzumfsms    | F01_c0_area_fraction z=+4.9, F03_c2_eqdiam_median_px z=-3.3, F03_c2_eqdiam_median_nm_if25 z=-3.3, F08_c0_local_thickness_median_px z=+4.3, F08_c0_local_thickness_median_nm_if25 z=+4.3, F10_c0_fraction_iqr_512px z=+8.3, seconds z=+6.1 |
| mgxahqnk    | F10_c0_fraction_iqr_512px z=+3.7, analysed_px z=-5.2, img_h z=-5.4                                                                                                                                                                        |
| pl8uabbv    | analysed_px z=+6.0, img_h z=+6.0                                                                                                                                                                                                          |
| ptg8lmto    | analysed_px z=-14.8, img_h z=-15.2                                                                                                                                                                                                        |
| tuy3zymq    | F03_c2_eqdiam_median_px z=+3.3, F03_c2_eqdiam_median_nm_if25 z=+3.3, F07_c2_solidity_area_weighted_median z=-4.3                                                                                                                          |
| vc2whyaq    | F09_c0_chord_anisotropy_h_over_v z=+3.1                                                                                                                                                                                                   |
| x77cy643    | F04_c2_eqdiam_p90_px z=+4.5, F04_c2_eqdiam_p90_nm_if25 z=+4.5                                                                                                                                                                             |
| xgj4xftb    | F03_c2_eqdiam_median_px z=+3.3, F03_c2_eqdiam_median_nm_if25 z=+3.3, analysed_px z=-14.8, img_h z=-15.2                                                                                                                                   |

Expected from the C4 check: vc2whyaq, ufdvpb81, hzumfsms.

# Batch identification and OOD screen: `features_f01_f11`

Provenance: config_path=configs/v1.yaml, config_hash=de199d6c8d69, git_sha=370d083, features=results/features/features_f01_f11.parquet, features_sha256=bfe253c224c0, seed=0, n_perm=200, heldout=none

Target (Polaron): what differs between batches; categorise held-back images as Batch_1/2/3 or `matches none`. Batch_3 is the supplier's promised baseline; Batch_1/2 are different, not worse. No good/bad claim follows.

Reading guide: LOIO = estimate for held-back images from the same acquisition sessions; LOGO = estimate for a new session. `p_perm` is the image-level label-permutation p of the accuracy; an accuracy inside the null band means the family does not identify the batch. Drivers are standardised logistic-regression coefficients tagged material or acquisition, so a separation is never reported without saying what carries it.

## Accuracy per feature family

| family               | model   | split   |   n_features |   accuracy |   balanced_accuracy |   chance_majority |   null_mean |   null_p95 |   p_perm |   recall_Batch_1 |   recall_Batch_2 |   recall_Batch_3 |
|:---------------------|:--------|:--------|-------------:|-----------:|--------------------:|------------------:|------------:|-----------:|---------:|-----------------:|-----------------:|-----------------:|
| material             | logreg  | LOIO    |           11 |      0.452 |               0.359 |             0.548 |       0.341 |      0.516 |  0.189   |            0.143 |            0.286 |            0.647 |
| material             | logreg  | LOGO    |           11 |      0.323 |               0.224 |             0.548 |       0.336 |      0.485 |  0.607   |            0     |            0.143 |            0.529 |
| acquisition          | logreg  | LOIO    |            6 |      0.71  |               0.655 |             0.548 |       0.341 |      0.516 |  0.00498 |            0.714 |            0.429 |            0.824 |
| acquisition          | logreg  | LOGO    |            6 |      0.645 |               0.56  |             0.548 |       0.344 |      0.548 |  0.00498 |            0.429 |            0.429 |            0.824 |
| material+acquisition | logreg  | LOIO    |           17 |      0.645 |               0.56  |             0.548 |       0.359 |      0.516 |  0.0149  |            0.286 |            0.571 |            0.824 |
| material+acquisition | logreg  | LOGO    |           17 |      0.677 |               0.608 |             0.548 |       0.347 |      0.516 |  0.00498 |            0.429 |            0.571 |            0.824 |

## Top-3 drivers per batch (LOIO, logreg)

| family               | batch   |   rank_in_batch | feature                          | driver_type   |   coef_std |
|:---------------------|:--------|----------------:|:---------------------------------|:--------------|-----------:|
| acquisition          | Batch_1 |               1 | sharpness                        | acquisition   |      0.931 |
| acquisition          | Batch_1 |               2 | noise_sigma                      | acquisition   |      0.725 |
| acquisition          | Batch_1 |               3 | curtaining_score                 | acquisition   |     -0.646 |
| acquisition          | Batch_2 |               1 | edge_charging_inlens             | acquisition   |     -0.828 |
| acquisition          | Batch_2 |               2 | mean_grey                        | acquisition   |     -0.429 |
| acquisition          | Batch_2 |               3 | hstripe_score                    | acquisition   |     -0.152 |
| acquisition          | Batch_3 |               1 | sharpness                        | acquisition   |     -0.903 |
| acquisition          | Batch_3 |               2 | noise_sigma                      | acquisition   |     -0.819 |
| acquisition          | Batch_3 |               3 | edge_charging_inlens             | acquisition   |      0.653 |
| material             | Batch_1 |               1 | F01_c0_area_fraction             | material      |     -1.24  |
| material             | Batch_1 |               2 | F06_c2_clark_evans_R             | material      |      0.856 |
| material             | Batch_1 |               3 | F08_c0_local_thickness_median_px | material      |      0.508 |
| material             | Batch_2 |               1 | F06_c2_clark_evans_R             | material      |     -1.1   |
| material             | Batch_2 |               2 | F04_c2_eqdiam_p90_px             | material      |     -0.828 |
| material             | Batch_2 |               3 | F09_c0_chord_anisotropy_h_over_v | material      |     -0.481 |
| material             | Batch_3 |               1 | F01_c0_area_fraction             | material      |      1.1   |
| material             | Batch_3 |               2 | F04_c2_eqdiam_p90_px             | material      |      0.59  |
| material             | Batch_3 |               3 | F05_c2_count_density_per_Mpx     | material      |      0.548 |
| material+acquisition | Batch_1 |               1 | F06_c2_clark_evans_R             | material      |      0.667 |
| material+acquisition | Batch_1 |               2 | F01_c0_area_fraction             | material      |     -0.654 |
| material+acquisition | Batch_1 |               3 | sharpness                        | acquisition   |      0.583 |
| material+acquisition | Batch_2 |               1 | edge_charging_inlens             | acquisition   |     -0.908 |
| material+acquisition | Batch_2 |               2 | F06_c2_clark_evans_R             | material      |     -0.831 |
| material+acquisition | Batch_2 |               3 | F04_c2_eqdiam_p90_px             | material      |     -0.637 |
| material+acquisition | Batch_3 |               1 | sharpness                        | acquisition   |     -0.748 |
| material+acquisition | Batch_3 |               2 | noise_sigma                      | acquisition   |     -0.692 |
| material+acquisition | Batch_3 |               3 | edge_charging_inlens             | acquisition   |      0.597 |

## Out-of-distribution screen (robust RMS z to each batch, alpha = 0.05)

| family               | batch   |   n |   matches_none |   in_reference |
|:---------------------|:--------|----:|---------------:|---------------:|
| acquisition          | Batch_1 |   7 |              0 |              7 |
| acquisition          | Batch_2 |   7 |              0 |              7 |
| acquisition          | Batch_3 |  17 |              0 |             16 |
| material             | Batch_1 |   7 |              0 |              7 |
| material             | Batch_2 |   7 |              0 |              7 |
| material             | Batch_3 |  17 |              0 |             16 |
| material+acquisition | Batch_1 |   7 |              0 |              7 |
| material+acquisition | Batch_2 |   7 |              0 |              7 |
| material+acquisition | Batch_3 |  17 |              0 |             16 |

Per image: `ood.csv` (`in_distribution_of`, `matches_none`, `in_reference`).

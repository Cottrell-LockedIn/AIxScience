# Batch identification and OOD screen: `kpi_per_image`

Provenance: config_path=configs/v1.yaml, config_hash=de199d6c8d69, git_sha=370d083, features=results/kpi_per_image.parquet, features_sha256=e377d9950dea, seed=0, n_perm=200, heldout=none

Target (Polaron): what differs between batches; categorise held-back images as Batch_1/2/3 or `matches none`. Batch_3 is the supplier's promised baseline; Batch_1/2 are different, not worse. No good/bad claim follows.

Reading guide: LOIO = estimate for held-back images from the same acquisition sessions; LOGO = estimate for a new session. `p_perm` is the image-level label-permutation p of the accuracy; an accuracy inside the null band means the family does not identify the batch. Drivers are standardised logistic-regression coefficients tagged material or acquisition, so a separation is never reported without saying what carries it.

## Accuracy per feature family

| family               | model   | split   |   n_features |   accuracy |   balanced_accuracy |   chance_majority |   null_mean |   null_p95 |   p_perm |   recall_Batch_1 |   recall_Batch_2 |   recall_Batch_3 |
|:---------------------|:--------|:--------|-------------:|-----------:|--------------------:|------------------:|------------:|-----------:|---------:|-----------------:|-----------------:|-----------------:|
| material             | logreg  | LOIO    |            8 |      0.581 |               0.493 |             0.548 |       0.356 |      0.516 |  0.0448  |            0.571 |            0.143 |            0.765 |
| material             | logreg  | LOGO    |            8 |      0.452 |               0.359 |             0.548 |       0.334 |      0.516 |  0.139   |            0.429 |            0     |            0.647 |
| acquisition          | logreg  | LOIO    |            6 |      0.71  |               0.655 |             0.548 |       0.341 |      0.516 |  0.00498 |            0.714 |            0.429 |            0.824 |
| acquisition          | logreg  | LOGO    |            6 |      0.645 |               0.56  |             0.548 |       0.344 |      0.548 |  0.00498 |            0.429 |            0.429 |            0.824 |
| material+acquisition | logreg  | LOIO    |           14 |      0.613 |               0.569 |             0.548 |       0.365 |      0.55  |  0.0348  |            0.571 |            0.429 |            0.706 |
| material+acquisition | logreg  | LOGO    |           14 |      0.581 |               0.521 |             0.548 |       0.352 |      0.516 |  0.0199  |            0.571 |            0.286 |            0.706 |

## Top-3 drivers per batch (LOIO, logreg)

| family               | batch   |   rank_in_batch | feature                    | driver_type   |   coef_std |
|:---------------------|:--------|----------------:|:---------------------------|:--------------|-----------:|
| acquisition          | Batch_1 |               1 | sharpness                  | acquisition   |      0.931 |
| acquisition          | Batch_1 |               2 | noise_sigma                | acquisition   |      0.725 |
| acquisition          | Batch_1 |               3 | curtaining_score           | acquisition   |     -0.646 |
| acquisition          | Batch_2 |               1 | edge_charging_inlens       | acquisition   |     -0.828 |
| acquisition          | Batch_2 |               2 | mean_grey                  | acquisition   |     -0.429 |
| acquisition          | Batch_2 |               3 | hstripe_score              | acquisition   |     -0.152 |
| acquisition          | Batch_3 |               1 | sharpness                  | acquisition   |     -0.903 |
| acquisition          | Batch_3 |               2 | noise_sigma                | acquisition   |     -0.819 |
| acquisition          | Batch_3 |               3 | edge_charging_inlens       | acquisition   |      0.653 |
| material             | Batch_1 |               1 | c0_region_eqdiam_median_px | material      |     -1.01  |
| material             | Batch_1 |               2 | c2_count_density_per_Mpx   | material      |     -0.55  |
| material             | Batch_1 |               3 | frac_c0                    | material      |     -0.497 |
| material             | Batch_2 |               1 | c0_region_area_mean_px     | material      |      0.525 |
| material             | Batch_2 |               2 | c2_count_density_per_Mpx   | material      |     -0.461 |
| material             | Batch_2 |               3 | c0_region_eqdiam_median_px | material      |      0.397 |
| material             | Batch_3 |               1 | c2_count_density_per_Mpx   | material      |      1.01  |
| material             | Batch_3 |               2 | frac_c0                    | material      |      0.727 |
| material             | Batch_3 |               3 | c0_region_eqdiam_median_px | material      |      0.616 |
| material+acquisition | Batch_1 |               1 | curtaining_score           | acquisition   |     -0.736 |
| material+acquisition | Batch_1 |               2 | sharpness                  | acquisition   |      0.604 |
| material+acquisition | Batch_1 |               3 | c0_region_eqdiam_median_px | material      |     -0.572 |
| material+acquisition | Batch_2 |               1 | edge_charging_inlens       | acquisition   |     -0.761 |
| material+acquisition | Batch_2 |               2 | c0_region_area_mean_px     | material      |      0.31  |
| material+acquisition | Batch_2 |               3 | hstripe_score              | acquisition   |     -0.291 |
| material+acquisition | Batch_3 |               1 | sharpness                  | acquisition   |     -0.747 |
| material+acquisition | Batch_3 |               2 | noise_sigma                | acquisition   |     -0.695 |
| material+acquisition | Batch_3 |               3 | edge_charging_inlens       | acquisition   |      0.653 |

## Out-of-distribution screen (robust RMS z to each batch, alpha = 0.05)

| family               | batch   |   n |   matches_none |   in_reference |
|:---------------------|:--------|----:|---------------:|---------------:|
| acquisition          | Batch_1 |   7 |              0 |              7 |
| acquisition          | Batch_2 |   7 |              0 |              7 |
| acquisition          | Batch_3 |  17 |              0 |             16 |
| material             | Batch_1 |   7 |              0 |              6 |
| material             | Batch_2 |   7 |              1 |              5 |
| material             | Batch_3 |  17 |              0 |             16 |
| material+acquisition | Batch_1 |   7 |              1 |              6 |
| material+acquisition | Batch_2 |   7 |              1 |              5 |
| material+acquisition | Batch_3 |  17 |              0 |             16 |

Per image: `ood.csv` (`in_distribution_of`, `matches_none`, `in_reference`).

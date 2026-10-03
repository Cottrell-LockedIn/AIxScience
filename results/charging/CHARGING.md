# Charging / topography glow in the class-2 (bright BSE) mask

Phase identity: class 2 bright = silicon, class 1 mid = graphite, class 0 dark = void/pore, **stated by Polaron, not image-verified**.
Produced by `python -m qc charging` with `configs/v1.yaml@1bec114301c3`, git `790c1ef`; n = 31 pixel-registered images (independent unit; 0 skipped as not registered). Units px; 25 nm/px unconfirmed.

## Method

Stitched BSE label mask per image (`qc segment` tiles, later tile wins). Inlens and ETD/SE images median-filtered (5 px, as the BSE before segmentation), robust z per image (median / 1.4826 MAD over analysed pixels). `bright_both_pP` = class 2 AND z_Inlens >= P-th percentile AND z_SE >= P-th percentile (P = 90, 95, 99). `edge_glow_nN` = class 2 AND within N px of class 0 AND bright in both at p95 (N = 3, 5, 10). Flagged class-2 pixels are relabelled class 1 and F02-F05 recomputed with the `qc features` definitions (8-connected particles >= 20 px, border exclusion for F03/F04, counting frame for F05). Control: `frac_c2_dark_both_p50` = class-2 area below the median in both SE channels (Z-contrast-only candidates, i.e. retained with certainty by any SE-based mask).

## Observed: fraction of class-2 area flagged, per batch (median over images; max in brackets)

| batch | n | bright_both_p90 | bright_both_p95 | bright_both_p99 | edge_glow_n10 | edge_glow_n3 | edge_glow_n5 |
|---|---|---|---|---|---|---|---|
| Batch_1 | 7 | 0.384 (0.435) | 0.089 (0.121) | 0.010 (0.025) | 0.007 (0.027) | 0.000 (0.004) | 0.002 (0.011) |
| Batch_2 | 7 | 0.251 (0.420) | 0.074 (0.133) | 0.012 (0.021) | 0.009 (0.022) | 0.001 (0.002) | 0.003 (0.009) |
| Batch_3 | 17 | 0.162 (0.355) | 0.070 (0.109) | 0.010 (0.064) | 0.014 (0.023) | 0.001 (0.002) | 0.005 (0.008) |

## Observed: SE brightness of class 2 vs class 1 (median over images)

| batch | median z_Inlens of class 2 | of class 1 | median z_SE of class 2 | of class 1 | class-1 area bright-in-both p95 | class-2 area dark-in-both p50 |
|---|---|---|---|---|---|---|
| Batch_1 | 1.31 | 0.00 | 3.71 | 0.00 | 0.0046 | 0.0067 |
| Batch_2 | 1.33 | 0.00 | 4.14 | 0.00 | 0.0061 | 0.0096 |
| Batch_3 | 1.85 | -0.16 | 4.13 | 0.00 | 0.0087 | 0.0002 |

## Observed: batch medians of F02-F05 with vs without the mask

Within-batch IQR is that of the unmasked feature; `>IQR` marks |median masked - median unmasked| > IQR.

| batch | variant | F02 unmasked | F02 masked | >IQR | F03 unmasked | F03 masked | >IQR | F04 unmasked | F04 masked | >IQR | F05 unmasked | F05 masked | >IQR | particles removed (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Batch_1 | bright_both_p90 | 0.089 | 0.056 | no | 8.137 | 7.979 | no | 23.939 | 21.188 | no | 116.287 | 111.460 | no | 304 / 1592 |
| Batch_1 | bright_both_p95 | 0.089 | 0.080 | no | 8.137 | 8.058 | no | 23.939 | 24.591 | no | 116.287 | 109.539 | no | 185 / 1592 |
| Batch_1 | bright_both_p99 | 0.089 | 0.088 | no | 8.137 | 8.137 | no | 23.939 | 24.364 | no | 116.287 | 112.228 | no | 42 / 1592 |
| Batch_1 | edge_glow_n10 | 0.089 | 0.088 | no | 8.137 | 8.137 | no | 23.939 | 24.397 | no | 116.287 | 110.230 | no | 70 / 1592 |
| Batch_1 | edge_glow_n3 | 0.089 | 0.089 | no | 8.137 | 8.137 | no | 23.939 | 24.048 | no | 116.287 | 115.886 | no | 7 / 1592 |
| Batch_1 | edge_glow_n5 | 0.089 | 0.089 | no | 8.137 | 8.137 | no | 23.939 | 24.191 | no | 116.287 | 114.481 | no | 28 / 1592 |
| Batch_2 | bright_both_p90 | 0.097 | 0.068 | yes | 7.979 | 7.818 | no | 24.685 | 22.343 | yes | 109.331 | 130.745 | no | 255 / 1697 |
| Batch_2 | bright_both_p95 | 0.097 | 0.085 | no | 7.979 | 7.818 | no | 24.685 | 24.634 | no | 109.331 | 111.514 | no | 138 / 1697 |
| Batch_2 | bright_both_p99 | 0.097 | 0.096 | no | 7.979 | 7.899 | no | 24.685 | 24.934 | no | 109.331 | 109.400 | no | 27 / 1697 |
| Batch_2 | edge_glow_n10 | 0.097 | 0.096 | no | 7.979 | 7.899 | no | 24.685 | 25.241 | no | 109.331 | 104.342 | no | 58 / 1697 |
| Batch_2 | edge_glow_n3 | 0.097 | 0.097 | no | 7.979 | 7.979 | no | 24.685 | 24.747 | no | 109.331 | 108.845 | no | 1 / 1697 |
| Batch_2 | edge_glow_n5 | 0.097 | 0.097 | no | 7.979 | 7.939 | no | 24.685 | 24.873 | no | 109.331 | 105.929 | no | 20 / 1697 |
| Batch_3 | bright_both_p90 | 0.101 | 0.086 | no | 8.137 | 7.979 | no | 26.607 | 24.096 | no | 130.714 | 127.283 | no | 357 / 1880 |
| Batch_3 | bright_both_p95 | 0.101 | 0.096 | no | 8.137 | 8.058 | no | 26.607 | 27.526 | no | 130.714 | 133.553 | no | 195 / 1880 |
| Batch_3 | bright_both_p99 | 0.101 | 0.100 | no | 8.137 | 8.137 | no | 26.607 | 25.982 | no | 130.714 | 129.233 | no | 49 / 1880 |
| Batch_3 | edge_glow_n10 | 0.101 | 0.100 | no | 8.137 | 8.058 | no | 26.607 | 26.231 | no | 130.714 | 127.697 | no | 67 / 1880 |
| Batch_3 | edge_glow_n3 | 0.101 | 0.101 | no | 8.137 | 8.137 | no | 26.607 | 26.576 | no | 130.714 | 129.548 | no | 5 / 1880 |
| Batch_3 | edge_glow_n5 | 0.101 | 0.100 | no | 8.137 | 8.137 | no | 26.607 | 26.559 | no | 130.714 | 127.907 | no | 26 / 1880 |

## Figures

- `results/charging/figures/Batch_1_ffwubibz_00000_01024.png`
- `results/charging/figures/Batch_2_epqdaau9_00000_02048.png`
- `results/charging/figures/Batch_3_pl8uabbv_00000_00000.png`

## OBSERVED vs INFERRED

- OBSERVED: the flagged fractions, particle counts and F02-F05 deltas above, per image and per batch.
- INFERRED: a class-2 pixel that is in the top few percent of both SE detectors has a brightness that topography or charging alone could explain; relabelling it is a conservative sensitivity check, not a correction.
- NOT ESTABLISHED: that any retained class-2 pixel is silicon. This test cannot prove a bright region is silicon; it can only remove pixels whose brightness is explained by topography/charging. If class 2 is systematically brighter than class 1 in the SE detectors (table above), the premise 'a true high-Z particle is not bright in SE' does not hold for this dataset and the mask measures SE brightness of the class-2 phase, not charging specifically.
- Nothing here is a statement about material quality.

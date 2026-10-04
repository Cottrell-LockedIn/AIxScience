# Inspection notes

`phase_identity: stated by Polaron, not image-verified` (class 0 void, class 1 graphite, class 2 silicon; Si vs SiOx indistinguishable in BSE; binder/additive lumped). Units px.

## B1 5-tile manual check (Phase B)

Tiles drawn with seed 0, 5 different images, at least one per batch; one panel per tile with raw BSE, three-class overlay, each class mask, tile ID and every B1 KPI value: `results/inspection/b1_tile_<tile_id>.png`. Inspected at full panel resolution by the Phase B author. Values below are copied from the panel titles.

| tile | batch | frac c0 / c1 / c2 | c2 count /Mpx | c2 eqdiam median / p90 px | c1 largest-component frac | c0 crack-like frac | c2 TPC length px |
|---|---|---|---|---|---|---|---|
| avn74qx1_BSE_00512_05960 | Batch_2 | 0.0889 / 0.828 / 0.0833 | 32.4 | 12.8 / 97.9 | 0.999 | 0.0647 | 63.7 |
| b3esycq1_BSE_01116_01536 | Batch_2 | 0.0875 / 0.825 / 0.0871 | 118 | 9.27 / 25.5 | 0.999 | 0.135 | 57.4 |
| i9jiqjwl_BSE_00000_00000 | Batch_2 | 0.102 / 0.58 / 0.317 | 840 | 6.68 / 11.2 | 0.363 | 0.0674 | 15.2 |
| iv6g2oq0_BSE_00000_01024 | Batch_1 | 0.0933 / 0.865 / 0.0416 | 73.4 | 7.82 / 28.1 | 0.999 | 0.198 | 32.4 |
| pl8uabbv_BSE_00000_04608 | Batch_3 | 0.0712 / 0.858 / 0.0706 | 27.7 | 14.0 / 69.0 | 0.998 | 0.0761 | 92.5 |

What the panels show:

1. **Silicon (class 2)**: in 4 of 5 tiles the bright, angular particles are captured as compact class-2 objects with clean outlines; the KPI values (fraction, size, TPC length) track what is visible (the tile with one large particle has the largest p90 and TPC length). Small class-2 specks also appear along bright flake edges and at the image border (e.g. the bright diagonal strip at the lower left of iv6g2oq0), which inflates the class-2 count and lowers the median size. These are the "bright halo on flake edges" risk.
2. **Segmentation defect, i9jiqjwl_BSE_00000_00000 (Batch_2)**: a tile with almost no distinct bright particles is still split into three classes by per-tile multi-Otsu. Large graphite areas become speckled class 2 (frac c2 0.317 vs 0.04-0.09 in the other tiles, 840 particles/Mpx, median 6.7 px). This is the known "particle-poor tile split into 3 classes" risk. It is an S4 design issue (per-tile thresholds), so it is proposed to the owner, not fixed: options are image-level thresholds, or flagging tiles whose class-2 histogram mode is not separated (e.g. a minimum between-class contrast). Until decided, class-2 KPIs from such tiles are kept and their effect is visible through G3 (threshold sensitivity) and G4 (reference outliers).
3. **Graphite (class 1)** is one connected matrix in 4 of 5 tiles (largest component 0.998-0.999 of class 1). Connected components therefore do not resolve individual flakes; `c1_flake_eqdiam_median_px` and `c1_flake_aspect_median` measure small detached fragments, not flakes. This is what the pre-registered percolation rule tests for at image level (`docs/PHASE_B_PREREGISTRATION.md` §1).
4. **Void (class 0)**: the dark inter-flake gaps and pores are segmented as expected. Most void is elongated along the flake direction, so `c0_cracklike_frac` (share of void in components with aspect ≥ 5) mostly measures elongated inter-flake porosity, not cracks. It cannot separate coating cracks (FM07) from preparation damage (A02) or normal inter-flake gaps. Treat it as a void-shape descriptor.
5. **Pore size** (`c0_region_eqdiam_median_px`, 8.7-12.3 px here) is dominated by many small dark regions; the large gaps carry the area (`c0_region_area_mean_px` 568-1040 px).

## B4/B6 review notes

`F08_c0_local_thickness_median_px` is quantised to 2 px steps, while the Batch_3 MAD is
2 px. Its G3 threshold-sensitivity and leave-one-out z values are therefore
resolution-limited. A continuous-radius local-thickness measurement is a v2 candidate;
the v1 F08 definition is unchanged.

On the seeded, centre-scaled synthetic texture, the smallest sampled positive scale
deviation flagged by the current registration gates is 0.5% (applied scale 1.005);
1.004 passes, while the first sampled negative-side failure is 0.6% (0.994). This is
an effective scale-detection limit of about 0.5% on this texture and sweep, not a
general calibration. The estimator shrinks small applied deviations toward 1 and
returns exactly 1.0 for the identity image. `mgxahqnk` Inlens has estimated scale
0.997323059300627, an absolute deviation of about 0.27% from 1.0, with rotation −0.03°;
that is an unconfirmed scale difference, neither ruled out nor confirmed. The reported
registration resolution for this image is 0.01° and 0.000122 in scale.

Comparing the 31 images from 7c43868 to d90cdea, `glow_frac_of_c2` changed in 29/31
(maximum absolute change 0.16940548296639446). For `xgj4xftb`, scale changed from
1.0 to 1.0003655936465718, glow fraction from 0 to 0.16940548296639446, and
`F02_glow_excluded` from 0.13680284617615057 to 0.11362769394850242. For `hawkfj64`,
scale changed from 1.0 to 1.000487487894953, glow fraction from 0 to
0.15635487194278472, and `F02_glow_excluded` from 0.09150235344225056 to
0.07719551468732405. For `xgj4xftb`, the 95th-percentile threshold on aligned Inlens
moved from 255.0 to 254.189728; all 1,524,868 class-2 pixels remained valid, and
applying the old cutoff to the new aligned intensities still yielded zero glow, while
the new cutoff yielded 258,320 glow pixels (`src/qc/charging.py:30-40`). The 0.000366
scale change therefore shifts interpolated intensities across the percentile cutoff;
the valid class-2 count did not change, so an edge band does not explain this example,
and `align_image` has no `scale == 1` shortcut (`src/qc/register.py:215-247`).

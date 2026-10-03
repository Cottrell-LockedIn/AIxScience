# Tier-1 image-level features (features_v1)

Phase identity: **stated by Polaron, not image-verified** (class 2 bright = silicon, class 1 mid = graphite, class 0 dark = void/pore; Si vs SiOx indistinguishable in BSE; binder / conductive additive lumped into class 0 or 1; no chemistry claims beyond the three stated identities).

Produced by `python -m qc features` with `configs/v1.yaml@1bec114301c3`, `configs/features_v1.yaml@a03b4b7c5a70`, git `d593ac3`; 31 images, 1443 BSE tiles, 75 s wall.

Units are px / px^2 / fractions. `*_nm_if25` columns are px x 25 and are only meaningful if the unconfirmed 25 nm/px pixel size is true. The image (8-char `sample_id`) is the independent unit (n = 31); `features_by_tile.parquet` rows are pseudo-replicates for diagnostics only.

## Conventions

- Stitching: tile masks pasted in (y, x) order, later tile wins (later_tile_wins); features computed once per image.
- Class-2 particles: 8-connected, re-filtered at min_object_px = 20 after stitching.
- F03, F04, F07: particles touching the analysed-area border are excluded (ASTM E1245 style).
- F05: unbiased counting frame, particles touching the left or bottom border are not counted.
- F06: Donnelly (1978) edge-corrected CSR expectation; `F06_c2_clark_evans_z` is the normal deviate.
- F08: Hildebrand-Rueegsegger local thickness via distance transform; integer radii exact up to 16 px, geometric bins (x1.2) above.
- F09: chords touching the border are excluded as censored.
- F10: non-overlapping 512 px windows from the top-left corner.

## Registry

| id | column | class | unit | definition | provenance |
|---|---|---|---|---|---|
| F01 | `F01_c0_area_fraction` | 0 | fraction | class-0 pixels / analysed pixels of the stitched per-image mask | stereological area fraction (Delesse); class identity stated by Polaron, not image-verified |
| F02 | `F02_c2_area_fraction` | 2 | fraction | class-2 pixels / analysed pixels of the stitched per-image mask (before min-size re-filtering, same as kpi frac_c2) | stereological area fraction (Delesse); class identity stated by Polaron, not image-verified |
| F03 | `F03_c2_eqdiam_median_px` | 2 | px | median over interior class-2 particles (8-connected, >= min_object_px, not touching the border) of sqrt(4 A / pi) | ASTM E1245 border exclusion; equivalent circular diameter |
| F04 | `F04_c2_eqdiam_p90_px` | 2 | px | 90th percentile of the same particle set as F03 | ASTM E1245 border exclusion; equivalent circular diameter |
| F05 | `F05_c2_count_density_per_Mpx` | 2 | 1/Mpx | class-2 particles (8-connected, >= min_object_px) counted with an unbiased counting frame (particles touching the left or bottom border excluded) per 1e6 analysed px | Gundersen (1977) unbiased counting frame |
| F06 | `F06_c2_clark_evans_R` | 2 | ratio | mean nearest-neighbour distance between class-2 particle centroids / CSR expectation with Donnelly edge correction for the rectangular analysed area (R < 1 clustered, R = 1 random, R > 1 regular) | Clark & Evans (1954); Donnelly (1978) edge correction |
| F07 | `F07_c2_solidity_area_weighted_median` | 2 | ratio | area-weighted median over interior class-2 particles of particle area / convex hull area | skimage regionprops solidity; ASTM E1245 border exclusion |
| F08 | `F08_c0_local_thickness_median_px` | 0 | px | median over class-0 pixels of the Hildebrand-Rueegsegger local thickness (diameter of the largest inscribed disc containing the pixel), computed via the Euclidean distance transform | Hildebrand & Rueegsegger (1997), 2D implementation |
| F09 | `F09_c0_chord_anisotropy_h_over_v` | 0 | ratio | mean horizontal chord length / mean vertical chord length through class 0; chords touching the analysed-area border are excluded as censored | stereological chord-length (intercept) analysis |
| F10 | `F10_c0_fraction_iqr_512px` | 0 | fraction | interquartile range of the class-0 area fraction over non-overlapping 512 px windows fully inside the analysed area | within-image heterogeneity, pre-registered |
| F11 | `F11_c2_perimeter_fraction_adjacent_c0` | 2 | fraction | among class-2 boundary pixels (at least one 4-neighbour not class 2), the fraction with at least one class-0 4-neighbour | pixel-boundary contact fraction, pre-registered |

Files: `features_by_image.parquet` / `.csv`, `features_by_tile.parquet`, `features_batch_medians.csv`. Parquet metadata carries `phase_identity`, `features_config` and `provenance`.

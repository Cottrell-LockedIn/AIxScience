# KPI implementation audit

**Status:** implementation audit of the frozen/exploratory engine on 4 October
2026. This document separates code facts from the scientist handoff's proposed
display controls. It does not create acceptance criteria, a defect model, or a
claim about battery performance.

## Scope and evidence

The source-code findings below come from `src/qc/features.py`,
`src/qc/segment.py`, `src/qc/tiles.py`, `src/qc/heldout.py`, and
`configs/features_v1.yaml`. The control ranges and their caveats come from the
user-supplied *Silicon–Graphite Micrograph Model Capabilities and Control-Range
Rationale* handoff, section 11. They are proposed wrapper settings only.

The related local material handoff is:

- `/Users/bedelau/Documents/ChatGPT/Cottrell/handoff/devin_sem_handoff/microstructure_feature_catalogue.md`
- `/Users/bedelau/Documents/ChatGPT/Cottrell/handoff/devin_sem_handoff/dataset_audit.md`
- `/Users/bedelau/Documents/ChatGPT/Cottrell/handoff/devin_sem_handoff/manifest.csv`
- `/Users/bedelau/.codex/attachments/00c7a99b-5df2-4321-ad16-06077854870e/Pasted text.txt`

The earlier local catalogue uses a different P namespace from the latest handoff. The authoritative current mapping is the user's 4 October manufacturing/formation and future-service handoff, normalized in `frontend/src/riskCatalog.json`: P01–P14 and U01–U14. The references are supplied scientific sources, not independently re-reviewed papers in this code audit. No paper observation becomes a specimen limit.

`phase_identity: stated by Polaron, not image-verified`: class 0 is dark
void/pore, class 1 mid graphite, and class 2 bright silicon. BSE alone cannot
distinguish Si from SiOx; binder and conductive additive are lumped into the
contrast classes.

## What the code actually measures

Before feature extraction, the engine takes BSE channel 0, removes 8 pixels on
each edge, makes 1024 px tiles at 512 px stride, and anchors a final full tile
to each bottom/right edge. The tiles overlap; when stitching, later tiles in
row-major `(y, x)` order overwrite earlier tiles. Therefore every feature uses
the complete **cropped** image mask, not a sum or average of overlapping tile
measurements and not the original TIFF area.

Each tile is median-filtered with a 5 px window, thresholded independently by
three-class multi-Otsu, then class-0 and class-2 regions smaller than 20 px are
removed and holes smaller than 20 px are filled. Class 2 has priority over
class 0. A tile with fewer than three intensity levels falls back to all class
1 and writes NaN thresholds. A stitched image containing an uncovered `255`
sentinel or a value other than 0/1/2 is rejected before measurements are made.

| Feature | Exact implementation | Important boundary / denominator rule |
|---|---|---|
| F01 | class-0 pixel count / cropped stitched-image pixel count | Full analysed cropped mask. |
| F02 | class-2 pixel count / cropped stitched-image pixel count | Calculated before the post-stitch object relabelling used by F03–F07. |
| F03 | median `sqrt(4A/pi)` of class-2 connected components | 8-connectivity; components under 20 px removed again; excludes components touching any analysed-image border. |
| F04 | 90th percentile of the same F03 population | Same components, number-based NumPy percentile. |
| F05 | count-frame class-2 particle count / cropped analysed area × 1,000,000 | 8-connected, post-filter objects. Its Gundersen frame includes only components with `min_col > 0` and `max_row < height`, so left/bottom-border objects are excluded. |
| F06 | mean nearest-neighbour centroid distance / Donnelly-corrected CSR expectation | Uses all post-filter class-2 components, including border-touching ones; rectangular cropped image area and perimeter are used. |
| F07 | area-weighted median solidity | Same interior-only component population as F03/F04; solidity is `regionprops` area / convex-hull area. |
| F08 | median of local-thickness values over class-0 pixels | Hildebrand–Rueegsegger-style 2-D maximal-disc implementation via medial axis / Euclidean distance transform. Integer radii through 16 px; above that, bins grow ×1.2. |
| F09 | mean uncensored horizontal void-chord length / mean uncensored vertical void-chord length | Any chord touching the corresponding image border is excluded. It is not an orientation angle. |
| F10 | `Q75-Q25` of F01 over non-overlapping 512×512 windows | Windows start at the cropped top-left and trailing strips smaller than 512 px are excluded. It does not use tile stride or partial windows. |
| F11 | class-2 boundary pixels with a 4-neighbour class-0 pixel / all class-2 boundary pixels | Boundary means at least one 4-neighbour is not class 2. This is pixel-contact fraction, not calibrated interface length or 3-D electrical contact. |

## Missing / unavailable states

The present engine has no aspect-ratio output. The proposed twelfth control
(per-phase aspect ratio, 1–50 logarithmic display preset) is **not F01–F11**,
is not a classifier input, and must show `Not measured in v1`.

The raw extraction functions return NaN when a quantity cannot be calculated:

- F03, F04 and F07: no accepted interior class-2 component.
- F06: fewer than two post-filter class-2 components.
- F08: no class-0 pixel.
- F09: no uncensored chord in either direction, or zero vertical mean.
- F10: no full 512 px window.
- F11: no class-2 boundary pixel.

The training data are finite, but the exploratory inference path does not
impute non-finite F01–F11 values before passing them to the frozen scaler and
classifier. A sparse or degenerate upload can therefore fail rather than yield
a meaningful probability. The UI must report a failed/unavailable analysis,
not turn these cases into zeros or a defect verdict.

## Proposed ranges: display guidance only

The supplied defaults are F01 0.05–0.80; F02 0–0.60; F03 5–1200 px; F04
5–2000 px; F05 0–30,000/Mpx; F06 0–3; F07 0–1; F08 2–1200 px; F09 0.1–10;
F10 0–1; F11 0–1. They are not model thresholds and should not change the
frozen recipe, probability, tier, or batch prediction. Values outside a soft
range must remain visible with a plain-language review prompt, never clipping
or a claim of physical impossibility.

The 5 px F03/F04 floor follows the 20 px cleanup area only under the circular
equivalent-diameter conversion. F05's 30,000/Mpx ceiling is conditional on a
0.60 bright-area display preset, disjoint post-cleanup objects, and the same
area denominator. The code supports the shared denominator and post-filter
objects, but it does not make the 0.60 preset a scientific constraint.

## Calibration and run `1656d9bdb6dd4dc29914304a060a4442`

The 0.025 µm/px user confirmation applies **only** to supplied
`img_4ih2ggld_BSE.tif`, SHA-256
`a7fa8987f58071205743249f0b089912c3cdab5289d48aa4dc21e5b73aa21b09`.
It does not apply to `b3esycq1` or to arbitrary uploads. Thus the run values
below must remain pixels, particles/Mpx, or dimensionless ratios/fractions.

Run `1656d9bdb6dd4dc29914304a060a4442` is a one-image **exploratory** BSE-only
run. It cropped the 2156×7000 input to a 2140×6984 analysed mask (52 tiles),
saved mask SHA-256
`f01c30ca031fb76b47f26de1d99865cca1d15ce24b4c1f572a4cf8bd7d47579b`,
and records crop offset `[8, 8]`.

| F01 | F02 | F03 px | F04 px | F05 /Mpx | F06 | F07 | F08 px | F09 | F10 | F11 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.095804 | 0.109739 | 7.938750 | 23.652916 | 141.913158 | 0.722384 | 0.876117 | 24.0 | 1.192611 | 0.045665 | 0.001009 |

These numbers only describe the fixed segmentation mask. Seven of the eleven
features are threshold-sensitive in the Phase B assessment (F01–F07 `drop`);
F08–F11 remain `investigate`. The run has no Inlens, ETD, or SE companion,
and reports the associated caveats.

The separate model result is Batch_2 probability 0.789, with a high tier and
within-Batch_3 embedding flag. It is a batch-match result, **not** a defect or
pass probability: LOIO Batch_2 bets were correct 2/9 overall and 1/3 for high
tier. Two of the three leading drivers are acquisition-confounded embedding
components; the physical feature driver, F04, is threshold-sensitive. Sections
12 and 13 of the supplied science catalogue are hypothesis/measurement
guidance. They do not establish an executable failure model or acceptable KPI
cutoffs.

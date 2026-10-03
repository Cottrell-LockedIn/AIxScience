# Phase B pre-registration: statistics (B4), validation gates (B5) and verdict rules (B7)

Status: pre-registered, exploratory (not frozen). Written on 2026-10-03 **before any batch contrast of the Phase B features, KPIs or embeddings was computed**. Machine-readable twin: `configs/stats_v1.yaml` (its sha256 prefix is stamped on every B4/B5/B7 row as `stats_config_hash`). Gate rules G1-G5 and the keep rule are quoted from the owner's handover; everything this document adds is a definition the handover leaves open. No rule is loosened after results are seen; any later change is logged as exploratory with its reason.

ID mapping used here: repository features `F01-F11` (`configs/features_v1.yaml`); consultant failure modes `FM01-FM22` (the consultant handoff numbers them F01-F22); preparation/measurement modes `A01-A06`. Phase identities: class 0 void, class 1 graphite, class 2 silicon — `phase_identity: stated by Polaron, not image-verified` (Si vs SiOx indistinguishable in BSE; binder/additive lumped). Units are px; pixel size is unconfirmed.

Disclosure: the author saw summary numbers from an earlier, discarded Phase B attempt in earlier sessions. To avoid steering, the gate rules are verbatim from the handover and every free choice below is fixed here, before contrasts, and justified by a design reason, not by data.

## 1. Inputs and unit

- Unit = image (8-character `sample_id`, n = 31: Batch_1 7, Batch_2 7, Batch_3 17). Tiles are pseudo-replicates; every permutation, split, bootstrap and jackknife resamples images, never tiles.
- Reference = `Batch_3` (configs/v1.yaml `stats.reference_batch`, Polaron-stated supplier-promised baseline). Batch_1/2 are "different, not better or worse".
- Tables (one row per image):
  - KPI table `results/kpi_per_image.parquet` (B1; per-image mean over tiles), columns listed in `configs/stats_v1.yaml: features`.
  - Feature table `results/features_per_image.parquet` (B2; F01-F11 on the stitched image mask).
  - Embedding table `results/emb_per_image.parquet` (B3; DINOv2 ViT-S/14 mean-patch vectors, per image and channel). Primary channel BSE (composition contrast, least charging). Inlens and ETD are reported as secondary and never count as a verdict line (they are more acquisition-sensitive). The 4 SE stems are not pooled with ETD.
- Graphite flake KPIs (`c1_flake_*`) are only measurable if class 1 is not one percolating matrix: if `c1_largest_component_frac` > 0.5 in more than half of the images, both columns are dropped (G5 fail: "not observable as discrete objects").

## 2. B4 statistics

**Reference scale.** For feature f, `s_f` = 1.4826 × MAD of the 17 Batch_3 images. If `s_f` = 0, use 1.4826 × MAD of all 31 images; if that is 0, the feature is excluded and listed.

**Standardised median shift.** For a pair of batches (a, b): `z_f(a,b) = (median_a(f) − median_b(f)) / s_f`. Per-table aggregate: `D(a,b) = sqrt(mean_f z_f²)` over the table's included features (KPI table and F table reported separately).

**Embedding distances** (per channel; image vectors L2-normalised; Euclidean distance):
- Energy distance `E = 2·mean‖x−y‖ − mean_{i≠j}‖x_i−x_j‖ − mean_{i≠j}‖y_i−y_j‖`.
- MMD² unbiased estimator, RBF kernel, bandwidth = median pairwise distance over all images of that channel (label-free, fixed before any permutation).

**Image-label permutation p.** For every pair (B1-B2, B1-B3, B2-B3) and every statistic (each `z_f`, each `D`, E, MMD²): pool the two batches' images, reassign labels keeping group sizes, 2000 permutations, fixed seed 20261003; `p = (1 + #{|stat_perm| ≥ |stat_obs|}) / (1 + 2000)` (two-sided for `z_f`, one-sided for D, E, MMD²). Smallest attainable p = 1/2001 ≈ 0.0005.

**Multiple testing.** Benjamini-Hochberg at 0.05 within each family: (i) per-feature `z_f` tests: all features of both tables × 3 pairs; (ii) aggregate D tests: 2 tables × 3 pairs; (iii) embedding tests: channels × {E, MMD²} × 3 pairs; (iv) covariate tests: covariates × 3 pairs.

**Batch_3 split-half null bands.** 1000 random splits of the 17 Batch_3 images into 7 + 10. Why 7 + 10: the 7-image half has the same size as Batch_1 and Batch_2, so the null statistic has the same small-sample noise on the test side; the 10 remaining images play the reference. Because the pseudo-reference (10) is smaller than the real reference (17), the null spread is wider than the true null: bands are conservative (fewer "outside" calls). Each statistic (`|z_f|`, D, E, MMD²) is computed on every split with the same `s_f`; band95 / band99 = 95th / 99th percentile of the split values. A Batch_k-vs-Batch_3 statistic is "within" if ≤ band95, "outside" if > band99, otherwise "between". The B1-B2 pair gets permutation p only (no baseline band applies).

**Acquisition-confound control** (reported alongside every table):
- Covariates per image (n = 31): BSE `noise_sigma`, `sharpness`, `curtaining_score`, `hstripe_score`, `edge_charging`; Inlens `edge_charging` (from `results/artefacts_per_image.parquet`); image `height` and `nm_per_px_if_tag_true` (from `results/audit/images.csv`). Grey-level mean/std/p01/p99 are excluded on purpose because BSE grey level carries composition (material) signal.
- Covariate distances: the same `z`, D, permutation and BH machinery applied to the covariates. **Acquisition drift** for a pair = any covariate with BH-adjusted p < 0.05.
- Residualised contrasts: each feature (and each embedding dimension) is regressed on the standardised covariates plus intercept by OLS over all 31 images without batch labels; the residuals go through the same distances and permutation tests. This is conservative: where batch and covariates are correlated, residualisation also removes real material differences.

**Consistency score per batch** (lower = less within-batch spread; not "better"):
- Feature consistency `C_feat(b)` = median over the included KPI + F features of `1.4826·MAD_b(f) / s_f`.
- Embedding consistency `C_emb(b)` = mean pairwise Euclidean distance between the batch's L2-normalised BSE image vectors.
- Jackknife SE (leave one image of the batch out): `SE = sqrt((n−1)/n · Σ(θ_i − θ̄)²)`. Ranks are separable between two adjacent batches if their intervals `θ ± 1.96·SE` do not overlap.

**Unit tests** (required): planted shift detected; no shift not detected; distance matrix symmetric with zero diagonal; duplicate image IDs rejected; a covariate-driven shift vanishes after residualisation.

## 3. B5 validation gates (per feature; G2 and G4 per Batch_k-vs-Batch_3 pair)

Handover rules, verbatim: "G1 image-level test; G2 not acquisition-confounded, or the contrast survives covariate residualisation with the same sign and p < 0.05; G3 ±10 % threshold sensitivity < 0.5 × Batch_3 MAD; G4 conclusion unchanged when Batch_3 leave-one-out outliers are removed (computed per table, never hard-coded); G5 the feature maps to a failure mode that is observable in 2D BSE. Keep rule = bootstrap rank stability ≥ 0.7 and passes G2, G3 and G4."

Operational definitions:
- **G1**: the image-level permutation test of `z_f(Batch_k, Batch_3)` has BH-adjusted p < 0.05.
- **G2**: passes if the pair has no acquisition drift (definition above); otherwise passes only if the residualised `z_f` has the same sign as the raw `z_f` and residualised permutation p < 0.05 (unadjusted, as the handover states).
- **G3**: `sens_f` = median over the 31 images of `max(|f(0.9) − f(1.0)|, |f(1.1) − f(1.0)|)` from the threshold-scaled re-segmentation; passes if `sens_f < 0.5 · s_f` (`s_f` as above, i.e. 1.4826 × Batch_3 MAD).
- **G4**: for the feature's table, a Batch_3 image i is a leave-one-out outlier if `|f_i − median(B3∖i)| / (1.4826·MAD(B3∖i)) > 3.5`. Remove those images (computed per feature from the table, never a hard-coded list), recompute `s_f`, `z_f` and its permutation p; passes if the sign of `z_f` and the significance call (unadjusted p < 0.05) are both unchanged. No outliers → pass.
- **G5**: the feature's mapped consultant failure mode(s) in `configs/stats_v1.yaml` (`g5`) are observable as 2D BSE structure. All mapped modes are structural (FM03, FM07, FM08, FM10, FM11, FM13, FM14, FM21). G5 fails for the `c1_flake_*` columns if the percolation rule fires.
- **Rank stability**: 1000 bootstrap replicates resampling images with replacement within each batch; stability = share of replicates in which the ordering of the three batch medians equals the observed ordering. (Chance level for a random ordering of 3 batches is 1/6.)
- **Status per feature**: **keep** = rank stability ≥ 0.7 and G2, G3, G4 pass for at least one Batch_k-vs-Batch_3 pair. **drop** = G5 fails or `sens_f ≥ 1.0 · s_f` (the threshold perturbation moves the feature as much as the reference spread). **investigate** = everything else. G1 is reported for every feature but is not part of the keep rule (handover).
- **Embedding line (BSE)**: passes if energy distance and MMD² both have BH p < 0.05 (G1), the residualised versions keep p < 0.05 when there is acquisition drift (G2), and the call is unchanged after removing Batch_3 leave-one-out outlier images, where an image is an outlier if its mean distance to the other 16 Batch_3 images has a robust z > 3.5 against the other 16 (G4). G3 and rank stability do not apply (no threshold, not a scalar).

## 4. B7 verdict rules (one JSON per batch, schema `schema/verdict.schema.json`)

- A **line** = one feature (or the BSE embedding) whose Batch_k-vs-Batch_3 statistic is "outside" (> band99) and has BH p < 0.05.
- **outside_bounds**: at least two lines from different families (`phase_fraction`, `silicon_particle`, `void_morphology`, `graphite_morphology`, `embedding`), each from a feature with status keep (embedding: passes its gates), and no acquisition drift for that pair.
- **within_bounds**: no feature (any status) and no BSE embedding statistic is beyond band95 with BH p < 0.05, and no acquisition drift.
- **investigate**: everything else. Signals from features that failed any gate can only give investigate. Acquisition drift alone gives investigate routed to the microscopy team.
- **Batch_3 (reference)**: each Batch_3 image is scored against the other 16 (robust z as in G4). Batch_3 is never outside_bounds; it is investigate if any Batch_3 image is a leave-one-out outlier on features from ≥ 2 families, otherwise within_bounds.
- Routing: outside_bounds or material investigate → `materials_expert_review`; acquisition-only investigate → `microscopy_team`; within_bounds → `none`. No supplier is blamed by code.
- Every verdict carries the rule text verbatim in `verdict.rule`, a reason sentence naming the drivers, evidence paths (file + selector) to the B4 rows, `pipeline.exploratory = true`, `pipeline.frozen = false`, and the phase-identity and px caveats. `accepted` / `rejected` are never written by code; they are human ledger entries only.

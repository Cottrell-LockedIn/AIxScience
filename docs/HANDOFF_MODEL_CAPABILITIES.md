# Handoff: v1 model capabilities (for agents writing the wrapper PRD)

Audience: AI agents and engineers who will write a product requirements document (PRD) for a wrapper around the
frozen v1 model. Primary end users of the wrapper are materials scientists who know FIB-SEM. This file states what
the model *is and does today*; Section 9 holds non-binding recommendations only. The PRD owners decide the product.

`phase_identity: stated by Polaron, not image-verified` (class 2 bright = silicon, class 1 mid = graphite,
class 0 dark = void/pore; Si vs SiOx indistinguishable in BSE; binder and conductive additive lumped into class 0/1).

## 1. Status and where it lives

| Item | Value |
|---|---|
| Model version | `v1-frozen` (git tag, commit `afdbfc9`), repo `Cottrell-LockedIn/AIxScience` |
| Code on GitHub | Tag and branch `devin/1791080364-phase-c` pushed; Phase B/C PRs (#10, #11) not yet merged to `main` |
| Official held-out run | Done once, 3 images, output `results/v1/heldout.json` (committed with this doc). Not re-runnable. |
| Later runs | Only as `exploratory` (separate output folder, labelled exploratory in every file) |
| Fitted model | No pickle. Each run refits from committed training inputs and checks against `results/v1/final_model.csv` (refuses if different; last diff 1e-16) |
| Pretrained weights | DINOv2 ViT-S/14, pinned hub commit + SHA-256, downloaded at run time. Licence: `docs/LICENSES_DINOV2.md` |

## 2. What the model does (one sentence)

For each FIB-SEM image it **always bets on one of the three known batches** (Batch_1, Batch_2, Batch_3), gives
probabilities and a confidence tier, names the 3 inputs that drove the bet, and separately flags whether the image
looks outside the Batch_3 (supplier baseline) distribution and whether its imaging conditions are unusual.

It is a closed-set classifier: an image from a new, unknown batch is still assigned to one of the three; the
out-of-baseline flag is the only signal that it may not belong to any of them. Unit of analysis is the whole image;
tiles are internal and never independent samples.

## 3. Inputs (the only accepted input)

- **TIFF files only** (`.tif` / `.tiff`), one file per detector channel per image. Nothing else is accepted, so
  that results stay valid for the frozen model. No user-tunable parameters (Section 6).
- Naming: `<id>_<CHANNEL>.tif` or `img_<id>_<CHANNEL>.tif`; `CHANNEL` in `BSE`, `Inlens`, `ETD`, `SE`.
  Unparseable names are skipped with a warning; duplicates keep the first file and warn.
- `BSE` is **required** (segmentation, measurements and embeddings all use BSE). `Inlens` is optional (without it one
  charging covariate is omitted). `ETD`/`SE` optional (a caveat is added if both are absent).
- Expected acquisition (what the training set looked like): uint8 (RGB with identical channels is fine), about
  7000 px wide, 1700-2300 px tall, nominal 25 nm/px (unconfirmed by Polaron), same instrument family as the training
  set. Images outside this still get a bet; the acquisition and out-of-baseline flags will show it.
- Every input file's SHA-256 is recorded in the output.

## 4. Processing pipeline (frozen)

1. Read BSE, crop 8 px border, tile 1024 px with 512 px stride (full tiles only).
2. Per tile: median filter (5 px), 3-class multi-Otsu threshold, remove/fill objects < 20 px.
   Labels: 0 dark (void), 1 mid (graphite), 2 bright (silicon). Tiles are stitched into one per-image mask.
3. 11 image-level measurements F01-F11 from that mask (Section 5.3).
4. 8 acquisition covariates (noise, sharpness, curtaining, horizontal stripes, edge charging BSE/Inlens, image
   height, pixel size if tag true).
5. DINOv2 ViT-S/14 embedding (384-d, mean-pooled patches) of each BSE tile, averaged per image. Computed on Modal
   (L4 GPU), about 18 s wall for 3 images, about USD 0.0014.
6. Classifier: StandardScaler(F01-F11) + PCA(29) of the embedding, both fitted on the 31 training images;
   LogisticRegression(L2, C=1.0, class_weight=balanced, multinomial, seed 0).
7. Rule-based tier, drivers, out-of-baseline check, acquisition check, routing and caveats (Section 5).

End-to-end wall time on the dev VM: about 3 min 20 s for 3 images (mostly local segmentation/features).

The per-image segmentation mask (step 2) is the "here is what was measured" image. Saving it and rendering it as an
overlay is being implemented in parallel to this handoff; the PRD can assume a 0/1/2 label image per input image,
same size as the cropped BSE image.

## 5. Outputs (per image, JSON; schema in `schema/verdict.schema.json`)

Every numeric field carries a `justification` block: `rule` (text), `numbers`, `evidence` (file + selector).
Example: `results/v1/heldout.json`.

### 5.1 Batch bet (`verdict.closed_set`)
- `predicted_batch` (always one of the three), `probabilities` for all three, `confidence` (= top probability),
  `runner_up`, `margin`.
- `tier`: `high` if p_max >= 0.75 and model permutation p < 0.05; `medium` if 0.5 <= p_max < 0.75; `low` if
  p_max < 0.5 or the image is `outside_bounds` (out-of-baseline caps the tier at low).
- `loio_reliability`: how often bets on the same predicted batch (and same tier) were right in validation,
  excluding this image, e.g. "Batch_1 bets right 2/6".

### 5.2 Drivers (`evidence.drivers`, top 3)
- contribution = coefficient[predicted batch] x model input (standardised F value or embedding PC score); top 3
  by signed contribution.
- Each driver: `name` (F-feature column or `embedding PC k`), raw `value`, `model_input`, `coefficient`,
  `effect_size` (the contribution), `direction` (higher/lower), `tag` (material-derived with its Phase B status, or
  embedding with the acquisition caveat).

### 5.3 Measurements (`inputs.<id>`, all 11 always reported, lengths in px)

| ID | Measurement | Phase B status | Independent label check |
|---|---|---|---|
| F01 | void area fraction | drop (threshold-sensitive) | agrees in Batch_3, partial in Batch_1 |
| F02 | silicon area fraction | drop | not checkable |
| F03 | silicon particle eq. diameter, median | drop | not checkable |
| F04 | silicon particle eq. diameter, p90 | drop | not checkable |
| F05 | silicon particle count density /Mpx | drop | not checkable |
| F06 | silicon Clark-Evans ratio (<1 clustered) | drop | not checkable |
| F07 | silicon particle solidity | drop | not checkable |
| F08 | void local thickness, median | investigate | agrees (Batch_1, Batch_3) |
| F09 | void chord anisotropy (h/v) | investigate | agrees |
| F10 | void patchiness (IQR over 512 px windows) | investigate | agrees in Batch_3, partial in Batch_1 |
| F11 | silicon perimeter fraction touching void | investigate | not checkable |

"drop" = value moves more than Batch_3's own spread when segmentation thresholds move +/-10 %. The independent
check ran the same code on AI-drafted masks from a separate labelling run (not expert ground truth); "not checkable"
means those masks outlined different objects (whole particles, ~110 px) than our bright specks (~8 px).

### 5.4 Out-of-baseline check (`verdict.label`, `verdict.open_set`)
- Energy distance E1 of the image's BSE embedding to the Batch_3 training images, against the 95 %/99 % band of
  Batch_3 images vs each other: `within_bounds` / `investigate` / `outside_bounds`.
- Also: distance to each batch, nearest batch, `matches_known_batch`, rank p (minimum about 1/18; band built from
  16-17 values, so "99 %" is approximate). Never replaces the batch bet.

### 5.5 Acquisition check (`acquisition`)
- Each of the 8 covariates with value, training 5th-95th percentile, and a flag if outside;
  `acquisition_drift_suspected` if any flag. Pixel size reported as unconfirmed.

### 5.6 Decision support
- `uncertainty`: sampling (n = 31, accuracy CI), segmentation (Phase B status), decision margin.
- `routing.stakeholder`: `materials_expert_review` (outside baseline), `microscopy_team` (acquisition flags only),
  or `none`; with reason. `next_action`: one plain sentence.
- `caveats`: phase identity provenance, px units, embedding/acquisition confound, "variations not better/worse".
- `verdict.reason`: one technical paragraph summarising all of the above.

### 5.7 Run-level
- `run`: git SHA and tag, config hash, timestamp, file hashes, embedding backend, Modal time and cost, frozen /
  exploratory flags, refit check, warnings. `summary_table`: one row per image (bet, confidence, tier, OOD, drivers).

## 6. Fixed behaviour a wrapper must respect

- No user parameters. `configs/v1.yaml` and `configs/features_v1.yaml` define the model; changing any value
  (tiling, denoising, min object size, thresholds, tiers) invalidates results and would be a new model version
  re-validated on the 31 training images.
- CLI: `python -m qc heldout --exploratory --input-dir <folder>` for any new run (output auto-named under
  `results/v1/exploratory/`). The official mode and `--dryrun` are locked and not for wrapper use.
- An exploratory run needs the official `results/v1/heldout.json` present (it is, in this commit).
- If Modal is unavailable, exploratory runs fall back to local CPU embedding (official run was Modal-only).

## 7. How well it performs (leave-one-image-out, 31 images: Batch_1 7, Batch_2 7, Batch_3 17)

- Accuracy 18/31 (Wilson 95 % CI 0.41-0.74). Always guessing Batch_3 = 17/31. Permutation p = 0.035.
- Confusion (rows true, cols predicted B1/B2/B3): B1 2/4/1, B2 4/2/1, B3 0/3/14.
- Bets right: Batch_3 14/16, Batch_2 2/9, Batch_1 2/6. By tier: high 14/18, medium 1/5, low 3/8;
  high-tier Batch_1/2 bets 1/4.
- Practical reading: "Batch_3 vs not Batch_3" is fairly reliable (26/31); Batch_1 vs Batch_2 is near chance.

## 8. Limitations to surface in the product

- 73 of 93 top-driver slots in validation were embedding PCs (not physical). In Phase B the embedding batch signal
  vanished after regressing out acquisition covariates, so it may reflect imaging rather than material.
- 31 training images only; new instruments or settings are outside what it has seen.
- Silicon features F02-F07, F11 are not independently validated; 7 of 11 features are threshold-sensitive.
- No chemistry claims; lengths in px (pixel size unconfirmed).
- Image-level only. There is no built-in rule that combines several images into one accept/reject call for a lot.
- Official held-out result has no score until true labels are provided; scoring it afterwards is exploratory.

## 9. Recommendations for the wrapper PRD (non-binding)

Based on comparable products: Polaron platform (segmentation, cross-condition change analysis, traceable outputs
with stated uncertainty), Thermo Fisher Avizo Trueput for battery QC (image -> analyse -> validate, one-click
reports with "one clear answer and all the data to support it", reproducible across operators), MIPAR (locked
shareable recipes, batch processor and folder watch, review before measuring, colour-coded measurement maps, CSV/PDF
reports), ZEISS arivis Pro and Comet Dragonfly (no-code pipelines, per-phase overlays, mask and measurement export).

Suggested for materials scientists:
1. TIFF upload with pre-run validation (channels present, naming, bit depth, size vs training range).
2. Batch queue for many images; optional folder watch.
3. Mask overlay viewer: BSE with toggleable void/graphite/silicon layers and opacity.
4. Result card per image: bet, three probabilities, tier, and the validation hit rate for that kind of bet.
5. Drivers in plain words, with physical drivers distinguished from embedding drivers.
6. All 11 measurements plotted against the Batch_1/2/3 training ranges, with Phase B status and validation badge.
7. Acquisition flags shown before material conclusions.
8. Plain-English summary generated by fixed templates from the JSON (deterministic, no free text generation).
9. Export: PDF report, CSV of measurements, masks, and the raw JSON with full audit trail (hashes, version).
10. Model version shown as a locked recipe; no parameter controls.
11. Expert comment/override stored separately from the model's answer.

## 10. Source files

- Code: `src/qc/heldout.py` (pipeline and output), `src/qc/classify.py` (model, tiers, drivers),
  `src/qc/features.py` (F01-F11), `src/qc/segment.py` (masks), `src/qc/embed.py` (DINOv2).
- Config: `configs/v1.yaml`, `configs/features_v1.yaml`. Schema: `schema/verdict.schema.json`.
- Validation: `results/v1/loio_summary.json`, `results/v1/loio_predictions.csv`, `results/v1/loio_images/`.
- Decisions and review: `docs/Log/2026-10-04_phase_c.md`, `docs/Log/2026-10-04_phase_c_review.md`,
  `docs/PHASE_B.md`, `results/stats/feature_status.csv`.
- Official held-out output: `results/v1/heldout.json`.

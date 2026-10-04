# Software features recommendation (wrapper on the v1 model)

Status: recommendation for the PRD authors, non-binding. The model team does not decide the wrapper PRD.
Companion documents: `docs/HANDOFF_MODEL_CAPABILITIES.md` (what v1 outputs today) and
`docs/PRD_MODEL_IMPROVEMENTS.md` (proposed v1.1 and v1.2 outputs, referenced below as M1-M5).

phase_identity: stated by Polaron, not image-verified (void / graphite / silicon). Lengths in pixels until the
pixel size is confirmed.

Primary user: a materials scientist who knows the material and the microscope but not the model.

## 0. APPROVED FOR NOW: what the wrapper can build immediately (read this first)

Decided by the owner on 2026-10-04. Model-side work is limited to two output-only items (masks + overlays, and
embedding-PC tags; see `docs/PRD_MODEL_IMPROVEMENTS.md` section 0). The wrapper team can build the following
without waiting for anything:

| Wrapper feature | Data source available today | Notes |
|---|---|---|
| W1-W4 upload, locked recipe, results list, result card | `results/v1/heldout.json` schema (see `docs/HANDOFF_MODEL_CAPABILITIES.md`) | run new images with `python -m qc heldout --exploratory` |
| W17 model accuracy panel | `results/v1/loio_summary.json` keys: `loio_accuracy_str` (18/31), `wilson95`, `chance_majority`, `permutation_p`, `confusion_matrix`, `per_batch_recall`, `precision_by_pred_batch`, `accuracy_by_tier`, `precision_by_pred_batch_tier` | add the held-out line: 2/3 correct, 5/6 under the confidence scoring (exploratory, n = 3); caveat "leave-one-out on the 31 training images, not an unseen-lot score; Batch_1 vs Batch_2 at chance" |
| W12a low-confidence guideline card | per-image fields in `heldout.json`: tier and tier reason, runner-up and margin, out-of-baseline label, acquisition flags, LOIO track record for this bet/tier (all under `verdict`, `acquisition`, `uncertainty`; exact paths in the handoff) | card texts are the six rows of the table in PRD section M5a; render verbatim with the fields filled; never name a batch the model did not name; a materials scientist should check wording before release |
| W10, W11, W13, W15 | `heldout.json` | as specified below |

Arriving from the model side within the approved 1 h 30 (branch `devin/<ts>-v1.1-masks-pcprofiles`):
- W5 mask overlay viewer: `images[i].evidence` entry `kind: segmentation_mask` with `mask_path`, `overlay_path`,
  `mask_offset_px: [8, 8]`, `class_values`, `overlay_downscale: 4`. The mask is 8 px inset from the TIFF on each
  side; align accordingly. Show the legend and the "one fixed segmentation, not ground truth" note from the entry.
- W18 embedding driver profile (lite): `results/v1/pc_tags.json` keyed by PC; show `sentence` next to every
  driver named `embedding PC k`, plus the fixed caveat "descriptive correlation over 31 training images; not
  separable from imaging conditions (Phase B)". If `review_status` is `unreviewed`, show that word.

Not arriving today (do not design around them yet): W6 crack-like locator, W7 per-feature layers, W8 F09 chords,
W9 aspect-ratio panel, W12b rule-based second opinion, tile galleries and heat maps in W18, W16 lot-level rule.

---

## 1. Context: what the model provides, by version

| Capability | v1 (frozen, today) | v1.1 (output-only, proposed) | v1.2 (decision support, proposed) |
|---|---|---|---|
| Batch bet, 3 probabilities, confidence tier, LOIO track record | yes | same bytes | same bytes |
| Top-3 drivers (measurement or embedding PC), with rule and numbers | yes | same | same |
| All 11 measurements F01-F11 with Phase B status and independent-check status | yes | same | same |
| Out-of-baseline flag (within / investigate / outside Batch_3 band) | yes | same | same |
| Acquisition flags (noise, sharpness, curtaining, stripes, charging, size) | yes | same | same |
| Routing (materials expert / microscopy team / none) and next action | yes | same | same |
| Audit trail (hashes, git tag, config hash, weights checksum) | yes | + mask hashes | same |
| Segmentation mask and colour overlay per image | computed, not saved | saved (M1) | same |
| Per-feature "where to look" layers (pixels, outlines, top regions) for F01-F11; crack-like void list | no | yes (M2) | same |
| Model card: LOIO accuracy, confusion matrix, per-tier and per-batch track record, held-out score when available | in repo files only | in every run output (M8) | same |
| Embedding PC profiles: correlates, exemplar tiles, plain-language tag (patch heat maps deferred) | no | yes (M9a/b/d) | same |
| F09 evidence: horizontal/vertical chords, direction map | no | yes (M3) | same |
| Aspect-ratio panel, labelled "not used by the model" | no | yes (M4) | same |
| Guideline card for low confidence, filled from existing fields | fields exist; card text proposed | yes (M5a) | same |
| Second opinion from pre-registered expert rules on the low tier | no | no | yes (M5b) |

Performance context the UI must keep showing (LOIO, 31 images): 18/31 correct; Batch_3 bets right 14/16;
Batch_1 or Batch_2 bets right 4/15; high tier right 14/18, low 4/13 (two tiers since v1.1; the former medium band was 1/5). v1.1 does not change these. v1.2
adds a separately scored track record for the rules.

## 2. Features

Each feature lists: what the user does, what the model provides (and from which version), what the UI must say.

### W1. Upload and validation
- User drops TIFF files for one or more images. Accepted: `.tif`/`.tiff` only, named `<id>_BSE`, optional
  `<id>_Inlens`, `<id>_ETD`, `<id>_SE`; BSE required. Anything else is rejected before any run.
- Provides (v1): the run reads the folder and runs `qc heldout --exploratory`.
- UI says: which channels were found, that Inlens is missing (one acquisition check skipped) or ETD/SE is
  missing (caveat added), and that results on previously scored images are exploratory.

### W2. Run and locked recipe
- User presses run; no parameters.
- Provides (v1): git tag, config hash, DINOv2 weights checksum, Modal runtime and cost.
- UI says: "Model v1 (tag v1-frozen, afdbfc9). Settings are locked; changing them would invalidate results."

### W3. Results list
- One row per image: bet, three probabilities, tier, out-of-baseline flag, acquisition flag, routing.
- Provides (v1): `summary_table`.
- UI says: tier before probability (a 0.98 probability can be `low` because of the out-of-baseline cap).

### W4. Per-image result card
- Bet, tier and tier reason, LOIO track record for this kind of bet, top-3 drivers each tagged "measurement" or
  "image feature (embedding)".
- Provides (v1): `verdict`, `evidence.drivers`.
- UI says, next to embedding drivers: "learned image feature; may reflect imaging conditions, not only material".
  Next to Batch_1/Batch_2 bets: "in testing, bets on this batch were right 2/6 (Batch_1) or 2/9 (Batch_2);
  Batch_1 and Batch_2 are often confused".

### W5. Mask overlay viewer ("here is what was measured")
- Raw BSE and overlay side by side or toggled; void / graphite / silicon layers on and off; opacity; zoom and pan;
  pixel-aligned (mask offset 8 px from the TIFF edge).
- Provides (v1.1 M1): `mask.png`, `overlay.png`, hashes.
- UI says: one fixed segmentation, not ground truth; 7 of 11 measurements shift under a +-10 % threshold change.

### W6. Crack-like region locator
- A list of elongated void regions (aspect >= 5); clicking one zooms the viewer to its bounding box and draws its
  outline; export as CSV with pixel coordinates.
- Provides (v1.1 M2): `objects.csv` rows with bbox, centroid, area, aspect, orientation.
- UI says: "2-D section: a plate seen edge-on looks like a rod"; shows the curtaining and horizontal-stripe
  covariates beside the list because vertical streaks can be FIB artefacts; objects shorter than ~100 px are marked
  "shape unreliable".

### W7. Feature-selected "where to look" view
- User clicks any measurement F01-F11 (or a driver in the result card); the viewer draws exactly what it used and
  lists the top 10 regions that moved it most; clicking a region zooms to its bounding box with its outline.
  Examples: F08 colours void pixels by pore thickness and lists the largest pores; F10 shows the 512 px window
  heat map and lists the most extreme windows; F04 outlines the largest 10 % of silicon particles; F06 draws
  centroids with nearest-neighbour links. Same interaction for F09 (W8) and the crack-like list (W6).
- Provides (v1.1 M2, M3): raster and vector evidence layers plus `where_to_look.csv` per image.
- UI says: silicon objects are bright specks (~8 px median), different from whole particles a labeller would
  outline; embedding drivers have no mask layer and link to the PC profile (W18) instead.

### W8. F09 direction evidence
- Horizontal and vertical void chords drawn in two colours over the void regions at the current zoom; two-bar
  rose plot of mean chord length; 512 px window heat map of the h/v ratio.
- Provides (v1.1 M3): chord files, direction map, means and counts.
- UI says: F09 = mean horizontal / mean vertical; training medians 1.157 / 1.143 / 1.164 for Batch_1 / 2 / 3, no
  batch difference; independently confirmed against the labeller's masks in Batch_1 and Batch_3.

### W9. Aspect-ratio panel (reference only)
- Share of void area in crack-like regions, void aspect median and p90, orientation histogram, number of objects
  measured and skipped as too small; graphite shown as "percolating network, no particle shape"; silicon shown as
  "not measurable at this magnification".
- Provides (v1.1 M4): `descriptive.elongation` plus Phase B training ranges.
- UI says, prominently: "Shown for reference; not used in the batch prediction." Values are compared with the
  Batch_1/2/3 training ranges, not tested.

### W10. Measurements vs training ranges
- All 11 measurements on a strip chart against the Batch_1/2/3 5-95 % training ranges; Phase B status
  (keep / investigate / drop) and independent-check status (F01, F08, F09, F10 checked; silicon features not).
- Provides (v1): `inputs`, Phase B tables in `results/stats`.

### W11. Imaging-quality panel, shown before material conclusions
- Each acquisition covariate against its training range, with out-of-range flags and the drift flag.
- Provides (v1): `acquisition`.
- UI says: if drift is suspected, "check acquisition settings before interpreting the bet".

### W12. Low-confidence guidance
- W12a Guideline card (v1 fields; text from M5a): on low tier, a short card chosen by situation
  (outside baseline, no batch favoured, medium evidence, imaging drift) and filled with the bet, runner-up,
  track record and flags, ending with what to do next (check imaging, image more sections, compare measurements
  with the Batch_1/2 ranges). Guidance only; it never names a batch the model did not name.
- W12b Second-opinion panel (v1.2 only, M5b): suggested alternative batch (or "none" / "reimage"), which rules
  fired, their evidence, and the rule track record from LOIO. Hidden until the rules pass independent review.
- UI says: "Guidance / expert rule, not model output. The model's bet above is unchanged."

### W13. Plain-English summary
- Fixed sentence templates filled from the JSON (no free-text generation), covering bet, tier, why, drivers,
  baseline flag, imaging flags, next action, caveats.
- Provides (v1): all fields exist today; v1.1/v1.2 add sentences for masks, locations and second opinion.

### W14. Expert notes and override
- Free-text note and an optional "expert batch call" per image, stored separately from the model output with
  author and time; never overwrites the model's bet.
- Provides: none needed; wrapper-side storage.

### W15. Report export
- PDF/HTML per run and per image, CSV of measurements and objects, JSON as produced, overlay and mask PNGs; every
  page carries the model version, config hash, provenance line and the sentence "Batch_1 and Batch_2 are variations
  on the baseline, not better or worse."
- Provides (v1, v1.1): JSON, PNGs, CSVs.

### W16. Batch of images and lot view (gap)
- Run many images and show them together.
- Provides (v1): per-image results only. There is no validated rule for combining images into a lot-level
  accept/reject; the UI should show per-image results and a count by predicted batch, and label any aggregate as
  "not validated".

### W17. Model accuracy panel (model card)
- Always visible from the results list and every report: 18/31 leave-one-image-out accuracy with the 95 %
  interval (0.41-0.74), the 17/31 "always Batch_3" baseline, the confusion matrix, accuracy by tier
  (high 14/18, low 4/13) and by bet (Batch_3 bets 14/16, Batch_1 2/6, Batch_2 2/9), and the held-out
  score: 2/3 correct, 5/6 under the confidence scoring (exploratory, n = 3; the one miss was a low-tier
  Batch_1 bet on a true Batch_2 image).
- Provides (v1 data today in `results/v1/`; v1.1 M8 puts it in every run output as `run.model_card`).
- UI says: "Estimated on the 31 training images, each held out in turn; not an unseen-lot score. Batch_1 vs
  Batch_2 is at chance."

### W18. Embedding driver profile ("what is PC1?")
- Clicking an embedding driver opens its profile: plain-language tag (e.g. "tracks void fraction" or
  "image-texture component, correlated with BSE noise"), its strongest measurement and imaging correlates with
  rho, and a gallery of the highest- and lowest-scoring tiles with their masks. A per-image heat map of where
  the PC score comes from (M9c) is deferred.
- Provides (v1.1 M9): `evidence.pc_profiles`.
- UI says: "Descriptive, not causal. Phase B could not separate the embedding's batch signal from imaging
  conditions." Tags are only shown after independent review.

## 3. Suggested priority

1. W1-W4, W10, W11, W12a, W13, W15, W17 (from repo files): possible on v1 today.
2. W5-W9, W17 in run output, W18: need v1.1 (about 8 h model-side work plus ~1 h review; W5 and W17 first, ~1.5 h).
3. W12b: needs v1.2 (rules authored by the materials scientist, scored by LOIO, reviewed).
4. W14, W16: wrapper-only; W16 aggregation rule is future model-side work.

## 4. Things the software must never do

- Hide or replace the model's bet with a rule, an override or an aggregate.
- Show probabilities without the tier and track record, or a result without the model card (W17).
- Present an embedding PC tag as a physical cause.
- Report lengths in nm or um before the pixel size is confirmed.
- Name phases without the provenance line, or go beyond void / graphite / silicon.
- Let users change model settings; settings are a locked recipe.
- Treat tiles as independent samples in any statistic it computes itself.

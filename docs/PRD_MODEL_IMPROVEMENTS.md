# Model improvement PRD and plan (v1.1 output release, v1.2 decision support)

Status: proposal, non-binding. Nothing here is implemented. `v1-frozen` (afdbfc9) and the official held-out
result (`results/v1/heldout.json`) stay untouched; anything run on the three held-out images from now on is
exploratory.

phase_identity: stated by Polaron, not image-verified (class 0 dark = void/pore, class 1 mid = graphite,
class 2 bright = silicon). Si vs SiOx is indistinguishable in BSE; binder and conductive additive are lumped
into classes 0/1. Lengths are in pixels; the nominal 25 nm/px is unconfirmed.

Companion document: `docs/SOFTWARE_FEATURES_RECOMMENDATION.md` (what the wrapper should do with these outputs).
Baseline capabilities: `docs/HANDOFF_MODEL_CAPABILITIES.md`.

## 1. Why

Three requests from the owner and the materials consultant:

1. Show "what we see": save the segmentation masks the measurements come from and show them in the wrapper.
2. Cover object aspect ratio (elongation) and show *where* elongated or crack-like objects are, and show the
   evidence behind the void-direction measurement F09.
3. When the model is not confident, offer a possible alternative batch from rules a materials scientist has
   approved, separate from the model.

## 2. Goals and non-goals

Goals
- Every number the wrapper shows can be traced to pixels on the image.
- Aspect ratio is exposed as evidence a scientist can judge, without changing the v1 prediction.
- Low-confidence bets come with a second opinion that is labelled, validated and never silently replaces the bet.

Non-goals
- No change to the v1 batch prediction, probabilities, tiers or drivers. Any change to those is a v2 and needs a
  pre-registered leave-one-image-out (LOIO) comparison against 18/31.
- No brittleness, transport or chemistry claims. The model assigns batches; linking shape to performance is the
  scientist's judgement.
- No lot-level accept/reject rule (separate pre-registered work).

## 3. Improvement items

Effort is engineering time to a reviewed result on this codebase; it excludes the independent review required by
`AGENTS.md` (about 1 h per release).

### M1. Save segmentation masks and overlays (v1.1, output-only)

What: `qc heldout` already builds a stitched per-image mask in memory (`heldout._extract_features`,
`features.stitch_mask`). Write it to disk and reference it from the JSON.

Spec
- `results/<run>/masks/<id>_mask.png`: uint8, values 0/1/2, 255 = unanalysed border; same height and width as the
  analysed BSE image (after the 8 px border crop). Pixel (x, y) in the mask is pixel (x+8, y+8) in the TIFF.
- `results/<run>/masks/<id>_overlay.png`: BSE greyscale with the three classes colour-coded, legend, image id,
  model version, provenance line.
- JSON: `evidence.mask_path`, `evidence.overlay_path`, `evidence.mask_sha256`, `evidence.mask_offset_px: [8, 8]`,
  `evidence.pixel_size_nm: null` until confirmed.

Acceptance
- Parity test: `features.extract_features(mask loaded from PNG)` reproduces the F01-F11 in the JSON exactly
  (max abs diff 0) for the 31 training images and the 3 held-out images (held-out: exploratory re-run).
- Verdict fields (`verdict`, `inputs`, `evidence.drivers`) are byte-identical before and after.

Effort: ~1 h. Masks for the 31 training images already exist on disk (`data/masks`, ~62 MB); the held-out images
need an exploratory re-run.

### M2. Object locations: crack-like regions and measured particles (v1.1, output-only)

What: list the objects behind the measurements with pixel coordinates so the wrapper can draw them.

Spec, per image, `results/<run>/objects/<id>_objects.csv` (and GeoJSON-style outlines in a sidecar):
- Crack-like regions: connected components of class 0 (4-connectivity, as in `kpi.kpis`) with
  major/minor axis >= 5.0 (`configs/v1.yaml: kpi_extra.crack_aspect_min`) and area >= `min_object_px` (20).
  Columns: `object_id, class, area_px, bbox_x0, bbox_y0, bbox_x1, bbox_y1, centroid_x, centroid_y,
  major_px, minor_px, aspect, orientation_deg, touches_border, outline_path`.
- Silicon particles used by F03/F04/F05/F06/F07: all class-2 components with the same columns, plus
  `eq_diam_px, solidity, nn_distance_px`. The wrapper highlights the 10 % largest for F04 and the centroids for F06.
- Graphite: *no per-object rows*. Class 1 percolates in 31/31 training images (Phase B gate G5), so components are
  fragments, not particles. Report only the percolating-component area fraction.

Caveats carried in the file header: 2-D section of 3-D objects (a plate cut edge-on looks like a rod); objects
under ~100 px long have unreliable shape descriptors (Takashimizu & Iiyoshi 2016; Sun et al. 2019); elongated
vertical voids coincide with FIB curtaining, so the wrapper must show the curtaining covariate next to them.

Acceptance: sum of crack-like `area_px` / total class-0 area equals `c0_cracklike_frac` from `kpi.kpis` on the
same mask (max abs diff 1e-9). Row count of class-2 objects equals the F05 numerator.

Effort: ~1.5 h (regionprops already used in `kpi.py`; add bbox/centroid/orientation/outline export).

### M3. F09 evidence: chords and direction map (v1.1, output-only)

What: F09 = mean horizontal void chord / mean vertical void chord (`features.chord_anisotropy`, border-touching
chords excluded). Expose the chords.

Spec
- `results/<run>/f09/<id>_chords_h.npz`, `_chords_v.npz`: for each chord `line_index, start, length`. Sizes are a
  few MB per image; store compressed. The wrapper draws them in two colours at the current zoom.
- `results/<run>/f09/<id>_direction_map.csv`: per 512 px window (same grid as F10) the mean h chord, mean v chord
  and their ratio, so the wrapper can show a heat map and a small rose plot (two bars: horizontal, vertical).
- JSON: `inputs.F09.evidence = {chords_h, chords_v, direction_map, n_chords_h, n_chords_v, mean_h_px, mean_v_px}`.

Acceptance: `mean_h_px / mean_v_px` from the saved chords equals F09 in the JSON exactly.

Effort: ~1 h.

### M4. Aspect-ratio panel (v1.1, output-only, not a model input)

What: report elongation from the same mask, labelled "shown for reference; not used in the batch prediction".

Spec, JSON `descriptive.elongation`:
- `c0_cracklike_frac` (already in `kpi.kpis`): share of void area in regions with aspect >= 5.
- `c0_aspect_median`, `c0_aspect_p90`, `c0_orientation_hist_deg` (12 bins) over class-0 components with
  area >= 20 px and major axis >= 100 px (shape reliability threshold); report `n_objects_measured` and
  `n_objects_too_small`.
- `c1_percolating_frac` only; no graphite aspect ratio (see M2).
- `c2_aspect`: `"not_measurable"` with the reason (median silicon object ~8 px across).
- Training context from Phase B (`results/stats/feature_contrasts.csv`), to be shown as ranges, not as a test:

| Measure | Batch_1 | Batch_2 | Batch_3 | Batch difference |
|---|---|---|---|---|
| `c0_cracklike_frac` (median) | 0.128 | 0.138 | 0.143 | none (perm p 0.68-0.77) |
| `c1_flake_aspect_median` (dropped, percolation) | 2.04 | 1.92 | 1.99 | none (p 0.30-0.41) |
| F09 void chord anisotropy h/v | 1.157 | 1.143 | 1.164 | none (p 0.26-1.0) |

Acceptance: values match `kpi.kpis` on the same mask; Phase B thresholds and the "not used by the model" label are
present in the output.

Effort: ~1 h.

### M5. Expert-rule second opinion for low and medium confidence (v1.2, decision-support release)

What: when the v1 tier is `low` or `medium`, add `second_opinion` next to the verdict. Rules are written by the
materials scientist, pre-registered, then scored once by LOIO on the 31 training images. The v1 bet is never
changed or hidden.

Why rules might help (observed in the frozen LOIO output `results/v1/loio_predictions.csv`; these are post-hoc
observations on training data, not validated rules):
- 13 images were low or medium tier. The v1 bet was right for 4 of them; the runner-up batch was right for 8.
- Of the 15 bets on Batch_1 or Batch_2, 4 were right; the runner-up was right for 9.
- 8 training images fell `outside_bounds` of the Batch_3 band; 7 of the 8 are truly Batch_1 or Batch_2.
- No F01-F11 measurement separates Batch_1 from Batch_2 (best: F06 clustering, p = 0.042 uncorrected, 0.96 after
  correction). Feature-range rules for Batch_1 vs Batch_2 are therefore expected to be weak; the LOIO score will say.

Candidate rules to put in front of the scientist (they choose, add or reject; nothing is adopted here):
- R1 runner-up: "if tier is low or medium and margin < 0.5, present the runner-up as the alternative."
- R2 not-baseline: "if `outside_bounds`, state 'unlikely to be Batch_3' and present the better of Batch_1/Batch_2."
- R3 measurement ranges: "if k or more of the independently checked void measurements (F01, F08, F09, F10) fall
  inside one batch's training 5-95 % range and outside the others', suggest that batch."
- R4 acquisition first: "if acquisition drift is suspected, the second opinion is 'reimage before deciding'."

Spec
- Rules live in `configs/rules_v1_2.yaml` with author, date, rationale and a `pre_registered_sha`.
- Output `second_opinion = {suggested_batch | "none" | "reimage", rules_fired: [...], evidence: {...},
  loio_track_record: {fired_n, correct_n}, label: "expert rule, not model output"}`.
- Scoring: LOIO on the 31 images, reported as (a) how often each rule fires, (b) accuracy when it fires,
  (c) accuracy of "bet, replaced by suggestion when it fires" against 18/31, with Wilson intervals. Reported once.
  The 3 held-out images are exploratory only.
- Fallback: if no rule fires, `second_opinion.suggested_batch = "none"`; the wrapper shows the v1 bet and tier only.

Acceptance: pre-registration committed before scoring; LOIO report committed; independent review PASS or
CONDITIONAL PASS before the field is shown to users; the v1 `verdict` block is byte-identical.

Effort: scientist authoring (external) + ~2 h implementation and LOIO scoring + ~1 h review.

### M6. Deferred: v2 with elongation as a model input

`c0_cracklike_frac` exists for all 31 training images (`results/kpi_per_image.parquet`), so a v2 with it as a 12th
input would take ~1-1.5 h. Not recommended: Phase B shows no batch difference, so with n = 31 the expected gain is
about zero and it costs a model version. Revisit only if the consultant names a specific object class we have not
measured.

### M7. Deferred: data-side fixes that unlock more

- Confirm pixel size with Polaron (`docs/READ/Questions for Polaron.md`) to report lengths in nm/um.
- Higher-magnification BSE of silicon so particle shape becomes measurable (>= 100 px objects).
- One labelling pipeline across batches if annotation-derived measurements are ever to be used (test 2 FAIL).

## 4. Releases and sequence

| Release | Items | What changes | Validation | Time |
|---|---|---|---|---|
| v1.1 | M1, M2, M3, M4 | New output files and JSON fields only | Parity tests in section 3; verdict bytes unchanged on 31 LOIO + 3 held-out (exploratory) | ~4.5 h + review |
| v1.2 | M5 | New `second_opinion` field driven by pre-registered expert rules | One LOIO scoring run; independent review | scientist time + ~3 h |
| v2 | M6 (if ever) | Classifier inputs | Pre-registered LOIO vs 18/31; new unseen images needed for a real held-out test | ~1.5 h |

Order: v1.1 first (unblocks the wrapper's mask viewer and evidence views), M5 rule authoring in parallel with the
scientist, v1.2 after review.

## 5. Risks

- Masks are one fixed segmentation, not ground truth: 7 of 11 measurements move under a +-10 % threshold shift.
  Mitigation: the overlay exists so the scientist can see it; carry the Phase B status next to each measurement.
- Elongated voids may be FIB curtaining. Mitigation: show curtaining and horizontal-stripe covariates with the
  crack list; R4.
- Second-opinion rules may be mistaken for model output. Mitigation: separate field, explicit label, LOIO track
  record shown each time.
- Held-out leakage: the 3 held-out images cannot validate anything further. Mitigation: label every re-run
  exploratory; ask for new unseen images for any v2 claim.

## 6. Decisions needed from the owner and consultant

1. Approve v1.1 scope (M1-M4) as output-only.
2. Who authors the M5 rules, and which of R1-R4 go in the first pre-registration.
3. Whether the aspect-ratio panel should use 5.0 as the crack-like threshold (current Phase B value) or a value
   the consultant prefers; it must be fixed before v1.1 is scored.

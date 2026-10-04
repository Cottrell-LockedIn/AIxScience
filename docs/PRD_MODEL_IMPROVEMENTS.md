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
4. Show the model's accuracy inside the software.
5. Mentor feedback: embedding PC1 is not interpretable; try to link the embedding components to microstructure
   properties.

## 2. Goals and non-goals

Goals
- Model performance must not decrease. Every v1.1 item is output-only (the `verdict` block stays byte-identical);
  the v1.2 second opinion never changes the bet or tier; any v2 must match or beat 18/31 in LOIO and keep the
  tier logic (the out-of-baseline cap earned a point on the held-out set, see M8).
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

### M2. "Where to look": per-feature evidence layers and object locations (v1.1, output-only)

Status: scope approved by the owner (2026-10-04); not yet implemented.

What: for every measurement F01-F11, save the exact pixels or object outlines it used, plus the regions that
moved the number most, so the wrapper can draw them when the user selects that feature (as for F09 in M3).

Spec, per image, under `results/<run>/evidence/<id>/`:
- Raster layers (PNG, same size as the mask, 0/255 or scalar): `F01_void.png`, `F02_silicon.png`,
  `F08_local_thickness.png` (scalar, px), `F10_window_void_fraction.png` (512 px grid, scalar),
  `F11_boundary_adjacent_void.png`.
- Vector layers (GeoJSON-style outlines in mask pixel coordinates, offset 8 px from the TIFF edge):
  `F03_F04_F07_particles.json` (every class-2 component with `eq_diam_px, solidity, bbox, centroid, outline`),
  `F05_counting_frame.json`, `F06_centroids_nn.json` (centroids and nearest-neighbour links),
  `cracklike_regions.json` (see below).
- `where_to_look.csv`: for each feature the top 10 regions ranked by contribution, with `feature, rank, bbox,
  centroid, value, why`:

| Feature | Highlight | Top regions ranked by |
|---|---|---|
| F01 void fraction | all void pixels | 512 px windows with the highest void fraction |
| F02 silicon fraction | all silicon pixels | windows with the highest silicon fraction |
| F03 silicon median size | particles within +-10 % of the median | particles nearest the median |
| F04 silicon p90 size | particles above the 90th percentile | largest particles |
| F05 count density | counting frame + every centroid | windows with most particles |
| F06 clustering (Clark-Evans) | centroids + nearest-neighbour links | shortest nearest-neighbour links |
| F07 solidity | particle outline vs convex hull | lowest-solidity particles |
| F08 pore thickness | local-thickness colouring of void pixels | largest inscribed discs |
| F09 void direction | horizontal and vertical chords (M3) | windows with the most extreme h/v ratio |
| F10 patchiness | window heat map | windows at the 25th and 75th percentiles and beyond |
| F11 silicon-void contact | silicon boundary pixels touching void | particles with the highest contact fraction |

- Crack-like regions (`cracklike_regions.json` + rows in `where_to_look.csv`): connected components of class 0
  (4-connectivity, as in `kpi.kpis`) with major/minor axis >= 5.0 (`configs/v1.yaml: kpi_extra.crack_aspect_min`)
  and area >= `min_object_px` (20); columns `object_id, area_px, bbox, centroid, major_px, minor_px, aspect,
  orientation_deg, touches_border, outline`, ranked by area.
- Graphite: *no per-object rows*. Class 1 percolates in 31/31 training images (Phase B gate G5), so components are
  fragments, not particles. Report only the percolating-component area fraction.
- Embedding PCs have no mask-based layer; their "where to look" comes from M9.

Caveats carried in the file header: 2-D section of 3-D objects (a plate cut edge-on looks like a rod); objects
under ~100 px long have unreliable shape descriptors (Takashimizu & Iiyoshi 2016; Sun et al. 2019); elongated
vertical voids coincide with FIB curtaining, so the wrapper must show the curtaining covariate next to them.

Acceptance
- Each feature recomputed from its own saved layer equals the JSON value (F01, F02, F11 from the raster; F03-F07
  from the particle file; F08 from the thickness raster; F10 from the window raster). Max abs diff 1e-9.
- Sum of crack-like `area_px` / total class-0 area equals `c0_cracklike_frac` from `kpi.kpis` on the same mask.
- Every `where_to_look.csv` bbox lies inside the mask and, for object rows, matches an outline in the vector file.

Effort: ~3 h (regionprops already used in `kpi.py`; local thickness and windows already computed in
`features.py`; new work is export, ranking and the parity tests).

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

#### M5a. Guideline card first (no rules, no scoring; ~30 min of writing, wrapper renders it)

Everything needed is already in the v1 output: tier and tier reason, runner-up and margin, out-of-baseline label,
acquisition flags, and the LOIO track record for this kind of bet and tier. A fixed guideline card is selected
by situation and filled from those fields. It is guidance for the scientist, not a prediction, so it needs no
validation; it must not name a batch the model did not already name.

| Situation (from the output) | Card text (filled from the JSON) |
|---|---|
| low tier, `outside_bounds`, bet Batch_1 or Batch_2 | "Probably not Batch_3 (outside its range). Batch_1 vs Batch_2 is near chance for this model (bets on {bet} right {k}/{n} in testing; misses were usually {runner_up}). Read '{bet}' as 'Batch_1 or Batch_2'. Check imaging flags first ({flags}). To decide: image more sections of this sample, or compare the 11 measurements with the Batch_1 and Batch_2 ranges." |
| low tier, `outside_bounds`, bet Batch_3 | "Unusual image: bet Batch_3 but outside the Batch_3 range. Check imaging flags ({flags}); if they are clear, send to materials review as a possible new variation." |
| low tier, p_max < 0.5 | "No batch is favoured (best {p_max}). Treat as undecided; image more sections. Runner-up {runner_up}." |
| medium tier | "Moderate evidence for {bet} (p {p_max}, margin {margin}); medium-tier bets were right 1/5 in testing. Confirm with a second image before acting." |
| any tier, acquisition drift suspected | prepend: "Imaging differs from the training images ({flags}); re-image or confirm settings before interpreting the bet." |
| high tier, bet Batch_1 or Batch_2 | append: "High tier, but Batch_1/Batch_2 bets at this tier were right 1/4 in testing; treat the batch identity as provisional." |

Template text lives in `configs/guidelines_v1.yaml`; a test renders all six cards from the LOIO output.
Example rendered for held-out `3e122cbj` (true batch Batch_2): first row with bet Batch_1, 2/6, runner-up
Batch_2, flags noise/sharpness/height.

#### M5b. Pre-registered expert rules (later, ~2 h + scientist time)

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
- R5 data-derived distinct traits: for each batch, find the measurements whose training range is most distinct
  from the other two (largest standardised median gap), and suggest the batch whose distinct ranges the image
  falls into. The trait selection must be done inside the LOIO loop (on the 30 training images of each fold), or
  the score is optimistic.

Expectation for R5, from Phase B (`results/stats/feature_contrasts.csv`): no measurement is distinct for any batch
pair after multiple-comparison correction. Largest uncorrected gaps: void region size (`c0_region_eqdiam_median_px`)
Batch_1 vs Batch_3, medians 9.9 vs 10.5 px, p = 0.003 (BH 0.21); silicon clustering F06 Batch_1 vs Batch_2,
medians 0.73 vs 0.68, p = 0.042 (BH 0.96). The traits that do separate batches are the BSE embedding distance
(Batch_1 and Batch_2 vs Batch_3, BH p 0.004 and 0.012) and the derived `outside_bounds` flag, and the model already
uses them. R5 is therefore expected to be weak for Batch_1 vs Batch_2 and partly redundant elsewhere. It costs
~2 h including LOIO scoring, so the honest course is to score it and report what it does.

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

### M8. Model accuracy in the software (v1.1, output-only; data already exists)

What: the wrapper should show how well the model did, with the right caveats. No model work is needed; the
numbers are already in `results/v1/loio_summary.json`, `results/v1/loio_predictions.csv` and
`results/v1/confusion_matrix.csv`.

Spec: copy a fixed `model_card` block into every run output (`run.model_card`) so the wrapper never has to read
repository files:
- `loio_accuracy: 18/31` with Wilson 95 % interval 0.41-0.74; majority-class baseline 17/31; permutation
  p = 0.035 (1000 shuffles, median shuffled accuracy 12/31).
- `balanced_accuracy: 0.465`; recall Batch_1 2/7, Batch_2 2/7, Batch_3 14/17; precision Batch_1 2/6, Batch_2 2/9,
  Batch_3 14/16.
- Confusion matrix (rows true, columns predicted): Batch_1 [2, 4, 1]; Batch_2 [4, 2, 1]; Batch_3 [0, 3, 14].
- Accuracy by tier: high 14/18, medium 1/5, low 3/8; by bet and tier (e.g. `Batch_3|high` 13/14, `Batch_1|high` 0/1).
- `evaluation: leave-one-image-out on the 31 training images`.
- Held-out set (true batches supplied by the owner on 2026-10-04 after the single official run; scoring is
  exploratory, n = 3): `3e122cbj` true Batch_2, predicted Batch_1 (p 0.98) at tier low; `fn0mhxef` true Batch_1,
  predicted Batch_1 at tier high; `xrv9xvzb` true Batch_3, predicted Batch_3 at tier high. Accuracy 2/3. Under
  the competition confidence score (0 = confident wrong, 1 = low-confidence wrong, 2 = confident correct):
  1 + 2 + 2 = 5/6. The miss is the Batch_1/Batch_2 confusion seen in LOIO; the out-of-baseline cap turned a
  would-be 0 (p 0.98 for the wrong batch) into a 1. These three images cannot validate any later model version.
- Phase B status of each measurement and the independent label check (F01, F08, F09, F10 checked in Batch_1 and
  Batch_3; silicon features unchecked).

Caveats the block must carry: LOIO is an estimate on the same 31 images the model was tuned on (choices were
frozen before evaluation, but it is not an unseen-lot score); n = 31 means +-1 image moves accuracy by 3 points;
Batch_1 vs Batch_2 is at chance.

Acceptance: the block is generated from the result files, not typed by hand, and a test compares it with them.
Effort: ~0.5 h.

### M9. Characterise the embedding PCs (mentor feedback; v1.1, output-only)

Mentor: "embedding PC1 isn't really interpretable ... would be cool to try link them to material/microstructure
properties."

How the embeddings arise: each 1024 px BSE tile is resized to 518 px and passed through frozen DINOv2 ViT-S/14
(`embed.embed_batch`); the 37 x 37 patch tokens are mean-pooled to one 384-d vector per tile, tiles are averaged
per image, and PCA (29 components, fitted on the training images) gives the PC scores the classifier uses. So a
PC is a weighted average of texture descriptors over the whole image; it has no built-in meaning.

What we can do without changing the model (profiles are computed on the final-model PCA fitted on all 31 images):
- M9a Correlation profile (~1 h, data exists: `results/emb_per_image.parquet`, `features_per_image.parquet`,
  `kpi_per_image.parquet`, `artefacts_per_image.parquet`). For each PC, Spearman rho with the 11 measurements, the
  KPIs and the 8 acquisition covariates across the 31 images, with permutation p-values and BH correction.
- M9b Tile exemplars (~1 h, data exists: `results/emb_per_tile.npy`, 4329 tiles). For each PC, the 8 tiles with
  the highest and lowest projection, shown as a gallery with their masks, so a scientist can see what "high PC1"
  looks like.
- M9c Patch heat maps (~2 h, needs one exploratory Modal re-embedding that keeps patch tokens; weights unchanged).
  Because the pooled vector is the mean of patch tokens, the PC score decomposes exactly into per-patch
  contributions; render them as a heat map over the image and report the share of high-contribution patches that
  fall on void, graphite and silicon in the mask.
- M9d Naming rule. A PC gets a plain-language tag only if |rho| >= 0.7 (BH p < 0.05) with a measurement or KPI
  *and* |rho| < 0.5 with every acquisition covariate; e.g. "PC3: tracks void fraction (rho 0.78)". Otherwise it is
  tagged "image-texture component" with its strongest correlate, e.g. "PC1: correlated with BSE noise (rho 0.71);
  not separable from imaging conditions". Tags are descriptive, never causal.

Output: `evidence.pc_profiles[k] = {tag, top_correlates: [...], exemplar_tiles: [...], patch_map_path,
phase_share_high_patches: {void, graphite, silicon}, acquisition_correlates: [...]}`, referenced from each
embedding driver in `evidence.drivers`.

Expectation, from Phase B (`docs/PHASE_B.md`): the raw embedding difference between Batch_1/Batch_2 and Batch_3
disappears after residualising on the 8 acquisition covariates (BH p 0.75 and 0.96), and for Batch_1 noise or
sharpness alone removes it. So at least one leading PC is likely to be an imaging component, and the honest
outcome may be "PC1 is mostly noise/sharpness". That is still useful: the wrapper can say so next to the driver.

Acceptance: profiles reproduce from the stored arrays; the naming rule is applied by code, not by hand; a
fresh-context reviewer checks the tags before they are shown to users (`AGENTS.md` independent review).
Effort: ~4 h for M9a-M9d plus review; M9a and M9b alone ~2 h.

## 4. Releases and sequence

| Release | Items | What changes | Validation | Time |
|---|---|---|---|---|
| v1.1 | M1, M2, M3, M4, M5a, M8, M9 | New output files and JSON fields only | Parity tests in section 3; verdict bytes unchanged on 31 LOIO + 3 held-out (exploratory); reviewer checks PC tags | ~10 h + review (M1-M4, M8 ~6 h; M9 ~4 h) |
| v1.2 | M5b | New `second_opinion` field driven by pre-registered expert rules | One LOIO scoring run; independent review | scientist time + ~3 h |
| v2 | M6 (if ever) | Classifier inputs | Pre-registered LOIO vs 18/31; new unseen images needed for a real held-out test | ~1.5 h |

Order: M1, M8 first (unblocks the mask viewer and the accuracy panel, ~1.5 h), then M2-M4 (evidence layers), then
M9 (PC profiles); M5a cards with M8; M5b rule authoring in parallel with the scientist, v1.2 after review.

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
2. Approve the M5a guideline cards (wording to be checked by the materials scientist); decide later who authors
   the M5b rules and which of R1-R5 go in the first pre-registration.
3. Whether the aspect-ratio panel should use 5.0 as the crack-like threshold (current Phase B value) or a value
   the consultant prefers; it must be fixed before v1.1 is scored.
4. Whether M9c (patch heat maps, one exploratory Modal re-embedding) is wanted in v1.1 or deferred; M9a-M9b need no
   new compute.

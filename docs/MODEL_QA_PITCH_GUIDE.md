# Model Q&A guide for the project pitch

Owner of this document: the model lead. Purpose: answer any judge or mentor question about the model with a short
answer first and the evidence second. Every number below is read from committed artefacts on `main`
(`results/v1/loio_summary.json`, `results/v1/accuracy_tab/metrics.json`, `results/v1/heldout.json`,
`results/v1/pc_tags.json`, `results/stats/*.csv`, `docs/PHASE_B.md`, `docs/Log/2026-10-04_phase_c.md`).
Diagram to show: `docs/Log/assets/model_workflow_overview.png` (SVG next to it).

`phase_identity: stated by Polaron, not image-verified` (class 2 bright = silicon, class 1 mid = graphite,
class 0 dark = void/pore). Si vs SiOx is indistinguishable in BSE. Lengths are in pixels (25 nm/px is a TIFF tag,
not microscope metadata). Batch_1 / Batch_2 are "different from the Batch_3 baseline", never better or worse.

---

## 1. The explanation in 20 seconds, and in 2 minutes

**20 seconds.** "Each FIB-SEM image goes through one frozen recipe: we segment the BSE image into void, graphite and
silicon and take 11 physical measurements; in parallel a frozen DINOv2 vision model gives a texture fingerprint;
one logistic regression on the 31 training images turns both into a bet on Batch_1, 2 or 3 with a probability,
a confidence tier and the three inputs that drove the bet. Separately we flag whether the image sits outside the
Batch_3 baseline and whether its imaging conditions look unusual. Everything is traceable: every number in the
output carries the rule that produced it and a path to the evidence."

**2 minutes** (follow the diagram left to right).

1. **Input**: standard microscopy TIFFs, one per detector. BSE is required; nothing is tunable by the user.
   SHA-256 of every file is logged.
2. **Tile**: 1024 px tiles, 512 px stride, 100 % coverage. Tiles are internal; the image is the unit.
3. **Three parallel views of the image**
   - 3a *Segment and measure* (classical, no training): median filter, 3-class multi-Otsu, remove objects < 20 px,
     stitch to one mask, 11 measurements F01-F11 (void fraction, Si particle size/count/clustering/solidity,
     pore thickness, void anisotropy, patchiness, Si-void contact). The mask and an overlay PNG are part of the
     output so a scientist can see what was measured.
   - 3b *Embed*: frozen DINOv2 ViT-S/14 (Apache-2.0), 384-d mean-pooled vector per tile, averaged per image.
     PCA to 29 components fitted on training images only. Runs on a Modal L4 GPU in ~18 s for 3 images.
   - 3c *Acquisition covariates*: 8 imaging descriptors (BSE noise, sharpness, curtaining, horizontal stripes,
     edge charging, height, nm/px tag). Reported and flagged, **not** model inputs.
4. **Classify**: StandardScaler(F01-F11) + PCA(29) of the embedding -> one L2 logistic regression,
   class_weight balanced, fitted on the 31 training images. The only fitted object. No pickle: every run refits and
   checks the coefficients against `final_model.csv` (last diff 1e-16).
5. **Pre-registered rules**: bet = argmax (always a batch, as Polaron asked); tier `high` if p >= 0.75, LOIO
   permutation p < 0.05 and the image is within the Batch_3 band, else `low`; top-3 drivers = coefficient x input;
   out-of-baseline = energy distance of the embedding to the Batch_3 images vs their own 95/99 % band; routing to
   materials expert / microscopy team / none.
6. **Output**: one schema-validated JSON per image with the bet, probabilities, tier, LOIO track record for that
   kind of bet, drivers with tags, 11 measurements vs training ranges, in/out-of-baseline label, acquisition flags,
   mask + overlay, and provenance (git tag, config hash, file hashes, cost).
7. **How we know it works**: leave-one-image-out validation over 31 folds, label-permutation test, a freeze
   (`git tag v1-frozen`) before the held-out images were opened, one official held-out run, and an independent
   fresh-context review (PASS).

---

## 2. Fact sheet (memorise this table)

| Item | Value | Source |
|---|---|---|
| Training data | 31 images (Batch_1 7, Batch_2 7, Batch_3 17), 93 TIFFs (3 detectors each), ~7000 x 1612-2316 px, uint8 | `docs/DATA_AUDIT.md` |
| Unit of analysis | the image; tiles are pseudo-replicates (~40-50 tiles per image) | AGENTS.md rule |
| Reference batch | Batch_3 = supplier-promised baseline (Polaron) | `docs/READ/Polaron Clarification ...md` |
| Model | StandardScaler(F01-F11) + PCA(29) of BSE DINOv2 embedding -> LogisticRegression(L2, C=1, balanced, multinomial, seed 0) | `loio_summary.json:model` |
| Trainable parameters | 3 x (11 + 29 + 1) = 123 logistic-regression weights; no neural network trained | `final_model.csv` |
| Validation | leave-one-image-out, 31 folds; scaler and PCA refit inside every fold | Phase C log |
| 3-way LOIO accuracy | **18/31 = 58 %**, Wilson 95 % CI 41-74 % | `loio_summary.json` |
| Chance references | always-Batch_3 17/31 = 55 %; random 33 %; permutation median 39 % | `metrics.json` |
| Label-permutation test | p = 0.035 (1000 shuffles, seed 0); 95th percentile of null = 17/31 | `loio_summary.json` |
| Balanced accuracy / kappa / MCC | 0.465 / 0.31 / 0.31 | `metrics.json` |
| Macro one-vs-rest AUROC | 0.82 (Batch_1 0.84, Batch_2 0.69, Batch_3 0.94) | `metrics.json` |
| Confusion (rows true B1/B2/B3, cols pred) | B1 [2,4,1]; B2 [4,2,1]; B3 [0,3,14] | `confusion_matrix.csv` |
| Batch_3 vs not-Batch_3 | **26/31 = 84 %**, Wilson 67-93 %, AUROC 0.94, 2 FP / 3 FN | `metrics.json:reference_vs_rest` |
| Precision of bets | Batch_3 bets right **14/16**; Batch_1 2/6; Batch_2 2/9 | `loio_summary.json` |
| Recall per batch | Batch_3 14/17; Batch_1 2/7; Batch_2 2/7 | `loio_summary.json` |
| Tier reliability | high 14/18 = 78 % (mean confidence 0.91); low 4/13 = 31 % (mean confidence 0.64) | `metrics.json:by_tier` |
| High-tier Batch_3 bets | 13/14 right; high-tier Batch_1/2 bets 1/4 | `loio_summary.json` |
| Out-of-baseline flags in training | 23 within_bounds, 8 outside_bounds (B1 5, B2 2, B3 1) | Phase C log |
| Drivers in LOIO | 73 of 93 top-3 slots and 28 of 31 top-1 drivers are embedding PCs | Phase C log |
| Official held-out run | once, 3 images, Modal L4, 18.5 s wall, USD 0.0014, tag `v1-frozen` (afdbfc9), config hash 45629944e398 | `heldout.json:run` |
| Held-out result (truth given afterwards) | **2/3 correct**; judging "confidence score" 5/6 | `metrics.json:heldout` |
| Held-out rows | 3e122cbj: bet Batch_1 p 0.98, tier low, outside_bounds, truth **Batch_2** (miss); fn0mhxef: Batch_1 p 0.86, high, truth Batch_1; xrv9xvzb: Batch_3 p 0.92, high, within_bounds, truth Batch_3 | `heldout.json` |
| Exploratory 6-image test set | 2 x Batch_3 (high, within), 2 x Batch_1 + 2 x Batch_2 (low, outside_bounds); labels not yet supplied | `results/v1_1/heldout_test_summary.csv` |
| Phase B (pre-registered stats, 2000 perms) | raw BSE embedding: B1-B3 energy 0.091 BH p 0.0045, B2-B3 0.040 p 0.012, B1-B2 p 0.37; after residualising on 8 acquisition covariates: p 0.75 / 0.96 | `docs/PHASE_B.md` |
| Measurements status | 0 keep, 4 investigate (F08-F11), 7 drop (threshold-sensitive); none differs between batches after BH (smallest family BH p 0.207) | `results/stats/feature_status.csv` |
| Segmentation sensitivity | +/-10 % threshold shift moves 7/11 measurements by more than Batch_3's own spread | `feature_status.csv` |
| Independent review | Phase B CONDITIONAL PASS; Phase C PASS at fd12b02; 74 tests passed at review | `docs/Log/2026-10-04_phase_c_review.md` |
| End-to-end time | ~3 min 20 s for 3 images on the dev VM (mostly local segmentation); embedding ~18 s on Modal | `docs/HANDOFF_MODEL_CAPABILITIES.md` |
| Licences | DINOv2 code + weights Apache-2.0, pinned hub commit 7764ea0 + SHA-256 of weights | `docs/LICENSES_DINOV2.md` |

Judging-score rule we used for 5/6: 2 = correct at tier high; 1 = correct at low or incorrect at low;
0 = incorrect at high. Our one miss was flagged low (outside the Batch_3 band), so it scored 1, not 0.

---

## 3. What each output field means (one line each, for the demo)

- **predicted_batch / probabilities / confidence**: argmax of the three class probabilities; confidence = top probability.
- **tier** (high/low): a pre-registered rule, not a feeling. high = p >= 0.75 AND model beats chance (perm p < 0.05)
  AND image within the Batch_3 band. The out-of-baseline flag caps the tier at low on purpose.
- **loio_reliability**: how often bets like this one were right in validation, excluding this image
  ("Batch_3 bets right 14/16"). This is the honest confidence, independent of the probability.
- **drivers (top 3)**: coefficient x this image's input. F-features carry their Phase B status (drop/investigate);
  embedding PCs carry a code-generated reading from `pc_tags.json` (PC1 ~ BSE sharpness/noise, near tie with void
  fraction; PC2 ~ horizontal-stripe score, near tie with graphite connectedness; PC3 ~ Si count density but blocked
  by curtaining). No PC earned a pure `material` tag.
- **label** (within_bounds / investigate / outside_bounds): energy distance E1 of the image's embedding to the 17
  Batch_3 images vs the 95 % (0.220) and 99 % (0.245) quantiles of Batch_3 images against each other.
  `matches_known_batch` = E1 <= band99. rank_p minimum is ~1/18 because the null has 17 values.
- **acquisition**: each of 8 covariates vs training 5th-95th percentile; `acquisition_drift_suspected` if any flag.
- **routing**: materials_expert_review (outside baseline) / microscopy_team (acquisition flags only) / none.
- **segmentation_mask + overlay**: the exact array the 11 measurements came from (void blue, silicon orange).
- **run**: git SHA + tag, config hash, file hashes, backend, Modal time and cost, frozen/exploratory flags, refit check.

---

## 4. Design decisions and the one-line defence

| Decision | Why | If challenged |
|---|---|---|
| Image is the unit, not tiles (n = 31, not 4329) | tiles of one field of view share the microscope session; treating them as samples fakes the n | "Tile-level splits would let the model memorise the session; our LOIO puts every tile of an image on the same side." |
| Leave-one-image-out CV | the largest honest training set per fold with 31 images; every image predicted by a model that never saw it | LOGO by acquisition group was done in Phase A (F01-F11 LR: LOIO 0.45 / LOGO 0.32); Phase C fixed one model and reported LOIO + permutation test |
| Logistic regression, not a CNN | 31 images cannot train or fine-tune a network; a linear model gives coefficients we can show as drivers and refit in 20 s | "The only thing we fit is 123 weights; the deep model is frozen and only supplies features." |
| Frozen DINOv2 ViT-S/14 | self-supervised features are the current default for frozen-feature industrial inspection (PatchCore-style); Apache-2.0; smallest variant to limit overfitting | PCA(29) because 30 training images per fold have rank <= 29; PCA fitted inside each fold |
| Classical segmentation (multi-Otsu), no learned segmenter | no ground-truth masks exist; multi-Otsu is the standard first pass for Si/graphite BSE; reproducible; sensitivity reported | "We report that 7/11 measurements move under a +/-10 % threshold shift; that is the honest error bar." |
| 11 pre-registered measurements, consultant-approved, not 84 | 31 images cannot support 84 hypotheses; false batch effects are guaranteed without pre-registration | the 84-dim catalogue exists as candidate pool only |
| Acquisition covariates measured and reported, never used as inputs | Polaron: artefacts may correlate with chemistry; so we flag drift instead of silently removing or exploiting it | Phase B residualisation tells us how much of the embedding signal is acquisition-collinear |
| Always bet on a batch; out-of-baseline is a flag next to the bet | Polaron (Steve Kench): "always assigned to a batch ... can say it's very unconfident but should still take a bet" | the flag is what turns "unknown batch N" into an in/out-of-distribution answer |
| Two-level tier, OOD caps it at low | high-tier Batch_1/2 bets were right only 1/4 in LOIO; non-Batch_3 bets with p >= 0.75 were 1/5 | we refused to lift tiers on the 6-image test set after seeing them: that is test-set tuning |
| Freeze before held-out, run once, exploratory afterwards | the only way the held-out score means anything | CLI refuses to overwrite `heldout.json`, refuses a dirty tree, refits + checks coefficients |
| Verdict vocabulary within/investigate/outside, never good/bad | no good/bad labels exist; Batch_1/2 are "different", not worse | `outside_bounds` here = outside the Batch_3 embedding distribution |
| Robust statistics (median/MAD, permutation, BH) | n = 7/7/17, skewed, outliers (3/17 Batch_3 images are LOO outliers) | Wilson intervals on every k/n |
| Modal for embeddings | L4 GPU ~56 s vs ~658 s CPU for the training set; USD 0.0014 for 3 images; every run logged in `MODAL_RUNS_v1.csv` | CPU fallback exists for exploratory runs (bets/tiers identical, embeddings differ ~1e-5) |

---

## 5. Limitations we state ourselves (say them before the judges do)

1. **n = 31.** The 3-way accuracy CI is 41-74 %; the held-out set is 3 images. We quote intervals, not points.
2. **Batch_1 vs Batch_2 is near chance** (2/7 recall each; they are confused with each other 4 + 4 times).
   Phase B found no Batch_1-Batch_2 difference by any statistic either. The reliable call is Batch_3 vs not-Batch_3.
3. **The embedding signal may be acquisition, not material.** Raw BSE embeddings separate Batch_1/2 from Batch_3
   (BH p 0.0045 / 0.012), but the difference vanishes after regressing out BSE noise sigma or sharpness alone.
   Batch_1/2 have higher BSE noise sigma (medians 46.3 / 44.4 vs 37.7) and higher Laplacian-variance sharpness
   (2349 / 2187 vs 1640; the two covariates have rho 0.99, so both read as noise/texture), though no
   single covariate differs significantly (all BH p >= 0.25). With these data, acquisition and material cannot be
   separated; only Polaron's acquisition log could do it. 73 of 93 top drivers are embedding PCs, so the bets lean
   on this signal. We say so in every JSON.
4. **Segmentation is one fixed threshold recipe, not ground truth.** 7/11 measurements are threshold-sensitive;
   the per-tile multi-Otsu can mis-split particle-free tiles. The overlay exists so a scientist can catch this.
5. **No physical units**: lengths in px; 25 nm/px is a tifffile tag, not microscope metadata.
6. **No chemistry**: silicon/graphite/void are Polaron's stated identities; Si vs SiOx indistinguishable; binder and
   conductive additive are lumped into classes 0/1.
7. **Closed-set classifier**: an image from a genuinely new batch is still assigned to one of three; the
   out-of-baseline flag is the only signal, and its 99 % band rests on 17 values (rank_p >= 1/18).
8. **Image-level only**: no built-in rule aggregates several images into one lot decision (the Phase B 7-vs-10
   split-half band is the ready-made set-level test, not wired in).
9. **Held-out score is exploratory** (n = 3, truth supplied after the run). The 6-image test set has no labels yet.

---

## 6. Hard questions, with answers

### Data and validation

**Q: 58 % accuracy is barely above always guessing Batch_3 (55 %). Why is this useful?**
A: The headline 3-way number hides where the signal is. Batch_3-vs-rest is 26/31 (84 %, AUROC 0.94) and Batch_3 bets
are right 14/16. The miss is Batch_1 vs Batch_2, which no statistic in our pre-registered Phase B could separate
either. The permutation test (p = 0.035, null median 39 %) shows the 3-way result is not chance. For Polaron's
question, "does this image match the supplier baseline, and if not, in what way", the baseline-vs-rest call is
the one that matters.

**Q: How do you know you are not overfitting with 31 images?**
A: Three ways. (1) Leave-one-image-out: every prediction comes from a model that never saw that image, and the
scaler and PCA are refit inside each fold. (2) A label-permutation test over the whole LOIO (1000 shuffles). (3) A
freeze before the held-out images were opened, one run, and an independent reviewer who reproduced the numbers.
We also kept the model tiny: 123 weights, no trained network.

**Q: Why not stratified k-fold or a train/test split?**
A: With 7 / 7 / 17 images, any split leaves 1-2 images of a minority batch in test; LOIO uses the most data per
fold and gives one honest out-of-fold prediction per image. Tiles are never split across sides.

**Q: Did you validate across acquisition sessions (leave-one-group-out)?**
A: In Phase A, yes, for the F01-F11-only model: LOIO 0.45, LOGO 0.32 over 13 (height, resolution-tag) groups;
8 of the 13 groups are single-batch, so LOGO is partly structural. Phase C fixed one model and reported LOIO plus the
permutation test; a LOGO estimate for the frozen model is listed as future work, not done.

**Q: Why is Wilson 41-74 % so wide?**
A: Because n = 31. We report the interval rather than hide it. The same interval logic applies to every k/n in
the output.

### Acquisition vs material

**Q: Is your model just detecting microscope settings?**
A: Possibly in part, and we say so. Phase B showed the raw embedding difference from Batch_3 disappears after
residualising on BSE noise or sharpness alone, and the 8 covariates predict the Batch_1/2 labels with R² 0.67 /
0.71. But a real microstructure difference that also changes noise and sharpness would look identical. We cannot
separate the two with these data, so the output tags every embedding driver with that caveat and flags acquisition
drift separately. The question we would ask Polaron first: did dwell, current or detector gain differ between
batches?

**Q: Then why keep the embedding in the model at all?**
A: Because the judging criterion is correct assignment of held-out images with an explanation, and Polaron said
acquisition-driven differences may contribute "provided the driver is reported as acquisition vs material". The
embedding is the strongest signal we have (F01-F11 alone: LOIO 0.45, below chance). We keep it, label it honestly,
and route flagged images to the microscopy team.

**Q: Why not remove the acquisition effect (residualise) before classifying?**
A: We considered it (listed as future work). Removing noise/sharpness also removes any real material difference
correlated with them, and with 31 images we cannot tell which we removed. Reporting both the raw bet and the
acquisition flags is the more honest design for n = 31.

### Model choice

**Q: Why not fine-tune a CNN / use a bigger foundation model?**
A: 31 images. Fine-tuning would overfit the session, not the material. A frozen self-supervised backbone plus a
linear head is the standard few-shot inspection recipe. ViT-S/14 is the smallest DINOv2 variant; we fit PCA(29)
because that is the maximum rank with 30 training images per fold.

**Q: Why PCA(29) and not fewer components? Isn't that nearly the full rank?**
A: It is the full rank. The owner fixed one model with no sweeps (no model selection = no selection bias). L2
regularisation with class_weight balanced handles the dimensionality; the permutation test confirms the result
is above chance. Fewer components is a legitimate v2 experiment.

**Q: Are the F01-F11 measurements even useful, since none differs between batches?**
A: Individually, after multiplicity correction, none reaches significance (smallest BH p 0.207), and 7/11 are
threshold-sensitive. They are in the model because they are the physically interpretable part of the explanation:
when a bet is driven by F01 void fraction or F06 Clark-Evans clustering, a scientist can check it on the overlay.
They are also what the wrapper shows against the training ranges.

**Q: Why no ensembles, SHAP, calibration, hyper-parameter search?**
A: Time budget and n. One pre-registered model with coefficient x input drivers is fully transparent; SHAP on a
linear model adds nothing. Any search over 31 images would have to be nested inside LOIO to be honest.

### Held-out and test set

**Q: You got 2/3. What went wrong on the third?**
A: 3e122cbj was a Batch_2 image; the model bet Batch_1 with p 0.98. Batch_1 vs Batch_2 is exactly the weak axis.
The system did flag it: energy distance 0.42 vs the Batch_3 99 % band 0.245 -> outside_bounds, acquisition drift
on noise, sharpness and height -> tier low, routed to materials expert. Under the judging "confidence" rule it
scored 1, not 0. That is the design working: wrong bet, correctly low confidence.

**Q: Why did a p = 0.98 prediction get a low tier?**
A: Tier is a pre-registered rule, not the probability. Logistic probabilities on 31 images are overconfident
(tier calibration gap 0.22; low-tier mean confidence 0.64 but 31 % accuracy). The out-of-baseline flag caps the
tier because images outside the Batch_3 band were in the region where the model was wrong most.

**Q: What about the six new images?**
A: Exploratory run only (`results/v1_1/heldout_test_summary.csv`): two bets Batch_3 at p 0.97 / 0.98, high tier,
within bounds; two Batch_1 (p 0.96, 0.80) and two Batch_2 (p 0.96, 0.69), all low tier because outside the
Batch_3 band. No truth labels yet, so no accuracy claim. Modal vs CPU embeddings agree to 1e-5 with identical bets.

**Q: Can I give you a Batch_4 image tomorrow?**
A: Yes. It will still get a bet on 1/2/3 (closed set), plus the out-of-baseline label and acquisition flags. If
a whole batch arrives, the Phase B set-level split-half band is the right in/out-of-distribution test; wiring it
in is the first v2 item.

### Interpretability and trust

**Q: What does "embedding PC 1" mean to a materials scientist?**
A: We profiled every PC against the 11 measurements, 13 KPIs and 8 covariates (Spearman, 2000 permutations, BH).
PC1 correlates most with BSE sharpness (rho -0.63), near tie with void area fraction (rho 0.62), so read it as a
noise/texture component that also carries porosity. PC2 tracks horizontal-stripe score (0.65) and graphite
connectedness (0.61). PC3 tracks silicon count density (0.81) but also curtaining (0.52). The output sentence for
each PC is generated from this table and marked `unreviewed`.

**Q: Can I audit a single number?**
A: Every numeric field carries `justification: {rule, numbers, evidence}` with a file path and selector into the
committed results. The segmentation mask is the exact array the measurements were computed from. The run block
has git tag, config hash and SHA-256 of each input.

**Q: How do you stop someone from changing a threshold to make a result look better?**
A: Configs are hashed into every output row; the official run requires HEAD = `v1-frozen` with a clean tree;
`heldout.json` cannot be overwritten; later runs are stamped exploratory in every file; the refit must match
`final_model.csv` to 1e-9.

### Product and scale

**Q: Cost and time per image?**
A: Embedding on Modal: 18.5 s wall (about 5 s container time) and USD 0.0014 for 3 images; the whole pipeline about
3 min 20 s for 3 images on a dev VM, dominated by local segmentation. No training at inference.

**Q: What would you do with 300 images?**
A: Nested LOGO by session, an acquisition-controlled model to settle the artefact question, a learned segmenter
checked against expert masks, set-level batch decisions, and physical units once Polaron confirms the pixel size.

---

## 7. Do-not-say list

- Do not say "the model detects material differences". Say "the model separates Batch_3 from the others; whether
  that is material or imaging cannot be separated with 31 images".
- Do not say "accuracy 84 %" without "Batch_3 vs rest"; the 3-way number is 58 %.
- Do not say "2 of 3 held-out correct" as validation evidence without "n = 3, exploratory"; the LOIO is the evidence.
- Do not say "we trained a deep learning model". We fit a logistic regression on frozen features.
- Do not say "silicon" without "as stated by Polaron, not image-verified". Never SiOx, SEI, lithium plating.
- Do not say "Batch_1 is worse". Batches are "different from the baseline".
- Do not quote nm or um. Pixels, or "if 25 nm/px holds".
- Do not call tiles samples. 31 images is the n.
- Do not present the 6-image run as accuracy; it has no labels.
- Do not say "99 % band" without noting it rests on 17 null values.

---

## 8. Demo script (2 minutes)

1. Show the workflow diagram: "one frozen recipe, three views of the image, one small classifier, rules, traceable output."
2. Open the held-out result for xrv9xvzb: Batch_3 at p 0.92, tier high, within bounds, Batch_3 bets right 14/16 in
   validation. Point at the overlay: "this is what we measured."
3. Open 3e122cbj: bet Batch_1 at p 0.98 **but** tier low, outside the Batch_3 band (0.42 vs 0.245), acquisition
   drift on noise/sharpness/height, routed to materials expert. "This one was wrong, and the system said do not
   trust it."
4. Show the accuracy tab: 18/31 with CI, 26/31 Batch_3 vs rest, confusion matrix with the B1/B2 confusion.
5. Close with limitations 2 and 3 of Section 5, unprompted.

---

## 9. Six-image exploratory test set (facts only, no labels)

| Image | Bet | P(B1)/P(B2)/P(B3) | Tier | Batch_3 band | Top drivers | Acquisition flags |
|---|---|---|---|---|---|---|
| 0eryguqq | Batch_3 | 0.013 / 0.020 / 0.967 | high | within_bounds | PC2 (+1.14), PC3 (+0.90), PC1 (+0.33) | height |
| fhwrjtet | Batch_3 | 0.004 / 0.012 / 0.984 | high | within_bounds | PC2 (+1.11), PC5 (+0.95), PC3 (+0.58) | height |
| 4hq27w4c | Batch_1 | 0.962 / 0.037 / 0.001 | low | outside_bounds | PC1 (+3.90), F01 void fraction (+0.63), F09 anisotropy (+0.42) | curtaining |
| soo2ax3r | Batch_1 | 0.798 / 0.187 / 0.015 | low | outside_bounds | PC2 (+1.03), PC1 (+1.02), F06 Clark-Evans (+0.35) | none |
| fspqbkxl | Batch_2 | 0.020 / 0.959 / 0.021 | low | outside_bounds | PC12 (+0.83), F06 Clark-Evans (+0.52), PC1 (+0.38) | none |
| y59rxmxl | Batch_2 | 0.311 / 0.686 / 0.004 | low | outside_bounds | PC12 (+0.73), F04 Si p90 diameter (+0.67), PC3 (+0.60) | none |

Pattern consistent with LOIO: the two Batch_3 bets are confident and inside the band; every non-Batch_3 bet is
outside the Batch_3 band and therefore capped at low. Masks/overlays: `results/v1_1/masks/`.

---

## 10. Where to find things

| Need | Path |
|---|---|
| Overview diagram | `docs/Log/assets/model_workflow_overview.{png,svg}` (generator `scripts/model_workflow_overview.py`) |
| Accuracy artefacts (tables, figures, EXPLANATION.md) | `results/v1/accuracy_tab/` |
| LOIO per-image predictions and JSONs | `results/v1/loio_predictions.csv`, `results/v1/loio_images/` |
| Official held-out JSON | `results/v1/heldout.json` |
| Exploratory held-out run with masks | `results/v1_1/heldout_exploratory.json`, `results/v1_1/masks/` |
| 6-image test run | `results/v1_1/heldout_test_{exploratory.json,summary.csv,report.html}` |
| PC readings | `results/v1/pc_tags.json`, `results/v1/pc_profiles.csv` |
| Phase B statistics | `docs/PHASE_B.md`, `results/stats/` |
| Frozen choices and review | `docs/Log/2026-10-04_phase_c.md`, `docs/Log/2026-10-04_phase_c_review.md` |
| Capabilities handoff | `docs/HANDOFF_MODEL_CAPABILITIES.md` |
| Polaron judging criterion | `docs/READ/Polaron Clarification Batch Baseline and Judging.md` |
| Licences | `docs/LICENSES_DINOV2.md` |
| Code | `src/qc/{tiles,segment,features,embed,classify,heldout,pc_profiles}.py` |

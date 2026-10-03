# Feature Details and Suggestions

Status: suggestions for team review, 2026-10-03 (T+1h). Feature names are the team's; nothing renamed. Priority after the Polaron discussion: one or two workflows done well with a wow factor, then completion and robustness.

## Feature 1. Supervised defect detection

What it means with this data: there are no good/bad labels, only batch membership. The supervised signal available is **"which batch does this image/tile come from"**. A classifier that separates batches, plus an explanation of *why*, is exactly Polaron's stated next step.

Details / suggestions:

- Input: per-tile features (KPIs + frozen embeddings). Output: batch probability per tile, aggregated to per-image by majority or mean log-probability.
- Validation must be **leave-one-image-out** (or leave-one-specimen-out). Tiles from one image must never be split across train and test; otherwise the classifier memorises the microscope session and the score is fake.
- Explanation: for a linear or tree model on KPIs, report the top drivers (e.g. "crack fraction and particle equivalent diameter separate batch B from A"). For the embedding model, report which tiles and regions carry the decision (nearest baseline tiles, or occlusion sensitivity).
- Artefact control: train once with artefact covariates included and once with them excluded. If accuracy collapses when excluded, the classifier was reading the ion beam, not the material. Report both numbers; this is a wow moment if done honestly.
- Held-back images: predict batch + confidence + drivers. If confidence is low or the image is outside all batches' bounds, the honest answer is "none of the three / investigate".
- Scope guard: logistic regression, random forest, or a linear head on embeddings. No fine-tuning.

## Feature 2. Unsupervised anomaly detection

What it means with this data: **batch-level distribution comparison** against a reference. If Polaron does not name a baseline, every batch is compared against every other, and against itself (consistency).

Details / suggestions:

- Reference-to-reference null: split one batch's images into halves repeatedly, compute every statistic, take the spread as the "no change" band. With few images per batch the null will be wide; say so.
- Per-batch distances: KPI effect sizes (standardised median shift) and embedding distances (energy distance / MMD with image-level permutation).
- Within-batch consistency score per batch: spread of per-image KPIs and mean pairwise embedding distance. This directly answers "which supplier is most consistent across repeats".
- Per-tile anomaly maps (PatchCore-style nearest-neighbour distance to the reference memory bank) only as the visual "where" layer. Never as the batch verdict on its own (high false-positive risk, see LIBAD).
- Output: pairwise batch distance matrix + consistency ranking + per-image out-of-bounds flags.

## Feature 3. Traceability for responsible stakeholder

What it means with this data: Polaron framed the commercial value as liability assignment ("outside statistical bounds, it's your fault"). Traceability is the evidence chain that makes a verdict defensible.

Details / suggestions (keep it to one JSON per verdict plus one table in the UI):

- Identifiers: batch, image, tile grid, file hash.
- Acquisition record: image size, pixel scale if known, intensity statistics, curtaining score, edge-brightening score.
- Pipeline record: git commit, config hash, dependency lock hash, thresholds, timestamp; whether the pipeline was frozen before the held-back images were opened.
- Evidence record: which KPIs and which tiles drove the verdict; effect size and position relative to the null band.
- Routing: who should act. Suggested mapping: material KPI shift -> powder supplier / cell manufacturer; acquisition covariate shift -> own microscopy team (re-image); conflicting evidence -> materials expert review. The five-stakeholder chain from the discussion can be the vocabulary.
- Do not build: logins, roles, databases.

## Feature 4. Verdicts with explanation and KPI evaluation

What it means with this data: the one screen that features 1-3 feed into.

Details / suggestions:

- Verdict vocabulary: `within bounds`, `investigate`, `outside bounds` (same three states as accept/investigate/reject but worded for an unlabelled setting; the team can keep accept/reject on screen if preferred, with a footnote that bounds come from the reference batch, not from defect labels).
- Each verdict shows: top 3 drivers with effect sizes, prevalence (how many images outside the band), uncertainty split into sampling (n images), segmentation sensitivity (threshold perturbation), decision margin (distance to band edge), and acquisition panel (artefact covariates).
- Representative crops: one tile that typifies the reference and one that typifies the shift, with masks overlaid.
- Next action sentence, e.g. "Request supplier lot records for batch B; crack fraction +3.8 pp is outside the reference 99% band in 5 of 6 images; imaging covariates are within band."

## Suggested additions (not new features; layers on 1-4)

- **Artefact-vs-material separation as an explicit output.** Curtaining: measure vertical-stripe energy in the FFT (ratio of power along the vertical frequency axis to total). Edge brightening: intensity gradient toward image borders. Report per image, per batch. Do not remove from the image before measurement; measure KPIs on both raw and destriped versions and show whether conclusions change. This answers Polaron's second "next step" directly.
- **Physics touch (optional wow).** Polaron mentioned combining ML with physics-based simulation. TauFactor (tldr-group, same group as Polaron) computes tortuosity factor from a segmented pore phase. A 2D tortuosity per batch is indicative only, but it converts a segmentation into a transport-relevant number and uses the sponsor's own tool. Only attempt after features 1, 2 and 4 are working end to end.
- **ImageRep per-image uncertainty** on one phase fraction (pore or crack) where its assumptions hold. Doubles as the Devin challenge.

## Suggested cuts

- Anything that needs good/bad labels (calibrated reject thresholds, defect classifiers). There are none.
- A third model family. Two workflows: (1) unsupervised batch comparison + KPIs, (2) supervised batch classifier with leave-one-image-out. Everything else is a layer.
- Elaborate UI. One Streamlit screen reading cached JSON.

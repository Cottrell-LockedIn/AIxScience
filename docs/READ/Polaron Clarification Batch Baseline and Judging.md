# Polaron clarification: batch baseline, judging criteria and decision output (2026-10-03, via Alvin)

Verbatim, relayed from Polaron through the team:

> Treat batch 3 as the baseline, it's what's been "promised" by the supplier. Batch 1 and 2 arrived subsequently, and we're trying to tell if they are different. They are not explicitly better or worse than the batch 3 baseline, but they show the types of variation we need your models to pick up on.
>
> "different from the baseline, and in what way" is what we are driving for, the way we are measuring whether you correctly identify the "in what way" part is through the question of whether you can correctly assign to the other batches
>
> The judging criteria reflects this; can you identify what's different about the batches, and thus categorise the held back samples correctly. If you can, this implies unknown batch N could be categorised accurately as in or out of distribution - helping manufacturers make critical decisions about when to accept and reject a batch!

Q&A, verbatim (Steve Kench, Polaron, 16:46):

> Q: Should each image be assigned to a batch, or judged against the baseline? And if the system isn't confident, is "not enough evidence to decide" an acceptable answer?
>
> A: Always assigned to a batch, ideally with confidence and explanation, as these are the factors you will be judged on. The system can say it's very unconfident but should still take a bet.

## What this fixes

- `stats.reference_batch` = Batch_3 (Polaron-stated, no longer `auto`).
- Batch_1 and Batch_2 are "different", not "worse". No good/bad claim follows from any batch contrast; the verdict vocabulary stays `within bounds / investigate / outside bounds`, where `outside bounds` means "outside the Batch_3 distribution".
- Judged deliverable = (a) say what differs between the batches ("in what way"), (b) assign every held-back image to Batch_1 / Batch_2 / Batch_3, (c) frame the result as in- vs out-of-distribution relative to the Batch_3 baseline. Correct assignment is how (a) is scored.
- Per held-back image the output must always contain a batch assignment (a bet), a confidence, and an explanation (the drivers). "Not enough evidence" / `matches none` is not an acceptable final answer on its own: it may be reported as a low-confidence or out-of-distribution flag next to the assignment, never instead of it.
- Explaining what differs is half the criterion, so acquisition-driven batch differences may contribute to the assignment provided the driver is reported as acquisition vs material.

## Phase C output contract (spec only; Phase C is not started and needs the owner's approval)

Written so that the "always take a bet" rule is met with what Phase A/B already produce (image-level F01-F11, acquisition covariates, frozen DINOv2 image embeddings, Batch_3 split-half null). n = 31 images; nothing here needs more data or new feature work.

Per held-back image (and per `heldout_dryrun` image), the frozen pipeline writes one verdict JSON (`schema/verdict.schema.json`, `subject.kind = image`) containing, in this order of priority:

1. **The bet.** `verdict.closed_set.predicted_batch` in {Batch_1, Batch_2, Batch_3}. Always present. "none", "undecided" and "not enough evidence" are not legal values. Fallback if no model beats its permutation null in LOIO: the nearest batch by standardised image-level feature distance (median/MAD on Batch_3) still names a batch, and the confidence tier is `low`.
2. **The confidence.** `verdict.closed_set.confidence` in [0, 1] = the image-level predicted probability of the predicted batch (probabilities for all three batches are also written). Plus a pre-registered tier set before the held-back images are seen: `low` if max probability < 0.5 or if the model's LOIO accuracy is inside its image-label permutation null band (p >= 0.05); `medium` if max probability in [0.5, 0.75); `high` if >= 0.75 and LOIO p < 0.05. Chance levels are stated next to it (majority class 17/31 = 0.55; permutation null).
3. **The explanation.** Top three drivers for the bet: standardised logistic-regression coefficients x this image's standardised feature values (KPI/F01-F11 model) or nearest reference images (embedding model), each tagged `material` or `acquisition`; the image's acquisition covariates (noise, sharpness, curtaining, edge charging, t0/t1, height x res_tag) against the training range. If the drivers are mainly acquisition, say so in the reason sentence; the bet still stands.
4. **The in/out-of-distribution flag.** `verdict.open_set`: distance to each batch, Batch_3 null bands (95/99 %), `matches_known_batch` true/false, nearest batch. This is reported next to the bet, never instead of it: `matches_known_batch = false` adds "outside the Batch_3 distribution" to the explanation and caps the tier at `low`; it does not remove `predicted_batch`.
5. **The label.** `verdict.label` in {within_bounds, investigate, outside_bounds} from the pre-registered rule, verbatim in `verdict.rule` (FRAMEWORK §13.5 items 1-6). `investigate` is a label about the Batch_3 bounds, not a refusal to assign a batch.

Models (unchanged from FRAMEWORK Phase C, kept deliberately small for n = 31): logistic regression on image-level features with and without acquisition covariates (ablation reported), and a linear head or nearest-centroid on frozen DINOv2 image embeddings. Validation: leave-one-image-out (held-back proxy) and leave-one-acquisition-group-out (new-session proxy), image-level label permutation p >= 1,000 (Modal), tiles never split across folds. Model, thresholds and tiers are frozen (`git tag v1-frozen`) before `data/heldout/` is touched; the held-back images are processed once. Schema consequence for Phase C: make `closed_set.predicted_batch` and `closed_set.confidence` required when `subject.kind = image`.

What this does not change: Phase A/B scope and gates, the B7 batch-level verdicts (subject.kind = batch), the keep/investigate/drop rule for features, and the ban on good/bad claims.

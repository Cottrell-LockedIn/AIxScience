# Polaron clarification: batch baseline and judging criteria (2026-10-03, via Alvin)

Verbatim, relayed from Polaron through the team:

> Treat batch 3 as the baseline, it's what's been "promised" by the supplier. Batch 1 and 2 arrived subsequently, and we're trying to tell if they are different. They are not explicitly better or worse than the batch 3 baseline, but they show the types of variation we need your models to pick up on.
>
> The judging criteria reflects this; can you identify what's different about the batches, and thus categorise the held back samples correctly. If you can, this implies unknown batch N could be categorised accurately as in or out of distribution - helping manufacturers make critical decisions about when to accept and reject a batch!

## What this fixes

- Judged deliverable = (a) say what differs between the batches, (b) classify the held-back images into Batch_1 / Batch_2 / Batch_3 (or "matches none") correctly, (c) frame it as in- vs out-of-distribution relative to the Batch_3 baseline.
- Batch_1 and Batch_2 are "different", not "worse". Good/bad is still not a label; `within bounds / investigate / outside bounds` stays, but `outside bounds` now means "out of the Batch_3 distribution", which is what Polaron asks for.
- Held-back images are expected to come from the same material and (presumably) the same acquisition sessions as the 31 known images, so LOIO is the relevant estimate for held-back accuracy; LOGO remains the honest estimate for a genuinely new session (unknown batch N).
- Acquisition-driven differences between batches are allowed to contribute to classification *provided the driver is reported* (material vs session); explaining what differs is half the criterion.

## Consequences for the backlog (see NEXT_STEPS.md)

1. Batch-identification accuracy becomes a tracked number: LOIO (held-back proxy) and LOGO (new-session proxy), per feature family (F01-F11, acquisition covariates, embeddings), with the top drivers per batch.
2. DINOv2 embeddings + LOIO/LOGO (Modal) move up from item 7 to item 2.
3. Out-of-distribution distance to the Batch_3 reference (robust Mahalanobis / one-class on image-level features and embeddings, permutation-calibrated) becomes a first-class output with a `matches none` outcome.
4. Segmentation stability stays item 1 because the material features are the explanation layer.

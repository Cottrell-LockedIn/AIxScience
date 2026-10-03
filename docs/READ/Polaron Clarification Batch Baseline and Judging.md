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

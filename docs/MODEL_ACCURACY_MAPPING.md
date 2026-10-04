# Model Accuracy tab: fixed-artifact mapping

The tab is a read-only model card. It reads the committed `results/v1/loio_summary.json` through `GET /api/model-accuracy`; it never refits the classifier or treats tiles as independent samples.

| UI element | Fixed source | Meaning |
|---|---|---|
| 18/31 accuracy and Wilson interval | `loio_accuracy_str`, `wilson95` | Leave-one-image-out result on 31 recorded training images. |
| Majority reference | fixed 17/31, also documented in W17 | Baseline that always chooses Batch_3. |
| Permutation p-value | `permutation_p`, `n_permutations`, `permutation_seed` | Test attached to the frozen LOIO analysis. |
| Confusion matrix | `confusion_matrix` | Rows are true batches; columns are predicted batches. |
| Per-batch and tier tables | `precision_by_pred_batch`, `accuracy_by_tier` | Reliability of the recorded predicted batch or tier. |
| Held-out line | `docs/PRD_MODEL_IMPROVEMENTS.md` M8 | Owner-supplied labels after the official run: exploratory 2/3 and competition confidence score 5/6. Labels are not stored in the immutable prediction JSON, so this is clearly a documented scoring layer. |

The interface renders simple CSS/SVG-like bars from these values rather than presenting generated figures as saved experimental graphs. It labels all charts “Rendered from saved results.”

The result is not a defect or future-failure probability, a lot-acceptance rule, or an unseen-lot guarantee. Batch_1 and Batch_2 are frequently confused in the recorded LOIO matrix. The committed six-image exploratory artifact contains predictions without labels, so it is not used as an accuracy result.

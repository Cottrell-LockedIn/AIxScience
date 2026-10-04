# Model accuracy (frozen v1 classifier)

`phase_identity: stated by Polaron, not image-verified`

## What this tab shows
How well the frozen batch classifier performed when tested on images it had not seen, and how honest its
confidence levels are. All numbers come from one procedure: **leave-one-image-out (LOIO)** on the 31
training images (7 Batch 1, 7 Batch 2, 17 Batch 3). The model is refitted 31 times, each time leaving one
whole image out and predicting it, so every image is scored as unseen. Tiles from one image are never split
across fit and test. The 3 official held-out images are reported separately.

## Headline
- **Batch 3 (the supplier baseline) is detected reliably.** When the model says "Batch 3" it is right
  14/16 times (88%); it finds 14/17 of the true Batch 3 images
  (82%) and keeps 12/14 of the non-Batch 3 images out
  (specificity 86%). Batch 3-vs-rest accuracy 26/31 (84%,
  95 % CI 67%-93%), ROC AUC 0.94.
- **Three-way batch accuracy is 18/31 (58%, 95 % CI 41%-74%), above chance:**
  a label-permutation test gives p = 0.035 (1000 shuffles; shuffled labels score
  39% on average). The always-Batch-3 baseline scores 17/31.
- **The confidence tier is honest.** High-tier bets were right 14/18 (78%); low-tier bets
  4/13 (31%). The model says "low" exactly where it is weak.
- **Official held-out run: 2/3 correct, 5/6 under the judging confidence score**
  (the one miss, 3e122cbj, was flagged low confidence, so it scored 1 rather than 0).

## Where the model is weak (shown on purpose)
- Batch 1 vs Batch 2 is close to a coin flip: recall 2/7 and 2/7,
  precision 2/6 and 2/9. Balanced accuracy 0.46
  (chance 0.33), Cohen's kappa 0.31, Matthews correlation 0.31. The confusion matrix shows the
  Batch 1 / Batch 2 misses go mostly to each other.
- 31 training images is small: the 95 % interval on three-way accuracy spans 41%-74%.
- Phase B could not separate the embedding's batch signal from imaging conditions; part of what the model detects
  may be how the images were taken rather than the material.

## Metrics in plain words
| Metric | What it means | Value |
|---|---|---|
| Accuracy | share of images whose batch was predicted correctly | 18/31 = 58% |
| Wilson 95 % CI | the range of true accuracies consistent with 18/31 | 41%-74% |
| Permutation p | chance that shuffled labels would do at least this well | 0.035 |
| Balanced accuracy | average recall over the three batches (fair when classes are unequal) | 0.46 |
| Precision | of the images called X, how many were X | per batch, see table |
| Recall | of the true X images, how many were called X | per batch, see table |
| Cohen's kappa / MCC | agreement beyond what chance would give (0 = chance) | 0.31 / 0.31 |
| ROC AUC (one vs rest) | how well the probability ranks "X" above "not X" (0.5 = chance) | B1 0.84, B2 0.69, B3 0.94 |
| Log loss / Brier | penalise confident wrong probabilities (lower is better) | 0.76 / 0.48 |
| Tier calibration gap | mean gap between reported probability and observed accuracy, by tier | 0.22 |

## Confidence tier rule (frozen)
high if p_max >= 0.75 and LOIO permutation p < 0.05 and OOD label = within_bounds; otherwise low (p_max < 0.75, or LOIO permutation p >= 0.05, or OOD label = outside_bounds). Two tiers only: the v1 'medium' band (0.5 <= p_max < 0.75, 1/5 correct in LOIO) is reported as low since v1.1, a score-neutral presentation change; bets and probabilities are unchanged.

## Official held-out images
Status: official once-only run; truth supplied after the run; exploratory as evidence (n = 3). Scoring rule: 2 = correct at tier high; 1 = correct at tier low, or incorrect at tier low; 0 = incorrect at tier high (owner's reading of the judging criterion 'confidence score').

| image | true | predicted | p | tier | Batch 3 flag | correct | score |
|---|---|---|---|---|---|---|---|
| 3e122cbj | Batch_2 | Batch_1 | 0.98 | low | outside_bounds | no | 1 |
| fn0mhxef | Batch_1 | Batch_1 | 0.86 | high | investigate | yes | 2 |
| xrv9xvzb | Batch_3 | Batch_3 | 0.92 | high | within_bounds | yes | 2 |

## Model
StandardScaler(F01-F11) + PCA(n_components=29, svd_solver='full') of the raw mean-pooled BSE DINOv2 embedding, both fitted on the training images only; LogisticRegression(C=1.0, class_weight='balanced', solver='lbfgs', max_iter=10000, random_state=0), L2, multinomial.

Frozen choices: `docs/Log/2026-10-04_phase_c.md`. Validation data: `results/v1/loio_predictions.csv`, `results/v1/loio_summary.json`;
held-out: `results/v1/heldout.json`. Regenerate with `python -m qc accuracy-tab`.

## References
- Mitchell et al. (2019) Model Cards for Model Reporting, FAT* 2019, arXiv:1810.03993
- scikit-learn User Guide 3.4 'Metrics and scoring: quantifying the quality of predictions'
- Wilson (1927) Probable inference, the law of succession, and statistical inference, JASA 22:209-212
- Ojala & Garriga (2010) Permutation tests for studying classifier performance, JMLR 11:1833-1863
- Brier (1950) Verification of forecasts expressed in terms of probability, Mon. Weather Rev. 78:1-3

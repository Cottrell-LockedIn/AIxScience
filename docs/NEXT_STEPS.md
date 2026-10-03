# Next steps (ordered backlog)

Status: written at the fold of PRs #2-#5 into `stage/s1-s5-reality-check` (2026-10-03). Read `PROJECT_STATE.md` first, then this file. Every item names the command that runs it and the file it writes, so a fresh session can pick up without re-deriving context.

## Target (Polaron clarification, 2026-10-03)

Batch_3 = supplier's promised baseline; Batch_1/2 = subsequent deliveries that are *different*, not worse. Judged on: what differs between batches, and correct categorisation of the held-back images (Batch_1/2/3 or "matches none" = out of the Batch_3 distribution). See `docs/READ/Polaron Clarification Batch Baseline and Judging.md`. Tracked numbers from now on: batch-ID accuracy LOIO (held-back proxy) and LOGO (new-session proxy) per feature family, plus the top drivers per batch and whether each driver is material or acquisition.

## Item 0 (from the independent audit): `qc classify`

`src/qc/classify.py`: batch identification per feature family (F01-F11, acquisition covariates, both, later embeddings) with LOIO and LOGO accuracy, balanced accuracy and per-batch confusion, a permutation null (labels shuffled at image level, >= 1000 draws) so "acquisition predicts batch, material features do not" becomes a tested statement, per-image out-of-distribution distance to the Batch_3 reference (robust Mahalanobis on fold-fitted scaling, calibrated against the Batch_3 LOO distribution) with a `matches none` outcome, and a `--heldout` path that scores new images with a frozen model. Output `results/classify/`. Done when the table of LOIO/LOGO/null accuracies exists per family and the held-back path runs end-to-end on a synthetic image.

## Where we are (one paragraph)

S1-S5 (audit, tiles, artefact covariates, multi-Otsu segmentation, KPIs) run on all 31 images. The 11 consultant-approved features (`qc features`) and the validation harness (`qc validate`) are implemented and tested. Under the pre-declared keep/drop rule **no feature is `keep` yet**: F05/F06/F09 are acquisition-group-confounded, the rest fail bootstrap rank-stability (< 0.7), F03 and F11 are degenerate, F08 has no variance, and no feature has a threshold-sensitivity row. Logistic regression batch accuracy is LOIO 0.58 / LOGO 0.45 without covariates (chance 0.55) and 0.61 / 0.58 with them: the only predictive signal is acquisition. Reading: acquisition and thresholding dominate; no batch separation on material features yet. This is a finding, not a failure, and it fixes the order of work below.

## Backlog

| # | Item | Why | Command / file | Done when |
|---|---|---|---|---|
| 1 | **Segmentation stability challenger** (S4b): image-level or batch-pooled multi-Otsu thresholds; robust handling of particle-free tiles (31/1443 tiles with `t1 < 60` carry class-2 fraction 0.29 vs 0.08) | FEATURE_DOSSIER: rho(mean threshold, Si fraction) = -0.59 at image level; VALIDATION: fractions move 1.2-1.7 Batch_3 MAD under +/-10 % threshold | new `configs/v1b.yaml` (do not edit `v1.yaml`); `python -m qc segment --config configs/v1b.yaml` -> `data/masks_v1b/`, `results/*_v1b.*` | per-tile vs image-level thresholds compared on F01/F02 stability and sensitivity in `results/validate/` |
| 2 | **Threshold-sensitivity rows for all 11 features** | keep/drop rule cannot pass a feature without one (`stability.csv` column `threshold_sensitivity` is NaN for F03-F11) | extend `qc features` with `--thresholds perturbed` (reuse `kpi_sensitivity` masks) -> `results/features/features_sensitivity.parquet`; `qc validate` picks it up | `sens_over_mad` populated for every feature in `decisions.csv` |
| 3 | **Charging sensitivity row** (registration confirmed: 31/31 images aligned to <= 0.1 px; the bright-in-both-SE mask removes 7-9 % of class-2 area at p95 and does not move F02-F05 outside the within-batch IQR, but class 2 is brighter than class 1 in the SE channels too, so it is not a charging-specific test) | report masked vs unmasked F02-F05 as a sensitivity row, not a covariate; bright-phase identity needs EDS, not another detector | `python -m qc register` -> `results/registration/`; `python -m qc charging` -> `results/charging/features_masked_vs_unmasked.csv`; add the p95 / edge-n5 rows to the sensitivity table read by `qc validate` | `decisions.csv` carries a `charging_sensitivity_over_mad` column for F02-F05 |
| 4 | **Re-run harness, freeze the feature list** | decide keep/drop on evidence | `python -m qc validate --features results/features/features_by_image.parquet` -> `results/validate/features_by_image/decisions.csv` | kept list written to `docs/PROJECT_STATE.md` decision log and `configs/features_v1.yaml` (`status: keep/investigate/drop`) |
| 5 | **Defect candidates** (W2): crack / pull-out / cavity candidates with artefact-aware exclusion (curtaining = vertical periodic; crack = non-periodic, crosses phases) | failure-mode map: FM07 coating cracks, FM04 foreign particles, A01 curtaining, A03 shine-through | new `src/qc/defects.py`, `python -m qc defects` -> `results/defects/candidates.csv` + overlays; reviewed-count column left for the consultant | raw and reviewed counts per image; overlays for all candidates |
| 6 | **Verdict + decision ledger** (S8/S9): `within bounds / investigate / outside bounds`, two-lines-of-evidence escalation, append-only ledger with `pending / accepted / rejected` | Feature 3 traceability; RULEBOOK.md | `src/qc/verdict.py`, `schema/verdict.schema.json` (+ `status`, `ledger`), `python -m qc verdict` -> `results/verdicts/*.json`, `results/ledger.jsonl` | every verdict JSON validates against the schema and lists the features, images, thresholds and evidence it rests on |
| 7 -> **2a (moved up)** | **Modal**: DINOv2 embeddings for all 4329 tiles, image-level pooling, LOIO x LOGO batch-ID accuracy, plus robust Mahalanobis / one-class distance to Batch_3 with permutation calibration and a `matches none` outcome; synthetic robustness panels (noise, curtaining, gamma) | Polaron: categorise held-back images correctly and flag out-of-distribution; embeddings are the strongest untested batch-ID route; FRAMEWORK 12-13 | `scripts/modal_embed.py`, `scripts/modal_matrix.py` -> `results/embeddings/`, `results/validate/matrix/` | embedding-based LOIO/LOGO numbers next to the feature-based ones in `PRESENTATION_JUSTIFICATION.md` |
| 8 | **Presentation figures** | `PRESENTATION_JUSTIFICATION.md` TODO list | `scripts/presentation_figs.py` -> `results/figures/presentation/` | LOIO vs LOGO bars, with/without covariates, feature stability table, confound screen, reference LOO, kept-feature table, overlays |
| 9 | **Freeze** (`v1-frozen` tag) before any held-back image is opened | HANDOFF / Polaron: 3 held-back images classified after freeze | `git tag v1-frozen`; record config hash, dependency lock hash, thresholds in `PROJECT_STATE.md` | tag exists; `qc verdict` refuses to run on new images unless `--frozen-tag` matches |

## Standing constraints (do not relitigate)

- Image/stem is the independent unit (n = 31); all three detector views of a stem stay together in every split; LOIO and LOGO both reported.
- Phase names: class 2 = silicon, class 1 = graphite, class 0 = void/pore, "stated by Polaron (confirmed T+6.5h), not image-verified"; the consultant handoff records composition as unconfirmed and bright particles as unidentified. Bright-phase evidence can route to `investigate` + EDS request, never alone to `outside bounds`.
- Batch_3 is the reference, not a gold standard: median/MAD, leave-one-out, `vc2whyaq` / `ufdvpb81` / `hzumfsms` flagged.
- No good/bad battery claims; the consultant importance weights are routing hints, not multipliers.
- `configs/v1.yaml` hash is stamped into every result; a config change means regenerating everything.
- Never commit `data/`, tiles, masks or raw TIFFs.

## Open PRs / sessions at the time of writing

See `PROJECT_STATE.md` handover log for the list and the fold record.

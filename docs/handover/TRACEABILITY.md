<!-- Redacted for the Phase-A reset handover: observed Phase B/C result numbers removed. -->
# Traceability: every Polaron / consultant input -> where it is in the repo (2026-10-03)

Branch `stage/s1-s5-reality-check` @ `d4d035c` (PR #1). Status: DONE = code + committed result; PARTIAL; LOCAL = code exists, uncommitted, not run on real data; MISSING; OPEN = needs an answer from Polaron. Lead's own reading; Phase A/B are being re-checked independently.

## 1. Polaron kickoff (`docs/READ/Polaron Kickoff Discussion.md`)
| Requirement | Where | Status |
|---|---|---|
| Classify the three batches | `qc classify`, `results/classify/*/accuracy.csv` | PARTIAL - embeddings family not run |
| Explainable, physically interpretable drivers | `results/classify/*/drivers.csv` tagged material/acquisition | PARTIAL - drivers are mostly acquisition |
| No good/bad labels | RULEBOOK verdict vocabulary; `accepted/rejected` only human (`qc decide`, LOCAL) | DONE |
| Artefacts vs real microstructure; do not discard artefacts | `results/artefacts_per_image.parquet`, confound screen, `results/charging/`, `results/registration/` | DONE (raw vs destriped KPI comparison MISSING) |
| Most consistent supplier across repeats | consistency ranking (FRAMEWORK Phase B, `src/qc/stats.py`) | MISSING - `stats.py` is a 17-line stub |
| Three held-back images | `qc classify --heldout` path | PARTIAL - not frozen, not run |
| Liability / traceability evidence chain | `schema/verdict.schema.json`; `src/qc/verdict.py` | LOCAL |
| Physics simulation (optional) | TauFactor | MISSING (optional) |

## 2. Polaron clarification (`docs/READ/Polaron Clarification Batch Baseline and Judging.md`)
| Requirement | Where | Status |
|---|---|---|
| Batch_3 = promised baseline | `REFERENCE_BATCH` in validate/classify; RULEBOOK | DONE |
| Identify what differs between batches | drivers.csv; batch_tests.csv | PARTIAL - answer so far: acquisition, not F01-F11 |
| Categorise held-back samples correctly | classify | PARTIAL |
| Unknown batch N in / out of distribution | OOD in classify: 0 images `matches_none`; PCA-whitened OOD LOCAL; leave-one-batch-out test MISSING | PARTIAL |

## 3. Questions for Polaron (`docs/READ/Questions for Polaron.md`)
| # | Question | Status |
|---|---|---|
| 1 | Pixel size 25 nm/px | OPEN - reported in px |
| 2 | Bright phase identity | Answered "silicon"; consultant says unconfirmed -> provenance tag kept |
| 3 | Reference batch | Answered: Batch_3 (clarification). `docs/DATA_AUDIT.md` "Unconfirmed facts" is STALE on Q2, Q3, Q5 |
| 4 | Held-back from known batches or a new one? | OPEN -> `matches_none` must be supported |
| 5 | Same field of view per stem | Verified: registration 31/31, shift <= 0.1 px |
| 6 | Why SE instead of ETD | OPEN -> detector set is a covariate |
| 7 | Same beam conditions | OPEN -> acquisition covariates stand in |
| 8 | Collector direction | OPEN |
| 9 | Cropped to coating thickness | OPEN |
| 10 | Artefact list | Partly answered by consultant prep failure modes P01-P06 |
| 11 | Pristine or cycled | Answered (consultant): fresh, uncycled |
| 12 | What to measure first | Answered by consultant sign-off (F01-F11) |
| 13 | Stakeholder routing | RULEBOOK routing |
| 14 | TauFactor wanted? | OPEN |
| 15 | Crops in slides allowed? | OPEN - must ask before the deck |
| 16 | Held-back channels | OPEN - missing-channel tolerance NOT tested |

## 4. Feature Details and Suggestions (`docs/READ/Feature Details and Suggestions.md`)
| Item | Status |
|---|---|
| F1 batch classifier, LOIO, no tile leakage | DONE (hand features); embeddings LOCAL |
| F1 artefact ablation with/without covariates | DONE (material vs material+acquisition families) |
| F1 embedding explanation (nearest baseline tiles / occlusion) | MISSING |
| F1 "none of the three / investigate" on held-back | PARTIAL (calibrated, never fires) |
| F2 reference half-split null band | MISSING (validate has reference LOO instead) |
| F2 energy distance / MMD on embeddings, image-level permutation | MISSING |
| F2 consistency score + pairwise distance matrix | MISSING |
| F2 PatchCore "where" maps (visual only) | MISSING (optional) |
| F3 verdict JSON with hashes, routing | LOCAL |
| F4 one screen, drivers, crops, next action | `app/streamlit_app.py` 20-line stub; next-action text in verdict.py LOCAL |
| KPIs on raw vs destriped | MISSING |
| ImageRep uncertainty (Devin challenge) | MISSING |

## 5. Consultant inputs
| Input | Status |
|---|---|
| Sign-off F01-F11 | DONE: implemented, validated; 0 keep / 11 investigate |
| Threshold sensitivity for F01-F11 (gate G3) | MISSING |
| 22 + 6 failure modes | DONE: `docs/FAILURE_MODE_MAP.md` (2 observable, 6 proxy, 14 unobservable); RULEBOOK gates |
| Bright objects = possible contamination | DONE: capped at `investigate` + EDS |

## 6. FRAMEWORK phase gates (lead's reading, to be verified independently)
- Phase A: all bullets implemented; gate (covariates plotted by batch) DONE (`results/audit/artefacts_by_batch.png`). "Look at 10 tiles per batch" - evidence not located.
- Phase B: KPIs DONE (5-tile manual check: evidence not located); embeddings LOCAL (Modal benchmark MISSING); `stats.py` (reference half-split null, distance matrix, energy/MMD, consistency ranking) MISSING; gate "distance matrix, consistency ranking, one verdict JSON" NOT MET.
- Phase C: logistic on KPIs DONE; embedding head LOCAL; artefact ablation DONE; KPI drivers DONE; embedding drivers MISSING; KPIs-to-3-5 not done (0 pass the keep rule); DECISION_RULES superseded by RULEBOOK.md.
- Judging map gaps: Modal time/cost table, Devin/ImageRep, one-screen usability.

## Verdict
On track for hygiene, features, validation and rules. Not on track for: Phase B statistics (`stats.py`), the verdict JSON, embeddings results, OOD validation, Modal, held-back freeze. Phase B is NOT fully done.

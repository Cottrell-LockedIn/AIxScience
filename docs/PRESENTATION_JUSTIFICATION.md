# Presentation justification note

Status: working note (T+1 day). Every methodological choice we will be asked to defend on stage, with the one-line justification and the evidence that backs it. Numbers are from PR #1 outputs (31 images, 93 TIFFs, config hash `de199d6c8d69`; earlier `1bec114301c3` numbers were regenerated and unchanged) unless marked TODO.

| # | Choice to justify | One-line justification | Evidence / where |
|---|---|---|---|
| 1 | The image (8-char stem) is the independent unit, n = 31, not 93 TIFFs and not 4329 tiles | 93 TIFFs = 31 fields of view x 3 detectors of the same cut; tiles are pseudo-replicates of one field | `docs/DATA_AUDIT.md`; AGENTS.md rule; hierarchical-bootstrap literature (Method Evidence note) |
| 2 | Leave-one-image-out (LOIO) instead of random tile splits | Tiles of one image on both sides of a split let a model memorise the microscope session; the score is fake | Feature Details, Feature 1; FRAMEWORK S00 |
| 3 | **Leave-one-acquisition-group-out (LOGO) in addition to LOIO** | Images cluster into 13 (height, resolution-tag) groups with near-identical noise (within-group noise spread 1.7 %, between 45 %); group predicts noise/sharpness/mean grey/curtaining with permutation p = 0.0002; 5 groups span 2-3 batches. LOIO alone still leaves the sibling images of the same session in training, so a classifier can read the session. LOGO removes the whole session. Report both; a large LOIO-LOGO gap = session leakage | `results/audit/REALITY_CHECK.md`; evidence note C3 (`C1_defaults_evidence.md`) |
| 4 | Artefact covariates are measured and kept, never removed | Polaron: artefacts may correlate with chemistry; so curtaining, stripe score, edge charging, noise, sharpness are covariates in every model and ablated (with/without) | Polaron kickoff notes; `src/qc/artefacts.py`; `reality_check_artefacts.png` |
| 5 | Artefact ablation as a required output | If batch accuracy collapses when covariates are removed, the classifier read the ion beam, not the material | Feature Details, Feature 1 |
| 6 | Batch_3 is the reference but treated as a fallible distribution | Polaron named it baseline, not error-free; leave-one-out robust z flags 3 of 17 reference images (`vc2whyaq` +10.8, `ufdvpb81` +6.7 on silicon diameter; `hzumfsms` +3.7 on void fraction); Batch_3 noise is bimodal (7 images at 30-31, 10 at 37-46) | `c4_batch3_loo.csv`; evidence note C4 |
| 7 | Robust statistics (median/MAD, permutation) rather than normal theory | n = 7/7/17, outliers present, distributions skewed | evidence note C4; S6 plan |
| 8 | 10 pre-registered features, everything else descriptive | 31 images cannot support 84 hypotheses; false batch effects are guaranteed without pre-registration + multiplicity control | consultant sign-off sheet (approved); `C1_tier_mapping.md` |
| 9 | Why these 10 (silicon fraction, size median/p90, count density, Clark-Evans, solidity; void fraction, local thickness, chord anisotropy; windowed void IQR; silicon-void interface fraction) | Tier 1 = measurable from the existing BSE 3-class mask; cover the four physical axes (how much, how big, how arranged, how uniform) plus one interface metric; consultant approved | sign-off sheet Part B; justification dossier (TODO, child session) |
| 10 | Phase names with provenance tag | class 2 = silicon, 1 = graphite, 0 = void: stated by Polaron, not image-verified; Si vs SiOx indistinguishable in BSE; binder/additive lumped | AGENTS.md; FRAMEWORK S00 |
| 11 | Units in pixels, nm only "if 25 nm/px is true" | 13 resolution tags, 24.9992-25.0006 nm/px, written by tifffile not the microscope | evidence note C1; `docs/DATA_AUDIT.md` |
| 12 | No orientation / depth-gradient features | Top and bottom 5 % rows have the same void fraction as the middle (0.08/0.09 vs 0.10); no collector or free surface in frame; intensity trends go both directions (charging/drift) | evidence note C2; `c2_edge_profiles.csv` |
| 13 | Per-tile multi-Otsu, with sensitivity | Simple, reproducible, standard for Si/graphite BSE; +-10 % threshold perturbation reported as error bar; known failure on particle-free tiles (2 %) is documented and is the first segmentation challenger | `results/kpi/sensitivity.csv`; REALITY_CHECK.md |
| 14 | Verdict vocabulary `within bounds / investigate / outside bounds`, not good/bad | No good/bad labels exist (Polaron); bounds come from the reference + literature, not from defect labels | Feature Details, Feature 4 and Suggested cuts |
| 15 | `outside bounds` requires two independent lines of evidence | Reference deviation alone can be a session effect; literature bound alone depends on unverified scale; defect evidence alone depends on candidate review. Two agreeing lines, each cited, or `investigate` | `RULEBOOK_literature_bounds.md`; evidence base (child session) |
| 16 | Agent-generated labels used only for segmentation/defect candidates, never for accept/reject | The labelling agent had no outcome data; a label on Tier 3/4 dimensions is an opinion encoded as a number | this note; evidence base topic 7 |
| 17 | Traceability = JSON per verdict + append-only decision ledger | Polaron: "outside statistical bounds, it's your fault" needs a reconstructable evidence chain; `status: pending/accepted/rejected` lets a verdict be revisited without rewriting history | `schema/verdict.schema.json`; S8 plan |
| 18 | Held-back images: frozen pipeline, confidence + abstention | 3 images is a coin-flip sample; `v1-frozen` tag before opening them; "matches none / investigate" is a valid answer | FRAMEWORK S9, S11 |
| 19 | Modal used for compute, not for data | Embeddings for 4329 tiles, LOIO x LOGO x config matrix, robustness panels; it cannot fix n = 31 | `docs/READ/Modal Recommended Workflow.md` |
| 20 | Tile grid covers 100 % of every image | Edge-anchored last tile; verified 93/93 image-channel fields fully covered after 8 px crop (found by review, fixed in PR #1) | `src/qc/tiles.py`; PR #1 |

## Target as clarified by Polaron (2026-10-03)

Batch_3 is the promised baseline; Batch_1/2 are different, not worse; the judged question is "what differs, and can you categorise the held-back images (in or out of the Batch_3 distribution)?" Every slide should answer that question first and keep the good/bad disclaimer as a footnote. Report batch-ID accuracy as LOIO (held-back proxy) and LOGO (new-session proxy), name the top drivers per batch, and label each driver material or acquisition. Source: `docs/READ/Polaron Clarification Batch Baseline and Judging.md`.

## Batch identification with a permutation null (`results/classify/features_f01_f11/accuracy.csv`)

| family | LOIO acc | null p95 | p_perm | LOGO acc | p_perm |
|---|---|---|---|---|---|
| material F01-F11 (11) | 0.45 | 0.52 | 0.19 | 0.32 | 0.61 |
| acquisition covariates (6) | 0.71 | 0.52 | 0.005 | 0.65 | 0.005 |
| material + acquisition (17) | 0.65 | 0.52 | 0.015 | 0.68 | 0.005 |
| old KPIs (8) | 0.58 | 0.52 | 0.045 | 0.45 | 0.14 |

Majority chance 0.55; null mean 0.34-0.36. Slide sentence: "with labels shuffled, the material features do exactly as well as they do with the true labels; the microscope settings identify the batch at 0.71." Top drivers per batch are in `drivers.csv`, each tagged material or acquisition. OOD screen (`ood.csv`): no image falls outside every batch at alpha 0.05 - the hand features are too weak for an in/out call; this is the honest reason embeddings come next.

## Numbers now available (config hash `de199d6c8d69`, `results/validate/`)

All from `python -m qc validate` (PR #2 harness) on the 11 pre-registered features alone (`results/validate/features_f01_f11/`) unless stated; n = 31 images, seed 0, 1000 bootstraps, 10 000 permutations.

| Claim on stage | Number | File |
|---|---|---|
| LOIO vs LOGO, no acquisition covariates (logistic regression, fold-fitted scaling) | accuracy 0.45 (LOIO) vs 0.32 (LOGO); chance (majority) 0.55 | `loio_logo.csv` |
| Same, with the 6 acquisition covariates added | 0.65 (LOIO) vs 0.68 (LOGO) | `loio_logo.csv` |
| Reading | material features alone do not predict batch; the only predictive signal is acquisition (noise, sharpness, mean grey). This is the artefact-ablation result the brief asked for | |
| Keep / drop / investigate under the pre-declared rule | 0 keep, 0 drop, 11 investigate | `decisions.csv` |
| Acquisition-confounded (group association stronger than batch, p_group < 0.05) | F05 count density (p 0.0002), F06 Clark-Evans R (p 0.007, rho +0.53 with mean grey); F09 anisotropy borderline (p ~0.05, rho +0.55 with horizontal-stripe score) | `confound.csv` |
| Bootstrap rank stability (>= 0.7 required) | F06 0.75; F01 0.69; F03 0.63; F07 0.56; F02 0.54; F05 0.44; F04 0.43; F11 0.39; F10 0.24; F09 0.22; F08 undefined (median pinned at 26 px in all batches) | `stability.csv` |
| Degenerate | F11 Si-void interface fraction ~0.001 (max 0.004); F03 Si median diameter 7.6-8.5 px, set by the 20 px min-object floor | PR #3 report |
| Batch effects after BH correction (median shift / Batch_3 MAD) | none with q < 0.05; best is F04 p90 Si diameter, Batch_2 vs Batch_3, -1.17 MAD after residualising on covariates, q = 0.15 | `batch_tests.csv` |
| Old KPI table (8 columns) for comparison | 8 investigate; LOIO 0.58 / LOGO 0.45 without covariates, 0.61 / 0.58 with | `results/validate/kpi_per_image/` |
| Threshold sensitivity (+/-10 %) on class fractions | moves them by 1.2-1.7 Batch_3 MAD, i.e. more than any batch gap; no sensitivity row exists yet for F03-F11 (NEXT_STEPS item 2) | `stability.csv` |
| Reference LOO (robust z > 3 vs the other 16) | old KPIs: 5 of 17 Batch_3 images flagged — `vc2whyaq` (+10.8, Si diameter), `ufdvpb81` (+6.7), `hzumfsms` (+3.7, void fraction), `cfe5vt7s` (+3.3), `0grcilhi` (+3.0); F01-F11 table: 7 of 17 (`0grcilhi`, `hzumfsms`, `mgxahqnk`, `tuy3zymq`, `vc2whyaq`, `x77cy643`, `xgj4xftb`). The reference is not clean; every bound is reported with and without the flagged images | `reference_loo.csv` |
| Detector registration (BSE vs In-Lens vs ETD/SE, phase correlation on 12 windows per image) | 31/31 registered: median shift <= 0.10 px, window std <= 0.09 px, scale 0.99996-1.00003, rotation <= 0.003 deg -> the three TIFFs are one scan, pixel-aligned (observed) | `results/registration/REGISTRATION.md` |
| "Is bright BSE = charging/relief?" test (class-2 pixels also bright in both SE channels) | at p95 the flagged class-2 area is 0.089 / 0.074 / 0.070 (B1/B2/B3 medians); edge glow at void borders <= 0.005; masked F02-F05 stay inside the within-batch IQR for every p95/p99/edge variant. BUT class 2 is systematically brighter than class 1 in both SE detectors (median z 1.3-1.9 In-Lens, 3.7-4.1 ETD/SE), and the flags sit inside large class-2 particles, so the mask measures SE brightness of the phase, not charging. Decision: not a v1 covariate or default mask; kept as a `qc charging` sensitivity option. Bright-phase identity still unverified | `results/charging/CHARGING.md` |
| Multi-Otsu failure tiles | 31/1443 tiles with t1 < 60 carry class-2 fraction 0.29 vs ~0.08; image-level rho(mean t1, F02) = -0.59 | `docs/FEATURE_DOSSIER.md` |

Honest one-liner for the deck: "We pre-registered 11 consultant-approved measurements, built the validation harness first, and found that none separates the batches once acquisition is controlled; what does separate them is the microscope session. The next lever is segmentation stability, not more features."

## Figures still needed for the deck (TODO; `scripts/presentation_figs.py`, NEXT_STEPS item 8)
- LOIO vs LOGO bars, with and without covariates (numbers above).
- Feature stability table + confound heat-map (from `stability.csv`, `confound.csv`).
- Kept / investigate / dropped table with reasons (`decisions.csv`).
- Reference LOO plot with the 3 flagged Batch_3 images and their overlays.
- One representative crop per batch with mask overlay, provenance tag in the caption.
- Failure-mode coverage table (which of the consultant's 22 modes we screen, proxy or cannot; `docs/FAILURE_MODE_MAP.md` when it lands).

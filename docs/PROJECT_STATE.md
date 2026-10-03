# Project State

Updated: 2026-10-03, ~T+1d (Devin cloud session 1, part 2)
Phase: S1-S5 + 11 pre-registered features + validation harness + evidence base folded into PR #1 on `stage/s1-s5-reality-check`; consultant sign-off received; no feature passes the pre-declared keep rule yet (see `NEXT_STEPS.md`)
Submission repository: github.com/Cottrell-LockedIn/AIxScience (private, org), local clone at `code/AIxScience_Msia`. Scaffold pushed to `main` at commit c9943d0 (T+6h). Planning docs mirrored under `docs/` in the repo.

## Current decision

The technical sequence is not fixed. The team will select the approach after inspecting the released dataset.

Draft plan: `FRAMEWORK.md` (24 h clock, lanes, default stack, decision tree, Modal and Devin challenge plans, open decisions).
Research audit: `Log/2026-10-03_ideation_verification.md`. All cited sources and licences verified; two corrections added (alibi-detect is BSL 1.1; Polaron founders = ImageRep authors' group).

Proposed Devin-challenge paper: ImageRep (Dahari et al., Advanced Science; code BSD-3). Pending team confirmation.

Agent context remaining (Devin Desktop, this session): unknown (tool does not expose it).

## Workstreams

| Workstream | Owner | Status | Reviewer | Context remaining |
|---|---|---|---|---|
| Dataset and acquisition audit (S1-S3) | Devin cloud session 1 | Done, in PR #1 | Required | n/a |
| KPI and segmentation lane (S4 v1 + reality check) | Devin cloud session 1 | Done, in PR #1; S4 challenger needed (per-tile multi-Otsu unstable on particle-free tiles) | Required | n/a |
| Batch-drift statistics | Unassigned | Not started | Required | Unknown |
| Frozen-feature challenger | Unassigned | Not started | Required | Unknown |
| Modal workload | Unassigned | Not started | Required | Unknown |
| Product and demo | Unassigned | Not started | Required | Unknown |

## Dataset facts

From the Polaron kickoff (`READ/Polaron Kickoff Discussion.md`):

- FIB-SEM cross-sections of electrodes (~30 um); 3 batches; 3 held-back images as the test;
- 18 MB to GB per image; hundreds of images at most; image is the independent unit;
- labels: batch membership only, no good/bad;
- known artefacts: ion-beam curtaining (vertical lines), bright edges; measure, do not discard.

Inspected at T+1.5 (`READ/Dataset First Look.md`): 7 / 7 / 17 fields of view, 3 detector channels each (BSE, Inlens, ETD|SE), 7000 px wide, ~1.7 GB, public Drive. Likely graphite anode with a high-Z particle phase; BSE gives 3-class contrast. Pixel size probably 25 nm (TIFF tag, unconfirmed).

Audited (`docs/DATA_AUDIT.md`, `results/audit/REALITY_CHECK.md`, PR #1): 31 images / 93 TIFFs (the repo's Drive listing had 92; `img_xgj4xftb_Inlens.tif` was missing and has been added, so all 31 images have BSE+Inlens plus ETD or SE); widths 6960-7000 px; 13 distinct XResolution tags, all ~25.000 nm/px, written by tifffile (unconfirmed); coloured edge line on left (20 files) or right (18 files), covered by the 8 px crop. Class fractions do not separate batches beyond within-batch spread and +/-10 % threshold sensitivity. Noise and sharpness do separate (Batch_3 much less noisy); images form 15 (height, res-tag) groups with near-identical noise, 5 spanning 2-3 batches: acquisition sessions appear to cut across batch labels.

Still unknown: whether the (height, res-tag) groups are sessions or specimens; pixel size confirmation; identity of the bright phase; whether a baseline batch is named; whether held-back images may come from a new batch.

## Freeze record

Before the unseen batch arrives, record:

- preprocessing configuration;
- scale-bar and annotation masks;
- KPI definitions;
- feature extractor and revision;
- aggregation rule;
- decision thresholds;
- dependency lock hash;
- Git commit and timestamp.

## Handover log

### 2026-10-03 cloud session 1 (S1-S5)

- Completed: `audit.py`, `tiles.py`, `artefacts.py`, `segment.py`, `kpi.py`, `scripts/reality_check.py`, tests (13 passing); all stages run on 31 images (audit 12 s, tiles 16 s, artefacts 57 s, segment 75 s, kpi 89 s on 8 CPU cores; 4329 tiles, 1443 BSE). Results under `results/` with `config_hash` + `git_sha`.
- Evidence: PR #1 (figures + Report-back), `results/audit/REALITY_CHECK.md`, `docs/DATA_AUDIT.md`, `results/audit/overlays/`.
- Decisions: tile 1024/512 per config (FRAMEWORK 2b still says 512, doc discrepancy open); per-image KPI = mean over tiles; curtaining measured on the k_y~0 FFT band (vertical image stripes) with the orthogonal band kept as control; hole filling limited to holes < 20 px so enclosed bright particles survive.
- Reviewer verdict: pending (fresh-context review required per AGENTS.md).
- Review fixes (Devin Review on PR #1): edge-anchored tiles for full field-of-view coverage, fallback for tiles with <3 grey levels, config-hash/position check before joining masks in `qc kpi`, SHA-256 recomputed in audit, nullable pixel-size tag. All S2-S5 outputs regenerated; conclusions unchanged (13 acquisition groups, not 15, after recount).
- Unresolved risks: batch/session confound (noise, sharpness, res-tag groups); multi-Otsu instability on tiles without class-2 particles; pixel size and phase identity unconfirmed.
- Exact next action: consultant checkpoint C1 on overlays/figures and the five questions in PR #1; then wave 1 (S5 embeddings on Modal, S6, S7 with artefact ablation + leave-one-group-out, S8, S9).

### 2026-10-03 cloud session 1, part 2 (consultant approval -> features, validation, evidence, fold)

- Completed: consultant approved the sign-off sheet (Parts A/B). Four child sessions ran in parallel and were folded into `stage/s1-s5-reality-check`: PR #2 validation harness (`src/qc/validate.py`, `qc validate`), PR #3 feature blocks (`src/qc/features.py`, `qc features`, `configs/features_v1.yaml`), PR #4 feature dossier (`docs/FEATURE_DOSSIER.md`, 33 DOIs), PR #5 evidence base (`docs/EVIDENCE_BASE.md`, `docs/evidence/claims.csv` 72 claims, `references.bib` 109 DOIs). `main` commit 50b375f (config class_names, Polaron-confirmed phase names) merged in; all results regenerated under config hash `de199d6c8d69` (previously `1bec114301c3`). Tests: 29 passing.
- Evidence: `results/validate/features_f01_f11/` (11 features alone), `results/validate/kpi_per_image/` (old KPIs); numbers summarised in `docs/PRESENTATION_JUSTIFICATION.md`.
- Decisions: (1) pre-declared keep/drop rule (rank stability >= 0.7, not acquisition-confounded, threshold sensitivity < 0.5 Batch_3 MAD) applied -> 0 keep / 11 investigate; no feature is frozen into the verdict yet. (2) F11 (Si-void interface) and F03 (Si median diameter) are degenerate as defined; kept in the table as pre-registered, flagged uninformative. (3) Bright-phase (class 2) evidence routes to `investigate` + EDS request only, never alone to `outside bounds`: the consultant handoff (`docs/READ/Consultant Failure Modes Handoff.md`) records composition as unconfirmed and bright particles as unidentified (possible contamination, charging, relief), while Polaron states silicon; both positions recorded. (4) Evidence base corrected two numbers in the earlier rulebook draft (Si wt% range and porosity window were not in the cited abstracts) -> direction-only rules. (5) Consultant failure-mode importance weights are routing hints, not score multipliers. (6) Cycling-induced modes are out of scope (fresh electrode).
- Rejected: training on agent-generated 84-feature labels as accept/reject ground truth (labels unavailable anyway; would only be valid for segmentation/defect candidates).
- Reviewer verdict: pending (fresh-context review of PR #1 after the fold).
- Unresolved risks: no feature passes the keep rule; acquisition group predicts batch better than material features (LOGO 0.32 vs 0.68 with covariates); per-tile multi-Otsu failure on particle-free tiles drives F02-F05; Batch_3 reference LOO flags 5/17 images on the old KPIs and 7/17 on F01-F11 at |z| > 3 (more than the 3 first reported); PR #7 (`qc register`, `qc charging`) folded: 31/31 images pixel-registered across detectors (|shift| <= 0.1 px); class-2 pixels also bright in both SE channels are 7-9 % of class-2 area at p95 and do not move F02-F05 outside the within-batch IQR, but class 2 is brighter than class 1 in the SE detectors too, so the test cannot separate charging from a genuinely bright phase -> charging mask kept as a sensitivity option, not a covariate; bright-phase identity remains unverified. PR #6 failure-mode map + `docs/RULEBOOK.md` folded: of the consultant's 22 material modes 2 are directly observable, 6 proxy-only, 14 unobservable in this data; no rule currently passes its gates; bright-object (FM04) evidence capped at `investigate` + EDS.
- Polaron clarification (after the fold, same day): Batch_3 is the supplier's promised baseline; Batch_1/2 are different, not worse; judging = identify what differs and categorise the held-back images correctly (in/out of the Batch_3 distribution). Recorded verbatim in `docs/READ/Polaron Clarification Batch Baseline and Judging.md`. Consequence: batch-identification accuracy (LOIO as held-back proxy, LOGO as new-session proxy) and an OOD distance to Batch_3 with a `matches none` outcome become tracked deliverables; DINOv2 embeddings move up the backlog; the material features remain the explanation layer. The current numbers (material features LOIO 0.45; with acquisition covariates 0.65) mean the batch-ID task is not yet solved.
- Independent audit (session 5cd6237f, report `REVIEW_ON_TRACK.md` in that session): verdict "off track against the Polaron judging criterion, recoverable; hygiene sound". Fixed in response: `validate.py` no longer hard-codes the old-KPI LOO flag set as the exclusion list — `batch_tests` now excludes the reference images flagged by `reference_loo` on the table being validated (KPIs: 0grcilhi, cfe5vt7s, hzumfsms, ufdvpb81, vc2whyaq -> n_ref 12; F01-F11: 0grcilhi, hzumfsms, mgxahqnk, tuy3zymq, vc2whyaq, x77cy643, xgj4xftb -> n_ref 10); decisions unchanged (8/8 and 11/11 `investigate`), KPI void-region-size contrast still the only BH survivor (q 0.046 on the reduced reference). F05 confound p corrected to 0.0002 in PRESENTATION_JUSTIFICATION and RULEBOOK; stale `1bec114301c3` mentions annotated; the metadata-polluted `results/validate/features_by_image/` run removed. Not changed: `claims.csv` X2 `status=not_found` is correct per the EVIDENCE_BASE legend (DOI resolves, number not in accessible text). Open from the audit: the judged deliverable (batch classifier, OOD distance to Batch_3, held-back path) is unimplemented -> `src/qc/classify.py` is now item 1 of NEXT_STEPS; "only acquisition predicts batch" needs a permutation null.
- `qc classify` added (`src/qc/classify.py`, 5 synthetic tests; 43 tests total): batch identification per feature family with LOIO/LOGO accuracy, balanced accuracy, per-batch recall, image-level label-permutation null (200 draws), standardised logistic-regression drivers tagged material/acquisition, robust-distance OOD screen against every batch calibrated on that batch's LOO distances, and a `--heldout` path (frozen model + OOD + verdict text). Observed on F01-F11: material 0.45 LOIO (p_perm 0.19, inside the null band), acquisition 0.71 (p 0.005), both 0.65 LOIO / 0.68 LOGO; KPIs 0.58 (p 0.045). Drivers: Batch_1 sharper/noisier/lower F01; Batch_2 lower In-Lens edge charging and lower F06; Batch_3 softer/lower noise/higher F01. OOD: no image `matches none` at alpha 0.05. Reading: the "acquisition, not material, identifies the batch" statement is now permutation-tested; the current features cannot carry a held-back categorisation on their own; embeddings and segmentation stability are the next levers.
- Exact next action: `docs/NEXT_STEPS.md` items 1-4 (segmentation challenger, sensitivity rows for all features, charging covariate, re-run harness and freeze the kept list), then defects, verdict + ledger, Modal matrix, presentation figures, `v1-frozen` tag before any held-back image.

Record for each entry:

- completed work;
- evidence and source links;
- decisions and rejected alternatives;
- reviewer verdict;
- unresolved risks;
- exact next action.

## Decision log: phase identities and reference batch (C1 pre-sign-off)

- Polaron (via Alvin) states: class 2 (bright) = silicon, class 1 (mid) = graphite, class 0 (dark) = void/pore. Adopted as named phases with provenance "stated by Polaron, not image-verified"; caveats: Si vs SiOx indistinguishable in BSE, binder/conductive additive lumped into class 0/1. Rule updated in AGENTS.md, FRAMEWORK.md Section 00, HANDOFF_BRIEF.md (configs/v1.yaml comment left unchanged on purpose: the config hash is over the file bytes and all PR #1 results carried 1bec114301c3 at the time; superseded by `main` 50b375f which edited configs/v1.yaml, after which everything was regenerated under de199d6c8d69).
- Reference batch = Batch_3 (Polaron). Treated as a robust reference distribution (median/MAD, leave-one-out within Batch_3); the LOO check flags `vc2whyaq` (silicon eq-diameter z +10.8), `ufdvpb81` (+6.7), `hzumfsms` (void fraction +3.7) for `investigate` before they define "normal".
- No further clarification from Polaron is available. Defaults with measured evidence: pixel size reported in px (tags 24.9992-25.0006 nm/px, software-written); no collector / free surface in frame (edge dark fraction equals mid-image in all 31 BSE images); the 13 (height, resolution-tag) groups are treated as acquisition sessions (within-group noise range 1.7 % vs 45 % between groups; permutation p = 0.0002) so leave-one-group-out validation is required in addition to LOIO.
- The materials consultant is independent of Polaron; C1 asks them only for image-based judgements (consistency of the stated identities, preparation damage vs real damage, scale plausibility, which of the 10 pre-registered measurements matter).

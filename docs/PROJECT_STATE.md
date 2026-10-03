# Project State

Updated: 2026-10-03, ~T+8h (Devin cloud session 1)
Phase: v1 S1-S5 implemented and run on all 31 images; PR #1 `v1 S1-S5 reality check` open on `stage/s1-s5-reality-check`, awaiting review and consultant checkpoint C1
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

Record for each entry:

- completed work;
- evidence and source links;
- decisions and rejected alternatives;
- reviewer verdict;
- unresolved risks;
- exact next action.

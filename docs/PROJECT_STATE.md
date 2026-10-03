# Project State

Updated: 2026-10-03, T+1h (Devin)
Phase: event started; FRAMEWORK.md v2 written after Polaron kickoff; awaiting team review
Submission repository: `code/AIxScience_Msia` cloned from github.com/alvinbong03/AIxScience_Msia, empty (no commits)

## Current decision

The technical sequence is not fixed. The team will select the approach after inspecting the released dataset.

Draft plan: `FRAMEWORK.md` (24 h clock, lanes, default stack, decision tree, Modal and Devin challenge plans, open decisions).
Research audit: `Log/2026-10-03_ideation_verification.md`. All cited sources and licences verified; two corrections added (alibi-detect is BSL 1.1; Polaron founders = ImageRep authors' group).

Proposed Devin-challenge paper: ImageRep (Dahari et al., Advanced Science; code BSD-3). Pending team confirmation.

Agent context remaining (Devin Desktop, this session): unknown (tool does not expose it).

## Workstreams

| Workstream | Owner | Status | Reviewer | Context remaining |
|---|---|---|---|---|
| Dataset and acquisition audit | Unassigned | Not started | Required | Unknown |
| KPI and segmentation lane | Unassigned | Not started | Required | Unknown |
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

Still unknown: pixel size confirmation; identity of the bright phase; whether a baseline batch is named; whether held-back images may come from a new batch.

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

Record:

- completed work;
- evidence and source links;
- decisions and rejected alternatives;
- reviewer verdict;
- unresolved risks;
- exact next action.

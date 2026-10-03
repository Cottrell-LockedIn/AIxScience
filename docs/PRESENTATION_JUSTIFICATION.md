# Presentation justification note

Status: working note (T+1 day). Every methodological choice we will be asked to defend on stage, with the one-line justification and the evidence that backs it. Numbers are from PR #1 outputs (31 images, 93 TIFFs, config hash `1bec114301c3`) unless marked TODO.

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

## Figures / numbers still needed for the deck (TODO)
- LOIO vs LOGO accuracy, with and without artefact covariates (S7).
- Feature stability table: bootstrap rank stability and threshold-perturbation sensitivity for the 10 features (validation harness, child session).
- Per-feature confound screen: correlation with noise/sharpness/group (validation harness).
- Which of the 10 features survive -> the kept list, with the drop reasons.
- Reference LOO plot with the 3 flagged Batch_3 images and their overlays.
- One representative crop per batch with mask overlay, provenance tag in the caption.

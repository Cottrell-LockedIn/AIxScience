# Track 4 Framework (code and implementation plan)

Status: v4, 2026-10-03, T+5h (parallel-agent plan added; v3 at T+2h, v2 at T+1h) after the Polaron kickoff discussion (`READ/Polaron Kickoff Discussion.md`). Not frozen. Evidence and team judgment override this document (`AGENTS.md`).

Feature definitions and suggestions for review: `READ/Feature Details and Suggestions.md`. Research audit: `Log/2026-10-03_ideation_verification.md`.

## 00. For any AI agent picking this up: read this block first

### The workflow in plain words

```
Download images -> cut into tiles -> measure each tile -> compare batches -> explain the verdict
  (no model)       (no model)        two kinds of measurement    (statistics)    (JSON + one screen)
                                      |
                                      |- A. Classical: multi-Otsu threshold on the BSE channel into
                                      |     pore / graphite / bright high-Z particles -> fractions, sizes,
                                      |     dispersion. NO training, NO labels. scikit-image only.
                                      |
                                      '- B. Frozen model: DINOv2 ViT-S/14 on each tile -> one embedding
                                            vector per tile. NO training. Inference only (Modal job).
```

The **baseline pipeline** (v1) has no data labelling and no neural-network training; its only fitted object is a scikit-learn logistic regression (W2) that predicts *which batch* a tile came from; its labels are the batch folder names, which are free. Segmentation thresholds come from multi-Otsu (unsupervised). Statistics are numpy. The **ambitious track** (Section 12) adds trained models on top of v1; each must beat v1 under leave-one-image-out to be adopted.

Order of work: build data (S1-S2) -> measure (S3-S5, in parallel) -> compare and classify (S6-S7) -> verdict and screen (S8-S9) -> frozen run on held-back images (S10). Stage table in Section 2b.

### Hard rules (violating any of these invalidates the result)

1. The **image** (field of view, 8-char id) is the independent unit. Tiles from one image never appear on both sides of any split, permutation or bootstrap. All cross-validation is leave-one-image-out.
2. Chemistry only as stated by Polaron: class 2 = silicon, class 1 = graphite, class 0 = void/pore, always tagged "stated by Polaron, not image-verified" (Si vs SiOx indistinguishable in BSE; binder/additive lumped). Nothing beyond that without EDS or labels. Say "pixel-domain" units until the 25 nm/px pixel size is confirmed.
3. Artefacts (curtaining, edge charging, detector type ETD vs SE) are **measured and reported**, never silently removed. Every KPI is computed on raw images; destriped variants are a sensitivity check.
4. Report `n` images on every statistic. No calibrated probabilities, no conformal claims, no p-values without the effect size and null band next to them.
5. `investigate` is a valid, first-class outcome. Conflicting evidence or acquisition drift routes there, with the reason stated.
6. Held-back images are quarantined on arrival (`data/heldout/`) and processed exactly once with the frozen `configs/v1.yaml` after `git tag v1-frozen`. Nothing is tuned on them.
7. Training is allowed (Section 12) only with: a frozen non-trained baseline to beat, leave-one-image-out validation, and the artefact ablation run on the trained model too. No training on scraped paper figures. No VLM looking at pixels to diagnose. No alibi-detect (BSL licence). No DINOv3 (custom licence).
8. Every stage writes a file with a fixed name (Section 2b). Agents hand off files, not function calls.
9. Any change after the freeze is labelled exploratory and cannot alter `results/v1/heldout.json`.
10. Cite the method for each layer from `READ/Method Evidence for Layers.md` in the README; keep licences and attributions.

### Models, libraries, skills and connectors to use

| Purpose | Use | Notes |
|---|---|---|
| Frozen embeddings | `torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14')`, pin the commit | Apache-2.0. Fallback: torchvision ResNet-50 |
| Segmentation + KPIs | scikit-image (`threshold_multiotsu`, `label`, `regionprops`, `denoise_nl_means`), OpenCV | no model |
| Two-point correlation | `representativity.core.radial_tpc` from ImageRep (BSD-3, `pip install -e` at a pinned commit) | also the Devin challenge target |
| Statistics | own numpy: energy distance, MMD (RBF, median heuristic), image-level permutation, hierarchical bootstrap | ~60 lines total |
| Classifier | scikit-learn `LogisticRegression` (KPIs) and a linear head on embeddings | LOIO = 31 fits |
| Destriping check | `pywt` wavelet + FFT damping (Munch 2009) | sensitivity only |
| Optional heatmaps | kNN distance to a reference memory bank (own code or Anomalib, Apache-2.0) | visual layer only |
| Optional physics | TauFactor (tldr-group) 2D tortuosity | after W1, W2, screen are stable |
| Large TIFF I/O | `tifffile` + `imagecodecs` (LZW); read channel 0; crop 8 px borders | |
| Compute | Modal L4 for S5 via `.map`; everything else local CPU | `modal skills install` puts Modal's agent skill in `.agents/skills/` for Devin and Codex |
| Agent config | `AGENTS.md` at repo root; `.agents/skills/`; optional `.devin/mcp_config.json` | `gh` CLI is enough for GitHub |
| UI | Streamlit reading `results/v1/*.json` | one screen |

### Where this project stands out (spend extra effort here, in this order)

1. **Artefact ablation**: W2 trained with and without artefact covariates; the delta is shown on the first screen. This answers Polaron's "artefact vs real microstructure" question quantitatively.
2. **High-Z particle KPIs with spatial dispersion**: fraction, size distribution, nearest-neighbour distance, cluster size, top-to-bottom gradient across the coating. "Supplier B's high-Z particles are agglomerated" beats "embedding distance 0.37".
3. **Leakage-free honesty**: LOIO, `n` on screen, null band from a batch against itself, `investigate` as an outcome.
4. **Frozen-hash protocol** for the held-back images.
5. **Devin + ImageRep**: reproduce the judges' own group's paper and extend it to batch-level uncertainty.

Do not over-invest in: UI beyond one screen, Modal beyond the measured timing table and an optional endpoint, more than two embedding backbones.

Expected field: most teams will do pretrained features -> classifier -> accuracy, often with tile-level leakage. The baseline model is a commodity; the differentiation is being right about statistics, artefacts and explanation.

## 0. What we now know, and what it forces

Dataset inspected at T+1.5 (`READ/Dataset First Look.md`):

- 3 batches: 7, 7 and 17 fields of view; each field has 3 co-registered detector channels (BSE, Inlens, ETD or SE); ~92 TIFFs, 7000 px wide, 1904 to 2316 px tall, ~1.7 GB total, publicly downloadable.
- Material looks like a **graphite anode with a brighter high-Z particle phase** (likely Si/SiOx; confirm). BSE gives clean three-class contrast (pore / graphite / high-Z). Inlens shows curtaining and edge charging.
- Pixel size probably 25 nm (TIFF tag; confirm). No databars. Need `imagecodecs` to read.
- No good/bad labels, only batch membership; 3 held-back **images** arrive as the test.
- Polaron's two asks: (1) classify batches and explain the distinguishing features before the held-back images arrive; (2) separate artefacts from real microstructure.
- Questions to ask: `READ/Questions for Polaron.md`. Method citations for each layer: `READ/Method Evidence for Layers.md`.

Team priority: **one or two workflows, wow factor, then completion, then robustness.**

Two workflows, everything else is a layer:

- **W1 Batch comparison (unsupervised).** Reference null from one batch, pairwise batch distances on KPIs and embeddings, within-batch consistency ranking, per-image out-of-bounds flags. -> Feature 2, feeds Feature 4.
- **W2 Batch classifier (supervised on batch membership).** KPI + embedding features, leave-one-image-out, top drivers, artefact-ablation check. -> Feature 1, feeds Feature 4.

Traceability (Feature 3) is a JSON schema that both workflows write into. Verdict screen (Feature 4) renders it.

## 1. Clock (24 h assumed; now T+1; held-back images ~T+8)

| Window | Goal | Gate |
|---|---|---|
| T+1 to T+2.5 | Phase A: data audit, tiling, artefact covariates | `DATA_AUDIT.md`; tile cache on disk; per-image covariate table |
| T+2.5 to T+6 | Phase B: W1 end to end on 3 batches (2 KPIs + embeddings + null) | pairwise distance matrix + consistency ranking + first verdict JSON |
| T+6 to T+8 | Phase C: W2 leave-one-image-out classifier + drivers; KPI set to 3-5 | classifier accuracy with and without artefact covariates; drivers table |
| ~T+8 | Held-back images arrive | **Quarantine** in `data/heldout/`; nobody opens them |
| T+8 to T+11 | Phase D: Modal run, verdict JSON schema complete, Streamlit skeleton, review | reviewer verdict on W1+W2 |
| T+11 (latest T+14) | **Freeze v1**: tag, hash, config | run v1 once on the 3 held-back images; save `results/v1/heldout.json` |
| T+11 to T+18 | Phase E: verdict screen polish, Devin/ImageRep, optional TauFactor, exploratory v2 | demo runs offline from cache |
| T+18 to T+22 | Phase F: README, attribution, 90 s pitch, 2 min recording | rehearsed twice |
| T+22 to T+24 | Buffer. No new features. | submitted |

Rules: hourly 5-minute stand-up and `PROJECT_STATE.md` update; experiments over 20 min need a stop condition; a lane more than 1 h behind cuts scope.

## 2. Lanes (team of 4)

| Person | Lane | Owns | Review partner |
|---|---|---|---|
| P1 | Data, statistics, W1 null and distances; Devin/ImageRep after freeze | `audit/`, `stats/`, `results/` | P3 |
| P2 | Segmentation and KPIs; artefact covariates | `kpi/`, `artefacts/` | P4 |
| P3 | Embeddings, W2 classifier, Modal | `features/`, `classify/`, `modal_app.py` | P1 |
| P4 | Verdict JSON schema, Streamlit screen, integration, README, pitch | `schema/`, `app/`, `README.md` | P2 |

Agents: Devin and Codex both read `AGENTS.md` and `.agents/skills/`. Run `modal skills install` once in the repo so both agents get Modal guidance. Each person works on a short-lived branch; P4 merges to `main`.

## 2b. Task division: what is trained, what is inference, what runs where

There is very little "training" in this project. Most compute is deterministic feature extraction (inference) followed by cheap statistics. That is deliberate: it keeps everything explainable and freezable.

| Stage | Type | Input -> Output | Runs on | Owner | Cadence |
|---|---|---|---|---|---|
| S1 Download + inventory | I/O | Drive IDs -> `data/raw/<batch>/<id>_<det>.tif`, `inventory.csv` with hashes | local | P1 | once |
| S2 Tiling + previews | preprocessing | each TIFF -> 512 px tiles (channel 0 only, 8 px border crop), tile index, 4x downsampled preview | local CPU | P1 | once per config |
| S3 Artefact covariates | inference (deterministic) | Inlens + BSE tiles -> curtaining score, edge-charging score, noise, sharpness, intensity stats per tile and image | local CPU | P2 | once per config |
| S4 Segmentation + KPIs | inference (deterministic, unsupervised) | BSE tiles -> 3-class mask -> phase fractions, high-Z particle size/count/dispersion, flake size/aspect, pore size, TPC length; +/-10% threshold variants | local CPU (Modal `.map` optional if slow) | P2 | once per config |
| S5 Embeddings | inference (frozen model) | tiles -> DINOv2 ViT-S/14 vectors per tile, mean per image | **Modal L4** (`.map`, weights in Volume); local CPU fallback for a subset | P3 | once per backbone |
| S6 Reference null + distances (W1) | statistics (no training) | per-image KPI + embedding tables -> null bands, pairwise batch distances, consistency ranking, per-image flags | local CPU | P1 | seconds; rerun freely |
| S7 Batch classifier (W2) | **training** (light) | per-tile features + batch label -> logistic regression / random forest; LOIO = 31 fits; with and without artefact covariates | local CPU (Modal optional for a backbone matrix) | P3 | minutes |
| S8 Verdict assembly | rules | S3 + S6 + S7 -> one JSON per batch and per image (Feature 3 schema) | local | P4 | seconds |
| S9 Screen | UI | `results/v1/*.json` -> Streamlit | local | P4 | continuous |
| S10 Held-back inference | inference only, frozen | 3 TIFFs -> S2..S8 with `configs/v1.yaml`, no refits except LOIO models already trained on all 31 | local (+ Modal for S5) | P1 runs, P4 witnesses | once |
| S11 Devin / ImageRep | reproduction + extension | synthetic blobs + our high-Z and pore masks -> coverage table, per-image phase-fraction CI | Devin session, CPU | P1 after freeze | once |

Hand-offs are files, not function calls, so lanes can work in parallel from T+2:

- P1 publishes `data/tiles/index.parquet` (tile id, image id, batch, detector, x, y) by ~T+2.5. Until then P2 and P3 develop on the three sample images already downloaded.
- P2 publishes `results/kpi_per_tile.parquet` and `results/artefacts_per_tile.parquet`.
- P3 publishes `results/emb_per_tile.npy` + `results/emb_index.parquet`, later `results/w2_loio.json`.
- P1 consumes all three and publishes `results/w1_distances.json`, `results/null_bands.json`.
- P4 owns `schema/verdict.schema.json` from T+2 so everyone writes to the same shape.

What is **not** trained: the segmentation (thresholds, unsupervised), the embeddings (frozen), the statistics. The only fitted objects are the W2 classifier weights and the threshold values chosen by multi-Otsu; both are recorded in the freeze.

Modal usage, concretely: S5 is the measured workload (time and cost vs local CPU). Optional: S4 via `.map` over images, S7 backbone matrix, and a deployed endpoint wrapping S10. Budget $150; expected spend well under $20.

## 3. Repository layout (proposed)

```
AIxScience_Msia/
  AGENTS.md                 # copy of the shared rules, trimmed
  README.md
  pyproject.toml / requirements.txt (pinned)
  configs/v1.yaml           # tile size, thresholds, model revision, seeds
  data/                     # git-ignored: raw/, tiles/, heldout/
  src/qc/
    audit.py                # inventory, hashes, metadata, covariates
    tiles.py                # out-of-core tiling of large images, overlay masks
    artefacts.py            # curtaining score (FFT vertical-stripe energy), edge brightening
    segment.py              # Otsu/multi-Otsu + morphology + watershed
    kpi.py                  # KPI definitions, units, threshold-sensitivity
    features.py             # DINOv2/ResNet embeddings per tile, image aggregation
    stats.py                # null construction, energy distance, MMD, image-level permutation, effect sizes
    classify.py             # W2: LOIO classifier, drivers, artefact ablation
    verdict.py              # combine evidence -> verdict JSON (Feature 3 schema)
    cli.py                  # python -m qc audit | run | heldout
  modal_app.py              # features.py on Modal with .map, Volume for weights
  app/streamlit_app.py      # Feature 4 screen, reads results/*.json
  results/v1/               # committed JSON/CSV outputs, never raw data
  devin/imagerep/           # Devin challenge reproduction + extension
```

## 4. Phase details

### Phase A: audit, tiling, artefacts (T+1 to T+2.5) - P1 + P2

- Inventory: files per batch, dimensions, bit depth, hashes, any metadata (pixel size, voltage, detector). Ask Polaron for pixel scale if absent; log as organiser-provided.
- Tiling (`tiles.py`): read large TIFFs with `tifffile` memmap; fixed tile size (start 512 px, decide after seeing feature sizes); stride = tile; drop tiles overlapping borders/databars; store tile -> image -> batch index. Keep a 2048-px downsampled preview per image.
- Artefact covariates (`artefacts.py`), per tile and per image: curtaining score = power along the vertical spatial-frequency axis divided by total power in a band; edge-brightening = mean intensity of outer 5% band minus centre; plus mean, std, percentiles, Laplacian variance (sharpness), noise estimate.
- Look at 10 tiles per batch at full resolution; write what a materials scientist would measure. Decide whether thresholding separates pore / particle / crack.

Gate: covariate table plotted by batch. If batches already separate on covariates, state it in the audit: this is the artefact-vs-material question made concrete.

### Phase B: W1 end to end (T+2.5 to T+6) - P1 stats, P2 KPIs, P3 embeddings

- KPIs first two, on the BSE channel: (a) three-class phase fractions (pore / graphite / high-Z particle phase) by multi-Otsu after denoising, (b) high-Z particle size distribution and count density (connected components, equivalent diameter). Then flake size/aspect ratio, pore size, crack-like fraction, TPC characteristic length. Each KPI: definition, units (px until pixel size confirmed), +/-10% threshold perturbation, 5-tile manual check.
- Embeddings: DINOv2 ViT-S/14 (fixed torch.hub revision) on tiles; one vector per tile, mean per image. Benchmark one batch locally, then Modal L4 with `.map`; log time and cost.
- Statistics (`stats.py`): choose reference batch (Polaron's choice if given; otherwise the batch with the most images, and report the alternative choices). Null = repeated image-level half-splits of the reference. Pairwise batch distances: standardised KPI median shifts; energy distance and MMD on embeddings with image-level permutation. Consistency score per batch = within-batch spread of per-image KPIs and mean pairwise embedding distance.
- Leakage rule: tiles from one image stay on one side of every split.

Gate: distance matrix, consistency ranking, one verdict JSON for one batch with a reason sentence.

### Phase C: W2 classifier and full KPI set (T+6 to T+8) - P3 classifier, P2 KPIs

- Features per tile: KPIs + artefact covariates + embedding. Models: logistic regression on KPIs (fully explainable) and a linear head on embeddings. Leave-one-image-out; aggregate tile predictions to image.
- Artefact ablation: train with and without artefact covariates; report both. If performance collapses without them, say so on screen.
- Drivers: coefficients / permutation importance on the KPI model; nearest reference tiles for the embedding model.
- KPIs to 3-5. Drop any KPI whose threshold-sensitivity change exceeds the batch effect it detects.
- Write `DECISION_RULES.md`: bands from the null (e.g. within 95th percentile -> within bounds; beyond 99th with large effect in most images -> outside bounds; otherwise investigate), aggregation (median, 90th percentile, prevalence), abstention conditions, what each uncertainty number means.

### Phase D: Modal, schema, review, freeze (T+8 to T+11)

- Held-back images quarantined. Single entry point `python -m qc run --config configs/v1.yaml` regenerates `results/v1/`.
- Modal: all batches' embeddings via `.map`; weights in a Volume; `@modal.enter`; timeouts; `max_containers` capped; cost log. Optional: `modal deploy` a web endpoint returning verdict JSON.
- Verdict JSON (Feature 3): identifiers and hashes, acquisition record, pipeline record (commit, config hash, lock hash, timestamp, frozen flag), evidence record (drivers, effect sizes, band positions, tile IDs), routing (supplier / microscopy team / expert review), next action.
- Independent review: leakage, units, phase naming, overconfident wording, abstention paths.
- Freeze: `git tag v1-frozen`; record in `PROJECT_STATE.md`; then `python -m qc heldout` once; save `results/v1/heldout.json` (per image: predicted batch, confidence, nearest-batch distances, within/outside bounds, drivers, artefact covariates). Later changes are exploratory and cannot alter this file.

### Phase E: screen, Devin, optional physics (T+11 to T+18)

- P4: Streamlit screen (`BUILD/Product and Demo Toolkit.md`): batch table with consistency ranking and verdicts -> selected batch: artefact panel, KPI shifts vs band, embedding distance vs null, prevalence, representative crops with masks, uncertainty panel, traceability stamp -> held-back images tab with per-image prediction and reason.
- P1: Devin challenge on ImageRep (`RESEARCH/Devin Challenge Paper Comparison.md`): reproduce coverage result, extend to batch-level phase-fraction uncertainty, apply to the pore fraction here where assumptions hold.
- Optional wow if W1+W2+screen are stable: TauFactor 2D tortuosity per batch from the pore mask (indicative only, say so).

### Phase F: submission (T+18 to T+22)

README (approach, KPIs, statistics, results on 3 batches and 3 held-back images, artefact analysis, uncertainty, limitations, Modal numbers, Devin workflow, licences). 90 s live flow; 2 min recording from cache; no data or secrets in Git.

## 5. Default stack

| Need | Default | Fallback |
|---|---|---|
| Env | Python 3.11, `uv`, pinned requirements | pip |
| Large image I/O | `tifffile` (memmap), `zarr` if needed | OpenCV |
| Segmentation | multi-Otsu + morphology + watershed (scikit-image, OpenCV) | micro-sam (MIT) only if particles are clean and time remains |
| Artefacts | numpy FFT stripe score, border-gradient score | none |
| Embeddings | DINOv2 ViT-S/14, Apache-2.0, fixed revision | torchvision ResNet-50 |
| Statistics | own numpy: energy distance, MMD, image-level permutation, hierarchical bootstrap | `scipy.stats.energy_distance` per KPI |
| Classifier | scikit-learn logistic regression / random forest | - |
| Anomaly map (visual only) | PatchCore-style kNN to reference memory bank, own ~40 lines or Anomalib (Apache-2.0) | skip |
| Physics (optional) | TauFactor (tldr-group) | skip |
| Compute | Modal L4 for embeddings, CPU locally for everything else; budget $150 available, target under $20 | local CPU |
| UI | Streamlit reading cached JSON | static HTML |

Not used: alibi-detect (BSL 1.1), DINOv3 (custom licence), KontElPro (AGPL), MatSAM (no licence), any fine-tuning, calibrated probabilities, conformal guarantees.

## 6. Branches for surprises

- **Very few images per batch (<= 4)**: permutation p-values are nearly meaningless; report effect sizes with image-level spread and say "n = 4 images"; consistency ranking still works; W2 LOIO still works but report per-image outcomes, not a percentage.
- **No pixel scale**: pixel-domain KPIs, label as such; compare only equal-magnification images.
- **Batches separate on artefact covariates alone**: headline finding is "difference is partly acquisition"; W2 ablation result goes on the first screen; verdict `investigate` with routing to the microscopy team.
- **Thresholding fails**: keep texture (GLCM, TPC correlation length) KPIs and embeddings; never name phases.
- **No baseline named**: pairwise matrix + consistency ranking is the product; "reference" is a user-selectable dropdown in the screen.
- **Held-back image matches none of the batches**: predicted "none / investigate" is a valid and honest output; show nearest-batch distances.

## 7. Challenge 2: Devin (ImageRep)

Reproduce the 95% phase-fraction error-bound coverage on synthetic `binary_blobs` sub-images using the repo's shipped statistics; compare to `validation.json`. Extend to batch-level uncertainty and apply to the pore fraction here. Record prompts, session links, pinned commit, deviations. Detail: `RESEARCH/Devin Challenge Paper Comparison.md`.

## 8. Challenge 1: Modal

Minimum: embedding extraction for all tiles on Modal with wall time and cost versus local CPU. Better: small model matrix (ResNet-50, DINOv2-S, DINOv2-B; two tile sizes) via `.map`. Ambitious and cheap: deployed endpoint returning verdict JSON; Streamlit calls it when online, cache when offline. Guardrails: spend limit, `max_containers`, timeouts, cost log, no tokens in Git.

## 9. Judging map

| Criterion | Evidence |
|---|---|
| Material KPIs | 3-5 KPIs with units, sensitivity, manual check, crops |
| Accuracy on held-back images | `results/v1/heldout.json` from the frozen tag, with confidence and abstention |
| Interpretability | drivers per verdict; W2 coefficients; artefact ablation; crops |
| Honest uncertainty | n images stated; sampling / segmentation / margin split; `investigate` is first class |
| Usability | one screen, routing to stakeholder, next action, offline |
| Modal | time/cost table, optional endpoint |
| Devin | ImageRep reproduction + batch extension, documented workflow |

## 10. Open decisions

1. Names for P1-P4.
2. Reference batch: ask Polaron whether one batch is the "approved baseline". If not, pairwise. (Batch_3 has 17 images vs 7 and 7; it is the statistically strongest candidate for a reference if Polaron has no preference.)
3. Verdict wording on screen: `within bounds / investigate / outside bounds` vs `accept / investigate / reject`. Recommendation: the former, with accept/reject in parentheses.
4. Tile size: graphite flakes are 400 to 600 px, so 512 px tiles contain ~1 flake. Suggest 1024 px tiles for KPIs (stride 512) and 518 px for DINOv2 input (resize from 1024). Decide at T+2.5.
5. Devin paper: ImageRep recommended; team to confirm.
6. Freeze time: T+11 target, T+14 latest.
7. Whether raw data may be committed: assume no.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Few images -> weak statistics | effect sizes + consistency + honest n; LOIO per image |
| Classifier reads the ion beam | artefact ablation is a required output |
| GB images choke laptops | memmap tiling in Phase A; Modal for embeddings |
| Three held-back images give a noisy "accuracy" | confidence + abstention + nearest-batch distances per image |
| Scope creep into a third model | two workflows rule; P4 enforces at stand-ups |
| Venue internet | cached JSON, recording early |

## 12. Ambitious track: parallel agents, trained models, experiment swarm

Resources (confirmed by team): Devin with up to 100 concurrent subagents, $200 Devin credit, $150 Modal credit, ~19 h remaining. Humans: 4. Goal: best result and strongest wow without breaking the hard rules in Section 00.

### 12.1 Principle: v1 first, then swarm against it

Nothing in this section starts until **v1 (Sections 2b, 4) produces `results/v1/` end to end** on all 31 images, target T+6. v1 is the frozen baseline every trained model must beat. Agents working in parallel before v1 exists will produce incompatible files and nobody will be able to judge their work.

From T+6 onward the human team becomes **reviewers and integrators**; agents do the experiments. Each human owns a swarm:

| Human | Swarm | Agents (approx) |
|---|---|---|
| P1 | Statistics + ImageRep/Devin challenge + experiment aggregator | 8 |
| P2 | Segmentation training + KPI expansion + labelling QA | 15 |
| P3 | Embedding / classifier experiments on Modal | 25 |
| P4 | Screen, schema, tests, README, pitch assets | 10 |

Spare capacity is reserved for re-runs and the held-back protocol. Do not launch 100 agents for the sake of it; launch the number whose outputs one human can review in the next hour.

### 12.2 Experiment registry (how agents coordinate without colliding)

- One agent = one experiment = one config file `experiments/<swarm>/<id>.yaml` = one output folder `results/experiments/<id>/` containing `metrics.json`, `config.yaml`, `git_sha.txt`, `notes.md`.
- Agents **never** edit `src/qc/` core modules concurrently. Shared code changes go through the owning human on a branch; experiments subclass or wrap via config.
- `metrics.json` has a fixed schema: `loio_image_accuracy`, `loio_image_accuracy_no_artefact_covariates`, `loio_image_accuracy_destriped_input`, `per_batch_recall`, `w1_energy_distance_matrix`, `null_band_95`, `kpi_iou` (if segmentation), `wall_time_s`, `modal_cost_usd`, `n_images`.
- One aggregator agent (P1's swarm) regenerates `results/LEADERBOARD.md` every 30 min and flags any experiment that violates a hard rule (e.g. tile-level split detected by checking that every image id appears in exactly one fold).
- Selection rule, declared now, before results exist: a trained model replaces its v1 counterpart only if it improves LOIO image-level accuracy by at least 1 image (of 31) **and** its accuracy drop under artefact ablation and under destriped input is no worse than v1's. Ties go to the simpler model.

### 12.3 Swarm A (P2): segmentation that is actually better

1. **Pseudo-label generation** (agents): run v1 multi-Otsu on 60 crops of 512 px, stratified across batches, detectors and image positions; save masks.
2. **Human correction** (P2 + any free human, napari or GIMP): correct the 60 masks. Budget 90 min total across people. This is the only human labelling in the project. Record who labelled which crop.
3. **Train in parallel** (agents on Modal, one config each): random forest on multiscale features; small U-Net (4 levels, ~1M params) from scratch; U-Net with a frozen DINOv2 encoder and light decoder (the architecture of arXiv 2608.27162). Inputs: BSE only; BSE + Inlens stacked; all three channels. Loss: cross-entropy with class weights. Split by **image id**: 45 crops train, 15 crops test, no image shared.
4. **Metrics:** IoU per class on the 15 test crops; and downstream: do the KPIs from the new masks separate batches more cleanly (W1 null band ratio) without widening threshold sensitivity?
5. **KPI expansion agents** (CPU, no training): per-image high-Z dispersion (nearest-neighbour distance, Ripley's K, cluster size), flake orientation (structure tensor), coating porosity gradient top to bottom, crack-like fraction inside flakes (Inlens), TPC characteristic length per phase. Each agent delivers one KPI with definition, units, sensitivity and a one-figure sanity plot.

### 12.4 Swarm B (P3): embeddings and the deep classifier

Run as a matrix, one agent per cell, on Modal L4/A10 (`.map` over tiles, weights in a Volume, `max_containers` capped at 20, timeout 20 min per job):

- Backbones: DINOv2 ViT-S/14, ViT-B/14, ViT-L/14; ResNet-50; ConvNeXt-T. All frozen, pinned revisions.
- Inputs: BSE; Inlens; ETD/SE; 3-channel stack; destriped variants of each.
- Tile sizes: 512, 1024 (resized to model input).
- Pooling: CLS token; mean patch; mean + std patch; attention-pooled probe (trained, LOIO).
- Heads: logistic regression; linear probe on patch tokens; small MLP.
- Two-sample tests: energy distance, MMD RBF, learned-kernel MMD (trained, LOIO folds), classifier two-sample test.

Ambitious cells (3 to 5 agents, each with an A10 for up to 2 h):

- **Domain-adapted DINOv2**: continue self-supervised training (DINO objective, or simpler: SimCLR on our ~3000 tiles) for 30 to 60 min; evaluate as a frozen backbone through the same matrix. Adopt only per the selection rule.
- **Deep batch classifier with saliency**: fine-tune the last block + head of DINOv2-S on tiles, LOIO at image level (31 fits, one per fold, parallel on Modal). Output attention/Grad-CAM maps per tile. Then the saliency test: overlay saliency on the curtaining-score map; report the fraction of saliency mass that falls on stripe regions. If the model is looking at stripes, say so on screen. This is the strongest visual answer to Polaron's artefact question.
- **Learned-kernel MMD** between batches with image-level permutation, to show whether a learned metric agrees with the KPI story.

Every cell reports the full `metrics.json`, including cost. The leaderboard is a deliverable in itself: "we evaluated N configurations under identical image-level validation; here is why we chose this one".

### 12.5 Swarm C (P1): statistics, uncertainty, Devin challenge

- Null bands: pseudo-batch splits for every batch as reference, not only one; report sensitivity of verdicts to the reference choice.
- Hierarchical bootstrap of every KPI (image -> tile) with CI per batch.
- ImageRep per-image CI on high-Z and pore fractions; propagate to batch means (the Devin challenge extension). Reproduction script and report under `devin/imagerep/`.
- "Most consistent supplier" ranking with uncertainty.
- Aggregator agent for the leaderboard and rule-violation checks.
- Held-back protocol dry run on 3 random training images treated as unknown, to make sure `python -m qc heldout` works before the real ones arrive.

### 12.6 Swarm D (P4): product

- Streamlit screen from `results/v1/*.json` and `results/LEADERBOARD.md`; a "model card" panel per adopted model.
- Verdict JSON schema with validation (`jsonschema`); tests that every result file validates.
- README sections written as results arrive; figure generation scripts.
- 90 s script, 2 min recording, Modal timing table, Devin usage log (session IDs, prompts, what humans corrected).
- Optional endpoint: `modal deploy` wrapping `qc heldout` and returning verdict JSON; the screen calls it when online.

### 12.7 Freeze and the two-pipeline story

- v1 is frozen at T+11 as planned and run on the held-back images once. That is the guaranteed, fully explainable result.
- If the swarm produces an adopted v2 by T+16 (selection rule met, reviewed by a human who did not author it), v2 is frozen with its own tag and run on the held-back images once. Both verdicts are shown side by side with their validation evidence. If they disagree, the verdict is `investigate` and the disagreement is the finding.
- Nothing after T+16 touches the held-back files.

### 12.8 Budget guardrails

- Modal: spend limit set in the dashboard at $120; `max_containers=20`; GPU jobs time-limited; every job logs cost to `results/modal_runs.csv`. Expected: matrix ~$15 to $30, SSL adaptation and LOIO fine-tunes ~$20 to $40.
- Devin: one experiment per agent, bounded prompt, explicit output files; kill agents that exceed 45 min without writing `metrics.json`.
- Humans: no human runs an experiment by hand after T+6; humans label (Swarm A step 2), review, integrate, present.

### 12.9 Where the wow comes from in this track

1. The saliency-vs-stripes figure: a deep model's attention overlaid on the curtaining map, with the number "x% of the batch signal sits on ion-beam artefacts".
2. The leaderboard: dozens of configurations under one honest validation, with the simple KPI model holding its own (or not) against deep models, and the reasons.
3. Two frozen pipelines, two sealed verdicts on the held-back images, shown together.
4. Dispersion KPIs with hierarchical confidence intervals in the sponsor's own vocabulary.
5. ImageRep reproduced and extended, documented as an agent workflow.

If any of these does not materialise by T+16, it is dropped from the pitch without comment. The v1 story stands on its own.

## 13. Generalisation and robustness protocol

Why this section exists: the track brief says the test is "a brand-new unseen **batch**" dropped at ~T+8 to "test generalization", and accuracy on it is a judged criterion. Polaron's kickoff said "three held-back images". Both can be true: the three images may come from a **fourth batch** we have never seen. The pipeline must therefore do well on two different questions, and we do not know which one will be asked:

- Q-closed: "which of Batch 1/2/3 does this image belong to?" (W2 classifier)
- Q-open: "is this image consistent with the reference, or is it something new, and why?" (W1 distances + null band)

Rule: **every held-back image gets both answers**, and the open-set answer takes precedence when the two disagree.

### 13.1 Open-set by construction

- Per image: distance to each batch's distribution (KPI effect sizes and embedding energy distance) plus the reference null band. If the image is outside the band for **all** batches, the verdict is `matches none of the known batches -> investigate`, with the nearest batch and the driving KPIs listed. A softmax from W2 is never shown alone; it is shown next to the distances.
- Calibrate "new batch" detection before the drop with **leave-one-batch-out**: hold out Batch k entirely, build the null from the remaining two, run every image of Batch k as if unseen, record how often it is flagged as "none" vs assigned to a wrong batch. Report the three numbers. This is the only honest estimate we can give of behaviour on a fourth batch.

### 13.2 No test-time dependence on batch statistics

- Per-image preprocessing only: intensity normalisation, thresholds, denoising parameters are computed from the image itself or fixed in `configs/v1.yaml`. Never from "the batch this image came in with"; a single held-back image has no batch.
- The pipeline must run on a **single image with any one channel missing** (Polaron may release only BSE). Test this in the dry run (Section 12.5).

### 13.3 Acquisition-invariance test (the robustness panel)

Before freezing, perturb every training image with synthetic acquisition changes and re-run the verdict. Report how many images change verdict or predicted batch under each perturbation:

| Perturbation | Range | What it simulates |
|---|---|---|
| Gamma / brightness / contrast | gamma 0.8 to 1.25, offset +/-10 grey levels | detector gain, session drift |
| Gaussian + Poisson noise | sigma 2 to 8 grey levels | dwell time, beam current |
| Blur | sigma 0.5 to 1.5 px | focus, charging |
| Synthetic curtaining | vertical stripes of amplitude 5 to 20 grey levels | ion-beam milling |
| Downscale and upscale | 0.8x to 1.25x | magnification change |
| Crop position | random 80% field of view | sampling location |

A KPI or model that flips verdicts under gamma 0.9 is reading the microscope. This panel is run for v1 and for every candidate in the Section 12 leaderboard; `metrics.json` gains `robustness_flip_rate` per perturbation, and the selection rule in 12.2 adds: a candidate may not have a worse worst-case flip rate than v1.

### 13.4 Model choices that favour generalisation

- Prefer KPIs defined by **ratios and shapes** (phase fraction, particle size, aspect ratio, nearest-neighbour distance, TPC length) over absolute intensities; they are invariant to gain by construction once segmentation is right.
- Segmentation thresholds per tile (adapts to local drift) with the threshold values logged as covariates (so drift is visible, not hidden).
- Embeddings: compute on per-tile standardised intensity; evaluate CLS vs mean-patch pooling on the robustness panel, not only on LOIO accuracy.
- Trained models (Section 12): training-time augmentation uses the same perturbation table; LOIO accuracy without augmentation is reported alongside so the effect is visible.
- Ensembles are allowed only as "KPI model + embedding model agree / disagree"; disagreement routes to `investigate`.

### 13.5 What we say on screen for a held-back image

1. Nearest known batch and distance, with the null band.
2. Closed-set prediction and confidence (W2), labelled "assumes the image is from one of the three known batches".
3. Open-set flag: within / outside all known batches.
4. Top three drivers (KPIs with effect sizes) and the artefact covariates for that image compared to the training range.
5. Robustness note: "verdict stable under N of M perturbations".
6. Final verdict with the rule that produced it.

### 13.6 Skills to install for the agents (verified on skills.sh, 2026-10-03)

Install into the repo's `.agents/skills/` (read by Devin and Codex):

```
pip install modal && modal skills install          # official Modal skill + docs
npx skills add k-dense-ai/scientific-agent-skills@statistical-analysis
npx skills add k-dense-ai/scientific-agent-skills@scikit-learn
npx skills add k-dense-ai/scientific-agent-skills@scientific-visualization
npx skills add k-dense-ai/scientific-agent-skills@scientific-critical-thinking
npx skills add k-dense-ai/scientific-agent-skills@peer-review
npx skills add k-dense-ai/scientific-agent-skills@optimize-for-gpu
npx skills add k-dense-ai/scientific-agent-skills@pytorch-lightning     # Swarm A/B training only
```

Not found and not needed as skills: scikit-image / microscopy segmentation (write our own, it is 30 lines), Streamlit (plain docs suffice), ImageRep (use the repo directly). The `impeccable` skill already installed locally is for the final screen polish only.

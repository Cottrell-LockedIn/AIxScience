# Handover prompt: reset to Phase A, then redo Phase B (Track 4 QC, Polaron FIB-SEM)

Repo: `Cottrell-LockedIn/AIxScience`. Read `AGENTS.md` and `docs/FRAMEWORK.md` (Section 00, 2b and 4) before anything else.

## Owner rules (non-negotiable)
1. **Start from the Phase-A-only state.** Create `devin/<unix-ts>-phase-a-reset` from commit `8b79c25` (last commit containing only S1-S5 = Phase A). Do not base on, merge, rebase onto or cherry-pick from `stage/s1-s5-reality-check` (PR #1) or `archive/phase-b-attempt-1`.
2. **No Phase B/C contamination.** No earlier Phase B or Phase C code, result files, fitted artefacts, cached embeddings, thresholds or numbers may enter the new branch or your reasoning. Concretely: do not read `results/` beyond Phase A outputs on any other branch; do not read `docs/PROJECT_STATE.md`, `docs/PRESENTATION_JUSTIFICATION.md`, `docs/NEXT_STEPS.md`, `docs/RULEBOOK.md`, `docs/FEATURE_DOSSIER.md`, `docs/FAILURE_MODE_MAP.md` or `docs/handover/PHASE_B_CHECK.md` on the archive branch; never run PR #1's classify/verdict/stats/validate code. Phase B fits **no supervised model** (no classifier, no training, no fine-tuning; DINOv2 is used frozen). Phase C (classifier, OOD, held-out scoring) is out of scope until the owner approves it.
3. **Use Modal wherever it speeds things up** (credentials `MODAL_TOKEN_ID`/`MODAL_TOKEN_SECRET` are already in the environment): DINOv2 embedding (GPU, `.map` over images, weights in a Volume), permutation and split-half nulls (fan out over containers), the ±10 % threshold re-segmentation and the from-raw reruns used by checkers. Pin container package versions to the local venv. Log every run (function, n, wall time, GPU/CPU, git SHA, config hash) in `results/MODAL_RUNS.csv`. Set BLAS threads to 1 in parallel workers (an earlier attempt stalled from oversubscription).
4. **Never move to the next phase without the owner's explicit approval.** Stop at each gate below and message the owner with the gate report.
5. **After each phase, run an on-track check and a "runs to the end" check** (see "Phase-end checks").

## Inputs you MAY use (specifications, not results)
Fetch read-only with `git show origin/archive/phase-b-attempt-1:<path>`:
- `docs/READ/Polaron Clarification Batch Baseline and Judging.md`, `docs/READ/Consultant Failure Modes Handoff.md`, `docs/READ/84-Dimension Feature Catalogue (owner-supplied).md` (candidate pool, not labels or ground truth), plus everything already in `docs/READ/` at `8b79c25` (kickoff, Questions for Polaron, Feature Details, Dataset First Look, Method Evidence).
- `configs/features_v1.yaml`: the consultant-approved, pre-registered F01-F11 definitions. It is a spec; copy it as is.
- `docs/evidence/*.csv|*.bib` and `docs/EVIDENCE_BASE.md`: literature with DOI, grade and access status, not our results.
- `docs/handover/PHASE_A_CHECK.md` (independent Phase A check of the earlier attempt) and `docs/handover/TRACEABILITY.md` (Polaron/consultant requirement traceability).
- `origin/main` (contains the owner's config edit `50b375f`: Polaron phase class names).

Polaron's governing clarification (verbatim): "Treat batch 3 as the baseline, it's what's been "promised" by the supplier. Batch 1 and 2 arrived subsequently, and we're trying to tell if they are different. They are not explicitly better or worse than the batch 3 baseline, but they show the types of variation we need your models to pick up on." and "The judging criteria reflects this; can you identify what's different about the batches, and thus categorise the held back samples correctly. If you can, this implies unknown batch N could be categorised accurately as in or out of distribution - helping manufacturers make critical decisions about when to accept and reject a batch!"

## Data facts (from Phase A, safe to use)
`python scripts/download_drive.py` (~1.7 GB, into git-ignored `data/`). 93 TIFFs = 31 stems (images/fields of view); Batch_1 7, Batch_2 7, Batch_3 17; detectors BSE + In-Lens + ETD (4 stems: BSE + In-Lens + SE). **The image (stem) is the statistical unit (n = 31)**; tiles and detector views of one stem are never split across folds or permutations. Phase identities: class 0 dark = void/pore, class 1 mid = graphite, class 2 bright = silicon, always tagged `phase_identity: stated by Polaron, not image-verified` (Si vs SiOx indistinguishable; binder/additive lumped). Pixel size is unconfirmed, so use px; columns `_nm_if25` only. The three held-back images are never touched in A or B.

## Phase A: reset and close (stop at the gate)
1. Branch from `8b79c25`; merge `origin/main`. In `configs/v1.yaml` set `stats.reference_batch: Batch_3` (Polaron-stated, so no code-level override). This changes the config hash; regenerate everything below under the new hash.
2. Fix the defects the independent Phase A check found (details in `PHASE_A_CHECK.md`):
   - add `tabulate` to `pyproject.toml`; add an empty `tests/__init__.py` so plain `pytest -q` collects;
   - `audit.py` / `DATA_AUDIT.md`: bright phase = "stated by Polaron, not image-verified (no EDS)"; Batch_3 = supplier-promised baseline; same field of view across detectors = *pending* until you verify it yourself (registration is Phase B item B6);
   - `REALITY_CHECK.md`: current config hash and git SHA, the correct edge-line file count, the exact pixel-size tag range instead of "all round to 25.000 nm/px", the correct number of acquisition groups.
   Derive each corrected value from the files, not from the checker's text.
3. Rerun S1-S5 (`qc audit/tiles/artefacts/segment/kpi` + `scripts/reality_check.py`). Use Modal for segmentation if it is faster. `results/audit/images.csv` and `files.csv` must be byte-identical to `8b79c25`; report any other numeric change against `8b79c25` with its cause (expected: only provenance columns change with the hash).
4. FRAMEWORK Phase A visual bullet: look at 10 random full-resolution BSE tiles per batch (fixed seed) yourself and write `docs/INSPECTION.md`. Cover what a materials scientist would measure, and whether thresholding separates pore / particle / crack. List the segmentation defects you see, with tile IDs. Commit one 5×2 mosaic per batch; don't commit the individual tiles if they exceed ~15 MB in total. Known risks to look for: bright halos on flake edges labelled class 2, particle-poor tiles that per-tile multi-Otsu still splits into 3 classes, bright image-border strips.
5. Gate report → owner: covariate table plotted by batch, plus the statement on whether batches already separate on acquisition covariates (FRAMEWORK gate). Also any segmentation defects that would need an S4 change; that is a design decision for the owner, so propose it, don't implement it.
6. Phase-end checks (below), including an independent Phase A checker. Open a **draft PR to main** from the new branch. Leave PR #1 untouched. **Stop and wait for approval.**

## Phase B: W1 end to end, no training (only after approval; stop at the gate)
Follow FRAMEWORK §4 Phase B. Every item states its definition, units (px), command, output path, config hash and git SHA. Items are numbered so the owner can approve partial progress.
- **B1 KPIs on BSE:** (a) three-class phase fractions by multi-Otsu after denoising; (b) class-2 size distribution and count density (connected components, equivalent diameter). Then flake size/aspect ratio, pore size, crack-like fraction and TPC characteristic length if feasible. For **every** KPI: ±10 % threshold perturbation (on Modal) and a 5-tile manual check (raw, overlay, each class mask, tile ID, values) recorded in `docs/INSPECTION.md`.
- **B2 consultant features F01-F11** exactly as defined in `configs/features_v1.yaml`, image-level, with the same ±10 % sensitivity for all 11.
- **B3 embeddings:** DINOv2 ViT-S/14, frozen, fixed torch.hub commit. One vector per tile, mean per image, per detector channel; run on Modal GPU with `.map`. Log time and cost. Verify and quote the code licence and the **weights** licence from the pinned commit's LICENSE/README; don't assume either.
- **B4 `stats.py`** (image level, reference = Batch_3 from config):
  - Null = repeated image-level split-halves of Batch_3. State the split sizes and why. Warn that a smaller reference half makes the null conservative.
  - Pairwise batch distances (all pairs, symmetric, zero diagonal): standardised KPI/feature median shifts, and energy distance + MMD on embeddings, each with image-label permutation p (≥ 1,000, on Modal) and BH adjustment.
  - Acquisition-confound control, reported alongside: the same distances on the acquisition covariates themselves, and on features/embeddings residualised on the covariates (label-free OLS; say it is conservative).
  - Consistency score per batch: within-batch spread of per-image KPIs and mean pairwise embedding distance, with jackknife SE and whether the ranks are separable.
  - Unit tests: planted shift detected, no shift not detected, matrix symmetry, duplicate IDs rejected, covariate-driven shift vanishes after residualisation.
- **B5 validation gates (pre-registered, set before you look at any batch contrast):** G1 image-level test; G2 not acquisition-confounded, or the contrast survives covariate residualisation with the same sign and p < 0.05; G3 ±10 % threshold sensitivity < 0.5 × Batch_3 MAD; G4 conclusion unchanged when Batch_3 leave-one-out outliers are removed (computed per table, never hard-coded); G5 the feature maps to a failure mode that is observable in 2D BSE. Keep rule = bootstrap rank stability ≥ 0.7 and passes G2, G3 and G4. Report keep/investigate/drop per feature and do not loosen the rule after seeing results.
- **B6 detector registration + charging-glow sensitivity:** verify same field of view across detectors (shift/scale/rotation per stem). Treat any "bright in BSE and SE" mask as a sensitivity row, not a correction.
- **B7 one verdict JSON per batch**, validated against `schema/verdict.schema.json`, with a reason sentence and evidence paths to B4 rows. Labels: `within_bounds` / `investigate` / `outside_bounds`.
  - `outside_bounds` requires two lines from *different* feature families, each from features that **passed all gates**, and no acquisition drift.
  - Signals from features that failed any gate can only give `investigate`.
  - Batch_3 images are scored against the other 16 (leave-one-out).
  - `accepted`/`rejected` are never written by code; they are human ledger entries only.
  - Mark the run `exploratory` (not frozen).
- **B gate report → owner:** distance matrix, consistency ranking, verdict JSON(s) with reason sentences (FRAMEWORK gate), plus the gate table and the acquisition-vs-material statement. Then the phase-end checks. **Stop and wait for approval; do not start Phase C.**

## Phase-end checks (after A and after B)
1. **Independent checker:** a fresh-context Devin session that did not author the work, started from the pushed branch. It re-runs the phase from raw data (Modal allowed) and grades each FRAMEWORK bullet and gate item L0 code exists / L1 ran on real data / L2 regenerated output matches committed / L3 doc numbers match result files. It returns PASS / CONDITIONAL PASS / FAIL with exact corrective actions (AGENTS.md "Independent review"). It must not rely on PROJECT_STATE, PR prose or docstrings as evidence. Relay its verdict verbatim; fix FAILs before reporting the phase as done.
2. **On-track check against Polaron's criterion:** for each item in `TRACEABILITY.md` and the clarification above, state whether this phase moved it to done/partial/missing. Also state what remains for "identify what differs" and "categorise held-back / batch N in or out of Batch_3".
3. **Runs-to-the-end check:**
   - Fresh clone + fresh venv; `pytest -q`; one command that regenerates every committed output of the phase from raw data and diffs it against the commit (max abs numeric diff must be 0, or explained).
   - A dry run proving the next phase's inputs exist with the expected schema and one row per image.
   - Confirm the frozen-config path can take a new image through S1-S5 on a synthetic copy of one training image renamed as `heldout_dryrun` (never the real held-back images).
4. **Evidence check:** every number written in docs is registered in `docs/evidence/numbers.csv` (doc, quote, source file, selector, value, tolerance); `scripts/check_numbers.py` passes.

## Reporting style to the owner
Short. Lead with the verdict per phase (properly done: yes / yes with defects / no). Distinguish "code exists" vs "ran" vs "matches". Give every number with its source file. Never call anything done, validated or frozen without the checker's PASS. No good/bad battery claims: Batch_1/2 are variation relative to the Batch_3 baseline, not worse.

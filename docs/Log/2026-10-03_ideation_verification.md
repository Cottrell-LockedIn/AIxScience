# Log: Ideation and research verification

Date: 2026-10-03
Agent: Devin (Desktop), ideation phase, no code written
Purpose: audit the pre-event research for validity, then draft `FRAMEWORK.md`

## Files read

- `AGENTS.md`, `CLAUDE.md`, `PROJECT_STATE.md`
- `RESEARCH/Track 4 Playbook.md`, `RESEARCH/SOURCES.md`
- `READ/Related Projects and Reusable Code.md`, `READ/Modal Recommended Workflow.md`
- `BUILD/Product and Demo Toolkit.md`
- `../../../40 Sources/Websites/AI x Science Track 4 Research Sources.md` (canonical source record)
- `code/AIxScience_Msia`: empty clone, `main` has no commits, remote = github.com/alvinbong03/AIxScience_Msia

## Claims checked and results

| Claim in notes | Method | Result |
|---|---|---|
| LIBAD preprint arXiv:2608.07958 exists | fetched arxiv.org/abs | VERIFIED. Submitted 8 Aug 2026, CC BY 4.0. VIS + X-ray roll-to-roll, not SEM. DA-Core FPR95 60.4% -> 54.3% confirms "high AUROC can coexist with bad FPR" lesson |
| Frozen-encoder crack preprint arXiv:2608.27162 | fetched arxiv.org/abs | VERIFIED. Submitted 27 Aug 2026, under review at Energy Storage Materials. Only 3 cross-sections. Not peer reviewed |
| ImageRep code BSD-3-Clause | GitHub page + shallow clone of LICENSE | VERIFIED (LICENSE file BSD-3). Note: `pyproject.toml` classifier says MIT, LICENSE file governs. Package name is `representative`, import is `representativity` |
| ImageRep reproducible | inspected repo | `paper_figures/` has fig1/fig3/model_accuracy/pred_vs_true_cls scripts; `tests/tests.py` uses `skimage.data.binary_blobs` + `tests/resources/default.tiff`; fitted MicroLib statistics shipped as JSON (`correction_fitting/*.json`, `validation/validation.json`). Reproduction does NOT require downloading MicroLib for the core claim |
| ImageRep assumptions (binary seg, >=200 px, feature <=70 px, non periodic) | README | VERIFIED verbatim in README limitations |
| Anomalib Apache-2.0 | GitHub API | VERIFIED, 6.2k stars, pushed 2026-10-03 |
| PatchCore Apache-2.0 | GitHub API | VERIFIED, last push 2024-07, effectively unmaintained |
| DINOv2 Apache-2.0 | GitHub API | VERIFIED |
| Hierarch MIT | GitHub API | VERIFIED, 8 stars, pushed 2026-08. Tiny project: validate before relying on it |
| LIBAD code BSD-3 | GitHub API | VERIFIED, 0 stars, pushed 2026-08 |
| micro-sam MIT, PoreSpy MIT | GitHub API | VERIFIED |
| Polaron crack case study | fetched polaron.ai/newsroom/quantifying-cracks | VERIFIED. Dated 13 May 2026. Classes: pore, single crystal NMC, polycrystal NMC, crack. "8 h to under 5 min" is vendor-reported |
| Modal prices (T4 0.59, L4 0.80, A10 1.10, L40S 1.95, A100-40 2.10, H100 3.95 per hour) | fetched modal.com/pricing | VERIFIED to 4 s.f. Starter plan: $30/month free credit, 10 GPU concurrency, 100 containers |
| Modal LLM guidance / llms.txt | modal docs | VERIFIED. `modal skills install` writes a Modal SKILL.md + docs into `.agents/` |

## New findings not in the notes

1. **Polaron was founded by the TLDR group (Imperial): Sam Cooper, Steve Kench, Isaac Squires.** ImageRep is a TLDR-group paper (Dahari, Docherty, Cooper...). The judges know this paper. It is published in Advanced Science (peer reviewed), code is BSD-3, and the key result is reproducible without large downloads. This makes it the strongest Devin-challenge candidate by a wide margin.
2. **alibi-detect is NOT permissive.** Licence changed to Business Source License 1.1 in January 2024 (converts to Apache-2.0 four years after each release). Do not import it. MMD / energy distance with a permutation test is ~30 lines of numpy; implement in-repo.
3. **`modal skills install`** (part of `pip install modal`) installs a Modal skill into `.agents/skills/`, which both Devin and Codex read. One command serves both agents. `--global` installs to `~/.agents/`.
4. Devin MCP config lives in `.devin/mcp_config.json` (project) or `~/.config/devin/mcp_config.json`. Codex reads `.agents/skills` from CWD up to repo root.
5. The brief says the unseen batch drops **~8 hours in**. The playbook assumed a 30-hour scope; the user says 24 hours. The real build window for a freezable v1 pipeline is therefore short. Recommended handling: quarantine the unseen batch on arrival (do not open), freeze v1 at a chosen time, evaluate once, log the commit hash.
6. No public prior winner for this exact track was found (unchanged from notes). Closest precedent remains the Dec 2025 ML-for-Microscopy hackathon.

## Critique of existing notes (what holds, what is weak)

- Playbook, Modal note and product toolkit are internally consistent and conservative. Nothing factually wrong was found.
- Weakness: notes list candidate tools but do not commit to a default stack, so a 24 h team would still spend time choosing. `FRAMEWORK.md` fixes a default and names the fallback.
- Weakness: the "frozen-feature challenger" lane is described as optional, but it is the only lane that can produce a defensible verdict if classical segmentation fails on the actual images (unknown modality). Promote it to a parallel must-have with a strict time box.
- Weakness: no plan for the Devin challenge. Added.
- Weakness: no explicit "what if the data is not what we expect" branch. Added as a decision tree in the framework.
- Weakness: no leakage rule for pseudo-batch construction (tiles from the same image must not be split across pseudo-batches). Added.
- Hierarch (8 stars) is treated as a dependency; safer to write a 20-line image-level permutation test ourselves and keep hierarch as a cross-check.
- Reddit/general hackathon advice (anecdotal): baseline first, one change per experiment, hard timers, "minimum presentable product", rehearsed 90 s pitch, nothing new on the day except what the sponsor challenges demand. Consistent with the playbook.

## Commands run (for reproducibility)

```
find . -type f -not -path '*/.git/*'
git -C code/AIxScience_Msia log --oneline ; git remote -v ; git status
curl https://api.github.com/repos/<owner>/<repo>  (licence, stars, pushed_at)
curl https://raw.githubusercontent.com/SeldonIO/alibi-detect/master/LICENSE
git clone --depth 1 https://github.com/tldr-group/ImageRep /tmp/ImageRep_peek   (inspected, then deleted)
```

GitHub unauthenticated API rate limit was hit once; fell back to shallow clone.

## Outputs of this session

- `Log/2026-10-03_ideation_verification.md` (this file)
- `FRAMEWORK.md` (new, top level)
- `RESEARCH/SOURCES.md` (appended: Polaron founders, alibi-detect licence warning, Modal skills, Codex skills)
- `PROJECT_STATE.md` (updated phase and decisions)

No files written to `READ/` (policy: only on explicit request). No code written to `code/`.

## Open items for the team

See "Decisions still open" in `FRAMEWORK.md`.

## Follow-up (same session)

Team answers: 4 people; wants a paper comparison before choosing the Devin target; "max plan, $200 credit" (product unclear, to confirm); repo stays empty until the team has discussed `FRAMEWORK.md`.

Additional checks for the comparison:
- Crack preprint code is at git.rwth-aachen.de (HTTP 200 but served an anti-bot challenge page; licence unreadable by curl). Data: Figshare 10.6084/m9.figshare.32975921, CC BY 4.0, single 1.13 GB zip.
- Written: `RESEARCH/Devin Challenge Paper Comparison.md` (ImageRep vs crack preprint vs hierarchical bootstrap vs LIBAD).
- `FRAMEWORK.md` Section 2 rewritten for 4 named lanes; Section 10 updated with the answers.

## T+1h update

- Polaron kickoff notes saved to `READ/Polaron Kickoff Discussion.md` with a "what changed" table.
- Feature details and suggestions saved to `READ/Feature Details and Suggestions.md` (four feature names unchanged).
- `FRAMEWORK.md` rewritten as v2: pre-event checklist removed, clock re-anchored at T+1, two workflows (W1 batch comparison, W2 batch classifier with LOIO + artefact ablation), repo layout, held-back images quarantine protocol.
- Modal budget confirmed by team: $150.
- Pending team review before any code is written.

## T+1.5h update: dataset access and first look

- Drive folder is public. Three subfolders Batch_1 (21 files), Batch_2 (21), Batch_3 (50 listed, likely 51). Names enumerated via HEAD requests; listing in `Log/assets/drive_file_listing.json`.
- Downloaded one image per batch (img_5n1q8atc_Inlens, img_3806gxp0_BSE, img_0grcilhi_BSE) to /tmp; previews and 800 px crops in `Log/assets/`. Not committed to the code repo.
- Format: LZW TIFF via tifffile, RGB with identical channels, uint8, 7000 px wide, 1904 to 2316 px tall. XResolution tag implies 25 nm/px (unconfirmed). No databars. One image has a 2 px coloured line at the right edge. `imagecodecs` needed.
- Visual reading: graphite flake anode with brighter angular particles in BSE (likely Si/SiOx, unconfirmed). Curtaining visible in Inlens.
- Literature checked for the approved layers: KIT FIB-SEM quality indices (curtaining index), Munch 2009 wavelet-Fourier destriping, Si-graphite FIB-SEM segmentation practice, TLDR-group KPI vocabulary (SliceGAN / MicroLib / ImageRep). Written to `READ/Method Evidence for Layers.md`.
- Written: `READ/Dataset First Look.md`, `READ/Questions for Polaron.md`. `FRAMEWORK.md` gained Section 2b (task division: train vs inference vs compute, per stage and person) and updated data facts / KPI priorities / tile size.

## T+2h update

- `FRAMEWORK.md` v3: added Section 00 "For any AI agent picking this up" (plain-words workflow, no-labelling/no-training statement, 10 hard rules, models/libraries/skills table, ranked differentiators, expected field). Intended as the entry point for Devin/Codex sessions working on any stage.

## T+5h update

- Team confirmed: Devin with up to 100 parallel subagents, $200 Devin credit, $150 Modal, ~19 h left; wants maximum ambition.
- `FRAMEWORK.md` v4: rule 7 relaxed to allow training under LOIO + ablation + frozen-baseline conditions; Section 12 added (parallel-agent swarms A-D, experiment registry and leaderboard, pre-declared selection rule, segmentation training on 60 human-corrected crops, embedding/classifier matrix on Modal, domain-adapted DINOv2 and saliency-vs-stripes experiment, two-pipeline freeze, budget guardrails).
- Position stated to the team: training helps in three places (segmentation, domain-adapted embeddings, deep classifier with saliency) and nowhere else; scraped paper figures remain excluded.

## T+5.5h update

- Re-read the track brief: test is described as a "brand-new unseen batch" for generalisation; Polaron said three held-back images. Added `FRAMEWORK.md` Section 13 (open-set by construction, leave-one-batch-out calibration, no test-time batch dependence, acquisition-invariance robustness panel with flip rates added to the selection rule, generalisation-favouring choices, held-back screen contents).
- Skills search via `npx skills find`: relevant and reputable = Modal official skill (`modal skills install`), k-dense-ai/scientific-agent-skills {statistical-analysis, scikit-learn, scientific-visualization, scientific-critical-thinking, peer-review, optimize-for-gpu, pytorch-lightning} (~1.7-2.1K installs each). No microscopy-segmentation or Streamlit skill worth installing.
- Devin local -> cloud: `/handoff` carries conversation context, repo + branch, and uncommitted diff of the git repo. Planning docs in this folder are outside the repo and must be committed into it first.

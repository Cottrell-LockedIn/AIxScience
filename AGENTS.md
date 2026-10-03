# AIxScience Agent Rules

## Purpose

This repository contains the submission implementation for the AI x Science Track 4 project.

## Authority

- Evidence and team judgment override recommendations in this file.
- State clearly when an idea is unsupported, infeasible or unlikely to help.
- Never claim that a method or result will win.
- Keep changes focused on the requested task and avoid unrelated refactoring.

## Competition boundary

- Build the submission implementation entirely during the event.
- Do not copy pre-event code, scaffolds, tests, configurations, fitted artefacts or cached predictions into this repository.
- Use open-source libraries and pretrained models only with attribution and compatible terms.
- Keep private links, credentials, coupons and activation codes out of files and Git.

## Scientific rules

- The primary question is batch-vs-baseline distribution change.
- Separate acquisition variation from material variation.
- Treat batch, specimen and original image identifiers as experimental hierarchy.
- Tiles from one image are not independent samples.
- Use physical units only when scale metadata supports them.
- Phase identities are those stated by Polaron (class 2 bright = silicon, class 1 mid = graphite, class 0 dark = void/pore) and are not image-verified. Use the names, but every table, figure and verdict must carry the provenance `phase_identity: stated by Polaron, not image-verified`, and keep the caveats: Si vs SiOx is indistinguishable in BSE; binder and conductive additive are lumped into class 0/1. Do not go beyond this (e.g. SEI, plated lithium, SiOx) without labels, EDS or equivalent evidence.
- Separate sampling, segmentation or model, and decision uncertainty.
- Prefer an `investigate` or abstain result over unsupported certainty.
- Freeze preprocessing, model, aggregation and thresholds before evaluating the unseen batch.
- Log any later changes as exploratory.

## Independent review

Material research claims, architecture decisions, implementations and releases require a fresh-context reviewer who did not author the work.

The reviewer must return:

- `PASS`, `CONDITIONAL PASS` or `FAIL`;
- source and licence problems;
- scientific or statistical objections;
- implementation feasibility;
- judge objections and advantage risks;
- exact corrective actions.

Conditional or failed work is not presented as validated.

## Code Review Rules

- Report only consequential, actionable defects introduced by the pull request. Leave formatting, lint and other deterministic checks to CI.
- Flag data leakage or pseudoreplication. Train, validation and test splits must respect batch, specimen and original-image boundaries; tiles from one image are not independent samples.
- Flag changes to preprocessing, models, aggregation or thresholds after evaluation on the unseen batch unless the result is explicitly marked exploratory.
- Flag physical-unit claims without scale metadata and chemical-phase labels beyond the Polaron-stated identities (silicon / graphite / void) or missing their provenance tag.
- Flag results that hide uncertainty, overstate conclusions or force a binary decision when `investigate` or abstention is appropriate.
- Flag exposed credentials, private links, confidential datasets, sensitive samples or generated artefacts that should not be committed.
- Require changed scientific or data-processing behaviour to have an appropriate test or documented verification, and state what remains unverified.

## Implementation guide (read before working on any stage)

- `docs/FRAMEWORK.md` Section 00 is the entry point: plain-words workflow, hard rules, models and tools, differentiators.
- `docs/FRAMEWORK.md` Section 2b is the stage table (S1 to S11): what each stage reads and writes, who owns it, train vs inference.
- `docs/FRAMEWORK.md` Section 12 is the parallel-agent plan (experiment registry, leaderboard, selection rule). Section 13 is the generalisation and robustness protocol.
- `docs/READ/Dataset First Look.md` describes the data. `docs/Log/assets/drive_file_listing.json` has the download IDs.
- `docs/READ/Method Evidence for Layers.md` lists the citation for each method; cite it in the README when you use one.
- `docs/READ/Questions for Polaron.md` lists open facts (pixel size, phase identity, reference batch). Treat them as unconfirmed until `docs/DATA_AUDIT.md` says otherwise.

## Working conventions

- Python 3.11, `uv`, pinned `requirements.txt`. Run `python -m qc --help` to see stages.
- Stages hand off files with fixed names under `results/`; never pass data between stages in memory across owners.
- One experiment = one YAML in `experiments/<swarm>/` = one folder in `results/experiments/<id>/` with `metrics.json`, `config.yaml`, `git_sha.txt`, `notes.md`.
- Do not edit `src/qc/` core modules from an experiment agent; wrap or configure instead. Core changes go through the owning human on a branch.
- Raw data (`data/`) is never committed. Derived JSON/CSV/PNG under `results/` may be.
- Held-back images go to `data/heldout/` and are processed once with the frozen config after `git tag v1-frozen`.
- Agent skills live in `.agents/skills/` (Modal official skill plus K-Dense scientific skills). Use them.

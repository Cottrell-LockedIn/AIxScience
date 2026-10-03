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
- Do not name image regions as chemical phases without labels, EDS or equivalent evidence.
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
- Flag physical-unit claims without scale metadata and chemical-phase labels without supporting labels, EDS or equivalent evidence.
- Flag results that hide uncertainty, overstate conclusions or force a binary decision when `investigate` or abstention is appropriate.
- Flag exposed credentials, private links, confidential datasets, sensitive samples or generated artefacts that should not be committed.
- Require changed scientific or data-processing behaviour to have an appropriate test or documented verification, and state what remains unverified.

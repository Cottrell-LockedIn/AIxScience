"""S7 W2 batch classifier (classify). Owner: P3.

Leave-one-image-out logistic regression; artefact ablation; drivers. Open-set handled in verdict.py with stats.py distances.

Reads:  per-tile features (kpi + artefacts + emb) and batch labels
Writes: results/w2_loio.json (image-level accuracy with/without artefact covariates, per-batch recall, drivers), results/w2_predictions.parquet

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from typing import Any


def run(cfg: dict[str, Any]) -> None:
    raise NotImplementedError("classify: not implemented yet; see docs/FRAMEWORK.md Section 2b")

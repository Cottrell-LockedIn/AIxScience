"""S8 verdict assembly (verdict). Owner: P4.

Combine evidence into within_bounds / investigate / outside_bounds with drivers, uncertainty split, artefact panel, routing and pipeline hash.

Reads:  results/*.json|parquet from S3, S6, S7
Writes: results/v1/batch_<k>.json, results/v1/image_<id>.json validated against schema/verdict.schema.json

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from typing import Any


def run(cfg: dict[str, Any]) -> None:
    raise NotImplementedError("verdict: not implemented yet; see docs/FRAMEWORK.md Section 2b")

"""S6 W1 batch comparison (stats). Owner: P1.

Reference null from image-level half splits; energy distance / MMD with image-level permutation; effect sizes; consistency ranking.

Reads:  kpi_per_image, emb_per_image, artefacts_per_image
Writes: results/null_bands.json, results/w1_distances.json, results/consistency.json, results/per_image_flags.parquet

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from typing import Any


def run(cfg: dict[str, Any]) -> None:
    raise NotImplementedError("stats: not implemented yet; see docs/FRAMEWORK.md Section 2b")

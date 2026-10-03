"""S3 artefact covariates (artefacts). Owner: P2.

Measure acquisition artefacts as covariates. Never remove them from the images used for KPIs.

Reads:  data/tiles/index.parquet + tiles
Writes: results/artefacts_per_tile.parquet, results/artefacts_per_image.parquet (curtaining_score, edge_charging, noise_sigma, sharpness, mean, std, p01, p99, detector)

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from typing import Any


def run(cfg: dict[str, Any]) -> None:
    raise NotImplementedError("artefacts: not implemented yet; see docs/FRAMEWORK.md Section 2b")

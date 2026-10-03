"""S4a segmentation (segment). Owner: P2.

Denoise, multi-Otsu 3 classes per tile, morphology clean-up; log thresholds; also masks at +/-10 % thresholds for sensitivity.

Reads:  BSE tiles
Writes: data/tiles/masks/<tile_id>.png (0 pore, 1 graphite, 2 high-Z; names unconfirmed), results/thresholds_per_tile.parquet

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from typing import Any


def run(cfg: dict[str, Any]) -> None:
    raise NotImplementedError("segment: not implemented yet; see docs/FRAMEWORK.md Section 2b")

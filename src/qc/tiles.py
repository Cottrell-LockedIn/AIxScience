"""S2 tiling (tiles). Owner: P1.

Crop border, cut fixed-size tiles with stride, keep an index so every tile maps back to its image.

Reads:  data/raw/**.tif
Writes: data/tiles/<batch>/<sample>_<channel>_<y>_<x>.npy (or memmap), data/tiles/index.parquet (tile_id, sample_id, batch, channel, y, x), data/tiles/previews/*.png

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from typing import Any


def run(cfg: dict[str, Any]) -> None:
    raise NotImplementedError("tiles: not implemented yet; see docs/FRAMEWORK.md Section 2b")

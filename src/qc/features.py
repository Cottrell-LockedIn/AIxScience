"""S5 frozen embeddings (features). Owner: P3.

DINOv2 ViT-S/14 frozen, pinned revision; mean-patch pooling; runs on Modal via modal_app.py or locally.

Reads:  tiles
Writes: results/emb_per_tile.npy, results/emb_index.parquet, results/emb_per_image.npy; results/modal_runs.csv (time, cost)

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from typing import Any


def run(cfg: dict[str, Any]) -> None:
    raise NotImplementedError("features: not implemented yet; see docs/FRAMEWORK.md Section 2b")

"""S1 inventory and audit (audit). Owner: P1.

Inventory every image, record shape/dtype/tags, detect duplicates and missing channels.

Reads:  data/raw/inventory.csv, TIFF headers
Writes: docs/DATA_AUDIT.md, results/audit/images.csv (shape, dtype, channel set, resolution tag)

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from typing import Any


def run(cfg: dict[str, Any]) -> None:
    raise NotImplementedError("audit: not implemented yet; see docs/FRAMEWORK.md Section 2b")

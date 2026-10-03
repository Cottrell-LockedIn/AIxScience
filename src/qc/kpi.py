"""S4b KPIs (kpi). Owner: P2.

Phase fractions, high-Z particle size/count/dispersion, pore size, TPC length. Units px until pixel size is confirmed.

Reads:  masks + tiles
Writes: results/kpi_per_tile.parquet, results/kpi_per_image.parquet, results/kpi_sensitivity.parquet

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from typing import Any


def run(cfg: dict[str, Any]) -> None:
    raise NotImplementedError("kpi: not implemented yet; see docs/FRAMEWORK.md Section 2b")

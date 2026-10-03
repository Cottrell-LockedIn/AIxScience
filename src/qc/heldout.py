"""S10 held-back inference (heldout). Owner: P1 runs, P4 witnesses.

Run once. Closed-set prediction, open-set distances, drivers, artefact covariates vs training range, robustness note.

Reads:  data/heldout/*.tif, configs/v1.yaml at tag v1-frozen
Writes: results/v1/heldout.json

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from typing import Any


def run(cfg: dict[str, Any]) -> None:
    raise NotImplementedError("heldout: not implemented yet; see docs/FRAMEWORK.md Section 2b")

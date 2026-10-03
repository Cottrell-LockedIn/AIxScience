"""S13 robustness panel (robustness). Owner: P1.

Perturb images (gamma, noise, blur, synthetic curtaining, rescale, crop) and count verdict flips; leave-one-batch-out open-set calibration.

Reads:  tiles + frozen config
Writes: results/robustness.json (flip rate per perturbation), results/lobo.json (leave-one-batch-out)

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from typing import Any


def run(cfg: dict[str, Any]) -> None:
    raise NotImplementedError("robustness: not implemented yet; see docs/FRAMEWORK.md Section 2b")

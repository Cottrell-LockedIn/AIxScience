"""Deterministic review suggestions for an existing exploratory run.

This module deliberately sits outside ``src/qc``.  It never alters the frozen
mask, features, classifier inputs, or batch prediction.  It only proposes
places for a human to inspect by measuring which denoised pixels lie close to
the two frozen-style 1024-pixel Otsu thresholds.  Those threshold-near pixels
would change *raw intensity class* when the thresholds are moved by the
configured +/-10 percent sensitivity perturbation.

The result is a *segmentation-sensitivity diagnostic*, not a pixel confidence
map, defect detector, or failure probability.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import tifffile
from PIL import Image

from qc import segment, tiles


DIAGNOSTIC_ID = "local-threshold-sensitivity"
VERSION = "v2"
OFFSET_PX = 8
TILE_PX = 1024
STRIDE_PX = 512
ROI_PX = 512
MEDIAN_PX = 5
MIN_OBJECT_PX = 20
SENSITIVITY = 0.10
REGION_COUNT = 3


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _gray(path: Path) -> np.ndarray:
    """Read the frozen BSE channel convention (first plane when RGB)."""
    image = np.asarray(tifffile.imread(path))
    if image.ndim == 3:
        image = image[..., 0]
    if image.ndim != 2:
        raise ValueError("Review-region source must be a two-dimensional or RGB TIFF.")
    if image.dtype != np.uint8:
        raise ValueError("Review-region source must be uint8, matching the frozen input contract.")
    return np.ascontiguousarray(image)


def _integral(binary: np.ndarray) -> np.ndarray:
    # A leading zero row/column makes rectangle sums exact and easy to audit.
    out = np.zeros((binary.shape[0] + 1, binary.shape[1] + 1), dtype=np.int64)
    out[1:, 1:] = np.cumsum(np.cumsum(binary, axis=0), axis=1)
    return out


def _rect_sum(integral: np.ndarray, y: int, x: int, h: int, w: int) -> int:
    return int(integral[y + h, x + w] - integral[y, x + w] - integral[y + h, x] + integral[y, x])


def _overlap(a: dict[str, int], b: dict[str, int]) -> bool:
    return not (
        a["x"] + a["width"] <= b["x"]
        or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"]
        or b["y"] + b["height"] <= a["y"]
    )


def _candidate_windows(changed: np.ndarray, tile_y: int, tile_x: int) -> list[tuple[float, int, int]]:
    """Return 512px candidate crops inside one 1024px frozen-style tile."""
    integral = _integral(changed)
    # 128px positions find local changes without making this diagnostic expensive.
    positions = (0, 128, 256, 384, 512)
    area = ROI_PX * ROI_PX
    result = []
    for dy in positions:
        for dx in positions:
            score = _rect_sum(integral, dy, dx, ROI_PX, ROI_PX) / area
            result.append((float(score), tile_y + dy, tile_x + dx))
    return result


def _diagnostic_candidates(cropped: np.ndarray) -> list[tuple[float, int, int]]:
    """Score windows from the same tile size/stride as frozen segmentation.

    The mask supplied to this module verifies coordinate alignment and source
    provenance.  Thresholds are refitted here only for review selection, so no
    diagnostic output can change a saved engine output.
    """
    candidates: list[tuple[float, int, int]] = []
    cfg = {"median_px": MEDIAN_PX, "classes": 3, "min_obj_px": MIN_OBJECT_PX}
    for tile_y, tile_x in tiles.tile_grid(cropped.shape[0], cropped.shape[1], TILE_PX, STRIDE_PX):
        source_tile = cropped[tile_y : tile_y + TILE_PX, tile_x : tile_x + TILE_PX]
        denoised = segment.denoise(source_tile, MEDIAN_PX)
        thresholds = segment.fit_thresholds(denoised, classes=3)
        if thresholds is None:
            changed = np.zeros(source_tile.shape, dtype=bool)
        else:
            # This deliberately stops before morphology cleanup.  It is a
            # bounded threshold-nearness proxy, not a second segmentation
            # output.  It is exactly the set of raw intensity assignments
            # that can change under either +/-10% threshold perturbation.
            changed = np.zeros(denoised.shape, dtype=bool)
            for threshold in thresholds:
                lower = threshold * (1.0 - SENSITIVITY)
                upper = threshold * (1.0 + SENSITIVITY)
                changed |= (denoised >= lower) & (denoised < upper)
        candidates.extend(_candidate_windows(changed, tile_y, tile_x))
    # Descending score, then deterministic image order for ties.
    return sorted(candidates, key=lambda item: (-item[0], item[1], item[2]))


def _select_regions(candidates: list[tuple[float, int, int]], cropped_shape: tuple[int, int]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for score, y, x in candidates:
        roi = {"x": x + OFFSET_PX, "y": y + OFFSET_PX, "width": ROI_PX, "height": ROI_PX}
        if any(_overlap(roi, other["roi"]) for other in selected):
            continue
        if score > 0:
            title = "Threshold-sensitive review area"
            reason = (
                "Many denoised pixels in this crop lie within the local ±10% threshold-perturbation bands. "
                "Inspect the phase boundaries before relying on related measurements."
            )
            score_label = "Local threshold sensitivity (pre-cleanup)"
        else:
            title = "Representative review region"
            reason = (
                "No pixels fell within the local ±10% threshold-perturbation bands here. "
                "It is provided for context, not as an uncertain region."
            )
            score_label = "No local threshold sensitivity observed"
        selected.append({
            "id": f"region-{len(selected) + 1}",
            "roi": roi,
            "title": title,
            "reason": reason,
            "score": round(float(score), 6),
            "scoreLabel": score_label,
        })
        if len(selected) == REGION_COUNT:
            break
    if len(selected) < REGION_COUNT:
        # A valid frozen input is at least 1040px per dimension, so this is an
        # invariant failure rather than silently returning fewer review areas.
        raise ValueError("Could not construct three non-overlapping review regions.")
    return selected


def _cache_path(cache_dir: Path, source_hash: str, mask_hash: str) -> Path:
    return cache_dir / f"{DIAGNOSTIC_ID}-{VERSION}-{source_hash[:16]}-{mask_hash[:16]}.json"


def generate_review_regions(source_path: str | Path, mask_path: str | Path, cache_dir: str | Path) -> dict[str, Any]:
    """Return three deterministic, original-image-coordinate review ROIs.

    ``mask_path`` must be the exact 8px-cropped engine mask.  Its pixels are
    not re-used to alter the engine; dimensions and checksum bind this adjunct
    diagnostic to the same source/mask evidence shown in the UI.
    """
    source = Path(source_path)
    mask_file = Path(mask_path)
    cache = Path(cache_dir)
    source_hash, mask_hash = _sha256(source), _sha256(mask_file)
    output_path = _cache_path(cache, source_hash, mask_hash)
    if output_path.exists():
        return json.loads(output_path.read_text(encoding="utf-8"))

    original = _gray(source)
    # Engine masks are lossless PNG label images, unlike the TIFF source.
    with Image.open(mask_file) as mask_image:
        mask = np.asarray(mask_image, dtype=np.uint8)
    expected = (original.shape[0] - 2 * OFFSET_PX, original.shape[1] - 2 * OFFSET_PX)
    if mask.ndim != 2 or tuple(mask.shape) != expected:
        raise ValueError(
            f"Mask dimensions {tuple(mask.shape)} do not match the expected 8px-cropped source dimensions {expected}."
        )
    if not np.isin(mask, (0, 1, 2)).all():
        raise ValueError("Review-region mask must contain only engine labels 0, 1, and 2.")

    cropped = original[OFFSET_PX:-OFFSET_PX, OFFSET_PX:-OFFSET_PX]
    regions = _select_regions(_diagnostic_candidates(cropped), tuple(cropped.shape))
    document: dict[str, Any] = {
        "id": DIAGNOSTIC_ID,
        "version": VERSION,
        "method": "Per frozen-style 1024px tile, refit multi-Otsu thresholds and mark denoised pixels inside either ±10% threshold band; choose non-overlapping 512px crops with the largest local fraction.",
        "scoreMeaning": "Fraction of pixels inside a local ±10% multi-Otsu threshold band before morphology cleanup; it is not model confidence, defect probability, a regenerated mask, or a pass/fail score.",
        "limitations": [
            "This is a separate exploratory review aid. It never changes the frozen mask, measurements, or classifier prediction.",
            "The frozen mask has one fixed segmentation; this diagnostic is raw threshold proximity before morphology cleanup, not a regenerated segmentation mask.",
            "Phase identity is stated by Polaron, not image-verified; silicon and SiOx are indistinguishable in BSE, and binder/additive may be in dark or mid classes.",
        ],
        "sourceHash": source_hash,
        "maskHash": mask_hash,
        "mainImage": {"width": int(original.shape[1]), "height": int(original.shape[0]), "offsetPx": OFFSET_PX},
        "regions": regions,
    }
    cache.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, output_path)
    return document

from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile

from app.review_regions import OFFSET_PX, generate_review_regions


def _write_input(tmp_path: Path, *, uniform: bool = False) -> tuple[Path, Path]:
    height, width = 1040, 1560
    yy, xx = np.mgrid[:height, :width]
    image = np.full((height, width), 120, dtype=np.uint8)
    if not uniform:
        # Three intensity zones provide multi-Otsu thresholds, and diagonal
        # boundaries ensure some of the diagnostic windows change at +/-10%.
        image[(xx + yy) % 311 < 100] = 45
        image[(xx + yy) % 311 > 215] = 205
    source = tmp_path / "img_example_BSE.tif"
    tifffile.imwrite(source, image)
    mask = np.ones((height - 2 * OFFSET_PX, width - 2 * OFFSET_PX), dtype=np.uint8)
    mask_path = tmp_path / "example_mask.png"
    tifffile.imwrite(mask_path, mask)
    return source, mask_path


def _assert_valid(document: dict, source_shape: tuple[int, int]) -> None:
    regions = document["regions"]
    assert len(regions) == 3
    assert document["mainImage"] == {"width": source_shape[1], "height": source_shape[0], "offsetPx": 8}
    for index, item in enumerate(regions, start=1):
        roi = item["roi"]
        assert item["id"] == f"region-{index}"
        assert roi["x"] >= OFFSET_PX and roi["y"] >= OFFSET_PX
        assert roi["x"] + roi["width"] <= source_shape[1] - OFFSET_PX
        assert roi["y"] + roi["height"] <= source_shape[0] - OFFSET_PX
        assert 0 <= item["score"] <= 1
    for index, left in enumerate(regions):
        for right in regions[index + 1:]:
            a, b = left["roi"], right["roi"]
            assert a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"] or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"]


def test_review_regions_are_deterministic_and_in_original_coordinates(tmp_path: Path) -> None:
    source, mask = _write_input(tmp_path)
    first = generate_review_regions(source, mask, tmp_path / "cache")
    second = generate_review_regions(source, mask, tmp_path / "cache")
    assert first == second
    _assert_valid(first, (1040, 1560))
    assert first["id"] == "local-threshold-sensitivity"
    assert first["regions"][0]["score"] > 0
    assert "not model confidence" in first["scoreMeaning"]


def test_uniform_input_is_not_described_as_uncertain(tmp_path: Path) -> None:
    source, mask = _write_input(tmp_path, uniform=True)
    document = generate_review_regions(source, mask, tmp_path / "cache")
    _assert_valid(document, (1040, 1560))
    assert all(region["score"] == 0 for region in document["regions"])
    assert all(region["scoreLabel"] == "No local threshold sensitivity observed" for region in document["regions"])
    assert all(region["title"] == "Representative review region" for region in document["regions"])


def test_mask_must_be_aligned_to_the_original_source(tmp_path: Path) -> None:
    source, _ = _write_input(tmp_path)
    bad_mask = tmp_path / "bad_mask.png"
    tifffile.imwrite(bad_mask, np.ones((100, 100), dtype=np.uint8))
    try:
        generate_review_regions(source, bad_mask, tmp_path / "cache")
    except ValueError as error:
        assert "Mask dimensions" in str(error)
    else:  # pragma: no cover - failure text is more useful than an assert here
        raise AssertionError("Expected misaligned mask to be rejected")

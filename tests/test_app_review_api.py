"""Review and crop boundaries for the local API; no engine work is started."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest
import tifffile
from fastapi import HTTPException

from app import api


@pytest.fixture
def bound_validation(tmp_path, monkeypatch):
    source = tmp_path / "img_fixture_BSE.tif"
    tifffile.imwrite(source, np.arange(100, dtype=np.uint8).reshape(10, 10))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(api, "_validation_records", lambda: [({"subject": {"id": "fixture"}}, {})])
    monkeypatch.setattr(api, "_source_or_404", lambda field, channel: source)
    monkeypatch.setattr(api, "_known_field", lambda field: True)
    monkeypatch.setattr(api, "REVIEWS_FILE", tmp_path / "reviews.json")
    monkeypatch.setattr(api, "_REVIEWS", {})
    return source, digest


def test_saved_validation_review_accepts_bound_hash_and_roi(bound_validation):
    _, digest = bound_validation
    result = api._store_review("fixture", {"detector": "BSE", "sourceHash": digest, "roi": {"x": 1, "y": 1, "width": 4, "height": 4}})
    assert result["review"]["sourceVerified"] is True


def test_saved_validation_review_rejects_bad_hash(bound_validation):
    with pytest.raises(HTTPException, match="source hash"):
        api._store_review("fixture", {"detector": "BSE", "sourceHash": "0" * 64, "roi": {"x": 1, "y": 1, "width": 4, "height": 4}})


def test_saved_validation_review_rejects_out_of_bounds_roi(bound_validation):
    _, digest = bound_validation
    with pytest.raises(HTTPException, match="outside"):
        api._store_review("fixture", {"detector": "BSE", "sourceHash": digest, "roi": {"x": 8, "y": 8, "width": 4, "height": 4}})


def test_skipped_unavailable_review_is_explicitly_unverified(bound_validation):
    result = api._store_review("fixture", {"skipped": True, "note": "Original unavailable"})
    assert result["review"]["sourceVerified"] is False


@pytest.fixture
def saved_test_review(tmp_path, monkeypatch):
    report = json.loads(api.TEST_SET.read_text(encoding="utf-8"))
    field_id = report["images"][0]["subject"]["id"]
    monkeypatch.setattr(api, "REVIEWS_FILE", tmp_path / "reviews.json")
    monkeypatch.setattr(api, "_REVIEWS", {})
    return field_id


def test_saved_test_field_allows_an_explicit_unverified_skipped_review(saved_test_review):
    result = api._store_review(saved_test_review, {"skipped": True, "note": "Original TIFF was not retained with this saved result."})
    assert result["review"]["fieldId"] == saved_test_review
    assert result["review"]["sourceVerified"] is False


def test_saved_test_field_rejects_non_skipped_review_without_bound_source(saved_test_review):
    with pytest.raises(HTTPException, match="bound validation image") as error:
        api._store_review(saved_test_review, {"note": "Trying to annotate without a verified original."})
    assert error.value.status_code == 422


def test_native_crop_clamps_source_edge_without_resampling(bound_validation):
    source, _ = bound_validation
    result = api._native_crop(source, 8, 8, 8, 8)
    assert result.headers["x-cottrell-crop"] == "8,8,2,2"
    assert result.headers["x-cottrell-display-resampled"] == "false"

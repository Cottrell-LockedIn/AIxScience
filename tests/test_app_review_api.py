"""Review and crop boundaries for the local API; no engine work is started."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest
import tifffile
from fastapi import HTTPException
from PIL import Image

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


@pytest.fixture
def saved_preview_review(tmp_path, monkeypatch):
    previews = tmp_path / "validation_previews"
    previews.mkdir()
    artifact = previews / "fixture_BSE.png"
    Image.new("L", (8, 6), color=127).save(artifact)
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    source_hash = "a" * 64
    (previews / "manifest.json").write_text(json.dumps({"entries": {"fixture_BSE": {
        "filename": artifact.name,
        "source_sha256": source_hash,
        "preview_sha256": artifact_hash,
        "width": 80,
        "height": 60,
        "preview_width": 8,
        "preview_height": 6,
        "method": "fixture",
    }}}))
    monkeypatch.setattr(api, "VALIDATION_PREVIEWS", previews)
    monkeypatch.setattr(api, "_validation_records", lambda: [({"subject": {"id": "fixture"}}, {})])
    monkeypatch.setattr(api, "_known_field", lambda field: field == "fixture")
    monkeypatch.setattr(api, "REVIEWS_FILE", tmp_path / "reviews.json")
    monkeypatch.setattr(api, "_REVIEWS", {})
    return artifact_hash, source_hash


def test_saved_micrograph_review_binds_roi_to_the_displayed_preview(saved_preview_review):
    artifact_hash, source_hash = saved_preview_review
    result = api._store_review("fixture", {
        "detector": "BSE",
        "roi": {"x": 2, "y": 1, "width": 4, "height": 3},
        "reviewSource": {"kind": "saved-micrograph", "sha256": artifact_hash, "width": 8, "height": 6, "sourceHash": source_hash},
    })

    review = result["review"]
    assert review["sourceVerified"] is False
    assert review["artifactVerified"] is True
    assert review["coordinateSpace"] == "saved-preview"
    assert review["reviewSource"] == {
        "kind": "saved-micrograph", "sha256": artifact_hash, "width": 8, "height": 6,
        "sourceHash": source_hash, "coordinateSpace": "saved-preview",
    }


def test_saved_micrograph_review_rejects_a_mismatched_display_frame(saved_preview_review):
    artifact_hash, _ = saved_preview_review
    with pytest.raises(HTTPException, match="dimensions"):
        api._store_review("fixture", {
            "detector": "BSE", "roi": {"x": 0, "y": 0, "width": 2, "height": 2},
            "reviewSource": {"kind": "saved-micrograph", "sha256": artifact_hash, "width": 80, "height": 60},
        })


def test_saved_segmentation_review_binds_roi_to_the_displayed_artifact(tmp_path, monkeypatch):
    official = json.loads(api.HELDOUT.read_text(encoding="utf-8"))
    field_id = official["images"][0]["subject"]["id"]
    evidence = api._saved_segmentation_evidence(official["images"][0])
    assert evidence is not None
    source = api._saved_segmentation_annotation_source(field_id, "overlay", evidence)
    monkeypatch.setattr(api, "REVIEWS_FILE", tmp_path / "reviews.json")
    monkeypatch.setattr(api, "_REVIEWS", {})

    result = api._store_review(field_id, {
        "roi": {"x": 0, "y": 0, "width": 1, "height": 1},
        "reviewSource": {key: source[key] for key in ("kind", "artifact", "sha256", "width", "height", "sourceHash")},
    })

    assert result["review"]["sourceVerified"] is False
    assert result["review"]["artifactVerified"] is True
    assert result["review"]["reviewSource"] == source


def test_native_crop_clamps_source_edge_without_resampling(bound_validation):
    source, _ = bound_validation
    result = api._native_crop(source, 8, 8, 8, 8)
    assert result.headers["x-cottrell-crop"] == "8,8,2,2"
    assert result.headers["x-cottrell-display-resampled"] == "false"

"""Hosted training previews work without claiming access to original TIFFs."""
import csv
import hashlib
import json
from PIL import Image

import pytest
from fastapi import HTTPException

from app import api


@pytest.fixture
def stored_previews(tmp_path, monkeypatch):
    manifest = json.loads((api.ROOT / "results/v1/validation_previews/manifest.json").read_text())
    for metadata in manifest["entries"].values():
        path = tmp_path / metadata["filename"]
        Image.new("RGB", (16, 5), "gray").save(path)
        metadata["preview_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(api, "VALIDATION_PREVIEWS", tmp_path)
    return tmp_path


def test_hosted_validation_keeps_all_fields_and_displays_previews_without_originals(monkeypatch, stored_previews):
    monkeypatch.setattr(api, "_find_source", lambda field, channel: None)
    fields = api.results("validation")["fields"]
    assert {field["id"] for field in fields} == {"b3esycq1", "fzrt2k6r", "71vgq3fw"}
    for field in fields:
        assert len(field["channels"]) == 3
        for channel in field["channels"]:
            assert channel["available"] is False
            assert channel["previewAvailable"] is True
            assert channel["previewKind"] == "saved-micrograph"
            assert channel["previewWidth"] == 1600
            response = api.preview(field["id"], channel["name"])
            assert response.media_type == "image/png"
            assert response.headers["x-cottrell-preview"] == "saved-micrograph"
            with pytest.raises(HTTPException) as error:
                api.raw(field["id"], channel["name"])
            assert error.value.status_code == 404


def test_saved_validation_preview_rejects_changed_png(stored_previews):
    (stored_previews / "b3esycq1_BSE.png").write_bytes(b"changed")
    with pytest.raises(HTTPException) as error:
        api._validation_preview("b3esycq1", "BSE")
    assert error.value.status_code == 409


def test_saved_validation_preview_is_not_reused_for_another_field():
    assert api._validation_preview("3e122cbj", "BSE") is None
    assert api._validation_preview("b3esycq1", "arbitrary-channel") is None


def test_preview_manifest_matches_the_original_training_data_audit():
    with (api.ROOT / "results" / "audit" / "files.csv").open() as handle:
        audit = {(row["sample_id"], row["channel"]): row for row in csv.DictReader(handle)}
    entries = json.loads((api.VALIDATION_PREVIEWS / "manifest.json").read_text())["entries"]
    assert len(entries) == 9
    for key, metadata in entries.items():
        field_id, channel = key.split("_")
        row = audit[(field_id, channel)]
        assert metadata["source_sha256"] == row["sha256"]
        assert (metadata["width"], metadata["height"]) == (int(row["width"]), int(row["height"]))
        assert len(metadata["preview_sha256"]) == 64

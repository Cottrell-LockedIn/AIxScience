import hashlib
import json
from copy import deepcopy

import numpy as np
import tifffile

from app import api


def test_test_set_sources_are_hash_bound_and_duplicate_roots_are_not_ambiguous(tmp_path, monkeypatch):
    source = tmp_path / "img_test0001_BSE.tif"
    tifffile.imwrite(source, np.zeros((4, 4), dtype=np.uint8))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    heldout = tmp_path / "heldout.json"
    test_set = tmp_path / "test.json"
    heldout.write_text(json.dumps({"run": {"file_hashes": {}}}))
    test_set.write_text(json.dumps({"run": {"file_hashes": {"data/heldout_test/img_test0001_BSE.tif": digest}}}))
    monkeypatch.setattr(api, "HELDOUT", heldout)
    monkeypatch.setattr(api, "TEST_SET", test_set)
    monkeypatch.setattr(api, "VALIDATION_DIR", tmp_path / "no-validation")
    monkeypatch.setattr(api, "_source_roots", lambda: [tmp_path, tmp_path])
    api._recorded_files.cache_clear()
    api._find_source.cache_clear()

    try:
        assert api._find_source("test0001", "BSE") == source.resolve()
        tifffile.imwrite(source, np.ones((4, 4), dtype=np.uint8))
        api._find_source.cache_clear()
        assert api._find_source("test0001", "BSE") is None
    finally:
        api._recorded_files.cache_clear()
        api._find_source.cache_clear()


def test_official_heldout_uses_hash_matched_exploratory_mask_with_provenance():
    official = json.loads(api.HELDOUT.read_text(encoding="utf-8"))
    image = next(item for item in official["images"] if item["subject"]["id"] == "3e122cbj")

    evidence = api._saved_segmentation_evidence(image)

    assert evidence is not None
    assert evidence["artifact_provenance"]["source"] == "results/v1_1/heldout_exploratory.json"
    assert evidence["artifact_provenance"]["source_hashes_match_official"] is True
    assert evidence["mask_sha256"] == hashlib.sha256(
        (api.SAVED_MASKS / "3e122cbj_mask.png").read_bytes()
    ).hexdigest()


def test_official_heldout_result_exposes_the_saved_artifact_without_replacing_prediction():
    official = json.loads(api.HELDOUT.read_text(encoding="utf-8"))
    recorded = next(item for item in official["images"] if item["subject"]["id"] == "3e122cbj")

    field = api._normalise(recorded, official["inputs"]["3e122cbj"])

    assert field["predictedBatch"] == recorded["verdict"]["closed_set"]["predicted_batch"]
    assert field["mask"]["overlayUrl"] == "/api/saved-mask/3e122cbj/overlay"
    assert field["mask"]["provenance"]["kind"] == "exploratory replay artifact"


def test_every_official_heldout_field_keeps_its_verdict_and_inputs_with_a_matched_artifact():
    official = json.loads(api.HELDOUT.read_text(encoding="utf-8"))

    for recorded in official["images"]:
        field_id = recorded["subject"]["id"]
        field = api._normalise(recorded, official["inputs"][field_id])

        assert field["predictedBatch"] == recorded["verdict"]["closed_set"]["predicted_batch"]
        assert field["features"] == {
            short: official["inputs"][field_id][full]
            for short, full in api.FEATURE_KEYS.items()
        }
        assert field["mask"]["overlayUrl"] == f"/api/saved-mask/{field_id}/overlay"
        assert field["mask"]["provenance"]["source_hashes_match_official"] is True


def test_official_heldout_rejects_exploratory_artifact_when_a_recorded_source_hash_differs():
    official = json.loads(api.HELDOUT.read_text(encoding="utf-8"))
    recorded = next(item for item in official["images"] if item["subject"]["id"] == "3e122cbj")
    altered = deepcopy(recorded)
    source_name = next(iter(altered["subject"]["file_hashes"]))
    altered["subject"]["file_hashes"][source_name] = "0" * 64

    assert api._saved_segmentation_evidence(altered) is None


def test_official_heldout_rejects_exploratory_artifact_without_recorded_source_hashes():
    official = json.loads(api.HELDOUT.read_text(encoding="utf-8"))
    recorded = next(item for item in official["images"] if item["subject"]["id"] == "3e122cbj")
    altered = deepcopy(recorded)
    altered["subject"]["file_hashes"] = {}

    assert api._saved_segmentation_evidence(altered) is None

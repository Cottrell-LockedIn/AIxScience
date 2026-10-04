import hashlib
import json

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

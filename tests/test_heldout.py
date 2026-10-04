import json
import sys

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from qc import config, features, heldout, tiles


def _mock_git(monkeypatch, frozen=False):
    monkeypatch.setattr(heldout, "_exact_tag", lambda: "v1-frozen" if frozen else None)
    monkeypatch.setattr(heldout, "_is_frozen_tag", lambda: frozen)


def _cfg(heldout_dir):
    return {"_hash": "config-hash", "data": {"heldout_dir": str(heldout_dir)}}


def test_filename_fallback_parser():
    assert heldout.parse_filename("img_sample_with_parts_Inlens.tiff") == (
        "sample_with_parts",
        "Inlens",
    )
    assert heldout.parse_filename("sample_01_unknown.tif") is None


def test_run_once_guard_refuses_existing_output(tmp_path, monkeypatch):
    monkeypatch.setattr(heldout._config, "ROOT", tmp_path)
    _mock_git(monkeypatch, frozen=True)
    output = tmp_path / "results" / "v1" / "heldout.json"
    output.parent.mkdir(parents=True)
    output.write_text("{}")

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        heldout.run(_cfg(tmp_path / "heldout"), out_path=output)


def test_dryrun_requires_explicit_input_dir(tmp_path):
    with pytest.raises(SystemExit, match="--dryrun requires an explicit --input-dir"):
        heldout.run(_cfg(tmp_path / "configured"), dryrun=True)


def test_dryrun_refuses_configured_heldout_dir(tmp_path, monkeypatch):
    _mock_git(monkeypatch)
    configured = tmp_path / "data" / "heldout"

    with pytest.raises(SystemExit, match="cannot be the configured data/heldout"):
        heldout.run(
            _cfg(configured),
            input_dir=configured,
            out_path=tmp_path / "dryrun.json",
            dryrun=True,
        )


def test_dryrun_refuses_unknown_sample_id(tmp_path):
    groups = {"unknown": {"BSE": tmp_path / "unknown_BSE.tif"}}
    with pytest.raises(SystemExit, match="non-training sample ids"):
        heldout._validate_dryrun_inputs(
            tmp_path / "input",
            tmp_path / "configured",
            groups,
            {"training01"},
            {},
        )


def test_dryrun_refuses_bse_sha256_mismatch(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    audit_dir = root / "results" / "audit"
    audit_dir.mkdir(parents=True)
    pd.DataFrame(
        [{"sample_id": "training01", "sha256_BSE": "0" * 64}]
    ).to_csv(audit_dir / "images.csv", index=False)
    monkeypatch.setattr(heldout._config, "ROOT", root)

    source = tmp_path / "input"
    source.mkdir()
    bse_path = source / "training01_BSE.tif"
    bse_path.write_bytes(b"training image")
    bse_key = heldout._file_key(bse_path, root)
    hashes = {bse_key: heldout._sha256(bse_path)}

    with pytest.raises(SystemExit, match="BSE sha256 mismatch"):
        heldout._validate_dryrun_inputs(
            source,
            tmp_path / "configured",
            {"training01": {"BSE": bse_path}},
            {"training01"},
            hashes,
        )


def test_exploratory_refuses_when_canonical_output_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(heldout._config, "ROOT", tmp_path)
    _mock_git(monkeypatch)

    with pytest.raises(SystemExit, match="requires canonical results/v1/heldout.json"):
        heldout.run(_cfg(tmp_path / "heldout"), exploratory=True)


def test_real_run_refuses_noncanonical_output(tmp_path, monkeypatch):
    monkeypatch.setattr(heldout._config, "ROOT", tmp_path)
    _mock_git(monkeypatch, frozen=True)

    with pytest.raises(SystemExit, match="always writes to canonical"):
        heldout.run(_cfg(tmp_path / "heldout"), out_path=tmp_path / "other.json")


def test_file_keys_resolve_under_repo_or_to_absolute_paths(tmp_path):
    repo = tmp_path / "repo"
    inside = repo / "data" / "image.tif"
    outside = tmp_path / "external.tif"

    assert heldout._file_key(inside, repo) == "data/image.tif"
    assert heldout._file_key(outside, repo) == str(outside.resolve())


def test_exploratory_output_is_timestamped_under_exploratory_dir(tmp_path):
    output = heldout._out_path(None, exploratory=True)
    assert output.parent == heldout._config.ROOT / heldout.EXPLORATORY_DIR
    assert output.name.startswith("heldout_")
    assert output.suffix == ".json"


def test_exploratory_accepts_custom_output(tmp_path, monkeypatch):
    monkeypatch.setattr(heldout._config, "ROOT", tmp_path)
    canonical = tmp_path / "results" / "v1" / "heldout.json"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("{}")
    _mock_git(monkeypatch)
    with pytest.raises(SystemExit, match="no images with a BSE TIFF"):
        heldout.run(
            {"_hash": "config-hash", "data": {"heldout_dir": str(tmp_path)}},
            input_dir=tmp_path,
            out_path=tmp_path / "heldout.json",
            exploratory=True,
        )


@pytest.mark.parametrize("alias", [False, True])
def test_exploratory_refuses_canonical_output(tmp_path, monkeypatch, alias):
    monkeypatch.setattr(heldout._config, "ROOT", tmp_path)
    canonical = tmp_path / "results" / "v1" / "heldout.json"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("{}")
    output = tmp_path / "alias.json" if alias else canonical
    if alias:
        output.symlink_to(canonical)
    _mock_git(monkeypatch)
    with pytest.raises(SystemExit, match="cannot be the canonical"):
        heldout.run(_cfg(tmp_path), out_path=output, exploratory=True)
    assert canonical.read_text() == "{}"


def test_segmentation_overlay_palette_offset_and_png_roundtrip(tmp_path):
    cfg = config.load()
    image = np.full((24, 28), 100, dtype=np.uint8)
    cropped = tiles.crop_border(image, 8)
    mask = np.repeat(np.array([[0, 1, 2]], dtype=np.uint8), 4, axis=1).repeat(8, axis=0)
    evidence = heldout._save_segmentation(tmp_path / "out.json", "synthetic", cropped, mask, cfg)
    with Image.open(tmp_path / evidence["mask_path"]) as png:
        np.testing.assert_array_equal(np.asarray(png), mask)
        assert png.mode == "L"
    with Image.open(tmp_path / evidence["overlay_path"]) as png:
        overlay = np.asarray(png)
        assert png.info["exploratory"] == "true"
        assert png.info["phase_identity"] == heldout.classify.PHASE_IDENTITY
    expected = np.array([[[69, 109, 136], [100, 100, 100], [170, 112, 61]]], dtype=np.uint8)
    np.testing.assert_array_equal(overlay, expected.repeat(2, axis=0))
    assert evidence["mask_offset_px"] == [8, 8]
    assert evidence["mask_shape"] == [8, 12]
    assert evidence["mask_sha256"] == heldout._sha256(tmp_path / evidence["mask_path"])
    assert evidence["overlay_downscale"] == 4
    assert evidence["class_values"] == {"0": "void", "1": "graphite", "2": "silicon"}
    assert evidence["exploratory"] is True
    assert "not ground truth" in evidence["note"]
    assert heldout._save_segmentation(tmp_path / "out.json", "synthetic", cropped, mask, cfg) == evidence
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        heldout._save_segmentation(tmp_path / "other.json", "synthetic", cropped, np.ones_like(mask), cfg)


def test_overlay_uses_area_average_and_nearest_labels():
    image = np.array([[0, 100, 0, 100], [100, 200, 100, 200]], dtype=np.uint8)
    mask = np.array([[1, 0, 2, 0], [0, 0, 0, 0]], dtype=np.uint8)
    result = heldout._segmentation_overlay(image, mask, 2)
    np.testing.assert_array_equal(result, [[[100, 100, 100], [170, 112, 61]]])


def test_overlay_rejects_unanalysed_pixels():
    with pytest.raises(ValueError, match="class labels"):
        heldout._segmentation_overlay(np.zeros((2, 2), dtype=np.uint8), np.full((2, 2), 255, dtype=np.uint8), 1)


EXPLORATORY_OUTPUT = config.ROOT / "results" / "v1_1" / "heldout_exploratory.json"
HELDOUT_IDS = ["3e122cbj", "fn0mhxef", "xrv9xvzb"]


@pytest.fixture(scope="module")
def exploratory_output():
    return json.loads(EXPLORATORY_OUTPUT.read_text())


@pytest.mark.parametrize("sample_id", HELDOUT_IDS)
def test_saved_mask_feature_parity(exploratory_output, sample_id):
    cfg = config.load()
    feature_cfg, _ = features._feature_config()
    doc = next(doc for doc in exploratory_output["images"] if doc["subject"]["id"] == sample_id)
    evidence = doc["evidence"]["segmentation_mask"]
    mask_path = EXPLORATORY_OUTPUT.parent / evidence["mask_path"]
    with Image.open(mask_path) as png:
        mask = np.asarray(png)
    assert mask.dtype == np.uint8
    assert set(np.unique(mask)) <= {0, 1, 2}
    assert list(mask.shape) == evidence["mask_shape"]
    assert evidence["mask_sha256"] == heldout._sha256(mask_path)
    recomputed = features.extract_features(mask, **heldout._feature_parameters(cfg, feature_cfg))
    expected = exploratory_output["inputs"][sample_id]
    differences = [abs(recomputed[col] - expected[col]) for col in heldout.classify.F_COLS]
    assert max(differences) <= 1e-9
    with Image.open(EXPLORATORY_OUTPUT.parent / evidence["overlay_path"]) as overlay:
        assert overlay.size == (mask.shape[1] // 4, mask.shape[0] // 4)
        assert overlay.mode == "RGB"
    heldout.classify.validate(doc)


@pytest.mark.parametrize("sample_id", HELDOUT_IDS)
def test_saved_mask_matches_cropped_tiff_shape(exploratory_output, sample_id):
    bse_path = config.ROOT / "data" / "heldout" / f"img_{sample_id}_BSE.tif"
    if not bse_path.is_file():
        pytest.skip("raw held-out TIFFs are not committed")
    cfg = config.load()
    image = tiles.read_gray(bse_path, cfg["data"]["read_channel"])
    doc = next(doc for doc in exploratory_output["images"] if doc["subject"]["id"] == sample_id)
    evidence = doc["evidence"]["segmentation_mask"]
    assert evidence["mask_shape"] == [image.shape[0] - 16, image.shape[1] - 16]
    assert evidence["mask_offset_px"] == [8, 8]
    key = heldout._file_key(bse_path, config.ROOT)
    assert heldout._sha256(bse_path) == doc["subject"]["file_hashes"][key]


@pytest.mark.parametrize("sample_id", HELDOUT_IDS)
def test_exploratory_verdict_and_inputs_match_official(exploratory_output, sample_id):
    official = json.loads((config.ROOT / "results" / "v1" / "heldout.json").read_text())
    normalized = json.loads(json.dumps(exploratory_output).replace(
        "results/v1_1/heldout_exploratory.json", "results/v1/heldout.json"
    ))
    doc = next(doc for doc in normalized["images"] if doc["subject"]["id"] == sample_id)
    original = next(doc for doc in official["images"] if doc["subject"]["id"] == sample_id)
    for key in ("verdict", "acquisition", "routing", "uncertainty"):
        assert json.dumps(doc[key], sort_keys=True) == json.dumps(original[key], sort_keys=True)
    assert json.dumps(normalized["inputs"][sample_id], sort_keys=True) == json.dumps(official["inputs"][sample_id], sort_keys=True)
    for key in original["evidence"]:
        assert json.dumps(doc["evidence"][key], sort_keys=True) == json.dumps(original["evidence"][key], sort_keys=True)
    assert doc["pipeline"]["exploratory"] is True


def test_local_cpu_fallback_logs_modal_run_when_app_cannot_import(monkeypatch):
    rows = []
    payloads = [{"sample_id": "sample01", "tiles": np.zeros((1, 1024, 1024), dtype=np.uint8)}]

    def fake_local_cpu(cfg, payloads):
        return {"sample01": np.zeros((1, 384), dtype=np.float32)}, 1.25

    monkeypatch.setitem(sys.modules, "modal_app", None)
    monkeypatch.setattr(heldout, "_embed_local_cpu", fake_local_cpu)
    monkeypatch.setattr(
        heldout,
        "_append_modal_run",
        lambda cfg, columns, **kwargs: rows.append((columns, kwargs)),
    )

    vectors, run = heldout._embedding_vectors({"_hash": "hash", "embeddings": {}}, payloads)

    assert run["embedding_backend"] == "local_cpu_fallback"
    assert run["embedding_error"].startswith("RuntimeError: modal_app could not be imported")
    assert vectors["sample01"].shape == (1, 384)
    assert len(rows) == 1
    assert rows[0][0] == heldout.V1_MODAL_RUN_COLUMNS
    assert rows[0][1]["cost"] == 0.0
    assert rows[0][1]["hardware"] == "local-cpu fallback"


def test_frozen_real_modal_failure_does_not_fallback_to_cpu(monkeypatch):
    payloads = [{"sample_id": "sample01", "tiles": np.zeros((1, 1024, 1024), dtype=np.uint8)}]
    monkeypatch.setitem(sys.modules, "modal_app", None)
    monkeypatch.setattr(
        heldout,
        "_embed_local_cpu",
        lambda *args: pytest.fail("real inference must not use CPU fallback"),
    )

    with pytest.raises(SystemExit, match="CPU fallback is disabled"):
        heldout._embedding_vectors(
            {"_hash": "hash", "embeddings": {}},
            payloads,
            allow_local_fallback=False,
        )

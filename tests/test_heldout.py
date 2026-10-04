import sys

import numpy as np
import pandas as pd
import pytest

from qc import heldout


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

    with pytest.raises(SystemExit, match="exploratory output path is generated automatically"):
        heldout.run(
            {"_hash": "config-hash", "data": {"heldout_dir": str(tmp_path)}},
            input_dir=tmp_path,
            out_path=tmp_path / "heldout.json",
            exploratory=True,
        )


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

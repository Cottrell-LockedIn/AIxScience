import sys

import numpy as np
import pytest

from qc import heldout


def test_filename_fallback_parser():
    assert heldout.parse_filename("img_sample_with_parts_Inlens.tiff") == (
        "sample_with_parts",
        "Inlens",
    )
    assert heldout.parse_filename("sample_01_unknown.tif") is None


def test_run_once_guard_refuses_existing_output(tmp_path):
    output = tmp_path / "heldout.json"
    output.write_text("{}")

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        heldout.run(
            {"_hash": "config-hash", "data": {"heldout_dir": str(tmp_path)}},
            input_dir=tmp_path,
            out_path=output,
        )


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

import pandas as pd

import modal_app


def test_append_modal_run_preserves_legacy_string_fields(tmp_path, monkeypatch):
    results = tmp_path / "results"
    results.mkdir()
    path = results / "MODAL_RUNS.csv"
    original = {
        "timestamp_utc": "2025-01-02T03:04:05+00:00",
        "function": "existing",
        "n_inputs": "2",
        "wall_s": "1.25",
        "hardware": "L4",
        "git_sha": "20e3371",
        "config_hash": "45629944e398",
        "est_cost_usd": "0.1234567890123456789",
        "cost_source": "pricing",
    }
    pd.DataFrame([original]).to_csv(path, index=False)
    monkeypatch.setattr(modal_app._config, "ROOT", tmp_path)
    monkeypatch.setattr(modal_app._config, "git_sha", lambda: "abcdef0")

    modal_app._append_modal_run(
        {"_hash": "new-config-hash"},
        "new",
        1,
        0.5,
        "L4",
        0.25,
    )

    result = pd.read_csv(path, dtype=str, keep_default_na=False)
    for column, value in original.items():
        assert result.loc[0, column] == value
    assert result.loc[0, "local_remote_max_abs_diff"] == ""
    assert result.loc[0, "repeat_max_abs_diff"] == ""
    assert result.loc[1, "git_sha"] == "abcdef0"
    assert result.loc[1, "config_hash"] == "new-config-hash"

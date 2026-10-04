from app import model_accuracy


def test_model_accuracy_uses_committed_loio_values():
    model_accuracy.model_accuracy_payload.cache_clear()
    payload = model_accuracy.model_accuracy_payload()
    assert payload["loio"]["accuracy_label"] == "18/31"
    assert payload["loio"]["wilson95"] == [0.4076626249536972, 0.7358445693268778]
    assert payload["loio"]["permutation"]["p"] == 0.03496503496503497
    assert payload["loio"]["balanced_accuracy"] == 0.46498599439775906
    assert payload["loio"]["majority_baseline"] == {"label": "17/31", "correct": 17, "total": 31}
    assert payload["loio"]["confusion"]["values"] == [[2, 4, 1], [4, 2, 1], [0, 3, 14]]


def test_model_accuracy_keeps_documented_heldout_separate_from_loio():
    payload = model_accuracy.model_accuracy_payload()
    assert payload["heldout"]["status"].startswith("official once-only")
    assert payload["heldout"]["correct"] == 2
    assert payload["heldout"]["status"].startswith("official once-only")
    assert "incorrect at tier high" in payload["heldout"]["confidence_scoring_rubric"]
    assert payload["exploratory_six_image_run"]["n_predictions"] == 6


def test_model_accuracy_provenance_hashes_all_fixed_sources():
    payload = model_accuracy.model_accuracy_payload()
    sources = payload["provenance"]["sources"]
    assert any(item["path"] == "results/v1/accuracy_tab/metrics.json" for item in sources)
    assert all(len(str(item["sha256"])) == 64 for item in sources)


def test_saved_figure_allowlist_rejects_paths_and_only_returns_committed_png():
    response = model_accuracy.get_model_accuracy_figure("confusion_matrix")
    assert str(response.path).endswith("results/v1/accuracy_tab/figures/confusion_matrix.png")
    try:
        model_accuracy.get_model_accuracy_figure("../../heldout")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Unsafe figure path was accepted")

import json

import pandas as pd

from qc import accuracy_tab, classify
from qc.config import ROOT


def test_judging_score_rule():
    assert accuracy_tab.judging_score(True, "high") == 2
    assert accuracy_tab.judging_score(False, "high") == 0
    assert accuracy_tab.judging_score(False, "low") == 1
    assert accuracy_tab.judging_score(True, "low") == 1
    assert accuracy_tab.judging_score(True, "medium") == 1


def test_metrics_match_loio_summary_and_regenerate(tmp_path):
    m = accuracy_tab.build(tmp_path)
    summary = json.loads((ROOT / accuracy_tab.LOIO_SUMMARY).read_text())
    assert m["overall"]["accuracy"]["str"] == summary["loio_accuracy_str"] == "18/31"
    assert m["confusion_matrix"]["values"] == summary["confusion_matrix"]["values"]
    for b in classify.BATCHES:
        assert m["per_batch"][b]["recall"]["str"] == summary["per_batch_recall"][b]
        assert m["per_batch"][b]["precision"]["str"] == summary["precision_by_pred_batch"][b]
    for t in ("high", "medium", "low"):
        assert m["by_tier"][t]["str"] == summary["accuracy_by_tier"][t]
    assert m["overall"]["permutation_p"] == summary["permutation_p"]
    assert m["reference_vs_rest"]["precision"]["str"] == "14/16"
    assert m["reference_vs_rest"]["recall_sensitivity"]["str"] == "14/17"
    assert m["heldout"]["accuracy"]["str"] == "2/3" and m["heldout"]["judging_score"]["str"] == "5/6"
    assert m["phase_identity"] == classify.PHASE_IDENTITY
    for rel in list(m["figures"].values()) + list(m["tables"].values()) + ["metrics.json", "EXPLANATION.md", "preview.html"]:
        assert (tmp_path / rel).exists(), rel
    committed = json.loads((ROOT / accuracy_tab.OUT_DIR / "metrics.json").read_text())
    for doc in (m, committed):
        doc.pop("provenance")
    assert json.dumps(m, sort_keys=True) == json.dumps(committed, sort_keys=True)
    heldout = pd.read_csv(tmp_path / "tables" / "heldout.csv")
    assert heldout["judging_score"].sum() == 5 and len(heldout) == 3

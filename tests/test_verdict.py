"""Decision-layer unit checks: rule precedence, ledger append-only, schema validity."""
import json

import numpy as np
import pandas as pd

from qc import verdict


def _ood(matches_none=False, in_ref=True, nearest="Batch_3", inside="Batch_3"):
    return pd.Series({"d_Batch_1": 2.0, "d_Batch_2": 2.0, "d_Batch_3": 1.0, "p_Batch_3": 0.5, "n_ref_Batch_3": 16,
                      "nearest_batch": nearest, "in_distribution_of": inside, "matches_none": matches_none, "in_reference": in_ref})


def _pred(b="Batch_3"):
    return pd.Series({"pred": b, "p_Batch_1": 0.1, "p_Batch_2": 0.1, "p_Batch_3": 0.8})


def _z(**kw):
    z = pd.Series({c: 0.0 for c in ["F01_a", "F02_b", "F08_c", "F05_d"]})
    for k, v in kw.items():
        z[k] = v
    return z


def test_rule_precedence():
    args = dict(confounded={}, cov_block={}, n_flags=0, flag_names=[], fam="material", agree=(2, 2), sens={})
    d = verdict.decide_image("s", "Batch_3", _pred(), _ood(), _z(), **args)
    assert d["verdict"]["label"] == "within_bounds" and d["routing"]["stakeholder"] == "none"
    d = verdict.decide_image("s", "Batch_1", _pred(), _ood(), _z(F01_a=4.0), **args)
    assert d["verdict"]["label"] == "investigate" and "second" in d["next_action"]
    d = verdict.decide_image("s", "Batch_1", _pred(), _ood(), _z(F01_a=4.0, F05_d=-3.5), **args)
    assert d["verdict"]["label"] == "outside_bounds" and d["routing"]["stakeholder"] == "powder_supplier"
    # a confounded feature cannot form a line
    d = verdict.decide_image("s", "Batch_1", _pred(), _ood(), _z(F01_a=4.0, F05_d=-3.5), **{**args, "confounded": {"F05_d": True}})
    assert d["verdict"]["label"] == "investigate"
    # acquisition drift demotes everything to investigate and routes to the microscopy team
    d = verdict.decide_image("s", "Batch_1", _pred(), _ood(), _z(F01_a=4.0, F05_d=-3.5),
                             **{**args, "n_flags": 2, "flag_names": ["noise_sigma", "sharpness"]})
    assert d["verdict"]["label"] == "investigate" and d["routing"]["stakeholder"] == "microscopy_team"
    d = verdict.decide_image("s", None, None, _ood(matches_none=True, in_ref=False, inside="none"), _z(), **args)
    assert d["verdict"]["label"] == "investigate" and "EDS" in d["next_action"]


def test_ledger_append_only_and_schema(tmp_path):
    p = tmp_path / "ledger.jsonl"
    verdict.append_ledger(p, {"a": 1, "x": np.float64(2.5)})
    verdict.append_ledger(p, {"b": 2})
    lines = p.read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[0]) == {"a": 1, "x": 2.5}
    from qc import config as _config
    d = verdict.decide_image("s", "Batch_3", _pred(), _ood(), _z(), confounded={}, cov_block={}, n_flags=0, flag_names=[],
                             fam="material", agree=(1, 1), sens={})
    assert verdict.CANNOT_DECIDE[0].startswith("phase_identity: stated by Polaron, not image-verified")
    d["pipeline"] = {"git_sha": "x", "config_path": "c", "config_hash": "h", "timestamp_utc": "t", "frozen": False}
    verdict.validate_schema(d, _config.ROOT / "schema" / "verdict.schema.json")


def test_batch_verdict_has_reason_sentence_and_stats_evidence():
    from qc import config as _config

    doc = verdict.batch_verdict(
        "Batch_1",
        [{"verdict": {"label": "investigate", "open_set": {"matches_known_batch": True}},
          "evidence": {"lines_fired": {}}, "acquisition": {"acquisition_drift_suspected": False}}],
        {"git_sha": "x", "config_path": "c", "config_hash": "h", "timestamp_utc": "t", "frozen": False},
    )
    refs = doc["evidence"]["stats_pair_tests"]
    assert len(refs) == 5
    assert {ref["pair"] for ref in refs} == {"Batch_1 vs Batch_3"}
    assert all(ref["path"] == f"results/stats/{ref['table']}/pair_tests.csv" for ref in refs)
    assert doc["routing"]["reason"].startswith("The Batch_1 batch is labeled investigate because ")
    assert doc["routing"]["reason"].endswith(".")
    verdict.validate_schema(doc, _config.ROOT / "schema" / "verdict.schema.json")

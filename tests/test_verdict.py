import json

import pandas as pd
import pytest

from qc import config as _config
from qc.verdict import (
    RULE_CONSTANTS,
    build_verdicts,
    decide_verdict,
    validate_documents,
    validate_evidence_selectors,
)


def _synthetic_stats(
    features,
    statuses,
    *,
    drift=False,
    energy_p=0.8,
    energy_band="within",
    mmd_p=0.8,
    mmd_band="within",
    embedding_gates=(False, True, True),
    loo_rows=None,
):
    pair = "Batch_1_vs_Batch_3"
    feature_rows = []
    status_rows = []
    for feature, family, z, p_bh, band_position, status in features:
        feature_rows.append({
            "table": "features",
            "feature": feature,
            "family": family,
            "pair": pair,
            "z": z,
            "p_bh": p_bh,
            "band_position": band_position,
        })
    for feature, family, status in statuses:
        status_rows.append({
            "table": "features",
            "feature": feature,
            "family": family,
            "status": status,
        })
    distance_rows = []
    for statistic, p_bh, band_position in (
        ("energy", energy_p, energy_band),
        ("mmd2", mmd_p, mmd_band),
    ):
        distance_rows.append({
            "table": "emb_BSE",
            "statistic": statistic,
            "batch_a": "Batch_1",
            "batch_b": "Batch_3",
            "residualised": False,
            "value": 1.0,
            "p_bh": p_bh,
            "band_position": band_position,
        })
    return {
        "feature_contrasts": pd.DataFrame(feature_rows),
        "feature_status": pd.DataFrame(status_rows),
        "distance_matrix": pd.DataFrame(distance_rows),
        "embedding_gates": pd.DataFrame([{
            "channel": "BSE",
            "pair": pair,
            "G1": embedding_gates[0],
            "G2": embedding_gates[1],
            "G4": embedding_gates[2],
        }]),
        "acquisition_drift": pd.DataFrame([{
            "pair": pair,
            "drift": drift,
            "drifting_covariates": "[]",
        }]),
        "covariate_contrasts": pd.DataFrame(
            columns=["pair", "feature", "p_bh"]
        ),
        "reference_loo": pd.DataFrame(
            loo_rows or [],
            columns=["table", "feature", "family", "sample_id", "robust_z", "outlier"],
        ),
    }


def test_verdict_rule_constants_are_preregistered_sentences():
    preregistration = (
        _config.ROOT / "docs" / "PHASE_B_PREREGISTRATION.md"
    ).read_text()

    for rule in RULE_CONSTANTS:
        assert rule in preregistration


@pytest.mark.parametrize(
    ("features", "statuses", "drift", "expected"),
    [
        (
            [
                ("F01_c0_area_fraction", "phase_fraction", 3.0, 0.001, "outside", "keep"),
                ("F05_c2_count_density_per_Mpx", "silicon_particle", 2.5, 0.002, "outside", "keep"),
            ],
            [
                ("F01_c0_area_fraction", "phase_fraction", "keep"),
                ("F05_c2_count_density_per_Mpx", "silicon_particle", "keep"),
            ],
            False,
            "outside_bounds",
        ),
        (
            [("F01_c0_area_fraction", "phase_fraction", 0.1, 0.8, "within", "investigate")],
            [("F01_c0_area_fraction", "phase_fraction", "investigate")],
            False,
            "within_bounds",
        ),
        (
            [("F01_c0_area_fraction", "phase_fraction", 2.0, 0.01, "outside", "investigate")],
            [("F01_c0_area_fraction", "phase_fraction", "investigate")],
            False,
            "investigate",
        ),
        (
            [("F01_c0_area_fraction", "phase_fraction", 0.1, 0.8, "within", "keep")],
            [("F01_c0_area_fraction", "phase_fraction", "keep")],
            True,
            "investigate",
        ),
    ],
)
def test_synthetic_nonreference_verdict_labels(features, statuses, drift, expected):
    stats = _synthetic_stats(features, statuses, drift=drift)

    assert decide_verdict("Batch_1", stats)["label"] == expected


def test_batch_3_reference_rule_investigates_multiple_families_and_never_exits():
    stats = _synthetic_stats([], [], loo_rows=[
        {
            "table": "features",
            "feature": "F01_c0_area_fraction",
            "family": "phase_fraction",
            "sample_id": "abcdefgh",
            "robust_z": 4.0,
            "outlier": True,
        },
        {
            "table": "features",
            "feature": "F05_c2_count_density_per_Mpx",
            "family": "silicon_particle",
            "sample_id": "abcdefgh",
            "robust_z": -4.2,
            "outlier": True,
        },
    ])

    decision = decide_verdict("Batch_3", stats)

    assert decision["label"] == "investigate"
    assert decision["label"] != "outside_bounds"


@pytest.fixture(scope="module")
def generated_verdicts():
    return build_verdicts(_config.load())


def test_generated_verdicts_validate_schema_and_exclude_classifier_fields(generated_verdicts):
    schema = (_config.ROOT / "schema" / "verdict.schema.json").read_text()
    validate_documents(generated_verdicts, json.loads(schema))
    assert {doc["subject"]["batch"] for doc in generated_verdicts} == {
        "Batch_1", "Batch_2", "Batch_3"
    }
    for document in generated_verdicts:
        assert document["pipeline"]["exploratory"] is True
        assert document["pipeline"]["frozen"] is False
        assert "closed_set" not in document["verdict"]
        assert "open_set" not in document["verdict"]
        assert document["verdict"]["justification"]["evidence"]
        assert document["acquisition"]["drift_justification"]["evidence"]
        for driver in document["evidence"]["drivers"]:
            assert driver["justification"]["evidence"]
            assert driver["justification"]["numbers"]
        for covariate in document["acquisition"]["covariates"].values():
            assert covariate["justification"]["evidence"]
            assert covariate["justification"]["numbers"]
            expected_flag = (
                covariate["value"] < covariate["training_p05"]
                or covariate["value"] > covariate["training_p95"]
            )
            assert covariate["flag"] is expected_flag
    assert generated_verdicts[2]["verdict"]["label"] != "outside_bounds"


def test_every_generated_selector_executes_and_matches_its_numbers(generated_verdicts):
    validate_evidence_selectors(generated_verdicts)

    selectors = []

    def collect(item):
        if isinstance(item, dict):
            if {"file", "selector"}.issubset(item):
                selectors.append(item)
            else:
                for value in item.values():
                    collect(value)
        elif isinstance(item, list):
            for value in item:
                collect(value)

    collect(generated_verdicts)
    assert selectors
    assert all(item["numbers"] for item in selectors)

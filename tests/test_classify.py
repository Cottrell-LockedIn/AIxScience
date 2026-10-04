import json

import jsonschema
import numpy as np
import pytest

from qc import classify, config as _config


def test_e1_matches_hand_computed_two_point_reference():
    value = classify.e1(np.array([0.0, 0.0]), np.array([[1.0, 0.0], [0.0, 1.0]]))
    assert value == pytest.approx(2.0 - np.sqrt(2.0))


@pytest.mark.parametrize(
    ("p_max", "perm_p", "ood_label", "expected"),
    [
        (0.49, 0.01, "within_bounds", "low"),
        (0.90, 0.05, "within_bounds", "low"),
        (0.90, 0.01, "outside_bounds", "low"),
        (0.70, 0.01, "within_bounds", "medium"),
        (0.75, 0.01, "within_bounds", "high"),
    ],
)
def test_tier_table(p_max, perm_p, ood_label, expected):
    assert classify.tier(p_max, perm_p, ood_label)[0] == expected


def test_fit_transform_fits_only_on_training_rows():
    rng = np.random.default_rng(2)
    xf = rng.normal(size=(31, len(classify.F_COLS)))
    xe = rng.normal(size=(31, len(classify.EMB_COLS)))
    train_indices = np.arange(1, 31)
    scaler_before, pca_before, z_before = classify.fit_transform(
        xf[train_indices], xe[train_indices]
    )

    xf[0] += 10_000
    xe[0] -= 10_000
    scaler_after, pca_after, z_after = classify.fit_transform(
        xf[train_indices], xe[train_indices]
    )

    np.testing.assert_array_equal(scaler_before.mean_, scaler_after.mean_)
    np.testing.assert_array_equal(scaler_before.scale_, scaler_after.scale_)
    np.testing.assert_array_equal(pca_before.mean_, pca_after.mean_)
    np.testing.assert_array_equal(pca_before.components_, pca_after.components_)
    np.testing.assert_array_equal(z_before, z_after)


def _image_document():
    pred = {
        "pred_batch": "Batch_3",
        "runner_up": "Batch_1",
        "probabilities": {"Batch_1": 0.1, "Batch_2": 0.1, "Batch_3": 0.8},
        "confidence": 0.8,
        "margin": 0.7,
        "drivers": [
            {
                "name": "embedding PC 1",
                "units": "PC score",
                "value": 1.0,
                "standardised_value": 1.0,
                "coefficient": 0.5,
                "effect_size": 0.5,
                "direction": "higher",
                "tag": classify.EMBEDDING_TAG,
            }
        ],
    }
    ood_result = {
        "label": "within_bounds",
        "e1_to_batch3": 0.1,
        "band95": 0.2,
        "band99": 0.3,
        "n_reference": 17,
        "null_max": 0.25,
        "matches_known_batch": True,
        "distance_to_each_batch": {"Batch_1": 0.2, "Batch_2": 0.3, "Batch_3": 0.1},
        "nearest_batch": "Batch_3",
        "margin_to_band99": 0.2,
    }
    return classify.image_document(
        sample_id="sample01",
        true_batch=None,
        n_tiles=1,
        pred=pred,
        ood_res=ood_result,
        perm_p=0.01,
        loio_k=18,
        loio_n=31,
        covariates={},
        detectors=["BSE"],
        evidence_file="results/v1/heldout.json",
        selector="images[subject.id == 'sample01']",
        cfg=_config.load(),
        frozen=False,
        exploratory=True,
        git_tag=None,
        kind_note="held-back image",
    )


def test_image_document_requires_closed_set_prediction():
    document = _image_document()
    del document["verdict"]["closed_set"]["predicted_batch"]

    with pytest.raises(jsonschema.ValidationError):
        classify.validate(document)


def test_phase_b_batch_verdicts_remain_valid():
    schema = json.loads((_config.ROOT / "schema" / "verdict.schema.json").read_text())
    for path in sorted((_config.ROOT / "results" / "verdicts").glob("*.json")):
        document = json.loads(path.read_text())
        jsonschema.validate(document, schema)

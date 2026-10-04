import numpy as np
import pandas as pd
import pytest

from qc import stats as stats_module
from qc.stats import (
    PAIR_ORDER,
    _embedding_permutation_tests,
    _exact_split_plan,
    _make_distance_matrix,
    _median_pairwise_distance,
    _parse_loo_outlier_ids,
    _plan_subset,
    _pair_name,
    _record_scalar_row,
    _split_embedding_bands,
    _unique_null_bands,
    pairwise_distance_matrix,
    permutation_test_z,
    residualize,
    validate_image_table,
)


def test_planted_median_shift_is_detected():
    values_a = np.arange(10.0, 18.0)
    values_b = np.arange(8.0)

    z, p_value = permutation_test_z(
        values_a, values_b, scale=1.0, seed=20261003, n_permutations=2000
    )

    assert z > 0
    assert p_value < 0.05


def test_identical_distributions_are_not_detected():
    values = np.arange(8.0)

    z, p_value = permutation_test_z(
        values, values.copy(), scale=1.0, seed=20261003, n_permutations=2000
    )

    assert z == 0
    assert p_value == 1


def test_pairwise_distance_matrix_is_symmetric_with_zero_diagonal():
    matrix = pairwise_distance_matrix([[0, 0], [3, 4], [2, 1]])

    np.testing.assert_allclose(matrix, matrix.T)
    np.testing.assert_array_equal(np.diag(matrix), np.zeros(3))


def test_reported_distance_matrix_is_symmetric_with_zero_diagonal():
    records = []
    for pair_index, pair in enumerate(PAIR_ORDER):
        records.append({
            "table": "kpi",
            "statistic": "rms_z",
            "residualised": False,
            "pair": _pair_name(*pair),
            "value": float(pair_index + 1),
            "p_perm": 0.2,
            "p_bh": 0.3,
            "band95": 1.0,
            "band99": 2.0,
            "band_position": "within",
        })
    table_counts = {
        table: {"Batch_1": 7, "Batch_2": 7, "Batch_3": 17}
        for table in ("kpi", "features", "emb_BSE", "emb_Inlens", "emb_ETD", "covariates")
    }

    matrix = _make_distance_matrix(records, table_counts, {})
    selected = matrix.loc[
        (matrix["table"] == "kpi")
        & (matrix["statistic"] == "rms_z")
        & ~matrix["residualised"]
    ]
    values = selected.pivot(index="batch_a", columns="batch_b", values="value")

    np.testing.assert_allclose(values.to_numpy(), values.to_numpy().T)
    np.testing.assert_array_equal(np.diag(values), np.zeros(3))


def test_pair_permutation_plan_uses_only_the_requested_pair_images():
    plan = {
        "ids": ["image_a", "image_b"],
        "priorities": np.asarray([[0.2, 0.8]]),
    }

    ids, priorities = _plan_subset(
        plan, ["image_a", "image_b", "image_c"]
    )

    assert ids == ["image_a", "image_b"]
    np.testing.assert_array_equal(priorities, [[0.2, 0.8]])


def test_null_bands_are_unique_per_statistic_and_table():
    row = {
        "table": "kpi",
        "feature": "",
        "channel": "",
        "statistic": "rms_z",
        "residualised": False,
        "band95": 1.0,
        "band99": 2.0,
    }

    bands = _unique_null_bands([row, row.copy()])

    assert len(bands) == 1


def test_duplicate_image_ids_are_rejected():
    frame = pd.DataFrame({
        "sample_id": ["img00001", "img00001"],
        "batch": ["Batch_1", "Batch_1"],
        "value": [1.0, 2.0],
    })

    with pytest.raises(ValueError, match="duplicate image keys"):
        validate_image_table(frame, "synthetic")


def test_covariate_driven_shift_vanishes_after_residualisation():
    covariate = np.arange(20.0)
    values = 4.5 * covariate + 2.0

    residuals = residualize(values, covariate[:, None])

    np.testing.assert_allclose(residuals, 0.0, atol=1e-12)


def test_tile_level_data_is_rejected():
    frame = pd.DataFrame({
        "sample_id": ["img00001", "img00001"],
        "batch": ["Batch_1", "Batch_1"],
        "tile_id": ["tile0001", "tile0002"],
        "y": [0, 0],
        "x": [0, 1],
    })

    with pytest.raises(ValueError, match="tile-level"):
        validate_image_table(frame, "synthetic_tiles")


def test_embedding_observed_permutations_and_null_share_bandwidth(monkeypatch):
    frame = pd.DataFrame({
        "sample_id": ["a1", "a2", "b1", "b2"],
        "batch": ["Batch_1", "Batch_1", "Batch_3", "Batch_3"],
    })
    vectors = np.asarray([
        [1.0, 0.0], [0.8, 0.6], [0.0, 1.0], [0.6, 0.8],
    ])
    ids = frame["sample_id"].tolist()
    plan = {
        "ids": ids,
        "priorities": np.asarray([
            [0.1, 0.2, 0.3, 0.4],
            [0.4, 0.3, 0.2, 0.1],
            [0.2, 0.4, 0.1, 0.3],
        ]),
        "batch_a": "Batch_1",
        "batch_b": "Batch_3",
    }
    bandwidth = _median_pairwise_distance(vectors)
    seen = []
    original = stats_module._rbf_kernel

    def record_bandwidth(received_vectors, received_bandwidth):
        seen.append(received_bandwidth)
        return original(received_vectors, received_bandwidth)

    monkeypatch.setattr(stats_module, "_rbf_kernel", record_bandwidth)
    tested = _embedding_permutation_tests(frame, vectors, plan, bandwidth)
    null = _split_embedding_bands(
        vectors,
        ids,
        [(["a1", "a2"], ["b1", "b2"])],
        bandwidth,
    )

    assert len(tested["permuted"]["mmd2"]) == 3
    assert set(null) == {"energy", "mmd2"}
    assert seen == [bandwidth, bandwidth]


def test_exact_split_plan_enumerates_registered_reference_splits():
    bse_splits = _exact_split_plan(
        [f"b3_{index}" for index in range(17)], 7, 10
    )
    etd_splits = _exact_split_plan(
        [f"etd_{index}" for index in range(14)], 7, 7
    )

    assert bse_splits is not None and len(bse_splits) == 19_448
    assert etd_splits is not None and len(etd_splits) == 3_432


def test_empty_loo_ids_survive_csv_round_trip(tmp_path):
    raw = {
        "z": 0.0, "p": 1.0, "median_a": 1.0, "median_b": 1.0, "n_a": 7, "n_b": 17,
    }
    row = _record_scalar_row(
        "features", "F08", "void_morphology", "Batch_1_vs_Batch_3",
        raw, raw, 1.0, 1.0, 2.0, [], raw, 0.0, 0.0, "0/7",
        1.0, 2.0, "within", 0.0,
    )
    path = tmp_path / "feature_contrasts.csv"
    pd.DataFrame([row]).to_csv(path, index=False)
    round_tripped = pd.read_csv(path)

    assert round_tripped.loc[0, "loo_outlier_ids"] == "none"
    assert _parse_loo_outlier_ids(round_tripped.loc[0, "loo_outlier_ids"]) == []

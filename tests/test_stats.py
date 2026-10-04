import numpy as np
import pandas as pd
import pytest

from qc.stats import (
    PAIR_ORDER,
    _make_distance_matrix,
    _pair_name,
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

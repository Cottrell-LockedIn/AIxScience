"""Image-level statistics tests with deterministic synthetic batches."""
import numpy as np
import pandas as pd
import pytest
from scipy.stats import energy_distance
from scipy.spatial.distance import pdist, squareform

from qc import stats


def synthetic_batches(seed=0, shift=0.0, spreads=(1.0, 1.0, 1.0)):
    rng = np.random.default_rng(seed)
    rows = []
    for batch, n, loc, scale in (
        ("Batch_1", 7, shift, spreads[0]),
        ("Batch_2", 7, 0.0, spreads[1]),
        ("Batch_3", 17, 0.0, spreads[2]),
    ):
        values = rng.normal(loc=loc, scale=scale, size=(n, 4))
        for i, row in enumerate(values):
            rows.append({"sample_id": f"{batch}-{i:02d}", "batch": batch,
                         **{f"f{j}": value for j, value in enumerate(row)}})
    return pd.DataFrame(rows)


def test_planted_shift_is_detected_by_permutation_and_reference_band():
    out = stats.analyze_table(synthetic_batches(seed=7, shift=5.0), n_perm=199, n_null_splits=200, seed=3, n_jobs=1)
    row = out["pair_tests"].query("pair == 'Batch_1 vs Batch_3' and metric == 'median_shift'").iloc[0]
    assert row.p_perm < 0.05
    assert row.above_p99


def test_no_shift_has_non_significant_fixed_seed_permutation():
    out = stats.analyze_table(synthetic_batches(seed=17), n_perm=199, n_null_splits=200, seed=5, n_jobs=1)
    row = out["pair_tests"].query("pair == 'Batch_1 vs Batch_3' and metric == 'median_shift'").iloc[0]
    assert row.p_perm > 0.05


def test_distance_matrix_is_symmetric_with_zero_diagonal():
    out = stats.analyze_table(synthetic_batches(seed=4), n_perm=19, n_null_splits=20, seed=2, n_jobs=1)
    matrix = out["distance_matrix"]
    for metric in stats.METRICS:
        square = matrix.loc[matrix.metric == metric].pivot(index="batch_a", columns="batch_b", values="value")
        np.testing.assert_allclose(square.to_numpy(), square.to_numpy().T)
        np.testing.assert_allclose(np.diag(square), 0.0)


def test_one_dimensional_energy_distance_matches_scipy_squared():
    x = np.array([-1.0, 0.5, 2.0, 4.0])
    y = np.array([0.0, 1.5, 3.0])
    assert stats.energy_distance_v_statistic(x, y) == pytest.approx(energy_distance(x, y) ** 2)


def test_lower_spread_batch_ranks_first():
    df = synthetic_batches(seed=9, spreads=(0.1, 1.0, 2.0))
    values = df[[f"f{i}" for i in range(4)]].to_numpy()
    med = np.median(values, axis=0)
    scale = 1.4826 * np.median(np.abs(values - med), axis=0)
    z = (values - med) / scale
    distances = squareform(pdist(z))
    ranked = stats.consistency_statistics(df.batch.to_numpy(), distances)
    assert ranked.iloc[0].batch == "Batch_1"
    assert ranked.iloc[0]["rank"] == 1


def test_duplicate_sample_id_is_rejected():
    df = synthetic_batches(seed=1)
    df.loc[1, "sample_id"] = df.loc[0, "sample_id"]
    with pytest.raises(ValueError, match="one non-null row per unique sample_id"):
        stats.analyze_table(df, n_perm=5, n_null_splits=5, n_jobs=1)


def test_permutation_outputs_are_deterministic_across_worker_counts():
    df = synthetic_batches(seed=11, shift=1.5)
    serial = stats.analyze_table(df, n_perm=29, n_null_splits=30, seed=21, n_jobs=1)
    parallel = stats.analyze_table(df, n_perm=29, n_null_splits=30, seed=21, n_jobs=2)
    pd.testing.assert_frame_equal(serial["pair_tests"], parallel["pair_tests"])
    pd.testing.assert_frame_equal(serial["null_bands"], parallel["null_bands"])

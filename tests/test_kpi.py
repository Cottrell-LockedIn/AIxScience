import numpy as np

from qc import kpi


def test_flake_and_crack_kpis():
    lab = np.ones((64, 64), dtype=np.uint8)
    lab[5:7, 5:25] = 0
    lab[30:35, 30:35] = 0

    values = kpi.kpis(lab, crack_aspect_min=5.0, tpc_max_r_px=24)

    assert values["c1_largest_component_frac"] == 1.0
    assert values["c1_flake_eqdiam_median_px"] > 0
    assert values["c1_flake_aspect_median"] >= 1
    assert np.isclose(values["c0_cracklike_frac"], 40 / 65)
    assert np.isnan(values["c2_tpc_length_px"])


def test_tpc_length_handles_constant_and_finite_indicators():
    assert np.isnan(kpi.tpc_length(np.zeros((32, 32), dtype=bool)))
    assert np.isnan(kpi.tpc_length(np.ones((32, 32), dtype=bool)))

    rng = np.random.default_rng(0)
    mask = rng.random((64, 64)) < 0.35
    length = kpi.tpc_length(mask, max_r_px=32)
    assert np.isfinite(length)
    assert 0 < length < 3

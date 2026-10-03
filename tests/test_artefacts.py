import numpy as np

from qc import artefacts

CFG_A = {"curtaining_band_px": 3, "curtaining_min_freq": 0.02, "edge_band_pct": 0.05}


def test_vertical_stripes_raise_curtaining_score_only():
    rng = np.random.default_rng(0)
    base = rng.normal(128, 10, (256, 256))
    x = np.arange(256)
    stripes = 25 * np.sin(2 * np.pi * x / 9.0)[None, :]  # vertical stripes: vary along x, constant along y
    v0, h0 = artefacts.stripe_scores(base, **{"band_px": 3, "min_freq": 0.02})
    v1, h1 = artefacts.stripe_scores(base + stripes, band_px=3, min_freq=0.02)
    assert v1 > 3 * v0
    assert abs(h1 - h0) < 0.05
    v2, h2 = artefacts.stripe_scores(base + stripes.T, band_px=3, min_freq=0.02)
    assert h2 > 3 * h0 and v2 < v1


def test_edge_charging_and_noise():
    a = np.full((200, 200), 100.0)
    a[:10, :] = a[-10:, :] = a[:, :10] = a[:, -10:] = 130.0
    assert abs(artefacts.edge_charging(a, 0.05) - 30.0) < 1e-6
    m = artefacts.tile_metrics(a.astype(np.uint8), CFG_A)
    assert set(artefacts.METRICS) <= set(m)
    rng = np.random.default_rng(1)
    noisy = rng.normal(128, 5, (256, 256))
    quiet = rng.normal(128, 1, (256, 256))
    assert artefacts.tile_metrics(noisy, CFG_A)["noise_sigma"] > 3 * artefacts.tile_metrics(quiet, CFG_A)["noise_sigma"]

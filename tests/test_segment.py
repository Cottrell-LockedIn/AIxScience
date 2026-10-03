import numpy as np
from skimage.draw import disk

from qc import kpi, segment

CFG_S = {"median_px": 5, "classes": 3, "min_obj_px": 20, "sens_pct": 0.1}


def synthetic(seed=0, size=512):
    rng = np.random.default_rng(seed)
    img = np.full((size, size), 120.0)
    lab = np.ones((size, size), dtype=np.uint8)
    for _ in range(12):  # dark regions (class 0)
        rr, cc = disk((rng.integers(40, size - 40), rng.integers(40, size - 40)), 28, shape=img.shape)
        img[rr, cc] = 30
        lab[rr, cc] = 0
    for _ in range(40):  # bright particles (class 2)
        rr, cc = disk((rng.integers(20, size - 20), rng.integers(20, size - 20)), 7, shape=img.shape)
        img[rr, cc] = 220
        lab[rr, cc] = 2
    img = np.clip(img + rng.normal(0, 8, img.shape), 0, 255).astype(np.uint8)
    return img, lab


def test_three_class_recovery():
    img, truth = synthetic()
    lab, th = segment.segment_tile(img, CFG_S)
    assert len(th) == 2 and 30 < th[0] < 120 < th[1] < 220
    assert set(np.unique(lab)) <= {0, 1, 2}
    agree = (lab == truth).mean()
    assert agree > 0.97, agree
    f_true = kpi.fractions(truth)
    f_hat = kpi.fractions(lab)
    for k in f_true:
        assert abs(f_true[k] - f_hat[k]) < 0.02, (k, f_true[k], f_hat[k])


def test_kpis_and_small_objects_removed():
    img, truth = synthetic(seed=1)
    lab, _ = segment.segment_tile(img, CFG_S)
    k = kpi.kpis(lab)
    assert abs(k["c2_count_density_per_Mpx"] - 40 / lab.size * 1e6) / (40 / lab.size * 1e6) < 0.15
    assert 11 < k["c2_eqdiam_median_px"] < 17  # true diameter 14 px
    assert 50 < k["c0_region_eqdiam_median_px"] < 80  # true diameter 56 px; overlapping disks merge
    # no connected component of class 2 or 0 smaller than min_obj_px
    from skimage.measure import label, regionprops
    for cls in (0, 2):
        areas = [r.area for r in regionprops(label(lab == cls, connectivity=1))]
        assert min(areas) >= CFG_S["min_obj_px"]


def test_uniform_and_two_level_tiles_fall_back_to_class_1():
    for img in (np.full((256, 256), 120, dtype=np.uint8),
                np.where(np.arange(256)[None, :] < 128, 30, 220).astype(np.uint8)):
        lab, th = segment.segment_tile(img, CFG_S)
        assert all(np.isnan(t) for t in th) and len(th) == 2
        assert (lab == 1).all()
    img, _ = synthetic()
    _, th = segment.segment_tile(img, CFG_S)
    assert not any(np.isnan(t) for t in th)


def test_join_thresholds_rejects_stale_inputs():
    import pandas as pd
    import pytest

    cfg = {"_hash": "abc"}
    index = pd.DataFrame({"tile_id": ["t1", "t2"], "path": ["p1", "p2"], "y": [0, 512], "x": [0, 0],
                          "h": [1024, 1024], "w": [1024, 1024], "config_hash": ["abc", "abc"]})
    th = pd.DataFrame({"tile_id": ["t1", "t2"], "y": [0, 512], "x": [0, 0], "t0": [60.0, 61.0], "t1": [150.0, 151.0],
                       "config_hash": ["abc", "abc"]})
    out = kpi.join_thresholds(th, index, cfg)
    assert list(out["path"]) == ["p1", "p2"]
    with pytest.raises(RuntimeError):
        kpi.join_thresholds(th.assign(config_hash="old"), index, cfg)
    with pytest.raises(RuntimeError):
        kpi.join_thresholds(th, index.assign(config_hash="retiled"), cfg)
    with pytest.raises(RuntimeError):
        kpi.join_thresholds(th.assign(y=[0, 520]), index, cfg)
    with pytest.raises(RuntimeError):
        kpi.join_thresholds(th, index.iloc[:1], cfg)

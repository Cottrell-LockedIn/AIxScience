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

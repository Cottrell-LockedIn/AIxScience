"""Synthetic-mask tests for the Tier-1 feature table (src/qc/features.py). Known answers, no real data."""
import numpy as np
import pandas as pd
import pytest
from skimage.draw import disk

from qc import features as F

P = {"min_object_px": 20, "connectivity": 8, "window_px": 512, "exact_radius_max_px": 16, "radius_growth": 1.2}


def lattice_image(size=1024, step=128, radius=10, offset=64):
    """Class-2 discs on a square lattice in a class-1 background."""
    lab = np.ones((size, size), dtype=np.uint8)
    centres = [(y, x) for y in range(offset, size, step) for x in range(offset, size, step)]
    for y, x in centres:
        rr, cc = disk((y, x), radius, shape=lab.shape)
        lab[rr, cc] = 2
    return lab, centres


def test_area_fractions_and_unanalysed_pixels():
    lab = np.ones((100, 200), dtype=np.uint8)
    lab[:, :50] = 0          # 25 % void
    lab[:, 150:] = 2         # 25 % silicon
    f = F.compute(lab, P)
    assert f["F01"] == pytest.approx(0.25) and f["F02"] == pytest.approx(0.25)
    lab[:50, :] = F.UNANALYSED   # top half unanalysed: fractions are over analysed pixels only
    f = F.compute(lab, P)
    assert f["analysed_px"] == 50 * 200 and f["coverage"] == pytest.approx(0.5)
    assert f["F01"] == pytest.approx(0.25) and f["F02"] == pytest.approx(0.25)


def test_particle_size_count_and_border_exclusion():
    lab, centres = lattice_image()
    f = F.compute(lab, P)
    n = len(centres)
    assert f["n_c2_particles"] == n and f["n_c2_particles_interior"] == n and f["n_c2_particles_border"] == 0
    eqd = 2 * np.sqrt(np.pi * 10 ** 2 / np.pi)  # area of a rasterised r=10 disc ~ 317 px -> eqd ~ 20.1
    assert abs(f["F03"] - eqd) < 1.0 and abs(f["F04"] - eqd) < 1.0
    assert f["F05"] == pytest.approx(n / lab.size * 1e6)
    assert f["F07"] == pytest.approx(1.0, abs=0.05)   # discs are convex
    # a particle cut by the border is excluded from size stats, and from the count when it touches left/bottom
    lab2 = lab.copy()
    rr, cc = disk((lab.shape[0] - 1, 500), 30, shape=lab.shape)   # bottom border, large
    lab2[rr, cc] = 2
    f2 = F.compute(lab2, P)
    assert f2["n_c2_particles"] == n + 1 and f2["n_c2_particles_border"] == 1
    assert f2["F03"] == pytest.approx(f["F03"]) and f2["F04"] == pytest.approx(f["F04"])
    assert f2["F05"] == pytest.approx(f["F05"])     # bottom-touching: not counted (unbiased counting frame)
    lab3 = lab.copy()
    rr, cc = disk((0, 500), 30, shape=lab.shape)   # top border: counted, but still excluded from size stats
    lab3[rr, cc] = 2
    f3 = F.compute(lab3, P)
    assert f3["F05"] == pytest.approx((n + 1) / lab.size * 1e6) and f3["F04"] == pytest.approx(f["F04"])


def test_min_object_size_filter_after_stitching():
    lab = np.ones((256, 256), dtype=np.uint8)
    lab[10:13, 10:13] = 2          # 9 px fragment, below min_object_px
    rr, cc = disk((128, 128), 12, shape=lab.shape)
    lab[rr, cc] = 2
    f = F.compute(lab, P)
    assert f["n_c2_particles"] == 1
    assert f["F02"] == pytest.approx((9 + (lab == 2).sum() - 9) / lab.size)   # area fraction keeps every pixel


def test_clark_evans_regular_random_clustered():
    lab, centres = lattice_image()
    R, z = F.clark_evans(np.array(centres, dtype=float), *lab.shape)
    assert R > 1.5 and z > 3                 # square lattice: R ~ 2 (regular)
    rng = np.random.default_rng(0)
    pts = rng.uniform(0, 1024, size=(2000, 2))
    R, z = F.clark_evans(pts, 1024, 1024)
    assert abs(R - 1.0) < 0.1 and abs(z) < 4  # CSR with edge correction
    clustered = np.concatenate([c + rng.normal(0, 5, size=(50, 2)) for c in rng.uniform(100, 900, size=(20, 2))])
    R, z = F.clark_evans(clustered, 1024, 1024)
    assert R < 0.5 and z < -3
    assert np.isnan(F.clark_evans(np.zeros((1, 2)), 10, 10)[0])


def test_solidity_area_weighted_median():
    lab = np.ones((400, 400), dtype=np.uint8)
    rr, cc = disk((100, 100), 20, shape=lab.shape)
    lab[rr, cc] = 2                                     # convex, area ~1257
    lab[250:350, 250:260] = 2                            # a cross: concave
    lab[295:305, 205:395] = 2
    f = F.compute(lab, P)
    # weighted median lands on the larger (cross) particle: 2800 px over an octagonal hull of ~10900 px
    assert 0.2 < f["F07"] < 0.35
    assert F.weighted_median(np.array([1.0, 0.5]), np.array([1, 10])) == 0.5
    assert np.isnan(F.weighted_median(np.array([]), np.array([])))


def test_local_thickness_strip_and_median():
    for width in (6, 20, 35):
        m = np.zeros((200, 300), dtype=bool)
        m[50:50 + width, :] = True
        th = F.local_thickness(m, **{k: P[k] for k in ("exact_radius_max_px", "radius_growth")})
        assert abs(np.median(th[m]) - width) <= 1, (width, np.median(th[m]))
        assert (th[~m] == 0).all()
    # two strips of width 10 and 30 in one class-0 mask: the pixel-weighted median is 30 (3x more pixels)
    lab = np.ones((300, 300), dtype=np.uint8)
    lab[20:30, :] = 0
    lab[100:130, :] = 0
    f = F.compute(lab, P)
    assert abs(f["F08"] - 30) <= 1
    # a disc of radius 25 has thickness ~50 at every pixel
    m = np.zeros((200, 200), dtype=bool)
    rr, cc = disk((100, 100), 25, shape=m.shape)
    m[rr, cc] = True
    th = F.local_thickness(m)
    assert abs(np.median(th[m]) - 50) <= 2


def test_chord_anisotropy_and_censoring():
    lab = np.ones((400, 600), dtype=np.uint8)
    lab[50:70, 50:110] = 0     # 20 high x 60 wide rectangles -> horizontal chords 60, vertical 20
    lab[200:220, 300:360] = 0
    f = F.compute(lab, P)
    assert f["F09"] == pytest.approx(3.0)
    assert f["n_c0_chords_h"] == 40 and f["n_c0_chords_v"] == 120
    lab[380:400, 0:600] = 0    # strip touching left, right and bottom borders: its chords are censored
    f2 = F.compute(lab, P)
    assert f2["n_c0_chords_h"] == 40 and f2["n_c0_chords_v"] == 120 and f2["F09"] == pytest.approx(3.0)
    assert len(F.chord_lengths(np.zeros((5, 5), dtype=bool), 1)) == 0


def test_window_iqr_heterogeneity():
    lab = np.ones((1024, 2048), dtype=np.uint8)
    f = F.compute(lab, P)
    assert f["n_windows"] == 8 and f["F10"] == 0.0
    lab[:, :1024] = 0           # left half void, right half not: window fractions are 0/1
    f = F.compute(lab, P)
    assert f["F10"] == pytest.approx(1.0)
    assert len(F.window_fractions(np.zeros((500, 500), dtype=bool), 512)) == 0


def test_perimeter_fraction_adjacent_to_void():
    lab = np.ones((300, 300), dtype=np.uint8)
    rr, cc = disk((150, 150), 40, shape=lab.shape)
    lab[rr, cc] = 2
    f = F.compute(lab, P)
    assert f["F11"] == 0.0 and f["n_c2_boundary_px"] > 0
    rr, cc = disk((150, 150), 60, shape=lab.shape)
    ring = np.zeros_like(lab, dtype=bool)
    ring[rr, cc] = True
    lab[ring & (lab != 2)] = 0  # void ring around the particle
    f = F.compute(lab, P)
    assert f["F11"] == pytest.approx(1.0)
    half = lab.copy()
    half[:, 150:][half[:, 150:] == 0] = 1   # right half of the ring back to graphite
    f = F.compute(half, P)
    assert 0.4 < f["F11"] < 0.6


def test_stitch_later_tile_wins_and_coverage():
    a = np.zeros((4, 4), dtype=np.uint8)
    b = np.full((4, 4), 2, dtype=np.uint8)
    canvas = F.stitch([(0, 2, b), (0, 0, a)], 4, 8)
    assert (canvas[:, :2] == 0).all() and (canvas[:, 2:6] == 2).all() and (canvas[:, 6:] == F.UNANALYSED).all()
    f = F.compute(canvas, P)
    assert f["analysed_px"] == 24 and f["coverage"] == pytest.approx(0.75)


def test_registry_columns_and_nm_twins():
    reg = F.load_registry()
    assert [f["id"] for f in reg["features"]] == [f"F{i:02d}" for i in range(1, 12)]
    for f in reg["features"]:
        assert {"id", "column", "name", "class", "definition", "unit", "provenance"} <= set(f)
    assert reg["phase_identity"] == F.PHASE_IDENTITY
    lab, _ = lattice_image()
    cols = F.to_columns(F.compute(lab, P), reg)
    assert set(reg["_columns"].values()) <= set(cols)
    assert cols["F03_c2_eqdiam_median_nm_if25"] == pytest.approx(25 * cols["F03_c2_eqdiam_median_px"])
    assert "F08_c0_local_thickness_median_nm_if25" in cols


def test_batch_medians_table():
    reg = F.load_registry()
    cols = list(reg["_columns"].values())
    img = pd.DataFrame({"batch": ["Batch_1"] * 3 + ["Batch_3"] * 2, **{c: np.arange(5, dtype=float) for c in cols}})
    bm = F.batch_medians(img, reg)
    assert list(bm["feature"]) == cols
    assert (bm["median_Batch_1"] == 1.0).all() and (bm["median_Batch_3"] == 3.5).all()
    assert bm["n_images_Batch_1"].iloc[0] == 3 and bm["n_images_Batch_3"].iloc[0] == 2

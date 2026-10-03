"""Synthetic tests for the detector registration check (src/qc/registration.py)."""
import numpy as np
import pytest
from scipy import ndimage

from qc import registration as R

P = dict(R.DEFAULTS, win_px=256, max_cols=4)


def texture(shape=(640, 1200), seed=0):
    """Smooth random texture with distinct blobs, like a BSE field; uint8."""
    rng = np.random.default_rng(seed)
    a = ndimage.gaussian_filter(rng.normal(size=shape), 6) + 0.3 * ndimage.gaussian_filter(rng.normal(size=shape), 1.5)
    a = (a - a.min()) / (a.max() - a.min()) * 255
    return a.astype(np.uint8)


def other_detector(img, seed=1):
    """A different-looking view of the same scene: inverted contrast, nonlinear tone, independent noise."""
    rng = np.random.default_rng(seed)
    a = 255 - img.astype(float)
    a = 255 * (a / 255) ** 1.6 + rng.normal(0, 10, img.shape)
    return np.clip(a, 0, 255).astype(np.uint8)


def test_known_shift_is_recovered_per_window_and_in_summary():
    ref = texture()
    mov = other_detector(np.roll(np.roll(ref, 3, axis=0), -5, axis=1))   # scene moved by (+3, -5) px
    rows, summ = R.register_pair(ref, mov, P)
    assert len(rows) == (640 // 256) * 4 == 8
    for r in rows:
        assert r["psr"] > P["min_psr"]
    # shift to apply to mov to align it with ref = (-3, +5)
    assert summ["dy_median"] == pytest.approx(-3, abs=0.3) and summ["dx_median"] == pytest.approx(5, abs=0.3)
    assert summ["dy_std"] < 0.3 and summ["dx_std"] < 0.3
    assert summ["scale"] == pytest.approx(1.0, abs=2e-3) and abs(summ["rotation_deg"]) < 0.2
    assert not summ["registered"] and "median shift" in summ["reason"]


def test_identity_is_registered_and_subpixel_shift_is_measured():
    ref = texture(seed=2)
    _, summ = R.register_pair(ref, other_detector(ref), P)
    assert summ["registered"] and summ["reason"] == ""
    assert abs(summ["dy_median"]) < 0.2 and abs(summ["dx_median"]) < 0.2
    # a 1.5 px shift is below the 2 px gate but must still be measured (upsampled correlation)
    mov = ndimage.shift(ref.astype(float), (0, 1.5), order=1, mode="reflect")
    _, summ2 = R.register_pair(ref, other_detector(mov.astype(np.uint8)), P)
    assert summ2["registered"]
    assert summ2["dx_median"] == pytest.approx(-1.5, abs=0.3)


def test_unrelated_images_have_no_sharp_peak_and_fail():
    ref = texture(seed=3)
    mov = texture(seed=4)
    _, summ = R.register_pair(ref, mov, P)
    assert summ["n_valid_windows"] < len(R.window_grid(*ref.shape, P["win_px"], P["max_cols"]))
    assert not summ["registered"]


def test_rotation_shows_up_as_inconsistent_shifts_and_in_the_fit():
    ref = texture(shape=(1024, 1024), seed=5)
    mov = ndimage.rotate(ref.astype(float), 1.0, reshape=False, order=1, mode="reflect").astype(np.uint8)
    _, summ = R.register_pair(ref, other_detector(mov), dict(P, max_cols=4))
    assert abs(summ["rotation_deg"]) == pytest.approx(1.0, abs=0.3)
    assert not summ["registered"]          # windows disagree: a rotated image is not pixel-registered


def test_window_grid_is_non_overlapping_and_inside():
    g = R.window_grid(2300, 6980, 768, 6)
    assert len(g) == 2 * 6
    for y, x in g:
        assert 0 <= y and y + 768 <= 2300 and 0 <= x and x + 768 <= 6980
    for i, (y1, x1) in enumerate(g):
        for y2, x2 in g[i + 1:]:
            assert abs(y1 - y2) >= 768 or abs(x1 - x2) >= 768
    assert R.window_grid(500, 500, 768, 6) == []


def test_shape_mismatch_is_rejected():
    with pytest.raises(ValueError):
        R.register_pair(np.zeros((300, 300), np.uint8), np.zeros((300, 310), np.uint8), P)

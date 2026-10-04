import numpy as np
import pytest

from qc.charging import glow_sensitivity


def test_glow_sensitivity_excludes_only_high_intensity_class2_pixels():
    intensity = np.arange(100, dtype=np.float32).reshape(10, 10)
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask.flat[[90, 95, 96, 97, 98, 99]] = 2
    glow_frac, f02_glow_excluded = glow_sensitivity(
        mask, intensity, percentile=95
    )
    assert glow_frac == pytest.approx(5 / 6)
    assert f02_glow_excluded == pytest.approx(1 / 100)


def test_glow_sensitivity_returns_zero_for_absent_class2():
    mask = np.zeros((4, 4), dtype=np.uint8)
    intensity = np.arange(16, dtype=np.float32).reshape(4, 4)
    assert glow_sensitivity(mask, intensity, 95) == (0.0, 0.0)

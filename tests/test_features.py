import numpy as np
import pandas as pd
import pytest

from qc.features import (
    c2_boundary_fraction_adjacent_c0,
    chord_anisotropy,
    clark_evans_ratio,
    count_frame_count,
    extract_features,
    stitch_mask,
)


def test_disc_particle_diameter_and_local_thickness():
    mask = np.ones((128, 128), dtype=np.uint8)
    yy, xx = np.ogrid[:128, :128]
    radius_c2, radius_c0 = 10, 15
    mask[(yy - 32) ** 2 + (xx - 32) ** 2 <= radius_c2**2] = 2
    mask[(yy - 90) ** 2 + (xx - 90) ** 2 <= radius_c0**2] = 0

    features = extract_features(mask, min_object_px=1)

    assert features["F03_c2_eqdiam_median_px"] == pytest.approx(2 * radius_c2, abs=1)
    assert features["F08_c0_local_thickness_median_px"] == pytest.approx(2 * radius_c0, abs=3)


def test_count_frame_excludes_left_and_bottom_edges():
    labels = np.zeros((10, 10), dtype=np.uint8)
    labels[0, 4] = 1
    labels[4, 9] = 2
    labels[4, 0] = 3
    labels[9, 4] = 4

    assert count_frame_count(labels) == 2


def test_clark_evans_detects_lattice_and_poisson_process():
    lattice = np.asarray(
        [(y, x) for y in range(10, 100, 20) for x in range(10, 100, 20)],
        dtype=np.float64,
    )
    rng = np.random.default_rng(4)
    poisson = rng.uniform(0, 1000, size=(500, 2))

    assert clark_evans_ratio(lattice, (100, 100)) > 1
    assert clark_evans_ratio(poisson, (1000, 1000)) == pytest.approx(1, abs=0.15)


def test_horizontal_stripes_have_longer_horizontal_chords():
    void = np.zeros((100, 100), dtype=bool)
    for top in (12, 32, 52, 72):
        void[top:top + 10, 10:90] = True

    assert chord_anisotropy(void) > 1


def test_f11_uses_four_neighbour_boundary_on_two_class_image():
    mask = np.full((3, 3), 2, dtype=np.uint8)
    mask[1, 1] = 0

    assert c2_boundary_fraction_adjacent_c0(mask) == pytest.approx(0.5)


def test_stitch_mask_uses_row_major_later_tile_wins(tmp_path):
    from PIL import Image

    Image.fromarray(np.ones((2, 2), dtype=np.uint8)).save(tmp_path / "first.png")
    Image.fromarray(np.full((2, 2), 2, dtype=np.uint8)).save(tmp_path / "second.png")
    rows = pd.DataFrame(
        [
            {"tile_id": "first", "mask_path": "first.png", "y": 0, "x": 0},
            {"tile_id": "second", "mask_path": "second.png", "y": 0, "x": 1},
        ]
    )

    stitched = stitch_mask(rows, tmp_path, (2, 3))

    assert np.array_equal(
        stitched,
        np.array([[1, 2, 2], [1, 2, 2]], dtype=np.uint8),
    )

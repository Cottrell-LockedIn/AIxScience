import numpy as np
from scipy.ndimage import shift as shift_image
from skimage.transform import SimilarityTransform, warp

from qc import register
from qc.register import estimate_registration


def test_registration_recovers_known_rotation_scale_and_translation():
    reference = np.zeros((512, 512), dtype=np.uint8)
    reference[45:130, 70:190] = 255
    reference[180:330, 285:350] = 255
    reference[355:405, 100:245] = 255
    reference[205:250, 90:135] = 255
    transform = SimilarityTransform(
        scale=1.015,
        rotation=np.deg2rad(1.2),
        translation=(5, -4),
    )
    moving = warp(
        reference,
        inverse_map=transform.inverse,
        output_shape=reference.shape,
        order=0,
        preserve_range=True,
    )
    moving = shift_image(moving, shift=(4, -6), order=0, mode="constant")
    result = estimate_registration(reference, 255 - moving)
    assert abs(result["rotation_deg"] + 1.2) < 1.0
    assert abs(result["scale"] - 1 / 1.015) < 0.02
    assert abs(result["shift_y_px"]) > 1
    assert abs(result["shift_x_px"]) > 1
    assert np.isfinite(result["psr"])
    assert not result["same_fov"]


def test_registration_scale_threshold_passes_0015_and_fails_0025(monkeypatch):
    reference = np.ones((32, 32), dtype=np.float32)
    moving = np.ones((32, 32), dtype=np.float32)
    monkeypatch.setattr(
        register, "_co_located_windows", lambda *_: [(reference, moving)]
    )
    monkeypatch.setattr(
        register, "_phase_shift", lambda *_, **__: (np.zeros(2), 10.0)
    )
    monkeypatch.setattr(
        register,
        "estimate_rotation_scale",
        lambda *_: (0.0, 1.0015),
    )
    limits = {
        "max_shift_px": 1.0,
        "max_rotation_deg": 0.1,
        "max_scale_dev": 0.002,
    }

    passing = estimate_registration(reference, moving, limits)
    monkeypatch.setattr(
        register,
        "estimate_rotation_scale",
        lambda *_: (0.0, 1.0025),
    )
    failing = estimate_registration(reference, moving, limits)

    assert passing["same_fov"]
    assert not failing["same_fov"]
    assert passing["rotation_step_deg"] == 0.01
    assert passing["scale_step"] > 0


def _sharp_binary_texture():
    rng = np.random.default_rng(6413)
    reference = np.zeros((1024, 1024), dtype=np.float32)
    for _ in range(750):
        y = int(rng.integers(12, 1000))
        x = int(rng.integers(12, 1000))
        height = int(rng.integers(5, 80))
        width = int(rng.integers(5, 80))
        reference[
            max(0, y - height // 2):min(1024, y + (height + 1) // 2),
            max(0, x - width // 2):min(1024, x + (width + 1) // 2),
        ] = float(rng.integers(0, 2))
    return reference


def _centre_scaled_image(reference, scale):
    transform = register._similarity_transform(reference.shape, 0.0, scale)
    return warp(
        reference,
        inverse_map=transform.inverse,
        output_shape=reference.shape,
        order=0,
        mode="constant",
        cval=0,
        preserve_range=True,
    ).astype(np.float32)


def test_registration_identity_transform_is_same_fov():
    reference = _sharp_binary_texture()
    result = estimate_registration(
        reference, _centre_scaled_image(reference, 1.0)
    )

    assert result["scale"] == 1.0
    assert result["same_fov"]


def test_registration_centre_scaled_006_and_994_fail_same_fov():
    reference = _sharp_binary_texture()
    results = {
        scale: estimate_registration(
            reference, _centre_scaled_image(reference, scale)
        )
        for scale in (1.006, 0.994)
    }

    assert not results[1.006]["same_fov"]
    assert not results[0.994]["same_fov"]


def test_registration_small_centre_scaled_deviations_shrink_towards_one():
    reference = _sharp_binary_texture()
    for applied_scale in (1.0015, 1.0025, 1.004):
        result = estimate_registration(
            reference, _centre_scaled_image(reference, applied_scale)
        )
        assert abs(result["scale"] - 1.0) <= abs(applied_scale - 1.0)

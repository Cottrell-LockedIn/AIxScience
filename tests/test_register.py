import numpy as np
from scipy.ndimage import shift as shift_image
from skimage.transform import SimilarityTransform, warp

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

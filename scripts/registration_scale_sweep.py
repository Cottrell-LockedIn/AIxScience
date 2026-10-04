import argparse
import csv
from pathlib import Path

import numpy as np
from skimage.transform import warp

from qc import register


APPLIED_SCALE_TEXTS = (
    "0.990",
    "0.994",
    "0.996",
    "0.997",
    "0.9975",
    "0.998",
    "0.9985",
    "1.0",
    "1.0015",
    "1.002",
    "1.0025",
    "1.003",
    "1.004",
    "1.005",
    "1.006",
    "1.008",
    "1.010",
)
LIMITS = {
    "max_shift_px": 1.0,
    "max_rotation_deg": 0.1,
    "max_scale_dev": 0.002,
}


def sharp_binary_texture() -> np.ndarray:
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


def centre_scaled_image(reference: np.ndarray, scale: float) -> np.ndarray:
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


def failure_reason(result: dict[str, object]) -> str:
    scale = float(result["scale"])
    shift_y = float(result["shift_y_px"])
    shift_x = float(result["shift_x_px"])
    rotation = float(result["rotation_deg"])
    if not np.isfinite(scale) or abs(scale - 1.0) > LIMITS["max_scale_dev"]:
        return "scale"
    if (
        not np.isfinite([shift_y, shift_x]).all()
        or abs(shift_y) > LIMITS["max_shift_px"]
        or abs(shift_x) > LIMITS["max_shift_px"]
    ):
        return "shift"
    if not np.isfinite(rotation) or abs(rotation) > LIMITS["max_rotation_deg"]:
        return "rotation"
    return "none"


def sweep_rows() -> list[dict[str, str]]:
    reference = sharp_binary_texture()
    rows = []
    for applied_scale_text in APPLIED_SCALE_TEXTS:
        applied_scale = float(applied_scale_text)
        result = register.estimate_registration(
            reference, centre_scaled_image(reference, applied_scale), LIMITS
        )
        rows.append(
            {
                "applied_scale": applied_scale_text,
                "estimated_scale": format(result["scale"], ".17g"),
                "abs_error": format(
                    abs(result["scale"] - 1.0 / applied_scale), ".17g"
                ),
                "shift_y_px": format(result["shift_y_px"], ".17g"),
                "shift_x_px": format(result["shift_x_px"], ".17g"),
                "same_fov": str(bool(result["same_fov"])).lower(),
                "failed_on": failure_reason(result),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/repro/registration_scale_sweep.csv"),
    )
    args = parser.parse_args()
    rows = sweep_rows()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "applied_scale",
                "estimated_scale",
                "abs_error",
                "shift_y_px",
                "shift_x_px",
                "same_fov",
                "failed_on",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

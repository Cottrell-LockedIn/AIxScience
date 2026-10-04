"""B6 translation, rotation, and scale registration for detector images.

Reads:  data/raw detector TIFFs and configs/v1.yaml
Writes: results/registration/registration_by_image.csv
"""
from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import ndimage
from scipy.fft import fft2, fftshift, ifft2
from skimage.registration import phase_cross_correlation
from skimage.transform import SimilarityTransform, warp, warp_polar

from qc import config as _config
from qc import tiles

PHASE_IDENTITY = "stated by Polaron, not image-verified"
TRANSLATION_UPSAMPLE_FACTOR = 10
LOG_POLAR_UPSAMPLE_FACTOR = 100


def read_raw_channel(path: Path, cfg: dict[str, Any]) -> np.ndarray:
    image = tiles.read_gray(path, int(cfg["data"]["read_channel"]))
    return tiles.crop_border(image, int(cfg["data"]["border_crop_px"]))


def raw_channel_paths(cfg: dict[str, Any]) -> dict[str, dict[str, Path]]:
    paths: dict[str, dict[str, Path]] = {}
    raw_dir = _config.resolve(cfg["data"]["raw_dir"])
    for path in sorted(raw_dir.glob("*/*.tif")):
        match = tiles.NAME_RE.match(path.name)
        if match:
            paths.setdefault(match["sample"], {})[match["channel"]] = path
    return paths


def _window_starts(length: int, size: int) -> list[int]:
    if length <= size:
        return [0]
    return sorted({0, (length - size) // 2, length - size})


def _co_located_windows(
    reference: np.ndarray, moving: np.ndarray, window_px: int = 1024
) -> list[tuple[np.ndarray, np.ndarray]]:
    height = min(reference.shape[0], moving.shape[0])
    width = min(reference.shape[1], moving.shape[1])
    size = min(window_px, height, width)
    ref_y0 = (reference.shape[0] - height) // 2
    ref_x0 = (reference.shape[1] - width) // 2
    mov_y0 = (moving.shape[0] - height) // 2
    mov_x0 = (moving.shape[1] - width) // 2
    windows = []
    y_starts = _window_starts(height, size)
    x_starts = _window_starts(width, size)
    for y, x in product(y_starts, x_starts):
        ref_window = reference[
            ref_y0 + y:ref_y0 + y + size, ref_x0 + x:ref_x0 + x + size
        ]
        mov_window = moving[
            mov_y0 + y:mov_y0 + y + size, mov_x0 + x:mov_x0 + x + size
        ]
        windows.append((ref_window, mov_window))
    return windows


def _phase_shift(
    reference: np.ndarray,
    moving: np.ndarray,
    upsample_factor: int = TRANSLATION_UPSAMPLE_FACTOR,
) -> tuple[np.ndarray, float]:
    ref = np.asarray(reference, dtype=np.float64)
    mov = np.asarray(moving, dtype=np.float64)
    if ref.shape != mov.shape or ref.ndim != 2:
        raise ValueError("phase correlation requires same-shaped 2-D windows")
    valid = np.isfinite(ref) & np.isfinite(mov)
    if valid.sum() < 0.3 * ref.size:
        return np.full(2, np.nan), float("nan")
    if ref[valid].std() == 0 or mov[valid].std() == 0:
        return np.full(2, np.nan), float("nan")
    ref = np.where(valid, ref - ref[valid].mean(), 0.0)
    mov = np.where(valid, mov - mov[valid].mean(), 0.0)
    shift, _, _ = phase_cross_correlation(
        ref, mov, upsample_factor=upsample_factor, normalization="phase"
    )

    cross_power = fft2(ref) * np.conj(fft2(mov))
    cross_power /= np.maximum(np.abs(cross_power), np.finfo(np.float64).eps)
    correlation = np.abs(ifft2(cross_power))
    peak_y, peak_x = np.unravel_index(
        np.argmax(correlation), correlation.shape
    )
    y_distance = np.minimum(
        np.abs(np.arange(ref.shape[0]) - peak_y),
        ref.shape[0] - np.abs(np.arange(ref.shape[0]) - peak_y),
    )
    x_distance = np.minimum(
        np.abs(np.arange(ref.shape[1]) - peak_x),
        ref.shape[1] - np.abs(np.arange(ref.shape[1]) - peak_x),
    )
    sidelobes = correlation[
        (y_distance[:, None] > 5) | (x_distance[None, :] > 5)
    ]
    spread = float(sidelobes.std())
    psr = (
        float((correlation[peak_y, peak_x] - sidelobes.mean()) / spread)
        if spread > 0
        else float("nan")
    )
    return np.asarray(shift, dtype=np.float64), psr


def _spectrum_magnitude(image: np.ndarray) -> np.ndarray:
    values = np.asarray(image, dtype=np.float64)
    if values.ndim != 2 or values.std() == 0:
        raise ValueError(
            "rotation/scale registration requires a non-constant 2-D image"
        )
    values = (values - values.mean()) * np.outer(
        np.hanning(values.shape[0]), np.hanning(values.shape[1])
    )
    spectrum = np.log1p(np.abs(fftshift(fft2(values))))
    center_y, center_x = np.array(spectrum.shape) // 2
    spectrum[
        max(0, center_y - 2):center_y + 3,
        max(0, center_x - 2):center_x + 3,
    ] = 0
    return spectrum


def estimate_rotation_scale(
    reference: np.ndarray, moving: np.ndarray
) -> tuple[float, float]:
    ref = np.asarray(reference)
    mov = np.asarray(moving)
    if ref.ndim != 2 or mov.ndim != 2:
        raise ValueError("rotation/scale registration requires 2-D images")
    height = min(ref.shape[0], mov.shape[0])
    width = min(ref.shape[1], mov.shape[1])
    size = min(1024, height, width)
    ref_y, ref_x = (ref.shape[0] - size) // 2, (ref.shape[1] - size) // 2
    mov_y, mov_x = (mov.shape[0] - size) // 2, (mov.shape[1] - size) // 2
    ref_window = ref[ref_y:ref_y + size, ref_x:ref_x + size]
    mov_window = mov[mov_y:mov_y + size, mov_x:mov_x + size]
    radius = size / 2
    output_shape = (360, max(128, min(512, size)))
    polar_ref = warp_polar(
        _spectrum_magnitude(ref_window),
        radius=radius,
        output_shape=output_shape,
        scaling="log",
        preserve_range=True,
    )
    polar_mov = warp_polar(
        _spectrum_magnitude(mov_window),
        radius=radius,
        output_shape=output_shape,
        scaling="log",
        preserve_range=True,
    )
    polar_shift, _ = _phase_shift(
        polar_ref, polar_mov, LOG_POLAR_UPSAMPLE_FACTOR
    )
    angular_shift = float(polar_shift[0])
    angular_shift = (
        (angular_shift + output_shape[0] / 2) % output_shape[0]
        - output_shape[0] / 2
    )
    radial_shift = float(polar_shift[1])
    rotation_deg = angular_shift * 360.0 / output_shape[0]
    scale = float(np.exp(-radial_shift * np.log(radius) / output_shape[1]))
    return rotation_deg, scale


def _similarity_transform(
    shape: tuple[int, int], rotation_deg: float, scale: float
) -> SimilarityTransform:
    height, width = shape
    center_x, center_y = (width - 1) / 2, (height - 1) / 2
    angle = np.deg2rad(rotation_deg)
    matrix = scale * np.array(
        [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    )
    translation = np.array([center_x, center_y]) - matrix @ np.array(
        [center_x, center_y]
    )
    return SimilarityTransform(
        scale=scale,
        rotation=angle,
        translation=tuple(translation),
    )


def _registration_step_sizes(shape: tuple[int, int]) -> tuple[float, float]:
    size = min(1024, *shape)
    radius = size / 2
    radial_bins = max(128, min(512, size))
    rotation_step_deg = (
        360.0 / 360 / LOG_POLAR_UPSAMPLE_FACTOR
    )
    scale_step = float(
        np.exp(
            np.log(radius)
            / (radial_bins * LOG_POLAR_UPSAMPLE_FACTOR)
        ) - 1
    )
    return rotation_step_deg, scale_step


def align_image(
    image: np.ndarray,
    rotation_deg: float,
    scale: float,
    shift_y_px: float = 0.0,
    shift_x_px: float = 0.0,
) -> np.ndarray:
    values = np.asarray(image, dtype=np.float32)
    if (
        not np.isfinite([rotation_deg, scale, shift_y_px, shift_x_px]).all()
        or scale <= 0
    ):
        return np.full(values.shape, np.nan, dtype=np.float32)
    transformed = warp(
        values,
        inverse_map=_similarity_transform(
            values.shape, rotation_deg, scale
        ).inverse,
        output_shape=values.shape,
        order=1,
        mode="constant",
        cval=np.nan,
        clip=False,
        preserve_range=True,
    )
    return ndimage.shift(
        transformed,
        shift=(shift_y_px, shift_x_px),
        order=1,
        mode="constant",
        cval=np.nan,
        prefilter=False,
    ).astype(np.float32, copy=False)


def estimate_registration(
    reference: np.ndarray,
    moving: np.ndarray,
    registration_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rotation_deg, scale = estimate_rotation_scale(reference, moving)
    rotation_step_deg, scale_step = _registration_step_sizes(reference.shape)
    aligned = align_image(moving, rotation_deg, scale)
    shifts, psrs = [], []
    for ref_window, mov_window in _co_located_windows(reference, aligned):
        shift, psr = _phase_shift(ref_window, mov_window)
        if np.isfinite(shift).all():
            shifts.append(shift)
        if np.isfinite(psr):
            psrs.append(psr)
    if shifts:
        shift_y_px, shift_x_px = np.median(np.stack(shifts), axis=0)
    else:
        shift_y_px = shift_x_px = float("nan")
    psr = float(np.median(psrs)) if psrs else float("nan")
    limits = registration_cfg or {
        "max_shift_px": 1.0,
        "max_rotation_deg": 0.1,
        "max_scale_dev": 0.002,
    }
    same_fov = bool(
        np.isfinite([shift_y_px, shift_x_px, rotation_deg, scale]).all()
        and abs(shift_y_px) <= float(limits["max_shift_px"])
        and abs(shift_x_px) <= float(limits["max_shift_px"])
        and abs(rotation_deg) <= float(limits["max_rotation_deg"])
        and abs(scale - 1.0) <= float(limits["max_scale_dev"])
    )
    return {
        "shift_y_px": float(shift_y_px),
        "shift_x_px": float(shift_x_px),
        "rotation_deg": float(rotation_deg),
        "rotation_step_deg": rotation_step_deg,
        "scale": float(scale),
        "scale_step": scale_step,
        "psr": psr,
        "same_fov": same_fov,
    }


def run(cfg: dict[str, Any]) -> None:
    paths = raw_channel_paths(cfg)
    rows = []
    registration_cfg = cfg["registration"]
    for sample_id, channels in sorted(paths.items()):
        if "BSE" not in channels:
            continue
        reference = read_raw_channel(channels["BSE"], cfg)
        batch = channels["BSE"].parent.name
        for channel, path in sorted(channels.items()):
            if channel == "BSE":
                continue
            moving = read_raw_channel(path, cfg)
            rows.append(
                {
                    "sample_id": sample_id,
                    "batch": batch,
                    "channel": channel,
                    **estimate_registration(
                        reference, moving, registration_cfg
                    ),
                }
            )
    if not rows:
        raise RuntimeError("register: no non-BSE detector TIFFs found")
    result = _config.stamp(pd.DataFrame(rows), cfg)
    out_dir = _config.ROOT / "results" / "registration"
    out_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_dir / "registration_by_image.csv", index=False)
    good = int(result.groupby("sample_id", sort=True)["same_fov"].all().sum())
    finite_shift = result[["shift_y_px", "shift_x_px"]].to_numpy(dtype=float)
    max_shift = (
        float(np.nanmax(np.abs(finite_shift)))
        if np.isfinite(finite_shift).any()
        else float("nan")
    )
    print(
        f"register: {len(result)} detector comparisons; "
        f"{good}/{result['sample_id'].nunique()} images pass all same_fov "
        f"thresholds; max |shift|={max_shift:.3f} px"
    )

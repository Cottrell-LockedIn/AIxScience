"""B2 image-level features F01-F11 from the frozen feature registry.

Reads:  BSE tiles, their stitched class masks, and configs/features_v1.yaml
Writes: results/features_per_image.parquet (scale 1.0)
        results/features_sensitivity.parquet is generated on Modal by modal_app.py.

The image (sample_id) is the independent unit. Class identities are Polaron-stated, not image-verified.
"""
from __future__ import annotations

import hashlib
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage.measure import regionprops
from skimage.morphology import medial_axis

from qc import config as _config
from qc import segment as _segment

BSE_CHANNEL = "BSE"
PHASE_IDENTITY = "stated by Polaron, not image-verified"
FEATURE_COLUMNS = [
    "F01_c0_area_fraction",
    "F02_c2_area_fraction",
    "F03_c2_eqdiam_median_px",
    "F04_c2_eqdiam_p90_px",
    "F05_c2_count_density_per_Mpx",
    "F06_c2_clark_evans_R",
    "F07_c2_solidity_area_weighted_median",
    "F08_c0_local_thickness_median_px",
    "F09_c0_chord_anisotropy_h_over_v",
    "F10_c0_fraction_iqr_512px",
    "F11_c2_perimeter_fraction_adjacent_c0",
]


def stitch_mask(
    rows: pd.DataFrame,
    masks_dir: Path | None,
    image_shape: tuple[int, int],
    unanalysed_value: int = 255,
    *,
    mask_arrays: dict[str, np.ndarray] | None = None,
) -> np.ndarray:
    """Paste masks in row-major order, with later tiles overwriting overlaps."""
    height, width = image_shape
    canvas = np.full((height, width), unanalysed_value, dtype=np.uint8)
    for _, row in rows.sort_values(["y", "x"], kind="stable").iterrows():
        if mask_arrays is None:
            if masks_dir is None:
                raise ValueError("masks_dir is required when mask arrays are not supplied")
            with Image.open(masks_dir / str(row["mask_path"])) as image:
                tile = np.asarray(image, dtype=np.uint8)
        else:
            tile = np.asarray(mask_arrays[str(row["tile_id"])], dtype=np.uint8)
        y, x = int(row["y"]), int(row["x"])
        y1, x1 = min(height, y + tile.shape[0]), min(width, x + tile.shape[1])
        if y < 0 or x < 0 or y >= height or x >= width:
            raise ValueError(f"tile origin {(y, x)} is outside image shape {image_shape}")
        canvas[y:y1, x:x1] = tile[:y1 - y, :x1 - x]
    if np.any(canvas == unanalysed_value):
        raise ValueError("stitched image contains uncovered pixels")
    if np.any(canvas > 2):
        raise ValueError("stitched masks must contain only class labels 0, 1, and 2")
    return canvas


def _particle_labels(class_mask: np.ndarray, min_object_px: int) -> np.ndarray:
    labels, count = ndimage.label(class_mask, structure=np.ones((3, 3), dtype=bool))
    if count == 0:
        return labels
    areas = np.bincount(labels.ravel())
    keep = areas >= max(1, int(min_object_px))
    keep[0] = False
    labels[~keep[labels]] = 0
    return labels


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    good = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not np.any(good):
        return float("nan")
    order = np.argsort(values[good], kind="stable")
    ordered_values = values[good][order]
    ordered_weights = weights[good][order]
    midpoint = ordered_weights.sum() / 2
    return float(ordered_values[np.searchsorted(np.cumsum(ordered_weights), midpoint, side="left")])


def count_frame_count(labels: np.ndarray) -> int:
    """Gundersen frame: include top/right edges and exclude left/bottom edges."""
    height, width = labels.shape
    props = _component_properties(labels)
    return sum(
        prop["min_col"] > 0 and prop["max_row"] < height
        for prop in props
    )


def _component_properties(labels: np.ndarray) -> list[dict[str, Any]]:
    return [
        {
            "label": int(prop.label),
            "area": int(prop.area),
            "centroid_y": float(prop.centroid[0]),
            "centroid_x": float(prop.centroid[1]),
            "min_row": int(prop.bbox[0]),
            "min_col": int(prop.bbox[1]),
            "max_row": int(prop.bbox[2]),
            "max_col": int(prop.bbox[3]),
            "solidity": float(prop.solidity),
        }
        for prop in regionprops(labels)
    ]


def clark_evans_ratio(centroids_yx: np.ndarray, image_shape: tuple[int, int]) -> float:
    """Nearest-neighbour ratio using the preregistered Donnelly rectangular-window correction."""
    points = np.asarray(centroids_yx, dtype=np.float64)
    n = len(points)
    if n < 2:
        return float("nan")
    height, width = image_shape
    area = float(height * width)
    perimeter = float(2 * (height + width))
    expected = 0.5 * np.sqrt(area / n) + (0.0514 + 0.041 / np.sqrt(n)) * perimeter / n
    nearest = cKDTree(points).query(points, k=2)[0][:, 1]
    return float(nearest.mean() / expected)


def local_thickness(
    void_mask: np.ndarray,
    exact_radius_max_px: float = 16.0,
    growth: float = 1.2,
) -> np.ndarray:
    """Hildebrand–Rueegsegger 2-D local thickness using maximal discs from the medial axis."""
    mask = np.asarray(void_mask, dtype=bool)
    thickness = np.zeros(mask.shape, dtype=np.float64)
    if not np.any(mask):
        return thickness
    if growth <= 1:
        raise ValueError("local-thickness radius growth must exceed 1")
    skeleton, distance = medial_axis(mask, return_distance=True, rng=0)
    distance = np.asarray(distance, dtype=np.float64)
    max_radius = float(distance[skeleton].max())
    sampled_radii = list(np.arange(1, np.floor(exact_radius_max_px) + 1, dtype=float))
    if not sampled_radii or sampled_radii[-1] < exact_radius_max_px:
        sampled_radii.append(float(exact_radius_max_px))
    while sampled_radii[-1] < max_radius:
        sampled_radii.append(sampled_radii[-1] * growth)
    for index, radius in enumerate(sampled_radii):
        upper = sampled_radii[index + 1] if index + 1 < len(sampled_radii) else np.inf
        centers = skeleton & (distance >= radius) & (distance < upper)
        if not np.any(centers):
            continue
        to_center = ndimage.distance_transform_edt(~centers)
        covered = to_center <= radius
        thickness[covered] = np.maximum(thickness[covered], 2 * radius)
    thickness[~mask] = 0
    return thickness


def _uncensored_chords(binary: np.ndarray, axis: int) -> np.ndarray:
    """Return chord lengths not touching either border perpendicular to `axis`."""
    chords: list[np.ndarray] = []
    lines = binary if axis == 1 else binary.T
    line_length = lines.shape[1]
    for line in lines:
        padded = np.pad(line, (1, 1), constant_values=False).astype(np.int8)
        transitions = np.diff(padded)
        starts = np.flatnonzero(transitions == 1)
        stops = np.flatnonzero(transitions == -1)
        lengths = stops - starts
        keep = (starts > 0) & (stops < line_length)
        if np.any(keep):
            chords.append(lengths[keep])
    return np.concatenate(chords) if chords else np.empty(0, dtype=np.int64)


def chord_anisotropy(void_mask: np.ndarray) -> float:
    binary = np.asarray(void_mask, dtype=bool)
    horizontal = _uncensored_chords(binary, axis=1)
    vertical = _uncensored_chords(binary, axis=0)
    if not horizontal.size or not vertical.size or vertical.mean() == 0:
        return float("nan")
    return float(horizontal.mean() / vertical.mean())


def c0_fraction_iqr(void_mask: np.ndarray, window_px: int = 512) -> float:
    height, width = void_mask.shape
    fractions: list[float] = []
    for y in range(0, height - window_px + 1, window_px):
        for x in range(0, width - window_px + 1, window_px):
            window = void_mask[y:y + window_px, x:x + window_px]
            fractions.append(float(np.mean(window)))
    if not fractions:
        return float("nan")
    q25, q75 = np.percentile(fractions, [25, 75])
    return float(q75 - q25)


def c2_boundary_fraction_adjacent_c0(mask: np.ndarray) -> float:
    values = np.asarray(mask)
    padded = np.pad(values, 1, constant_values=255)
    up = padded[:-2, 1:-1]
    down = padded[2:, 1:-1]
    left = padded[1:-1, :-2]
    right = padded[1:-1, 2:]
    class2 = values == 2
    boundary = class2 & ((up != 2) | (down != 2) | (left != 2) | (right != 2))
    adjacent_c0 = class2 & ((up == 0) | (down == 0) | (left == 0) | (right == 0))
    denominator = int(boundary.sum())
    return float((boundary & adjacent_c0).sum() / denominator) if denominator else float("nan")


def extract_features(
    mask: np.ndarray,
    min_object_px: int = 20,
    thickness_exact_radius_max_px: float = 16.0,
    thickness_growth: float = 1.2,
    heterogeneity_window_px: int = 512,
    pixel_size_nm_if_true: float = 25.0,
) -> dict[str, float]:
    """Calculate F01-F11 from a stitched 0/1/2 label image."""
    labels_image = np.asarray(mask, dtype=np.uint8)
    if labels_image.ndim != 2 or not np.isin(labels_image, [0, 1, 2]).all():
        raise ValueError("features require a fully analysed 2-D mask with labels 0, 1, and 2")
    height, width = labels_image.shape
    analysis_area = float(height * width)
    class0 = labels_image == 0
    class2 = labels_image == 2
    labels = _particle_labels(class2, min_object_px)
    props = _component_properties(labels)
    interior = [
        prop for prop in props
        if prop["min_row"] > 0 and prop["min_col"] > 0
        and prop["max_row"] < height and prop["max_col"] < width
    ]
    diameters = np.asarray([np.sqrt(4 * prop["area"] / np.pi) for prop in interior])
    eqdiam_median = float(np.median(diameters)) if diameters.size else float("nan")
    eqdiam_p90 = float(np.percentile(diameters, 90)) if diameters.size else float("nan")
    solidity = weighted_median(
        np.asarray([prop["solidity"] for prop in interior]),
        np.asarray([prop["area"] for prop in interior]),
    )
    count_density = count_frame_count(labels) / analysis_area * 1_000_000
    centroids = np.asarray([[p["centroid_y"], p["centroid_x"]] for p in props], dtype=np.float64)
    f06 = clark_evans_ratio(centroids, (height, width))
    thickness = local_thickness(class0, thickness_exact_radius_max_px, thickness_growth)
    f08 = float(np.median(thickness[class0])) if np.any(class0) else float("nan")
    result = {
        "F01_c0_area_fraction": float(class0.sum() / analysis_area),
        "F02_c2_area_fraction": float(class2.sum() / analysis_area),
        "F03_c2_eqdiam_median_px": eqdiam_median,
        "F04_c2_eqdiam_p90_px": eqdiam_p90,
        "F05_c2_count_density_per_Mpx": float(count_density),
        "F06_c2_clark_evans_R": f06,
        "F07_c2_solidity_area_weighted_median": solidity,
        "F08_c0_local_thickness_median_px": f08,
        "F09_c0_chord_anisotropy_h_over_v": chord_anisotropy(class0),
        "F10_c0_fraction_iqr_512px": c0_fraction_iqr(class0, heterogeneity_window_px),
        "F11_c2_perimeter_fraction_adjacent_c0": c2_boundary_fraction_adjacent_c0(labels_image),
    }
    for px_column in (
        "F03_c2_eqdiam_median_px",
        "F04_c2_eqdiam_p90_px",
        "F08_c0_local_thickness_median_px",
    ):
        result[px_column.replace("_px", "_nm_if25")] = (
            result[px_column] * pixel_size_nm_if_true
        )
    return result


def _encode_label_png(labels: np.ndarray) -> bytes:
    buffer = BytesIO()
    Image.fromarray(labels).save(buffer, format="PNG", compress_level=1)
    return buffer.getvalue()


def _feature_tile_sensitivity_work(args: tuple) -> dict[str, Any]:
    row, tiles_dir, masks_dir, cfg_s = args
    started = time.perf_counter()
    tile_path = Path(tiles_dir) / row["path"]
    mask_path = Path(masks_dir) / row["mask_path"]
    tile = np.load(tile_path)
    with Image.open(mask_path) as image:
        saved_mask = np.asarray(image, dtype=np.uint8)
    saved_png = mask_path.read_bytes()
    thresholds = (float(row["t0"]), float(row["t1"]))
    fallback = bool(row.get("threshold_fallback", False)) or any(
        np.isnan(value) for value in thresholds
    )
    denoised = _segment.denoise(tile, int(cfg_s["median_px"]))
    generated = (
        _segment.fallback_label(denoised)
        if fallback
        else _segment.label_from_thresholds(
            denoised, thresholds, int(cfg_s["min_obj_px"])
        )
    )
    if not np.array_equal(generated, saved_mask) or (
        _encode_label_png(generated) != saved_png
    ):
        raise AssertionError(f"scale-1.0 mask mismatch: {row['tile_id']}")

    sensitivity = float(cfg_s.get("sens_pct", 0.1))
    mask_pngs = []
    for scale in (round(1.0 - sensitivity, 3), 1.0, round(1.0 + sensitivity, 3)):
        if fallback or scale == 1.0:
            encoded = saved_png
        else:
            labels = _segment.label_from_thresholds(
                denoised,
                tuple(value * scale for value in thresholds),
                int(cfg_s["min_obj_px"]),
            )
            encoded = _encode_label_png(labels)
        mask_pngs.append({"scale": scale, "png": encoded})
    keys = {key: row[key] for key in ("tile_id", "sample_id", "batch", "y", "x")}
    return {
        **keys,
        "mask_pngs": mask_pngs,
        "mask_parity_checks": 1,
        "wall_s": time.perf_counter() - started,
    }


def _feature_sensitivity_chunk_work(args: tuple) -> dict[str, Any]:
    chunk_id, rows, tiles_dir, masks_dir, cfg_s = args
    started = time.perf_counter()
    results = [
        _feature_tile_sensitivity_work((row, tiles_dir, masks_dir, cfg_s))
        for row in rows
    ]
    return {
        "chunk_id": chunk_id,
        "masks": results,
        "n_tiles": len(rows),
        "mask_parity_checks": sum(result["mask_parity_checks"] for result in results),
        "wall_s": time.perf_counter() - started,
    }


def _feature_image_sensitivity_work(payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    mask_arrays: dict[str, np.ndarray] = {}
    for item in payload["mask_pngs"]:
        with Image.open(BytesIO(item["png"])) as image:
            mask_arrays[str(item["tile_id"])] = np.asarray(image, dtype=np.uint8)
    rows = pd.DataFrame(payload["rows"])
    stitched = stitch_mask(
        rows,
        None,
        tuple(payload["image_shape"]),
        int(payload["unanalysed_value"]),
        mask_arrays=mask_arrays,
    )
    metrics = extract_features(stitched, **payload["feature_params"])
    return {
        "batch": payload["batch"],
        "sample_id": payload["sample_id"],
        "scale": payload["scale"],
        **metrics,
        "wall_s": time.perf_counter() - started,
    }


def _feature_config() -> tuple[dict[str, Any], str]:
    path = _config.ROOT / "configs" / "features_v1.yaml"
    contents = path.read_bytes()
    return yaml.safe_load(contents), hashlib.sha256(contents).hexdigest()[:12]


def run(cfg: dict[str, Any]) -> None:
    from qc import kpi

    feature_cfg, feature_hash = _feature_config()
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    masks_dir = _config.resolve(cfg["data"].get("masks_dir", "data/masks"))
    index = pd.read_parquet(tiles_dir / "index.parquet")
    index = index[index["channel"] == BSE_CHANNEL]
    thresholds = pd.read_parquet(_config.ROOT / "results" / "thresholds_per_tile.parquet")
    rows = kpi.join_thresholds(thresholds, index, cfg)
    rows = rows.merge(
        index[["tile_id", "img_h", "img_w"]],
        on="tile_id",
        how="left",
        validate="one_to_one",
    )
    if len(rows) != len(index):
        raise ValueError(f"mask/index mismatch: {len(rows)} masks for {len(index)} BSE tiles")
    segmentation = cfg["segmentation"]
    min_object_px = int(segmentation["min_object_px"])
    local_thickness_cfg = feature_cfg["local_thickness"]
    records: list[dict[str, Any]] = []
    for (batch, sample_id), group in rows.groupby(["batch", "sample_id"], sort=True):
        first = group.iloc[0]
        stitched = stitch_mask(
            group,
            masks_dir,
            (int(first["img_h"]), int(first["img_w"])),
            int(feature_cfg["stitch"]["unanalysed_value"]),
        )
        record = {
            "batch": batch,
            "sample_id": sample_id,
            "scale": 1.0,
            **extract_features(
                stitched,
                min_object_px=min_object_px,
                thickness_exact_radius_max_px=float(
                    local_thickness_cfg["exact_radius_max_px"]
                ),
                thickness_growth=float(local_thickness_cfg["radius_growth"]),
                heterogeneity_window_px=int(feature_cfg["heterogeneity"]["window_px"]),
                pixel_size_nm_if_true=float(feature_cfg["pixel_size_nm_if_true"]),
            ),
        }
        records.append(record)
    output = pd.DataFrame(records)
    output["phase_identity"] = PHASE_IDENTITY
    output["features_config_hash"] = feature_hash
    output = _config.stamp(output, cfg)
    result_dir = _config.ROOT / "results"
    result_dir.mkdir(exist_ok=True)
    output.to_parquet(result_dir / "features_per_image.parquet", index=False)
    print(
        f"features: {len(output)} image rows, scale 1.0 -> "
        "results/features_per_image.parquet; run `modal run modal_app.py --task features` "
        "for ±10% sensitivity"
    )

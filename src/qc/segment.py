"""S4a multi-Otsu segmentation (segment). Owner: P2.

Reads:  data/tiles/index.parquet + BSE tiles
Writes: data/masks/<batch>/<sample_id>/<tile_id>.png   (uint8 label masks, values 0/1/2; ignored data, never committed)
        results/thresholds_per_tile.parquet            (t_lo, t_hi per tile + provenance)

Per tile: median filter (`segmentation.median_px`) -> skimage.filters.threshold_multiotsu(classes=3) on the
denoised tile -> labels 0 (dark) / 1 (mid) / 2 (bright) -> for classes 2 and 0: remove connected components
smaller than `segmentation.min_obj_px` and fill holes smaller than the same size (a full fill would swallow
bright particles enclosed by dark regions). Class 2 has priority over class 0; everything else is class 1.
Thresholds are fitted per tile only (no batch statistics, docs/FRAMEWORK.md Section 13.2).

Classes are grey-level classes. They are never given chemical names here or downstream until Polaron confirms.

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage
from skimage.filters import threshold_multiotsu
from skimage.morphology import remove_small_holes, remove_small_objects

from qc import config as _config

SEG_CHANNEL = "BSE"


def params(cfg_s: dict[str, Any]) -> dict[str, Any]:
    """Flatten configs/v1.yaml `segmentation:` into the keys the per-tile functions use."""
    if "median_px" in cfg_s:  # already flat (tests)
        return cfg_s
    den = cfg_s.get("denoise", {})
    if den.get("method", "median") != "median":
        raise ValueError(f"unsupported denoise method {den.get('method')!r}; v1 uses median")
    return {"median_px": int(den.get("size", 5)), "classes": int(cfg_s.get("classes", 3)),
            "min_obj_px": int(cfg_s.get("min_object_px", 20)),
            "sens_pct": float(cfg_s.get("threshold_perturbation", 0.10))}


def denoise(tile: np.ndarray, median_px: int) -> np.ndarray:
    return ndimage.median_filter(tile, size=median_px)


def fit_thresholds(den: np.ndarray, classes: int = 3) -> tuple[float, ...]:
    return tuple(float(t) for t in threshold_multiotsu(den, classes=classes))


def _clean(mask: np.ndarray, min_obj_px: int) -> np.ndarray:
    """Drop components and holes smaller than min_obj_px (skimage >=0.26 uses max_size, inclusive)."""
    try:
        mask = remove_small_objects(mask, max_size=min_obj_px - 1)
        return remove_small_holes(mask, max_size=min_obj_px - 1)
    except TypeError:  # skimage < 0.26
        mask = remove_small_objects(mask, min_size=min_obj_px)
        return remove_small_holes(mask, area_threshold=min_obj_px)


def label_from_thresholds(den: np.ndarray, thresholds: tuple[float, ...], min_obj_px: int) -> np.ndarray:
    raw = np.digitize(den, thresholds).astype(np.uint8)
    hi = raw == len(thresholds)
    lo = raw == 0
    if min_obj_px > 0:
        hi = _clean(hi, min_obj_px)
        lo = _clean(lo, min_obj_px)
    lab = np.ones_like(raw)
    lab[lo] = 0
    lab[hi] = len(thresholds)
    return lab


def segment_tile(tile: np.ndarray, cfg_s: dict[str, Any]) -> tuple[np.ndarray, tuple[float, ...]]:
    den = denoise(tile, int(cfg_s["median_px"]))
    th = fit_thresholds(den, int(cfg_s["classes"]))
    return label_from_thresholds(den, th, int(cfg_s["min_obj_px"])), th


def mask_path(masks_dir: Path, row) -> Path:
    return masks_dir / row["batch"] / row["sample_id"] / f"{row['tile_id']}.png"


def _work(args) -> dict[str, Any]:
    row, tiles_dir, masks_dir, cfg_s = args
    tile = np.load(Path(tiles_dir) / row["path"])
    lab, th = segment_tile(tile, cfg_s)
    out_path = mask_path(Path(masks_dir), row)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(lab, mode="L").save(out_path, compress_level=1)
    rec = {k: row[k] for k in ("tile_id", "sample_id", "batch", "channel", "y", "x")}
    rec.update({f"t{i}": t for i, t in enumerate(th)})
    rec["mask_path"] = str(out_path.relative_to(Path(masks_dir)))
    return rec


def run(cfg: dict[str, Any]) -> None:
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    masks_dir = _config.resolve(cfg["data"].get("masks_dir", "data/masks"))
    index = pd.read_parquet(tiles_dir / "index.parquet")
    channel = cfg["segmentation"].get("channel", SEG_CHANNEL)
    index = index[index["channel"] == channel]
    cfg_s = params(cfg["segmentation"])
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(_work, [(r, str(tiles_dir), str(masks_dir), cfg_s) for r in index.to_dict("records")],
                           chunksize=8))
    th = _config.stamp(pd.DataFrame(rows), cfg)
    res = _config.ROOT / "results"
    res.mkdir(exist_ok=True)
    th.to_parquet(res / "thresholds_per_tile.parquet", index=False)
    print(f"segment: {len(th)} {channel} tiles -> {masks_dir.relative_to(_config.ROOT)}/, results/thresholds_per_tile.parquet")

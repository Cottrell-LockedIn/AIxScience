"""S2 tiling (tiles). Owner: P1.

Crop border, cut fixed-size tiles with stride, keep an index so every tile maps back to its image.

Reads:  data/raw/**/*.tif (channel `data.read_channel` of the RGB TIFF)
Writes: data/tiles/<batch>/<sample>_<channel>_<y>_<x>.npy (uint8, git-ignored),
        data/tiles/index.parquet (tile_id, sample_id, batch, channel, y, x, h, w, path, config_hash, git_sha),
        data/tiles/previews/<batch>_<sample>_<channel>.png (downscaled by `tiling.preview_downscale`),
        results/audit/index_sample.csv (20 rows of the index, committed)

Coordinates (y, x) are in the cropped image frame, i.e. after removing `data.border_crop_px` from every side.
Partial tiles at the bottom/right border are dropped (`tiling.min_fill: 1.0`).

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import tifffile
from skimage.io import imsave

from qc import config as _config

NAME_RE = re.compile(r"^img_(?P<sample>[a-z0-9]{8})_(?P<channel>BSE|Inlens|ETD|SE)\.tif$")


def tile_grid(height: int, width: int, tile: int, stride: int) -> list[tuple[int, int]]:
    """Top-left corners of all full tiles (no partial tiles) in row-major order.

    Stride-aligned positions plus, when the grid does not reach the bottom/right edge, one extra tile
    anchored on that edge so every pixel is covered (the last tile overlaps its neighbour by more than usual).
    """
    if height < tile or width < tile:
        return []

    def starts(n: int) -> list[int]:
        s = list(range(0, n - tile + 1, stride))
        if s[-1] != n - tile:  # stride grid stops short of the edge: anchor one last full tile on it
            s.append(n - tile)
        return s

    return [(y, x) for y in starts(height) for x in starts(width)]


def read_gray(path: Path, read_channel: int) -> np.ndarray:
    arr = tifffile.imread(path)
    if arr.ndim == 3:
        arr = arr[..., read_channel]
    return np.ascontiguousarray(arr.astype(np.uint8, copy=False))


def crop_border(arr: np.ndarray, px: int) -> np.ndarray:
    return arr[px:arr.shape[0] - px, px:arr.shape[1] - px] if px else arr


def tile_image(img: np.ndarray, sample_id: str, batch: str, channel: str, cfg: dict[str, Any],
               tiles_dir: Path) -> list[dict[str, Any]]:
    t, s = int(cfg["tiling"]["tile_px"]), int(cfg["tiling"]["stride_px"])
    out_dir = tiles_dir / batch
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for y, x in tile_grid(img.shape[0], img.shape[1], t, s):
        tile_id = f"{sample_id}_{channel}_{y:05d}_{x:05d}"
        rel = Path(batch) / f"{tile_id}.npy"
        np.save(tiles_dir / rel, img[y:y + t, x:x + t])
        rows.append(dict(tile_id=tile_id, sample_id=sample_id, batch=batch, channel=channel,
                         y=y, x=x, h=t, w=t, img_h=int(img.shape[0]), img_w=int(img.shape[1]), path=str(rel)))
    return rows


def _process(args) -> list[dict[str, Any]]:
    path, cfg, tiles_dir = args
    p = Path(path)
    m = NAME_RE.match(p.name)
    if not m:
        return []
    img = crop_border(read_gray(p, int(cfg["data"]["read_channel"])), int(cfg["data"]["border_crop_px"]))
    batch = p.parent.name
    rows = tile_image(img, m["sample"], batch, m["channel"], cfg, tiles_dir)
    ds = int(cfg["tiling"]["preview_downscale"])
    prev_dir = tiles_dir / "previews"
    prev_dir.mkdir(parents=True, exist_ok=True)
    imsave(prev_dir / f"{batch}_{m['sample']}_{m['channel']}.png", img[::ds, ::ds], check_contrast=False)
    return rows


def build_index(raw_dir: Path, tiles_dir: Path, cfg: dict[str, Any], workers: int | None = None) -> pd.DataFrame:
    paths = sorted(raw_dir.glob("*/*.tif"))
    with ProcessPoolExecutor(max_workers=workers) as ex:
        chunks = list(ex.map(_process, [(str(p), cfg, tiles_dir) for p in paths]))
    rows = [r for c in chunks for r in c]
    return _config.stamp(pd.DataFrame(rows), cfg)


def load_tile(index_row, tiles_dir: Path) -> np.ndarray:
    return np.load(tiles_dir / index_row["path"])


def run(cfg: dict[str, Any]) -> None:
    raw_dir = _config.resolve(cfg["data"]["raw_dir"])
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    tiles_dir.mkdir(parents=True, exist_ok=True)
    index = build_index(raw_dir, tiles_dir, cfg)
    if index.empty:
        raise SystemExit(f"tiles: no TIFFs under {raw_dir}")
    index.to_parquet(tiles_dir / "index.parquet", index=False)
    sample = (index.sample(frac=1.0, random_state=int(cfg["seed"]))
                   .groupby("batch").head(7)
                   .head(20).sort_values(["batch", "sample_id", "channel", "y", "x"]))
    out = _config.ROOT / "results" / "audit"
    out.mkdir(parents=True, exist_ok=True)
    sample.to_csv(out / "index_sample.csv", index=False)
    per_img = index.groupby(["batch", "sample_id", "channel"]).size()
    print(f"tiles: {len(index)} tiles from {index['sample_id'].nunique()} images x {index['channel'].nunique()} "
          f"channels; tiles per image/channel {per_img.min()}-{per_img.max()} -> {tiles_dir}/index.parquet")

"""S4b KPIs from masks (kpi). Owner: P2.

Reads:  data/tiles/index.parquet, BSE tiles, data/masks/**, results/thresholds_per_tile.parquet
Writes: results/kpi_per_tile.parquet        (one row per BSE tile)
        results/kpi_per_image.parquet       (mean and sd over tiles per image, n_tiles)
        results/kpi_sensitivity.parquet     (class fractions per tile with thresholds scaled by 1 +/- segmentation.sens_pct,
                                             plus the per-image aggregate; `scale` column = 0.9 / 1.0 / 1.1)
        results/audit/overlays/*.png        (6 example tiles, 2 per batch, class 0 and class 2 outlined)

KPIs per tile (pixel units; pixel size is unconfirmed, see docs/DATA_AUDIT.md):
- frac_c0, frac_c1, frac_c2            : area fraction of each grey-level class
- c2_count_density_per_Mpx             : class-2 connected components per 1e6 px
- c2_eqdiam_median_px, c2_eqdiam_p90_px: equivalent circular diameter of class-2 components
- c0_region_eqdiam_median_px, c0_region_area_mean_px: size of class-0 connected regions
Per-image KPI = mean over the image's tiles (tiles overlap 50 %, so interior pixels are weighted ~uniformly);
_sd columns give the between-tile spread, n_tiles the tile count. Tiles are not independent samples.

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
from PIL import Image
from skimage.measure import label, regionprops_table
from skimage.segmentation import find_boundaries

from qc import config as _config
from qc import segment as _segment

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

KPI_COLS = ["frac_c0", "frac_c1", "frac_c2", "c2_count_density_per_Mpx", "c2_eqdiam_median_px",
            "c2_eqdiam_p90_px", "c0_region_eqdiam_median_px", "c0_region_area_mean_px"]
FRAC_COLS = ["frac_c0", "frac_c1", "frac_c2"]


def fractions(lab: np.ndarray) -> dict[str, float]:
    n = lab.size
    return {f"frac_c{k}": float((lab == k).sum() / n) for k in range(3)}


def _eqdiams(mask: np.ndarray) -> np.ndarray:
    if not mask.any():
        return np.array([])
    props = regionprops_table(label(mask, connectivity=1), properties=("equivalent_diameter_area", "area"))
    return props["equivalent_diameter_area"], props["area"]


def kpis(lab: np.ndarray) -> dict[str, float]:
    out = fractions(lab)
    d2 = _eqdiams(lab == 2)
    if len(d2):
        eq2, _ = d2
        out.update(c2_count_density_per_Mpx=float(len(eq2) / lab.size * 1e6),
                   c2_eqdiam_median_px=float(np.median(eq2)), c2_eqdiam_p90_px=float(np.percentile(eq2, 90)))
    else:
        out.update(c2_count_density_per_Mpx=0.0, c2_eqdiam_median_px=np.nan, c2_eqdiam_p90_px=np.nan)
    d0 = _eqdiams(lab == 0)
    if len(d0):
        eq0, area0 = d0
        out.update(c0_region_eqdiam_median_px=float(np.median(eq0)), c0_region_area_mean_px=float(area0.mean()))
    else:
        out.update(c0_region_eqdiam_median_px=np.nan, c0_region_area_mean_px=np.nan)
    return out


def _work(args) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row, tiles_dir, masks_dir, cfg_s = args
    keys = {k: row[k] for k in ("tile_id", "sample_id", "batch", "y", "x")}
    lab = np.asarray(Image.open(Path(masks_dir) / row["mask_path"]))
    rec = {**keys, **kpis(lab)}
    th = (row["t0"], row["t1"])
    den = _segment.denoise(np.load(Path(tiles_dir) / row["path"]), int(cfg_s["median_px"]))
    sens = []
    for scale in (1.0 - cfg_s["sens_pct"], 1.0, 1.0 + cfg_s["sens_pct"]):
        lab_s = lab if scale == 1.0 else _segment.label_from_thresholds(
            den, tuple(t * scale for t in th), int(cfg_s["min_obj_px"]))
        sens.append({**keys, "scale": round(scale, 3), **fractions(lab_s)})
    return rec, sens


def per_image(per_tile: pd.DataFrame, cols: list[str], extra_keys: list[str] | None = None) -> pd.DataFrame:
    keys = ["batch", "sample_id"] + (extra_keys or [])
    g = per_tile.groupby(keys, sort=True)
    out = pd.concat([g[cols].mean(), g[cols].std().add_suffix("_sd")], axis=1)
    out["n_tiles"] = g.size()
    return out.reset_index()


def overlay(tile: np.ndarray, lab: np.ndarray, title: str, out_png: Path) -> None:
    rgb = np.stack([tile] * 3, axis=-1).astype(np.float32) / 255.0
    b0 = find_boundaries(lab == 0, mode="inner")
    b2 = find_boundaries(lab == 2, mode="inner")
    rgb[b0] = (0.1, 0.5, 1.0)
    rgb[b2] = (1.0, 0.2, 0.1)
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.3))
    axes[0].imshow(tile, cmap="gray", vmin=0, vmax=255)
    axes[0].set_title("BSE tile")
    axes[1].imshow(rgb)
    axes[1].set_title("class 0 (dark) blue, class 2 (bright) red; class 1 unmarked")
    for ax in axes:
        ax.axis("off")
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def make_overlays(th: pd.DataFrame, tiles_dir: Path, masks_dir: Path, out_dir: Path, per_batch: int = 2) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for batch, g in th.groupby("batch", sort=True):
        for sample_id in sorted(g["sample_id"].unique())[:per_batch]:
            gs = g[g["sample_id"] == sample_id].sort_values(["y", "x"])
            row = gs.iloc[len(gs) // 2]
            tile = np.load(tiles_dir / row["path"])
            lab = np.asarray(Image.open(masks_dir / row["mask_path"]))
            fr = fractions(lab)
            title = (f"{batch} / {sample_id} / {row['tile_id']}  thresholds=({row['t0']:.0f}, {row['t1']:.0f})  "
                     f"fractions c0={fr['frac_c0']:.2f} c1={fr['frac_c1']:.2f} c2={fr['frac_c2']:.2f}")
            p = out_dir / f"{batch}_{sample_id}_{row['tile_id']}.png"
            overlay(tile, lab, title, p)
            written.append(p)
    return written


def run(cfg: dict[str, Any]) -> None:
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    masks_dir = _config.resolve(cfg["data"].get("masks_dir", "data/masks"))
    res = _config.ROOT / "results"
    index = pd.read_parquet(tiles_dir / "index.parquet")
    th = pd.read_parquet(res / "thresholds_per_tile.parquet")
    th = th.merge(index[["tile_id", "path"]], on="tile_id", how="left")
    cfg_s = _segment.params(cfg["segmentation"])
    with ProcessPoolExecutor() as ex:
        results = list(ex.map(_work, [(r, str(tiles_dir), str(masks_dir), cfg_s) for r in th.to_dict("records")],
                              chunksize=8))
    per_tile = _config.stamp(pd.DataFrame([r for r, _ in results]), cfg)
    sens_tile = pd.DataFrame([s for _, ss in results for s in ss])
    sens_img = per_image(sens_tile, FRAC_COLS, ["scale"])
    sens = _config.stamp(pd.concat([sens_tile.assign(level="tile"), sens_img.assign(level="image")],
                                   ignore_index=True), cfg)
    img = _config.stamp(per_image(per_tile, KPI_COLS), cfg)
    per_tile.to_parquet(res / "kpi_per_tile.parquet", index=False)
    img.to_parquet(res / "kpi_per_image.parquet", index=False)
    sens.to_parquet(res / "kpi_sensitivity.parquet", index=False)
    paths = make_overlays(th, tiles_dir, masks_dir, res / "audit" / "overlays")
    print(f"kpi: {len(per_tile)} tiles, {len(img)} images -> results/kpi_per_*.parquet, kpi_sensitivity.parquet, "
          f"{len(paths)} overlays")

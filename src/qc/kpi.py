"""S4b KPIs from masks (kpi). Owner: P2.

Reads:  data/tiles/index.parquet, BSE tiles, data/masks/**, results/thresholds_per_tile.parquet
Writes: results/kpi_per_tile.parquet        (one row per BSE tile)
        results/kpi_per_image.parquet       (mean and sd over tiles per image, n_tiles)
        results/kpi_sensitivity.parquet     (all KPI columns per tile and image at scales 0.9 / 1.0 / 1.1)
        results/audit/overlays/*.png        (6 example tiles, 2 per batch, class 0 and class 2 outlined)

KPIs per tile (pixel units; pixel size is unconfirmed, see docs/DATA_AUDIT.md):
- frac_c0, frac_c1, frac_c2            : area fraction of each grey-level class
- c2_count_density_per_Mpx             : class-2 connected components per 1e6 px
- c2_eqdiam_median_px, c2_eqdiam_p90_px: equivalent circular diameter of class-2 components
- c0_region_eqdiam_median_px, c0_region_area_mean_px: size of class-0 connected regions
- c0_region_eqdiam_median_px remains the pore-size KPI
- class-1 flake size/aspect/percolation, class-0 crack-like fraction, and class-2 TPC length
Per-image KPI = mean over the image's tiles (tiles overlap 50 %, so interior pixels are weighted ~uniformly);
_sd columns give the between-tile spread, n_tiles the tile count. Tiles are not independent samples.
Phase identity is stated by Polaron, not image-verified.

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from io import BytesIO
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
            "c2_eqdiam_p90_px", "c0_region_eqdiam_median_px", "c0_region_area_mean_px",
            "c1_flake_eqdiam_median_px", "c1_flake_aspect_median", "c1_largest_component_frac",
            "c0_cracklike_frac", "c2_tpc_length_px"]
FRAC_COLS = ["frac_c0", "frac_c1", "frac_c2"]
PHASE_IDENTITY = "stated by Polaron, not image-verified"


def fractions(lab: np.ndarray) -> dict[str, float]:
    n = lab.size
    return {f"frac_c{k}": float((lab == k).sum() / n) for k in range(3)}


@lru_cache(maxsize=16)
def _tpc_geometry(
    height: int, width: int, max_r_px: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    dy = np.arange(-max_r_px, max_r_px + 1)
    dx = np.arange(-max_r_px, max_r_px + 1)
    bins = np.floor(np.hypot(dy[:, None], dx[None, :]) + 0.5).astype(np.int16)
    valid = bins <= max_r_px
    fft_shape = (2 * height - 1, 2 * width - 1)
    yidx = np.mod(dy, fft_shape[0])
    xidx = np.mod(dx, fft_shape[1])
    overlap = (height - np.abs(dy))[:, None] * (width - np.abs(dx))[None, :]
    bin_ids = bins[valid]
    radial_counts = np.bincount(bin_ids, minlength=max_r_px + 1)
    arrays = (yidx, xidx, valid, bin_ids, overlap, radial_counts)
    for array in arrays:
        array.setflags(write=False)
    return arrays


def _eqdiams(mask: np.ndarray) -> np.ndarray:
    if not mask.any():
        return np.array([])
    props = regionprops_table(label(mask, connectivity=1), properties=("equivalent_diameter_area", "area"))
    return props["equivalent_diameter_area"], props["area"]


def tpc_length(mask: np.ndarray, max_r_px: int = 256) -> float:
    indicator = np.asarray(mask, dtype=np.float64)
    phi = float(indicator.mean())
    if phi == 0.0 or phi == 1.0:
        return float("nan")

    h, w = indicator.shape
    max_r_px = min(int(max_r_px), h - 1, w - 1)
    if max_r_px < 1:
        return float("nan")
    fft_shape = (2 * h - 1, 2 * w - 1)
    spectrum = np.fft.rfftn(indicator, s=fft_shape)
    autocorrelation = np.fft.irfftn(spectrum * spectrum.conj(), s=fft_shape).real

    yidx, xidx, valid, bin_ids, overlap, radial_counts = _tpc_geometry(h, w, max_r_px)
    pairs = autocorrelation[np.ix_(yidx, xidx)]
    s2 = pairs / overlap
    sums = np.bincount(bin_ids, weights=s2[valid], minlength=max_r_px + 1)
    radial_s2 = np.divide(
        sums,
        radial_counts,
        out=np.full(max_r_px + 1, np.nan),
        where=radial_counts > 0,
    )
    corr = (radial_s2 - phi * phi) / (phi - phi * phi)
    target = 1.0 / np.e
    for radius in range(1, max_r_px + 1):
        if np.isfinite(corr[radius]) and corr[radius] <= target:
            previous = radius - 1
            if not np.isfinite(corr[previous]) or corr[previous] == corr[radius]:
                return float(radius)
            fraction = (target - corr[previous]) / (corr[radius] - corr[previous])
            return float(previous + fraction)
    return float("nan")


def kpis(
    lab: np.ndarray, crack_aspect_min: float = 5.0, tpc_max_r_px: int = 256
) -> dict[str, float]:
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

    props1 = regionprops_table(
        label(lab == 1, connectivity=1),
        properties=("area", "equivalent_diameter_area", "major_axis_length", "minor_axis_length"),
    )
    if len(props1["area"]):
        out["c1_flake_eqdiam_median_px"] = float(np.median(props1["equivalent_diameter_area"]))
        minor = props1["minor_axis_length"]
        valid_aspect = minor > 0
        out["c1_flake_aspect_median"] = (
            float(np.median(props1["major_axis_length"][valid_aspect] / minor[valid_aspect]))
            if valid_aspect.any() else float("nan")
        )
        out["c1_largest_component_frac"] = float(props1["area"].max() / props1["area"].sum())
    else:
        out.update(
            c1_flake_eqdiam_median_px=float("nan"),
            c1_flake_aspect_median=float("nan"),
            c1_largest_component_frac=0.0,
        )

    props0 = regionprops_table(
        label(lab == 0, connectivity=1),
        properties=("area", "major_axis_length", "minor_axis_length"),
    )
    total0 = float(props0["area"].sum()) if len(props0["area"]) else 0.0
    if total0 == 0:
        out["c0_cracklike_frac"] = 0.0
    else:
        minor0 = props0["minor_axis_length"]
        aspect0 = np.divide(
            props0["major_axis_length"], minor0,
            out=np.full_like(minor0, np.inf, dtype=np.float64), where=minor0 > 0,
        )
        out["c0_cracklike_frac"] = float(
            props0["area"][aspect0 >= crack_aspect_min].sum() / total0
        )
    out["c2_tpc_length_px"] = tpc_length(lab == 2, tpc_max_r_px)
    return out


def sensitivity_for_tile(
    row: dict[str, Any],
    tile: np.ndarray,
    saved_mask: np.ndarray,
    cfg_s: dict[str, Any],
    saved_png: bytes,
) -> list[dict[str, Any]]:
    keys = {k: row[k] for k in ("tile_id", "sample_id", "batch", "y", "x")}
    thresholds = (float(row["t0"]), float(row["t1"]))
    fallback = bool(row.get("threshold_fallback", False)) or any(
        np.isnan(value) for value in thresholds
    )
    denoised = _segment.denoise(tile, int(cfg_s["median_px"]))
    generated = (
        _segment.fallback_label(denoised)
        if fallback
        else _segment.label_from_thresholds(denoised, thresholds, int(cfg_s["min_obj_px"]))
    )
    encoded = BytesIO()
    Image.fromarray(generated, mode="L").save(encoded, format="PNG", compress_level=1)
    if not np.array_equal(generated, saved_mask) or encoded.getvalue() != saved_png:
        raise AssertionError(f"scale-1.0 mask mismatch: {row['tile_id']}")

    sensitivity = float(cfg_s.get("sens_pct", 0.1))
    output = []
    for scale in (round(1.0 - sensitivity, 3), 1.0, round(1.0 + sensitivity, 3)):
        if fallback:
            labels = saved_mask
        elif scale == 1.0:
            labels = generated
        else:
            labels = _segment.label_from_thresholds(
                denoised,
                tuple(value * scale for value in thresholds),
                int(cfg_s["min_obj_px"]),
            )
        output.append({
            **keys,
            "scale": scale,
            **kpis(labels, float(cfg_s["crack_aspect_min"]), int(cfg_s["tpc_max_r_px"])),
        })
    return output


def _sensitivity_work(args) -> dict[str, Any]:
    row, tiles_dir, masks_dir, cfg_s = args
    tile_path = Path(tiles_dir) / row["path"]
    mask_path = Path(masks_dir) / row["mask_path"]
    tile = np.load(tile_path)
    with Image.open(mask_path) as image:
        saved_mask = np.asarray(image)
    rows = sensitivity_for_tile(
        row, tile, saved_mask, cfg_s, mask_path.read_bytes()
    )
    return {"rows": rows, "mask_parity_checks": 1}


def _work(args) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row, tiles_dir, masks_dir, cfg_s = args
    keys = {k: row[k] for k in ("tile_id", "sample_id", "batch", "y", "x")}
    mask_path = Path(masks_dir) / row["mask_path"]
    with Image.open(mask_path) as image:
        lab = np.asarray(image)
    rec = {**keys, **kpis(lab, cfg_s["crack_aspect_min"], cfg_s["tpc_max_r_px"])}
    tile = np.load(Path(tiles_dir) / row["path"])
    sens = sensitivity_for_tile(row, tile, lab, cfg_s, mask_path.read_bytes())
    return rec, sens


def _base_work(args) -> dict[str, Any]:
    row, masks_dir, cfg_s = args
    keys = {k: row[k] for k in ("tile_id", "sample_id", "batch", "y", "x")}
    lab = np.asarray(Image.open(Path(masks_dir) / row["mask_path"]))
    return {
        **keys,
        **kpis(lab, cfg_s["crack_aspect_min"], cfg_s["tpc_max_r_px"]),
    }


def join_thresholds(th: pd.DataFrame, index: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Attach current tile paths to the saved thresholds, refusing to mix stale masks with re-tiled data.

    A tile_id encodes sample/channel/position but not the tiling config or source pixels, so the saved
    thresholds must come from the same config (hash) as the current run and the current index, and every
    threshold row must match exactly one index row at the same (y, x) with the same tile size.
    """
    for name, hashes in (("thresholds_per_tile", th["config_hash"].unique()), ("tiles index", index["config_hash"].unique())):
        if len(hashes) != 1 or hashes[0] != cfg["_hash"]:
            raise RuntimeError(f"{name} was produced with config hash {list(hashes)}, current config is {cfg['_hash']}: "
                               "re-run `qc tiles` and `qc segment` before `qc kpi`")
    cols = ["tile_id", "path", "y", "x", "h", "w"]
    merged = th.merge(index[cols].rename(columns={"y": "y_idx", "x": "x_idx"}), on="tile_id", how="inner", validate="one_to_one")
    if len(merged) != len(th):
        raise RuntimeError(f"{len(th) - len(merged)} threshold rows have no tile in the current index: re-run `qc segment`")
    if not ((merged["y"] == merged["y_idx"]) & (merged["x"] == merged["x_idx"])).all():
        raise RuntimeError("tile positions in thresholds_per_tile differ from the current index: re-run `qc segment`")
    return merged.drop(columns=["y_idx", "x_idx", "h", "w"])


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
                     f"fractions c0={fr['frac_c0']:.2f} c1={fr['frac_c1']:.2f} c2={fr['frac_c2']:.2f}\n"
                     f"phase_identity: {PHASE_IDENTITY}")
            p = out_dir / f"{batch}_{sample_id}_{row['tile_id']}.png"
            overlay(tile, lab, title, p)
            written.append(p)
    return written


def make_inspection_panels(
    th: pd.DataFrame, per_tile: pd.DataFrame, tiles_dir: Path, masks_dir: Path, out_dir: Path,
    cfg: dict[str, Any],
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    images = th[["batch", "sample_id"]].drop_duplicates().sort_values(["batch", "sample_id"]).reset_index(drop=True)
    selected = []
    for _, group in images.groupby("batch", sort=True):
        selected.append(group.iloc[int(rng.integers(len(group)))])
    used = {row["sample_id"] for row in selected}
    remaining = images.loc[~images["sample_id"].isin(used)].reset_index(drop=True)
    selected.extend(remaining.iloc[i] for i in rng.choice(len(remaining), 2, replace=False))

    metrics = per_tile.set_index("tile_id")
    provenance = _config.provenance(cfg)
    written = []
    for image in selected:
        choices = th[(th["batch"] == image["batch"]) & (th["sample_id"] == image["sample_id"])]
        choices = choices.sort_values(["y", "x"]).reset_index(drop=True)
        row = choices.iloc[int(rng.integers(len(choices)))]
        tile = np.load(tiles_dir / row["path"])
        lab = np.asarray(Image.open(masks_dir / row["mask_path"]))
        gray = tile.astype(np.float32) / 255.0
        color = np.stack([gray, gray, gray], axis=-1)
        palette = {0: np.array([0.10, 0.40, 1.00]), 1: np.array([1.00, 0.82, 0.08]), 2: np.array([1.00, 0.12, 0.08])}
        overlay_img = color.copy()
        for class_id, rgb in palette.items():
            selected_pixels = lab == class_id
            overlay_img[selected_pixels] = 0.45 * color[selected_pixels] + 0.55 * rgb

        values = []
        for name in KPI_COLS:
            value = metrics.at[row["tile_id"], name]
            values.append(f"{name}={value:.3g}" if np.isfinite(value) else f"{name}=NaN")
        metrics_text = "\n".join("  ".join(values[i:i + 4]) for i in range(0, len(values), 4))
        fig, axes = plt.subplots(1, 5, figsize=(25, 6.5))
        axes[0].imshow(tile, cmap="gray", vmin=0, vmax=255)
        axes[1].imshow(overlay_img)
        for ax, class_id in zip(axes[2:], range(3)):
            ax.imshow(lab == class_id, cmap="gray", vmin=0, vmax=1)
            ax.set_title(f"class {class_id}")
        axes[0].set_title("raw BSE")
        axes[1].set_title("three-class overlay")
        for ax in axes:
            ax.axis("off")
        fig.suptitle(
            f"{row['tile_id']} | {row['batch']} | phase_identity: {PHASE_IDENTITY}\n{metrics_text}",
            fontsize=8.5, y=0.99,
        )
        fig.tight_layout(rect=[0, 0, 1, 0.88])
        out = out_dir / f"b1_tile_{row['tile_id']}.png"
        fig.savefig(
            out, dpi=120,
            metadata={
                "Description": f"config_hash={provenance['config_hash']}; git_sha={provenance['git_sha']}; "
                               f"phase_identity: {PHASE_IDENTITY}",
            },
        )
        plt.close(fig)
        written.append(out)
    return written


def run(cfg: dict[str, Any]) -> None:
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    masks_dir = _config.resolve(cfg["data"].get("masks_dir", "data/masks"))
    res = _config.ROOT / "results"
    index = pd.read_parquet(tiles_dir / "index.parquet")
    th = pd.read_parquet(res / "thresholds_per_tile.parquet")
    th = join_thresholds(th, index, cfg)
    cfg_s = {
        **_segment.params(cfg["segmentation"]),
        "crack_aspect_min": float(cfg["kpi_extra"]["crack_aspect_min"]),
        "tpc_max_r_px": int(cfg["kpi_extra"]["tpc_max_r_px"]),
    }
    with ProcessPoolExecutor() as ex:
        results = list(ex.map(
            _base_work, [(r, str(masks_dir), cfg_s) for r in th.to_dict("records")],
            chunksize=8,
        ))
    per_tile = pd.DataFrame(results)
    per_tile["phase_identity"] = PHASE_IDENTITY
    per_tile = _config.stamp(per_tile, cfg)
    img = per_image(per_tile, KPI_COLS)
    img["phase_identity"] = PHASE_IDENTITY
    img = _config.stamp(img, cfg)
    per_tile.to_parquet(res / "kpi_per_tile.parquet", index=False)
    img.to_parquet(res / "kpi_per_image.parquet", index=False)
    paths = make_overlays(th, tiles_dir, masks_dir, res / "audit" / "overlays")
    inspection = make_inspection_panels(th, per_tile, tiles_dir, masks_dir, res / "inspection", cfg)
    print(f"kpi: {len(per_tile)} tiles, {len(img)} images -> results/kpi_per_*.parquet; "
          f"run `modal run modal_app.py --task kpi` for sensitivity; "
          f"{len(paths)} overlays, {len(inspection)} inspection panels")

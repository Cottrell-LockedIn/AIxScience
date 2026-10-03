"""S3 artefact covariates (artefacts). Owner: P2.

Measure acquisition artefacts as covariates. Never remove them from the images used for KPIs.

Reads:  data/tiles/index.parquet + tiles (all detector channels)
Writes: results/artefacts_per_tile.parquet  (one row per tile)
        results/artefacts_per_image.parquet (one row per sample_id x channel: mean and sd over that image's tiles, n_tiles)
        results/audit/artefacts_by_batch.png

Per-tile covariates (all in pixel / grey-level units; images are never modified):
- curtaining_score: FIB curtaining = stripes that run vertically in the image (along the milling direction).
  Their energy sits on the horizontal spatial-frequency axis (k_y ~ 0, k_x != 0). Score = power within
  +/-`artefacts.curtaining_band_px` frequency bins of the k_y = 0 line, at radii above
  `artefacts.curtaining_min_freq` cycles/px, divided by the total power at those radii. A Hann window is applied
  before the FFT to suppress tile-border leakage. The brief's wording "vertical spatial-frequency axis" is read as
  "the axis carrying vertical-stripe energy"; the orthogonal band (k_x ~ 0) is reported as hstripe_score as a control.
- edge_charging: mean of the outer `artefacts.edge_band_pct` frame band minus the centre mean (grey levels).
  Reported for every channel; the Inlens value is the one the brief asks for.
- noise_sigma: 1.4826 * median absolute deviation of the Laplacian (grey levels, Laplacian units).
- sharpness: variance of the Laplacian.
- mean, std, p01, p99, detector (= channel name).

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
from scipy import ndimage

from qc import config as _config

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

METRICS = ["curtaining_score", "hstripe_score", "edge_charging", "noise_sigma", "sharpness", "mean", "std", "p01", "p99"]


def stripe_scores(tile: np.ndarray, band_px: int, min_freq: float) -> tuple[float, float]:
    """(vertical-stripe score on the k_y~0 band, horizontal-stripe score on the k_x~0 band)."""
    a = tile.astype(np.float64)
    a -= a.mean()
    h, w = a.shape
    win = np.outer(np.hanning(h), np.hanning(w))
    p = np.abs(np.fft.fftshift(np.fft.fft2(a * win))) ** 2
    ky = np.fft.fftshift(np.fft.fftfreq(h))[:, None]
    kx = np.fft.fftshift(np.fft.fftfreq(w))[None, :]
    r = np.sqrt(ky ** 2 + kx ** 2)
    annulus = r > min_freq
    total = p[annulus].sum()
    if total <= 0:
        return float("nan"), float("nan")
    cy, cx = h // 2, w // 2
    iy = np.arange(h)[:, None]
    ix = np.arange(w)[None, :]
    vband = annulus & (np.abs(iy - cy) <= band_px)
    hband = annulus & (np.abs(ix - cx) <= band_px)
    return float(p[vband].sum() / total), float(p[hband].sum() / total)


def edge_charging(tile: np.ndarray, band_pct: float) -> float:
    h, w = tile.shape
    by, bx = max(1, int(round(h * band_pct))), max(1, int(round(w * band_pct)))
    a = tile.astype(np.float64)
    inner = a[by:h - by, bx:w - bx]
    outer_sum = a.sum() - inner.sum()
    outer_n = a.size - inner.size
    return float(outer_sum / outer_n - inner.mean())


def tile_metrics(tile: np.ndarray, cfg_a: dict[str, Any]) -> dict[str, float]:
    a = tile.astype(np.float64)
    lap = ndimage.laplace(a)
    v, hs = stripe_scores(tile, int(cfg_a["curtaining_band_px"]), float(cfg_a["curtaining_min_freq"]))
    return dict(
        curtaining_score=v, hstripe_score=hs,
        edge_charging=edge_charging(tile, float(cfg_a["edge_band_pct"])),
        noise_sigma=float(1.4826 * np.median(np.abs(lap - np.median(lap)))),
        sharpness=float(lap.var()),
        mean=float(a.mean()), std=float(a.std()),
        p01=float(np.percentile(a, 1)), p99=float(np.percentile(a, 99)),
    )


def _work(args) -> dict[str, Any]:
    row, tiles_dir, cfg_a = args
    tile = np.load(Path(tiles_dir) / row["path"])
    out = {k: row[k] for k in ("tile_id", "sample_id", "batch", "channel", "y", "x")}
    out["detector"] = row["channel"]
    out.update(tile_metrics(tile, cfg_a))
    return out


def per_image(per_tile: pd.DataFrame) -> pd.DataFrame:
    g = per_tile.groupby(["batch", "sample_id", "channel"], sort=True)
    agg = g[METRICS].mean()
    sd = g[METRICS].std().add_suffix("_sd")
    out = pd.concat([agg, sd], axis=1)
    out["n_tiles"] = g.size()
    out["detector"] = out.index.get_level_values("channel")
    return out.reset_index()


def plot_by_batch(img: pd.DataFrame, out_png: Path) -> None:
    panels = [("curtaining_score", "BSE"), ("curtaining_score", "Inlens"), ("curtaining_score", "third"),
              ("edge_charging", "Inlens"), ("noise_sigma", "BSE"), ("sharpness", "BSE")]
    df = img.copy()
    df["slot"] = df["channel"].where(df["channel"].isin(["BSE", "Inlens"]), "third")
    batches = sorted(df["batch"].unique())
    colors = {b: f"C{i}" for i, b in enumerate(batches)}
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    rng = np.random.default_rng(0)
    for ax, (metric, slot) in zip(axes.ravel(), panels):
        d = df[df["slot"] == slot]
        for i, b in enumerate(batches):
            v = d.loc[d["batch"] == b, metric].to_numpy()
            xj = i + rng.uniform(-0.18, 0.18, len(v))
            ax.scatter(xj, v, s=22, color=colors[b], alpha=0.85, label=f"{b} (n={len(v)})")
            if len(v):
                ax.hlines(np.median(v), i - 0.3, i + 0.3, color=colors[b], lw=2)
        ax.set_xticks(range(len(batches)), batches)
        ax.set_title(f"{metric} ({slot if slot != 'third' else 'ETD/SE'})", fontsize=10)
        ax.grid(alpha=0.3)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Artefact covariates per image (mean over tiles), by batch; line = batch median; n = images", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def run(cfg: dict[str, Any]) -> None:
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    index = pd.read_parquet(tiles_dir / "index.parquet")
    cfg_a = cfg["artefacts"]
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(_work, [(r, str(tiles_dir), cfg_a) for r in index.to_dict("records")], chunksize=16))
    per_tile = _config.stamp(pd.DataFrame(rows), cfg)
    img = _config.stamp(per_image(per_tile), cfg)
    res = _config.ROOT / "results"
    (res / "audit").mkdir(parents=True, exist_ok=True)
    per_tile.to_parquet(res / "artefacts_per_tile.parquet", index=False)
    img.to_parquet(res / "artefacts_per_image.parquet", index=False)
    plot_by_batch(img, res / "audit" / "artefacts_by_batch.png")
    print(f"artefacts: {len(per_tile)} tiles, {len(img)} image x channel rows -> results/artefacts_per_*.parquet")

"""Charging / topography-glow check on the class-2 (bright BSE) mask (charging). Exploratory, added after S1-S5.

Question: how much of the class-2 area (silicon, stated by Polaron, not image-verified) is bright because of
charging, edge glow or relief rather than Z-contrast? Rationale offered by the team: a true high-Z particle is
bright in BSE but not necessarily bright in the secondary-electron detectors, whereas charging or relief glow is
bright in every detector. This module measures that; it cannot prove that any region is silicon.

Runs on pixel-registered images only (results/registration/registration_by_image.csv, pair == ALL, registered).

Reads:  data/tiles/index.parquet, results/thresholds_per_tile.parquet, data/masks/** (BSE class masks of `qc segment`,
        stitched per image with `features.stitch`), data/raw/<batch>/img_<sample_id>_{Inlens,ETD|SE}.tif
Writes: results/charging/charging_by_image.csv              (one row per image x mask variant: fraction of class-2
                                                              area flagged, particles removed, control fractions)
        results/charging/features_masked_vs_unmasked.csv    (one row per image x variant: F02-F05 unmasked, masked, delta)
        results/charging/charging_batch_summary.csv         (per batch x variant: medians, within-batch IQR, exceeds-IQR flag)
        results/charging/figures/<batch>_<sample_id>_<y>_<x>.png (one overlay per batch)
        results/charging/CHARGING.md

Masks (all computed on the stitched BSE label image; SE images are median-filtered with the segmentation
`denoise.size` so their resolution matches the mask, then robustly normalised per image, z = (I - median) / (1.4826 MAD);
"above percentile p" means z >= the p-th percentile of z over the analysed pixels, so saturated pixels count):
- `bright_both_p{90,95,99}`: class 2 AND Inlens above p AND ETD/SE above p.
- `edge_glow_n{3,5,10}`:     class 2 AND within N px (Euclidean) of a class-0 pixel AND Inlens, ETD/SE above p = `edge_pct`.
- control `dark_both_p50`:   class 2 AND Inlens below p50 AND ETD/SE below p50 (the opposite failure: bright only in BSE,
                             Z-contrast candidates); reported as `frac_c2_dark_both`, never applied as a mask.
- control `frac_c1_bright_both_p`: how much of class 1 passes the same bright-in-both test (specificity of the criterion).

Masked features: flagged class-2 pixels are relabelled class 1 and F02 (class-2 area fraction), F03 / F04 (interior
particle equivalent-diameter median / p90, px), F05 (count density per Mpx, unbiased counting frame) are recomputed
with the definitions of `qc features` (`features._particles`, 8-connected, >= min_object_px). "Particles removed
entirely" = class-2 particles of the unmasked image (>= min_object_px) with fewer than min_object_px unflagged pixels
left.

OBSERVED vs INFERRED: the fractions, counts and feature deltas are observed. That a flagged pixel is charging or
relief rather than silicon is inferred from the brightness pattern only; that an unflagged pixel is silicon is not
established by this test. Units: px; 25 nm/px is unconfirmed.

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
from scipy import ndimage
from skimage.segmentation import find_boundaries

from qc import config as _config
from qc import features as _features
from qc import kpi as _kpi
from qc import segment as _segment
from qc import tiles as _tiles

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DEFAULTS = {"percentiles": [90, 95, 99], "edge_px": [3, 5, 10], "edge_pct": 95, "dark_pct": 50, "crop_px": 1024}
PHASE_IDENTITY = _features.PHASE_IDENTITY
FEATS = ("F02", "F03", "F04", "F05")
FEAT_COLS = {"F02": "F02_c2_area_fraction", "F03": "F03_c2_eqdiam_median_px", "F04": "F04_c2_eqdiam_p90_px",
             "F05": "F05_c2_count_density_per_Mpx"}


def params(cfg: dict[str, Any]) -> dict[str, Any]:
    return {**DEFAULTS, **(cfg.get("charging") or {})}


# ------------------------------------------------------------------------------------------------------ primitives

def robust_z(img: np.ndarray, analysed: np.ndarray | None = None) -> np.ndarray:
    """(I - median) / (1.4826 MAD) over the analysed pixels; MAD of 0 (flat image) falls back to 1."""
    x = np.asarray(img, dtype=np.float32)
    v = x[analysed] if analysed is not None else x.ravel()
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med))) * 1.4826
    return (x - med) / (mad if mad > 0 else 1.0)


def bright(z: np.ndarray, pct: float, analysed: np.ndarray) -> tuple[np.ndarray, float]:
    """(z >= p-th percentile of z over analysed pixels, that threshold). >= so saturated (255) pixels count."""
    t = float(np.percentile(z[analysed], pct))
    return z >= t, t


def dark(z: np.ndarray, pct: float, analysed: np.ndarray) -> tuple[np.ndarray, float]:
    t = float(np.percentile(z[analysed], pct))
    return z < t, t


def near_class(lab: np.ndarray, cls: int, n_px: int) -> np.ndarray:
    """Pixels within n_px (Euclidean) of a class-`cls` pixel (the class-`cls` pixels themselves included)."""
    target = lab == cls
    if not target.any():
        return np.zeros(lab.shape, dtype=bool)
    return ndimage.distance_transform_edt(~target) <= n_px


def build_masks(lab: np.ndarray, z_inlens: np.ndarray, z_se: np.ndarray, p: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    """All flag masks (restricted to class 2) plus per-image threshold diagnostics."""
    analysed = lab != _features.UNANALYSED
    c2 = lab == 2
    masks: dict[str, np.ndarray] = {}
    diag: dict[str, float] = {}
    both_at: dict[float, np.ndarray] = {}
    for pct in sorted(set(list(p["percentiles"]) + [p["edge_pct"]])):
        bi, ti = bright(z_inlens, pct, analysed)
        bs, ts = bright(z_se, pct, analysed)
        both_at[pct] = bi & bs
        diag[f"z_thr_inlens_p{pct}"] = ti
        diag[f"z_thr_se_p{pct}"] = ts
        diag[f"frac_c1_bright_both_p{pct}"] = float(both_at[pct][lab == 1].mean()) if (lab == 1).any() else float("nan")
        diag[f"frac_c2_bright_inlens_only_p{pct}"] = float((bi & ~bs)[c2].mean()) if c2.any() else float("nan")
        diag[f"frac_c2_bright_se_only_p{pct}"] = float((bs & ~bi)[c2].mean()) if c2.any() else float("nan")
    for pct in p["percentiles"]:
        masks[f"bright_both_p{pct}"] = c2 & both_at[pct]
    edge_both = both_at[p["edge_pct"]]
    for n in p["edge_px"]:
        near0 = near_class(lab, 0, int(n))
        masks[f"edge_glow_n{n}"] = c2 & near0 & edge_both
        diag[f"frac_c2_within_{n}px_of_c0"] = float(near0[c2].mean()) if c2.any() else float("nan")
    di, _ = dark(z_inlens, p["dark_pct"], analysed)
    ds, _ = dark(z_se, p["dark_pct"], analysed)
    diag[f"frac_c2_dark_both_p{p['dark_pct']}"] = float((di & ds)[c2].mean()) if c2.any() else float("nan")
    diag["frac_c2_z_inlens_median"] = float(np.median(z_inlens[c2])) if c2.any() else float("nan")
    diag["frac_c2_z_se_median"] = float(np.median(z_se[c2])) if c2.any() else float("nan")
    diag["c1_z_inlens_median"] = float(np.median(z_inlens[lab == 1])) if (lab == 1).any() else float("nan")
    diag["c1_z_se_median"] = float(np.median(z_se[lab == 1])) if (lab == 1).any() else float("nan")
    return masks, diag


def c2_features(lab: np.ndarray, fp: dict[str, Any]) -> tuple[dict[str, float], pd.DataFrame]:
    """F02-F05 with the `qc features` definitions, plus the particle table (for the removed-entirely count)."""
    analysed = lab != _features.UNANALYSED
    n_px = int(analysed.sum())
    c2 = lab == 2
    parts = _features._particles(c2, fp["min_object_px"], fp["connectivity"])
    interior = parts[~parts["touch_any"]]
    out = {"F02": float(c2.sum() / n_px) if n_px else float("nan"),
           "F03": float(np.median(interior["eqd"])) if len(interior) else float("nan"),
           "F04": float(np.percentile(interior["eqd"], 90)) if len(interior) else float("nan"),
           "F05": float((~parts["touch_lb"]).sum() / n_px * 1e6) if n_px else float("nan"),
           "n_c2_particles": int(len(parts))}
    return out, parts


def particles_removed(lab: np.ndarray, flagged: np.ndarray, fp: dict[str, Any]) -> int:
    """Class-2 particles (>= min_object_px, connectivity as in `qc features`) left with < min_object_px unflagged px."""
    c2 = lab == 2
    if not c2.any():
        return 0
    structure = np.ones((3, 3), bool) if fp["connectivity"] == 8 else None
    lab_c2, n = ndimage.label(c2, structure=structure)
    if n == 0:
        return 0
    area = np.bincount(lab_c2.ravel(), minlength=n + 1)
    kept = np.bincount(lab_c2[~flagged].ravel(), minlength=n + 1)
    is_particle = area[1:] >= fp["min_object_px"]
    return int((is_particle & (kept[1:] < fp["min_object_px"])).sum())


def apply_mask(lab: np.ndarray, flagged: np.ndarray) -> np.ndarray:
    out = lab.copy()
    out[flagged & (lab == 2)] = 1
    return out


def evaluate(lab: np.ndarray, z_inlens: np.ndarray, z_se: np.ndarray, p: dict[str, Any], fp: dict[str, Any]
             ) -> tuple[list[dict[str, Any]], dict[str, np.ndarray], dict[str, float]]:
    """Rows (one per variant, plus variant 'none' = unmasked) for one image."""
    masks, diag = build_masks(lab, z_inlens, z_se, p)
    base, _ = c2_features(lab, fp)
    c2_area = int((lab == 2).sum())
    rows = [{"variant": "none", "frac_c2_area_flagged": 0.0, "n_c2_particles_removed": 0,
             "n_c2_particles_unmasked": base["n_c2_particles"], "n_c2_particles_masked": base["n_c2_particles"],
             **{f"{f}_unmasked": base[f] for f in FEATS}, **{f"{f}_masked": base[f] for f in FEATS},
             **{f"{f}_delta": 0.0 for f in FEATS}}]
    for name, m in masks.items():
        masked, _ = c2_features(apply_mask(lab, m), fp)
        rows.append({"variant": name, "frac_c2_area_flagged": float(m.sum() / c2_area) if c2_area else float("nan"),
                     "n_c2_particles_removed": particles_removed(lab, m, fp),
                     "n_c2_particles_unmasked": base["n_c2_particles"], "n_c2_particles_masked": masked["n_c2_particles"],
                     **{f"{f}_unmasked": base[f] for f in FEATS}, **{f"{f}_masked": masked[f] for f in FEATS},
                     **{f"{f}_delta": masked[f] - base[f] for f in FEATS}})
    return rows, masks, diag


# ---------------------------------------------------------------------------------------------------------- figure

def best_crop(flag: np.ndarray, crop: int) -> tuple[int, int]:
    """Top-left of the crop x crop window (grid-aligned) holding the most flagged pixels."""
    H, W = flag.shape
    nh, nw = max(1, H // crop), max(1, W // crop)
    counts = flag[:nh * crop, :nw * crop].reshape(nh, crop, nw, crop).sum(axis=(1, 3))
    iy, ix = np.unravel_index(int(np.argmax(counts)), counts.shape)
    return int(iy * crop), int(ix * crop)


def overlay_figure(bse: np.ndarray, inlens: np.ndarray, se: np.ndarray, lab: np.ndarray, flag_a: np.ndarray,
                   flag_b: np.ndarray, title: str, names: tuple[str, str, str], out_png: Path) -> None:
    rgb = np.stack([bse] * 3, axis=-1).astype(np.float32) / 255.0
    rgb[find_boundaries(lab == 2, mode="inner")] = (1.0, 0.55, 0.0)
    rgb[flag_b & ~flag_a] = (1.0, 1.0, 0.0)
    rgb[flag_a] = (1.0, 0.0, 0.3)
    fig, axes = plt.subplots(2, 2, figsize=(13, 13 * bse.shape[0] / bse.shape[1] + 0.9))
    for ax, im, t in zip(axes.ravel()[:3], (bse, inlens, se), names):
        ax.imshow(im, cmap="gray", vmin=0, vmax=255)
        ax.set_title(t)
    axes[1, 1].imshow(rgb)
    axes[1, 1].set_title("BSE: class-2 outline orange; flagged bright-in-both-SE (p95) magenta; edge glow (n5) only yellow")
    for ax in axes.ravel():
        ax.axis("off")
    fig.suptitle(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(out_png, dpi=100)
    plt.close(fig)


# -------------------------------------------------------------------------------------------------------- pipeline

def registered_images(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"charging: {path} not found; run `python -m qc register` first (registered images only)")
    reg = pd.read_csv(path)
    reg = reg[reg["pair"] == "ALL"]
    return reg[["batch", "sample_id", "third_detector", "registered"]]


def _work(args) -> dict[str, Any]:
    batch, sample_id, third, rows, masks_dir, raw_dir, cfg_data, p, fp, med_px, fig_path = args
    tiles = [(int(r["y"]), int(r["x"]), np.asarray(Image.open(Path(masks_dir) / r["mask_path"]))) for r in rows]
    lab = _features.stitch(tiles, int(rows[0]["img_h"]), int(rows[0]["img_w"]))
    rd, crop = int(cfg_data["read_channel"]), int(cfg_data["border_crop_px"])
    load = lambda ch: _tiles.crop_border(_tiles.read_gray(Path(raw_dir) / batch / f"img_{sample_id}_{ch}.tif", rd), crop)  # noqa: E731
    inlens, se = load("Inlens"), load(third)
    if inlens.shape != lab.shape or se.shape != lab.shape:
        raise RuntimeError(f"{sample_id}: SE image shape {inlens.shape}/{se.shape} differs from mask {lab.shape}")
    analysed = lab != _features.UNANALYSED
    z_i = robust_z(ndimage.median_filter(inlens, size=med_px), analysed)
    z_s = robust_z(ndimage.median_filter(se, size=med_px), analysed)
    rows_out, masks, diag = evaluate(lab, z_i, z_s, p, fp)
    keys = {"sample_id": sample_id, "batch": batch, "third_detector": third, "n_tiles": len(rows),
            "c2_area_px": int((lab == 2).sum()), "analysed_px": int(analysed.sum())}
    out = {"rows": [{**keys, **r} for r in rows_out], "diag": {**keys, **diag}}
    if fig_path is not None:
        a_name, b_name = f"bright_both_p{p['edge_pct']}", f"edge_glow_n{p['edge_px'][len(p['edge_px']) // 2]}"
        c = int(p["crop_px"])
        y, x = best_crop(masks[a_name], c)
        sl = (slice(y, y + c), slice(x, x + c))
        bse = load("BSE")
        fa, fb = masks[a_name], masks[b_name]
        title = (f"{batch} / {sample_id} / crop y={y} x={x} ({c} px)  class 2 = silicon ({PHASE_IDENTITY}); "
                 f"flagged {fa[sl].sum() / max(1, (lab[sl] == 2).sum()):.1%} of class-2 area in this crop, "
                 f"{fa.sum() / max(1, (lab == 2).sum()):.1%} in the image ({a_name}); units px")
        overlay_figure(bse[sl], inlens[sl], se[sl], lab[sl], fa[sl], fb[sl], title, ("BSE", "Inlens", third),
                       Path(fig_path) / f"{batch}_{sample_id}_{y:05d}_{x:05d}.png")
        out["figure"] = str(Path(fig_path) / f"{batch}_{sample_id}_{y:05d}_{x:05d}.png")
    return out


def batch_summary(feat: pd.DataFrame) -> pd.DataFrame:
    """Per batch x variant: median fraction flagged, batch medians of F02-F05 unmasked and masked, within-batch IQR
    of the unmasked feature, and whether |median_masked - median_unmasked| exceeds that IQR."""
    recs = []
    for (batch, variant), d in feat.groupby(["batch", "variant"], sort=True):
        rec = {"batch": batch, "variant": variant, "n_images": int(len(d)),
               "frac_c2_area_flagged_median": float(d["frac_c2_area_flagged"].median()),
               "frac_c2_area_flagged_max": float(d["frac_c2_area_flagged"].max()),
               "n_c2_particles_removed_median": float(d["n_c2_particles_removed"].median()),
               "n_c2_particles_unmasked_median": float(d["n_c2_particles_unmasked"].median())}
        for f in FEATS:
            u, m = d[f"{f}_unmasked"], d[f"{f}_masked"]
            iqr = float(u.quantile(0.75) - u.quantile(0.25))
            rec[f"{f}_median_unmasked"] = float(u.median())
            rec[f"{f}_median_masked"] = float(m.median())
            rec[f"{f}_median_delta"] = float(m.median() - u.median())
            rec[f"{f}_iqr_unmasked"] = iqr
            rec[f"{f}_delta_exceeds_iqr"] = bool(abs(m.median() - u.median()) > iqr)
        recs.append(rec)
    return pd.DataFrame(recs)


def write_report(path: Path, feat: pd.DataFrame, diag: pd.DataFrame, summ: pd.DataFrame, skipped: pd.DataFrame,
                 figures: list[str], p: dict[str, Any], fp: dict[str, Any], cfg: dict[str, Any]) -> None:
    n = feat["sample_id"].nunique()
    L = ["# Charging / topography glow in the class-2 (bright BSE) mask", "",
         f"Phase identity: class 2 bright = silicon, class 1 mid = graphite, class 0 dark = void/pore, **{PHASE_IDENTITY}**.",
         f"Produced by `python -m qc charging` with `{cfg['_path']}@{cfg['_hash']}`, git `{_config.git_sha()}`; "
         f"n = {n} pixel-registered images (independent unit; {len(skipped)} skipped as not registered). Units px; 25 nm/px unconfirmed.", "",
         "## Method", "",
         f"Stitched BSE label mask per image (`qc segment` tiles, later tile wins). Inlens and ETD/SE images median-filtered "
         f"({_segment.params(cfg['segmentation'])['median_px']} px, as the BSE before segmentation), robust z per image "
         f"(median / 1.4826 MAD over analysed pixels). `bright_both_pP` = class 2 AND z_Inlens >= P-th percentile AND z_SE >= "
         f"P-th percentile (P = {', '.join(map(str, p['percentiles']))}). `edge_glow_nN` = class 2 AND within N px of class 0 AND "
         f"bright in both at p{p['edge_pct']} (N = {', '.join(map(str, p['edge_px']))}). Flagged class-2 pixels are relabelled "
         f"class 1 and F02-F05 recomputed with the `qc features` definitions (8-connected particles >= {fp['min_object_px']} px, "
         f"border exclusion for F03/F04, counting frame for F05). Control: `frac_c2_dark_both_p{p['dark_pct']}` = class-2 area "
         f"below the median in both SE channels (Z-contrast-only candidates, i.e. retained with certainty by any SE-based mask).", "",
         "## Observed: fraction of class-2 area flagged, per batch (median over images; max in brackets)", "",
         "| batch | n | " + " | ".join(v for v in summ["variant"].unique() if v != "none") + " |",
         "|---|---|" + "---|" * (summ["variant"].nunique() - 1)]
    for batch, d in summ.groupby("batch", sort=True):
        d = d[d["variant"] != "none"].set_index("variant")
        L.append(f"| {batch} | {int(d['n_images'].iloc[0])} | " + " | ".join(
            f"{d.loc[v, 'frac_c2_area_flagged_median']:.3f} ({d.loc[v, 'frac_c2_area_flagged_max']:.3f})" for v in d.index) + " |")
    L += ["", "## Observed: SE brightness of class 2 vs class 1 (median over images)", "",
          "| batch | median z_Inlens of class 2 | of class 1 | median z_SE of class 2 | of class 1 | class-1 area bright-in-both p95 | class-2 area dark-in-both p50 |",
          "|---|---|---|---|---|---|---|"]
    dark_col = f"frac_c2_dark_both_p{p['dark_pct']}"
    for batch, d in diag.groupby("batch", sort=True):
        L.append(f"| {batch} | {d['frac_c2_z_inlens_median'].median():.2f} | {d['c1_z_inlens_median'].median():.2f} | "
                 f"{d['frac_c2_z_se_median'].median():.2f} | {d['c1_z_se_median'].median():.2f} | "
                 f"{d['frac_c1_bright_both_p95'].median():.4f} | {d[dark_col].median():.4f} |")
    L += ["", "## Observed: batch medians of F02-F05 with vs without the mask", "",
          "Within-batch IQR is that of the unmasked feature; `>IQR` marks |median masked - median unmasked| > IQR.", "",
          "| batch | variant | F02 unmasked | F02 masked | >IQR | F03 unmasked | F03 masked | >IQR | F04 unmasked | F04 masked | >IQR | F05 unmasked | F05 masked | >IQR | particles removed (median) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in summ[summ["variant"] != "none"].iterrows():
        cells = []
        for f in FEATS:
            cells += [f"{r[f'{f}_median_unmasked']:.3f}", f"{r[f'{f}_median_masked']:.3f}", "yes" if r[f"{f}_delta_exceeds_iqr"] else "no"]
        L.append(f"| {r['batch']} | {r['variant']} | " + " | ".join(cells) + f" | {r['n_c2_particles_removed_median']:.0f} / {r['n_c2_particles_unmasked_median']:.0f} |")
    L += ["", "## Figures", ""] + [f"- `{Path(f).relative_to(_config.ROOT)}`" for f in figures]
    if len(skipped):
        L += ["", "## Skipped (not pixel-registered)", ""] + [f"- {r['batch']} / {r['sample_id']}" for _, r in skipped.iterrows()]
    L += ["", "## OBSERVED vs INFERRED", "",
          "- OBSERVED: the flagged fractions, particle counts and F02-F05 deltas above, per image and per batch.",
          "- INFERRED: a class-2 pixel that is in the top few percent of both SE detectors has a brightness that topography or "
          "charging alone could explain; relabelling it is a conservative sensitivity check, not a correction.",
          "- NOT ESTABLISHED: that any retained class-2 pixel is silicon. This test cannot prove a bright region is silicon; it "
          "can only remove pixels whose brightness is explained by topography/charging. If class 2 is systematically brighter "
          "than class 1 in the SE detectors (table above), the premise 'a true high-Z particle is not bright in SE' does not hold "
          "for this dataset and the mask measures SE brightness of the class-2 phase, not charging specifically.",
          "- Nothing here is a statement about material quality.", ""]
    path.write_text("\n".join(L))


def run(cfg: dict[str, Any]) -> None:
    p = params(cfg)
    reg_cfg = _features.load_registry(cfg.get("features_config", _features.FEATURES_CONFIG))
    fp = _features.feature_params(reg_cfg, cfg)
    med_px = _segment.params(cfg["segmentation"])["median_px"]
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    masks_dir = _config.resolve(cfg["data"].get("masks_dir", "data/masks"))
    raw_dir = _config.resolve(cfg["data"]["raw_dir"])
    res = _config.ROOT / "results" / "charging"
    fig_dir = res / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    reg = registered_images(_config.ROOT / "results" / "registration" / "registration_by_image.csv")
    skipped = reg[~reg["registered"].astype(bool)]
    reg = reg[reg["registered"].astype(bool)]

    index = pd.read_parquet(tiles_dir / "index.parquet")
    th = pd.read_parquet(_config.ROOT / "results" / "thresholds_per_tile.parquet")
    th = _kpi.join_thresholds(th, index, cfg)
    th = th.merge(index[["tile_id", "img_h", "img_w"]], on="tile_id", how="left", validate="one_to_one")
    groups = {(b, s): g.sort_values(["y", "x"]).to_dict("records") for (b, s), g in th.groupby(["batch", "sample_id"])}
    # one figure per batch: the registered image whose sample_id is the alphabetical median of its batch (no cherry-picking)
    fig_pick = {b: sorted(d["sample_id"])[len(d) // 2] for b, d in reg.groupby("batch")}
    jobs = []
    for r in reg.sort_values(["batch", "sample_id"]).itertuples():
        if (r.batch, r.sample_id) not in groups:
            raise RuntimeError(f"{r.sample_id}: no BSE masks; run `qc segment`")
        jobs.append((r.batch, r.sample_id, r.third_detector, groups[(r.batch, r.sample_id)], str(masks_dir), str(raw_dir),
                     cfg["data"], p, fp, med_px, str(fig_dir) if fig_pick[r.batch] == r.sample_id else None))
    with ProcessPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(_work, jobs))
    feat = pd.DataFrame([row for r in results for row in r["rows"]])
    diag = pd.DataFrame([r["diag"] for r in results])
    figures = [r["figure"] for r in results if "figure" in r]
    by_image = feat[["sample_id", "batch", "third_detector", "n_tiles", "c2_area_px", "analysed_px", "variant",
                     "frac_c2_area_flagged", "n_c2_particles_unmasked", "n_c2_particles_masked", "n_c2_particles_removed"]]
    by_image = by_image.merge(diag.drop(columns=["batch", "third_detector", "n_tiles", "c2_area_px", "analysed_px"]), on="sample_id")
    for df in (feat, diag, by_image):
        df["phase_identity"] = PHASE_IDENTITY
    summ = batch_summary(feat)
    _config.stamp(by_image, cfg).to_csv(res / "charging_by_image.csv", index=False)
    _config.stamp(feat, cfg).to_csv(res / "features_masked_vs_unmasked.csv", index=False)
    _config.stamp(summ, cfg).to_csv(res / "charging_batch_summary.csv", index=False)
    write_report(res / "CHARGING.md", feat, diag, summ, skipped, figures, p, fp, cfg)
    print(f"charging: {feat['sample_id'].nunique()} registered images x {feat['variant'].nunique() - 1} mask variants, "
          f"{len(skipped)} skipped -> results/charging/ (charging_by_image.csv, features_masked_vs_unmasked.csv, "
          f"charging_batch_summary.csv, CHARGING.md, {len(figures)} figures)")

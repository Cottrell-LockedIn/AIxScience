"""Tier-1 image-level feature table (features). Owner: P2.

Ten consultant-approved, pre-registered microstructure features computed once per image on the per-image label
mask stitched from the BSE tile masks written by `qc segment`. The registry (id, name, class, definition, unit,
provenance) is `configs/features_v1.yaml`; column names come from there.

Reads:  data/tiles/index.parquet, results/thresholds_per_tile.parquet (for the stale-input guard and mask paths),
        data/masks/<batch>/<sample_id>/<tile_id>.png
Writes: results/features/features_f01_f11.parquet          (one row per image: sample_id, batch, F01..F11;
                                                            provenance in Parquet metadata)
        results/features/features_by_image.parquet + .csv   (one row per image: sample_id, batch, F01..F11,
                                                              diagnostics, n_tiles, config_hash, features_config_hash, git_sha)
        results/features/features_by_tile.parquet            (same features per 1024 px tile; tiles are pseudo-replicates)
        results/features/features_batch_medians.csv          (per-batch median and IQR per feature, n images)
        results/features/README.md                           (registry, conventions, provenance tag)

Stitching: tiles overlap (1024 px, stride 512, plus edge-anchored tiles). The per-image mask is a canvas of the
cropped image size filled in (y, x) row-major order, later tile wins where tiles overlap. Particle features are
therefore computed once per image, with no cross-tile duplicates. Class-2 connected components are re-filtered
at `segmentation.min_object_px` after stitching because seams can split or merge components.

Phase identity: class 2 bright = silicon, class 1 mid = graphite, class 0 dark = void/pore, stated by Polaron, not
image-verified. Units are px / px^2; `*_nm_if25` columns multiply by 25 nm/px and are only valid if that is true.

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree
from skimage.measure import label, regionprops_table

from qc import config as _config
from qc import kpi as _kpi
from qc import segment as _segment

FEATURES_CONFIG = "configs/features_v1.yaml"
UNANALYSED = 255
PHASE_IDENTITY = "stated by Polaron, not image-verified"
LENGTH_FEATURES = ("F03", "F04", "F08")   # get a *_nm_if25 twin


# ----------------------------------------------------------------------------------------------------------- config

def load_registry(path: str | Path = FEATURES_CONFIG) -> dict[str, Any]:
    p = _config.resolve(path)
    reg = yaml.safe_load(p.read_text())
    reg["_path"] = str(p.relative_to(_config.ROOT)) if p.is_relative_to(_config.ROOT) else str(p)
    reg["_hash"] = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    reg["_columns"] = {f["id"]: f["column"] for f in reg["features"]}
    return reg


def feature_params(reg: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """The handful of numbers the feature functions need, resolved from both configs."""
    mop = reg["particles"].get("min_object_px", "from_v1_segmentation")
    if mop == "from_v1_segmentation":
        mop = _segment.params(cfg["segmentation"])["min_obj_px"]
    return {"min_object_px": int(mop), "connectivity": int(reg["particles"].get("connectivity", 8)),
            "window_px": int(reg["heterogeneity"].get("window_px", 512)),
            "exact_radius_max_px": int(reg["local_thickness"].get("exact_radius_max_px", 16)),
            "radius_growth": float(reg["local_thickness"].get("radius_growth", 1.2))}


DEFAULT_PARAMS = {"min_object_px": 20, "connectivity": 8, "window_px": 512, "exact_radius_max_px": 16, "radius_growth": 1.2}


# --------------------------------------------------------------------------------------------------------- stitching

def stitch(tiles: list[tuple[int, int, np.ndarray]], img_h: int, img_w: int) -> np.ndarray:
    """Per-image label mask from (y, x, tile) triples, pasted in (y, x) row-major order: later tile wins.

    Pixels no tile covers keep UNANALYSED (255). With the edge-anchored tile grid every pixel is covered.
    """
    canvas = np.full((img_h, img_w), UNANALYSED, dtype=np.uint8)
    for y, x, lab in sorted(tiles, key=lambda t: (t[0], t[1])):
        h, w = lab.shape
        canvas[y:y + h, x:x + w] = lab
    return canvas


# ------------------------------------------------------------------------------------------------------- primitives

def _particles(mask: np.ndarray, min_object_px: int, connectivity: int) -> pd.DataFrame:
    """One row per class-2 component >= min_object_px: area, eq. diameter, centroid, solidity, border flags."""
    empty = pd.DataFrame({"label": pd.Series(dtype=int), "area": pd.Series(dtype=float), "eqd": pd.Series(dtype=float),
                          "cy": pd.Series(dtype=float), "cx": pd.Series(dtype=float), "solidity": pd.Series(dtype=float),
                          "touch_any": pd.Series(dtype=bool), "touch_lb": pd.Series(dtype=bool)})
    if not mask.any():
        return empty
    lab = label(mask, connectivity=2 if connectivity == 8 else 1)
    props = regionprops_table(lab, properties=("label", "area", "equivalent_diameter_area", "centroid", "bbox",
                                               "solidity"))
    df = pd.DataFrame(props).rename(columns={"equivalent_diameter_area": "eqd", "centroid-0": "cy", "centroid-1": "cx",
                                             "bbox-0": "r0", "bbox-1": "c0", "bbox-2": "r1", "bbox-3": "c1"})
    df = df[df["area"] >= min_object_px].copy()
    if df.empty:
        return empty
    H, W = mask.shape
    df["touch_any"] = (df["r0"] == 0) | (df["c0"] == 0) | (df["r1"] == H) | (df["c1"] == W)
    df["touch_lb"] = (df["c0"] == 0) | (df["r1"] == H)   # left or bottom = forbidden lines of the counting frame
    return df.drop(columns=["r0", "c0", "r1", "c1"]).reset_index(drop=True)


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    if len(values) == 0:
        return float("nan")
    order = np.argsort(values)
    v, w = np.asarray(values)[order], np.asarray(weights, dtype=float)[order]
    cum = np.cumsum(w)
    return float(v[np.searchsorted(cum, 0.5 * cum[-1])])


def clark_evans(points: np.ndarray, height: int, width: int) -> tuple[float, float]:
    """(R, z) of Clark & Evans (1954) with the Donnelly (1978) edge correction for a rectangular window.

    R = observed mean nearest-neighbour distance / expected under CSR; z is the normal deviate of that difference.
    NaN when fewer than 2 points.
    """
    n = len(points)
    if n < 2:
        return float("nan"), float("nan")
    d, _ = cKDTree(points).query(points, k=2)
    r_obs = float(d[:, 1].mean())
    A, P = float(height * width), float(2 * (height + width))
    r_exp = 0.5 * np.sqrt(A / n) + (0.0514 + 0.041 / np.sqrt(n)) * P / n
    var = 0.0703 * A / n ** 2 + 0.037 * P * np.sqrt(A / n ** 5)
    return r_obs / r_exp, (r_obs - r_exp) / np.sqrt(var)


def _radii(r_max: float, exact_radius_max_px: int, radius_growth: float) -> list[float]:
    radii = [float(r) for r in range(1, min(exact_radius_max_px, int(np.floor(r_max))) + 1)]
    r = float(exact_radius_max_px)
    while r * radius_growth <= r_max:
        r *= radius_growth
        radii.append(r)
    if not radii or r_max > radii[-1]:
        radii.append(r_max)
    return sorted(set(radii), reverse=True)


def _thickness_component(m: np.ndarray, exact_radius_max_px: int, radius_growth: float) -> np.ndarray:
    """Local thickness of one foreground component `m` (bool, padded by a background border)."""
    edt = ndimage.distance_transform_edt(m)
    thick = np.zeros(m.shape, dtype=np.float32)
    for r in _radii(float(edt.max()), exact_radius_max_px, radius_growth):
        centres = edt >= r
        if not centres.any():
            continue
        covered = ndimage.distance_transform_edt(~centres) <= r
        thick[covered & (thick == 0)] = 2.0 * r
    thick[~m] = 0.0
    return thick


def local_thickness(mask: np.ndarray, exact_radius_max_px: int = 16, radius_growth: float = 1.2) -> np.ndarray:
    """Hildebrand-Rueegsegger local thickness in 2D: thickness(p) = 2 r_max(p), r_max(p) the radius of the largest
    disc that lies inside `mask` and contains p. Zero outside the mask.

    Radii are distance-transform values. Every integer radius up to `exact_radius_max_px` is evaluated; above
    that, radii grow geometrically by `radius_growth`, so thick regions are binned (relative bias <= growth - 1).
    A disc of radius r centred at a pixel with distance >= r covers the pixels within r of that pixel, i.e. the set
    where the distance transform of the complement of those centres is <= r. Radii are visited in descending
    order so the first assignment is the maximal one. Discs cannot cross between 8-connected components, so each
    component is processed on its own bounding box (padded by one background pixel), which keeps the cost
    proportional to the foreground area rather than the image area.
    """
    thick = np.zeros(mask.shape, dtype=np.float32)
    if not mask.any():
        return thick
    lab, _ = ndimage.label(mask, structure=np.ones((3, 3), dtype=bool))
    H, W = mask.shape
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        # one background pixel of padding, except on sides where the component touches the image border: there,
        # as in the whole-image distance transform, the structure is assumed to continue beyond the field of view
        pad = ((int(sl[0].start > 0), int(sl[0].stop < H)), (int(sl[1].start > 0), int(sl[1].stop < W)))
        m = np.pad(lab[sl] == i, pad)
        inner = (slice(pad[0][0], m.shape[0] - pad[0][1]), slice(pad[1][0], m.shape[1] - pad[1][1]))
        t = _thickness_component(m, exact_radius_max_px, radius_growth)[inner]
        mi = m[inner]
        thick[sl][mi] = t[mi]
    return thick


def chord_lengths(mask: np.ndarray, axis: int) -> np.ndarray:
    """Lengths of runs of True along `axis` (1 = horizontal chords, 0 = vertical), excluding runs that touch the
    array border along that axis (censored chords)."""
    m = mask if axis == 1 else mask.T
    padded = np.pad(m, ((0, 0), (1, 1)))
    d = np.diff(padded.astype(np.int8), axis=1)
    starts = np.argwhere(d == 1)
    ends = np.argwhere(d == -1)
    lengths = ends[:, 1] - starts[:, 1]
    interior = (starts[:, 1] > 0) & (ends[:, 1] < m.shape[1])
    return lengths[interior]


def window_fractions(mask: np.ndarray, window_px: int) -> np.ndarray:
    """Class fraction in non-overlapping windows anchored at the top-left; partial windows are dropped."""
    H, W = mask.shape
    nh, nw = H // window_px, W // window_px
    if nh == 0 or nw == 0:
        return np.array([])
    m = mask[:nh * window_px, :nw * window_px].reshape(nh, window_px, nw, window_px)
    return m.mean(axis=(1, 3)).ravel()


def boundary_contact(lab: np.ndarray, cls: int = 2, other: int = 0) -> tuple[int, int]:
    """(number of class-`cls` boundary pixels, number of those with a 4-neighbour of class `other`).

    Boundary pixel = class-`cls` pixel with at least one 4-neighbour that is not class `cls` (image border counts
    as not-boundary, i.e. only neighbours inside the array are considered; unanalysed pixels are neighbours too).
    """
    a = lab == cls
    b = lab == other
    not_a_nb = np.zeros(a.shape, dtype=bool)
    other_nb = np.zeros(a.shape, dtype=bool)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        sa, sb = _shift(~a, dy, dx), _shift(b, dy, dx)
        not_a_nb |= sa
        other_nb |= sb
    boundary = a & not_a_nb
    return int(boundary.sum()), int((boundary & other_nb).sum())


def _shift(m: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """m shifted by (dy, dx) with False fill: out[y, x] = m[y - dy, x - dx]."""
    out = np.zeros_like(m)
    H, W = m.shape
    ys, yd = (slice(0, H - dy), slice(dy, H)) if dy >= 0 else (slice(-dy, H), slice(0, H + dy))
    xs, xd = (slice(0, W - dx), slice(dx, W)) if dx >= 0 else (slice(-dx, W), slice(0, W + dx))
    out[yd, xd] = m[ys, xs]
    return out


# ---------------------------------------------------------------------------------------------------- the features

def compute(lab: np.ndarray, p: dict[str, Any] | None = None) -> dict[str, float]:
    """All ten features (keyed by id) plus diagnostics for one label image (0/1/2, 255 = unanalysed)."""
    p = {**DEFAULT_PARAMS, **(p or {})}
    analysed = lab != UNANALYSED
    n_px = int(analysed.sum())
    H, W = lab.shape
    out: dict[str, float] = {"analysed_px": n_px, "coverage": n_px / lab.size, "img_h": H, "img_w": W}
    if n_px == 0:
        return out
    c0, c2 = lab == 0, lab == 2
    out["F01"] = float(c0.sum() / n_px)
    out["F02"] = float(c2.sum() / n_px)

    parts = _particles(c2, p["min_object_px"], p["connectivity"])
    interior = parts[~parts["touch_any"]]
    out["n_c2_particles"] = int(len(parts))
    out["n_c2_particles_interior"] = int(len(interior))
    out["n_c2_particles_border"] = int(parts["touch_any"].sum())
    out["F03"] = float(np.median(interior["eqd"])) if len(interior) else float("nan")
    out["F04"] = float(np.percentile(interior["eqd"], 90)) if len(interior) else float("nan")
    out["F05"] = float((~parts["touch_lb"]).sum() / n_px * 1e6)
    out["F06"], out["F06_z"] = clark_evans(parts[["cy", "cx"]].to_numpy(), H, W)
    out["F07"] = weighted_median(interior["solidity"].to_numpy(), interior["area"].to_numpy())

    th = local_thickness(c0, p["exact_radius_max_px"], p["radius_growth"])
    out["F08"] = float(np.median(th[c0])) if c0.any() else float("nan")
    hc, vc = chord_lengths(c0, 1), chord_lengths(c0, 0)
    out["n_c0_chords_h"], out["n_c0_chords_v"] = int(len(hc)), int(len(vc))
    out["F09"] = float(hc.mean() / vc.mean()) if len(hc) and len(vc) and vc.mean() > 0 else float("nan")
    wf = window_fractions(c0, p["window_px"])
    out["n_windows"] = int(len(wf))
    out["F10"] = float(np.percentile(wf, 75) - np.percentile(wf, 25)) if len(wf) >= 2 else float("nan")
    nb, nb0 = boundary_contact(lab, 2, 0)
    out["n_c2_boundary_px"] = nb
    out["F11"] = float(nb0 / nb) if nb else float("nan")
    return out


def to_columns(feat: dict[str, float], reg: dict[str, Any]) -> dict[str, float]:
    """Rename F-ids to registry column names, keep diagnostics, add *_nm_if25 twins for length features."""
    cols = reg["_columns"]
    nm = float(reg.get("pixel_size_nm_if_true", 25))
    out: dict[str, float] = {}
    for fid, col in cols.items():
        v = feat.get(fid, float("nan"))
        out[col] = v
        if fid in LENGTH_FEATURES:
            out[col.replace("_px", "") + f"_nm_if{int(nm)}"] = v * nm
    out["F06_c2_clark_evans_z"] = feat.get("F06_z", float("nan"))
    for k, v in feat.items():
        if not k.startswith("F"):
            out[k] = v
    return out


# -------------------------------------------------------------------------------------------------------- pipeline

def _image_work(args) -> dict[str, Any]:
    batch, sample_id, rows, masks_dir, p, reg = args
    tiles = [(int(r["y"]), int(r["x"]), np.asarray(Image.open(Path(masks_dir) / r["mask_path"]))) for r in rows]
    lab = stitch(tiles, int(rows[0]["img_h"]), int(rows[0]["img_w"]))
    t0 = time.perf_counter()
    rec = {"sample_id": sample_id, "batch": batch, **to_columns(compute(lab, p), reg), "n_tiles": len(rows),
           "seconds": round(time.perf_counter() - t0, 2)}
    return rec


def _tile_work(args) -> dict[str, Any]:
    row, masks_dir, p, reg = args
    lab = np.asarray(Image.open(Path(masks_dir) / row["mask_path"]))
    keys = {k: row[k] for k in ("tile_id", "sample_id", "batch", "y", "x")}
    return {**keys, **to_columns(compute(lab, p), reg)}


def batch_medians(img: pd.DataFrame, reg: dict[str, Any]) -> pd.DataFrame:
    cols = list(reg["_columns"].values())
    g = img.groupby("batch", sort=True)
    med = g[cols].median().T.add_prefix("median_")
    iqr = (g[cols].quantile(0.75) - g[cols].quantile(0.25)).T.add_prefix("iqr_")
    out = pd.concat([med, iqr], axis=1)
    out.insert(0, "feature", out.index)
    for b, n in g.size().items():
        out[f"n_images_{b}"] = int(n)
    return out.reset_index(drop=True)


def image_feature_table(img: pd.DataFrame, reg: dict[str, Any]) -> pd.DataFrame:
    """The compact image-level F01-F11 table consumed by validation, classification and verdict."""
    columns = ["sample_id", "batch", *(f["column"] for f in reg["features"])]
    return img.loc[:, columns].copy()


def write_parquet(df: pd.DataFrame, path: Path, reg: dict[str, Any], cfg: dict[str, Any]) -> None:
    table = pa.Table.from_pandas(df, preserve_index=False)
    meta = {b"phase_identity": PHASE_IDENTITY.encode(),
            b"phase_map": b"class 2 bright = silicon, class 1 mid = graphite, class 0 dark = void/pore",
            b"units": b"px, px^2, fractions; *_nm_if25 columns valid only if 25 nm/px is true (unconfirmed)",
            b"features_config": json.dumps({"path": reg["_path"], "hash": reg["_hash"]}).encode(),
            b"provenance": json.dumps(_config.provenance(cfg)).encode()}
    table = table.replace_schema_metadata({**(table.schema.metadata or {}), **meta})
    pq.write_table(table, path)


def write_readme(path: Path, reg: dict[str, Any], cfg: dict[str, Any], img: pd.DataFrame, elapsed: float) -> None:
    lines = ["# Tier-1 image-level features (features_v1)", "",
             f"Phase identity: **{PHASE_IDENTITY}** (class 2 bright = silicon, class 1 mid = graphite, class 0 dark = void/pore; "
             + "; ".join(reg.get("phase_caveats", [])) + ").", "",
             f"Produced by `python -m qc features` with `{cfg['_path']}@{cfg['_hash']}`, `{reg['_path']}@{reg['_hash']}`, "
             f"git `{_config.git_sha()}`; {len(img)} images, {int(img['n_tiles'].sum())} BSE tiles, {elapsed:.0f} s wall.", "",
             "Units are px / px^2 / fractions. `*_nm_if25` columns are px x 25 and are only meaningful if the unconfirmed "
             "25 nm/px pixel size is true. The image (8-char `sample_id`) is the independent unit (n = 31); "
             "`features_by_tile.parquet` rows are pseudo-replicates for diagnostics only.", "",
             "## Conventions", "",
             f"- Stitching: tile masks pasted in (y, x) order, later tile wins ({reg['stitch']['rule']}); features computed once per image.",
             f"- Class-2 particles: {reg['particles']['connectivity']}-connected, re-filtered at min_object_px = "
             f"{_segment.params(cfg['segmentation'])['min_obj_px']} after stitching.",
             "- F03, F04, F07: particles touching the analysed-area border are excluded (ASTM E1245 style).",
             "- F05: unbiased counting frame, particles touching the left or bottom border are not counted.",
             "- F06: Donnelly (1978) edge-corrected CSR expectation; `F06_c2_clark_evans_z` is the normal deviate.",
             f"- F08: Hildebrand-Rueegsegger local thickness via distance transform; integer radii exact up to "
             f"{reg['local_thickness']['exact_radius_max_px']} px, geometric bins (x{reg['local_thickness']['radius_growth']}) above.",
             "- F09: chords touching the border are excluded as censored.",
             f"- F10: non-overlapping {reg['heterogeneity']['window_px']} px windows from the top-left corner.",
             "", "## Registry", "", "| id | column | class | unit | definition | provenance |", "|---|---|---|---|---|---|"]
    for f in reg["features"]:
        lines.append(f"| {f['id']} | `{f['column']}` | {f['class']} | {f['unit']} | {f['definition']} | {f['provenance']} |")
    lines += ["", "Files: `features_f01_f11.parquet`, `features_by_image.parquet` / `.csv`, "
              "`features_by_tile.parquet`, `features_batch_medians.csv`. "
              "Parquet metadata carries `phase_identity`, `features_config` and `provenance`."]
    path.write_text("\n".join(lines) + "\n")


def run(cfg: dict[str, Any]) -> None:
    t_start = time.perf_counter()
    reg = load_registry(cfg.get("features_config", FEATURES_CONFIG))
    p = feature_params(reg, cfg)
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    masks_dir = _config.resolve(cfg["data"].get("masks_dir", "data/masks"))
    res = _config.ROOT / "results" / "features"
    res.mkdir(parents=True, exist_ok=True)
    index = pd.read_parquet(tiles_dir / "index.parquet")
    th = pd.read_parquet(_config.ROOT / "results" / "thresholds_per_tile.parquet")
    th = _kpi.join_thresholds(th, index, cfg)          # same stale-input guard as `qc kpi`
    th = th.merge(index[["tile_id", "img_h", "img_w"]], on="tile_id", how="left", validate="one_to_one")
    th = th.sort_values(["batch", "sample_id", "y", "x"]).reset_index(drop=True)

    img_jobs = [(b, s, g.to_dict("records"), str(masks_dir), p, reg) for (b, s), g in th.groupby(["batch", "sample_id"], sort=True)]
    tile_jobs = [(r, str(masks_dir), p, reg) for r in th.to_dict("records")]
    with ProcessPoolExecutor() as ex:
        img_rows = list(ex.map(_image_work, img_jobs))
        tile_rows = list(ex.map(_tile_work, tile_jobs, chunksize=8))
    img = _config.stamp(pd.DataFrame(img_rows), cfg)
    img["features_config_hash"] = reg["_hash"]
    img["phase_identity"] = PHASE_IDENTITY
    per_tile = _config.stamp(pd.DataFrame(tile_rows), cfg)
    per_tile["features_config_hash"] = reg["_hash"]
    per_tile["phase_identity"] = PHASE_IDENTITY

    write_parquet(image_feature_table(img, reg), res / "features_f01_f11.parquet", reg, cfg)
    write_parquet(img, res / "features_by_image.parquet", reg, cfg)
    img.to_csv(res / "features_by_image.csv", index=False)
    write_parquet(per_tile, res / "features_by_tile.parquet", reg, cfg)
    batch_medians(img, reg).to_csv(res / "features_batch_medians.csv", index=False)
    elapsed = time.perf_counter() - t_start
    write_readme(res / "README.md", reg, cfg, img, elapsed)
    print(f"features: {len(img)} images, {len(per_tile)} tiles -> results/features/ (features_f01_f11.parquet, "
          f"features_by_image.parquet/.csv, features_by_tile.parquet, features_batch_medians.csv, README.md) "
          f"in {elapsed:.0f} s")

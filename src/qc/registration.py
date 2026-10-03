"""Detector pixel-registration check (register). Exploratory, added after S1-S5.

Are the three detector TIFFs of one image (BSE, Inlens, ETD or SE) the same pixel grid? The phase segmentation
runs on BSE only; any later per-pixel fusion with the SE detectors (e.g. the charging mask in `qc charging`)
is valid only where this check passes.

Reads:  data/raw/<batch>/img_<sample_id>_{BSE,Inlens,ETD|SE}.tif  (channel `data.read_channel`, `data.border_crop_px`
        cropped, i.e. the same frame as the tiles)
Writes: results/registration/registration_windows.csv    (one row per image x pair x window: dy, dx, peak, psr)
        results/registration/registration_by_image.csv   (one row per image x pair: median/std shift, peak sharpness,
                                                           affine scale/rotation fitted to the window shift field, verdict)
        results/registration/REGISTRATION.md             (which images are pixel-registered, which are not)

Method: BSE is the reference. On a grid of non-overlapping `win_px` windows (all rows that fit, up to `max_cols`
columns spread across the width) the translation of the moving detector relative to BSE is estimated with
`skimage.registration.phase_cross_correlation` (normalization="phase", upsampled by `upsample`), after mean removal and
a Hann taper. Sign convention: (dy, dx) is the shift that must be applied to the moving image to align it with BSE,
in px of the cropped frame. Peak sharpness is the peak-to-sidelobe ratio (PSR) of the phase-correlation surface,
(peak - mean of |surface| outside an 11 x 11 box around the peak) / std of that remainder (abs so that a
contrast-inverted detector still gives a positive peak); a featureless or
mis-matched window gives PSR of order 5, a real match gives PSR >> 10. Scale and rotation are not estimated with
a log-polar transform; instead a similarity transform (scale s, rotation theta) is fitted by least squares to the
per-window shift field (shift as a function of window centre): a scale error or rotation makes the shift vary
linearly across the 7000 px field, which is exactly what the consistency (std) across windows detects.

Verdict per pair: registered iff |median dy| <= `max_shift_px` and |median dx| <= `max_shift_px` and the std of
both components over valid windows (PSR >= `min_psr`) <= `max_std_px` and at least `min_windows` windows are valid.
An image is pixel-registered iff both pairs (BSE-Inlens and BSE-ETD/SE) are.

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from skimage.registration import phase_cross_correlation

from qc import config as _config
from qc import tiles as _tiles

DEFAULTS = {"win_px": 768, "max_cols": 6, "upsample": 10, "max_shift_px": 2.0, "max_std_px": 1.0,
            "min_psr": 10.0, "min_windows": 4, "peak_box_px": 5}
REFERENCE = "BSE"
MOVING = ("Inlens", "ETD", "SE")   # ETD and SE occupy the same slot (configs/v1.yaml data.channels)


def params(cfg: dict[str, Any]) -> dict[str, Any]:
    return {**DEFAULTS, **(cfg.get("registration") or {})}


# -------------------------------------------------------------------------------------------------- core estimators

def window_grid(h: int, w: int, win: int, max_cols: int) -> list[tuple[int, int]]:
    """Top-left corners of non-overlapping win x win windows: every row that fits, `max_cols` columns spread evenly
    across the width (all columns when fewer fit). Rows and columns are centred so the margins are symmetric."""
    nr, nc = h // win, w // win
    if nr == 0 or nc == 0:
        return []
    cols = np.unique(np.round(np.linspace(0, nc - 1, min(nc, max_cols))).astype(int))
    y0 = (h - nr * win) // 2
    x0 = (w - nc * win) // 2
    return [(y0 + r * win, x0 + int(c) * win) for r in range(nr) for c in cols]


def prepare(a: np.ndarray) -> np.ndarray:
    """float, zero-mean, Hann-tapered (periodic FFT assumption)."""
    a = np.asarray(a, dtype=np.float64)
    a = a - a.mean()
    taper = np.hanning(a.shape[0])[:, None] * np.hanning(a.shape[1])[None, :]
    return a * taper


def psr(ref: np.ndarray, mov: np.ndarray, box: int = 5) -> tuple[float, float]:
    """(peak, peak-to-sidelobe ratio) of the normalised cross-power (phase correlation) surface of two prepared windows."""
    cross = np.fft.fft2(ref) * np.conj(np.fft.fft2(mov))
    cross /= np.abs(cross) + 1e-12
    surf = np.abs(np.fft.ifft2(cross))      # abs: a contrast-inverted detector gives a negative peak
    py, px = np.unravel_index(int(np.argmax(surf)), surf.shape)
    keep = np.ones(surf.shape, dtype=bool)
    keep[max(0, py - box):py + box + 1, max(0, px - box):px + box + 1] = False
    rest = surf[keep]
    sd = float(rest.std())
    peak = float(surf.max())
    return peak, (peak - float(rest.mean())) / sd if sd > 0 else float("inf")


def window_shift(ref: np.ndarray, mov: np.ndarray, upsample: int = 10, box: int = 5) -> dict[str, float]:
    """Translation of `mov` relative to `ref` for one window: dy, dx (apply to mov to align with ref), peak, psr."""
    r, m = prepare(ref), prepare(mov)
    shift, _, _ = phase_cross_correlation(r, m, upsample_factor=upsample, normalization="phase")
    peak, ratio = psr(r, m, box)
    return {"dy": float(shift[0]), "dx": float(shift[1]), "peak": peak, "psr": ratio}


def fit_similarity(centres: np.ndarray, shifts: np.ndarray) -> dict[str, float]:
    """Least-squares similarity transform through the window shift field.

    centres: (n, 2) window centres (y, x); shifts: (n, 2) measured (dy, dx). Model: the moving image maps BSE pixel
    p to s R(theta) p + t, so shift(p) = (s R - I) p + t. Returns scale s, rotation (deg), the translation at the
    field centre and the RMS residual in px. With fewer than 3 windows, or windows all on one row/column, the
    linear part is not identifiable and NaN is returned for scale/rotation.
    """
    n = len(centres)
    out = {"scale": float("nan"), "rotation_deg": float("nan"), "affine_rms_px": float("nan")}
    if n < 3 or np.unique(centres[:, 0]).size < 2 or np.unique(centres[:, 1]).size < 2:
        return out
    c = centres - centres.mean(axis=0)
    A = np.column_stack([c, np.ones(n)])                      # [y, x, 1]
    coef, *_ = np.linalg.lstsq(A, shifts, rcond=None)         # (3, 2): columns dy, dx
    L = coef[:2, :].T                                         # L[i, j] = d shift_i / d coord_j, (y, x) ordering
    M = np.eye(2) + L
    det = float(np.linalg.det(M))
    scale = float(np.sqrt(abs(det)))
    # in (y, x) ordering a rotation by theta (x towards y positive) is [[cos, sin], [-sin, cos]]
    rot = float(np.degrees(np.arctan2(M[0, 1] - M[1, 0], M[0, 0] + M[1, 1])))
    resid = shifts - A @ coef
    out.update(scale=scale, rotation_deg=rot, affine_rms_px=float(np.sqrt((resid ** 2).sum(axis=1).mean())))
    return out


def register_pair(ref: np.ndarray, mov: np.ndarray, p: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """All window shifts plus the per-pair summary for one (reference, moving) image pair of equal shape."""
    if ref.shape != mov.shape:
        raise ValueError(f"shape mismatch {ref.shape} vs {mov.shape}: cannot be pixel-registered")
    win = int(p["win_px"])
    rows = []
    for y, x in window_grid(ref.shape[0], ref.shape[1], win, int(p["max_cols"])):
        r = window_shift(ref[y:y + win, x:x + win], mov[y:y + win, x:x + win], int(p["upsample"]), int(p["peak_box_px"]))
        rows.append({"win_y": y, "win_x": x, "win_px": win, **r})
    return rows, summarise_windows(rows, p)


def summarise_windows(rows: list[dict[str, Any]], p: dict[str, Any]) -> dict[str, Any]:
    df = pd.DataFrame(rows)
    valid = df[df["psr"] >= float(p["min_psr"])] if len(df) else df
    out: dict[str, Any] = {"n_windows": int(len(df)), "n_valid_windows": int(len(valid))}
    if len(valid) == 0:
        out.update(dy_median=np.nan, dx_median=np.nan, dy_std=np.nan, dx_std=np.nan, dy_max_abs=np.nan, dx_max_abs=np.nan,
                   peak_median=np.nan, psr_median=np.nan, psr_min=np.nan, scale=np.nan, rotation_deg=np.nan,
                   affine_rms_px=np.nan, registered=False, reason="no window with a usable correlation peak")
        return out
    out.update(dy_median=float(valid["dy"].median()), dx_median=float(valid["dx"].median()),
               dy_std=float(valid["dy"].std(ddof=0)), dx_std=float(valid["dx"].std(ddof=0)),
               dy_max_abs=float(valid["dy"].abs().max()), dx_max_abs=float(valid["dx"].abs().max()),
               peak_median=float(valid["peak"].median()), psr_median=float(valid["psr"].median()),
               psr_min=float(valid["psr"].min()))
    half = valid["win_px"].to_numpy() / 2.0
    centres = np.column_stack([valid["win_y"].to_numpy() + half, valid["win_x"].to_numpy() + half])
    out.update(fit_similarity(centres, valid[["dy", "dx"]].to_numpy()))
    reasons = []
    if out["n_valid_windows"] < int(p["min_windows"]):
        reasons.append(f"only {out['n_valid_windows']} windows with PSR >= {p['min_psr']}")
    if max(abs(out["dy_median"]), abs(out["dx_median"])) > float(p["max_shift_px"]):
        reasons.append(f"median shift ({out['dy_median']:.2f}, {out['dx_median']:.2f}) px > {p['max_shift_px']} px")
    if max(out["dy_std"], out["dx_std"]) > float(p["max_std_px"]):
        reasons.append(f"shift std ({out['dy_std']:.2f}, {out['dx_std']:.2f}) px > {p['max_std_px']} px")
    out["registered"] = not reasons
    out["reason"] = "; ".join(reasons)
    return out


# ------------------------------------------------------------------------------------------------------- pipeline

def image_files(raw_dir: Path) -> pd.DataFrame:
    """One row per image: batch, sample_id, path per channel (BSE, Inlens, third) and the third detector's name."""
    recs: dict[tuple[str, str], dict[str, Any]] = {}
    for p in sorted(raw_dir.glob("*/*.tif")):
        m = _tiles.NAME_RE.match(p.name)
        if not m:
            continue
        rec = recs.setdefault((p.parent.name, m["sample"]), {"batch": p.parent.name, "sample_id": m["sample"]})
        rec[m["channel"]] = str(p)
    rows = []
    for rec in recs.values():
        third = next((c for c in ("ETD", "SE") if c in rec), None)
        rows.append({**rec, "third_detector": third})
    return pd.DataFrame(rows)


def _work(args) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rec, cfg_data, p = args
    rd = int(cfg_data["read_channel"])
    crop = int(cfg_data["border_crop_px"])
    load = lambda path: _tiles.crop_border(_tiles.read_gray(Path(path), rd), crop)  # noqa: E731
    keys = {"sample_id": rec["sample_id"], "batch": rec["batch"], "third_detector": rec["third_detector"]}
    ref = load(rec[REFERENCE])
    win_rows, pair_rows = [], []
    for mov_name in ("Inlens", rec["third_detector"]):
        if not mov_name or not rec.get(mov_name):
            continue
        pair = f"{REFERENCE}-{mov_name}"
        try:
            rows, summ = register_pair(ref, load(rec[mov_name]), p)
        except ValueError as e:
            rows, summ = [], {"n_windows": 0, "n_valid_windows": 0, "registered": False, "reason": str(e)}
        win_rows += [{**keys, "pair": pair, **r} for r in rows]
        pair_rows.append({**keys, "pair": pair, "moving": mov_name, "img_h": ref.shape[0], "img_w": ref.shape[1], **summ})
    return win_rows, pair_rows


def image_verdicts(by_pair: pd.DataFrame) -> pd.DataFrame:
    """One row per image: registered iff every pair is registered, with the worst |median shift| and std."""
    g = by_pair.groupby(["batch", "sample_id", "third_detector"], sort=True)
    out = pd.DataFrame({
        "n_pairs": g.size(),
        "registered_all": g["registered"].all(),
        "max_abs_median_shift_px": g.apply(lambda d: float(np.nanmax(np.abs(d[["dy_median", "dx_median"]].to_numpy())))),
        "max_shift_std_px": g.apply(lambda d: float(np.nanmax(d[["dy_std", "dx_std"]].to_numpy()))),
        "min_psr_median": g["psr_median"].min(),
        "reasons": g["reason"].apply(lambda s: "; ".join(f"{pr}: {r}" for pr, r in zip(by_pair.loc[s.index, "pair"], s) if r)),
    }).reset_index()
    return out


def write_report(path: Path, by_pair: pd.DataFrame, by_image: pd.DataFrame, p: dict[str, Any], cfg: dict[str, Any]) -> None:
    n = len(by_image)
    n_reg = int(by_image["registered_all"].sum())
    lines = ["# Detector pixel registration (BSE vs Inlens, BSE vs ETD/SE)", "",
             f"Produced by `python -m qc register` with `{cfg['_path']}@{cfg['_hash']}`, git `{_config.git_sha()}`. "
             f"n = {n} images (independent unit), {len(by_pair)} detector pairs.", "",
             f"Method: phase correlation (`skimage.registration.phase_cross_correlation`, normalization=phase, x{p['upsample']} "
             f"upsampling) on {p['win_px']} px non-overlapping windows (all rows that fit x up to {p['max_cols']} columns), "
             f"BSE as reference, Hann taper. Shift (dy, dx) in px of the cropped frame = shift to apply to the SE image to "
             f"align it with BSE. Peak sharpness = peak-to-sidelobe ratio (PSR) of the phase-correlation surface; windows with "
             f"PSR < {p['min_psr']} are ignored. Scale / rotation: similarity transform fitted to the window shift field.", "",
             f"Verdict rule per pair: |median shift| <= {p['max_shift_px']} px in both axes, std over windows <= {p['max_std_px']} px, "
             f">= {p['min_windows']} valid windows. An image is pixel-registered iff both pairs pass.", "",
             f"## Result: {n_reg} of {n} images are pixel-registered across all three detectors", ""]
    for pair, d in by_pair.groupby("pair", sort=True):
        ok = d["registered"].sum()
        lines.append(f"- `{pair}` (n = {len(d)}): {ok} registered; |median shift| max {np.nanmax(np.abs(d[['dy_median', 'dx_median']].to_numpy())):.2f} px, "
                     f"shift std max {np.nanmax(d[['dy_std', 'dx_std']].to_numpy()):.2f} px, PSR median {d['psr_median'].median():.0f} "
                     f"(min {d['psr_min'].min():.0f}), fitted scale {d['scale'].min():.5f}-{d['scale'].max():.5f}, "
                     f"rotation {d['rotation_deg'].abs().max():.4f} deg max |.|.")
    lines += ["", "## Registered images (channels may be fused per pixel)", ""]
    reg = by_image[by_image["registered_all"]]
    for b, d in reg.groupby("batch", sort=True):
        lines.append(f"- {b} ({len(d)}): " + ", ".join(f"{s} ({t})" for s, t in zip(d["sample_id"], d["third_detector"])))
    lines += ["", "## Not registered (do not fuse channels for these)", ""]
    bad = by_image[~by_image["registered_all"]]
    if bad.empty:
        lines.append("- none")
    for _, r in bad.iterrows():
        lines.append(f"- {r['batch']} / {r['sample_id']} ({r['third_detector']}): {r['reasons']}")
    lines += ["", "## Per-image table", "",
              "| batch | image | 3rd det. | pair | n win (valid) | dy med | dx med | dy std | dx std | PSR med | scale | rot (deg) | registered |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in by_pair.sort_values(["batch", "sample_id", "pair"]).iterrows():
        lines.append(f"| {r['batch']} | {r['sample_id']} | {r['third_detector']} | {r['pair']} | {r['n_windows']} ({r['n_valid_windows']}) | "
                     f"{r['dy_median']:.2f} | {r['dx_median']:.2f} | {r['dy_std']:.2f} | {r['dx_std']:.2f} | {r['psr_median']:.0f} | "
                     f"{r['scale']:.5f} | {r['rotation_deg']:.4f} | {'yes' if r['registered'] else 'NO'} |")
    lines += ["", "Caveat (OBSERVED vs INFERRED): a zero shift with a sharp peak is observed; that the detectors were read out in the "
              "same scan (simultaneous acquisition) is inferred from it, not documented in the files. Units: px; "
              "25 nm/px is unconfirmed.", ""]
    path.write_text("\n".join(lines))


def run(cfg: dict[str, Any]) -> None:
    p = params(cfg)
    raw_dir = _config.resolve(cfg["data"]["raw_dir"])
    files = image_files(raw_dir)
    if files.empty:
        raise SystemExit(f"register: no TIFFs under {raw_dir}")
    with ProcessPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(_work, [(r, cfg["data"], p) for r in files.to_dict("records")]))
    win = _config.stamp(pd.DataFrame([w for ws, _ in results for w in ws]), cfg)
    by_pair = _config.stamp(pd.DataFrame([r for _, rs in results for r in rs]).sort_values(["batch", "sample_id", "pair"]), cfg)
    by_image = _config.stamp(image_verdicts(by_pair), cfg)
    out = _config.ROOT / "results" / "registration"
    out.mkdir(parents=True, exist_ok=True)
    win.to_csv(out / "registration_windows.csv", index=False)
    # per pair rows first, then one summary row per image (pair = "ALL") so one file answers both questions
    by_image_rows = by_image.rename(columns={"registered_all": "registered"}).assign(pair="ALL")
    pd.concat([by_pair, by_image_rows], ignore_index=True, sort=False).to_csv(out / "registration_by_image.csv", index=False)
    write_report(out / "REGISTRATION.md", by_pair, by_image, p, cfg)
    print(f"register: {len(by_image)} images, {len(by_pair)} pairs, {int(by_image['registered_all'].sum())} images registered "
          f"-> results/registration/ (registration_by_image.csv, registration_windows.csv, REGISTRATION.md)")

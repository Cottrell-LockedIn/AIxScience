"""S1 inventory and audit (audit). Owner: P1.

Inventory every image, record shape/dtype/tags, detect duplicates and missing channels.

Reads:  data/raw/inventory.csv (if present), data/raw/**/*.tif headers and pixels
Writes: results/audit/files.csv (one row per TIFF), results/audit/images.csv (one row per 8-char sample id:
        batch, channel set, missing channels, shape, dtype, resolution tag, sha256 per channel, duplicate flags),
        docs/DATA_AUDIT.md

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import tifffile

from qc import config as _config

NAME_RE = re.compile(r"^img_(?P<sample>[a-z0-9]{8})_(?P<channel>BSE|Inlens|ETD|SE)\.tif$")
EXPECTED = ("BSE", "Inlens", ("ETD", "SE"))  # ETD or SE fills the third slot


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _res_tag(page) -> tuple[str, float | None]:
    xr = page.tags.get("XResolution")
    unit = page.tags.get("ResolutionUnit")
    if xr is None:
        return "absent", None
    num, den = xr.value
    tag = f"{num}/{den}"
    unit_v = unit.value if unit is not None else None
    unit_v = getattr(unit_v, "value", unit_v)
    nm_per_px = None
    if den and num and unit_v == 2:  # inch
        nm_per_px = 25.4e6 / (num / den)
    elif den and num and unit_v == 3:  # cm
        nm_per_px = 1e7 / (num / den)
    return tag, nm_per_px


def inspect_file(path: str, known_sha: str | None = None) -> dict[str, Any]:
    p = Path(path)
    m = NAME_RE.match(p.name)
    row: dict[str, Any] = {
        "name": p.name, "batch": p.parent.name,
        "sample_id": m["sample"] if m else None, "channel": m["channel"] if m else None,
        "bytes": p.stat().st_size,
    }
    with tifffile.TiffFile(p) as t:
        page = t.pages[0]
        arr = page.asarray()
        row.update(
            n_pages=len(t.pages), height=int(page.shape[0]), width=int(page.shape[1]),
            samples=int(page.samplesperpixel), dtype=str(page.dtype),
            compression=str(page.compression.name), photometric=str(page.photometric.name),
            software=str(page.tags.get("Software").value) if page.tags.get("Software") else None,
        )
        row["res_tag"], row["nm_per_px_if_tag_true"] = _res_tag(page)
    if arr.ndim == 3:
        row["channels_identical"] = bool(all(np.array_equal(arr[..., 0], arr[..., k]) for k in range(1, arr.shape[2])))
        g = arr[..., 0]
    else:
        row["channels_identical"] = True
        g = arr
    row.update(mean=float(g.mean()), std=float(g.std()), p01=float(np.percentile(g, 1)),
               p99=float(np.percentile(g, 99)), min=int(g.min()), max=int(g.max()))
    # right-edge colour line reported in Dataset First Look: flag if the last 2 columns differ between RGB channels
    row["right_edge_rgb_differs"] = bool(arr.ndim == 3 and not np.array_equal(arr[:, -2:, 0], arr[:, -2:, 1]))
    row["left_edge_rgb_differs"] = bool(arr.ndim == 3 and not np.array_equal(arr[:, :2, 0], arr[:, :2, 1]))
    row["pixel_sha256"] = hashlib.sha256(np.ascontiguousarray(g).tobytes()).hexdigest()
    row["sha256"] = known_sha or _sha256(p)
    return row


def _inspect(args):
    return inspect_file(*args)


def build_files_table(raw_dir: Path) -> pd.DataFrame:
    inv = raw_dir / "inventory.csv"
    known = {}
    if inv.exists():
        known = dict(pd.read_csv(inv)[["name", "sha256"]].values)
    paths = sorted(raw_dir.glob("*/*.tif"))
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(_inspect, [(str(p), known.get(p.name)) for p in paths]))
    return pd.DataFrame(rows)


def build_images_table(files: pd.DataFrame) -> pd.DataFrame:
    sha_counts = Counter(files["sha256"])
    pix_counts = Counter(files["pixel_sha256"])
    rows = []
    for (batch, sid), g in files.groupby(["batch", "sample_id"], sort=True):
        chans = sorted(g["channel"])
        third = [c for c in chans if c in EXPECTED[2]]
        missing = [c for c in EXPECTED[:2] if c not in chans] + ([] if third else ["ETD|SE"])
        shapes = set(zip(g["height"], g["width"]))
        rows.append({
            "sample_id": sid, "batch": batch, "n_files": len(g), "channels": "+".join(chans),
            "third_detector": third[0] if third else None, "missing_channels": "+".join(missing),
            "height": int(g["height"].iloc[0]), "width": int(g["width"].iloc[0]),
            "shapes_consistent_across_channels": len(shapes) == 1,
            "dtype": "+".join(sorted(set(g["dtype"]))), "res_tag": "+".join(sorted(set(g["res_tag"]))),
            "nm_per_px_if_tag_true": float(g["nm_per_px_if_tag_true"].iloc[0]),
            "channels_identical_rgb": bool(g["channels_identical"].all()),
            "duplicate_file_elsewhere": bool(any(sha_counts[s] > 1 for s in g["sha256"])),
            "duplicate_pixels_elsewhere": bool(any(pix_counts[s] > 1 for s in g["pixel_sha256"])),
            **{f"sha256_{c}": s for c, s in zip(g["channel"], g["sha256"])},
        })
    return pd.DataFrame(rows)


def write_markdown(files: pd.DataFrame, images: pd.DataFrame, cfg: dict[str, Any], out: Path) -> None:
    prov = _config.provenance(cfg)
    per_batch = images.groupby("batch").agg(images=("sample_id", "count"), files=("n_files", "sum"))
    chan_sets = images.groupby(["batch", "channels"]).size().unstack(fill_value=0)
    res_tags = files["res_tag"].value_counts()
    nm = files["nm_per_px_if_tag_true"].dropna().unique()
    lines = [
        "# Data audit (S1)",
        "",
        f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by `python -m qc audit` "
        f"(config `{prov['config_path']}` @ `{prov['config_hash']}`, git `{prov['git_sha']}`). "
        "Source tables: `results/audit/files.csv` (per TIFF) and `results/audit/images.csv` (per 8-char sample id).",
        "",
        "## Images per batch",
        "",
        per_batch.to_markdown(),
        "",
        "## Channel set per image (count of images)",
        "",
        chan_sets.to_markdown(),
        "",
        f"Images missing a channel: {int((images['missing_channels'] != '').sum())}. "
        f"Images whose channels have inconsistent shapes: {int((~images['shapes_consistent_across_channels']).sum())}.",
        "",
        "## Geometry and encoding",
        "",
        f"- Width: {files['width'].min()} to {files['width'].max()} px; height: {files['height'].min()} to {files['height'].max()} px.",
        f"- dtype {sorted(files['dtype'].unique())}, samples per pixel {sorted(files['samples'].unique())}, "
        f"compression {sorted(files['compression'].unique())}, software {sorted(files['software'].dropna().unique())}.",
        f"- RGB channels identical in {int(files['channels_identical'].sum())}/{len(files)} files "
        f"(read channel {cfg['data']['read_channel']} only).",
        f"- Files where the last 2 columns differ between RGB channels (coloured edge line): "
        f"{int(files['right_edge_rgb_differs'].sum())}; first 2 columns differ (left edge line): "
        f"{int(files['left_edge_rgb_differs'].sum())} -> border crop {cfg['data']['border_crop_px']} px applies to all.",
        "",
        "## Resolution tag",
        "",
        "Counts of the TIFF `XResolution` tag across files:",
        "",
        res_tags.to_frame("files").to_markdown(),
        "",
        (f"Consistent across all files: **{'yes' if len(res_tags) == 1 else 'no'}**. "
         f"If the tag were intentional it would mean {', '.join(f'{v:.3f}' for v in nm)} nm/px. "
         "The tag was written by `tifffile.py`, not by the microscope; **pixel size is unconfirmed**. All units stay in pixels."),
        "",
        "## Duplicates",
        "",
        f"- Files with identical bytes elsewhere: {int(files['sha256'].duplicated(keep=False).sum())}.",
        f"- Files with identical pixel content elsewhere: {int(files['pixel_sha256'].duplicated(keep=False).sum())}.",
        "",
        "## Intensity per channel (channel 0, whole image)",
        "",
        files.groupby(["batch", "channel"])[["mean", "std", "p01", "p99"]].mean().round(1).to_markdown(),
        "",
        "## Unconfirmed facts (see docs/READ/Questions for Polaron.md)",
        "",
        "- Pixel size (25 nm/px inferred from a tifffile-written tag).",
        "- Identity of the bright class on BSE (no EDS); class names stay 0 / 1 / 2.",
        "- Whether a reference batch is designated.",
        "- Whether ETD vs SE naming reflects a different session or microscope.",
        "",
    ]
    out.write_text("\n".join(lines))


def run(cfg: dict[str, Any]) -> None:
    raw_dir = _config.resolve(cfg["data"]["raw_dir"])
    out_dir = _config.ROOT / "results" / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = build_files_table(raw_dir)
    if files.empty:
        raise SystemExit(f"audit: no TIFFs under {raw_dir}; run scripts/download_drive.py first")
    images = build_images_table(files)
    _config.stamp(files, cfg).to_csv(out_dir / "files.csv", index=False)
    _config.stamp(images, cfg).to_csv(out_dir / "images.csv", index=False)
    write_markdown(files, images, cfg, _config.ROOT / "docs" / "DATA_AUDIT.md")
    print(f"audit: {len(files)} files, {len(images)} images -> {out_dir}/files.csv, images.csv, docs/DATA_AUDIT.md")

"""B6 Inlens charging-glow sensitivity, separate from baseline feature values.

Reads:  stitched BSE masks, raw Inlens images, and registration output
Writes: results/charging/charging_by_image.csv
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qc import config as _config
from qc import features, kpi, register

PHASE_IDENTITY = "stated by Polaron, not image-verified"


def glow_sensitivity(
    bse_mask: np.ndarray, aligned_inlens: np.ndarray, percentile: float
) -> tuple[float, float]:
    labels = np.asarray(bse_mask, dtype=np.uint8)
    intensity = np.asarray(aligned_inlens, dtype=np.float64)
    if labels.ndim != 2 or intensity.shape != labels.shape:
        raise ValueError(
            "charging sensitivity requires co-registered 2-D mask "
            "and Inlens image"
        )
    valid = np.isfinite(intensity)
    if not valid.any():
        return float("nan"), float("nan")
    threshold = float(np.nanpercentile(intensity[valid], percentile))
    class2 = labels == 2
    count_c2 = int(class2.sum())
    if count_c2 == 0:
        return 0.0, 0.0
    glow = class2 & valid & (intensity > threshold)
    glow_frac = float(glow.sum() / count_c2)
    f02_glow_excluded = float((count_c2 - glow.sum()) / labels.size)
    return glow_frac, f02_glow_excluded


def _registration_map(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"charging requires registration output: {path}; "
            "run `qc register` first"
        )
    frame = pd.read_csv(
        path, dtype={"sample_id": str, "config_hash": str, "git_sha": str}
    )
    rows = frame.loc[frame["channel"] == "Inlens"]
    return {
        str(row.sample_id): row._asdict()
        for row in rows.itertuples(index=False)
    }


def run(cfg: dict[str, Any]) -> None:
    index_path = _config.resolve(cfg["data"]["tiles_dir"]) / "index.parquet"
    index = pd.read_parquet(index_path)
    bse_index = index.loc[index["channel"] == "BSE"].copy()
    thresholds = pd.read_parquet(
        _config.ROOT / "results" / "thresholds_per_tile.parquet"
    )
    joined = kpi.join_thresholds(thresholds, bse_index, cfg)
    joined = joined.merge(
        bse_index[["tile_id", "img_h", "img_w"]],
        on="tile_id",
        how="left",
        validate="one_to_one",
    )
    masks_dir = _config.resolve(cfg["data"].get("masks_dir", "data/masks"))
    raw_paths = register.raw_channel_paths(cfg)
    registration_path = (
        _config.ROOT
        / "results"
        / "registration"
        / "registration_by_image.csv"
    )
    alignments = _registration_map(registration_path)
    glow_cfg = cfg["charging"]
    channel = str(glow_cfg["glow_channel"])
    percentile = float(glow_cfg["glow_percentile"])
    records = []
    for (batch, sample_id), rows in joined.groupby(
        ["batch", "sample_id"], sort=True
    ):
        first = rows.iloc[0]
        mask = features.stitch_mask(
            rows,
            masks_dir,
            (int(first["img_h"]), int(first["img_w"])),
        )
        source = raw_paths.get(str(sample_id), {}).get(channel)
        alignment = alignments.get(str(sample_id))
        metrics = {
            "glow_frac_of_c2": float("nan"),
            "F02_glow_excluded": float("nan"),
        }
        same_fov = False
        if source is not None and alignment is not None:
            raw = register.read_raw_channel(source, cfg)
            if raw.shape == mask.shape:
                aligned = register.align_image(
                    raw,
                    float(alignment["rotation_deg"]),
                    float(alignment["scale"]),
                    float(alignment["shift_y_px"]),
                    float(alignment["shift_x_px"]),
                )
                (
                    metrics["glow_frac_of_c2"],
                    metrics["F02_glow_excluded"],
                ) = glow_sensitivity(mask, aligned, percentile)
                same_fov = bool(alignment["same_fov"])
        records.append(
            {
                "sample_id": str(sample_id),
                "batch": str(batch),
                "glow_channel": channel,
                "glow_percentile": percentile,
                **metrics,
                "registration_same_fov": same_fov,
                "phase_identity": PHASE_IDENTITY,
            }
        )
    if not records:
        raise RuntimeError("charging: no BSE image masks found")
    result = _config.stamp(pd.DataFrame(records), cfg)
    out_dir = _config.ROOT / "results" / "charging"
    out_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_dir / "charging_by_image.csv", index=False)
    print(
        f"charging: {len(result)} image sensitivity rows; "
        f"{int(result['registration_same_fov'].sum())} images pass Inlens "
        "registration; "
        "baseline F02 unchanged"
    )

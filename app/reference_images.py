"""Representative training image per batch for the side-by-side comparison panel.

Selection rule (fixed, label-aware, training images only): the image nearest its own
batch centre in the frozen classifier's 40-dimensional input space (standardised
F01-F11 + 29 BSE DINOv2 PCs, fitted on all 31 training images). The masks are produced
with the frozen v1 segmentation recipe exactly as `qc heldout` does for unseen images
and are display evidence only; the committed Phase B outputs are unchanged.

Run once: .venv/bin/python -m app.reference_images   (writes results/v1_1/reference/)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qc import classify, config as _config, features, heldout, kpi

OUT_DIR = _config.ROOT / "results" / "v1_1" / "reference"
MANIFEST = OUT_DIR / "manifest.json"


def select_representatives() -> list[dict[str, Any]]:
    frame = classify.load_training()
    xf, xe, y = classify._arrays(frame)
    _, _, z = classify.fit_transform(xf, xe)
    out = []
    for batch in classify.BATCHES:
        idx = np.where(y == batch)[0]
        centre = z[idx].mean(axis=0)
        dist = np.linalg.norm(z[idx] - centre, axis=1)
        best = idx[int(np.argmin(dist))]
        out.append({"batch": batch, "id": str(frame["sample_id"][best]), "distance_to_batch_centre": float(dist.min())})
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, Any]:
    cfg = _config.load()
    feature_cfg, feature_hash = features._feature_config()
    train_feats = pd.read_parquet(_config.ROOT / "results" / "features_per_image.parquet")
    train_feats = train_feats.loc[train_feats["scale"] == 1.0].set_index("sample_id")
    train_kpis = pd.read_parquet(_config.ROOT / "results" / "kpi_per_image.parquet").set_index("sample_id")
    raw_dir = _config.resolve(cfg["data"]["raw_dir"])
    items = []
    for rep in select_representatives():
        tif = raw_dir / rep["batch"] / f"img_{rep['id']}_BSE.tif"
        if not tif.is_file():
            raise SystemExit(f"missing training TIFF {tif}")
        bse = heldout._prepare_channel(tif, rep["id"], "BSE", cfg)
        feats, mask = heldout._extract_features(bse, cfg, feature_cfg)
        mask_png = features._encode_label_png(mask)
        mask_path = OUT_DIR / f"{rep['id']}_mask.png"
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        mask_path.write_bytes(mask_png)
        recorded = train_feats.loc[rep["id"]]
        feature_check = {
            name: {"recomputed": float(feats[name]), "training_table": float(recorded[name])}
            for name in classify.F_COLS
        }
        max_rel = max(
            abs(v["recomputed"] - v["training_table"]) / max(abs(v["training_table"]), 1e-9)
            for v in feature_check.values()
        )
        k = kpi.kpis(mask, float(cfg["kpi_extra"]["crack_aspect_min"]), int(cfg["kpi_extra"]["tpc_max_r_px"]))
        items.append({
            **rep,
            "source": {"path": str(tif.relative_to(_config.ROOT)), "sha256": _sha256(tif)},
            "mask_path": f"reference/{mask_path.name}",
            "mask_sha256": hashlib.sha256(mask_png).hexdigest(),
            "mask_shape": list(mask.shape),
            "mask_offset_px": [int(cfg["data"]["border_crop_px"])] * 2,
            "class_values": {"0": "void", "1": "graphite", "2": "silicon"},
            "feature_check": feature_check,
            "feature_check_max_relative_difference": max_rel,
            "image_level_kpis": {key: (None if not np.isfinite(val) else float(val)) for key, val in k.items()},
            "training_table_kpis_tile_mean": {
                key: float(train_kpis.loc[rep["id"], key]) for key in ("frac_c0", "frac_c1", "frac_c2", "c0_cracklike_frac", "c1_largest_component_frac")
            },
        })
    manifest = {
        "purpose": "display-only representative training image per batch for side-by-side comparison",
        "selection_rule": "nearest to own batch centre in the frozen classifier input space (standardised F01-F11 + 29 BSE DINOv2 PCs, fit on all 31 training images)",
        "segmentation": "frozen v1 recipe (per-tile multi-Otsu, min_object_px, stitch) applied as in qc heldout; exploratory display evidence, not ground truth",
        "phase_identity": classify.PHASE_IDENTITY,
        "config_hash": _config.provenance(cfg).get("config_hash"),
        "features_config_hash": feature_hash,
        "git_sha": _config.git_sha(),
        "references": items,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    built = build()
    for item in built["references"]:
        print(item["batch"], item["id"], "max rel feature diff", f"{item['feature_check_max_relative_difference']:.2e}", item["mask_shape"])

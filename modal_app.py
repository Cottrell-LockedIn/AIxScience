"""Modal fan-out for KPI and feature sensitivity plus frozen DINOv2 embeddings."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import time

import modal

from qc import config as _config

app = modal.App("aixscience-qc")
data_volume = modal.Volume.from_name("aixscience-data", create_if_missing=True)
weights_volume = modal.Volume.from_name("aixscience-weights", create_if_missing=True)
common_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "numpy==2.4.6",
        "scipy==1.17.1",
        "scikit-image==0.26.0",
        "pandas==3.0.6",
        "pyarrow==25.0.1",
        "pillow==12.3.0",
        "matplotlib==3.11.2",
        "PyYAML==6.0.3",
    )
    .env({"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    .add_local_python_source("qc")
)
gpu_image = common_image.pip_install(
    "torch==2.14.1+cu130",
    "torchvision==0.29.1+cu130",
    extra_index_url="https://download.pytorch.org/whl/cu130",
)

MODAL_RUN_COLUMNS = [
    "timestamp_utc", "function", "n_inputs", "wall_s", "hardware", "git_sha",
    "config_hash", "est_cost_usd", "cost_source",
]
MODAL_PRICING = (
    "https://modal.com/pricing; CPU=$0.0000131/physical-core-s, "
    "memory=$0.00000222/GiB-s, L4=$0.000222/GPU-s"
)


@app.function(
    image=common_image,
    cpu=1,
    memory=4096,
    volumes={"/mnt/data": data_volume},
    timeout=30 * 60,
    max_containers=20,
)
def kpi_sensitivity_image(payload: dict) -> dict:
    from qc import kpi, segment
    from PIL import Image
    import numpy as np

    started = time.perf_counter()
    data_root = Path("/mnt/data")
    params = payload["params"]
    out_rows = []
    parity_checks = 0
    for row in payload["rows"]:
        tile_path = data_root / "tiles" / row["path"]
        mask_path = data_root / "masks" / row["mask_path"]
        tile = np.load(tile_path)
        saved = np.asarray(Image.open(mask_path))
        thresholds = (float(row["t0"]), float(row["t1"]))
        fallback = bool(row["threshold_fallback"]) or any(np.isnan(t) for t in thresholds)
        denoised = segment.denoise(tile, params["median_px"])
        if fallback:
            generated = segment.fallback_label(denoised)
        else:
            generated = segment.label_from_thresholds(denoised, thresholds, params["min_obj_px"])
        buffer = BytesIO()
        Image.fromarray(generated, mode="L").save(buffer, format="PNG", compress_level=1)
        if not np.array_equal(generated, saved) or buffer.getvalue() != mask_path.read_bytes():
            raise AssertionError(f"scale-1.0 mask mismatch: {row['tile_id']}")
        parity_checks += 1

        for scale in (0.9, 1.0, 1.1):
            if fallback:
                labels = saved
            elif scale == 1.0:
                labels = generated
            else:
                labels = segment.label_from_thresholds(
                    denoised, tuple(t * scale for t in thresholds), params["min_obj_px"]
                )
            out_rows.append({
                **{key: row[key] for key in ("tile_id", "sample_id", "batch", "y", "x")},
                "scale": scale,
                **kpi.kpis(labels, params["crack_aspect_min"], params["tpc_max_r_px"]),
            })
    return {
        "sample_id": payload["sample_id"],
        "rows": out_rows,
        "n_tiles": len(payload["rows"]),
        "mask_parity_checks": parity_checks,
        "wall_s": time.perf_counter() - started,
    }


def _append_modal_run(
    cfg: dict,
    function: str,
    n_inputs: int,
    wall_s: float,
    hardware: str,
    est_cost_usd: float,
    cost_source: str = MODAL_PRICING,
) -> None:
    import pandas as pd

    path = _config.ROOT / "results" / "MODAL_RUNS.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "function": function,
        "n_inputs": n_inputs,
        "wall_s": wall_s,
        "hardware": hardware,
        "git_sha": _config.git_sha(),
        "config_hash": cfg["_hash"],
        "est_cost_usd": est_cost_usd,
        "cost_source": cost_source,
    }
    row = pd.DataFrame([record], columns=MODAL_RUN_COLUMNS)
    if path.exists():
        existing = pd.read_csv(path)
        if list(existing.columns) != MODAL_RUN_COLUMNS:
            raise RuntimeError(f"unexpected Modal run log schema in {path}")
        row.to_csv(path, mode="a", index=False, header=False)
    else:
        row.to_csv(path, index=False)


def _run_kpi_sensitivity() -> None:
    import numpy as np
    import pandas as pd
    from PIL import Image
    from qc import kpi, segment

    cfg = _config.load()
    results_dir = _config.ROOT / "results"
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    masks_dir = _config.resolve(cfg["data"].get("masks_dir", "data/masks"))
    index = pd.read_parquet(tiles_dir / "index.parquet")
    thresholds = pd.read_parquet(results_dir / "thresholds_per_tile.parquet")
    rows = kpi.join_thresholds(thresholds, index, cfg)
    params = {
        **segment.params(cfg["segmentation"]),
        "crack_aspect_min": float(cfg["kpi_extra"]["crack_aspect_min"]),
        "tpc_max_r_px": int(cfg["kpi_extra"]["tpc_max_r_px"]),
    }
    payloads = [
        {"sample_id": sample_id, "rows": group.to_dict("records"), "params": params}
        for (_, sample_id), group in rows.groupby(["batch", "sample_id"], sort=True)
    ]
    started = time.perf_counter()
    remote = list(kpi_sensitivity_image.map(payloads))
    wall_s = float(sum(result["wall_s"] for result in remote))
    parity_checks = sum(result["mask_parity_checks"] for result in remote)
    if parity_checks != len(rows):
        raise RuntimeError(f"scale-1.0 mask parity checks {parity_checks} != {len(rows)}")
    sensitivity_rows = [row for result in remote for row in result["rows"]]
    base = pd.read_parquet(results_dir / "kpi_per_tile.parquet").set_index("tile_id")
    for row in sensitivity_rows:
        if row["scale"] != 1.0:
            continue
        for col in kpi.KPI_COLS:
            local_value = base.at[row["tile_id"], col]
            remote_value = row[col]
            if not (pd.isna(local_value) and pd.isna(remote_value)) and local_value != remote_value:
                raise AssertionError(
                    f"scale-1.0 KPI mismatch at {row['tile_id']} {col}: "
                    f"{remote_value} != {local_value}"
                )

    expected_fraction = {}
    for row in rows.to_dict("records"):
        lab = np.asarray(Image.open(masks_dir / row["mask_path"]))
        thresholds_pair = (float(row["t0"]), float(row["t1"]))
        fallback = bool(row["threshold_fallback"]) or any(np.isnan(t) for t in thresholds_pair)
        denoised = None if fallback else segment.denoise(
            np.load(tiles_dir / row["path"]), params["median_px"]
        )
        for scale in (0.9, 1.0, 1.1):
            labels = lab if fallback or scale == 1.0 else segment.label_from_thresholds(
                denoised, tuple(t * scale for t in thresholds_pair), params["min_obj_px"]
            )
            expected_fraction[(row["tile_id"], scale)] = kpi.fractions(labels)
    for row in sensitivity_rows:
        expected = expected_fraction[(row["tile_id"], row["scale"])]
        for col in kpi.FRAC_COLS:
            if row[col] != expected[col]:
                raise AssertionError(
                    f"Modal fraction mismatch at {row['tile_id']} scale={row['scale']} {col}: "
                    f"{row[col]} != {expected[col]}"
                )

    tile = pd.DataFrame(sensitivity_rows)
    tile["phase_identity"] = kpi.PHASE_IDENTITY
    image = kpi.per_image(tile, kpi.KPI_COLS, ["scale"])
    image["phase_identity"] = kpi.PHASE_IDENTITY
    sensitivity = _config.stamp(
        pd.concat([tile.assign(level="tile"), image.assign(level="image")], ignore_index=True),
        cfg,
    )
    sensitivity.to_parquet(results_dir / "kpi_sensitivity.parquet", index=False)
    rate = 0.0000131 + 4 * 0.00000222
    _append_modal_run(
        cfg, "kpi_sensitivity", len(payloads), wall_s, "Modal CPU (1 core, 4 GiB)",
        wall_s * rate,
    )
    elapsed = time.perf_counter() - started
    print(
        f"kpi_sensitivity: {len(sensitivity_rows)} tile-scale rows, {len(payloads) * 3} image-scale rows; "
        f"{parity_checks}/{len(rows)} byte-identical masks; scale-1.0 KPI and fraction parity exact; "
        f"Modal container seconds={wall_s:.2f}, local elapsed={elapsed:.2f}, "
        f"estimated cost=${wall_s * rate:.6f}"
    )


@app.local_entrypoint()
def main(task: str = "kpi"):
    if task == "kpi":
        _run_kpi_sensitivity()
        return
    raise ValueError(f"unsupported task {task!r}")

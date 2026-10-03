"""Modal fan-out for KPI and feature sensitivity plus frozen DINOv2 embeddings."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timezone
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
    cpu=2,
    memory=4096,
    volumes={"/mnt/data": data_volume},
    timeout=30 * 60,
    max_containers=20,
)
def kpi_sensitivity_image(payload: dict) -> dict:
    from qc import kpi
    from PIL import Image
    import numpy as np

    started = time.perf_counter()
    data_root = Path("/mnt/data")
    params = payload["params"]

    def process(row):
        tile_path = data_root / "tiles" / row["path"]
        mask_path = data_root / "masks" / row["mask_path"]
        tile = np.load(tile_path)
        with Image.open(mask_path) as image:
            saved = np.asarray(image)
        result_rows = kpi.sensitivity_for_tile(
            row, tile, saved, params, mask_path.read_bytes()
        )
        return result_rows

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(process, payload["rows"]))
    out_rows = [row for result in results for row in result]
    return {
        "chunk_id": payload["chunk_id"],
        "rows": out_rows,
        "n_tiles": len(payload["rows"]),
        "mask_parity_checks": len(payload["rows"]),
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
    from qc import kpi, segment

    cfg = _config.load()
    results_dir = _config.ROOT / "results"
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    masks_dir = _config.resolve(cfg["data"].get("masks_dir", "data/masks"))
    index = pd.read_parquet(tiles_dir / "index.parquet")
    thresholds = pd.read_parquet(results_dir / "thresholds_per_tile.parquet")
    local_sensitivity = pd.read_parquet(results_dir / "kpi_sensitivity.parquet")
    local_sensitivity = local_sensitivity.loc[local_sensitivity["level"] == "tile"].set_index(
        ["tile_id", "scale"]
    )
    rows = kpi.join_thresholds(thresholds, index, cfg)
    params = {
        **segment.params(cfg["segmentation"]),
        "crack_aspect_min": float(cfg["kpi_extra"]["crack_aspect_min"]),
        "tpc_max_r_px": int(cfg["kpi_extra"]["tpc_max_r_px"]),
    }
    records = rows.sort_values(["batch", "sample_id", "y", "x"]).to_dict("records")
    chunk_size = 10
    payloads = [
        {"chunk_id": chunk_id, "rows": records[start:start + chunk_size], "params": params}
        for chunk_id, start in enumerate(range(0, len(records), chunk_size))
    ]
    started = time.perf_counter()
    map_started = time.perf_counter()
    remote = list(kpi_sensitivity_image.map(payloads))
    map_wall_s = time.perf_counter() - map_started
    container_seconds = float(sum(result["wall_s"] for result in remote))
    rate = 2 * 0.0000131 + 4 * 0.00000222
    _append_modal_run(
        cfg, "kpi_sensitivity", len(payloads), map_wall_s, "Modal CPU (2 cores, 4 GiB)",
        container_seconds * rate,
    )
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
            if pd.isna(local_value) and pd.isna(remote_value):
                continue
            if col in kpi.FRAC_COLS:
                matches = local_value == remote_value
            else:
                matches = np.isclose(local_value, remote_value, rtol=1e-12, atol=0)
            if not matches:
                raise AssertionError(
                    f"scale-1.0 KPI mismatch at {row['tile_id']} {col}: "
                    f"{remote_value} != {local_value}"
                )

    for row in sensitivity_rows:
        for col in kpi.FRAC_COLS:
            expected = local_sensitivity.at[(row["tile_id"], row["scale"]), col]
            if row[col] != expected:
                raise AssertionError(
                    f"Modal fraction mismatch at {row['tile_id']} scale={row['scale']} {col}: "
                    f"{row[col]} != {expected}"
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
    elapsed = time.perf_counter() - started
    print(
        f"kpi_sensitivity: {len(sensitivity_rows)} tile-scale rows, {len(payloads) * 3} image-scale rows; "
        f"{parity_checks}/{len(rows)} byte-identical masks; scale-1.0 KPI and fraction parity exact; "
        f"Modal wall={map_wall_s:.2f}s, container seconds={container_seconds:.2f}, "
        f"local elapsed={elapsed:.2f}s, estimated cost=${container_seconds * rate:.6f}"
    )


def _run_kpi_local_benchmark() -> None:
    import numpy as np
    import pandas as pd
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
    tasks = [
        (row, str(tiles_dir), str(masks_dir), params)
        for row in rows.sort_values(["batch", "sample_id", "y", "x"]).to_dict("records")
    ]
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(kpi._sensitivity_work, tasks, chunksize=4))
    wall_s = time.perf_counter() - started
    parity_checks = sum(result["mask_parity_checks"] for result in results)
    local_rows = [row for result in results for row in result["rows"]]

    remote = pd.read_parquet(results_dir / "kpi_sensitivity.parquet")
    remote = remote.loc[remote["level"] == "tile"].set_index(["tile_id", "scale"])
    max_abs_diff = 0.0
    for row in local_rows:
        for column in kpi.KPI_COLS:
            local_value = row[column]
            remote_value = remote.at[(row["tile_id"], row["scale"]), column]
            if pd.isna(local_value) and pd.isna(remote_value):
                continue
            if column in kpi.FRAC_COLS:
                matches = local_value == remote_value
            else:
                matches = np.isclose(local_value, remote_value, rtol=1e-12, atol=0)
                max_abs_diff = max(max_abs_diff, abs(local_value - remote_value))
            if not matches:
                raise AssertionError(
                    f"local/Modal KPI mismatch at {row['tile_id']} scale={row['scale']} "
                    f"{column}: {local_value} != {remote_value}"
                )

    _append_modal_run(
        cfg,
        "kpi_sensitivity_local",
        len(tasks),
        wall_s,
        "local-cpu (8 cores)",
        0.0,
        "local CPU benchmark (8 worker processes); no Modal charge",
    )
    print(
        f"kpi_sensitivity_local: {len(local_rows)} tile-scale rows; "
        f"{parity_checks}/{len(rows)} byte-identical masks; fractions exact; "
        f"all KPI values matched Modal within 1e-12; max_abs_diff={max_abs_diff:.3g}; "
        f"8-core local wall={wall_s:.2f}s"
    )


@app.local_entrypoint()
def main(task: str = "kpi"):
    if task == "kpi":
        _run_kpi_sensitivity()
        return
    if task == "kpi-local":
        _run_kpi_local_benchmark()
        return
    raise ValueError(f"unsupported task {task!r}")

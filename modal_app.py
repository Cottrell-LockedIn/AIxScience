"""Modal fan-out for KPI and feature sensitivity plus frozen DINOv2 embeddings."""

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import time

import modal

from qc import config as _config

app = modal.App("aixscience-qc")
data_volume = modal.Volume.from_name("aixscience-data", create_if_missing=True)
weights_volume = modal.Volume.from_name("aixscience-weights", create_if_missing=True)
base_image = (
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
)
common_image = base_image.add_local_python_source("qc")
gpu_image = base_image.pip_install(
    "torch==2.14.1+cu130",
    "torchvision==0.29.1+cu130",
    extra_index_url="https://download.pytorch.org/whl/cu130",
).add_local_python_source("qc")

MODAL_RUN_COLUMNS = [
    "timestamp_utc", "function", "n_inputs", "wall_s", "hardware", "git_sha",
    "config_hash", "est_cost_usd", "cost_source", "local_remote_max_abs_diff",
    "repeat_max_abs_diff",
]
LEGACY_MODAL_RUN_COLUMNS = MODAL_RUN_COLUMNS[:-2]
DINO_LOCAL_REMOTE_MAX_ABS_TOL = 1e-4
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


@app.function(
    image=common_image,
    cpu=2,
    memory=4096,
    volumes={"/mnt/data": data_volume},
    timeout=30 * 60,
    max_containers=20,
)
def feature_sensitivity_chunk(payload: dict) -> dict:
    from concurrent.futures import ThreadPoolExecutor
    from qc import features

    started = time.perf_counter()
    params = payload["params"]

    def process(row):
        return features._feature_tile_sensitivity_work(
            (row, "/mnt/data/tiles", "/mnt/data/masks", params)
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(process, payload["rows"]))
    return {
        "chunk_id": payload["chunk_id"],
        "masks": results,
        "n_tiles": len(results),
        "mask_parity_checks": sum(result["mask_parity_checks"] for result in results),
        "wall_s": time.perf_counter() - started,
    }


@app.function(
    image=common_image,
    cpu=2,
    memory=4096,
    timeout=30 * 60,
    max_containers=20,
)
def feature_image_sensitivity(payload: dict) -> dict:
    from qc import features

    return features._feature_image_sensitivity_work(payload)


@app.cls(
    image=gpu_image,
    gpu="L4",
    cpu=4,
    memory=8192,
    volumes={"/mnt/data": data_volume, "/mnt/weights": weights_volume},
    timeout=60 * 60,
    max_containers=20,
)
class DINOv2ImageEncoder:
    weights_cfg_json: str = modal.parameter()

    @modal.enter()
    def load_model(self):
        import json
        import pandas as pd
        import torch
        from qc import embed

        self.weights_cfg = json.loads(self.weights_cfg_json)
        weights_volume.reload()
        weights_path = Path("/mnt/weights") / embed.WEIGHT_FILENAME
        if not weights_path.is_file():
            raise FileNotFoundError(
                f"missing checksum-verified DINOv2 weights in aixscience-weights: {weights_path}"
            )
        expected = str(self.weights_cfg["weights_sha256"]).lower()
        actual = embed._sha256(weights_path)
        if actual != expected:
            raise ValueError(
                f"DINOv2 weights SHA-256 mismatch: expected {expected}, got {actual}"
            )
        torch.set_num_threads(1)
        self.model = embed.load_frozen_model(self.weights_cfg, weights_path, "cuda")
        self.index = pd.read_parquet("/mnt/data/tiles/index.parquet").sort_values(
            "tile_id", kind="stable"
        )
        self.tiles_dir = Path("/mnt/data/tiles")

    @modal.method()
    def embed_image(self, payload: dict) -> dict:
        from qc import embed

        rows = self.index.loc[
            (self.index["sample_id"].astype(str) == str(payload["sample_id"]))
            & (self.index["channel"].astype(str) == str(payload["channel"]))
        ]
        if rows.empty:
            raise ValueError(f"no tiles found for image-channel input {payload}")
        result = embed.embed_image_rows(
            self.model,
            rows,
            self.tiles_dir,
            int(self.weights_cfg["input_px"]),
            "cuda",
            batch_size=16,
        )
        return {
            "sample_id": str(payload["sample_id"]),
            "channel": str(payload["channel"]),
            **result,
        }


def _append_modal_run(
    cfg: dict,
    function: str,
    n_inputs: int,
    wall_s: float,
    hardware: str,
    est_cost_usd: float,
    cost_source: str = MODAL_PRICING,
    *,
    local_remote_max_abs_diff: float | None = None,
    repeat_max_abs_diff: float | None = None,
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
        "local_remote_max_abs_diff": local_remote_max_abs_diff,
        "repeat_max_abs_diff": repeat_max_abs_diff,
    }
    row = pd.DataFrame([record], columns=MODAL_RUN_COLUMNS)
    if path.exists():
        existing = pd.read_csv(path)
        if list(existing.columns) == LEGACY_MODAL_RUN_COLUMNS:
            existing["local_remote_max_abs_diff"] = float("nan")
            existing["repeat_max_abs_diff"] = float("nan")
            existing = existing[MODAL_RUN_COLUMNS]
            existing.to_csv(path, index=False)
        elif list(existing.columns) != MODAL_RUN_COLUMNS:
            raise RuntimeError(f"unexpected Modal run log schema in {path}")
        row.to_csv(path, mode="a", index=False, header=False)
    else:
        row.to_csv(path, index=False)


def _assert_sensitivity_unchanged(new, path: Path) -> float:
    import numpy as np
    import pandas as pd
    from qc import kpi

    if not path.exists():
        return 0.0
    old = pd.read_parquet(path)
    provenance = {"config_hash", "git_sha"}
    columns = [column for column in new.columns if column not in provenance]
    old_columns = [column for column in old.columns if column not in provenance]
    if columns != old_columns:
        raise AssertionError(
            f"kpi_sensitivity schema changed: previous={old_columns}, new={columns}"
        )
    sort_keys = [key for key in ("level", "sample_id", "scale", "tile_id") if key in columns]
    old = old.sort_values(sort_keys, kind="stable", na_position="last")[columns].reset_index(drop=True)
    current = new.sort_values(sort_keys, kind="stable", na_position="last")[columns].reset_index(drop=True)
    exact_kpis = {
        "frac_c0", "frac_c1", "frac_c2", "c2_count_density_per_Mpx",
        "c2_eqdiam_median_px", "c2_eqdiam_p90_px", "c0_region_eqdiam_median_px",
        "c0_region_area_mean_px", "c1_largest_component_frac", "c0_cracklike_frac",
    }
    max_abs_diff = 0.0
    for column in columns:
        left, right = old[column].to_numpy(), current[column].to_numpy()
        if column in exact_kpis or not np.issubdtype(left.dtype, np.number):
            equal = (left == right) | (pd.isna(left) & pd.isna(right))
        else:
            equal = np.isclose(left, right, rtol=1e-12, atol=0, equal_nan=True)
            finite = np.isfinite(left) & np.isfinite(right)
            if np.any(finite):
                max_abs_diff = max(max_abs_diff, float(np.max(np.abs(left[finite] - right[finite]))))
        if not np.all(equal):
            position = int(np.flatnonzero(~equal)[0])
            raise AssertionError(
                f"optimized KPI sensitivity differs at row {position}, column {column}: "
                f"{left[position]!r} != {right[position]!r}"
            )
    return max_abs_diff


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
    max_abs_diff = _assert_sensitivity_unchanged(
        sensitivity, results_dir / "kpi_sensitivity.parquet"
    )
    sensitivity.to_parquet(results_dir / "kpi_sensitivity.parquet", index=False)
    elapsed = time.perf_counter() - started
    print(
        f"kpi_sensitivity: {len(sensitivity_rows)} tile-scale rows, {len(image)} image-scale rows; "
        f"{parity_checks}/{len(rows)} byte-identical masks; scale-1.0 KPI and fraction parity exact; "
        f"old KPI values/fractions exact, other floats within 1e-12 (max abs={max_abs_diff:.3g}); "
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


def _feature_sensitivity_setup(cfg: dict):
    import pandas as pd
    from qc import features, kpi, segment

    results_dir = _config.ROOT / "results"
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    masks_dir = _config.resolve(cfg["data"].get("masks_dir", "data/masks"))
    index = pd.read_parquet(tiles_dir / "index.parquet")
    index = index.loc[index["channel"] == "BSE"]
    thresholds = pd.read_parquet(results_dir / "thresholds_per_tile.parquet")
    rows = kpi.join_thresholds(thresholds, index, cfg)
    rows = rows.merge(
        index[["tile_id", "img_h", "img_w"]],
        on="tile_id",
        how="left",
        validate="one_to_one",
    )
    if len(rows) != len(index):
        raise RuntimeError(f"expected {len(index)} BSE rows, got {len(rows)} threshold rows")

    segmentation_params = segment.params(cfg["segmentation"])
    records = rows.sort_values(["batch", "sample_id", "y", "x"]).to_dict("records")
    chunk_size = 10
    label_payloads = [
        {
            "chunk_id": chunk_id,
            "rows": records[start:start + chunk_size],
            "params": segmentation_params,
        }
        for chunk_id, start in enumerate(range(0, len(records), chunk_size))
    ]
    feature_cfg, feature_hash = features._feature_config()
    thickness_cfg = feature_cfg["local_thickness"]
    feature_params = {
        "min_object_px": int(cfg["segmentation"]["min_object_px"]),
        "thickness_exact_radius_max_px": float(thickness_cfg["exact_radius_max_px"]),
        "thickness_growth": float(thickness_cfg["radius_growth"]),
        "heterogeneity_window_px": int(feature_cfg["heterogeneity"]["window_px"]),
        "pixel_size_nm_if_true": float(feature_cfg["pixel_size_nm_if_true"]),
    }
    return {
        "results_dir": results_dir,
        "tiles_dir": tiles_dir,
        "masks_dir": masks_dir,
        "rows": rows,
        "label_payloads": label_payloads,
        "feature_cfg": feature_cfg,
        "feature_hash": feature_hash,
        "feature_params": feature_params,
        "segmentation_params": segmentation_params,
    }


def _build_feature_image_payloads(
    rows,
    label_results: list[dict],
    feature_params: dict,
    unanalysed_value: int,
) -> list[dict]:
    mask_map = {}
    for chunk in label_results:
        for tile in chunk["masks"]:
            for item in tile["mask_pngs"]:
                mask_map[(tile["tile_id"], item["scale"])] = item["png"]

    payloads = []
    for (batch, sample_id), group in rows.groupby(["batch", "sample_id"], sort=True):
        group = group.sort_values(["y", "x"], kind="stable")
        first = group.iloc[0]
        tile_rows = group[["tile_id", "y", "x"]].to_dict("records")
        for scale in (0.9, 1.0, 1.1):
            masks = []
            for row in tile_rows:
                key = (row["tile_id"], scale)
                if key not in mask_map:
                    raise RuntimeError(f"missing sensitivity mask for {key}")
                masks.append({"tile_id": row["tile_id"], "png": mask_map[key]})
            payloads.append(
                {
                    "batch": batch,
                    "sample_id": sample_id,
                    "scale": scale,
                    "image_shape": (int(first["img_h"]), int(first["img_w"])),
                    "unanalysed_value": unanalysed_value,
                    "rows": tile_rows,
                    "mask_pngs": masks,
                    "feature_params": feature_params,
                }
            )
    return payloads


def _assert_feature_scale_one(
    rows: list[dict],
    baseline_path: Path,
) -> None:
    import numpy as np
    import pandas as pd
    from qc import features

    baseline = pd.read_parquet(baseline_path).set_index("sample_id")
    exact_columns = {
        "F01_c0_area_fraction",
        "F02_c2_area_fraction",
        "F05_c2_count_density_per_Mpx",
        "F10_c0_fraction_iqr_512px",
        "F11_c2_perimeter_fraction_adjacent_c0",
    }
    feature_columns = [
        *features.FEATURE_COLUMNS,
        "F03_c2_eqdiam_median_nm_if25",
        "F04_c2_eqdiam_p90_nm_if25",
        "F08_c0_local_thickness_median_nm_if25",
    ]
    for row in rows:
        if row["scale"] != 1.0:
            continue
        for column in feature_columns:
            actual = row[column]
            expected = baseline.at[row["sample_id"], column]
            if pd.isna(actual) and pd.isna(expected):
                continue
            matches = (
                actual == expected
                if column in exact_columns
                else np.isclose(actual, expected, rtol=1e-12, atol=0)
            )
            if not matches:
                raise AssertionError(
                    f"scale-1.0 feature mismatch for {row['sample_id']} {column}: "
                    f"{actual} != {expected}"
                )


def _run_features_sensitivity() -> None:
    import numpy as np
    import pandas as pd
    from qc import features

    cfg = _config.load()
    setup = _feature_sensitivity_setup(cfg)
    rows = setup["rows"]
    label_payloads = setup["label_payloads"]
    feature_params = setup["feature_params"]
    overall_started = time.perf_counter()

    label_started = time.perf_counter()
    label_results = list(feature_sensitivity_chunk.map(label_payloads))
    label_wall_s = time.perf_counter() - label_started
    label_container_seconds = float(sum(result["wall_s"] for result in label_results))
    cpu_rate = 2 * 0.0000131 + 4 * 0.00000222
    _append_modal_run(
        cfg,
        "features_sensitivity_labels",
        len(label_payloads),
        label_wall_s,
        "Modal CPU (2 cores, 4 GiB)",
        label_container_seconds * cpu_rate,
    )
    parity_checks = sum(result["mask_parity_checks"] for result in label_results)
    if parity_checks != len(rows):
        raise RuntimeError(f"feature mask parity checks {parity_checks} != {len(rows)}")

    feature_payloads = _build_feature_image_payloads(
        rows,
        label_results,
        feature_params,
        int(setup["feature_cfg"]["stitch"]["unanalysed_value"]),
    )
    image_started = time.perf_counter()
    image_results = list(feature_image_sensitivity.map(feature_payloads))
    image_wall_s = time.perf_counter() - image_started
    image_container_seconds = float(sum(result["wall_s"] for result in image_results))
    _append_modal_run(
        cfg,
        "features_sensitivity_images",
        len(feature_payloads),
        image_wall_s,
        "Modal CPU (2 cores, 4 GiB)",
        image_container_seconds * cpu_rate,
    )
    feature_rows = [
        {key: value for key, value in result.items() if key != "wall_s"}
        for result in image_results
    ]
    if len(feature_rows) != 93:
        raise RuntimeError(f"expected 93 image-scale feature rows, got {len(feature_rows)}")
    _assert_feature_scale_one(
        feature_rows,
        setup["results_dir"] / "features_per_image.parquet",
    )
    output = pd.DataFrame(feature_rows).sort_values(
        ["batch", "sample_id", "scale"], kind="stable"
    )
    output["phase_identity"] = features.PHASE_IDENTITY
    output["features_config_hash"] = setup["feature_hash"]
    output = _config.stamp(output, cfg)
    output.to_parquet(setup["results_dir"] / "features_sensitivity.parquet", index=False)

    overall_wall_s = time.perf_counter() - overall_started
    total_cost = (
        label_container_seconds + image_container_seconds
    ) * cpu_rate
    print(
        f"features_sensitivity: {len(label_payloads)} ten-tile label inputs, "
        f"{parity_checks}/{len(rows)} scale-1.0 byte-identical masks; "
        f"{len(feature_rows)} image-scale rows; scale-1.0 features matched baseline; "
        f"Modal wall={overall_wall_s:.2f}s (labels={label_wall_s:.2f}s, "
        f"images={image_wall_s:.2f}s), estimated cost=${total_cost:.6f}"
    )


def _run_features_local_benchmark() -> None:
    import numpy as np
    import pandas as pd
    from qc import features

    cfg = _config.load()
    setup = _feature_sensitivity_setup(cfg)
    rows = setup["rows"]
    label_tasks = [
        (
            payload["chunk_id"],
            payload["rows"],
            str(setup["tiles_dir"]),
            str(setup["masks_dir"]),
            payload["params"],
        )
        for payload in setup["label_payloads"]
    ]
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=8) as executor:
        label_results = list(
            executor.map(features._feature_sensitivity_chunk_work, label_tasks, chunksize=1)
        )
    parity_checks = sum(result["mask_parity_checks"] for result in label_results)
    feature_payloads = _build_feature_image_payloads(
        rows,
        label_results,
        setup["feature_params"],
        int(setup["feature_cfg"]["stitch"]["unanalysed_value"]),
    )
    with ProcessPoolExecutor(max_workers=8) as executor:
        image_results = list(
            executor.map(
                features._feature_image_sensitivity_work,
                feature_payloads,
                chunksize=1,
            )
        )
    wall_s = time.perf_counter() - started
    local_rows = [
        {key: value for key, value in result.items() if key != "wall_s"}
        for result in image_results
    ]
    remote = pd.read_parquet(
        setup["results_dir"] / "features_sensitivity.parquet"
    ).set_index(["sample_id", "scale"])
    exact_columns = {
        "F01_c0_area_fraction",
        "F02_c2_area_fraction",
        "F05_c2_count_density_per_Mpx",
        "F10_c0_fraction_iqr_512px",
        "F11_c2_perimeter_fraction_adjacent_c0",
    }
    feature_columns = [
        *features.FEATURE_COLUMNS,
        "F03_c2_eqdiam_median_nm_if25",
        "F04_c2_eqdiam_p90_nm_if25",
        "F08_c0_local_thickness_median_nm_if25",
    ]
    max_abs_diff = 0.0
    for row in local_rows:
        for column in feature_columns:
            local_value = row[column]
            remote_value = remote.at[(row["sample_id"], row["scale"]), column]
            if pd.isna(local_value) and pd.isna(remote_value):
                continue
            if column in exact_columns:
                matches = local_value == remote_value
            else:
                matches = np.isclose(local_value, remote_value, rtol=1e-12, atol=0)
                max_abs_diff = max(max_abs_diff, abs(local_value - remote_value))
            if not matches:
                raise AssertionError(
                    f"local/Modal feature mismatch for {row['sample_id']} "
                    f"scale={row['scale']} {column}: {local_value} != {remote_value}"
                )

    _append_modal_run(
        cfg,
        "features_sensitivity_local",
        len(setup["label_payloads"]) + len(feature_payloads),
        wall_s,
        "local-cpu (8 cores)",
        0.0,
        "local CPU benchmark (8 worker processes); no Modal charge",
    )
    print(
        f"features_sensitivity_local: {len(feature_payloads)} image-scale rows; "
        f"{parity_checks}/{len(rows)} byte-identical masks; feature values matched Modal "
        f"within 1e-12 (max abs={max_abs_diff:.3g}); 8-core local wall={wall_s:.2f}s"
    )


def _dino_cost(container_seconds: float) -> float:
    return container_seconds * (
        0.000222 + 4 * 0.0000131 + 8 * 0.00000222
    )


def _run_dino_embedding_checks(
    cfg,
    benchmark_group,
    benchmark_rows,
    weights_cfg,
    local_weights,
    *,
    torch,
    embed,
) -> tuple[float, float, float, float]:
    import numpy as np
    torch.set_num_threads(8)
    local_model = embed.load_frozen_model(weights_cfg, local_weights, "cpu")
    local_started = time.perf_counter()
    local_result = embed.embed_image_rows(
        local_model,
        benchmark_rows,
        _config.resolve(cfg["data"]["tiles_dir"]),
        int(weights_cfg["input_px"]),
        "cpu",
        batch_size=8,
    )
    local_wall = time.perf_counter() - local_started
    _append_modal_run(
        cfg,
        "dino_embed_one_image_local",
        1,
        local_wall,
        "local-cpu (8 cores)",
        0.0,
        "local CPU benchmark (8 cores); no Modal charge",
    )

    encoder = DINOv2ImageEncoder(
        weights_cfg_json=json.dumps(weights_cfg, sort_keys=True)
    )
    remote_started = time.perf_counter()
    remote_one = list(encoder.embed_image.map([benchmark_group]))
    remote_wall = time.perf_counter() - remote_started
    remote_one_result = remote_one[0]
    local_ids = [row["tile_id"] for row in local_result["rows"]]
    remote_ids = [row["tile_id"] for row in remote_one_result["rows"]]
    if local_ids != remote_ids:
        raise AssertionError("local and Modal one-image tile order differs")
    local_remote_diff = float(
        np.max(np.abs(local_result["embeddings"] - remote_one_result["embeddings"]))
    )
    if local_remote_diff > DINO_LOCAL_REMOTE_MAX_ABS_TOL:
        raise AssertionError(
            f"local/Modal embedding difference {local_remote_diff:.6g} exceeds "
            f"{DINO_LOCAL_REMOTE_MAX_ABS_TOL:g}"
        )
    _append_modal_run(
        cfg,
        "dino_embed_one_image",
        1,
        remote_wall,
        "L4",
        _dino_cost(float(remote_one_result["wall_s"])),
        local_remote_max_abs_diff=local_remote_diff,
    )

    repeat_started = time.perf_counter()
    repeats = list(encoder.embed_image.map([benchmark_group, benchmark_group]))
    repeat_wall = time.perf_counter() - repeat_started
    repeat_diff = float(np.max(np.abs(repeats[0]["embeddings"] - repeats[1]["embeddings"])))
    if repeat_diff != 0:
        raise AssertionError(f"repeated Modal embeddings differ by {repeat_diff:.6g}")
    _append_modal_run(
        cfg,
        "dino_embed_repeat",
        2,
        repeat_wall,
        "L4",
        _dino_cost(sum(float(result["wall_s"]) for result in repeats)),
        repeat_max_abs_diff=repeat_diff,
    )
    print(
        f"dino_embedding_checks: local one-image wall={local_wall:.2f}s; "
        f"Modal one-image wall={remote_wall:.2f}s; "
        f"local/Modal max_abs_diff={local_remote_diff:.3g}; "
        f"repeat max_abs_diff={repeat_diff:.3g}"
    )
    return local_wall, remote_wall, local_remote_diff, repeat_diff


def _load_dino_embedding_inputs():
    import torch
    from qc import embed

    cfg = _config.load()
    weights_cfg = cfg["embeddings"]
    index = embed.load_tile_index(cfg)
    groups = embed.image_groups(index)
    if len(index) != 4329 or len(groups) != 93:
        raise AssertionError(
            f"expected 4329 tiles across 93 image-channels, got {len(index)} and {len(groups)}"
        )
    local_weights = embed.local_weights_path(weights_cfg)
    with weights_volume.batch_upload(force=True) as batch:
        batch.put_file(str(local_weights), f"/{embed.WEIGHT_FILENAME}")
    benchmark_group = groups[0]
    benchmark_rows = index.loc[
        (index["sample_id"].astype(str) == benchmark_group["sample_id"])
        & (index["channel"].astype(str) == benchmark_group["channel"])
    ]
    return cfg, weights_cfg, index, groups, local_weights, benchmark_group, benchmark_rows, torch, embed


def _run_dino_embedding_checks_only() -> None:
    (
        cfg, weights_cfg, _, _, local_weights, benchmark_group, benchmark_rows,
        torch, embed,
    ) = _load_dino_embedding_inputs()
    _run_dino_embedding_checks(
        cfg,
        benchmark_group,
        benchmark_rows,
        weights_cfg,
        local_weights,
        torch=torch,
        embed=embed,
    )


def _run_dino_embeddings() -> None:
    import numpy as np

    (
        cfg, weights_cfg, index, groups, local_weights, benchmark_group,
        benchmark_rows, torch, embed,
    ) = _load_dino_embedding_inputs()
    local_wall, remote_wall, local_remote_diff, repeat_diff = _run_dino_embedding_checks(
        cfg,
        benchmark_group,
        benchmark_rows,
        weights_cfg,
        local_weights,
        torch=torch,
        embed=embed,
    )

    full_started = time.perf_counter()
    results = list(encoder.embed_image.map(groups))
    full_wall = time.perf_counter() - full_started
    _append_modal_run(
        cfg,
        "dino_embed_full",
        len(groups),
        full_wall,
        "L4",
        _dino_cost(sum(float(result["wall_s"]) for result in results)),
    )

    vectors_by_tile = {}
    for result in results:
        for row, vector in zip(result["rows"], result["embeddings"], strict=True):
            vectors_by_tile[str(row["tile_id"])] = vector
    tile_order = index["tile_id"].astype(str).tolist()
    if set(vectors_by_tile) != set(tile_order):
        raise AssertionError(
            f"embedding coverage mismatch: {len(vectors_by_tile)} embeddings for {len(tile_order)} tiles"
        )
    embeddings = np.stack([vectors_by_tile[tile_id] for tile_id in tile_order]).astype(
        np.float32, copy=False
    )
    embed.write_outputs(cfg, index, embeddings)
    print(f"dino_embedding: full Modal wall={full_wall:.2f}s; {len(embeddings)} tile embeddings")


@app.local_entrypoint()
def main(task: str = "kpi"):
    if task == "kpi":
        _run_kpi_sensitivity()
        return
    if task == "kpi-local":
        _run_kpi_local_benchmark()
        return
    if task == "features":
        _run_features_sensitivity()
        return
    if task == "features-local":
        _run_features_local_benchmark()
        return
    if task == "embed":
        _run_dino_embeddings()
        return
    if task == "embed-check":
        _run_dino_embedding_checks_only()
        return
    raise ValueError(f"unsupported task {task!r}")

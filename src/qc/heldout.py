"""Frozen image-level inference for the quarantined held-out set."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import warnings
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
from PIL import Image, PngImagePlugin

from qc import audit, artefacts, classify, config as _config, embed, features, segment, tiles

CHANNELS = {"BSE", "Inlens", "ETD", "SE"}
V1_MODAL_RUN_PATH = Path("results") / "v1" / "MODAL_RUNS_v1.csv"
EXPLORATORY_DIR = Path("results") / "v1" / "exploratory"
V1_MODAL_RUN_COLUMNS = [
    "timestamp_utc", "function", "n_inputs", "wall_s", "hardware", "git_sha",
    "config_hash", "est_cost_usd", "cost_source", "local_remote_max_abs_diff",
    "repeat_max_abs_diff",
]


def parse_filename(path: str | Path) -> tuple[str, str] | None:
    path = Path(path)
    match = tiles.NAME_RE.match(path.name)
    if match:
        return match["sample"], match["channel"]

    tokens = path.stem.split("_")
    channel_positions = [index for index, token in enumerate(tokens) if token in CHANNELS]
    if not channel_positions:
        return None
    channel_index = channel_positions[0]
    channel = tokens[channel_index]
    sample_id = "_".join(tokens[:channel_index] + tokens[channel_index + 1 :])
    if sample_id.startswith("img_"):
        sample_id = sample_id[4:]
    return (sample_id, channel) if sample_id else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_key(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _discover_files(
    input_dir: Path,
) -> tuple[dict[str, dict[str, Path]], dict[str, str], list[str]]:
    groups: dict[str, dict[str, Path]] = {}
    file_hashes: dict[str, str] = {}
    notes: list[str] = []
    paths = sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".tif", ".tiff"}
    )
    for path in paths:
        key = _file_key(path, _config.ROOT)
        file_hashes[key] = _sha256(path)
        parsed = parse_filename(path)
        if parsed is None:
            message = f"Could not parse channel/sample id from {key}; file hash recorded, image skipped."
            warnings.warn(message)
            notes.append(message)
            continue
        sample_id, channel = parsed
        channels = groups.setdefault(sample_id, {})
        if channel in channels:
            message = (
                f"Duplicate {channel} files for {sample_id}; keeping "
                f"{_file_key(channels[channel], _config.ROOT)} and skipping {key}."
            )
            warnings.warn(message)
            notes.append(message)
            continue
        channels[channel] = path

    complete: dict[str, dict[str, Path]] = {}
    for sample_id, channels in sorted(groups.items()):
        if "BSE" not in channels:
            message = f"Skipping {sample_id}: required BSE channel is missing."
            warnings.warn(message)
            notes.append(message)
            continue
        complete[sample_id] = channels
    return complete, file_hashes, notes


def _feature_parameters(cfg: dict[str, Any], feature_cfg: dict[str, Any]) -> dict[str, Any]:
    thickness = feature_cfg["local_thickness"]
    return {
        "min_object_px": int(cfg["segmentation"]["min_object_px"]),
        "thickness_exact_radius_max_px": float(thickness["exact_radius_max_px"]),
        "thickness_growth": float(thickness["radius_growth"]),
        "heterogeneity_window_px": int(feature_cfg["heterogeneity"]["window_px"]),
        "pixel_size_nm_if_true": float(feature_cfg["pixel_size_nm_if_true"]),
    }


def _prepare_channel(
    path: Path,
    sample_id: str,
    channel: str,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    image = tiles.read_gray(path, int(cfg["data"]["read_channel"]))
    image = tiles.crop_border(image, int(cfg["data"]["border_crop_px"]))
    tile_px = int(cfg["tiling"]["tile_px"])
    stride_px = int(cfg["tiling"]["stride_px"])
    rows = []
    arrays: dict[str, np.ndarray] = {}
    for y, x in tiles.tile_grid(image.shape[0], image.shape[1], tile_px, stride_px):
        tile_id = f"{sample_id}_{channel}_{y:05d}_{x:05d}"
        arrays[tile_id] = image[y : y + tile_px, x : x + tile_px]
        rows.append(
            {"tile_id": tile_id, "sample_id": sample_id, "channel": channel, "y": y, "x": x}
        )
    ordered_rows = sorted(rows, key=lambda row: row["tile_id"])
    ordered_arrays = [(row, arrays[row["tile_id"]]) for row in ordered_rows]
    metric_rows = [
        {
            "batch": "heldout",
            "sample_id": sample_id,
            "channel": channel,
            **artefacts.tile_metrics(tile, cfg["artefacts"]),
        }
        for _, tile in ordered_arrays
    ]
    if metric_rows:
        image_metrics = artefacts.per_image(pd.DataFrame(metric_rows))
        metrics = image_metrics.iloc[0][artefacts.METRICS].to_dict()
    else:
        metrics = {}
    return {
        "image": image,
        "rows": ordered_rows,
        "tiles": ordered_arrays,
        "metrics": metrics,
    }


def _extract_features(
    bse: dict[str, Any],
    cfg: dict[str, Any],
    feature_cfg: dict[str, Any],
) -> tuple[dict[str, float], np.ndarray]:
    segmentation_cfg = segment.params(cfg["segmentation"])
    mask_arrays: dict[str, np.ndarray] = {}
    for row, tile in bse["tiles"]:
        mask, _ = segment.segment_tile(tile, segmentation_cfg)
        mask_arrays[row["tile_id"]] = mask
    stitched = features.stitch_mask(
        pd.DataFrame(bse["rows"]),
        None,
        tuple(bse["image"].shape),
        int(feature_cfg["stitch"]["unanalysed_value"]),
        mask_arrays=mask_arrays,
    )
    return features.extract_features(stitched, **_feature_parameters(cfg, feature_cfg)), stitched


def _segmentation_overlay(image: np.ndarray, mask: np.ndarray, downscale: int) -> np.ndarray:
    if image.ndim != 2 or image.shape != mask.shape:
        raise ValueError("mask and cropped grayscale image must have the same 2D shape")
    if mask.dtype != np.uint8 or not np.isin(mask, [0, 1, 2]).all():
        raise ValueError("mask must be uint8 with only class labels 0, 1, and 2")
    if downscale < 1:
        raise ValueError("overlay downscale must be positive")
    height, width = image.shape
    size = (max(1, width // downscale), max(1, height // downscale))
    gray = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    labels = cv2.resize(mask, size, interpolation=cv2.INTER_NEAREST)
    rgb = np.repeat(gray[..., None], 3, axis=2).astype(np.float64)
    for label, color in ((0, (31, 119, 180)), (2, (255, 127, 14))):
        selected = labels == label
        rgb[selected] = 0.55 * rgb[selected] + 0.45 * np.asarray(color)
    return np.rint(rgb).astype(np.uint8)


def _save_segmentation(
    output: Path,
    sample_id: str,
    image: np.ndarray,
    mask: np.ndarray,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    downscale = int(cfg["tiling"]["preview_downscale"])
    overlay = _segmentation_overlay(image, mask, downscale)
    mask_png = features._encode_label_png(mask)
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("exploratory", "true")
    metadata.add_text("phase_identity", classify.PHASE_IDENTITY)
    buffer = BytesIO()
    Image.fromarray(overlay).save(buffer, format="PNG", pnginfo=metadata)
    paths = {
        output.parent / "masks" / f"{sample_id}_mask.png": mask_png,
        output.parent / "masks" / f"{sample_id}_overlay.png": buffer.getvalue(),
    }
    for path, content in paths.items():
        if path.exists() and path.read_bytes() != content:
            raise FileExistsError(f"refusing to overwrite different segmentation artifact {path}")
    for path, content in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(content)
    border = int(cfg["data"]["border_crop_px"])
    return {
        "kind": "segmentation_mask",
        "exploratory": True,
        "mask_path": f"masks/{sample_id}_mask.png",
        "overlay_path": f"masks/{sample_id}_overlay.png",
        "mask_sha256": hashlib.sha256(mask_png).hexdigest(),
        "mask_shape": list(mask.shape),
        "mask_offset_px": [border, border],
        "class_values": {"0": "void", "1": "graphite", "2": "silicon"},
        "overlay_downscale": downscale,
        "overlay_alpha": 0.45,
        "legend": "void (0): blue (31,119,180); graphite (1): unshaded; silicon (2): orange (255,127,14)",
        "phase_identity": classify.PHASE_IDENTITY,
        "note": "one fixed threshold segmentation, not ground truth; 7/11 measurements move under +-10 % threshold shifts",
    }


def _covariate_values(
    channels: dict[str, dict[str, Any]],
    bse_path: Path,
    training_names: list[str],
) -> tuple[dict[str, float], list[str]]:
    notes: list[str] = []
    file_meta = audit.inspect_file(str(bse_path))
    available: dict[str, float | None] = {
        "height": float(file_meta["height"]),
        "nm_per_px_if_tag_true": file_meta["nm_per_px_if_tag_true"],
    }
    for channel in ("BSE", "Inlens"):
        if channel not in channels:
            if channel == "Inlens":
                notes.append("Inlens channel is missing; its edge-charging covariate is omitted.")
            continue
        for metric, value in channels[channel]["metrics"].items():
            available[f"{metric}_{channel}"] = value

    values: dict[str, float] = {}
    for name in training_names:
        if name not in available:
            if name.endswith("_Inlens"):
                continue
            notes.append(f"Covariate {name} is unavailable and was omitted; no imputation was used.")
            continue
        if available[name] is None:
            notes.append(f"Covariate {name} is missing and was omitted; no imputation was used.")
            continue
        value = float(available[name])
        if not np.isfinite(value):
            notes.append(f"Covariate {name} is non-finite and was omitted; no imputation was used.")
            continue
        values[name] = value
    return values, notes


def _exact_tag() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "describe", "--tags", "--exact-match", "HEAD"],
            cwd=_config.ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _is_frozen_tag() -> bool:
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_config.ROOT, text=True
        ).strip()
        frozen = subprocess.check_output(
            ["git", "rev-list", "-n", "1", "v1-frozen"],
            cwd=_config.ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return head == frozen
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _out_path(path: str | Path | None, exploratory: bool) -> Path:
    if path is not None:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else _config.ROOT / candidate
    if exploratory:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return _config.ROOT / EXPLORATORY_DIR / f"heldout_{stamp}.json"
    return _config.ROOT / "results" / "v1" / "heldout.json"


def _run_once_guard(out_path: Path, frozen: bool) -> None:
    if out_path.exists():
        raise SystemExit(f"heldout: refusing to overwrite existing output {out_path}")
    if not frozen:
        raise SystemExit("heldout: HEAD is not exactly tagged v1-frozen")
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--", "src", "configs", "schema"],
        cwd=_config.ROOT,
        text=True,
    )
    if dirty.strip():
        raise SystemExit("heldout: src, configs, or schema has uncommitted changes")


def _canonical_output_path() -> Path:
    return (_config.ROOT / "results" / "v1" / "heldout.json").resolve()


def _validate_dryrun_inputs(
    source: Path,
    configured_heldout: Path,
    groups: dict[str, dict[str, Path]],
    training_ids: set[str],
    file_hashes: dict[str, str],
) -> None:
    if source.resolve() == configured_heldout.resolve():
        raise SystemExit("heldout: dry-run input directory cannot be the configured data/heldout")

    unknown = sorted(set(groups) - training_ids)
    if unknown:
        raise SystemExit(f"heldout: dry-run includes non-training sample ids: {unknown}")

    audit_path = _config.ROOT / "results" / "audit" / "images.csv"
    if not audit_path.is_file():
        raise SystemExit(f"heldout: dry-run requires the audit hash table {audit_path}")
    audit = pd.read_csv(audit_path, dtype=str, keep_default_na=False)
    required = {"sample_id", "sha256_BSE"}
    missing = required - set(audit.columns)
    if missing:
        raise SystemExit(f"heldout: {audit_path} is missing columns {sorted(missing)}")
    if audit["sample_id"].duplicated().any():
        raise SystemExit(f"heldout: {audit_path} has duplicate sample ids")
    reference_hashes = audit.set_index("sample_id")["sha256_BSE"].to_dict()
    for sample_id, files in groups.items():
        expected = reference_hashes.get(sample_id, "").strip().lower()
        if not expected:
            raise SystemExit(f"heldout: no audited BSE hash found for dry-run sample {sample_id}")
        bse_key = _file_key(files["BSE"], _config.ROOT)
        actual = file_hashes.get(bse_key, "").lower()
        if actual != expected:
            raise SystemExit(
                f"heldout: BSE sha256 mismatch for dry-run sample {sample_id}; "
                "only byte-identical training BSE images are allowed"
            )


def _append_modal_run(
    cfg: dict[str, Any],
    columns: list[str] | None,
    *,
    wall_s: float,
    n_inputs: int,
    hardware: str,
    cost: float,
    cost_source: str,
    exploratory: bool = False,
) -> None:
    path = _config.ROOT / V1_MODAL_RUN_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = columns or V1_MODAL_RUN_COLUMNS
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "function": "dino_embed_heldout_exploratory" if exploratory else "dino_embed_heldout",
        "n_inputs": str(n_inputs),
        "wall_s": str(wall_s),
        "hardware": hardware,
        "git_sha": _config.git_sha(),
        "config_hash": str(cfg["_hash"]),
        "est_cost_usd": str(cost),
        "cost_source": cost_source,
        "local_remote_max_abs_diff": "",
        "repeat_max_abs_diff": "",
    }
    row = pd.DataFrame([{name: str(record.get(name, "")) for name in columns}], columns=columns)
    if path.exists():
        existing = pd.read_csv(path, dtype=str, keep_default_na=False)
        extra = set(existing.columns) - set(columns)
        if extra:
            raise RuntimeError(f"unexpected Modal run log columns in {path}: {sorted(extra)}")
        for name in columns:
            if name not in existing:
                existing[name] = ""
        existing = existing[columns]
        existing.to_csv(path, index=False)
        row.to_csv(path, mode="a", index=False, header=False)
    else:
        row.to_csv(path, index=False)


def _embed_on_modal(
    cfg: dict[str, Any],
    payloads: list[dict[str, Any]],
    modal_app: Any,
) -> tuple[dict[str, np.ndarray], float, float]:
    weights_cfg = cfg["embeddings"]
    client_started = time.perf_counter()
    with modal_app.app.run():
        encoder = modal_app.DINOv2TileEncoder(
            weights_cfg_json=json.dumps(weights_cfg, sort_keys=True)
        )
        results = list(encoder.embed_tiles.map(payloads))
    client_wall = time.perf_counter() - client_started
    by_sample: dict[str, np.ndarray] = {}
    container_seconds = 0.0
    payload_sizes = {str(payload["sample_id"]): len(payload["tiles"]) for payload in payloads}
    for result in results:
        sample_id = str(result["sample_id"])
        vectors = np.asarray(result["embeddings"], dtype=np.float32)
        expected_shape = (payload_sizes.get(sample_id, -1), embed.EMBEDDING_WIDTH)
        if vectors.shape != expected_shape:
            raise ValueError(f"invalid held-out embedding shape for {sample_id}: {vectors.shape}")
        by_sample[sample_id] = vectors
        container_seconds += float(result["wall_s"])
    if set(by_sample) != set(payload_sizes):
        raise ValueError("Modal held-out embedding coverage does not match submitted images")
    return by_sample, client_wall, container_seconds


def _embed_local_cpu(
    cfg: dict[str, Any],
    payloads: list[dict[str, Any]],
) -> tuple[dict[str, np.ndarray], float]:
    import torch

    torch.set_num_threads(min(8, os.cpu_count() or 1))
    weights_cfg = cfg["embeddings"]
    weights_path = embed.local_weights_path(weights_cfg)
    model = embed.load_frozen_model(weights_cfg, weights_path, "cpu")
    started = time.perf_counter()
    by_sample: dict[str, np.ndarray] = {}
    for payload in payloads:
        tiles_array = np.asarray(payload["tiles"])
        vectors = []
        for start in range(0, len(tiles_array), 16):
            vectors.append(
                embed.embed_batch(
                    model,
                    list(tiles_array[start : start + 16]),
                    int(weights_cfg["input_px"]),
                    "cpu",
                )
            )
        by_sample[str(payload["sample_id"])] = np.concatenate(vectors, axis=0).astype(
            np.float32, copy=False
        )
    return by_sample, time.perf_counter() - started


def _safe_error(exc: Exception) -> str:
    message = str(exc)
    message = re.sub(r"\b(?:ak|as)-[A-Za-z0-9_-]+\b", "[REDACTED_MODAL_CREDENTIAL]", message)
    message = re.sub(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/-]+", r"\1[REDACTED]", message)
    message = re.sub(
        r"(?i)\b(token|secret|password|authorization)(\s*[:=]\s*)\S+",
        r"\1\2[REDACTED]",
        message,
    )
    return f"{type(exc).__name__}: {message}"


def _embedding_vectors(
    cfg: dict[str, Any],
    payloads: list[dict[str, Any]],
    allow_local_fallback: bool = True,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    modal_attempt_started = time.perf_counter()
    modal_app = None
    try:
        import modal_app
    except Exception:
        modal_app = None

    embedding_error = None
    try:
        if modal_app is None:
            raise RuntimeError("modal_app could not be imported")
        vectors, modal_wall, container_seconds = _embed_on_modal(cfg, payloads, modal_app)
        cost = modal_app._dino_cost(container_seconds)
        backend = "modal_l4"
        local_wall = None
    except Exception as exc:
        embedding_error = _safe_error(exc)
        modal_wall = time.perf_counter() - modal_attempt_started
        if not allow_local_fallback:
            raise SystemExit(
                "heldout: Modal embedding failed; CPU fallback is disabled for a frozen real run: "
                f"{embedding_error}"
            ) from exc
        vectors, local_wall = _embed_local_cpu(cfg, payloads)
        container_seconds = 0.0
        cost = modal_app._dino_cost(0.0) if modal_app is not None else 0.0
        backend = "local_cpu_fallback"

    columns = modal_app.MODAL_RUN_COLUMNS if modal_app is not None else V1_MODAL_RUN_COLUMNS
    _append_modal_run(
        cfg,
        columns,
        wall_s=modal_wall if backend == "modal_l4" else float(local_wall),
        n_inputs=len(payloads),
        hardware="L4" if backend == "modal_l4" else "local-cpu fallback",
        cost=cost,
        exploratory=allow_local_fallback,
        cost_source=(
            modal_app.MODAL_PRICING
            if backend == "modal_l4"
            else "local CPU fallback; no Modal charge"
        ),
    )
    return vectors, {
        "embedding_backend": backend,
        "embedding_error": embedding_error,
        "modal_wall_s": modal_wall,
        "modal_container_s": container_seconds,
        "modal_cost_usd": cost,
    }


def run(
    cfg: dict[str, Any],
    input_dir: str | Path | None = None,
    out_path: str | Path | None = None,
    dryrun: bool = False,
    exploratory: bool = False,
) -> None:
    canonical_output = _canonical_output_path()
    if dryrun and input_dir is None:
        raise SystemExit("heldout: --dryrun requires an explicit --input-dir")

    tag = _exact_tag()
    frozen = _is_frozen_tag()
    if frozen:
        tag = "v1-frozen"
    exploratory_run = bool(dryrun or exploratory)
    configured_heldout = _config.resolve(cfg["data"]["heldout_dir"]).expanduser().resolve()
    source = (
        Path(input_dir).expanduser().resolve()
        if input_dir is not None
        else configured_heldout
    )

    if dryrun:
        if source == configured_heldout:
            raise SystemExit(
                "heldout: dry-run input directory cannot be the configured data/heldout"
            )
        output = _out_path(out_path, False)
        if output.resolve() == canonical_output:
            raise SystemExit("heldout: dry-run output cannot be the canonical heldout.json")
    elif exploratory:
        if not canonical_output.is_file():
            raise SystemExit(
                "heldout: exploratory inference requires canonical results/v1/heldout.json"
            )
        output = _out_path(out_path, True)
        if output.resolve() == canonical_output:
            raise SystemExit("heldout: exploratory output cannot be the canonical heldout.json")
    else:
        output = _out_path(out_path, False)
        if output.resolve() != canonical_output:
            raise SystemExit(
                "heldout: real inference always writes to canonical results/v1/heldout.json"
            )
        output = canonical_output
        _run_once_guard(output, frozen)

    if output.exists():
        raise SystemExit(f"heldout: refusing to overwrite existing output {output}")
    if output.suffix.lower() != ".json":
        raise SystemExit("heldout: output path must be a JSON file")

    if not source.is_dir():
        raise SystemExit(f"heldout: input directory does not exist: {source}")
    groups, file_hashes, discovery_notes = _discover_files(source)
    if not groups:
        raise SystemExit(f"heldout: no images with a BSE TIFF found under {source}")

    train = classify.load_training()
    if dryrun:
        _validate_dryrun_inputs(
            source,
            configured_heldout,
            groups,
            set(train["sample_id"].astype(str)),
            file_hashes,
        )

    feature_cfg, _ = features._feature_config()
    model = classify.final_model(train)
    model_diff = classify.check_frozen_model(model)
    train_xe = train[classify.EMB_COLS].to_numpy(dtype=np.float64)
    train_y = train["batch"].to_numpy(dtype=object)
    train_units = classify.unit(train_xe)
    train_cov_all31, covariate_names = classify.covariate_frame(
        train["sample_id"].tolist(), train["batch"].tolist()
    )
    with (_config.ROOT / "results" / "v1" / "loio_summary.json").open() as stream:
        loio_summary = json.load(stream)
    perm_p = float(loio_summary["permutation_p"])
    loio_k = int(loio_summary["loio_correct"])
    status = classify.feature_status()

    prepared: list[dict[str, Any]] = []
    bse_payloads = []
    for sample_id, files in groups.items():
        channel_data = {
            channel: _prepare_channel(path, sample_id, channel, cfg)
            for channel, path in sorted(files.items())
        }
        bse = channel_data["BSE"]
        if not bse["tiles"]:
            message = f"Skipping {sample_id}: BSE image has no full tiles."
            warnings.warn(message)
            discovery_notes.append(message)
            continue
        feature_values, stitched = _extract_features(bse, cfg, feature_cfg)
        segmentation_evidence = (
            _save_segmentation(output, sample_id, bse["image"], stitched, cfg)
            if exploratory_run else None
        )
        del stitched
        cov_values, cov_notes = _covariate_values(channel_data, files["BSE"], covariate_names)
        channels_present = sorted(files)
        caveats = list(cov_notes)
        if not ({"ETD", "SE"} & set(files)):
            caveats.append("Neither ETD nor SE channel is present.")
        hashes = {
            _file_key(path, _config.ROOT): file_hashes[_file_key(path, _config.ROOT)]
            for path in files.values()
        }
        prepared.append(
            {
                "sample_id": sample_id,
                "feature_values": feature_values,
                "segmentation_evidence": segmentation_evidence,
                "covariate_values": cov_values,
                "caveats": caveats,
                "detectors": channels_present,
                "file_hashes": hashes,
                "n_tiles": len(bse["tiles"]),
            }
        )
        bse_payloads.append(
            {
                "sample_id": sample_id,
                "tiles": np.stack([tile for _, tile in bse["tiles"]]).astype(np.uint8, copy=False),
            }
        )
        del channel_data, bse
    if not prepared:
        raise SystemExit("heldout: no images with usable BSE tiles")

    vectors_by_sample, embedding_info = _embedding_vectors(
        cfg,
        bse_payloads,
        allow_local_fallback=exploratory_run,
    )
    out_rel = _file_key(output, _config.ROOT)
    image_docs = []
    input_rows: dict[str, Any] = {}
    summary_table = []
    for item in prepared:
        sample_id = item["sample_id"]
        tile_vectors = vectors_by_sample[sample_id]
        emb_vec = np.mean(tile_vectors, axis=0, dtype=np.float64).astype(np.float32)
        f_vec = np.asarray(
            [item["feature_values"][column] for column in classify.F_COLS],
            dtype=np.float64,
        )
        pred = classify.predict_one(model, f_vec, emb_vec, status)
        ood_result = classify.ood(classify.unit(emb_vec)[0], train_units, train_y)
        available_names = [name for name in covariate_names if name in item["covariate_values"]]
        evidence = [
            {"file": out_rel, "selector": f"inputs.{sample_id}.covariates"},
            {
                "file": _file_key(groups[sample_id]["BSE"], _config.ROOT),
                "selector": "TIFF metadata",
            },
        ]
        covariate_block = classify.covariate_block(
            item["covariate_values"],
            train_cov_all31,
            available_names,
            evidence,
        )
        document = classify.image_document(
            sample_id=sample_id,
            true_batch=None,
            n_tiles=item["n_tiles"],
            pred=pred,
            ood_res=ood_result,
            perm_p=perm_p,
            loio_k=loio_k,
            loio_n=int(loio_summary["n_images"]),
            covariates=covariate_block,
            detectors=item["detectors"],
            evidence_file=out_rel,
            selector=f"images[subject.id == '{sample_id}']",
            cfg=cfg,
            frozen=frozen,
            exploratory=exploratory_run,
            git_tag=tag,
            kind_note=(
                "heldout_dryrun: training image copied to a temporary folder; its score does not count"
                if dryrun
                else "held-back image"
            ),
        )
        document["subject"]["file_hashes"] = item["file_hashes"]
        document["caveats"].extend(item["caveats"])
        if item["segmentation_evidence"] is not None:
            document["evidence"]["segmentation_mask"] = item["segmentation_evidence"]
        classify.validate(document)
        image_docs.append(document)
        input_rows[sample_id] = {
            **{column: float(item["feature_values"][column]) for column in classify.F_COLS},
            "covariates": item["covariate_values"],
            "BSE_embedding": emb_vec.tolist(),
        }
        summary_table.append(
            {
                "sample_id": sample_id,
                "pred_batch": pred["pred_batch"],
                "confidence": pred["confidence"],
                "tier": document["verdict"]["closed_set"]["tier"],
                "ood_label": ood_result["label"],
                **{
                    f"driver{index + 1}": pred["drivers"][index]["name"]
                    if index < len(pred["drivers"])
                    else None
                    for index in range(3)
                },
            }
        )

    run_info = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": _config.git_sha(),
        "git_tag": tag,
        "config_hash": cfg["_hash"],
        "input_dir": str(source),
        "n_images": len(image_docs),
        "file_hashes": file_hashes,
        "embedding_backend": embedding_info["embedding_backend"],
        "embedding_error": embedding_info["embedding_error"],
        "modal_wall_s": embedding_info["modal_wall_s"],
        "modal_container_s": embedding_info["modal_container_s"],
        "modal_cost_usd": embedding_info["modal_cost_usd"],
        "dryrun": bool(dryrun),
        "frozen": frozen,
        "exploratory": exploratory_run,
        "frozen_model_max_abs_coefficient_diff": model_diff,
        "warnings": discovery_notes,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "run": run_info,
                "images": image_docs,
                "inputs": input_rows,
                "summary_table": summary_table,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    print(
        f"heldout: {len(image_docs)} images; backend={run_info['embedding_backend']}; "
        f"Modal wall={run_info['modal_wall_s']:.2f}s; cost=${run_info['modal_cost_usd']:.6f} "
        f"-> {output}"
    )

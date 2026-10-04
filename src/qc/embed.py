"""Frozen DINOv2 tile embeddings for BSE and co-registered detector channels."""
from __future__ import annotations

import hashlib
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qc import config as _config

INDEX_COLUMNS = ["tile_id", "sample_id", "batch", "channel", "y", "x"]
PHASE_IDENTITY = "stated by Polaron, not image-verified"
WEIGHT_FILENAME = "dinov2_vits14_pretrain.pth"
EMBEDDING_WIDTH = 384
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_weights(weights_cfg: dict[str, Any], destination: Path) -> Path:
    expected = str(weights_cfg["weights_sha256"]).lower()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and _sha256(destination) == expected:
        return destination
    partial = destination.with_suffix(destination.suffix + ".part")
    partial.unlink(missing_ok=True)
    try:
        with urllib.request.urlopen(str(weights_cfg["weights_url"]), timeout=120) as source:
            with partial.open("wb") as target:
                while block := source.read(1024 * 1024):
                    target.write(block)
        actual = _sha256(partial)
        if actual != expected:
            raise ValueError(f"DINOv2 weights SHA-256 mismatch: expected {expected}, got {actual}")
        os.replace(partial, destination)
    finally:
        partial.unlink(missing_ok=True)
    return destination


def local_weights_path(weights_cfg: dict[str, Any]) -> Path:
    cache = Path.home() / ".cache" / "aixscience-weights" / WEIGHT_FILENAME
    return ensure_weights(weights_cfg, cache)


def load_frozen_model(weights_cfg: dict[str, Any], weights_path: Path, device: str):
    import torch

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    model = torch.hub.load(
        f"{weights_cfg['hub_repo']}:{weights_cfg['hub_ref']}",
        str(weights_cfg["backbone"]),
        pretrained=False,
        trust_repo=True,
        skip_validation=True,
    )
    state = torch.load(weights_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    model.eval()
    model.requires_grad_(False)
    return model.to(device)


def preprocess_batch(
    images: list[np.ndarray], input_px: int, device: str
):
    import torch
    from torch.nn import functional as functional

    arrays = np.stack([np.asarray(image) for image in images])
    if arrays.dtype != np.uint8 or arrays.shape[1:] != (1024, 1024):
        raise ValueError("DINOv2 inputs must be uint8 grayscale 1024x1024 tiles")
    batch = torch.from_numpy(arrays).to(device=device, dtype=torch.float32).unsqueeze(1) / 255.0
    batch = batch.expand(-1, 3, -1, -1)
    batch = functional.interpolate(
        batch,
        size=(input_px, input_px),
        mode="bicubic",
        align_corners=False,
        antialias=True,
    )
    mean = torch.tensor(IMAGENET_MEAN, device=device, dtype=torch.float32).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD, device=device, dtype=torch.float32).view(1, 3, 1, 1)
    return (batch - mean) / std


def embed_batch(model, images: list[np.ndarray], input_px: int, device: str) -> np.ndarray:
    import torch

    inputs = preprocess_batch(images, input_px, device)
    with torch.inference_mode():
        features = model.forward_features(inputs)["x_norm_patchtokens"].mean(dim=1)
    result = features.float().cpu().numpy()
    if result.shape != (len(images), EMBEDDING_WIDTH):
        raise ValueError(f"expected {EMBEDDING_WIDTH}-D embeddings, got {result.shape}")
    return result.astype(np.float32, copy=False)


def load_tile_index(cfg: dict[str, Any]) -> pd.DataFrame:
    path = _config.resolve(cfg["data"]["tiles_dir"]) / "index.parquet"
    index = pd.read_parquet(path)
    missing = set(INDEX_COLUMNS + ["path"]) - set(index.columns)
    if missing:
        raise ValueError(f"tile index is missing columns: {sorted(missing)}")
    if index["tile_id"].duplicated().any():
        raise ValueError("tile index contains duplicate tile_id values")
    return index.sort_values("tile_id", kind="stable").reset_index(drop=True)


def image_groups(index: pd.DataFrame) -> list[dict[str, str]]:
    groups = (
        index[["sample_id", "channel"]]
        .drop_duplicates()
        .sort_values(["sample_id", "channel"], kind="stable")
    )
    return [
        {"sample_id": str(row.sample_id), "channel": str(row.channel)}
        for row in groups.itertuples(index=False)
    ]


def embed_image_rows(
    model,
    rows: pd.DataFrame,
    tiles_dir: Path,
    input_px: int,
    device: str,
    batch_size: int = 16,
) -> dict[str, Any]:
    started = time.perf_counter()
    ordered = rows.sort_values("tile_id", kind="stable").reset_index(drop=True)
    tile_vectors = []
    for start in range(0, len(ordered), batch_size):
        batch_rows = ordered.iloc[start:start + batch_size]
        tiles = [np.load(tiles_dir / str(path)) for path in batch_rows["path"]]
        tile_vectors.append(embed_batch(model, tiles, input_px, device))
    vectors = np.concatenate(tile_vectors, axis=0) if tile_vectors else np.empty((0, EMBEDDING_WIDTH), dtype=np.float32)
    return {
        "rows": ordered[INDEX_COLUMNS].to_dict("records"),
        "embeddings": vectors,
        "wall_s": time.perf_counter() - started,
    }


def _embedding_frames(
    cfg: dict[str, Any], index: pd.DataFrame, embeddings: np.ndarray
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = index.sort_values("tile_id", kind="stable").reset_index(drop=True)
    embeddings = np.asarray(embeddings, dtype=np.float32)
    if embeddings.shape != (len(ordered), EMBEDDING_WIDTH):
        raise ValueError(
            f"expected an embedding matrix of shape {(len(ordered), EMBEDDING_WIDTH)}, "
            f"got {embeddings.shape}"
        )
    if ordered["tile_id"].duplicated().any():
        raise ValueError("embedding output contains duplicate tile_id values")

    emb_cfg = cfg["embeddings"]
    provenance = {
        "hub_ref": str(emb_cfg["hub_ref"]),
        "weights_sha256": str(emb_cfg["weights_sha256"]),
        "phase_identity": PHASE_IDENTITY,
    }
    per_tile = _config.stamp(ordered[INDEX_COLUMNS].copy(), cfg)
    for key, value in provenance.items():
        per_tile[key] = value
    per_tile = per_tile[INDEX_COLUMNS + ["config_hash", "git_sha", *provenance]]

    vector_columns = [f"e{index:03d}" for index in range(EMBEDDING_WIDTH)]
    image_rows = []
    for key, positions in ordered.groupby(
        ["sample_id", "batch", "channel"], sort=True
    ).indices.items():
        vector = np.mean(embeddings[positions], axis=0, dtype=np.float64).astype(np.float32)
        image_rows.append(
            {
                "sample_id": key[0],
                "batch": key[1],
                "channel": key[2],
                **dict(zip(vector_columns, vector, strict=True)),
                **provenance,
            }
        )
    per_image = _config.stamp(pd.DataFrame(image_rows), cfg)
    leading = [
        "sample_id", "batch", "channel", "config_hash", "git_sha",
        "hub_ref", "weights_sha256", "phase_identity",
    ]
    per_image = per_image[leading + vector_columns]
    return per_tile, per_image


def write_outputs(cfg: dict[str, Any], index: pd.DataFrame, embeddings: np.ndarray) -> None:
    per_tile, per_image = _embedding_frames(cfg, index, embeddings)
    results_dir = _config.ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    np.save(results_dir / "emb_per_tile.npy", np.asarray(embeddings, dtype=np.float32))
    per_tile.to_parquet(results_dir / "emb_index.parquet", index=False)
    per_image.to_parquet(results_dir / "emb_per_image.parquet", index=False)
    print(
        f"embeddings: {len(per_tile)} tile rows, {len(per_image)} image-channel rows "
        "-> results/emb_per_tile.npy, emb_index.parquet, emb_per_image.parquet"
    )


def _run_local(cfg: dict[str, Any], index: pd.DataFrame, groups: list[dict[str, str]]) -> np.ndarray:
    weights_cfg = cfg["embeddings"]
    weights_path = local_weights_path(weights_cfg)
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(min(8, os.cpu_count() or 1))
    model = load_frozen_model(weights_cfg, weights_path, device)
    tiles_dir = _config.resolve(cfg["data"]["tiles_dir"])
    vectors_by_tile: dict[str, np.ndarray] = {}
    for group in groups:
        rows = index.loc[
            (index["sample_id"].astype(str) == group["sample_id"])
            & (index["channel"].astype(str) == group["channel"])
        ]
        encoded = embed_image_rows(
            model,
            rows,
            tiles_dir,
            int(weights_cfg["input_px"]),
            device,
            batch_size=8 if device == "cpu" else 32,
        )
        for row, vector in zip(encoded["rows"], encoded["embeddings"], strict=True):
            vectors_by_tile[str(row["tile_id"])] = vector
    return np.stack([vectors_by_tile[str(tile_id)] for tile_id in index["tile_id"]]).astype(
        np.float32, copy=False
    )


def run(cfg: dict[str, Any]) -> None:
    """Compute frozen DINOv2 embeddings locally for every indexed image-channel."""
    index = load_tile_index(cfg)
    groups = image_groups(index)
    vectors = _run_local(cfg, index, groups)
    write_outputs(cfg, index, vectors)

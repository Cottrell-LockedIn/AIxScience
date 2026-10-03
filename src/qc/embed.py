"""Frozen DINOv2 ViT-S/14 tile embeddings, pooled per image and detector channel (embed). Owner: P3.

Usage: python -m qc embed [--channels BSE,Inlens,ETD,SE] [--batch-size 32]

Frozen, non-trained baseline required by docs/FRAMEWORK.md Section 12 before any training. The model is
`facebookresearch/dinov2` at a pinned commit (Apache-2.0), loaded via torch.hub; weights are the public
`dinov2_vits14_pretrain.pth`. Each 1024 px tile (uint8 BSE / SE grey) is resized to 224 px, replicated to 3
channels, ImageNet-normalised, and the CLS token (384-d) is taken. Tiles are mean-pooled per (image, channel).

Reads:  data/tiles/index.parquet and the .npy tiles it lists
Writes: results/embeddings/dinov2_vits14_<channel>_by_image.parquet   one row per image: sample_id, batch, E000..E383
        results/embeddings/dinov2_vits14_setype_by_image.parquet       ETD and SE pooled as one "SE-type" channel
        results/embeddings/EMBED.md                                     provenance and timing
Per-tile vectors are written to data/embeddings/ (not committed; regenerable in ~2 min on 8 CPU cores).

Rules: the image is the unit (tiles are pooled before any statistic); embeddings are features, never a verdict; a
batch separation on embeddings is reported with its driver type `embedding` and is not a material claim until the
acquisition-covariate check (`qc classify`, family `<name>+acquisition`) has been run.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from qc import config as _config

HUB_REPO = "facebookresearch/dinov2"
HUB_COMMIT = "7764ea0f912e"  # pinned 2026-10-03
MODEL = "dinov2_vits14"
DIM = 384
SIDE = 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
SE_TYPE = ("ETD", "SE")


def preprocess(tile: np.ndarray, side: int = SIDE) -> np.ndarray:
    """uint8 (H, W) grey tile -> float32 (3, side, side), area-downsampled, ImageNet-normalised."""
    import torch
    import torch.nn.functional as F
    t = torch.from_numpy(np.ascontiguousarray(tile)).float()[None, None] / 255.0
    t = F.interpolate(t, size=(side, side), mode="area")[0, 0].numpy()
    x = np.repeat(t[None], 3, axis=0)
    return ((x - MEAN[:, None, None]) / STD[:, None, None]).astype(np.float32)


def load_model():
    import torch
    torch.hub.set_dir(str(Path.home() / ".cache" / "torch" / "hub"))
    m = torch.hub.load(f"{HUB_REPO}:{HUB_COMMIT}", MODEL, trust_repo=True, skip_validation=True)
    return m.eval()


def embed_tiles(model, tiles: Iterable[np.ndarray], batch_size: int = 32) -> np.ndarray:
    import torch
    out = []
    buf: list[np.ndarray] = []

    def flush() -> None:
        if buf:
            with torch.no_grad():
                out.append(model(torch.from_numpy(np.stack(buf))).cpu().numpy())
            buf.clear()

    for t in tiles:
        buf.append(preprocess(t))
        if len(buf) == batch_size:
            flush()
    flush()
    return np.concatenate(out) if out else np.empty((0, DIM), np.float32)


def pool_by_image(index: pd.DataFrame, vectors: np.ndarray, channels: Iterable[str]) -> pd.DataFrame:
    """Mean over tiles of the given channel(s) per image; one row per sample_id with E000..E{DIM-1}."""
    sel = index["channel"].isin(list(channels)).to_numpy()
    sub = index.loc[sel, ["sample_id", "batch"]].reset_index(drop=True)
    V = vectors[sel]
    rows = []
    for (sid, batch), g in sub.groupby(["sample_id", "batch"], sort=True):
        rows.append({"sample_id": sid, "batch": batch, "n_tiles": len(g),
                     **{f"E{j:03d}": float(v) for j, v in enumerate(V[g.index].mean(axis=0))}})
    return pd.DataFrame(rows)


def run(cfg: dict[str, Any], channels: str = "BSE,Inlens,ETD,SE", batch_size: int = 32,
        index_path: str = "data/tiles/index.parquet", tile_root: str = "data/tiles",
        out: str = "results/embeddings", cache: str = "data/embeddings") -> Path:
    import torch
    torch.set_num_threads(max(1, torch.get_num_threads()))
    idx = pd.read_parquet(_config.resolve(index_path))
    if (idx["config_hash"] != cfg["_hash"]).any():
        raise ValueError(f"tile index config_hash {idx['config_hash'].unique()} != current {cfg['_hash']}; rerun qc tiles")
    chans = [c.strip() for c in channels.split(",") if c.strip()]
    idx = idx[idx["channel"].isin(chans)].reset_index(drop=True)
    root = _config.resolve(tile_root)
    out_dir, cache_dir = _config.resolve(out), _config.resolve(cache)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    model = load_model()
    t_load = time.time() - t0
    t0 = time.time()
    V = embed_tiles(model, (np.load(root / p) for p in idx["path"]), batch_size)
    t_embed = time.time() - t0
    per_tile = pd.concat([idx[["tile_id", "sample_id", "batch", "channel"]],
                          pd.DataFrame(V, columns=[f"E{j:03d}" for j in range(DIM)])], axis=1)
    _config.stamp(per_tile, cfg).to_parquet(cache_dir / f"{MODEL}_by_tile.parquet", index=False)
    written = []
    for name, cs in [(c, (c,)) for c in chans] + [("setype", SE_TYPE)]:
        if not idx["channel"].isin(cs).any():
            continue
        tab = pool_by_image(idx, V, cs)
        p = out_dir / f"{MODEL}_{name.lower()}_by_image.parquet"
        _config.stamp(tab, cfg).to_parquet(p, index=False)
        written.append((name, len(tab), int(tab["n_tiles"].sum()), p.name))
    lines = [f"# Frozen embeddings: {MODEL} ({HUB_REPO}@{HUB_COMMIT})", "",
             f"Provenance: {', '.join(f'{k}={v}' for k, v in _config.provenance(cfg).items())}", "",
             f"Tiles embedded: {len(idx)} ({SIDE} px area-resize of 1024 px tiles, CLS token, {DIM}-d). "
             f"Model load {t_load:.1f} s; embedding {t_embed:.1f} s on CPU ({torch.get_num_threads()} threads, batch {batch_size}).", "",
             "| table | images | tiles pooled | file |", "|---|---|---|---|",
             *[f"| {n} | {ni} | {nt} | `{f}` |" for n, ni, nt, f in written], "",
             "Mean-pooled per (image, channel); the image is the unit. Use with `qc classify --features <file> --table-family embedding`.",
             "Per-tile vectors: `data/embeddings/` (not committed)."]
    (out_dir / "EMBED.md").write_text("\n".join(lines) + "\n")
    print(f"embed: {len(idx)} tiles in {t_embed:.0f} s -> {out_dir.relative_to(_config.ROOT)}/ ({len(written)} image tables)", file=sys.stderr)
    return out_dir

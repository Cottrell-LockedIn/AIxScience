import numpy as np
import pandas as pd
import tifffile

from qc import config as _config
from qc import tiles


def _cfg(tmp_path):
    cfg = _config.load("configs/v1.yaml")
    cfg["data"]["raw_dir"] = str(tmp_path / "raw")
    cfg["data"]["tiles_dir"] = str(tmp_path / "tiles")
    return cfg


def test_grid_has_no_partial_tiles():
    h, w, t, s = 2300, 6984, 1024, 512
    grid = tiles.tile_grid(h, w, t, s)
    assert grid, "grid should not be empty"
    assert all(y + t <= h and x + t <= w for y, x in grid)
    assert len(grid) == ((h - t) // s + 1) * ((w - t) // s + 1)
    assert tiles.tile_grid(500, 500, 1024, 512) == []


def test_index_round_trip(tmp_path):
    cfg = _cfg(tmp_path)
    cfg["tiling"].update(tile_px=64, stride_px=32)
    cfg["data"]["border_crop_px"] = 8
    rng = np.random.default_rng(0)
    raw = tmp_path / "raw" / "Batch_9"
    raw.mkdir(parents=True)
    img = rng.integers(0, 255, size=(150, 300), dtype=np.uint8)
    tifffile.imwrite(raw / "img_abcd1234_BSE.tif", np.stack([img] * 3, axis=-1))

    tiles_dir = tmp_path / "tiles"
    index = tiles.build_index(tmp_path / "raw", tiles_dir, cfg, workers=1)
    index.to_parquet(tiles_dir / "index.parquet", index=False)
    back = pd.read_parquet(tiles_dir / "index.parquet")

    cropped = img[8:-8, 8:-8]
    assert len(back) == len(tiles.tile_grid(*cropped.shape, 64, 32))
    assert set(back.columns) >= {"tile_id", "sample_id", "batch", "channel", "y", "x", "h", "w", "config_hash", "git_sha"}
    assert (back["sample_id"] == "abcd1234").all() and (back["batch"] == "Batch_9").all()
    for _, r in back.iterrows():
        arr = tiles.load_tile(r, tiles_dir)
        assert arr.shape == (64, 64) and arr.dtype == np.uint8
        assert np.array_equal(arr, cropped[r.y:r.y + 64, r.x:r.x + 64])
    assert (tiles_dir / "previews" / "Batch_9_abcd1234_BSE.png").exists()

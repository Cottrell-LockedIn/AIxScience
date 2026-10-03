"""Embedding plumbing without downloading the model: preprocessing shape/normalisation, batching, image pooling."""
import numpy as np
import pandas as pd

from qc import embed


class _Fake:
    """Stands in for DINOv2: returns the per-sample mean of the first channel as a DIM-d vector."""
    def __call__(self, x):
        import torch
        return x[:, 0].mean(dim=(1, 2))[:, None].repeat(1, embed.DIM)


def test_preprocess_shape_and_normalisation():
    tile = np.full((1024, 1024), 255, np.uint8)
    x = embed.preprocess(tile)
    assert x.shape == (3, embed.SIDE, embed.SIDE) and x.dtype == np.float32
    np.testing.assert_allclose(x[:, 0, 0], (1 - embed.MEAN) / embed.STD, rtol=1e-5)


def test_embed_tiles_batches_and_pool_by_image():
    rng = np.random.default_rng(0)
    tiles = [np.full((64, 64), v, np.uint8) for v in (0, 128, 255, 64, 192)]
    V = embed.embed_tiles(_Fake(), tiles, batch_size=2)
    assert V.shape == (5, embed.DIM)
    assert V[2, 0] > V[1, 0] > V[0, 0]
    idx = pd.DataFrame({"tile_id": list("abcde"), "sample_id": ["s1", "s1", "s2", "s2", "s2"],
                        "batch": ["Batch_1"] * 2 + ["Batch_3"] * 3, "channel": ["BSE", "BSE", "BSE", "ETD", "SE"]})
    bse = embed.pool_by_image(idx, V, ["BSE"])
    assert list(bse["sample_id"]) == ["s1", "s2"] and list(bse["n_tiles"]) == [2, 1]
    np.testing.assert_allclose(bse.loc[0, "E000"], V[:2, 0].mean())
    se = embed.pool_by_image(idx, V, embed.SE_TYPE)
    assert list(se["sample_id"]) == ["s2"] and se.loc[0, "n_tiles"] == 2

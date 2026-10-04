import numpy as np
import pytest

from qc.embed import _embedding_frames, preprocess_batch


def test_dinov2_preprocessing_resizes_gray_tiles_and_normalizes():
    image = np.full((1024, 1024), 128, dtype=np.uint8)

    tensor = preprocess_batch([image], input_px=518, device="cpu")

    assert tuple(tensor.shape) == (1, 3, 518, 518)
    expected = (128 / 255 - 0.485) / 0.229
    assert float(tensor[0, 0, 0, 0]) == pytest.approx(expected, abs=1e-5)


def test_embedding_frames_keep_tile_order_and_image_channel_means():
    import pandas as pd

    index = pd.DataFrame(
        [
            {
                "tile_id": "sample_BSE_00000_00512",
                "sample_id": "sample",
                "batch": "Batch_1",
                "channel": "BSE",
                "y": 0,
                "x": 512,
            },
            {
                "tile_id": "sample_BSE_00000_00000",
                "sample_id": "sample",
                "batch": "Batch_1",
                "channel": "BSE",
                "y": 0,
                "x": 0,
            },
        ]
    )
    embeddings = np.zeros((2, 384), dtype=np.float32)
    embeddings[0, 0] = 2
    embeddings[1, 0] = 4

    per_tile, per_image = _embedding_frames(
        {
            "_hash": "config123",
            "embeddings": {"hub_ref": "abcdef", "weights_sha256": "123456"},
        },
        index,
        embeddings,
    )

    assert per_tile["tile_id"].tolist() == [
        "sample_BSE_00000_00000",
        "sample_BSE_00000_00512",
    ]
    assert per_tile["channel"].tolist() == ["BSE", "BSE"]
    assert per_tile["phase_identity"].unique().tolist() == [
        "stated by Polaron, not image-verified"
    ]
    assert len(per_image) == 1
    assert per_image.iloc[0]["channel"] == "BSE"
    assert per_image.iloc[0]["e000"] == pytest.approx(3.0)
    assert per_image.iloc[0]["config_hash"] == "config123"

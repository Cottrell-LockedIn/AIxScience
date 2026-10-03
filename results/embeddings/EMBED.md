# Frozen embeddings: dinov2_vits14 (facebookresearch/dinov2@7764ea0f912e)

Provenance: config_path=configs/v1.yaml, config_hash=de199d6c8d69, git_sha=d4d035c

Tiles embedded: 4329 (224 px area-resize of 1024 px tiles, CLS token, 384-d). Model load 0.7 s; embedding 81.8 s on CPU (8 threads, batch 32).

| table | images | tiles pooled | file |
|---|---|---|---|
| BSE | 31 | 1443 | `dinov2_vits14_bse_by_image.parquet` |
| Inlens | 31 | 1443 | `dinov2_vits14_inlens_by_image.parquet` |
| ETD | 27 | 1235 | `dinov2_vits14_etd_by_image.parquet` |
| SE | 4 | 208 | `dinov2_vits14_se_by_image.parquet` |
| setype | 31 | 1443 | `dinov2_vits14_setype_by_image.parquet` |

Mean-pooled per (image, channel); the image is the unit. Use with `qc classify --features <file> --table-family embedding`.
Per-tile vectors: `data/embeddings/` (not committed).

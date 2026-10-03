# Handoff brief: cloud session 1 (v1 reality check)

Written at T+6h by the local Devin session. Approved by Alvin. You are continuing that session's work in Devin Cloud.

## Read first (in this order, ~10 min)

1. `AGENTS.md` (rules; the hard rules in `docs/FRAMEWORK.md` Section 00 are binding)
2. `docs/FRAMEWORK.md` Sections 00, 0, 2b, 4 (Phase A and B), 13.2
3. `docs/READ/Dataset First Look.md`
4. `configs/v1.yaml`, `src/qc/*.py` docstrings, `schema/verdict.schema.json`

## Your task: steps 1 to 5 of the first sprint

Produce v1 up to the reality-check figure. Stop after step 5 and report.

| # | Stage | Build | Output files |
|---|---|---|---|
| 1 | S1 audit | `python scripts/download_drive.py` (all channels, ~1.7 GB); implement `src/qc/audit.py`: per image shape, dtype, channel set, resolution tag, sha256, duplicates, missing channels | `data/raw/inventory.csv` (git-ignored), `results/audit/images.csv`, `docs/DATA_AUDIT.md` |
| 2 | S2 tiles | implement `src/qc/tiles.py`: read channel 0, crop 8 px borders, 1024 px tiles at stride 512, drop partial tiles; write tiles as uint8 `.npy` under `data/tiles/` and `data/tiles/index.parquet` (tile_id, sample_id, batch, channel, y, x, h, w); 4x downsampled PNG preview per image | `data/tiles/**` (git-ignored), `data/tiles/index.parquet` (git-ignored; commit a 20-row sample to `results/audit/index_sample.csv`) |
| 3 | S3 artefacts | implement `src/qc/artefacts.py`: per tile and per image: curtaining_score (power in a +/-3 px band around the vertical spatial-frequency axis above 0.02 cycles/px, divided by total power in that band of radii), edge_charging (mean of outer 5 % frame band minus centre mean, Inlens), noise_sigma (MAD of Laplacian), sharpness (Laplacian variance), mean, std, p01, p99, detector name | `results/artefacts_per_tile.parquet`, `results/artefacts_per_image.parquet`, `results/audit/artefacts_by_batch.png` |
| 4 | S4 segment + kpi | implement `src/qc/segment.py` and `src/qc/kpi.py` on the BSE channel: median 5 px denoise, `skimage.filters.threshold_multiotsu(classes=3)` per tile, remove objects < 20 px, fill holes; masks saved as PNG (0, 1, 2; do not name phases); thresholds logged per tile; KPIs per tile and per image: fraction of each class, class-2 particle count density and equivalent-diameter distribution (median, p90), class-0 region size; recompute fractions with thresholds scaled by +/-10 % | `data/tiles/masks/**` (git-ignored), `results/thresholds_per_tile.parquet`, `results/kpi_per_tile.parquet`, `results/kpi_per_image.parquet`, `results/kpi_sensitivity.parquet`, 6 example mask overlays (2 per batch) under `results/audit/overlays/` |
| 5 | Reality-check figure | one figure: per-image fractions of class 0, 1, 2 (three panels), x = image, colour = batch, horizontal line = batch median, error bar = +/-10 % threshold sensitivity; plus a second figure of per-image curtaining_score and edge_charging by batch | `results/audit/reality_check_fractions.png`, `results/audit/reality_check_artefacts.png`, `results/audit/REALITY_CHECK.md` (what the figures show, in 10 lines, no chemistry names, no verdicts) |

## Rules that apply to every step

- The image (8-char sample id) is the independent unit. Never aggregate across images without keeping the image id. Never split tiles of one image across anything.
- Class names are 0, 1, 2. In text say "dark class / mid class / bright class" or "pore / graphite / high-Z particle phase (unconfirmed)". Never "silicon".
- Units are pixels. Pixel size 25 nm is unconfirmed; mention it as unconfirmed if you convert anything.
- Artefact scores are measured; images are not modified for KPIs.
- Every result file includes `config_hash` and `git_sha` (use `qc.config.load` and the CLI banner).
- Write unit tests for `tiles` (index round-trip, no partial tiles) and `segment` (3 classes on `skimage.data.binary_blobs`-style synthetic input). `pytest` must pass.
- Commit on branch `stage/s1-s5-reality-check`, open a PR to `main` titled "v1 S1-S5 reality check", include the two figures in the PR description. Do not merge.
- No raw data, tiles, masks, or `.npy` in Git. Check `git status` before each commit.
- Budget: this is CPU-only. Do not use Modal in this session. If a step exceeds 45 min, commit what exists and write what blocked you in `results/audit/REALITY_CHECK.md`.

## Report back (in the PR description and as your final message)

1. Images per batch and channel set per image (table).
2. Whether the resolution tag is consistent across all images.
3. The two figures, and in two sentences each: do batches separate on any class fraction relative to within-batch spread; do artefact scores differ by batch.
4. Anything that contradicts `docs/READ/Dataset First Look.md`.
5. Wall time per stage.

Do not proceed to embeddings (S5), statistics (S6), classifier (S7) or the verdict (S8). Those are assigned to separate sessions once this PR is reviewed.

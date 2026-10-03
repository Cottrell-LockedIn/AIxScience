# PHASE_A_CHECK — FRAMEWORK Phase A + HANDOFF_BRIEF steps 1-5 (report only)

Repo `Cottrell-LockedIn/AIxScience`, branch `stage/s1-s5-reality-check` (PR #1), HEAD `d4d035c`. Checked 2026-10-03, 8-core CPU. Nothing tracked was edited (`git status` in the repo is clean); every re-run went into a scratch clone `~/scratch_aix` (same HEAD, `PYTHONPATH=~/scratch_aix/src`, `data/raw` symlinked). Committed `results/` were copied to `/tmp/committed/results` first and compared afterwards.

Levels: **L0** code exists, not a stub · **L1** I re-ran it on the real data and it completed · **L2** my regenerated output matches the committed file numerically (config hash and git SHA checked) · **L3** numbers quoted in docs match the file exactly.

Provenance: every committed S1-S5 file has `config_hash = de199d6c8d69` and `git_sha = f1ea178`. My regenerated files have `de199d6c8d69` / `d4d035c`. `git diff f1ea178 d4d035c` is empty for `src/qc/{audit,tiles,artefacts,segment,kpi,config}.py`, `configs/v1.yaml` and `scripts/reality_check.py`, so the code is the same and only the SHA stamp differs.

Data: `python scripts/download_drive.py` completed (93 files, 1.7 GB, `data/raw/inventory.csv` 93 rows).

## Re-run summary (scratch, OMP_NUM_THREADS=1)

| stage | completed | wall (mine) | wall in REALITY_CHECK.md:13 |
|---|---|---|---|
| `qc audit` | **first run FAILED** (`ImportError: tabulate` in `write_markdown`); passed after `uv pip install tabulate` | 11.4 s | 12 s |
| `qc tiles` | yes, 4329 tiles, 39-52 per image/channel | 21.4 s | 16 s |
| `qc artefacts` | yes, 4329 tiles, 93 image x channel rows | 77.6 s | 57 s |
| `qc segment` | yes, 1443 BSE tiles | 113.1 s | 75 s |
| `qc kpi` | yes, 1443 tiles, 31 images, 6 overlays | 118.6 s | 89 s |
| `scripts/reality_check.py` | yes | 2.4 s | 1 s |
| `qc register` (for the same-FOV check) | yes, 31/31 registered | 24.9 s | n/a |

My wall times are not comparable one to one: two other jobs were running at the same time.

## Numeric comparison: regenerated vs committed (L2)

| file | rows (committed / regen) | max abs diff over numeric columns | other differences |
|---|---|---|---|
| `results/audit/files.csv` | 93 / 93 | 0 | `sha256_matches_inventory` for `img_xgj4xftb_Inlens.tif`: committed NaN, regen True (the inventory now has 93 rows). All 93 sha256 and pixel_sha256 identical |
| `results/audit/images.csv` | 31 / 31 | 0 | none (the apparent sha256_ETD/SE string differences are NaN on both sides, 4 + 27) |
| `results/audit/index_sample.csv` | 20 / 20 | 0 | none |
| `results/artefacts_per_tile.parquet` | 4329 / 4329 | 0 | none |
| `results/artefacts_per_image.parquet` | 93 / 93 | 0 | none |
| `results/thresholds_per_tile.parquet` | 1443 / 1443 | 0 | none |
| `results/kpi_per_tile.parquet` | 1443 / 1443 | 0 | none |
| `results/kpi_per_image.parquet` | 31 / 31 | 0 | none |
| `results/kpi_sensitivity.parquet` | 4422 / 4422 | 0 | none |
| `docs/DATA_AUDIT.md` | — | body identical (diff from line 4 on is empty) | only the timestamp and git line (line 3) differ |
| `results/audit/reality_check_fractions.png`, `reality_check_artefacts.png`, `artefacts_by_batch.png`, 6 × `overlays/*.png` | — | 0 differing pixels in each of the 9 PNGs | same 6 overlay filenames |
| `results/registration/registration_by_image.csv`, `registration_windows.csv` | 93 / 93, 744 / 744 | 0 | committed git_sha `20e3371` |

## Item table

| # | item | requirement (source) | level | evidence path | defect, if any | what closes it |
|---|---|---|---|---|---|---|
| A1 | S1 inventory | 93 files / 31 stems / 7-7-17 (brief step 1) | **L3** | `results/audit/files.csv` (93 rows), `images.csv` (31; Batch_1 7, Batch_2 7, Batch_3 17); `docs/DATA_AUDIT.md` per-batch table | — | — |
| A2 | channel sets | channel set per image, missing channels | **L3** | images.csv: BSE+ETD+Inlens 7/6/14, BSE+Inlens+SE 0/1/3; missing 0 | — | — |
| A3 | shape, dtype, sha256, duplicates | brief step 1 | **L2** | files.csv: w 6960-7000, h 1612-2316, uint8, LZW; 0 byte-duplicates and 0 pixel-duplicates; sha256 92/92 match the inventory in the committed file (93/93 now) | — | — |
| A4 | resolution tag | consistency (brief step 1, Report back 2) | **L2** (L3: see the mismatch list) | 13 distinct `XResolution` values; nm/px-if-true 24.99920 to 25.00055; the only TIFF tags are the tifffile ones (`Software=tifffile.py`, `ImageDescription={"shape":...}`) | the docs say "all round to 25.000 nm/px", but at 3 dp they round to 24.999 / 25.000 / 25.001 | change the wording to "all within 25.000 ± 0.001 nm/px" |
| A5 | other metadata (pixel size, voltage, detector) | FRAMEWORK Phase A bullet 1 | **L1** | one BSE TIFF tag dump: only baseline tifffile tags; no voltage or detector metadata | — (absence verified) | ask Polaron, as already listed in `docs/READ/Questions for Polaron.md` |
| A6 | `data/raw/inventory.csv`, `docs/DATA_AUDIT.md` produced | brief step 1 outputs | **L1** | both produced in scratch | **`qc audit` crashes on a fresh `uv pip install -e .`**: `tabulate` is only in `requirements.txt:5`, not in `pyproject.toml`; `files.csv`/`images.csv` are written, then `DATA_AUDIT.md` fails | add `tabulate>=0.9` to the pyproject dependencies |
| A7 | DATA_AUDIT facts vs current answers | phase names recorded with Polaron provenance (brief step 4); Batch_3 = baseline; same-FOV | **L0 — FAIL** | `docs/DATA_AUDIT.md:76` still says "Identity of the bright class on BSE (no EDS); class names stay 0 / 1 / 2", `:77` "Whether a reference batch is designated" (both under "Unconfirmed facts"); no mention of silicon/graphite/void provenance or of registration | stale on all three facts. The text is hard-coded in `src/qc/audit.py` `write_markdown`, so a hand edit to DATA_AUDIT.md would be overwritten by the next `qc audit` run | update the template in `audit.py`: phase identity "stated by Polaron, not image-verified" (class 2 = silicon, 1 = graphite, 0 = void); Batch_3 = supplier baseline (Polaron clarification); "31/31 pixel-registered, see `results/registration/REGISTRATION.md`". Also `configs/v1.yaml:49` `reference_batch: auto` gives Batch_3 only because it has the most images; set it explicitly (this changes the config hash) |
| A8 | same-FOV across detectors | the DATA_AUDIT claim the owner asked about | **L2** | regenerated `results/registration/*` identical to committed (0 diff); 31/31 registered, max abs median shift 0.10 px, min window PSR 57.4 | not in DATA_AUDIT.md (see A7). Committed `registration_*.csv` git_sha `20e3371` is read back by pandas as float `inf` (scientific notation) | quote git_sha as a string (or `dtype={'git_sha': str}` on read) |
| B1 | 8 px crop, channel 0 | brief step 2 | **L2** | `tiles.crop_border`, `read_gray`; crop applied before tiling; RGB channels differ outside the 8 px border in 0 files (my scan) | — | — |
| B2 | 1024 tiles, stride 512, no partial tiles | brief step 2 | **L2** | index: h = w = 1024 for all 4329; 0 tiles extend past the image; my count from `tile_grid` on the 31 cropped shapes is 1443 per channel × 3 = 4329 = committed | **deviation**: 1449/4329 tiles are edge-anchored (not on the 512 stride grid; they overlap their neighbour by more than 50 %). This is documented (review fix, REALITY_CHECK.md:5, :14) but differs from the literal "stride 512" | accept and keep it documented, or report a stride-only sensitivity check (2880 tiles) |
| B3 | index columns, uint8 `.npy`, 4x previews, 20-row sample | brief step 2 | **L1/L2** | index has tile_id, sample_id, batch, channel, y, x, h, w (+ img_h, img_w, path, hash, sha); tiles uint8 1024×1024; 93 previews (e.g. 1745×575); `index_sample.csv` 20 rows, identical | FRAMEWORK says 2048-px previews; the brief (4x) takes precedence | — |
| B4 | unit tests | tiles (round-trip, no partial), segment (3 classes on synthetic) | **L1** | `tests/test_tiles.py` (no partial, full coverage, round-trip), `tests/test_segment.py` (3-class disks with >97 % agreement, small objects, fallback, stale join). `python -m pytest -q` passes 43; `pytest -q --ignore=tests/test_classify.py` passes 38 | **plain `pytest -q` (the command in the brief) fails at collection**: `tests/test_classify.py:8 from tests.test_validate import synthetic`, and there is no `tests/__init__.py` | add an empty `tests/__init__.py` or a conftest/pythonpath setting (this belongs to the classify PR, but it breaks the "pytest must pass" rule) |
| C1 | curtaining_score definition | "power in a ±3 px band around the vertical spatial-frequency axis above 0.02 cycles/px ÷ total power in that band of radii" | **L2** (code read) | `artefacts.stripe_scores`: band ±3 bins, `r > 0.02`, ÷ power over the same annulus ✓ | **deviation**: the band is around the **k_y = 0 line (the horizontal frequency axis)**, reinterpreted as "the axis that carries vertical-stripe energy"; the literal "vertical axis" (k_x ≈ 0) band is reported as `hstripe_score`. Also adds a Hann window (not in the brief). Documented in the docstring and the PR text; not in REALITY_CHECK.md | have the owner pick the reading; state it in REALITY_CHECK.md |
| C2 | edge_charging | outer 5 % frame band mean − centre mean, Inlens | **L2** | `artefacts.edge_charging` per tile, band = round(0.05 × 1024) = 51 px; all channels; the Inlens panel is plotted | **interpretation risk**: the per-image value is the mean of per-tile values (tile border vs tile centre), **not the outer 5 % band of the whole field of view**, so it does not measure edge charging at the FOV edge | add an image-level frame-band metric, or rename it as within-tile |
| C3 | noise_sigma, sharpness, mean/std/p01/p99, detector | brief step 3 | **L2** | noise = 1.4826·MAD(Laplacian) (the scale factor is extra; harmless), sharpness = var(Laplacian), the other stats plus `detector` column ✓ | — | — |
| C4 | artefacts outputs | per tile, per image, `artefacts_by_batch.png` | **L2** | 4329 / 93 rows identical; PNG 0 px diff | — | — |
| D1 | segmentation recipe | median 5 px, multi-Otsu classes=3 per tile, remove < 20 px, fill holes | **L2** | `segment.denoise` (`ndimage.median_filter size=5`) ✓; `threshold_multiotsu(classes=3)` per tile ✓; `remove_small_objects(max_size=19)` on skimage 0.26 ✓ (< 20 px) | **deviation**: "fill holes" is implemented as `remove_small_holes(max_size=19)`, i.e. only holes < 20 px are filled, on classes 0 and 2 only. The reason is given in the PR text ("a full hole fill would swallow bright particles") | accept and document it in REALITY_CHECK.md / DATA_AUDIT, or implement the literal rule |
| D2 | masks PNG 0/1/2, thresholds logged | brief step 4 | **L1/L2** | 1443 mask PNGs, values {0, 1, 2}; `thresholds_per_tile.parquet` identical, 0 fallback tiles | masks are written to `data/masks/` rather than the `data/tiles/masks/` the brief names (git-ignored either way) | cosmetic |
| D3 | KPIs | void/graphite/silicon fractions, class-2 count density, eq-diameter median/p90, void region size; per tile and per image | **L2** | `kpi.kpis`: frac_c0/1/2, c2_count_density_per_Mpx, c2_eqdiam_median/p90_px, c0_region_eqdiam_median_px, c0_region_area_mean_px; identical | — | — |
| D4 | ±10 % sensitivity | fractions recomputed with thresholds ×0.9/×1.1 | **L2** | `kpi._work` rescales both thresholds and relabels with the same cleaning; 4422 rows identical | — | — |
| D5 | 6 overlays (2 per batch) | brief step 4 | **L2** | 6 PNGs, 0 px diff, 2 per batch | overlays label "class 0 (dark) / class 2 (bright)" with no Polaron provenance; the Batch_1 4ih2ggld tile (t = 32, 66) shows class 2 outlining flake edges and binder, not discrete particles | add the provenance tag; use it as evidence for the S4 challenger |
| E1 | fractions figure | 3 panels, x = image, colour = batch, batch median line, ±10 % error bars | **L2** | `reality_check_fractions.png` 0 px diff; inspected: 3 panels, 31 images, dashed medians, error bars from ×0.9/×1.1 ✓ | — | — |
| E2 | artefacts figure | curtaining_score and edge_charging by batch | **L2** | `reality_check_artefacts.png` 0 px diff; BSE curtaining + Inlens edge_charging ✓ | — | — |
| E3 | REALITY_CHECK.md | ≤ 10 lines, what the figures show, no verdicts; numbers match | **L3 with 3 mismatches** | `results/audit/REALITY_CHECK.md`; see L3 table | stale header hash; 1 count wrong; 1 rounding claim wrong (mismatch list) | fix the header to `de199d6c8d69` / `f1ea178`; 20 → 21; reword the 25.000 claim |
| R1 | image is the unit | rule | **L2** | all per-image tables keyed by sample_id; n_tiles kept; no splits in S1-S5 | — | — |
| R2 | class naming in text with Polaron provenance | rule | **L0 — partial** | REALITY_CHECK.md and the figures use only "class 0/1/2 (dark/mid/bright)" | allowed (class number kept), but the updated rule wants the name plus the provenance tag in text; DATA_AUDIT.md has neither (A7) | add "void / graphite / silicon (stated by Polaron, not image-verified)" |
| R3 | units px; 25 nm unconfirmed | rule | **L0 ✓** | all KPI columns in `_px`; DATA_AUDIT.md says "pixel size is unconfirmed" | — | — |
| R4 | artefacts measured, not removed | rule | **L0 ✓** | KPIs are computed on raw tiles; artefacts are covariates only | — | — |
| R5 | config_hash + git_sha in every result file | rule | **L2 ✓** | all 9 S1-S5 files plus `data/tiles/index.parquet` | git_sha strings such as `20e3371` read back as `inf` from CSV (A8) | as A8 |
| R6 | no raw data in git | rule | **L1 ✓** | `git ls-files` lists no `.npy`/`.tif` files and nothing under `data/` | — | — |
| R7 | PR titled "v1 S1-S5 reality check", figures in the description, not merged | rule | **L1 — partial** | PR #1 is open, not merged, both figures embedded | the title is now "v1 S1-S5 reality check + pre-registered features, validation harness, evidence base, failure-mode rulebook, detector checks"; the PR has grown far past steps 1-5, which the brief said not to do | owner's call |
| R8 | CPU only, 45-min cap | rule | **L1 ✓** | the whole chain runs on CPU in about 6 min | — | — |
| RB | Report back items 1-5 | brief | **L3 (with the E3 mismatches)** | PR #1 "Report back" section plus REALITY_CHECK.md items 1, 2, 6, 8, 9 | the PR repeats "all of which round to 25.000 nm/px (24.999–25.001)", which contradicts itself | as E3 |
| PA1 | inventory | FRAMEWORK Phase A bullet 1 | **L2** | as A1-A5 | — | — |
| PA2 | tiling | Phase A bullet 2 (512 px, stride = tile, databars) | **L2** | the brief overrides to 1024/512; no databar per `docs/READ/Dataset First Look.md:23` | this departs from FRAMEWORK and is recorded in the PR ("Doc discrepancy") | — |
| PA3 | artefact covariates | Phase A bullet 3 | **L2** | as C1-C4 | as C1/C2 | as C1/C2 |
| PA4 | **look at 10 tiles per batch at full resolution; write what a materials scientist would measure; decide whether thresholding separates pore / particle / crack** | Phase A bullet 4 | **NOT DONE (no artefact)** | `grep` over docs/ and results/ finds no note; the only visual record is 6 overlays (2 per batch, not 10). REALITY_CHECK.md:9 covers part of the thresholding question | missing deliverable | a 30-tile contact sheet (10 per batch, full-res crops), a written note, and an explicit pore/particle/crack decision |
| PA5 | **Gate: covariate table plotted by batch; state whether batches separate on covariates** | Phase A gate | **L3 ✓ (in REALITY_CHECK, not in the audit)** | `artefacts_by_batch.png` (6 panels) and REALITY_CHECK.md:10-11: no separation on curtaining/edge_charging; noise and sharpness do separate (3.2x / 3.3x IQR) and are confounded with 13 acquisition groups | the gate says "state it in the audit"; DATA_AUDIT.md does not | add one paragraph to the audit template |

## L3 checks: doc value vs file value

| doc:line | doc value | file value (file) | match |
|---|---|---|---|
| REALITY_CHECK.md:1 | config `1bec114301c3`, git `bb277e7` | `de199d6c8d69` / `f1ea178` (all S1-S5 files) | **MISMATCH (stale header)** |
| REALITY_CHECK.md:5 | 31 images; 7/7/17; 93 TIFFs | 31; 7/7/17; 93 (images.csv, files.csv) | match |
| REALITY_CHECK.md:5 | 27 BSE+ETD+Inlens, 4 BSE+Inlens+SE | 27, 4 (images.csv) | match |
| REALITY_CHECK.md:5 | 4329 tiles, 1443 BSE, 39-52 per image | 4329, 1443, 39-52 (artefacts_per_tile, kpi_per_image.n_tiles) | match |
| REALITY_CHECK.md:6 | c0 medians 0.095 / 0.098 / 0.102 | 0.0951 / 0.0976 / 0.1019 (kpi_per_image) | match |
| REALITY_CHECK.md:6 | c1 0.829 / 0.811 / 0.804 | 0.8290 / 0.8113 / 0.8039 | match |
| REALITY_CHECK.md:6 | c2 0.089 / 0.092 / 0.097 | 0.0894 / 0.0922 / 0.0974 | match |
| REALITY_CHECK.md:6 | gap / IQR 0.3-1.0x | 0.26 (c2), 0.45 (c0), 1.02 (c1) | match (rounded) |
| REALITY_CHECK.md:7 | 4ih2ggld, 5n1q8atc c2 = 0.21-0.22 | 0.2051, 0.2203 | match |
| REALITY_CHECK.md:7 | r17byphk 0.14; others 0.06-0.13 | 0.1400; 0.0595-0.1262 | match |
| REALITY_CHECK.md:8 | c2 shift 0.041 / 0.024; c0 0.009 / 0.015 | 0.0412 / 0.0237; 0.0092 / 0.0146 (kpi_sensitivity, image level) | match |
| REALITY_CHECK.md:8 | "error bars as large as or larger than every between-batch gap" | true for c0 (gap 0.0068 vs 0.0092/0.0146) and c2 (gap 0.0080 vs 0.0412/0.0237); for c1 the gap is 0.0251 vs ×1.1 shift 0.0092 | match for the stated classes; **does not hold for c1** (caveat) |
| REALITY_CHECK.md:9 | t1 range 47-170, median 82, 3 tiles > 120 | 47, 170, 82, 3 (thresholds_per_tile) | match |
| REALITY_CHECK.md:9 | 31/1443 tiles t1 < 60; c2 0.29 vs 0.08; corr -0.57 | 31; 0.289 vs 0.079; -0.5749 | match |
| REALITY_CHECK.md:10 | curtaining gap 0.6x, edge_charging 1.0x IQR | 0.553, 0.956 (artefacts_per_image) | match |
| REALITY_CHECK.md:10 | Batch_3 noise 37.7 vs 46.3 / 44.4; gap 3.2x; sharpness 3.3x | 37.71 vs 46.30 / 44.36; 3.155; 3.257 | match |
| REALITY_CHECK.md:10 | Batch_3 low-noise 7 images 29.7-31.4; high 10 images 37.2-45.5 | 7: 29.69-31.36; 10: 37.22-45.53 | match |
| REALITY_CHECK.md:11 | 13 groups; 5 span 2-3 batches; 2080 / 126998864/125 holds all 3 | 13; 5; yes (images.csv) | match. "Near-identical noise": max within-group noise range 1.8 vs between-group SD 5.94 — supported |
| REALITY_CHECK.md:12 | widths 6960-7000 | 6960-7000 (files.csv) | match |
| REALITY_CHECK.md:12 | edge line in column 0: **20 files**; right edge 18 | **21** (files.csv `left_edge_rgb_differs`; my raw scan of column 0 = 21); right 18 | **MISMATCH (20 vs 21)** |
| REALITY_CHECK.md:12 | 13 tag values "all round to 25.000 nm/px" | 13 values, 24.99920-25.00055, 3-dp rounding gives {24.999, 25.000, 25.001} | **MISMATCH (wording)** |
| REALITY_CHECK.md:14 | 2880 → 4329 tiles; 0/1443 fallback; 92/92 sha match | 2880 stride-aligned + 1449 anchored = 4329; 0; 92 True + 1 NaN | match |
| DATA_AUDIT.md (all tables) | per-batch counts, channel sets, res-tag counts, intensity table | regenerated body is byte-identical | match |
| DATA_AUDIT.md:27 | RGB identical 54/93 | 54 | match |
| DATA_AUDIT.md:28 | right edge 18, left edge 21 | 18, 21 | match (and contradicts REALITY_CHECK.md:12) |
| DATA_AUDIT.md:76-77 | bright class identity and reference batch "unconfirmed" | Polaron: class 2 = silicon (stated), Batch_3 = baseline (`docs/READ/Polaron Clarification ...md`) | **STALE vs current answers** |
| PROJECT_STATE.md:40 | edge line "left (20 files)" | 21 | **MISMATCH** |
| PROJECT_STATE.md:40 | "15 (height, res-tag) groups" | 13 (corrected later at :65, but :40 still says 15) | **MISMATCH (stale)** |
| PROJECT_STATE.md:61 | 4329 tiles, 1443 BSE | 4329, 1443 | match |
| PR #1 Report back 2 | "all of which round to 25.000 nm/px (24.999–25.001)" | 24.999-25.001 | self-contradictory wording |

## Mismatch / defect list

1. **`qc audit` fails on a fresh install** (`tabulate` is missing from `pyproject.toml`; it is only in `requirements.txt`). Following the brief's setup command, DATA_AUDIT.md cannot be regenerated.
2. **Plain `pytest -q` fails at collection** (`tests/test_classify.py:8` imports `tests.test_validate`; there is no `tests/__init__.py`). `python -m pytest -q` passes 43.
3. **DATA_AUDIT.md is stale on all three current answers**: bright phase = silicon (Polaron), Batch_3 = baseline, same-FOV registration. The brief's required Polaron provenance record is missing. The text is hard-coded in `audit.py`, so it has to be fixed in code. `configs/v1.yaml:49` still has `reference_batch: auto`.
4. REALITY_CHECK.md:1 header quotes config `1bec114301c3` / git `bb277e7`; the files are `de199d6c8d69` / `f1ea178`. The numbers still match because the hash change did not alter S1-S5 outputs.
5. Column-0 edge-line count: REALITY_CHECK.md:12 and PROJECT_STATE.md:40 say 20; the file and my raw scan give 21.
6. "All round to 25.000 nm/px" is wrong at 3 dp (24.999 / 25.001 occur): REALITY_CHECK.md:12 and the PR's Report back 2.
7. PROJECT_STATE.md:40 still says 15 acquisition groups (13 is correct).
8. FRAMEWORK Phase A "10 tiles per batch at full resolution + materials-scientist note + pore/particle/crack decision": **not done**; there is no artefact.
9. Phase A gate statement is in REALITY_CHECK.md, not in "the audit" (DATA_AUDIT.md).
10. Definitional deviations from the brief (documented in code/PR, not in REALITY_CHECK.md):
    - curtaining uses the k_y = 0 band, not the literal vertical axis, and adds a Hann window;
    - "fill holes" means holes < 20 px only;
    - stride 512 plus 1449 edge-anchored tiles;
    - masks are in `data/masks/`;
    - per-image edge_charging is a mean of tile-frame contrasts, not the FOV frame band.
11. REALITY_CHECK.md:8's "error bars ≥ every between-batch gap" does not hold for class 1 (gap 0.025 vs ×1.1 shift 0.009).
12. git_sha values that look like scientific notation (`20e3371`) read back as `inf` from CSV.
13. PR #1 title and scope have grown past "v1 S1-S5 reality check", contrary to the brief's stop-after-step-5 rule.

## Verdict

**Phase A properly done: yes with defects.**

The S1-S5 pipeline is real code. It re-runs end to end on the 31 downloaded images, and every committed S1-S5 output matches my regeneration exactly: all 9 tables (max abs diff 0, same config hash `de199d6c8d69`, code unchanged between stamp `f1ea178` and HEAD `d4d035c`), DATA_AUDIT.md's body, all 9 PNGs pixel for pixel, and the registration tables. Almost every number in REALITY_CHECK.md matches the files.

The defects are:
- **Reproducibility:** `qc audit` crashes on a clean `uv pip install -e .` (tabulate), and plain `pytest -q` fails at collection.
- **DATA_AUDIT.md is stale:** it does not record any of the three current answers (Polaron silicon/graphite/void provenance, Batch_3 baseline, same-FOV registration), and its generator would overwrite a hand fix.
- **One FRAMEWORK Phase A deliverable was never produced:** the 10-tiles-per-batch visual review with a pore/particle/crack decision.
- **Small doc mismatches:** stale header hash, 20 vs 21 edge-line files, "all round to 25.000", 15 vs 13 groups.
- **Definitional deviations:** curtaining orientation, partial hole filling, edge-anchored tiles, tile-level edge_charging. The code and PR document them, but REALITY_CHECK.md does not.

None of these changes a committed S1-S5 number. Items 1-3 and the missing visual review should be closed before Phase A is called complete.

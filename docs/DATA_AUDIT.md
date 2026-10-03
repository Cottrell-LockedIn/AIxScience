# Data audit (S1)

Generated 2026-10-03T17:17:39+00:00 by `python -m qc audit` (config `configs/v1.yaml` @ `de199d6c8d69`, git `f1ea178`). Source tables: `results/audit/files.csv` (per TIFF) and `results/audit/images.csv` (per 8-char sample id).

## Images per batch

| batch   |   images |   files |
|:--------|---------:|--------:|
| Batch_1 |        7 |      21 |
| Batch_2 |        7 |      21 |
| Batch_3 |       17 |      51 |

## Channel set per image (count of images)

| batch   |   BSE+ETD+Inlens |   BSE+Inlens+SE |
|:--------|-----------------:|----------------:|
| Batch_1 |                7 |               0 |
| Batch_2 |                6 |               1 |
| Batch_3 |               14 |               3 |

Images missing a channel: 0. Images whose channels have inconsistent shapes: 0.

## Geometry and encoding

- Width: 6960 to 7000 px; height: 1612 to 2316 px.
- dtype ['uint8'], samples per pixel [np.int64(3)], compression ['LZW'], software ['tifffile.py'].
- RGB channels identical in 54/93 files (read channel 0 only).
- Files where the last 2 columns differ between RGB channels (coloured edge line): 18; first 2 columns differ (left edge line): 21 -> border crop 8 px applies to all.

## Resolution tag

Counts of the TIFF `XResolution` tag across files:

| res_tag       |   files |
|:--------------|--------:|
| 127004056/125 |      12 |
| 126999264/125 |      12 |
| 126998864/125 |       9 |
| 126997216/125 |       9 |
| 25399712/25   |       9 |
| 25399944/25   |       6 |
| 127001504/125 |       6 |
| 126997984/125 |       6 |
| 127001488/125 |       6 |
| 126998952/125 |       6 |
| 25400152/25   |       6 |
| 25399552/25   |       3 |
| 127000848/125 |       3 |

Consistent across all files: **no**. If the tag were intentional it would mean 25.000, 25.000, 25.000, 25.000, 25.000, 25.000, 25.000, 25.000, 24.999, 25.001, 25.000, 25.000, 25.000 nm/px. The tag was written by `tifffile.py`, not by the microscope; **pixel size is unconfirmed**. All units stay in pixels.

## Duplicates

- Files with identical bytes elsewhere: 0.
- Files with identical pixel content elsewhere: 0.

## Intensity per channel (channel 0, whole image)

|                       |   mean |   std |   p01 |   p99 |
|:----------------------|-------:|------:|------:|------:|
| ('Batch_1', 'BSE')    |   58.5 |  23.7 |   0   | 127.6 |
| ('Batch_1', 'ETD')    |   80   |  32.7 |   0   | 167.9 |
| ('Batch_1', 'Inlens') |  117.2 |  47   |   1.7 | 253.6 |
| ('Batch_2', 'BSE')    |   55.2 |  23.6 |   0   | 128.6 |
| ('Batch_2', 'ETD')    |   77.2 |  32.9 |   0   | 166.7 |
| ('Batch_2', 'Inlens') |  122.6 |  52.7 |   4.9 | 255   |
| ('Batch_2', 'SE')     |   73.6 |  31.3 |   0   | 158   |
| ('Batch_3', 'BSE')    |   58.8 |  21.2 |   7.1 | 125.7 |
| ('Batch_3', 'ETD')    |   74   |  31.7 |   5.7 | 162.9 |
| ('Batch_3', 'Inlens') |  105.3 |  52.6 |  15.9 | 242.8 |
| ('Batch_3', 'SE')     |   74   |  33.4 |   0   | 164   |

## Unconfirmed facts (see docs/READ/Questions for Polaron.md)

- Pixel size (25 nm/px inferred from a tifffile-written tag).
- Identity of the bright class on BSE (no EDS); class names stay 0 / 1 / 2.
- Whether a reference batch is designated.
- Whether ETD vs SE naming reflects a different session or microscope.

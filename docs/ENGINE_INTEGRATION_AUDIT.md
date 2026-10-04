# Engine integration audit — 2026-10-04

Scope: read-only audit of the merged engine and focused regression checks before
running the UI's exploratory analysis path. This is not an official held-out
evaluation.

## Result

The frozen classifier can be refit from the committed feature tables: it loads
31 image-level records, uses 11 measured features plus a 384-value BSE
embedding, and reproduces `results/v1/final_model.csv` with maximum coefficient
difference `1.37e-14` (the engine tolerance is `1e-9`).

The UI worker calls the correct isolated recipe:

```text
uploaded TIFFs -> .cottrell/uploads/<id> -> qc.heldout.run(..., exploratory=True)
  -> .cottrell/runs/<id>/result.json and masks/
```

That output mode cannot overwrite `results/v1/heldout.json`. It saves the
segmentation mask and overlay beside the run result. The mask records its
original-image crop offset as `[8, 8]` and its PNG SHA-256; clients must apply
that offset when aligning a mask to the source TIFF.

## Focused checks

* `tests/test_heldout.py`: 27 passed; 3 raw-heldout shape checks skipped because
  their source TIFFs are absent locally. The saved-mask parity, mask SHA-256,
  offset, exploratory-result parity, and fatal real-run Modal failure checks
  passed.
* `tests/test_pc_profiles.py`: 4 passed, 1 failed. The regenerated correlation
  table is self-deterministic, but its committed permutation p-values differ by
  as much as `0.0034982509` (seven increments of `1/2001`).
* The local environment is Python 3.12.15, NumPy 2.5.3, scikit-learn 1.9.1.
  `requirements.txt` specifies version ranges rather than an environment lock.

## Blocking / operational findings

1. `modal profile list` reports no configured profile. A Modal L4 embedding
   attempt will therefore fail until the user authenticates Modal. In
   exploratory mode, `heldout.run` falls back to local CPU; the local verified
   DINOv2 weight file and cached DINOv2 source are present, so this fallback is
   possible but slower. The official non-exploratory recipe intentionally makes
   a Modal failure fatal.
2. The PC-profile committed-output test is not reproducible under the current
   dependency ranges. It does not alter the model prediction path, but it makes
   a green full test run impossible. Pin the original NumPy/Python environment
   or regenerate/review the exploratory PC-profile artifact before treating it
   as reproducible.
3. The result API correctly calls all uploaded runs exploratory. Its displayed
   probabilities remain batch-match probabilities, not defect probabilities.

## API and evidence contract

* `POST /api/uploads` accepts a single-frame uint8 grayscale (or equal-channel
  RGB) TIFF, max 128 MiB / 25 million pixels, minimum 1040 pixels in each
  dimension, named `img_<field-id>_<channel>.tif`.
* Every field requires BSE. Other detector channels are optional.
* `POST /api/runs` launches one worker at a time. Poll `GET /api/runs/<id>` and
  retrieve the completed record at `GET /api/runs/<id>/results`.
* The run-specific source/preview, cropped BSE, overlay, and three phase-layer
  routes keep the UI traceable to the saved evidence.

# Dataset First Look (T+1.5h, 2026-10-03)

Source: public Google Drive folder "Hackathon-Polaron" (`https://drive.google.com/drive/folders/12UnB4HYDElXzoR4I0mG7NZ0buSr4QXF6`). Listing saved to `Log/assets/drive_file_listing.json`. Three images downloaded and inspected (one per batch); previews in `Log/assets/`.

## Inventory

| Batch | Files | Samples (unique stems) | Channels per sample | Size |
|---|---|---|---|---|
| Batch_1 | 21 | 7 | BSE, ETD, Inlens | 421 MB |
| Batch_2 | 21 | 7 | BSE, Inlens + ETD (6) or SE (1) | 420 MB |
| Batch_3 | 50 listed (listing truncated at 50; expect 51) | 17 | BSE, Inlens + ETD (14) or SE (3) | 878 MB |
| Total | ~92 | ~31 | | ~1.7 GB |

Download of the whole set is feasible in minutes with `curl` on `https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t`. File IDs are in the JSON listing.

Filename pattern: `img_<8-char id>_<DETECTOR>.tif`. The 8-char id is the sample/field-of-view id; the three detector files for one id are the **same field of view** (confirm by overlay, but shapes match).

## Image format

- TIFF, LZW, written by `tifffile.py`; stored as 3-channel uint8 RGB where all channels are identical (grayscale duplicated). Read channel 0 only.
- Width always 7000 px; height varies 1904 to 2316 px (likely cropped to the electrode cross-section; height = coating thickness in pixels).
- No SEM vendor metadata (no pixel size tag from the microscope). The TIFF `XResolution` tag is `25399944/25` px per inch, which equals **25.0 nm per pixel** if intentional. Cross-check: 7000 px = 175 um width, 2048 px = 51 um height; graphite flakes measure roughly 400 to 600 px = 10 to 15 um, consistent with typical anode graphite. **Treat 25 nm/px as inferred; confirm with Polaron before quoting physical units.**
- No databar, scale bar or text: images are already cropped to pure microstructure. One Batch_3 image has a 2-px coloured line at the far right edge (cols 6998 to 6999); crop 8 px from all borders to be safe.
- Needs `imagecodecs` for LZW decoding with tifffile.

## What the material is (visual reading, to confirm with Polaron)

This is a **graphite anode cross-section with a second, brighter particle phase**, not an NMC cathode:

- Inlens channel: large platelet/flake particles with layered striations (graphite), bright charging halos at particle edges, dark pore network, fine-grained binder/conductive-additive domains between particles. Some particles appear speckled.
- BSE channel: graphite appears dark grey; a minority of angular, blocky particles appear distinctly brighter (higher mean atomic number). In a graphite anode the obvious candidate is **silicon or SiOx**. The same particles are the speckled ones in Inlens. Pores are black.
- Faint vertical streaks (curtaining) visible in Inlens; BSE is noisier (grainy) but has the cleanest phase contrast.

Do not label the bright phase "silicon" in outputs until Polaron confirms; use "high-Z particle phase" until then.

## Why this matters for the KPIs

If the bright phase is Si/SiOx, its **area fraction, particle size, and spatial dispersion** are the most physically meaningful supplier-batch variables in the whole image (Si drives the 200 to 300% expansion Polaron described and therefore cracking). BSE gives this almost for free with a two-threshold segmentation. Candidate KPI set, in the vocabulary Polaron's group uses in their own papers (SliceGAN, MicroLib, ImageRep: phase volume fraction, two-point correlation, particle size, tortuosity):

1. Phase area fractions from BSE (pore / graphite / high-Z phase).
2. High-Z particle size distribution and count density; nearest-neighbour or cluster statistics for dispersion.
3. Graphite flake size and aspect ratio / orientation (anisotropy relative to the current collector direction).
4. Pore / crack fraction and pore size from Inlens or BSE; crack-like = thin dark elongated regions inside particles.
5. Two-point correlation characteristic length (ImageRep `radial_tpc`) per phase.
6. Optional: coating thickness per image (image height in px if cropping was to the coating), and electrode-scale porosity gradient top-to-bottom.

## Acquisition covariates to log per image

- Detector set (ETD vs SE naming may indicate a different session or microscope; check whether SE-named samples differ in brightness/noise).
- Height in px; mean/std intensity per channel; noise estimate on BSE; curtaining score on Inlens; edge-charging score on Inlens; sharpness.

## Sample sizes (drives the statistics)

7, 7 and 17 independent fields of view. Leave-one-image-out gives 31 folds. Permutation tests between batches of 7 and 7 have limited power; report effect sizes with image-level spread and say n explicitly.

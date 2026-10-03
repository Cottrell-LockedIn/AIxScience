# Visual inspection: Phase A 10-tile-per-batch review and Phase B 5-tile manual check

phase_identity: stated by Polaron, not image-verified (class 0 dark = void/pore, class 1 mid = graphite, class 2 bright = silicon; Si vs SiOx indistinguishable in BSE; binder/additive lumped into class 0/1).

Reviewed by the lead agent (not a materials scientist) on 2026-10-03, by eye, on the BSE tiles below. This is a qualitative record, not a measurement; nothing here changes a number.

Material: `results/audit/inspection/Batch_{1,2,3}_mosaic.png` (10 random BSE tiles per batch, seed 0, raw | class overlay; full-resolution tiles `Batch_*_tile_NN.png` are regenerated locally, not committed for size) and `results/audit/inspection/manual5_0{1..5}.png` (5 random tiles, seed 1, raw | overlay | class-0/1/2 masks).

## What the images show (all three batches)
- Large layered mid-grey flakes (class 1) dominate every tile; they are aligned roughly horizontally (in-plane), with dark elongated gaps between and inside flakes.
- Bright angular particles (class 2) sit between flakes, sizes from a few px to several hundred px. Most are dense and smooth; a minority are textured/porous-looking (e.g. `x77cy643_BSE_01028_00512`, `epqdaau9_BSE_01108_04096`, `r17byphk_BSE_00000_02048`). Whether that is agglomeration, a different particle type or a polishing effect cannot be told from BSE alone.
- No batch looks qualitatively different by eye at tile scale. Batch_1 tiles contain several very large bright particles (`5n1q8atc_BSE_01276_05632`, `uhdslk0o_BSE_00840_04608`), consistent with Batch_1 having the widest within-batch spread in `results/stats/*/consistency.csv`, but 10 tiles cannot establish a batch difference.

## Does thresholding separate pore / particle / crack? (FRAMEWORK Phase A bullet 4)
- Pore vs particle: yes for objects larger than a few px. Large class-2 particles and large dark gaps are segmented with clean boundaries (`manual5_04`, `manual5_05`).
- Pore vs crack: no. Both are class 0. Elongated inter-flake gaps, intra-flake cracks and rounder pores get the same label; separating them needs a shape rule (e.g. aspect ratio, skeleton length) or a learned detector, and curtaining must be excluded first. FM07 (cracks) therefore stays proxy-only.
- Class 0 also absorbs thin dark seams inside flakes; F08/F09 are sensitive to this.

## Segmentation defects seen (affect class-2 features F02-F07, F11)
1. Edge halo: thin bright rims along flake edges and fine porous texture are labelled class 2 (`manual5_01`: tile F02 = 0.28, much of it speckle on flake borders; also `xgj4xftb_BSE_00572_00000`, `tuy3zymq_BSE_00512_05120`, `mgxahqnk_BSE_00512_02048`). This inflates F02/F05 and lowers F03/F07, and is consistent with their failed threshold-sensitivity gate (`results/validate/features_f01_f11/decisions.csv`).
2. Particle-poor tile failure: `avn74qx1_BSE_00512_04096` (Batch_2) has almost no bright particles, and multi-Otsu still splits it into 3 classes, so most graphite becomes class 2. This is the known per-tile Multi-Otsu failure (NEXT_STEPS item 1: image-level thresholds).
3. Border strip: `manual5_03` (`epqdaau9_BSE_01108_01536`) has a bright strip on the bottom rows labelled class 2, which is an image-edge effect, not material.

## Consequences
- Large-particle and void statistics are usable as screening signals. Small-object class-2 statistics (F03, F05, F11) are not trustworthy until the edge halo is removed (e.g. an opening or minimum-thickness filter on class 2, or image-level thresholds) and the threshold-sensitivity gate is re-run.
- The bright-phase texture variation is a candidate new feature (within-class-2 texture), but it is not pre-registered and stays exploratory.

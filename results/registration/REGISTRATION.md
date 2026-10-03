# Detector pixel registration (BSE vs Inlens, BSE vs ETD/SE)

Produced by `python -m qc register` with `configs/v1.yaml@1bec114301c3`, git `790c1ef`. n = 31 images (independent unit), 62 detector pairs.

Method: phase correlation (`skimage.registration.phase_cross_correlation`, normalization=phase, x10 upsampling) on 768 px non-overlapping windows (all rows that fit x up to 6 columns), BSE as reference, Hann taper. Shift (dy, dx) in px of the cropped frame = shift to apply to the SE image to align it with BSE. Peak sharpness = peak-to-sidelobe ratio (PSR) of the phase-correlation surface; windows with PSR < 10.0 are ignored. Scale / rotation: similarity transform fitted to the window shift field.

Verdict rule per pair: |median shift| <= 2.0 px in both axes, std over windows <= 1.0 px, >= 4 valid windows. An image is pixel-registered iff both pairs pass.

## Result: 31 of 31 images are pixel-registered across all three detectors

- `BSE-ETD` (n = 27): 27 registered; |median shift| max 0.10 px, shift std max 0.09 px, PSR median 139 (min 57), fitted scale 0.99998-1.00003, rotation 0.0026 deg max |.|.
- `BSE-Inlens` (n = 31): 31 registered; |median shift| max 0.10 px, shift std max 0.06 px, PSR median 124 (min 60), fitted scale 0.99996-1.00002, rotation 0.0025 deg max |.|.
- `BSE-SE` (n = 4): 4 registered; |median shift| max 0.10 px, shift std max 0.06 px, PSR median 155 (min 60), fitted scale 1.00000-1.00002, rotation 0.0024 deg max |.|.

## Registered images (channels may be fused per pixel)

- Batch_1 (7): 4ih2ggld (ETD), 5n1q8atc (ETD), f1vzngrs (ETD), ffwubibz (ETD), fzrt2k6r (ETD), iv6g2oq0 (ETD), uhdslk0o (ETD)
- Batch_2 (7): 3806gxp0 (ETD), avn74qx1 (ETD), b3esycq1 (ETD), epqdaau9 (ETD), i9jiqjwl (ETD), r17byphk (ETD), rxax5ozo (SE)
- Batch_3 (17): 0grcilhi (ETD), 71vgq3fw (ETD), 9luzk4jm (ETD), cfe5vt7s (ETD), hawkfj64 (ETD), hzumfsms (ETD), kbdh4tri (ETD), mgxahqnk (ETD), pl8uabbv (ETD), ptg8lmto (ETD), tuy3zymq (ETD), ufdvpb81 (ETD), utfgcjfa (SE), vc2whyaq (SE), x77cy643 (SE), x7u69zsw (ETD), xgj4xftb (ETD)

## Not registered (do not fuse channels for these)

- none

## Per-image table

| batch | image | 3rd det. | pair | n win (valid) | dy med | dx med | dy std | dx std | PSR med | scale | rot (deg) | registered |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Batch_1 | 4ih2ggld | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.00 | 0.04 | 199 | 1.00000 | 0.0006 | yes |
| Batch_1 | 4ih2ggld | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.03 | 0.00 | 195 | 0.99999 | 0.0000 | yes |
| Batch_1 | 5n1q8atc | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.00 | 0.03 | 200 | 1.00000 | 0.0006 | yes |
| Batch_1 | 5n1q8atc | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.03 | 198 | 1.00000 | 0.0006 | yes |
| Batch_1 | f1vzngrs | ETD | BSE-ETD | 12 (12) | 0.00 | 0.00 | 0.05 | 0.06 | 111 | 1.00003 | -0.0004 | yes |
| Batch_1 | f1vzngrs | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.05 | 0.04 | 95 | 0.99998 | 0.0003 | yes |
| Batch_1 | ffwubibz | ETD | BSE-ETD | 12 (12) | 0.00 | -0.05 | 0.00 | 0.06 | 126 | 1.00000 | -0.0019 | yes |
| Batch_1 | ffwubibz | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.04 | 0.04 | 105 | 1.00001 | 0.0003 | yes |
| Batch_1 | fzrt2k6r | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.00 | 0.03 | 142 | 1.00000 | 0.0006 | yes |
| Batch_1 | fzrt2k6r | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.03 | 0.05 | 116 | 0.99999 | -0.0023 | yes |
| Batch_1 | iv6g2oq0 | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.00 | 0.05 | 136 | 1.00000 | -0.0006 | yes |
| Batch_1 | iv6g2oq0 | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.05 | 120 | 1.00000 | 0.0000 | yes |
| Batch_1 | uhdslk0o | ETD | BSE-ETD | 12 (12) | 0.00 | 0.00 | 0.00 | 0.05 | 149 | 1.00000 | -0.0012 | yes |
| Batch_1 | uhdslk0o | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.03 | 0.04 | 127 | 1.00001 | 0.0001 | yes |
| Batch_2 | 3806gxp0 | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.05 | 0.06 | 111 | 0.99999 | -0.0014 | yes |
| Batch_2 | 3806gxp0 | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.03 | 0.06 | 101 | 1.00001 | -0.0012 | yes |
| Batch_2 | avn74qx1 | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.04 | 0.06 | 101 | 1.00000 | -0.0012 | yes |
| Batch_2 | avn74qx1 | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.04 | 0.05 | 90 | 0.99999 | -0.0007 | yes |
| Batch_2 | b3esycq1 | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.03 | 0.04 | 139 | 1.00001 | 0.0006 | yes |
| Batch_2 | b3esycq1 | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.03 | 0.05 | 116 | 0.99999 | -0.0000 | yes |
| Batch_2 | epqdaau9 | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.00 | 0.06 | 120 | 1.00000 | 0.0006 | yes |
| Batch_2 | epqdaau9 | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.03 | 0.05 | 104 | 1.00001 | -0.0000 | yes |
| Batch_2 | i9jiqjwl | ETD | BSE-ETD | 12 (12) | 0.00 | -0.05 | 0.00 | 0.05 | 125 | 1.00000 | -0.0012 | yes |
| Batch_2 | i9jiqjwl | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.04 | 0.05 | 103 | 0.99998 | 0.0005 | yes |
| Batch_2 | r17byphk | ETD | BSE-ETD | 12 (12) | 0.00 | 0.00 | 0.03 | 0.05 | 140 | 0.99999 | 0.0017 | yes |
| Batch_2 | r17byphk | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.05 | 123 | 1.00000 | 0.0000 | yes |
| Batch_2 | rxax5ozo | SE | BSE-Inlens | 12 (12) | 0.00 | 0.05 | 0.00 | 0.05 | 138 | 1.00000 | 0.0025 | yes |
| Batch_2 | rxax5ozo | SE | BSE-SE | 12 (12) | 0.00 | -0.10 | 0.03 | 0.06 | 163 | 1.00001 | 0.0024 | yes |
| Batch_3 | 0grcilhi | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.03 | 0.08 | 84 | 0.99999 | -0.0018 | yes |
| Batch_3 | 0grcilhi | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.04 | 81 | 1.00000 | 0.0019 | yes |
| Batch_3 | 71vgq3fw | ETD | BSE-ETD | 12 (12) | 0.00 | -0.05 | 0.03 | 0.06 | 136 | 0.99999 | -0.0007 | yes |
| Batch_3 | 71vgq3fw | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.04 | 132 | 0.99999 | 0.0000 | yes |
| Batch_3 | 9luzk4jm | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.03 | 0.05 | 144 | 0.99998 | -0.0001 | yes |
| Batch_3 | 9luzk4jm | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.04 | 0.05 | 124 | 1.00002 | -0.0016 | yes |
| Batch_3 | cfe5vt7s | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.03 | 0.05 | 151 | 0.99999 | 0.0007 | yes |
| Batch_3 | cfe5vt7s | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.04 | 125 | 1.00000 | -0.0012 | yes |
| Batch_3 | hawkfj64 | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.04 | 0.09 | 75 | 1.00002 | 0.0025 | yes |
| Batch_3 | hawkfj64 | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.05 | 78 | 1.00000 | -0.0006 | yes |
| Batch_3 | hzumfsms | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.03 | 0.05 | 134 | 0.99999 | 0.0007 | yes |
| Batch_3 | hzumfsms | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.06 | 0.05 | 120 | 0.99996 | 0.0000 | yes |
| Batch_3 | kbdh4tri | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.00 | 0.05 | 173 | 1.00000 | 0.0000 | yes |
| Batch_3 | kbdh4tri | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.03 | 163 | 1.00000 | 0.0006 | yes |
| Batch_3 | mgxahqnk | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.06 | 0.06 | 78 | 1.00001 | 0.0026 | yes |
| Batch_3 | mgxahqnk | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.04 | 75 | 1.00000 | 0.0000 | yes |
| Batch_3 | pl8uabbv | ETD | BSE-ETD | 12 (12) | 0.00 | 0.00 | 0.03 | 0.05 | 151 | 1.00000 | -0.0006 | yes |
| Batch_3 | pl8uabbv | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.03 | 0.04 | 129 | 0.99998 | 0.0004 | yes |
| Batch_3 | ptg8lmto | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.03 | 0.05 | 183 | 1.00002 | 0.0006 | yes |
| Batch_3 | ptg8lmto | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.03 | 160 | 1.00000 | 0.0006 | yes |
| Batch_3 | tuy3zymq | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.00 | 0.04 | 170 | 1.00000 | 0.0000 | yes |
| Batch_3 | tuy3zymq | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.04 | 160 | 1.00000 | 0.0000 | yes |
| Batch_3 | ufdvpb81 | ETD | BSE-ETD | 12 (12) | 0.00 | 0.00 | 0.03 | 0.05 | 136 | 1.00000 | 0.0006 | yes |
| Batch_3 | ufdvpb81 | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.04 | 0.06 | 116 | 1.00002 | -0.0015 | yes |
| Batch_3 | utfgcjfa | SE | BSE-Inlens | 12 (12) | 0.00 | 0.10 | 0.03 | 0.05 | 137 | 0.99998 | -0.0017 | yes |
| Batch_3 | utfgcjfa | SE | BSE-SE | 12 (12) | 0.00 | -0.10 | 0.04 | 0.05 | 153 | 1.00002 | -0.0016 | yes |
| Batch_3 | vc2whyaq | SE | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.06 | 126 | 1.00000 | -0.0012 | yes |
| Batch_3 | vc2whyaq | SE | BSE-SE | 12 (12) | 0.00 | -0.10 | 0.00 | 0.06 | 146 | 1.00000 | 0.0019 | yes |
| Batch_3 | x77cy643 | SE | BSE-Inlens | 12 (12) | 0.00 | 0.10 | 0.00 | 0.06 | 131 | 1.00001 | 0.0006 | yes |
| Batch_3 | x77cy643 | SE | BSE-SE | 12 (12) | 0.00 | -0.05 | 0.00 | 0.05 | 156 | 1.00000 | -0.0012 | yes |
| Batch_3 | x7u69zsw | ETD | BSE-ETD | 12 (12) | 0.00 | 0.00 | 0.03 | 0.05 | 175 | 0.99999 | -0.0007 | yes |
| Batch_3 | x7u69zsw | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.05 | 159 | 1.00000 | 0.0006 | yes |
| Batch_3 | xgj4xftb | ETD | BSE-ETD | 12 (12) | 0.00 | -0.10 | 0.00 | 0.04 | 147 | 1.00000 | -0.0006 | yes |
| Batch_3 | xgj4xftb | ETD | BSE-Inlens | 12 (12) | 0.00 | 0.00 | 0.00 | 0.06 | 128 | 1.00000 | -0.0012 | yes |

Caveat (OBSERVED vs INFERRED): a zero shift with a sharp peak is observed; that the detectors were read out in the same scan (simultaneous acquisition) is inferred from it, not documented in the files. Units: px; 25 nm/px is unconfirmed.

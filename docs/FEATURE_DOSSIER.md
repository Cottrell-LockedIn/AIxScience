# Feature dossier: the 10 pre-registered measurements

Status: 2026-10-03, written against PR #1 (`stage/s1-s5-reality-check`, config `1bec114301c3` at writing time; all tables now carry `de199d6c8d69` after the `main` phase-name merge, feature values unchanged, 31 images: Batch_1 7, Batch_2 7, Batch_3 17 = reference). Docs only; no code changed.
Scope: for each pre-registered measurement, (a) does it make physical and measurement sense on a single 2D BSE cross-section at ~25 nm/px (if that pixel size is true), (b) can it contribute to the project goal (separate batches, explain why, separate acquisition from material), and (c) what pre-declared test keeps or drops it.
Companion documents (not duplicated here): `docs/EVIDENCE_BASE.md` (general evidence base, separate session), the validation harness (separate session; this dossier only declares the criteria it applies), `docs/READ/Method Evidence for Layers.md` (method citations), `results/audit/REALITY_CHECK.md` and PR #1 (the v1 numbers quoted below). References with DOIs: `docs/evidence/feature_refs.bib`; every DOI was resolved through `https://api.crossref.org/works/<DOI>` on 2026-10-03.

`phase_identity: stated by Polaron, not image-verified` applies to every statement below. Class 2 (bright) = silicon, class 1 (mid) = graphite, class 0 (dark) = void/pore. Si vs SiOx is indistinguishable in BSE; binder and conductive additive are lumped into class 0/1. No chemistry beyond this is claimed anywhere in this document. Units are pixels (px); a value in nm is given only as "if 25 nm/px is true" (13 distinct tifffile-written tags, all ~25.000 nm/px, unconfirmed).

Conventions used below:

- "Observed in literature" = a published, DOI-cited statement. "Inferred by us" = our reasoning from the images and v1 numbers, not from a source.
- v1 numbers are per-image means over 1024 px tiles (stride 512), 39-52 BSE tiles per image, n = 31 images. "Batch median" = median of per-image values. "B3 MAD" = 1.4826 x median absolute deviation of the 17 Batch_3 images (the robust reference spread). Batch_3 is the reference but not error-free: `vc2whyaq`, `ufdvpb81` (silicon equivalent-diameter z = +10.8 / +6.7) and `hzumfsms` (void fraction z = +3.7) are LOO-flagged `investigate` in PR #1.
- Artefact covariates (BSE `noise_sigma`, `sharpness`, `curtaining_score`; Inlens `edge_charging`; per-tile thresholds `t0`, `t1`) are measured and kept, never removed (FRAMEWORK §00 rule 3). Correlations quoted are Spearman rho over the 31 images, computed from `results/kpi_per_image.parquet`, `results/artefacts_per_image.parquet` and `results/thresholds_per_tile.parquet` as committed in PR #1. Note that `noise_sigma` and `sharpness` are both Laplacian statistics and have rho = 0.99 across images: they are one acquisition axis, not two.
- Features F06-F11 are not computed in v1 (`src/qc/kpi.py` computes F01-F05 plus class-0 region size). Their sensitivity estimates are therefore first-principles plus proxies, and are labelled so.

## 1. Summary table

Evidence grade for relevance to the project goal: **A** = the quantity is a standard microstructure descriptor and literature on Si/graphite anodes or electrode cross-sections ties it to a material property; **B** = standard descriptor, relevance to this material inferred by us with partial literature support; **C** = inferred by us only, plausible; **D** = mainly a sanity or acquisition covariate rather than a material axis.

| ID | Feature | Physical axis (stated identities) | Grade | Main confound (direction) | Cut priority (1 = cut first) |
|---|---|---|---|---|---|
| F01 | class-0 (void) area fraction | porosity / calendering density | A | lower threshold `t0` and noise (noise -> rho -0.36); +/-10 % threshold = +/-0.01-0.015 | keep (anchor) |
| F02 | class-2 (silicon) area fraction | resolvable silicon loading | A | upper threshold `t1` (rho -0.59); multi-Otsu failure on particle-free tiles inflates c2 to ~0.29; +/-10 % threshold = +0.04 / -0.02 | keep (anchor) |
| F03 | class-2 equivalent-diameter median | silicon particle size (small-particle mode) | A | resolution limit (median 8.3 px, i.e. ~200 nm if 25 nm/px) and `min_object_px = 20`; `t0`/`t1` | keep |
| F04 | class-2 equivalent-diameter p90 | silicon particle size (large / agglomerate mode) | A | sampling (few large particles per image: B3 MAD 18 px on a median of 42 px); image mean intensity (rho -0.48) | keep, report with n of particles |
| F05 | class-2 count density per Mpx | silicon dispersion / fragmentation | B | multi-Otsu failure (x4 on failed tiles); double counting at tile borders; rho 0.73 with F02, -0.81 with F04 | 5 |
| F06 | class-2 Clark-Evans NN ratio | silicon agglomeration vs random dispersion | B | depends on F05 (density enters the expected NN distance); tile borders; 2D section of 3D arrangement | 4 |
| F07 | class-2 solidity | silicon particle fracture / shape | C | noise and blur (both roughen or smooth boundaries); failure tiles produce texture outlines with low solidity; pixelation at 8 px | 2 |
| F08 | class-0 local thickness median | pore width (transport proxy) | B | noise (c0 region size rho -0.63 with noise, batch-confounded); curtaining stripes; 2D bias low | 6 |
| F09 | class-0 chord-length anisotropy (x/y) | pore orientation / flake alignment in section plane | B | curtaining (vertical stripes elongate class-0 chords in y); no collector in frame, so "y" is not "through-plane" | 7 |
| F10 | within-image IQR of class-0 fraction over 512 px windows | mesoscale heterogeneity of porosity | C | window size and tile seams; rho 0.63 with F01 (proxy); per-tile thresholds add seam variance | 3 |
| F11 | class-2 perimeter fraction adjacent to class 0 | silicon-void contact (debonding / detachment proxy) | C | threshold choice at both boundaries; edge charging rims; perimeter estimation bias; failure tiles | 1 |

Consultant's cut order (F11, F07, F10) is adopted as priorities 1-3; our order for 4-7 follows the redundancy analysis in each section (F06 and F05 are partly redundant with F02/F04; F08 and F09 carry the acquisition confounds that are batch-correlated in v1).

## 2. Common definitions and caveats (apply to every feature)

- **Mask.** `qc segment`: BSE channel 0, median filter 5 px, `threshold_multiotsu(classes=3)` per 1024 px tile giving `t0 < t1`; class 0 = grey < t0, class 2 = grey >= t1, class 1 otherwise; for classes 0 and 2, connected components < 20 px removed and holes < 20 px filled; class 2 has priority over class 0. Thresholds are per tile and logged (FRAMEWORK §13.2). Otsu-type thresholds are histogram-driven [otsu1979] and are known to move with noise and with the relative population of the classes [sezgin2004], which is the root of the particle-free-tile failure described below. Tiles are 50 % overlapping; per-image KPI = mean over tiles (interior pixels weighted ~uniformly).
- **Border handling.** 8 px frame crop before tiling (coloured edge line). Within a tile, objects touching the tile border are kept, so an object cut by a border contributes a truncated area and is counted in each tile it touches. The probability that a disc of diameter d touches the border of an L = 1024 tile is ~2d/L: ~1.6 % at d = 8 px, ~8 % at d = 40 px. For count-type features (F05, F06) the harness should use the whole-image mask or a Gundersen unbiased counting frame [gundersen1977] rather than tile means; for fraction-type features (F01, F02) the tile mean is unbiased.
- **2D vs 3D.** Area fraction on a random section is an unbiased estimator of volume fraction (Delesse / Cavalieri principle, [russ2000]). Section diameters of 3D particles are biased low and the section size distribution is a Wicksell transform of the 3D one [wicksell1925]; 2D counts per area (N_A) are not 3D counts per volume (N_V = N_A / mean caliper height, [russ2000]); nearest-neighbour distances, solidity, chord lengths and local thickness measured on a section describe the section, not the 3D body [torquato2002]. The dossier therefore treats every size/shape/arrangement feature as a **2D descriptor compared between batches under the same sectioning protocol**, which is valid for batch comparison but not for absolute 3D claims. The section is a FIB-milled face at an unknown orientation to the coating; no collector or free surface is in frame (edge dark fraction equals mid-image in all 31 BSE images, PR #1), so there is no depth axis.
- **Resolution.** If 25 nm/px is true, the median class-2 particle (8.3 px) is ~200 nm, and `min_object_px = 20` (~5 px diameter, ~125 nm) is the detection floor. Silicon at the few-hundred-nm scale is at the resolution limit; the class-2 fraction is a *resolvable* silicon fraction, not total silicon content (`docs/READ/Method Evidence for Layers.md`, Layer B).
- **Multi-Otsu failure mode (PR #1 item 5).** On tiles without bright particles the upper threshold collapses into the graphite grey-level texture: `t1` ranges 47-170 (median 82); the 31/1443 BSE tiles with `t1 < 60` report median c2 = 0.29 vs 0.08 elsewhere, count density 303 vs 80 per Mpx, equivalent-diameter median 7.7 px and p90 23.4 px (vs 29.7 px on non-failure tiles), i.e. many small, low-solidity "particles" that are flake-edge texture. Tile-level corr(`t1`, c2) = -0.57; image-level Spearman rho(mean `t1`, F02) = -0.54 (KPI `frac_c2` rho = -0.59). Class 0 is much less affected (corr(`t0`, c0) = 0.18). Every feature built on class 2 (F02-F07, F11) inherits this failure on ~2 % of tiles; features built on class 0 (F01, F08-F10) mostly do not. v1 keeps the failure as specified; the S4 challenger (per-image thresholds or a floor on `t1`) is a separate decision. Until then the harness must report each class-2 feature with and without the `t1 < 60` tiles.
- **Threshold sensitivity (v1, image level, thresholds x0.9 / x1.1).** F02: median +0.041 / -0.024 (max 0.092 / 0.056). F01: median -0.009 / +0.015 (max 0.028 / 0.030). Reference values: F02 batch medians 0.089 / 0.092 / 0.097, B3 MAD 0.027; F01 batch medians 0.095 / 0.098 / 0.102, B3 MAD 0.012.

## 3. Feature sections

### F01: class-0 (void) area fraction

#### Definition

phi_0 = N(class 0 px) / N(all px) per tile, dimensionless, 0-1; per-image value = mean over tiles. Border: tile mean over the cropped frame; no edge correction needed for an area fraction. 2D vs 3D: unbiased for volume fraction under uniform random sectioning (Delesse, [russ2000]); the FIB face is a single, non-random section, so the estimate is for that face and is compared between batches, not converted to 3D porosity. Includes anything darker than `t0`: pores, cracks, and the low-Z parts of the carbon-binder domain (lumped, per the Polaron caveat).

#### What it should detect in this material

Observed in literature: porosity is a primary design and quality variable of electrodes (calendering sets it) and the carbon-binder domain is itself nanoporous and resolvable in FIB-SEM [vierrath2015] but not in X-ray tomography [zielke2014], so a BSE section at ~25 nm/px sees pore + CBD darkness together; silicon expands ~3x on lithiation and fractures, which changes pore space and particle-matrix contact with cycling [mcdowell2013, obrovac2014, muller2018]; Polaron's own validation metrics put phase volume fraction first [kench2021, kench2022].
Inferred by us: a batch with different calendering, binder content or Si expansion history would move phi_0 by several percentage points; v1 shows batch medians 0.095 / 0.098 / 0.102 with within-batch IQR 0.013-0.023, so the three delivered batches do not differ on it beyond spread.

#### Known confounds

Lower threshold `t0` (rho(`t0`, F01) = 0.04 at image level, so weak); image noise (rho -0.36: noisier images report *less* void, plausibly because the 5 px median filter plus 20 px minimum object size removes small dark regions when the noise widens the dark-class tail); mean intensity (rho -0.30; brighter acquisitions push dark pixels over `t0`). Curtaining (rho +0.25): dark stripes add class-0 pixels. Edge charging: weak (rho -0.12; BSE is the segmented channel). Tile boundaries: none for a fraction. Multi-Otsu failure: largely insulated (`t0` is stable; the failure is in `t1`). Direction summary: noise down, brightness down, curtaining up.

#### Expected sensitivity

Measurement noise: +/-10 % threshold = -0.009 / +0.015 (max 0.03); B3 MAD = 0.012; within-image tile SD median 0.021. A meaningful batch shift is therefore >= 0.03 absolute (>= 2.5 B3 MAD, > the threshold error bar); the v1 between-batch gaps (0.003-0.007) are not meaningful. If 25 nm/px is true nothing changes: the fraction is unitless.

#### Keep/drop test

(T1) threshold sensitivity: |median Delta phi_0 at x0.9 and x1.1| < 0.5 x |claimed batch median gap|, else the gap is reported as "within segmentation uncertainty" and F01 contributes no verdict; (T2) confound screen: |rho| with `noise_sigma`, `curtaining_score`, `edge_charging`, mean intensity all < 0.5 over the 31 images and the batch effect must survive within the 13 (height, res-tag) acquisition groups (leave-one-group-out, LOGO); (T3) robustness panel (FRAMEWORK §13.3): per-image rank correlation >= 0.8 under gamma 0.9-1.1, noise sigma 2-8, blur 0.5-1.5 px; (T4) split-half repeatability: left/right half-image difference median < 0.5 x B3 MAD. Drop if T1 fails for every batch pair *and* T4 fails (then it measures nothing above noise). F01 is an anchor: it is kept as a reported quantity even if it does not separate batches, because "no porosity change" is itself a result.

#### Redundancy

rho = 0.78 with class-0 region mean area, 0.63 with the within-image tile SD of phi_0 (F10 proxy), 0.31 with class-0 region equivalent diameter (F08 proxy), 0.37 with F04. F01 and F08 are kept together because fraction and width answer different questions (how much vs how coarse). F10 is cut before F01 if their correlation stays > 0.6 on the final windows.

### F02: class-2 (silicon) area fraction

#### Definition

phi_2 = N(class 2 px) / N(all px), after removal of components < 20 px and hole filling < 20 px; per-image mean over tiles. Border: as F01. 2D vs 3D: Delesse applies [russ2000]; this is the *resolvable* bright-phase fraction (particles >= ~5 px diameter), not total silicon content, and Si vs SiOx cannot be separated in BSE. Mean BSE grey level scales monotonically with mean atomic number [goldstein2018], which is why Si (Z = 14) is the bright class against carbon (Z = 6) and void.

#### What it should detect in this material

Observed in literature: Si/graphite blends carry a few to ~20 wt% Si and their capacity and degradation scale with Si content and distribution [chae2019]; Si lithiates/delithiates at different potentials from graphite, so Si particles cycle against a graphite matrix [yao2019]; Si fracture and pulverisation redistribute the bright phase into smaller fragments [liu2012, mcdowell2013].
Inferred by us: a batch with a different Si loading or different Si particle survival should move phi_2 by >= 0.02-0.03 absolute. F02 batch medians are 0.089 / 0.097 / 0.101 (Batch_1 / Batch_2 / Batch_3; gap <= 0.012) and do not separate; three images (`4ih2ggld`, `5n1q8atc` in Batch_1 at 0.21-0.22, `r17byphk` in Batch_2 at 0.14) carry most of the spread and are either field-of-view sampling of Si-rich regions or real within-batch heterogeneity (C1 question).

#### Known confounds

Upper threshold `t1` is the dominant one: rho(`t1`, F02) = -0.59 across images, tile-level corr -0.57; a lower `t1` increases phi_2. Multi-Otsu failure on particle-free tiles inflates phi_2 to ~0.29 on ~2 % of tiles (see §2) and raises the image mean by up to ~0.005 per failed tile. Curtaining rho +0.37, image mean rho +0.29, edge charging rho +0.16 (bright rims at particle edges fatten class 2; BSE less affected than Inlens [goldstein2018]). Noise rho -0.19 (small bright fragments removed by the 20 px floor). Blur: widens the grey transition at particle edges so phi_2 depends more steeply on `t1` (direction depends on where `t1` falls; inferred). Tile boundaries: none for a fraction. Direction summary: lower `t1` up, curtaining up, charging up, noise down, failure tiles up.

#### Expected sensitivity

+/-10 % threshold = +0.041 / -0.024 (median; max 0.092 / 0.056), i.e. roughly +/-30-45 % relative on a median of ~0.09; B3 MAD 0.027; within-image tile SD median 0.045. A meaningful shift is >= 0.05 absolute (about 2 B3 MAD and above the threshold band); a 2x change (as in the three high-c2 images) is unambiguous. Between-batch gaps of < 0.01 are noise.

#### Keep/drop test

T1-T4 as for F01, plus (T5) class-2 features are evaluated twice, with all tiles and with `t1 < 60` tiles excluded; a batch effect that appears in only one of the two is reported as `investigate`, not as a finding. Drop criterion: T1 fails (threshold band wider than every batch gap) *and* the LOIO logistic regression without F02 loses no image of accuracy. Like F01, F02 stays as a reported anchor even when it does not separate, because the resolvable silicon fraction is the quantity Polaron would ask for first.

#### Redundancy

rho = 0.73 with F05 (more particles at fixed size = more area), -0.44 with F04 (images with many small particles have lower p90). F02 and F05 are both kept because they separate "more silicon" from "same silicon in more pieces" (fragmentation): phi_2 constant with F05 up is fragmentation, both up is loading. If one must go, cut F05 (priority 5), not F02.

### F03 / F04: class-2 particle equivalent-diameter median and p90

#### Definition

For each class-2 connected component (4-connectivity, after the 20 px cleaning) d_eq = sqrt(4A/pi) in px; F03 = median of d_eq over all components in the tile, F04 = 90th percentile; per-image = mean over tiles (v1) or, preferably for the harness, pooled over all components of the image with a Gundersen counting frame. Border: components cut by a tile border are truncated (biases d_eq low, more for large particles: ~8 % of 40 px particles touch a border); the harness should pool on the whole-image mask. 2D vs 3D: section diameters of spheres are biased low and their distribution is the Wicksell transform of the 3D distribution [wicksell1925, russ2000]; we compare 2D section distributions between batches and make no 3D claim. If 25 nm/px is true, 8.3 px = ~210 nm and 42 px = ~1.05 um.

#### What it should detect in this material

Observed in literature: Si particle size controls fracture on lithiation (critical diameter ~150 nm for crystalline Si nanoparticles [liu2012]); size and size distribution of the alloying phase are design levers for cycle life [obrovac2014, mcdowell2013]; nanoscale 3D imaging of Si-graphite anodes quantifies particle fracture and pore-space change with cycling [muller2018]; particle size is one of Polaron's standard microstructure metrics [kench2021].
Inferred by us: F03 tracks the small-particle mode (which sits at the resolution limit here: medians 8.4 / 8.4 / 8.3 px per batch with B3 MAD 0.20 px, i.e. almost pinned by the 20 px object floor), while F04 tracks the large-particle/agglomerate tail (33 / 40 / 42 px, B3 MAD 18 px). A batch of coarser or agglomerated silicon moves F04 first; a batch with finer or fractured silicon moves F05 and F02 before F03, because sub-floor fragments disappear rather than lowering the median. Batch_2 images `epqdaau9` (13.1 px) and `avn74qx1` (11.3 px) have the largest F03 in the set (z = +24 / +15 vs B3), and the two LOO-flagged Batch_3 images `vc2whyaq`, `ufdvpb81` have large F04 (68, 77 px): F03/F04 are where the current within-reference structure is.

#### Known confounds

`t0`: rho(`t0`, F03) = -0.50 (a higher lower threshold leaves fewer dark pixels inside/around particles; inferred); `t1`: lower `t1` adds small texture components, pulling F03 and F04 down (failure tiles: F03 7.7 px, F04 23 px vs ~40). Image mean intensity: rho -0.39 (F03), -0.48 (F04). Edge charging: rho -0.36 with F04. Noise: rho +0.28 with F03 (noise removes the smallest components, raising the median). Blur: merges close particles (F04 up) and erases the smallest (F03 up). Tile boundaries: truncation biases both low, F04 more. Resolution floor: F03 is clamped near sqrt(4 x 20/pi) = 5 px from below and sits at 8 px, so it has little downward room. Multi-Otsu failure: both down.

#### Expected sensitivity

F03: B3 MAD 0.20 px, batch gaps 0.13 px: no batch effect; a meaningful change is >= 1 px (12 %) and would also need to survive the x0.9 / x1.1 threshold recomputation (not yet run for diameters in v1; the harness computes it). F04: B3 MAD 18 px on a median of 42 px (43 % relative) because an image has only tens of particles in the tail; a meaningful change is >= 20 px (~0.5x) at image level, or a batch median shift that exceeds the image-level permutation null (7 vs 17 images gives a minimum p of ~1e-5 but low power; report effect size and null band, FRAMEWORK §00 rule 4). Report the number of particles behind every F04 value.

#### Keep/drop test

T1 (threshold sensitivity on d_eq, to be produced by the harness at x0.9 / x1.1): |Delta F03| < 1 px and |Delta F04| < 0.5 x claimed gap; T2 confound screen as F01, with `t0` and mean intensity added to the screened covariates; T3 robustness panel including the 0.8x-1.25x rescale row, under which F03/F04 must scale linearly with the factor (a feature that does not is reading pixel texture, not particles); T4 split-half repeatability: F04 half-image difference < B3 MAD. Drop F03 if, after excluding the 20 px floor effect, its B3 MAD stays < 0.3 px and no batch pair differs by > 1 px (it is then a constant and only confirms the resolution limit). Drop F04 if T4 fails (p90 not repeatable within an image) because it is then sampling noise.

#### Redundancy

rho(F03, F04) = 0.51; rho(F04, F05) = -0.81; rho(F04, F02) = -0.44. F03 and F04 are kept as a pair because they describe different modes of the distribution and v1 shows them moving independently (Batch_2 high F03 with ordinary F04; `ufdvpb81` ordinary F03 with high F04). F04 vs F05: strongly anti-correlated by construction (at fixed phi_2, many particles means small ones), so if F05 is dropped (priority 5), F04 carries the fragmentation axis.

### F05: class-2 count density per Mpx

#### Definition

N_A = (number of class-2 connected components) / (tile area in px) x 1e6, components >= 20 px, 4-connectivity; per-image mean over tiles. Border: components touching tile borders are counted in each tile they touch (v1), which over-counts by roughly the border-touching probability (~2-8 %); the harness should count on the whole-image mask with an unbiased counting frame [gundersen1977]. 2D vs 3D: N_A is a profile count; N_V = N_A / mean caliper height requires a size assumption [russ2000], so N_A is compared between batches as a 2D quantity.

#### What it should detect in this material

Observed in literature: fracture and pulverisation of Si particles on cycling increase the number of fragments at fixed loading [liu2012, mcdowell2013]; dispersion quality of a particulate phase is characterised by counts and spacing statistics in composite microstructure analysis [pyrz1994].
Inferred by us: N_A separates "same silicon in more pieces" (fragmentation or finer powder) from "more silicon" when read with F02. v1 batch medians 119 / 113 / 138 per Mpx with within-batch IQR 31-141: no separation; the two high-c2 Batch_1 images have N_A ~300 (2.5x) with ordinary diameters, i.e. more particles, not larger ones.

#### Known confounds

The multi-Otsu failure is the worst: failed tiles report N_A ~303 vs 80 per Mpx, so a single failed tile among ~45 adds ~5 per Mpx to the image mean. `t1`: rho -0.39; `t0`: rho +0.33 (a higher `t0` removes dark pixels that would otherwise split a particle; inferred). Curtaining rho +0.37, edge charging rho +0.38, image mean rho +0.44 (bright rims and stripes create extra small bright components). Noise rho -0.17 (small components removed). Blur: merges neighbours, N_A down. Tile boundaries: over-count ~2-8 %. Direction summary: failure tiles, charging, curtaining, brightness up; noise, blur down.

#### Expected sensitivity

B3 MAD 81 per Mpx on a median of 138 (59 % relative): the noisiest of the v1 features. Meaningful change: >= 2x at image level, or a batch median shift > the image-level permutation null band. Threshold sensitivity on counts has not been computed in v1; expected to be large because every spurious texture component counts once regardless of size.

#### Keep/drop test

T1: |Delta N_A| at x0.9 / x1.1 < 0.5 x claimed gap; T2: |rho| < 0.5 with every artefact covariate (currently 0.37-0.44 with three of them, so marginal) and survival under LOGO; T5: recomputed without `t1 < 60` tiles, batch ordering unchanged. Drop if T1 fails or if the LOIO classifier's drivers never include it once F02 and F04 are present. Pre-declared: if the S4 challenger (per-image thresholds / `t1` floor) is not adopted, F05 is reported only as a ratio to F02 (particles per unit silicon area), which cancels the loading dependence.

#### Redundancy

rho = 0.73 with F02, -0.81 with F04, -0.34 with F03. F05 is largely a function of (F02, F04) and is therefore cut priority 5: it is kept only while it adds a driver that F02 and F04 do not.

### F06: class-2 Clark-Evans nearest-neighbour ratio

#### Definition

For the centroids of class-2 components in a window, R = mean observed NN distance / expected NN distance under complete spatial randomness, with E[d] = 1 / (2 sqrt(lambda)), lambda = N / window area (px^-2) [clark1954]. R = 1 random, R < 1 clustered, R > 1 regular (dispersed). Dimensionless. Border: NN distances near the window edge are biased high because neighbours outside the window are unseen; use a guard zone (exclude centroids within the median NN distance of the edge from the "observed" set but keep them as neighbours) or compute on the whole-image mask [pyrz1994]. 2D vs 3D: the 2D NN ratio of section centroids is not the 3D NN ratio; with lambda estimated from the same window it is scale-free and batch-comparable [torquato2002].

#### What it should detect in this material

Observed in literature: nearest-neighbour and second-order statistics are the standard quantitative description of particle/fibre dispersion in composites [pyrz1994]; heterogeneity (agglomeration) at the meso-scale degrades Li-ion electrode durability [harris2013]; FRAMEWORK §00 names "agglomerated high-Z particles" as the kind of finding that beats an embedding distance.
Inferred by us: a batch whose silicon is agglomerated (poor mixing or fragments of a shattered parent particle) would show R clearly < 1; well-dispersed powder gives R near 1. No v1 value exists yet.

#### Known confounds

F06 inherits F05's count confounds through lambda and through spurious components: multi-Otsu failure tiles add dense texture "particles" that are strongly clustered (R down) and change lambda; fractured-particle fragments are, by construction, clustered (so R < 1 is ambiguous between agglomerated powder and in-situ fracture; this ambiguity cannot be resolved from a 2D BSE section and must be stated). Blur merges near neighbours (R up). Edge charging and curtaining add components (R down). Window edges (R up without guard). Noise: removes small components (lambda down, R slightly up).

#### Expected sensitivity

With N ~ 100-150 components per 1024 px tile (from F05), the standard error of R under CSR is ~0.26 / sqrt(N) = 0.02-0.03 per tile and < 0.01 per image after pooling [clark1954]; a meaningful batch effect is |Delta R| >= 0.1, which is well above sampling noise but must be checked against the failure-tile effect (one failed tile per image can shift R by more than that; inferred). The harness must report R with and without `t1 < 60` tiles.

#### Keep/drop test

T2 confound screen with `t1` and the failure-tile fraction added; T5 failure-tile exclusion must leave batch ordering unchanged; T3 robustness: R must be invariant to the 0.8x-1.25x rescale row (it is scale-free by construction; a drift means the component floor is driving it) and change by < 0.05 under gamma 0.9-1.1. Drop if the with/without-failure-tiles versions disagree in sign of the batch effect, or if |rho(F06, F05)| > 0.8 across images (then it is a re-expression of count density).

#### Redundancy

Expected to correlate with F05 (through lambda and through fragment clusters) and inversely with F04 (large agglomerates segment as one large component, which removes the cluster from the centroid set and raises R). F06 is kept because it is the only pre-registered feature that speaks to spatial arrangement; cut priority 4, after F11, F07, F10.

### F07: class-2 solidity

#### Definition

For each class-2 component, solidity = A / A_convex-hull (`skimage.measure.regionprops` "solidity"), dimensionless 0-1; feature = area-weighted median over components with A >= 50 px (below ~50 px the convex hull is dominated by pixelation and solidity is near 1 for any shape; inferred, to be confirmed by the harness on synthetic discs). Border: components touching a tile border are excluded (a cut particle has an artificially straight edge and high solidity). 2D vs 3D: section shape of a 3D body depends on the cut; a cracked sphere sectioned off-crack looks solid. Compared between batches under the same protocol only [russ2000].

#### What it should detect in this material

Observed in literature: Si particles crack and pulverise on lithiation [liu2012, mcdowell2013, obrovac2014]; cracks and fragmentation have been quantified in 3D images of Si-graphite anodes [muller2018].
Inferred by us: a cracked or partially delaminated particle sectioned through the crack has concavities (solidity down); an agglomerate of fragments also has low solidity. v1 has no value; particles are small (median 8 px), so only the tail above ~50 px area (~8 px diameter) carries information.

#### Known confounds

Noise roughens boundaries (solidity down); blur and the 5 px median filter smooth them (solidity up); lower `t1` grows particles into their halo (up) and, in failure tiles, produces thin texture outlines with very low solidity (down, strongly); edge-charging rims (up, rims fill concavities). Pixelation at 8 px makes solidity quantised. Because Batch_3 is less noisy (median 37.7 vs 46.3 / 44.4) and sharper by the Laplacian metric, F07 is expected to be batch-confounded by acquisition in v1 unless restricted to large components.

#### Expected sensitivity

Not measured. For a disc of 40 px diameter rasterised with Gaussian noise sigma ~ 5-8 grey levels the solidity change is of order 0.01-0.03 (inferred); a crack that removes 10 % of the area from a convex outline lowers solidity by ~0.1. The meaningful band is therefore |Delta| >= 0.05 on the >= 50 px subset, with the robustness panel's noise and blur rows required to move it by < 0.02.

#### Keep/drop test

T3 robustness is decisive: solidity must shift by < 0.02 under noise sigma 2-8 and blur 0.5-1.5 px (FRAMEWORK §13.3); T2: |rho| with `noise_sigma` < 0.5 across images; T5 failure-tile exclusion. Drop if the noise/blur rows move it by more than any batch gap (expected on current evidence) or if fewer than 20 qualifying components per image exist.

#### Redundancy

Expected to correlate with F04 (large particles are the ones with measurable shape) and with F11 (concavities at particle edges are often void-filled). Cut priority 2 (consultant's order), because it is the feature most exposed to the noise/sharpness axis that already separates batches in v1 and so would most likely be reading acquisition.

### F08: class-0 local thickness median

#### Definition

For every class-0 pixel, local thickness = diameter of the largest disc fully inside class 0 that contains the pixel [hildebrand1997, dougherty2007] (2D version: distance transform -> local maxima -> disc painting); F08 = median over class-0 pixels, in px; per-image from the whole-image mask (the 50 % tile overlap makes tile means redundant). Border: discs are clipped at the image frame; exclude pixels within half the maximum thickness of the frame. 2D vs 3D: the 2D local thickness of a section is biased low relative to the 3D local thickness (a channel cut obliquely yields an inscribed disc no larger than its 3D diameter; a sphere cut off-centre yields a smaller disc) [hildebrand1997]; batch-comparable only. If 25 nm/px is true, the v1 proxy (class-0 region equivalent diameter median 10.5 px) is ~260 nm.

#### What it should detect in this material

Observed in literature: pore width governs electrolyte transport and tortuosity, which is one of Polaron's four standard metrics [kench2021, cooper2016]; FIB-SEM-based pore-space quantification is established for Li-ion electrodes [hutzenlaub2013]; the carbon-binder domain's nanoporosity is resolved by FIB-SEM [vierrath2015], so part of the thin class-0 population is CBD porosity rather than inter-particle voids (lumped, per the Polaron caveat).
Inferred by us: a batch with coarser pores (less calendering, or voids left by expanded-then-contracted silicon) raises the median; a batch with more CBD-filled space lowers it.

#### Known confounds

Noise is the serious one: the v1 proxy (class-0 region equivalent-diameter median) has rho = -0.63 with `noise_sigma` and -0.62 with `sharpness` across images, and noise is the covariate that separates Batch_3 from Batches 1-2 (gap 3.2x IQR). Two mechanisms are plausible and pull in opposite directions (inferred): noise fragments thin dark regions into sub-20 px pieces that are deleted, biasing the surviving population to thicker regions (median up); or noise pushes isolated dark pixels across `t0`, breaking regions into many small survivors (median down). The observed negative sign favours the second, but the direction must be settled by the synthetic-noise row of the robustness panel before F08 is interpreted. Curtaining: vertical dark stripes are thin and long and should lower the median, yet the proxy's rho with `curtaining_score` is +0.34; likewise unresolved. `t0`: a higher `t0` grows class 0 (thickness up). Multi-Otsu failure: little effect (class 0 depends on `t0`). Tile seams: thresholds differ between adjacent tiles, so a region spanning a seam can be split; compute on a seam-free whole-image mask or on the tile union.

#### Expected sensitivity

Proxy B3 MAD 0.28 px on a median of 10.5 px (2.7 %), batch medians 9.9 / 10.3 / 10.5: a tight quantity, so a meaningful change is >= 1 px (10 %), but only after the noise dependence is removed (the noise gradient implied by rho -0.63 and the Batch_3 noise gap is of the same order; inferred).

#### Keep/drop test

T2 is decisive and pre-declared: F08 is kept only if, after regressing out `noise_sigma` across the 31 images (and equivalently within acquisition groups, LOGO), the residual still orders batches the same way, and |rho(F08, noise)| within Batch_3's low-noise and high-noise clusters is < 0.5; T3 robustness: noise sigma 2-8 and synthetic-curtaining rows must move it by < 0.5 px. Drop (demote to acquisition covariate) if the noise row of the robustness panel reproduces the observed between-batch difference.

#### Redundancy

rho(proxy, F01) = 0.31, rho(proxy, class-0 mean area) = 0.25. Kept with F01 because fraction and width are distinct axes; if F08 fails T2 it is cut before F01 (priority 6).

### F09: class-0 chord-length anisotropy (x/y)

#### Definition

Chords = maximal runs of class-0 pixels along image rows (x) and along columns (y); F09 = mean chord length in x / mean chord length in y (or the ratio of the chord-length distribution means [torquato1993, torquato2002]), dimensionless; chords touching the image frame are discarded (border), chords >= 2 px only. Per-image from the whole-image mask. 2D vs 3D: this is anisotropy *within the section plane*; the orientation of the FIB face relative to the coating is unknown and no collector is in frame, so "y" is the image vertical, not the through-plane direction. The ratio is a 2D descriptor compared between batches under the same cut.

#### What it should detect in this material

Observed in literature: graphite flake alignment makes electrode tortuosity anisotropic (in-plane vs through-plane) [ebner2013]; chord-length distributions are the standard orientation-sensitive descriptor for two-phase media [torquato1993].
Inferred by us: pores between aligned flakes are elongated along the flake direction, so F09 != 1 indicates aligned flakes (or aligned cracks) in the section; a batch with a different calendering pressure or flake morphology would change the ratio. Overlays in `results/audit/overlays/` show elongated inter-flake voids, so F09 is expected to be well away from 1 in all batches.

#### Known confounds

Curtaining is the direct one: ion-milling stripes are vertical in the image [munch2009, fitschen2017, roldan2024], so dark stripes add long y-chords and pull F09 down; the v1 BSE curtaining range is narrow (0.019-0.027) and does not separate batches, but the Inlens channel shows it more strongly and a batch milled differently would. Noise: breaks long chords in both directions equally (ratio robust; inferred). `t0`: grows class 0 isotropically (ratio robust). Scan direction / drift: horizontal line-to-line jitter adds x-chords (ratio up). Multi-Otsu failure: no effect (class 0). Tile seams: chords must be measured on the whole-image mask.

#### Expected sensitivity

Not measured. For the v1 proxy class-0 region sizes (~10 px equivalent diameter) and chords of a few to tens of px, a ratio difference of >= 0.1 between batches with an image-level MAD of a few hundredths is the meaningful band (inferred); the synthetic-curtaining row (stripes of amplitude 5-20 grey levels, FRAMEWORK §13.3) must move F09 by < 0.05 for it to count as material.

#### Keep/drop test

T2: |rho(F09, `curtaining_score`)| < 0.5 across images and within LOGO groups; T3: synthetic-curtaining row shift < 0.05 and rescale row leaves the ratio unchanged (scale-free); T4 split-half: top/bottom half-image ratio difference < 0.05. Drop (demote to curtaining covariate) if the synthetic-curtaining row shift exceeds any batch gap.

#### Redundancy

Expected modest correlation with F08 (thin pores are the elongated ones) and with F01. Kept as the only orientation-sensitive measure; cut priority 7 (last among the non-anchors) because it is cheap, scale-free and has a clear confound test.

### F10: within-image IQR of class-0 fraction over 512 px windows

#### Definition

Tile the whole-image class-0 mask into non-overlapping 512 x 512 px windows (edge windows dropped), compute phi_0 per window, F10 = IQR (p75 - p25) of those values, dimensionless; per image, one value from ~50-100 windows. Border: non-overlapping windows avoid the double counting of the 50 %-overlap tiles; drop partial windows. 2D vs 3D: a within-section heterogeneity measure; its magnitude depends on window size relative to the microstructure's correlation length (representative-area argument, [kanit2003]), so 512 px must be fixed and the same for every image. If 25 nm/px is true a window is 12.8 um.

#### What it should detect in this material

Observed in literature: meso-scale inhomogeneity of electrodes degrades durability and localises damage [harris2013]; representativity of a field of view is a function of window size and phase fraction, and can be predicted from a single image [kanit2003, dahari2025].
Inferred by us: a batch with patchy porosity (uneven calendering, agglomerated binder, locally detached silicon) has a larger F10 at the same F01; a uniform electrode has a small one. The v1 proxy (SD of phi_0 over 1024 px tiles) has batch medians around 0.02 with no separation.

#### Known confounds

Window size (declared and fixed). Threshold seams: v1 thresholds are per 1024 px tile, so adjacent windows can sit under different thresholds and the seam variance adds to F10; the harness must either compute windows inside single tiles or use the S4 challenger's per-image thresholds. Noise: rho(proxy, noise) = -0.14 (weak). Curtaining: stripes are vertical and long, so they raise phi_0 in the columns they cross and inflate the IQR across windows (up). Multi-Otsu failure: no effect (class 0). Sampling: F10 is itself a spread estimate from ~50-100 windows and has a standard error of ~10-15 % (inferred, bootstrap in harness).

#### Expected sensitivity

Proxy: tile SD median 0.021 (1024 px tiles); at 512 px the IQR will be larger (~0.03-0.04, inferred from the variance scaling of a 4x smaller window). Meaningful change: >= 50 % relative between batch medians, with the window bootstrap SE < 15 %.

#### Keep/drop test

T4 is decisive: the within-image bootstrap SE of F10 must be < 0.5 x the between-image B3 MAD, else F10 is not estimable per image; T2 confound screen with curtaining; T1 computed at thresholds x0.9 / x1.1 (an IQR that doubles with the threshold is reading seam/threshold variance). Drop if rho(F10, F01) > 0.7 across images (then it is F01 restated through binomial variance) or if T4 fails.

#### Redundancy

rho(proxy, F01) = 0.63 and rho(proxy, class-0 mean area) = 0.49: heterogeneity of a fraction scales with the fraction and with region size by construction. Cut priority 3 (consultant's order) because it is the most derivative of F01 and the costliest to make seam-free.

### F11: class-2 perimeter fraction adjacent to class 0

#### Definition

On the whole-image mask, for every class-2 boundary pixel (inner boundary, 4-connectivity) record the class of the adjacent non-class-2 neighbour(s); F11 = N(class-2 boundary pixels with at least one class-0 neighbour) / N(class-2 boundary pixels), dimensionless 0-1. Boundary pixels at the image frame are excluded. 2D vs 3D: interface fractions on a random section estimate interface-area fractions in 3D (surface density S_V = (4/pi) L_A, [russ2000]), but digital perimeter estimates are biased and orientation-dependent unless a Crofton-type estimator is used [legland2011]; as a ratio of two perimeters measured the same way the bias largely cancels, and we compare between batches only.

#### What it should detect in this material

Observed in literature: repeated expansion/contraction of silicon detaches it from the surrounding matrix and binder, creating voids around particles, which is a named degradation mechanism of alloy anodes [obrovac2014, mcdowell2013].
Inferred by us: silicon surrounded by graphite/binder (class 1) reads as "bonded", silicon bordered by void (class 0) reads as "debonded or sitting in a pore". A batch with poor binder coverage or with cycled, contracted silicon would show a higher F11. In the delivered images no cycling history is known, and no chemistry beyond the Polaron identities is claimed: F11 is a geometric contact fraction, nothing more.

#### Known confounds

The feature sits on both thresholds at once: a higher `t0` grows class 0 into the particle halo (F11 up); a lower `t1` grows class 2 (F11 changes sign-ambiguously depending on what the halo is); failure tiles produce texture outlines in a graphite matrix (F11 down, they are bordered by class 1). Edge charging and the BSE edge effect brighten particle rims and darken the immediate surround (a dark "trench" around bright particles is a classic BSE/SE edge artefact [goldstein2018]), which would create apparent void adjacency around every particle (F11 up) irrespective of material. Blur widens the transition zone so that a thin dark ring appears between class 2 and class 1 when `t0` and `t1` are both inside the ramp (F11 up). Noise roughens boundaries (more boundary pixels, ratio roughly stable). Perimeter estimation bias [legland2011] cancels in the ratio.

#### Expected sensitivity

Not measured. The +/-10 % threshold perturbation moves F02 by 30-45 % relative; the boundary-pixel population is far more threshold-sensitive than the area, so a +/-0.1 change in F11 under x0.9 / x1.1 is expected (inferred). A meaningful batch effect would need |Delta F11| >= 0.15 and stability under the blur and gamma rows.

#### Keep/drop test

T1: |Delta F11| at x0.9 / x1.1 < 0.5 x claimed gap; T3: blur 0.5-1.5 px and gamma 0.9-1.1 rows move it by < 0.05; T2: |rho| with `edge_charging` and `sharpness` < 0.5; T5 failure-tile exclusion. Drop if T1 or the blur row fails. On current evidence this is the feature most likely to be dropped.

#### Redundancy

Expected to correlate with F07 (concave, cracked particles have void-filled concavities), with F01 (more void everywhere means more void adjacency) and with F05 (texture components are bordered by class 1). Cut priority 1 (consultant's order); its information is partly recoverable from F01 x F02 plus F07.

## 4. What we deliberately do not measure, and why

- **Orientation and depth features (through-plane gradients, distance to collector, top vs bottom of coating).** FRAMEWORK §00 lists a "top-to-bottom gradient across the coating" as a differentiator; it is withdrawn for this dataset because no collector or free surface is in frame: the edge dark fraction equals the mid-image dark fraction in all 31 BSE images (PR #1 / PROJECT_STATE decision log), so there is no reference direction along which a gradient could be defined. F09 keeps the in-plane anisotropy only, labelled as image x/y, not in-plane/through-plane.
- **Class-1 (graphite) flake instance metrics (flake count, flake size, aspect ratio).** Class 1 occupies 0.80-0.83 of the area and forms a connected matrix in every tile; instance segmentation of flakes in a connected phase requires watershed or learned boundaries that we have no labels to validate, and flake sections are 400-600 px, which also breaks the feature-size assumption of the single-image representativity method [dahari2025] (`docs/READ/Method Evidence for Layers.md`, Layer C). Graphite is characterised indirectly through its complement (F01, F08, F09) and through the frozen embeddings, which see texture without instance boundaries.
- **The pre-registered Tier 3/4 dimensions.** As we understand the tiering, these are quantities that a single 2D BSE section at this pixel size cannot support without further evidence: chemistry beyond the Polaron-stated identities (Si vs SiOx, SEI, binder distribution, lithium plating; AGENTS.md scientific rules), 3D connectivity and transport properties (tortuosity factor, effective diffusivity; 2D values from TauFactor [cooper2016] are indicative only and listed as an optional late layer in FRAMEWORK §4 Phase E), and absolute particle number densities or 3D size distributions (Wicksell unfolding needs a shape model [wicksell1925]). They are not pre-registered as batch separators; if any is computed later it is labelled exploratory.
- **Two-point correlation length (`tpc_length` in `configs/v1.yaml`).** Not computed in v1 and not in the consultant's list; it is reserved for the ImageRep / Devin challenge layer [dahari2025, kench2021], where it serves the per-image uncertainty on F01 and F02 rather than acting as a separate batch feature.
- **Anything computed on Inlens or ETD/SE.** Phase features use BSE only (composition contrast, least charging [goldstein2018]); the other channels provide artefact covariates (`edge_charging`, curtaining) and are never segmented into phases.
- **Absolute units.** Nothing is reported in nm or um until the 25 nm/px pixel size is confirmed; all "if 25 nm/px is true" conversions in this dossier are illustrative.

## 5. How the harness applies the tests (declared once, referenced above)

| Test | What is computed | Pass | Fail consequence |
|---|---|---|---|
| T1 threshold sensitivity | feature at thresholds x0.9, x1.0, x1.1 per image (v1 does this for F01/F02; harness extends to all) | median abs change < 0.5 x claimed batch gap (or < 1 B3 MAD when no gap is claimed) | feature reported "within segmentation uncertainty"; no verdict weight; drop if it also fails T4 |
| T2 confound screen | Spearman rho with `noise_sigma`, `sharpness`, `curtaining_score`, `edge_charging`, mean intensity, `t0`, `t1` over 31 images; batch effect recomputed within the 13 (height, res-tag) acquisition groups (LOGO) and after regressing out noise | all abs rho < 0.5 and batch ordering unchanged under LOGO | demote to acquisition covariate (kept in the artefact panel, excluded from material drivers) |
| T3 robustness panel | FRAMEWORK §13.3 perturbations (gamma, noise, blur, synthetic curtaining, rescale, crop); per-image rank correlation with unperturbed, batch-median ordering | rank rho >= 0.8 for every row; ordering unchanged; scale-free features invariant to rescale | `investigate`; drop if a single row reproduces the between-batch difference |
| T4 split-half repeatability | feature on left/right (or top/bottom) half-images, 31 x 2 values | median within-image difference < 0.5 x B3 MAD | feature not estimable per image; drop |
| T5 failure-tile exclusion | class-2 features with and without `t1 < 60` tiles | same sign and ordering of batch effect | `investigate`; the S4 challenger decision is escalated |
| LOIO / LOGO contribution | W2 logistic regression (image-level, leave-one-image-out and leave-one-group-out), with and without the feature, with and without artefact covariates | feature is among the top drivers or its removal costs >= 1 image of accuracy | not a drop criterion on its own (anchors F01/F02 are reported regardless); used to order cuts among F05-F11 |

Hierarchy is respected throughout: the image is the unit of every permutation, bootstrap and fold; tiles and windows are pseudo-replicates [saravanan2019] (preprint, cited for the hierarchical-bootstrap procedure only). Every statistic carries n images, the effect size and the null band (FRAMEWORK §00 rule 4).

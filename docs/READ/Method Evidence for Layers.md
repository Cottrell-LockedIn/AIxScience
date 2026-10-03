# Method Evidence for the Approved Layers

Approved on 2026-10-03: the additions are layers on the four features, not new features. This note records which published method each layer is based on, so that the README can cite them and nobody re-derives them at 3 am. Sources verified in this session; preprints and vendor pages are labelled.

## Layer A. Artefact-vs-material separation

**Curtaining (vertical stripes from ion milling).**

- Quantify, do not just remove: Prill, Schladitz et al. (KIT, Journal of Microscopy, "Image quality evaluation for FIB-SEM images") introduce dedicated no-reference indices for curtaining and charging alongside contrast, noise and blur. Our `curtaining_score` follows the same idea in its simplest form: ratio of spectral power in a narrow band around the vertical-frequency axis (horizontal frequency ~ 0, vertical frequency above a cut-off) to total power in that frequency range. Report per image and per batch.
- Removal when needed: Munch et al. 2009, Optics Express, "Stripe and ring artifact removal with combined wavelet-Fourier filtering" is the standard for FIB-SEM "waterfall" artefacts; implementable with `pywt` + numpy in ~30 lines (decompose, damp the vertical-detail coefficients along the stripe direction with a Gaussian in Fourier space, reconstruct). Newer variational methods (arXiv 2401.14220, 2024) are better but heavier; not needed here.
- Protocol: compute every KPI on raw and on destriped images; report whether any batch conclusion changes. If it does, the conclusion is fragile and goes to `investigate`.

**Edge brightening / charging.**

- The bright halos at particle edges in the Inlens channel are the SE edge effect plus charging. Score = mean intensity in a 3 to 6 px band around segmented particle boundaries divided by particle-interior mean. Also border gradient (outer 5% of the frame vs centre) for frame-level charging.
- Use BSE, not Inlens, for phase-fraction KPIs: BSE is far less affected by charging and carries composition contrast.

**Artefact ablation in the classifier (the wow).** Train W2 with and without artefact covariates; if accuracy drops a lot without them, batches differ by acquisition. This is a plain feature-ablation study; no special citation needed, but phrase it as the Polaron "next step" answered.

## Layer B. Phase segmentation and KPIs on BSE

- Two-threshold (multi-Otsu, 3 classes) segmentation of BSE into pore / graphite / high-Z phase is the standard first pass for Si-graphite composite cross-sections (e.g. FIB-SEM and XCT characterisation of Si-based anodes, where phases are separated by iterating threshold intervals plus watershed / random walker). Apply a median or non-local-means denoise first because BSE is grainy.
- Known pitfall from the Si-graphite literature (e.g. arXiv 2508.06413, 2025, preprint): nanoscale Si (~200 nm) mixed into the binder is not resolvable and clusters into CBD-Si domains; only the large Si/SiOx particles are countable. At 25 nm/px, 200 nm = 8 px, so small Si is at the resolution limit. Report the high-Z fraction as "resolvable high-Z particle fraction", not total Si content.
- KPI vocabulary: Polaron's founders validate microstructures with phase volume fraction, two-point correlation, particle size and tortuosity/relative diffusivity (SliceGAN, Nature Machine Intelligence 2021; MicroLib, Scientific Data 2022; ImageRep, Advanced Science 2025). Using the same four quantities makes our KPIs immediately legible to the judges.
- Threshold-sensitivity: recompute each KPI at threshold +/-10% grey levels; report the KPI change next to the batch effect. This is the segmentation-uncertainty term.

## Layer C. Single-image uncertainty (ImageRep)

- Dahari et al., Advanced Science 2025 (peer reviewed), code BSD-3. Gives a confidence interval on a phase fraction from one binary image via the two-point correlation. Assumptions: credible binary segmentation, >= 200 px, feature size <= ~70 px, non-periodic. Graphite flakes here are 400 to 600 px, which **breaks the feature-size assumption for the graphite phase**; the high-Z particles (tens of px) and the pore phase are likelier to satisfy it. Apply ImageRep to the high-Z phase fraction and pore fraction only; state why.
- This doubles as the Devin challenge reproduction target.

## Layer D. Batch statistics with few images

- Tiles from one field of view are pseudo-replicates; hierarchical structure must be respected (hierarchical bootstrap literature, PMC9098003, peer reviewed). Rule: image is the unit; permutation and bootstrap resample images, never tiles.
- Two-sample tests on embeddings: energy distance and MMD with permutation p-values are the standard (Gretton et al., JMLR 2012 for MMD; Szekely & Rizzo for energy distance). With 7 vs 7 images the minimum achievable permutation p-value is 1/C(14,7) = 0.0003, which is fine, but power is low; always report the effect size and the null band, not only p.
- Embedding backbone: DINOv2 (Oquab et al., 2023; Apache-2.0) patch features are the current default for frozen-feature industrial inspection (PatchCore-style memory banks, Roth et al., CVPR 2022). LIBAD (arXiv 2608.07958, preprint) is the warning that per-image anomaly scores on homogeneous electrode material give high false-positive rates; hence batch-level aggregation.

## Layer E. Physics touch (optional)

- TauFactor (tldr-group; Cooper et al., SoftwareX 2016; TauFactor 2 in JOSS 2023) computes tortuosity factor from a segmented phase. 2D values are indicative only; say so. Only if W1, W2 and the screen are stable.

## Explicitly not adopted

- Fine-tuning a segmentation foundation model (micro-sam etc.) on 31 images: no labels, no time.
- Per-tile anomaly maps as a verdict: visual layer only.
- Any claim of chemistry (Si, SiOx, binder) without Polaron confirmation or EDS.

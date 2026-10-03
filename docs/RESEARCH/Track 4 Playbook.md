# Track 4 Playbook

## Objective

Compare each incoming electron-microscopy batch with an approved baseline and produce a defensible `accept`, `investigate` or `reject` decision.

The primary target is batch-level distribution change—not isolated unusual patches.

## Dataset inspection gate

Before selecting models:

1. inventory files, metadata and identifiers;
2. determine batch → specimen → image → tile hierarchy;
3. inspect magnification, pixel scale, detector settings and overlays;
4. mask scale bars, text, borders and interface annotations from model inputs;
5. preserve those items as metadata;
6. test whether acquisition conditions are comparable;
7. establish baseline-to-baseline variation by repeatedly making pseudo-batches from baseline images or specimens.

Poor acquisition should route to `investigate`; it must not silently remove inconvenient images.

## Evidence lanes

### 1. Interpretable KPI lane

Use only 3–5 validated primary KPIs.

Possible KPIs, conditional on the data:

- phase or region area fraction;
- pore or crack fraction;
- particle-size distribution;
- aspect ratio or circularity;
- boundary or interface density;
- spatial correlation length or texture.

Use physical units only when pixel scale is known. Otherwise identify results as pixel-domain exploratory measurements.

If phase identity is unsupported, use terms such as `image region` or `intensity class`, not NMC, CBD, pore or chemistry.

Manually audit a small stratified mask sample and perturb thresholds to measure KPI stability.

### 2. Frozen-feature challenger

Evaluate one frozen representation against simpler baselines.

Candidates:

- handcrafted intensity, edge and texture features;
- ResNet/PatchCore;
- DINOv2 patch embeddings.

DINOv2 is not mandatory. Select it only if leakage-safe validation shows useful improvement. Generic embeddings may learn magnification, scale bars or detector texture.

DINOv3 is optional only if access is already approved and its custom licence is accepted. Do not spend event time chasing access.

### 3. Batch-comparison layer

For acquisition-matched comparisons:

- create a reference-to-reference null from baseline pseudo-batches;
- compare KPI distributions with effect sizes and image/specimen-level permutation or hierarchical bootstrap;
- compare embedding distributions using energy distance, MMD or a carefully cross-validated classifier two-sample test;
- aggregate evidence using median, upper quantile and affected-image prevalence;
- never let a single extreme tile determine the batch verdict;
- expose acquisition covariates alongside material evidence.

Calibrate decision bands from baseline variability and known batches when available. If the number of independent units is too small, report descriptive uncertainty rather than formal coverage.

## Optional ImageRep diagnostic

ImageRep may estimate uncertainty in a chosen segmented phase fraction from one image.

It is not a universal field-of-view representativity test. It does not validate crack density, particle-size distribution, morphology, embeddings or anomaly maps.

Use it only when its assumptions hold:

- a credible binary segmentation;
- at least 200 × 200 pixels;
- relevant feature size no larger than about 70 pixels;
- non-periodic structure;
- segmentation uncertainty assessed separately.

General field-of-view adequacy must be evaluated through between-image sampling and KPI stability.

## Verdict logic

- `Accept`: acquisition is comparable and batch evidence lies within frozen baseline bands.
- `Investigate`: acquisition failure, inadequate sampling, conflicting evidence, marginal change or unfamiliar structure.
- `Reject`: repeated, substantial batch-level change with a localized and scientifically meaningful driver.

Do not report a calibrated probability unless calibration data genuinely supports it.

## Unseen-batch protocol

Freeze the complete pipeline before the unseen batch:

- preprocessing;
- exclusions and masks;
- feature extractor;
- KPI definitions;
- image-to-batch aggregation;
- thresholds and uncertainty rules.

Record a commit/hash and timestamp. Post-drop changes are exploratory and must be labelled.

## Thirty-hour scope

Must ship:

1. acquisition and metadata audit;
2. reference-to-reference null;
3. 3–5 validated KPIs where supported;
4. one frozen-feature challenger;
5. batch-level comparison and honest abstention;
6. one-screen demonstration with cached fallback.

Only attempt later:

- ImageRep under valid assumptions;
- Modal endpoint;
- additional segmentation models.

Avoid unless uniquely enabled by the dataset:

- foundation-model fine-tuning;
- DA-Core reimplementation;
- 3D reconstruction;
- causal performance predictions;
- elaborate frontend engineering;
- conformal guarantees from a tiny calibration set.

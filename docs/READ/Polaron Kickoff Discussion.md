# Polaron Kickoff Discussion (notes as given, 2026-10-03, T+1h)

Source: team notes from the initial conversation with Polaron mentors. Organiser-provided; treat as authoritative over public listings.

## Battery cell microstructure overview

- Electrode material: ~30 microns wide, rolled onto metal sheet inside a can
- Materials expand and contract 20–200% during charge/discharge cycles
- Huge internal pressure builds over cycles, causing particle cracking
- Cracking is a core microstructural failure mode

## Data characteristics and constraints

- Images collected via ion-beam microscopy (FIB-SEM style), cutting cells in half
- Each image takes ~6 hours to collect on a machine costing over £1M
- File sizes range from 18 MB to gigabytes per image
- Largest datasets are only in the hundreds of images: no large-scale collection feasible
- Three batches provided, plus three held-back images for later testing

## The core challenge: batch classification and explainability

- Goal: distinguish and categorise batches as if receiving from different suppliers
- ML output must be explainable, not just a label
  - Manufacturers won't deploy black-box models
  - Decisions must map to physically interpretable features
- No "good" or "bad" ground-truth labels: only batch membership
- Some apparent features may be imaging artefacts, not real microstructure
  - Example: faint vertical lines from ion beam, bright edge regions
  - Even artefacts may correlate with underlying chemistry, so nothing should be discarded outright

## Supply chain accountability

- Five main stakeholders: powder suppliers, cell manufacturers, automotive OEMs, and end users
- Batch differences could originate at any point in the chain
- Billions of pounds lost annually in automotive recalls when fault cannot be proven
- Root-cause analysis using this data could assign liability: "this material was outside statistical bounds, it's your fault"
- Explainable ML output is key to making that legal/commercial case

## What success looks like

- Fast, reliable supplier selection and quality-control decisions
- Identify which supplier is most consistent across repeats
- Combine ML with physics-based simulation where useful
- Workflow acceleration on subtle, high-dimensional data is the core value

## Next steps (from Polaron)

- Attempt batch classification on the three provided batches; identify distinguishing features and prepare explainable rationale before the held-back test images are released
- Investigate imaging artefacts vs. true microstructural features; determine which visual elements are ion-beam artefacts and which reflect real material differences

## What this changes versus the pre-event assumptions (Devin's reading)

| Pre-event assumption | Now known | Consequence |
|---|---|---|
| Known acceptable and defective batches | Only batch membership; no good/bad labels | "Supervised defect detection" becomes supervised **batch-membership** classification; `accept/reject` cannot be calibrated on labelled defects, so it must be expressed as "inside / outside the baseline's statistical bounds" |
| Unseen *batch* drops at ~T+8 | Three held-back **images** | Test task is per-image: which batch does each image belong to, with what confidence, and why. Accuracy on 3 images is a coin-flip-level sample; confidence and abstention matter more than the raw hit rate |
| Many images per batch | Hundreds at most across all data, likely a handful per batch | Image is the independent unit; tiles are pseudo-replicates. Use leave-one-image-out. Report n honestly |
| Unknown modality | FIB-SEM cross-sections, ~30 µm electrode | Cracks, pores, particle morphology are the physically meaningful KPIs; curtaining (vertical lines) and edge brightening are known artefacts |
| Artefacts should be masked out | Artefacts may correlate with chemistry; do not discard | Measure artefacts as separate covariates, report them alongside material KPIs, never silently remove |
| 18 MB to GB images | Confirmed | Tiling and out-of-core processing needed; Modal is genuinely useful for embedding GB images in parallel |
| Baseline + incoming batches | Three batches, no designated baseline (to confirm) | Either Polaron names a baseline, or we treat each batch as a candidate baseline and report pairwise distances plus within-batch consistency ("most consistent supplier") |

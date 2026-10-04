# Phase B gate report (exploratory, not frozen)

Branch `devin/1791064782-phase-b`, outputs at `d90cdea`, config hash `45629944e398`, stats config hash `e718e5866dea`.
Reference = Batch_3 (Polaron's supplier-promised baseline). Batch_1 and Batch_2 are described as different or not different from it, never as better or worse.
Unit = image (n = 31: 7 / 7 / 17). Phase names are stated by Polaron and not image-verified. All lengths are in pixels.
Rules were pre-registered in `docs/PHASE_B_PREREGISTRATION.md` and `configs/stats_v1.yaml` (`c55e1ae`) before any contrast was computed. Every later choice is listed in `docs/PHASE_B_DEVIATIONS.md`.

## Status

| Item | Status |
|---|---|
| Code exists | B1 `kpi`, B2 `features`, B3 `embed`, B4/B5 `stats`, B6 `register`/`charging`, B7 `verdict` |
| Code ran | Yes. Full fresh-clone rerun of `qc run` plus the Modal tasks plus `stats`/`verdict` (README "Regenerate Phase B") |
| Outputs match | Yes. Stats CSVs and verdicts: max abs diff 0. Masks: 1443/1443 byte-identical. Embeddings: max abs diff 0. KPI sensitivity: max abs diff 1.8e-15. Inspection PNGs: pixel-identical (metadata only) |
| Tests | `pytest`: 49 passed |
| Independent review | CONDITIONAL PASS on `7c43868`. Corrective actions 1–7 were applied in `0559a35`…`d90cdea`; a re-review of those changes is pending |
| Phase C / held-back images | Not started / not touched |

## Results

**Verdicts** (`results/verdicts/Batch_{1,2,3}.json`): all three are `investigate`. Each label, driver and acquisition flag carries the rule text, the numbers and pandas selectors into `results/stats/*.csv`. The tests execute every selector.

**Features (B5).** Of 23 measurements (12 KPIs + F01–F11): 0 keep, 6 investigate, 17 drop.
- None passes G1: the smallest family BH p is 0.207.
- Most drops come from G3: a ±10 % threshold shift moves the measurement more than Batch_3's own image-to-image spread (1.4826·MAD).
  - The extreme case is `c2_eqdiam_median_px`, with ratio 18.6. This is consistent with the per-tile multi-Otsu splitting seen in `docs/INSPECTION.md`.
  - The `c1_flake_*` metrics also fail G5, because class 1 percolates in 31/31 images.
- Investigate: `c0_region_area_mean_px`, `c0_cracklike_frac`, F08, F09, F10, F11.

**Distances vs Batch_3, BSE** (`results/stats/distance_matrix.csv`):

| Pair | Statistic | Raw value / BH p / band | Residualised value / BH p / band |
|---|---|---|---|
| Batch_1–Batch_3 | energy | 0.0907 / 0.0045 / outside | 8.7e-5 / 0.75 / within |
| Batch_1–Batch_3 | MMD² | 0.237 / 0.0045 / outside | 0.0015 / 0.75 / within |
| Batch_2–Batch_3 | energy | 0.0404 / 0.012 / outside (between on the exact null; 1.0 % of splits exceed) | −0.011 / 0.96 / within |
| Batch_2–Batch_3 | MMD² | 0.117 / 0.012 / outside | −0.042 / 0.96 / within |
| Batch_1–Batch_2 | energy | 0.0061 / 0.37 | — |

On the aggregate feature/KPI rms_z, every pair is within the null band (BH p 0.67, raw).

**Acquisition vs material.**
- The BSE-embedding difference from Batch_3 is significant for both batches, but it disappears after label-free residualisation on the 8 pre-registered acquisition covariates.
- No single covariate passes the pre-registered drift test (all BH p ≥ 0.249), so G2 does not fire.
- The post-hoc probe (`results/stats/exploratory_confound_probe.csv`, exploratory, not used by any gate) shows:
  - Residualising on `noise_sigma_BSE` alone (p 0.26) or `sharpness_BSE` alone (p 0.35) removes the Batch_1 difference. The other six covariates do not (p ≤ 0.015).
  - Eight random covariates leave a median energy of 0.055, so the effect is not from overfitting.
  - The covariates predict the batch label with R² 0.67 (p 0.018) for Batch_1 and 0.71 (p 0.0075) for Batch_2.
- Noise σ and sharpness are higher in Batch_1/2 than in Batch_3. Either acquisition or finer microstructure could produce that, so **acquisition and material contributions cannot be separated with these data**.

**Batch_3 reference check.**
- 3/17 images are leave-one-out outliers in ≥ 2 families.
- Every qualifying image involves a `drop`-status feature. Excluding drop features leaves 0 images, so the reference label rests on unreliable measurements.

**Consistency** (`consistency.csv`): no pair is separable on C_feat or C_emb.

**B6 registration.**
- 30/31 stems pass the same-FOV thresholds; max |shift| is 0.3 px; rotation ranges from −0.06° to 0.05°.
- `mgxahqnk` Inlens fails on scale (0.99732, versus the 0.002 tolerance) even with the log-polar step refined to about 0.00012.
- Its charging row is flagged `registration_same_fov=False`. Charging stays a sensitivity column; baseline F02 is unchanged.

**Compute.** Total Modal cost $0.70 for all runs, including the fresh-clone repeat (`results/MODAL_RUNS.csv`).
- Embeddings: about 56–127 s on an L4, versus 658 s on local CPU.
- KPI sensitivity: 74–93 s on Modal, versus 256 s locally.
- Feature sensitivity: 147 s on Modal, versus 331 s locally.

## On track for Polaron's criterion?

The criterion is to say what is different about each batch and to assign held-back images to Batch_1/2/3.

- **Supported:** at the image-distribution level, Batch_1 and Batch_2 each differ from Batch_3 in frozen BSE embeddings.
- **Not supported:**
  - No interpretable measurement explains the difference under the pre-registered gates.
  - Batch_1 and Batch_2 are not distinguishable from each other by any Phase-B statistic (energy p 0.37).
  - The embedding difference is collinear with BSE noise and sharpness.
- **Implication for Phase C:** a closed-set classifier will probably separate Batch_3 from {Batch_1, Batch_2} using embedding/acquisition-correlated signal, and will be weak between Batch_1 and Batch_2. Its explanations would have to say that the signal may be acquisition. Phase C, under the PR #9 contract, must report confidence honestly. It must also test leave-one-image-out accuracy with and without covariate residualisation, so the "in what way" claim is not overstated.

## Remaining before held-out / Batch_N use

1. Re-review of corrective actions 1–7, then owner decision on Phase C (needs explicit approval).
2. Ask Polaron whether acquisition settings (dwell, current, detector gain) differed between batches. That is the only way to separate acquisition from material.
3. Segmentation robustness (v2 candidate): per-image or global thresholds instead of per-tile multi-Otsu, and a continuous-radius F08. These are exploratory, and only allowed before freezing.
4. Freeze (`git tag v1-frozen`) before any held-back image is processed.

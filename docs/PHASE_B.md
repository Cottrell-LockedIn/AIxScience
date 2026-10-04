# Phase B gate report (exploratory, not frozen)

Branch `devin/1791064782-phase-b`, statistics/verdict outputs at `d90cdea`, config hash `45629944e398`, stats config hash `e718e5866dea`.
Reference = Batch_3 (Polaron's supplier-promised baseline). Batch_1 and Batch_2 are described as different or not different from it, never as better or worse.
Unit = image (n = 31: 7 / 7 / 17). Phase names are stated by Polaron and not image-verified. All lengths are in pixels.
Rules were pre-registered in `docs/PHASE_B_PREREGISTRATION.md` and `configs/stats_v1.yaml` (`c55e1ae`) before any contrast was computed. Every later choice is listed in `docs/PHASE_B_DEVIATIONS.md`.

## Status

| Item | Status |
|---|---|
| Code exists | B1 `kpi`, B2 `features`, B3 `embed`, B4/B5 `stats`, B6 `register`/`charging`, B7 `verdict` |
| Code ran | Yes. Full fresh-clone rerun of `qc run` plus the Modal tasks plus `stats`/`verdict` (README "Regenerate Phase B") |
| Outputs match | Yes. Fresh clone of `7c43868` (`results/repro/fresh_clone_7c43868.csv`, 48 rows): stats CSVs and verdicts max abs diff 0; masks 1443/1443 byte-identical to the Phase-A reference; `emb_per_tile.npy` max abs diff 0; KPI sensitivity max abs diff 1.8e-15; inspection PNGs pixel-identical (metadata differs). Post-fix recheck of register/charging/stats/verdict at `d90cdea`: 16/16 identical (`results/repro/fresh_clone_post_fix_d90cdea.csv`) |
| Tests | `python -m pytest -q`: 53 passed |
| Independent review | CONDITIONAL PASS on `7c43868`; delta re-review of `7c43868..2241037` also CONDITIONAL PASS (all 7 first-round actions confirmed; labels/statuses unchanged). Second delta re-review of `2241037..516f62d`: CONDITIONAL PASS (round-2 actions 1–4 and 6 done; registration test passed for the wrong reason). Third delta re-review of `516f62d..ec369f1`: **PASS** (round-3 actions confirmed; sweep and repro scripts re-run byte-identically; one optional wording fix applied). Phase-B results remain exploratory, not frozen |
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

On the aggregate rms_z, Batch_1–Batch_3 and Batch_2–Batch_3 are within the null band for both KPIs and features (BH p 0.67 raw, 0.96 residualised). Batch_1–Batch_2 has no null band (the null is built from Batch_3 only); its BH p is 0.67.

**Acquisition vs material.**
- The raw BSE-embedding difference from Batch_3 is significant for both batches. It is absent after label-free residualisation on the 8 pre-registered acquisition covariates (BH p 0.75 and 0.96).
- No single covariate differs significantly from Batch_3 (all BH p ≥ 0.249), so G2 does not fire. Medians of BSE noise σ (46.3 / 44.4 vs 37.7) and sharpness (2349 / 2187 vs 1640) are higher in Batch_1 / Batch_2 than in Batch_3, but not significantly.
- Post-hoc probe (`results/stats/exploratory_confound_probe.csv`, exploratory, not used by any gate or label):
  - Batch_1: residualising on `noise_sigma_BSE` alone (p 0.26) or `sharpness_BSE` alone (p 0.35) removes the difference; each of the other six leaves it (p ≤ 0.015). Eight random Gaussian covariates leave median energy 0.055 (5th pct 0.023), so for Batch_1 the removal is not explained by fitting 8 columns to 24 images.
  - Batch_2: four single covariates each remove the difference (`noise_sigma_BSE` p 0.69, `sharpness_BSE` 0.66, `hstripe_score_BSE` 0.16, `edge_charging_Inlens` 0.17). Eight random covariates already reduce its energy from 0.040 to a median 0.024 (5th pct 0.004), against a 95 % band of 0.022, so for Batch_2 the residualised result is weak evidence either way.
  - The 8 covariates predict the batch label with R² 0.67 (p 0.018) for Batch_1 and 0.71 (p 0.0075) for Batch_2.
- Either acquisition or a real microstructure difference that also changes noise/sharpness could produce this, so **acquisition and material contributions cannot be separated with these data**.

**Batch_3 reference check.**
- 3/17 images are leave-one-out outliers in ≥ 2 families.
- Every qualifying image involves a feature that failed the gates (status `drop`). Excluding drop features leaves 0 qualifying images, so the Batch_3 `investigate` label rests on drop-status features.

**Consistency** (`consistency.csv`): no pair is separable on C_feat or C_emb.

**B6 registration.**
- 30/31 stems pass the same-FOV thresholds; max |shift| is 0.3 px; rotation ranges from −0.06° to 0.05°.
- `mgxahqnk` Inlens fails on scale (0.99732, deviation 0.0027 vs the 0.002 tolerance) even with the log-polar step refined to about 0.00012.
- The scale check is much less sensitive than its 0.002 tolerance. On a centre-scaled synthetic binary texture (`results/repro/registration_scale_sweep.csv`, `scripts/registration_scale_sweep.py`), small deviations (≤ 0.6 %) are shrunk towards 1 (identity gives exactly 1.0; larger ones of 0.8–1 % overshoot). The smallest flagged applied deviation was 0.5 % (scale 1.005); 0.4 % and smaller passed.
- So "30/31 pass" means no detector scale difference of about 0.5 % or more was detected, not that the views match within 0.2 %. `mgxahqnk` Inlens's estimated 0.27 % deviation is an **unconfirmed** scale difference: given the shrinkage, the true difference may be larger. No label uses registration; it only flags the charging sensitivity row.
- Its charging row is flagged `registration_same_fov=False`. Charging stays a sensitivity column; baseline F02 is unchanged.
- The registration refinement changed `glow_frac_of_c2` in 29/31 images (max |Δ| 0.169; `results/repro/charging_change_7c43868_to_d90cdea.csv`). Examples: `xgj4xftb` went 0 → 0.169 for a scale change of 0.00037 and `hawkfj64` 0 → 0.156 for 0.00049. For `xgj4xftb`, the cause is that its aligned Inlens 95th percentile sits at the 255 saturation level and moves to 254.19 after interpolation (`docs/INSPECTION.md`). `glow_frac_of_c2` is therefore unstable where Inlens saturates; no label uses it.

**Compute.** Modal cost: $0.70 in the committed run log (`results/MODAL_RUNS.csv`, development and post-fix determinism runs) plus $0.26 for the fresh-clone verification (`results/repro/fresh_clone_modal_runs.csv`), about $0.95 in total.
- Embeddings: about 56–127 s on an L4, versus 658 s on local CPU. Determinism: local vs Modal max abs diff 3.5e-5 (tolerance 1e-4), remote repeat diff 0 (logged in `MODAL_RUNS.csv`; the fresh-clone run did not log these columns).
- KPI sensitivity: 74–93 s on Modal, versus 256 s locally.
- Feature sensitivity: 147 s on Modal, versus 331 s locally.

## On track for Polaron's criterion?

The criterion is to say what is different about each batch and to assign held-back images to Batch_1/2/3.

- **Supported:** in raw frozen BSE embeddings, Batch_1 and Batch_2 each differ from Batch_3 at the image-distribution level. The difference is absent after acquisition-covariate residualisation.
- **Not supported:**
  - No interpretable measurement explains the difference under the pre-registered gates (0 keep).
  - No difference between Batch_1 and Batch_2 was detected by any Phase-B statistic (lowest BH p 0.264, 7 vs 7 images). This is absence of evidence at this sample size, not evidence that they are the same.
  - The embedding difference is collinear with BSE noise and sharpness.
- **Untested hypothesis for Phase C:** a closed-set classifier may separate Batch_3 from {Batch_1, Batch_2} using embedding/acquisition-correlated signal and be weak between Batch_1 and Batch_2. Phase C, under the PR #9 contract, must report confidence honestly and should test leave-one-image-out accuracy with and without covariate residualisation, so the "in what way" claim is not overstated.

## Remaining before held-out / Batch_N use

1. Owner decision on Phase C (needs explicit approval).
2. Ask Polaron whether acquisition settings (dwell, current, detector gain) differed between batches. That is the only way to separate acquisition from material.
3. Segmentation robustness (v2 candidate): per-image or global thresholds instead of per-tile multi-Otsu, and a continuous-radius F08. These are exploratory, and only allowed before freezing.
4. Freeze (`git tag v1-frozen`) before any held-back image is processed.

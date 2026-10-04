# Phase C review: `devin/1791080364-phase-c`

**FINAL VERDICT (fd12b02): PASS.** No blocking items remain. The close-out section is directly below. The original review (at e593c3e) follows it, unchanged.

## Close-out of fixes (e593c3e..fd12b02: b7d5556, bd8b9db, fd12b02)

- **Model unchanged.** I reran `python -m qc classify` in a `git archive` copy of fd12b02. Result: 18/31, p 0.03497, same confusion matrix. Compared with the committed files: `loio_predictions.csv` numeric max |diff| 0 and strings equal; `final_model.csv` diff 0; all 31 `loio_images/*.json` identical (excluding timestamp and git_sha); `loio_summary.json` differs only in git_sha. Every pre-existing column of `loio_predictions.csv` and `final_model.csv` is also identical to e593c3e. The tier rule is unchanged.
- **C1 closed.** In `heldout.run`:
  - `--dryrun` without `--input-dir` raises.
  - `--dryrun` on the configured `data/heldout` raises.
  - Dry-run on any non-training id raises, and so does any BSE whose sha256 is not byte-identical to `results/audit/images.csv:sha256_BSE`. A held-out image copied elsewhere therefore cannot pass as a dry-run.
  - `--exploratory` raises until `results/v1/heldout.json` exists.
  - The real run raises on a non-canonical `--out`, then keeps the existing-file, exact-tag and clean-tree checks.
  - Each path has a test in `tests/test_heldout.py`.
- **C2 closed.** Each bet's justification now carries `loio_reliability`, with two selectors that resolve and a reason sentence. I hand-checked three images:
  - `vc2whyaq`: Batch_2 2/8, high 1/2.
  - `3806gxp0`: Batch_2 1/8, high 0/2.
  - `uhdslk0o`: Batch_2 2/8, low 0/2.
  All match the CSV with the image excluded. Summary: `precision_by_pred_batch` B1 2/6, B2 2/9, B3 14/16; `accuracy_by_tier` high 14/18, medium 1/5, low 3/8. These match my original counts.
- **C3 closed.** `rank_p` and `n_null` appear in `open_set.justification.numbers`. For example, `uhdslk0o` has rank_p 0.0556 with n_null 17, the minimum achievable. The routing no longer says "99 % band", and the rule text states the 16–17-value null.
- **C4 closed.** `_file_key` resolves paths against the repo root, so the real run gives `data/heldout/...`. The dry-run's temporary folder sits outside the repo, so its paths are absolute and resolvable.
- **C5 closed.** The log section "Independent review fixes" lists no LOGO, no acquisition ablation, and an OOD+covariate-only label, all as owner-excluded.
- **Minor fixes closed.** `standardised_value` is renamed `model_input`, with units saying "raw PC score" for PCs. A Modal failure in a frozen real run now raises (`allow_local_fallback=False`), and there is a test for it.
- **Dry-run regenerated.** Modal L4, $0.00088 (third row in MODAL_RUNS_v1.csv). Parity is unchanged: features and embeddings diff 0, covariate diff 3.6e-15 on `nm_per_px_if_tag_true`.
- **Tests and scope.** `python -m pytest -q`: 74 passed, 0 skipped, 0 failed. The fix commits touch only classify.py, heldout.py, 2 test files, the Phase C log and results/v1/. No Phase A/B file changed.

**Non-blocking note.** `heldout_dryrun.json` is stamped `git_sha b7d5556`, so it ran before the bd8b9db heldout hardening was committed; that hardening code is in the output, but uncommitted at run time. Optionally re-run the dry-run (about $0.001) at the commit that will carry `v1-frozen`, so the tagged code has its own dry-run record.

---

## Original review (at e593c3e)

**VERDICT: CONDITIONAL PASS.** The numbers reproduce exactly and there is no leakage. Before tagging `v1-frozen`, fix the held-out run-once guard bypass (C1) and add the evidence that LOIO tier reliability depends on the predicted class (C2). C3–C5 are wording and evidence fixes. None of them changes the model.

## What I checked (evidence)
- **Reproduction.** Ran `python -m qc classify` in a `git archive` copy (19 s). Result: 18/31, perm p 0.0350, confusion matrix B1 [2,4,1] / B2 [4,2,1] / B3 [0,3,14]. Max |diff| = 0 for `loio_predictions.csv` (all numeric columns, all string columns equal), `final_model.csv` and all 31 `loio_images/*.json` (comparison excludes timestamp and git_sha). `loio_summary.json` differs only in git_sha.
- **Hand refit.** I refit the folds for `3806gxp0` and `uhdslk0o` with plain sklearn (11 F columns, float64 embeddings, PCA 29, same LR). Probabilities and top-3 drivers match the JSONs to 1e-6. For example, `3806gxp0`: p = (0.027504, 0.793979, 0.178517); drivers PC3 +0.5756, F06 +0.3182, F09 +0.2830.
- **Freeze ordering.** af87cd9 (02:19:52) is earlier than e6046e6 (02:23:24). The committed `loio_predictions.csv` rows carry `git_sha = af87cd9`, so classify ran with HEAD at the freeze commit, i.e. after it. The deviations are not result-driven:
  - PCA 29: the centred rank of 30 training images is ≤ 29.
  - Matched-size 1-vs-rest OOD band: a single image is not on the scale of a 7-vs-10 set statistic.
  - No nearest-distance fallback: the owner fixed one model.
  - Permutation p feeds the tier exactly as the PR #9 rule says.
  Caveat: `classify.py` was uncommitted when it ran, so only the result is pinned (to e6046e6). That reproduction passes.
- **Leakage.**
  - The scaler and PCA are fit per fold on 30 images (`fit_transform`). The full refit is asserted equal to `fold_designs`.
  - The permutation test reuses label-free designs. This is valid because the scaler and PCA never see labels, so it is exactly a full refit under permuted labels.
  - OOD: the reference excludes the test image. For a Batch_3 image, the band uses only its 16 peers.
  - Covariate p05/p95 use the fold's 30 training images (`n_training_images: 30` in the JSON).
  - Held-out run: the final 31-image model, the 17-image Batch_3 reference, and covariate ranges from all 31 images.
- **Scope (6).** Changed outside `results/v1/`: README, docs/Log, modal_app.py (adds `DINOv2TileEncoder` only; `DINOv2ImageEncoder` untouched), schema (adds an `allOf` if/then), the classify.py and heldout.py stubs (base was `NotImplementedError`), cli.py, and 2 new test files. No Phase A/B module or Phase B result file changed. `test_phase_b_batch_verdicts_remain_valid` confirms the B7 verdicts still pass the schema.
- **Tests (7).** `python -m pytest -q`: 66 passed, 0 skipped, 0 failed (9 s, with no raw data present).
- **Held-out parity.**
  - `heldout_dryrun_parity.csv`: features and embeddings max |diff| 0. The only covariate difference is `nm_per_px_if_tag_true` at 3.6e-15 (a CSV round-trip).
  - Frozen-model refit check: diff 9.7e-17.
  - Modal L4 run: 23.4 s wall, $0.0014, logged in `results/v1/MODAL_RUNS_v1.csv`. Phase B `results/MODAL_RUNS.csv` is untouched.
  - Training only reads committed parquet, and heldout writes nothing under `data/tiles` or `results/*.parquet`. Held-out images therefore cannot enter training.
- **Licence / sources.** No new external sources. The DINOv2 ViT-S/14 weights are SHA-256 checked at load (Apache-2.0, as in Phase B). No licence problems found.

## Consequential defects and corrective actions

**C1 (blocking before the tag): the run-once guard can be bypassed.** In `heldout.run`, `_run_once_guard` only runs when `not dryrun and not exploratory`, and when `--input-dir` is omitted the input defaults to `cfg.data.heldout_dir = data/heldout`. So:
- `qc heldout --dryrun --out x.json` processes the real held-out set before the tag, with no guard. It then labels the images "training image copied to a temporary folder; its score does not count".
- `--exploratory` does the same.
- The guard also checks only the `--out` path given. A second "real" run at the tag with `--out results/v1/heldout2.json` passes, even though the log says the guard checks "no existing results/v1/heldout.json".

Fix:
- `--dryrun`: require `--input-dir`, and refuse unless every parsed sample_id is one of the 31 training ids. If `data/raw` is present, also check that the BSE sha256 matches the training file.
- `--exploratory`: refuse while `results/v1/heldout.json` does not exist, or whenever the input resolves under `data/heldout` before that file exists.
- Real run: always check the canonical `results/v1/heldout.json`, and refuse a non-canonical `--out`.
- Add a test for each of these three cases.

**C2 (before the tag, justification only): the tier does not reflect how reliable a Batch_1/Batch_2 bet is.** From the committed `loio_predictions.csv`:

| predicted | high | medium | low | all |
|---|---|---|---|---|
| Batch_3 | 13/14 | 0/1 | 1/1 | 14/16 |
| Batch_2 | 1/3 | 1/3 | 0/3 | 2/9 |
| Batch_1 | 0/1 | 0/1 | 2/4 | 2/6 |

- "High" tier on a Batch_1/2 bet was right 1 time in 4.
- Medium overall was 1/5, which is lower than low overall at 3/8.
- `vc2whyaq` and `utfgcjfa` (both Batch_3) were bet Batch_2 at "high". `uhdslk0o` (Batch_1) was bet Batch_2 at p = 0.954; its tier is low only because of OOD.
- The aggregate line "high 18 (14 correct)" hides this.

A held-out image bet Batch_1 or Batch_2 at "high" would overstate confidence. A judge will check exactly this.

Do **not** change the tier rule after seeing results. Instead, add numbers to `closed_set.justification.numbers`:
- `loio_precision_for_predicted_batch` (e.g. "2/9"), and the precision for this predicted batch within this tier (k/n). These come from the frozen `loio_predictions.csv`, with the evidence selector `pred_batch == '<b>'`.
- One sentence in the reason when the predicted batch is Batch_1 or Batch_2.

Log these as reporting additions. If the owner wants a tier change instead, log it as a post-results deviation.

**C3: the OOD band is overstated as "99 %".** The null has 16–17 values, so band99 is just an interpolation between the top two null values. Any image beyond the null max has an empirical p of at least 1/18 ≈ 0.056 (Batch_3 test) or 1/18 (non-Batch_3, n = 17). "Outside the Batch_3 99 % band" therefore reads as stronger than the data allows. Fix:
- Add `ood_rank_p = (1 + #{null ≥ E1}) / (n_null + 1)` and `n_null` to `open_set.justification.numbers`.
- Reword the reason and routing to say "beyond the 17-image Batch_3 null (empirical p ≥ 0.056)".
- The label rule itself stays unchanged.

**C4: one held-out evidence path does not resolve.** The covariate evidence `{"file": "img_<id>_BSE.tif", "selector": "TIFF metadata"}` is a bare file name relative to the input directory. In the dry-run that directory was `/home/ubuntu/heldout_dryrun`. In the real run it would be `img_*.tif` rather than `data/heldout/img_*.tif`. Fix: write a repo-relative path, or input_dir + name (and record input_dir, which `run.input_dir` already does).

**C5: undocumented deviations from the contract in the log.** `docs/READ/... Phase C section` asks for:
- LOGO accuracy with the bet justification;
- an ablation with and without acquisition covariates;
- `verdict.label` from FRAMEWORK §13.5 items 1–6.

The implementation omits LOGO and the ablation, and uses an E1-only label. All three follow from the owner's Phase C spec, but the "Frozen choices" deviations list does not state them. Add three one-line deviations ("owner excluded / OOD-only label"). Do not add the analyses.

## Minor (non-blocking)
- For PC drivers, `standardised_value` holds the raw PC score (train SD 3.18 for PC1 down to 0.20 for PC29), not a standardised value. Either rename it or note it in `units`. This follows the spec ("PCA scores not rescaled"), but the field name misleads.
- A frozen real run silently falls back to local CPU if Modal fails. The fallback is recorded, but CPU and GPU embeddings can differ at about 1e-4. Make the frozen run fail instead of falling back, or record the max diff against a training image.
- Interpretation already covered by the log, but worth repeating to judges:
  - 18/31 is one image above the majority rate (17/31); balanced accuracy is 0.465.
  - The label-permutation null ignores acquisition groups.
  - 73/93 driver slots are embedding PCs, whose batch signal could not be separated from acquisition in Phase B.
  - The top driver for `uhdslk0o` is F04, a Phase B `drop` feature (threshold-sensitive); it is tagged correctly.
- The permutation p of 0.035 has a Monte Carlo SE of ≈ 0.006 with 1,000 permutations. p < 0.05 is stable.

## Future work (one line each; owner-excluded)
- Acquisition-residualised variant of the classifier.
- LOGO accuracy.
- Set-level OOD for a whole incoming batch.

# PHASE_B_CHECK — `stage/s1-s5-reality-check` @ `d4d035c5e444254798d682ee3fdf93d5a00c51d5`

Report only. No tracked file was edited, committed or pushed. Reruns ran in two untracked copies made with `git archive HEAD`: `~/phaseB_run` (full chain tiles→segment→kpi→features→validate→register→charging, raw data symlinked) and `~/phaseB_val` (validate/classify on the committed input tables). Because these are archive copies, the rerun outputs stamp `git_sha = 297d134` / `unknown`. The SHAs stamped in the committed files (`eca6fa7` validate, `f1ea178` kpi/features, `20e3371` register/charging, `370d083` classify) are all ancestors of HEAD (`git merge-base --is-ancestor`). Config hash `de199d6c8d69` is the same in every committed and regenerated file.

Environment: `uv venv --python 3.11`; there is no `.[dev]` extra, so the fallback `uv pip install -e .` was used. `pytest -q` gives `ModuleNotFoundError: tests`; `python -m pytest -q` gives **43 passed**. `python scripts/download_drive.py` worked: 93 TIFFs (31 images × 3 detectors), `data/raw/inventory.csv`.

Levels: L0 = code exists and is not a stub · L1 = I reran it on the real data and it completed · L2 = my regenerated output matches the committed file numerically (max |diff| reported) · L3 = numbers quoted in the docs match the file (see §2). "—" = no level, because the item is a stub or missing.

## 1. Item table

| # | item | requirement (FRAMEWORK.md:185-190 unless noted) | level | evidence | defect | what closes it |
|---|---|---|---|---|---|---|
| 1 | KPI definitions | phase fractions + high-Z size distribution/count density, each with a definition | **L2** | `src/qc/kpi.py` docstring: 8 KPIs (`frac_c0/1/2`, `c2_count_density_per_Mpx`, `c2_eqdiam_median_px`, `c2_eqdiam_p90_px`, `c0_region_eqdiam_median_px`, `c0_region_area_mean_px`). I regenerated `results/kpi_per_image.parquet` (31×21), `kpi_per_tile.parquet` (1443×15) and `thresholds_per_tile.parquet` (1443×12): max \|diff\| = 0 against the committed files. | none in the code. 1443 BSE tiles, 4329 tiles in total | — |
| 2 | KPI units | px until pixel size is confirmed | **L2** | Column names end in `_px`, `_per_Mpx`, or are unitless fractions. `configs/v1.yaml` has `min_object_px: 20` | none | — |
| 3 | ±10 % threshold perturbation | for every KPI | **L2 (fractions only)** | `results/kpi_sensitivity.parquet` (4422×16, `scale` ∈ {0.9, 1.0, 1.1}) regenerated with max \|diff\| = 0. It contains only `frac_c0/1/2`. In `results/validate/kpi_per_image/decisions.csv`, `threshold_sensitivity` is NaN for 5/8 KPIs and for **11/11** F01–F11 | No sensitivity for count density, size, c0-region KPIs or F03–F11. The keep rule's G3 cannot be evaluated for those | Extend `kpi.py`/`features` to compute all features at scale 0.9/1.1 and write the results into `kpi_sensitivity.parquet` (~2-3 h) |
| 4 | "5-tile manual check" | FRAMEWORK.md:185 and :257 ("sensitivity, manual check, crops") | **— (missing)** | `grep -i "5-tile\|five tile\|manual check"` finds it only in `docs/FRAMEWORK.md:185,257`. There is no record, CSV or annotated crops. `qc kpi` writes 6 overlays, but nothing shows they were reviewed | There is no evidence that the check was done | Pick 5 tiles (include ≥1 with `t1 < 60`), review the overlays and record pass/fail per KPI in `docs/` (~1 h) |
| 5 | Embeddings | DINOv2 ViT-S/14 with a fixed torch.hub revision, one vector per tile, mean per image, plus a benchmark | **— (stub)** | `src/qc/embed.py` **does not exist**. `modal_app.py` `embed_tiles()` raises `NotImplementedError("S5: load DINOv2 ViT-S/14 ...")`. `configs/v1.yaml` `embeddings:` has `backbone: dinov2_vits14`, `hub_repo: facebookresearch/dinov2` and **no revision/commit pin**. No `emb_per_image` file exists | Not implemented; the revision is not fixed | Write `embed.py`: `torch.hub.load(...:<commit>)`, 518 px input, mean-patch pooling, mean per image → `results/emb_per_image.parquet`, logging time and cost (~4-6 h CPU/Modal) |
| 6 | `src/qc/stats.py` | S6 module | **— (stub)** | The whole body is `raise NotImplementedError("stats: not implemented yet; see docs/FRAMEWORK.md Section 2b")`. None of its declared outputs exist (`null_bands.json`, `w1_distances.json`, `consistency.json`, `per_image_flags.parquet`) | Confirmed stub | see rows 7-11 |
| 7 | Reference choice | Polaron's choice if given, and report the alternatives | **partial, L2** | `src/qc/validate.py:59` hard-codes `REFERENCE_BATCH = "Batch_3"`, which matches Polaron's clarification. `configs/v1.yaml` still says `reference_batch: auto` and is ignored | No alternative-reference run is reported. The config contradicts the code | Read the reference from the config and report Batch_1/Batch_2-as-reference rows (~0.5 h) |
| 8 | Null from image-level half-splits of the reference | — | **— (missing)** | No half-split code anywhere in `src/` (grep "half" matches only `registration.py:152`). The closest is `validate.py` `reference_loo()` (Batch_3 leave-one-out robust z, flag \|z\|>3), which is an outlier screen, not a null band | Missing | Implement it in `stats.py`: B random 8/9 splits of the 17 Batch_3 images → distribution of the same distance statistic → 95/99 % bands (~2 h) |
| 9 | Standardised KPI median shifts | pairwise batch distances | **partial, L2** | `validate.py` `batch_tests()` → `batch_tests.csv` columns `median_shift`, `effect_shift_over_mad`, `p_perm`, `q_bh`. This covers Batch_1/2 **vs Batch_3 only**, raw + residualised, all/excl-LOO-flagged. Regenerated with max \|diff\| = 0 | No Batch_1–Batch_2 pair, no aggregated distance matrix, not calibrated against a reference null | Aggregate into a 3×3 matrix in `stats.py` and band it with row 8 (~1 h) |
| 10 | Energy distance / MMD on embeddings with image-level permutation | — | **— (missing)** | grep "energy\|mmd" in `src/` matches only the `stats.py` docstring (and an unrelated "energy" in `artefacts.py`). The image-level permutation exists in `validate.py` `_two_sample_perm`, but for univariate medians only | Missing, and blocked by row 5 | Energy distance on image-mean embeddings, permuting image labels (~1-2 h after row 5) |
| 11 | Consistency score per batch | within-batch spread of per-image values, as a ranking | **— (missing)** | No consistency output. `stability.csv` `rank_stability` is a bootstrap stability of the *ordering of batch medians*, which is a different quantity | Missing | Per-batch median pairwise image distance, or MAD of per-image KPIs, ranked, with a bootstrap CI (~1 h) |
| 12 | Leakage rule | tiles from one image stay on one side of every split | **L2** | `validate.py` `grouped_folds()` puts every row whose unit equals the held-out unit into test; `cv_predict` and `classify.py` `oof_predict` call `assert not set(train) & set(test)`; the imputer, scaler and model are refitted per fold (`_model` pipeline). Both harness tables are image-level (31 rows, one per `sample_id`), so tiles cannot cross a split. LOGO has 13 folds by acquisition group. The `classify.py` `permutation_null` permutes the image-level `y`, and `ood_table` uses leave-self-out | None found. Caveat: there is no tile-level model yet (Phase C), so the rule is untested for tile tables (the docstring claims it holds for them) | Add a synthetic test with repeated `sample_id` tile rows (~0.5 h) |
| 13 | Gate: distance matrix | — | **— (missing)** | There is no `w1_distances.json` or any batch×batch matrix. `classify` `ood.csv` holds image→batch robust distances (a Phase C item) | Gate item missing | rows 8+9 (+10) |
| 14 | Gate: consistency ranking | — | **— (missing)** | none | Gate item missing | row 11 |
| 15 | Gate: one verdict JSON for one batch with a reason sentence | — | **— (stub)** | `src/qc/verdict.py` is a stub (`raise NotImplementedError("verdict: ...")`). `schema/verdict.schema.json` exists (required: subject, verdict, pipeline, acquisition, evidence, uncertainty, routing, next_action). No `results/v1/batch_*.json` exists anywhere. `classify.py:226` writes verdict *text* into `CLASSIFY.md` only | Gate item missing | `verdict.py`: one `batch_Batch_1.json` that validates against the schema, label `investigate`, a reason sentence and evidence pointers (~1-2 h) |
| 16 | F01–F11 features (`qc features`, `configs/features_v1.yaml`) | added work | **L2** | `features_v1.yaml` defines F01–F11 with provenance. I reran `qc features` (78 s): `features_by_tile.parquet` (1443×35) max \|diff\| 0; `features_by_image.parquet` (31×34) max \|diff\| 0 on every feature column; only the `seconds` (runtime) column differs, by 2.68. **`results/features/features_f01_f11.parquet` is not written by `qc features` or by any script in `src/`/`scripts/`.** It was added by hand in commit `89dfd8e`. I rebuilt it as a 13-column subset of the regenerated `features_by_image` and got max \|diff\| 0 against the committed file | `features_f01_f11.parquet` has no code provenance. F08 is degenerate (median 26.0 px in all three batches, `rank_stability` NaN). F11 is ~0 (median 0.000684, max 0.004233). F03 sits at the 20 px floor (7.569–8.519 px) | Have `qc features` write `features_f01_f11.parquet` (~15 min) |
| 17 | Validation harness (`qc validate`) on both tables | decisions 0 keep / 11 investigate; flag counts 5/17 (KPI) and 7/17 (F01–F11) | **L2** | (a) Committed inputs → `~/phaseB_val/rerun/*`, and (b) **fully regenerated inputs** → `~/phaseB_run/rerun/val_*`. For all 12 CSVs (`batch_tests`, `confound`, `decisions`, `loio_logo`, `reference_loo`, `stability` × 2 tables), shape is equal, max \|diff\| = 0, NaN pattern equal, labels equal; only `git_sha` differs. Decisions: F01–F11 `{'investigate': 11}`, KPI `{'investigate': 8}`. KPI LOO flags: `0grcilhi, cfe5vt7s, hzumfsms, ufdvpb81, vc2whyaq` (5/17). Feature flags: `0grcilhi, hzumfsms, mgxahqnk, tuy3zymq, vc2whyaq, x77cy643, xgj4xftb` (7/17). Wall time 6 s per table | `src/qc/validate.py` changed since `eca6fa7` (21 lines); the outputs still reproduce. G3 is NaN for most features (row 3), so the "investigate" label partly reflects missing data, not a failed test | row 3 |
| 18 | Registration (`qc register`) | added work | **L2** | Rerun took 55 s: "31 images, 62 pairs, 31 images registered". `registration_by_image.csv` (93×30) and `registration_windows.csv` (744×13) have max \|diff\| 0 against the committed files, git_sha excepted. `max_abs_median_shift_px` max = 0.1 | none | — |
| 19 | Charging (`qc charging`) | added work | **L2** | Rerun took 161 s (31 images × 6 mask variants, 0 skipped). `charging_by_image.csv` (217×37), `charging_batch_summary.csv` (21×29) and `features_masked_vs_unmasked.csv` (217×26) have max \|diff\| 0 against the committed files (git `20e3371`). p95 `frac_c2_area_flagged_median` = 0.089180 / 0.074443 / 0.070038 (B1/B2/B3). No `*_delta_exceeds_iqr` at p95. At **p90**, Batch_2 F02 and F04 are `True` | p90 exceedances are not mentioned in `PROJECT_STATE.md:76` | Mention p90 in the docs (~10 min) |
| 20 | Confounding / G2 | added work | **L2** | `confound.csv`: F05 `p_group 0.00020`, `z_group 3.50344`; F06 `p_group 0.00800`, `p_batch 0.06219`, `rho_mean_grey 0.53387`; F09 `p_group 0.05079`, `rho_hstripe 0.55282`, not confounded | doc values are wrong in places (§2) | §3 |
| 21 | RULEBOOK.md gates | added work | **L3 with mismatches** | `docs/RULEBOOK.md:26` matches the files. `:124` has F06 p wrong | §3 | §3 |
| 22 | FAILURE_MODE_MAP.md | added work | **L3 with mismatches** | `:47` has 3/4 numbers wrong | §3 | §3 |
| 23 | FEATURE_DOSSIER.md | added work | **L3 with mismatches** | `:42` 9/11 numbers match; `:83` medians are KPI `frac_c2`, not F02 | §3 | §3 |
| 24 | EVIDENCE_BASE.md / `docs/evidence/claims.csv` | DOIs resolve and support the direction | **L3 for metadata (5/5 resolve)**; direction is checked only against title/metadata | 72 rows, 16 columns. §5 | All are `source_access = abstract`; Crossref returns no abstract for any of the 5, so I could check direction only against title/metadata | Grade A/B claims need full-text locators (~ongoing) |
| 25 | "31 images cannot support 84 hypotheses" (`docs/PRESENTATION_JUSTIFICATION.md:14`) | backed by a repo file? | **not backed** | No repo file enumerates 84 hypotheses, features or dimensions. The row cites "consultant sign-off sheet (approved); `C1_tier_mapping.md`"; **`C1_tier_mapping.md` is not in the repo** (`git ls-files` / grep). `PROJECT_STATE.md` mentions "84-feature labels" only as something that was rejected | The number comes only from an owner-supplied catalogue that is not committed | Commit the catalogue, or rephrase as "many candidate dimensions" (~10 min) |
| 26 | Classifier / OOD (Phase C, used for the Polaron answer) | context | **L2**; committed numbers reach L3 (§2) | `results/classify/*/accuracy.csv`, `ood.csv` (git `370d083`). `src/qc/classify.py` changed by 287 lines since `370d083`, but a rerun with the current code (126 s / 124 s, n_perm 200) reproduces `accuracy`, `drivers`, `ood` and `predictions` with max \|diff\| 0 for both tables. In the rerun OOD, Batch_3 `in_reference` is False for 1 image (F01–F11, every family) and for 4 images (KPI material and material+acquisition) | The committed git stamp `370d083` is older than the code that produces identical output, so it is cosmetic | Restamp on the next commit (~5 min) |

## 2. Number check (doc path:line, doc value, file value, match)

Files: V = `results/validate/<table>/`, C = `results/classify/<table>/`, K = `results/kpi_per_image.parquet`, T = `results/thresholds_per_tile.parquet` + `results/kpi_per_tile.parquet`.

| # | doc:line | quantity | doc | file (exact) | match |
|---|---|---|---|---|---|
| 1 | PRESENTATION_JUSTIFICATION.md:49 | F01–F11 LOIO, no covariates | 0.45 | V/features_f01_f11/loio_logo.csv 0.45161290322580644 | yes |
| 2 | :49 | LOGO, no covariates | 0.32 | 0.3225806451612903 | yes |
| 3 | :49 | majority chance | 0.55 | 0.5483870967741935 | yes |
| 4 | :50 | LOIO / LOGO with covariates | 0.65 / 0.68 | 0.6451612903225806 / 0.6774193548387096 | yes |
| 5 | :52 | keep / drop / investigate | 0 / 0 / 11 | decisions.csv 0 / 0 / 11 | yes |
| 6 | :53 | F05 p_group | 0.0002 | confound.csv 0.00020 | yes |
| 7 | :53 | F06 p_group | 0.007 | 0.007999 (prints as 0.0080) | **no** |
| 8 | :53 | F06 rho mean grey | +0.53 | 0.53387 | yes |
| 9 | :53 | F09 p / rho hstripe | ~0.05 / +0.55 | 0.05079 / 0.55282 | yes |
| 10 | :54 | rank stability F06/F01/F03/F07/F02 | 0.75/0.69/0.63/0.56/0.54 | 0.746/0.6905/0.6282/0.5615/0.539 | yes |
| 11 | :54 | rank stability F05/F04/F11/F10/F09, F08 | 0.44/0.43/0.39/0.24/0.22, undefined | 0.437/0.4275/0.39/0.2445/0.2245, NaN | yes |
| 12 | :54 | F08 median pinned | 26 px | stability.csv medians 26.0/26.0/26.0 | yes |
| 13 | :55 | F11 typical / max | ~0.001 / 0.004 | median 0.000684 / max 0.004233 | yes |
| 14 | :55 | F03 range | 7.6-8.5 px | 7.569398-8.519076 | yes |
| 15 | :57 | KPI LOIO/LOGO without / with covariates | 0.58/0.45, 0.61/0.58 | 0.5806/0.4516, 0.6129/0.5806 | yes |
| 16 | :58 | ±10 % sensitivity on fractions | 1.2-1.7 × B3 MAD | KPI decisions.csv `sens_over_mad` 1.235187 / 1.700646 / 1.605109 | yes |
| 17 | :62 | failure tiles | 31/1443 | T: 31 / 1443 tiles with t1<60 | yes |
| 18 | :62 | c2 fraction, fail vs other tiles | 0.29 vs ~0.08 | 0.289479 vs 0.079442 | yes |
| 19 | :62 | image rho(mean t1, F02) | −0.59 | −0.539167 with F02; −0.594213 with KPI `frac_c2` | **no** (the doc value is for frac_c2) |
| 20 | :36 | classify material LOIO / null_p95 / p / LOGO / p | 0.45/0.52/0.19/0.32/0.61 | C accuracy.csv 0.4516/0.5161/0.1891/0.3226/0.6070 | yes |
| 21 | :37 | acquisition | 0.71/0.52/0.005/0.65/0.005 | 0.7097/0.5161/0.0050/0.6452/0.0050 | yes |
| 22 | :38 | material+acquisition | 0.65/0.52/0.015/0.68/0.005 | 0.6452/0.5161/0.0149/0.6774/0.0050 | yes |
| 23 | :39 | old KPIs | 0.58/0.52/0.045/0.45/0.14 | C/kpi_per_image 0.5806/0.5161/0.0448/0.4516/0.1393 | yes |
| 24 | :9 | acquisition groups | 13 | loio_logo.csv LOGO `n_folds` 13 | yes |
| 25 | :13 | n per batch | 7/7/17 | features table batch counts 7/7/17 | yes |
| 26 | RULEBOOK.md:26 | frac_c0 G3 | 1.24 × MAD | 1.235187 | yes |
| 27 | RULEBOOK.md:26 | KPIs failing G2 | count density, eqdiam median/p90, c0 region area | KPI confound.csv `acquisition_confounded` True for exactly those 4 | yes |
| 28 | RULEBOOK.md:26 | rank stability < 0.7 for all but F06 | — | only F06 ≥ 0.7 (0.746) | yes |
| 29 | RULEBOOK.md:124 | F06 / F05 p_group | 0.0077 / 0.0002 | 0.00800 / 0.00020 | **F06 no**, F05 yes |
| 30 | FAILURE_MODE_MAP.md:47 | F06 KW p across groups | 0.0077 | 0.00800 | **no** |
| 31 | FAILURE_MODE_MAP.md:47 | F06 p across batches | 0.052 | p_batch 0.06219 | **no** |
| 32 | FAILURE_MODE_MAP.md:47 | F06 ρ with BSE mean grey | 0.53 | 0.53387 | yes |
| 33 | FAILURE_MODE_MAP.md:47 | F05 p | 0.0007 | p_group 0.00020 | **no** |
| 34 | FEATURE_DOSSIER.md:42 | t1 range / median | 47-170 / 82 | 47.0-170.0 / 82.0 | yes |
| 35 | FEATURE_DOSSIER.md:42 | count density fail vs other | 303 vs 80 /Mpx | 303.268 vs 79.632 | yes |
| 36 | FEATURE_DOSSIER.md:42 | eqdiam median / p90 on fail tiles | 7.7 / 23 px | 7.653 / 23.396 | yes |
| 37 | FEATURE_DOSSIER.md:42 | p90 elsewhere | ~40 | median tile p90 of non-fail tiles 29.688 (image-level batch medians 33.4/39.7/41.8) | **no** (tile-level) |
| 38 | FEATURE_DOSSIER.md:42 | tile corr(t1, c2) / corr(t0, c0) | −0.57 / 0.18 | −0.574932 / 0.182678 | yes |
| 39 | FEATURE_DOSSIER.md:42 | image rho(t1, F02) | −0.59 | −0.539167 (F02); −0.594213 (frac_c2) | **no** |
| 40 | FEATURE_DOSSIER.md:83 | phi_2 batch medians | 0.089/0.092/0.097 | K `frac_c2` 0.0894/0.0922/0.0974 (match); F02 0.0891/0.0971/0.1006 | **no for F02** (labelled as the v1 KPI) |
| 41 | EVIDENCE_BASE.md:38 | class-0 fraction medians | 0.095/0.098/0.102 | K `frac_c0` 0.0951/0.0976/0.1019 | yes |
| 42 | PROJECT_STATE.md:76 | LOGO 0.32 vs 0.68 with covariates | 0.32 / 0.68 | 0.3226 / 0.6774 | yes |
| 43 | PROJECT_STATE.md:76 | reference LOO flags | 5/17 KPI, 7/17 F01–F11 | 5 and 7 distinct Batch_3 ids flagged | yes |
| 44 | PROJECT_STATE.md:76 | registered, max shift | 31/31, \|shift\| ≤ 0.1 px | 31 all-pairs registered; `max_abs_median_shift_px` 0.1 | yes |
| 45 | PROJECT_STATE.md:76 | class-2 bright in both SE at p95 | 7-9 % | 0.070038-0.089180 | yes |
| 46 | PROJECT_STATE.md:79 | classify 0.45 (p 0.19), 0.71 (p 0.005), 0.65/0.68, KPIs 0.58 (p 0.045) | as stated | as in rows 20-23 | yes |
| 47 | PROJECT_STATE.md:79 (and NEXT_STEPS.md:11) | OOD: no image `matches none` at α 0.05 | 0 | F01–F11 ood.csv 0/0/0 per family; **KPI ood.csv: material 1, material+acquisition 2** | **partial** (true only for the F01–F11 table) |

## 3. Mismatch list
1. `docs/PRESENTATION_JUSTIFICATION.md:53`: F06 p **0.007**; file 0.007999.
2. `docs/RULEBOOK.md:124`: F06 p **0.0077**; file 0.00800.
3. `docs/FAILURE_MODE_MAP.md:47`: F06 p **0.0077** vs 0.00800; F06 p across batches **0.052** vs 0.06219; F05 p **0.0007** vs 0.00020. These look like numbers from an earlier run (FMC19/FMC20) that were never refreshed.
4. `docs/PRESENTATION_JUSTIFICATION.md:62` and `docs/FEATURE_DOSSIER.md:42`: image rho(t1, **F02**) = −0.59; with F02 it is −0.539167. −0.594213 is the value for KPI `frac_c2`.
5. `docs/FEATURE_DOSSIER.md:42`: "p90 23 px (vs ~40)". At tile level the non-failure p90 median is 29.688.
6. `docs/FEATURE_DOSSIER.md:83`: medians 0.089/0.092/0.097 are KPI `frac_c2`, not F02 (0.0891/0.0971/0.1006). The paragraph is about F02.
7. `docs/PROJECT_STATE.md:79` / `docs/NEXT_STEPS.md:11`: "no image matches none" holds for F01–F11 only. The KPI table OOD has 1 (material) and 2 (material+acquisition) `matches_none`.
8. `docs/PRESENTATION_JUSTIFICATION.md:14`: "84 hypotheses" has no backing file in the repo. The cited `C1_tier_mapping.md` is not in the repo.
9. `configs/v1.yaml` `stats.reference_batch: auto` contradicts `validate.py:59` (`"Batch_3"`).
10. `docs/FEATURE_DOSSIER.md:3` cites config `1bec114301c3` "at writing time" (it says this itself; the files now carry `de199d6c8d69`).
11. (Cosmetic) `results/classify/*` are stamped `370d083`, older than the current `classify.py`. The rerun output is identical.

## 4. Charging / classify reruns
- `qc charging` rerun: all 3 CSVs have max |diff| 0 (L2).
- `qc classify` rerun on current code, both tables: all 4 CSVs have max |diff| 0 (L2). OOD `matches_none`: F01–F11 0/0/0. KPI: material 1, material+acquisition 2, acquisition 0.
- Tests: `python -m pytest -q` gives 43 passed.
- `git status` in the repo checkout is clean after all reruns.

## 5. DOI spot check (5 random rows of `docs/evidence/claims.csv`, Crossref API)
| id | DOI | resolves | Crossref title (journal, year) | stated direction | supports? |
|---|---|---|---|---|---|
| L5b | 10.1149/2.1281809jes | yes | "Modeling the Effects of Electrode Microstructural Heterogeneities on Li-Ion Battery Performance and Lifetime" (J. Electrochem. Soc., 2018) | heterogeneity degrades performance (direction only, model) | consistent with the title; Crossref has no abstract, so the direction is not checked against the text |
| X4 | 10.2307/1931034 | yes | "Distance to Nearest Neighbor as a Measure of Spatial Relationships in Populations" (Ecology, 1954) | method: R<1 clustered, R=1 random, R>1 regular | yes (the Clark–Evans paper; method definition) |
| M7 | 10.1016/j.softx.2016.09.002 | yes | "TauFactor: An open-source application for calculating tortuosity factors from tomographic data" (SoftwareX, 2016) | 3D only; `not_applicable` to 2D | yes; the title says "tomographic", consistent with the claim's own `not_applicable` status |
| L4a | 10.1016/j.jmatprotec.2017.05.031 | yes | "Characterization of the calendering process for compaction of electrodes for lithium-ion batteries" (J. Mater. Process. Technol., 2017) | calendering lowers porosity; 25-40 % window `not_found` | the direction is consistent with the title; the claim's own status says the number is not found, which is honest |
| L6b | 10.1038/nenergy.2016.97 | yes | "Magnetically aligned graphite electrodes for high-rate performance Li-ion batteries" (Nature Energy, 2016) | alignment matters; 1.6-3× at high rate | the direction is consistent with the title; the 1.6-3× figure is attributed to the corrigendum, which I did not open |

All 5 DOIs resolve, and the bibliographic metadata matches `source_locator`. Only for X4 and M7 is the direction fully checkable from the metadata; L5b, L4a and L6b are consistent with their titles, but I could not verify the abstract text (`source_access = abstract`; Crossref returned none).

## 6. Answers
**(a) Phase B gate: NOT MET.** All three gate items (distance matrix, consistency ranking, one verdict JSON with a reason sentence) are absent: `stats.py` and `verdict.py` are stubs and `embed.py` does not exist. What is in place is the measurement and validation layer around Phase B: the KPIs, the F01–F11 features, the validate harness, registration and charging. All of these reproduce exactly (L2, max |diff| 0) from raw data, and the leakage rule holds for every split that exists.

**(b) Minimal ordered closure list**
1. `stats.py` KPI-only W1 (~3-4 h): reference from config = Batch_3 + alternatives; 3×3 standardised median-shift distance matrix (reusing `batch_tests` logic); Batch_3 half-split null bands (95/99 %); per-batch consistency score + ranking; outputs `w1_distances.json`, `null_bands.json`, `consistency.json`. Image-level throughout; add a leakage unit test.
2. `verdict.py` (~1-2 h): `results/v1/batch_Batch_1.json`, validated against `schema/verdict.schema.json`, with a reason sentence. → **This closes the gate on KPIs alone.**
3. Five-tile manual check record (~1 h).
4. ±10 % sensitivity for all KPIs/F03–F11 (~2-3 h), so the G3 NaNs stop forcing `investigate`.
5. `embed.py` DINOv2 ViT-S/14 with a pinned hub commit, mean per image, plus energy distance/MMD with image-level permutation in `stats.py` (~5-8 h incl. Modal).
6. Doc fixes from §3 + make `qc features` write `features_f01_f11.parquet` (~1 h).

**(c) What matters for Polaron judging** (identify what differs; categorise the held-back images; in/out of Batch_3)
- **Needed:** item 1 (distance to Batch_3 against a Batch_3 null, which is exactly the in/out-of-distribution question; `classify.ood_table` already gives a per-image version), item 2 (a traceable reason sentence per batch/image), item 4 (otherwise no feature can leave `investigate` and the "what differs" answer is unsupported), the `classify` held-back path (`score_heldout`; it reproduces at L2 but has not yet been run on held-back images), and the leakage guarantee (already met).
- **Useful but optional for the criterion:** item 3 (credibility of the KPIs on stage), item 5 (embeddings/MMD are a second evidence line; the RULEBOOK needs two lines for `outside bounds`, but the judging asks for categorisation and in/out, which KPI/F-feature + acquisition families already attempt), and the remaining doc fixes.
- Current evidence on "what differs": acquisition covariates identify the batch (LOIO 0.7097, p_perm 0.0050). F01–F11 material features alone do not beat the permutation null (0.4516, p 0.1891). Phase B has no artefact-balanced material verdict yet.

## Verdict
**Phase B properly done: no.** The measurement and validation layer under it is reproducible (L2) and leakage-safe, but `stats.py`, embeddings and `verdict.py` are missing, so no gate deliverable exists. In addition, 9 doc numbers mismatch the files and 1 doc claim is only partly true (§3).

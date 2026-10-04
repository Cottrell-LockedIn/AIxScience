# Log: embedding PC correlation profiles (v1.1 Item B, M9-lite) — EXPLORATORY

Status: exploratory, output-only, `review_status: unreviewed`. The frozen model (`v1-frozen` = afdbfc9), the
`verdict` blocks, probabilities, tiers, drivers and F01-F11 of every image are untouched; the official
`results/v1/heldout.json` is byte-identical. Plan of record: `docs/PRD_MODEL_IMPROVEMENTS.md` section 0.3.

## What was done

- New stage `python -m qc pc-profiles` (`src/qc/pc_profiles.py`, registered in `src/qc/cli.py`). It refits the v1
  final model from the committed parquet (`classify.load_training`, `classify.final_model`), checks it against
  `results/v1/final_model.csv` (max |coefficient diff| 9.7e-17), takes the 29 PC scores of the 31 training images and
  correlates each PC with 32 variables: the 11 measurements F01-F11, the 8 pre-registered acquisition covariates
  (`classify.covariate_frame`) and 13 Phase B KPIs (`results/kpi_per_image.parquet`, context only).
- Statistic: Spearman rho; two-sided permutation p from 2000 label-free shuffles of the variable (seed 0,
  p = (1 + #{|rho_perm| >= |rho|}) / 2001); Benjamini-Hochberg within each PC across its 32 variables. n = 31 for
  every cell. Runtime about 2 s, no raw data, no Modal.
- Tag rule (constants at the top of the module, copied into the JSON): `material:<F-id>` if |rho| >= 0.7 and
  BH p < 0.05 with a measurement and |rho| < 0.5 with every covariate; `imaging:<covariate>` if |rho| >= 0.5 with a
  covariate and that |rho| exceeds every measurement |rho|; otherwise `unresolved image-texture component`.
  The KPI block does not enter the rule.
- Outputs: `results/v1/pc_profiles.csv` (928 rows, long format) and `results/v1/pc_tags.json` (per PC: tag,
  explained variance ratio, max |LR coefficient|, top measurement / covariate / KPI, template sentence), both
  stamped `config_hash 45629944e398`, `git_sha`, `n_images 31`, `exploratory true`,
  `phase_identity: stated by Polaron, not image-verified`, `review_status: unreviewed`.
- Tests: `tests/test_pc_profiles.py` (tag rule on synthetic vectors, BH hand example, deterministic regeneration
  matching the committed files, every driver PC in `heldout.json` and `loio_predictions.csv` has a tag).

## Result (descriptive; 31 images; not causal)

Tag counts: material 0, imaging 3, unresolved 26.

| PC | driver slots (LOIO / held-out) | tag | top measurement (rho, BH p) | top covariate (rho, BH p) |
|---|---|---|---|---|
| PC1 (EVR 0.371) | 18 / 2 | imaging:sharpness_BSE | F01 void area fraction 0.62, 0.008 | sharpness_BSE -0.63, 0.008 |
| PC2 (EVR 0.196) | 13 / 1 | imaging:hstripe_score_BSE | F11 -0.49, 0.069 | hstripe_score_BSE 0.65, 0.016 |
| PC3 (EVR 0.109) | 14 / 1 | unresolved (material blocked) | F05 silicon count density 0.81, 0.002 | curtaining_score_BSE 0.52, 0.009 |
| PC4 | 6 / 1 | unresolved | F10 0.51, 0.19 | edge_charging_BSE -0.14, 0.96 |
| PC5 | 8 / 1 | unresolved | F11 -0.41, 0.70 | sharpness_BSE 0.33, 0.70 |
| PC7, PC8, PC9, PC11, PC12, PC13 | 3, 4, 0/1, 2, 4, 1 | unresolved | max |rho| 0.20-0.52, BH p >= 0.13 | max |rho| 0.24-0.30, BH p >= 0.63 |
| PC6 (not a driver) | 0 | imaging:nm_per_px_if_tag_true | — | nm_per_px_if_tag_true -0.73 |

Reading: PC1 is tagged imaging, but by a hair (|rho| 0.63 vs 0.62 for void fraction F01); with n = 31 these two
are indistinguishable, so PC1 should be read as "sharpness and/or void fraction, not resolvable here". PC3 is
the only PC with a strong measurement correlation (F05, rho 0.81) and would be `material:F05` if the curtaining
correlation were below 0.5. Tags are descriptive correlations over 31 training images; Phase B could not separate
the embedding's batch signal from acquisition (BH p 0.75 / 0.96 after residualisation).

## Not done / open

- No independent fresh-context review of the tags yet (`review_status: unreviewed`); the parent session arranges it.
- Tile galleries (M9b) and patch heat maps (M9c) remain deferred.

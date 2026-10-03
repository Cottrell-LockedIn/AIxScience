# Evidence base for the Track 4 QC rulebook

Status: v0.1, 2026-10-03, branch `docs/evidence-base`. Docs only; nothing under `src/`, `configs/`, `schema/`, `results/`, `data/` is touched.

Companion files (machine-checkable):

- `docs/evidence/claims.csv` — one row per claim: `id, claim, quantity_bounded, threshold_or_direction, source_doi, source_type, evidence_grade, applies_if, cannot_cover, status, observed, inferred, source_locator, source_access, checked_url, bibkey`.
- `docs/evidence/references.bib` — 109 BibTeX entries, every one resolved on 2026-10-03 through `https://api.crossref.org/works/<DOI>` (or the arXiv API for preprints); the URL checked is in each `note` field.

## 0. How to read this document

**Grades** (as specified in the task):

- **A** peer-reviewed primary measurement on Si/graphite anodes or on FIB-SEM/tomography of battery electrodes.
- **B** peer-reviewed review, model study, or related electrode chemistry (e.g. cathodes), or a materials application outside batteries.
- **C** textbook, standard (ASTM) or widely used method paper (statistics, image analysis, SEM physics, provenance).
- **D** preprint or single-source; always `status = check`.

**Status**: `verified` (number/direction read in the source and locator given), `not_found` (source resolved but the exact number is not in the text we could access; row kept as direction-only), `check` (preprint/single source), `not_applicable` (bound exists but our data cannot measure it).

**Access**: 15 claims are from full text (Müller 2018, Eshetu 2021, Taiwo 2016, Roldán 2024, Dahari 2025, FAIR, Snorkel, Sandve 2013); 53 from abstracts only; 3 from ASTM scope text; 1 from Crossref metadata only (Lewis 1973, no abstract exists). Where only the abstract was read the row says so and no number beyond the abstract is claimed.

**OBSERVED vs INFERRED**: each row separates what the paper measured (`observed`) from how we apply it (`inferred`). Nothing in the `inferred` column is literature; it is our reasoning and is only as good as the stated `applies_if`.

**Counts**: 72 claims — A 15, B 10, C 41, D 6; verified 59, check 6, not_found 5, not_applicable 2.

**What this evidence base cannot do**: no claim here establishes good/bad battery performance from images, confirms phase identity (class 2 = Si, class 1 = graphite, class 0 = void are Polaron statements), or validates the 25 nm/px tag. Every physical unit below is conditional on "if 25 nm/px is true".

## 1. Rulebook bounds (L1–L6, D1–D2, S1–S3)

### 1.1 Measured values used for comparison (PR #1, S1–S5 reality check)

31 images (Batch_1 7, Batch_2 7, Batch_3 17), BSE channel, per-tile multi-Otsu (3 classes), per-image mean over tiles.

| quantity | measured (px / fraction) | if 25 nm/px | note |
|---|---|---|---|
| class-2 (bright, "Si") area fraction | medians 0.089 / 0.092 / 0.097 by batch; ~0.09 overall | — | ±10 % threshold shift moves it by 0.02–0.04 per image |
| class-0 (dark, "void") area fraction | 0.095 / 0.098 / 0.102; ~0.10 | — | lumps pores, binder/CB, sub-resolution material |
| class-2 equivalent diameter, median | 8.4 px | ~0.21 µm | 2D section diameter; min component 20 px² |
| class-2 equivalent diameter, p90 | 41 px | ~1.0 µm | agglomerates merged |
| three images with class-2 ≈ 0.14–0.22 | `4ih2ggld`, `5n1q8atc` (B1), `r17byphk` (B2) | — | ~2× the other 28 |
| noise_sigma / sharpness (BSE) | Batch_3 lower noise, gap 3.2× IQR | — | 13 acquisition groups, 5 span batches |

### 1.2 Rule-by-rule verdict

| rule | draft statement | what the literature actually supports | change | our values vs bound |
|---|---|---|---|---|
| **L1** Si critical size | ~150 nm (Liu 2012) | **Confirmed**: "critical particle diameter of ~150 nm" (abstract, 10.1021/nn204476h, grade A). Lee 2012 (PNAS) confirms a size effect for pillars; exact number not found in abstract. | Kept as a *material mechanism*, demoted from discriminator: 150 nm = 6 px at 25 nm/px, which is at the segmentation floor (components < 20 px² removed ≈ 5 px diameter). | Median 0.21 µm and p90 1.0 µm are **above** 150 nm, as is essentially every resolvable class-2 object. The bound cannot separate batches here; it only says "most resolvable bright objects are in the fracture-prone regime *if* they are single crystalline Si particles", which is unverified (agglomerates, SiOx). |
| **L2** detachment / isolation (Müller 2018) | gaps grow with radius and cycles | **Confirmed** from full text: gap formation at 1/5/10 cycles (Fig. 2), detachment vs radius (Fig. 3), isolation → capacity fade (Results). κ₀ ≈ 0.02 µm (< 0.05 µm) is a model parameter, not an image threshold. | Direction only; no numeric gap cutoff exists. | Not measurable yet: our masks have no binder class, so a dark rim around a class-2 particle is pore, binder or artefact. Candidate feature for D1 only. |
| **L3** commercial Si content | 3–10 wt% (Chae 2019) | **Not confirmed from Chae** (abstract only, no number). Found instead: Eshetu 2021 (Nat Commun review, full text): "manufacturers have introduced small amounts of Si (<6–8 wt.%)", "SiOx < 10 wt.%"; Müller 2018 intro: "5–20 wt.%" in composite research electrodes; Günter 2022 teardown: a 2022 automotive anode was **silicon-free**. | Replaced by a direction ("commercial loading is low, upper range ~6–10 wt%"); the draft lower limit (3 wt%) is dropped (0 wt% exists in production). Grade B for the range. | Area fraction cannot be converted to wt% without unverified assumptions. **If** class 2 = Si, Delesse holds, and bulk densities (Si 2.33, graphite 2.2 g cm⁻³) apply to a 0.92 solid fraction, 0.09 area → ~10 wt% of solids: at/above Eshetu's <6–8 wt%, inside Müller's 5–20 wt%. Action: ask Polaron for nominal Si wt% rather than inferring it. |
| **L4** calendered graphite porosity | 25–40 % (Meyer 2017) | **Not found** in the accessible record of Meyer 2017 (abstract; grade A paper, no window given). Numbers found: Haselrieder 2013 (graphite, 10 % compression beneficial, direction); Taiwo 2016 (one *uncalendered* graphite electrode, 3D pore fraction 0.484, 2D slices 0.443–0.531). | Direction-only; the 25–40 % window is removed until a verified passage is found (TODO). | Class-0 0.10 is **below** every published electrode porosity we found (0.25–0.48). Because class 0 is a grey-level class in FIB-SEM (shine-through, resin-filled pores, binder lumped elsewhere: Fager 2020, Prill 2012), the gap is more plausibly a measurement-definition issue than a material fact → `investigate` the segmentation/phase definition, not a batch verdict. |
| **L5** inhomogeneity (Harris & Lu 2013) | heterogeneity harms durability | **Confirmed as direction** (review, grade B); Forouzan 2018 model agrees. No numeric cutoff anywhere. | Unchanged, direction only. | We can report tile-to-tile IQR of fractions per image; no literature bound to compare. |
| **L6** flake orientation / anisotropy | alignment affects transport | **Confirmed as direction**: Ebner 2013 (tortuosity anisotropy, A); Billaud 2016 (aligned flakes → 1.6–3× capacity at practical rates in model anodes, from the 2017 corrigendum text, A). | Direction only; image axes vs collector normal unknown. | A 2D orientation index is a within-dataset comparison only. |
| **D1** cracks / pull-out / isolation | direct defect evidence | Müller 2018 provides the definitions; FIB artefact classes from Roldán 2024 (curtaining = vertical thin uneven bands) and Giannuzzi & Stevie 1999 / Bassim 2011 (redeposition, damage). | Added explicit exclusion rule: a candidate aligned with the milling direction, or confined to one FIB slice, is an artefact until shown otherwise. | No inter-annotator agreement figure for electrode cross-section defects was found (`not_found`); we must measure our own (Cohen κ / Dice). |
| **D2** delamination | collector interface | Requires the collector in the field of view. | `not_applicable` for the current 31 images; ledger records "not measured". | — |
| **S1** T² / Mahalanobis | reference deviation | Tracy–Young–Mason 1992 (exact Phase-I limits), Champ 2005 (estimated parameters degrade performance; corrected limits), grade C. | Keep the statistic; **calibrate by image-level permutation**, never by F/χ² at n = 17, p ≳ 5. | — |
| **S2** reference contamination | Batch_3 not guaranteed clean | Vargas 2003 (robust T²), Rousseeuw & Van Driessen 1999 (FAST-MCD), grade C. | Added: compute classical and MCD distances; disagreement → `investigate`; LOO on reference images. | — |
| **S3** pseudoreplication | tiles not independent | Saravanan 2019/2020 (hierarchical bootstrap; >45 % false positives when hierarchy ignored) is a preprint → grade D, `check`. Caicedo 2017 (image-based profiling aggregation) and Leek 2010 (batch effects) are peer-reviewed C-grade support. | Unchanged in substance; add Caicedo/Leek as the non-preprint basis. | — |

### 1.3 Additional bounds/directions searched

| topic | found | grade | result |
|---|---|---|---|
| Si particle size distribution vs cycle life | Wetjen 2017/2018 (Si-graphite degradation; Si NP morphology changes with cut-off potential), Moyassari 2022 (Si content vs ageing) | A (abstracts) | direction only; no pristine PSD bound found (`not_found` for numbers) |
| Si clustering / agglomeration | no battery-specific bound; Clark–Evans 1954 R statistic as a method | C | KPI only, compared across batches |
| pore size / local thickness | Hildebrand & Rüegsegger 1997 (local thickness) | C | KPI in px; no anode bound found |
| graphite flake orientation | Ebner 2013, Billaud 2016 | A | direction |
| Si–void interface fraction | Taiwo 2016: 2D specific surface area under-estimates 3D by up to 52 % and depends on slicing direction (Table 4) | A | 2D within-dataset comparison only; never a 3D claim |
| within-electrode heterogeneity | Harris & Lu 2013, Forouzan 2018 | B | direction |
| 4D Si-graphite chemo-mechanics | Vanpeene 2025 (arXiv) | D | background, `check` |

## 2. Defect detection (Feature 1)

**OBSERVED.** Müller 2018 (full text) images Si/graphite cross-sections (BSE-SEM + X-ray tomography) and defines *detachment* as a gap between the Si particle and the carbon-black/binder domain that grows with cycle number and particle radius (Figs 2–3); electrically isolated particles are the modelled fade mechanism. Heenan 2020 (NMC811, grade B) supplies the intra-/inter-particle crack vocabulary for cathodes. Roldán 2024 (full text) defines FIB curtaining as "vertical, thin, uneven bands" caused by milling through phases of different density, and charging as halos on insulating regions; Giannuzzi & Stevie 1999 and Bassim 2011 list redeposition, implantation and preparation damage. Tegetmeyer-Kleine 2026 (arXiv, D) shows foundation-model transfer for cathode crack segmentation.

**INFERRED (how we apply it).**

1. Candidate classes we may name from BSE cross-sections: (a) crack = dark discontinuity inside a class-1/2 object, (b) rim gap = dark band between a class-2 object and surrounding class 1, (c) pull-out = class-0 cavity with particle-shaped outline, (d) isolated particle = class-2 object fully enclosed by class 0. Delamination (D2) is not observable.
2. Artefact exclusion before any candidate counts: aligned with the milling (vertical) direction → curtaining candidate; bright halo at the boundary → charging; cavity with smeared or redeposited bright material → preparation pull-out. These are *reviewer* decisions, logged per candidate; no automatic rule promotes a candidate to a defect.
3. Inter-annotator agreement: **no published figure for electrode cross-section defects was found**. Joskowicz 2018 (medical CT, C) shows expert disagreement is large even for well-defined structures. We therefore require ≥ 2 independent annotations on a pilot set and report Cohen κ (1960) / Dice before Feature 1 outputs are used for anything beyond `investigate`.
4. Presence of a reviewed defect is one line of evidence; "outside bounds" still needs a second independent line (reference deviation or literature bound).

## 3. Anomaly detection / batch comparison (Feature 2)

**OBSERVED.** Hotelling T² for individual observations needs exact Phase-I limits (Tracy 1992) and degrades with estimated parameters (Champ 2005; review Jensen 2006). Robust location/scatter (MCD: Rousseeuw & Van Driessen 1999; Hubert 2017; Vargas 2003) counters masking. Energy distance and MMD are equivalent two-sample families (Sejdinovic 2013; Székely & Rizzo 2013; Gretton 2007); permutation gives exact finite-sample calibration (Ernst 2004; Phipson & Smyth 2010 — never report p = 0). Aggregated MMD (Schrab 2021, D). Hierarchical bootstrap (Saravanan, D). One-class SVM (Schölkopf 2001), Isolation Forest (Liu 2008), unifying review (Ruff 2021). PatchCore (Roth 2022) on MVTec AD (Bergmann 2019), Anomalib (Akcay 2022); LIBAD (Sui 2026, D) reports homogeneous electrode appearance and poor transfer in battery-electrode anomaly detection. Conformal envelopes and conformal outlier p-values (Lei 2018; Bates 2023; Angelopoulos & Bates 2023). Applications: additive-manufacturing layer anomaly detection (Scime & Beuth 2018, B), image-based cell profiling aggregation (Caicedo 2017), batch effects (Leek 2010), micrograph CV/transfer (DeCost & Holm 2015; Goetz 2022).

**INFERRED.**

- Unit = image (n = 31; 7/7/17). Every statistic is computed on per-image feature vectors; tiles only feed descriptive dispersion.
- Report, per batch vs reference: T² (classical and MCD), energy distance/MMD, each with an image-level permutation null band (stratified by acquisition group where possible), and the minimum achievable p (7 vs 17 → two-sided minimum ≈ 2/C(24,7)). Conformal envelope with the achievable α (1/18 for 17 reference images) stated.
- Reference contamination: leave-one-reference-image-out; flag reference images whose removal changes a verdict.
- PatchCore-style maps are shown as review aids and aggregated to one score per image; they never upgrade a verdict (LIBAD warning).
- Any learned embedding must pass leave-one-acquisition-group-out before use (Section 5).
- Multiplicity across KPIs: Benjamini–Hochberg; both raw and adjusted p reported.

## 4. Traceability / SPC / liability (Feature 3)

**OBSERVED.** MSPC foundations (Mason & Young 2002; Bersimis 2006; Woodall 2000). Preregistration (Nosek 2018), researcher degrees of freedom (Simmons 2011), FDR (Benjamini & Hochberg 1995). Provenance: W3C PROV rationale (Moreau 2015), FAIR (Wilkinson 2016, full text), reproducible research (Peng 2011; Sandve 2013, full text). Traceability definition (Olsen & Borit 2013). Regulated-QC data integrity: ALCOA+ (Rattan 2017). ISO 9001 / IATF 16949 texts have no DOI and are **not** cited as claims (TODO: cite standard numbers only, no quotes).

**INFERRED — JSON ledger fields we can implement now** (most already exist in PR #1: `config_hash`, `git_sha`, per-file sha256):

| PROV concept | ledger field(s) | ALCOA+ attribute |
|---|---|---|
| entity | `image_id`, `file_sha256`, `result_sha256`, `mask_version` | original, accurate |
| activity | `stage` (S1…S11), `started_at`, `ended_at`, `config_hash`, `random_seed` | contemporaneous, complete |
| agent | `code_sha`, `tool_version`, `agent_or_person` | attributable |
| derivation | `inputs[]` → `outputs[]`, `wasDerivedFrom` | consistent |
| decision | `verdict` ∈ {within bounds, investigate, outside bounds}, `evidence_lines[]` (≥ 2 for outside), `claim_ids[]` from `claims.csv`, `frozen_plan_hash`, `exploratory: bool` | legible, enduring |

Phase I (reference establishment) and Phase II (new batch) are recorded as separate activities; any change after `git tag v1-frozen` is written with `exploratory: true` (AGENTS.md).

## 5. Artefact vs material

**OBSERVED.** Roldán, Redenbach & Schladitz 2024 (full text): no-reference indices for noise, contrast, blur, curtaining (FFT of the x-gradient; stripes concentrate on the horizontal frequency axis, following Münch 2009) and charging; indices near 0 mean serious quality problems; the curtaining index "works well only for higher dwell time, as curtaining artefacts are hidden by noise otherwise"; the charging index is misled by overexposed halos (Table 1); indices are comparable only between similar structures imaged under similar conditions. Fager 2020 and Prill 2012/2013: sub-surface pore walls (shine-through) overlap grey levels with solid and bias pore segmentation. Cazaux 2004: charging mechanisms. Joy 1996: absolute detector SNR. Immerkær 1996 / Pech-Pacheco 2000: Laplacian-based noise and sharpness. Confounding cases: Zhong 2021 (SEM quality tied to microscope conditions degrades ML robustness, B), DeGrave 2021 / Zech 2018 / Geirhos 2020 (shortcut learning on acquisition markers).

**INFERRED.** PR #1 already computes analogous covariates (`curtaining_score`, `hstripe_score`, `edge_charging`, `noise_sigma`, `sharpness`) and found that noise/sharpness separate batches (3.2× IQR) while 13 acquisition groups (height × XResolution tag) include 5 that span batches. That is exactly the Zhong/DeGrave pattern. Rules: (i) report artefact covariates beside every KPI; (ii) a KPI difference that vanishes under leave-one-acquisition-group-out is `investigate (acquisition)`; (iii) KPI(raw) vs KPI(destriped, Münch filter with frozen parameters) is a sensitivity check, not a correction; (iv) no absolute artefact threshold is adopted — Roldán's indices are only within-dataset comparators.

## 6. Measurement standards

**OBSERVED.** ASTM E1245 (automatic second-phase content), E562 (point-count volume fraction, Delesse V_V = A_A), E112 (grain size), E3 (specimen preparation) — scope text only. Stereology texts (Russ & DeHoff 2000; Baddeley & Jensen 2004). Taiwo 2016 (full text, battery electrodes): slice-wise 2D pore fraction of a graphite electrode scattered 0.443–0.531 around the 3D value 0.484 (Table 3); 2D specific surface area under-estimated 3D by up to 52 % and depended on slicing direction (Table 4). Saltykov unfolding and extensions (Lewis 1973; Higgins 2000; Lopez-Sanchez 2016) assume particle shape. ImageRep (Dahari 2025 = arXiv 2410.19568, full text): single-image phase-fraction confidence from the two-point correlation function; assumes macro-homogeneity (decaying correlations) and finite feature size; 95.5 % / 96 % empirical coverage on two battery separators (3D). Segmentation sensitivity (Iassonov 2009; Otsu 1979; Sezgin 2004). TauFactor (Cooper 2016) needs 3D.

**INFERRED.** Report "area fraction of grey-level class k" (E1245 wording), never "volume fraction of phase" unless the Delesse assumption and phase identity are stated. Size KPIs stay in px (2D equivalent diameter); no Saltykov conversion. Run ImageRep per image on class-2 and class-0 masks and flag images whose 95 % CI is wider than the batch difference; check the feature-size assumption for class 1 (large flakes). Report fractions at thresholds ×0.9/1.0/1.1 (PR #1): the ±10 % shift (0.02–0.04 in class 2) is as large as any batch gap, so fractions alone cannot support `outside bounds`.

## 7. Supervised labels caveat

**OBSERVED.** Label noise degrades learning and inflates data needs (Frénay & Verleysen 2014; Karimi 2020); benchmark labels contain pervasive errors (Northcutt 2021, D); weak labelling functions have unknown accuracies that must be modelled (Ratner 2017, full text); LLM annotators are task-dependent (Gilardi 2023, text only); recursive training on generated data collapses models (Shumailov 2024); micrograph segmentation quality depends on expert annotation (Durmaz 2021; Holm 2020).

**INFERRED.** Agent-generated masks or defect labels are *labelling functions*: logged with version, prompt/config hash and reviewer; usable for segmentation proposals and triage; never as outcome truth (good/bad battery) and never as training targets without human adjudication. Agreement between agent and human (κ / Dice) must be measured on a pilot set before any Feature-1 statistic is reported.

## 8. Report-back summary

- **Claims per grade**: A 15, B 10, C 41, D 6 (72 total; 109 BibTeX entries including supporting references).
- **Draft rules changed**: L3 (3–10 wt% → direction, upper ~6–10 wt%, no lower bound; Chae gives no number), L4 (25–40 % → direction only, number not found in Meyer; only Taiwo 0.484 and Haselrieder "10 % compression" exist), L1 (kept but demoted to mechanism, at resolution floor), S1 (calibration by permutation, not F/χ²), S2 (classical + MCD, LOO), D1 (explicit FIB-artefact exclusion), D2 (not_applicable now).
- **Our values vs bounds (if 25 nm/px)**: Si median 0.21 µm and p90 1.0 µm are above the 150 nm fracture size (mechanism only, not a verdict); class-2 area 0.09 → ~10 wt% of solids under four unverified assumptions, at/above the commercial <6–8 wt% and inside the 5–20 wt% research range; class-0 area 0.10 is below every published electrode porosity found (0.25–0.48) and is most plausibly a class-definition/FIB effect → `investigate`; heterogeneity and anisotropy have no numeric bounds.

## 9. TODO (not filled with unverified claims)

- L4: locate an exact calendered-graphite porosity passage (Meyer 2017 full text or Günter 2022 mercury porosimetry tables) — both resolved but only abstracts were accessible.
- L3: obtain the nominal Si wt% from Polaron; obtain the Chae 2019 full-text table.
- Inter-annotator agreement for electrode cross-section defects: none found; measure in-house.
- ISO 9001 / IATF 16949 / ISO 13322 (particle size by image analysis): no DOI; cite by standard number only after reading scope.
- ImageRep applicability to class 1 (graphite flakes) needs a feature-size check before use.

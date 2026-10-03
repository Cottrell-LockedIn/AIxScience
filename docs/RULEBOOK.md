# RULEBOOK — evidence-backed screening rules for the FIB-SEM batch comparison

Status: docs-only revision. **Supersedes** the earlier `RULEBOOK_literature_bounds.md` draft referenced in PR #5 (`docs/EVIDENCE_BASE.md`). It is a specification for how verdicts may be produced; it changes no code and no `configs/v1.yaml` threshold. Identifier mapping (FM01–FM22 consultant failure modes, A01–A06 preparation/measurement modes, F01–F11 repository features, FMC claims) is stated once in `docs/FAILURE_MODE_MAP.md` and reused here.

Verdict vocabulary (AGENTS.md / FRAMEWORK §00): **`within bounds` / `investigate` / `outside bounds`**, always about *this batch's image distribution relative to the Batch_3 reference*, never "good/bad battery". `investigate` is a first-class outcome. "Bounds" are **relative** (distribution shift vs Batch_3 in MAD units with image-level permutation p) unless a rule explicitly states an absolute literature bound — and no rule in this version does.

## 0. Data and unit conventions every rule inherits

- Unit of evidence: the image (8-character stem), n = 31 (Batch_1 7, Batch_2 7, Batch_3 17). Tiles are pseudo-replicates and never enter a test, resample or fold (PR #2).
- Quantities are in px or dimensionless; nm only as `*_nm_if25` and never as a threshold (A05, FMC17).
- Classes are named "class 2 (stated Si)", "class 1 (stated graphite)", "class 0 (stated void/pore)". Identity is stated by Polaron and not image-verified; the consultant records composition and Si/SiOx as unconfirmed (FMC22). Binder and additives are lumped into class 0/1.
- Batch_3 is the reference but not error-free: PR #2 leave-one-out flags 5 of 17 reference images at abs(z) > 3 (vc2whyaq, ufdvpb81, hzumfsms, cfe5vt7s, 0grcilhi).
- Acquisition covariates per image (BSE): curtaining_score, hstripe_score, noise_sigma, sharpness, mean grey; edge_charging (In-Lens). Acquisition group = height × resolution tag, 13 groups.
- Evidence grades are PR #5's A–D; "consultant judgement" marks statements without a resolvable DOI.

## 1. Gates (apply before any rule can produce a verdict)

| Gate | Requirement | Evidence | If it fails |
|---|---|---|---|
| G1 image-level | The statistic is computed per image and compared with an image-level permutation null (≥ 10 000 permutations) and effect size in Batch_3 MAD units. | PR #2 harness; PR #5 S1–S3 (Tracy–Young–Mason, Champ; Caicedo/Leek, grade C) | no verdict |
| G2 acquisition first | The feature is not `acquisition_confounded` (z_group > z_batch and p_group < 0.05 in PR #2's confound table) **or** the batch contrast is re-tested after residualising on the six covariates and keeps the same sign with p < 0.05. | PR #2 VALIDATION §Acquisition confounding; LOIO−LOGO gap +0.129 shows session leakage | at most `investigate` |
| G3 segmentation | The contrast holds under both segmentation variants and the threshold sensitivity is < 0.5 × Batch_3 MAD (PR #2 decision table). | S16 pietsch2018 (C, FMC15); PR #2 | at most `investigate` |
| G4 reference integrity | Removing the five abs(z) > 3 Batch_3 images does not flip the verdict; classical and MCD distances agree. | PR #5 S2 (Vargas 2003, Rousseeuw & Van Driessen 1999, grade C) | at most `investigate` |
| G5 observability | The failure mode served is `directly observable` or `proxy only` in `docs/FAILURE_MODE_MAP.md`. | map | rule is out of scope |

PR #2 harness on the 11 pre-registered features alone (`results/validate/features_f01_f11/`, config `de199d6c8d69`): all 11 `investigate` (F05, F06 confounded; F09 borderline; rank stability < 0.7 for all but F06; no sensitivity rows yet). PR #2 result for the current KPIs: all 8 are `investigate` (frac_c0 fails G3 at 1.24 × MAD; c2 count density, c2 eqdiam median/p90 and c0 region area fail G2). No rule below is currently past its gates.

## 2. Escalation: two independent lines of evidence

`outside bounds` for a batch requires **two lines of evidence that are independent in measurement family and in failure dependence**, each individually passing G1–G5 for the same batch, plus balanced artefacts:

- **Line families** (a rule may only pair across families): (i) class-0 geometry (F01, F08, F09, F10); (ii) class-2 object statistics (F02–F07, F11); (iii) a validated defect detector (cracks, bright-object screen); (iv) an external measurement supplied by Polaron (EDS, thickness, porosimetry, nominal composition).
- **Balance condition**: no acquisition covariate differs between the test batch and Batch_3 at image-level permutation p < 0.05, or the contrast is re-established on residualised features.
- **Independence**: two features computed from the same class map with the same threshold (e.g. F01 and F08) are *one* family and cannot form the pair on their own; they need a family (ii), (iii) or (iv) partner.
- Grey-level-only evidence (brightness, class-2 inflation) can never be the second line because A02 redeposition and A03 shine-through cannot be excluded as covariates (FMC13, FMC14).
- One line passing → `investigate` with the named mode(s) and the missing second line stated. Zero lines passing and no covariate imbalance → `within bounds` *for the quantities tested*, with the cannot-decide list attached.
- Anything decided after the held-out batch is scored is logged as exploratory (AGENTS.md).

## 3. Rules

Column key — **Serves**: FM/A modes; **Quantity**: feature(s); **Bound**: relative or 'direction only'; **Evidence**: DOI + grade (bibkeys in `docs/evidence/failure_mode_refs.bib` and PR #5 `references.bib`) or consultant judgement; **Applies if**; **Exclude first**; **Verdict reachable** (max).

### 3.1 Material rules (relative to Batch_3)

| Rule | Serves | Quantity | Bound | Evidence | Applies if | Exclude first | Verdict reachable |
|---|---|---|---|---|---|---|---|
| **R-FM13/14** compaction & 2D pore architecture | FM13, FM14 (weight 4, 4) | F01 c0 area fraction; F08 c0 local-thickness median px; F09 c0 chord anisotropy; F10 c0 fraction IQR (512 px) | **relative, two-sided**: shift vs Batch_3 median in MAD units with image-level p; no absolute porosity window (PR #5 L4 removed 25–40 %; class-0 0.10 is below all published porosities) | 10.1016/j.jpowsour.2024.235063 guk2024 (A, metadata) direction compaction→density; 10.3389/fenrg.2014.00056 sheng2014 (A) non-monotonic wetting; 10.3390/batteries8050046 scheffler2022 (A) pore-size distribution more sensitive than porosity; 10.1111/jmi.12389 taiwo2016 (C) 2D ambiguity | class 0 definition unchanged between batches; same detector (BSE); both segmentation variants available | A03 shine-through (detector disagreement), A01 curtaining for F09, A04 (frac_c0 threshold sensitivity), noise_sigma (ρ −0.63 with c0 region size), A06 | `outside bounds` only as line (i) **paired with** a family (ii)/(iii)/(iv) line; alone → `investigate`. **Currently `investigate`** (G3 fails for F01; F08/F09/F10 lack sensitivity measurements) |
| **R-FM08** dispersion / agglomerates | FM08 (4); mentions FM03 | F06 Clark–Evans R (primary); F05 count density; F03/F04 size tail as context | **direction only**: R lower than Batch_3 = more clustered class-2 (stated Si) objects; no literature value for R exists for electrodes | 10.1016/j.jcis.2022.06.006 kitamura2022 (A, metadata) dispersion→resistance; FMC19/FMC20 repository observation | class-2 object count per image sufficient for CE (≥ 100 objects); mean grey and curtaining balanced or residualised | **acquisition group** (F06 p = 0.0077 across groups vs 0.052 across batches, ρ 0.53 with mean grey; F05 p = 0.0007), A03, A04 min-component size, A06 (2D adjacency ≠ agglomerate) | in principle line (ii) partner for `outside bounds`; **currently `investigate` only** because G2 fails and no residualised re-test exists |
| **R-FM07** coating / matrix cracks | FM07 (4) | artefact-aware crack detector output per image: count and total length of elongated class-0 features **not** aligned with the FIB milling direction and not co-located with curtaining stripes (specification only; not implemented) | direction only: more coating-scale cracks than Batch_3 | 10.1002/ente.201900722 kumberg2019 (A) drying cracks; 10.3390/batteries9020111 schoo2023 (B); 10.1017/S1431927619014752 kim2019 (C) and PR #5 roldan2024 for curtaining; Heenan 2020 (PR #5, B) crack vocabulary (cathode, cycled — vocabulary only) | detector validated on images with high vs low curtaining_score and shown insensitive to it; particle-internal fissures excluded by object size | **A01 curtaining**, hstripe_score, A02, resin shrinkage, the unresolved Batch_1 fissure candidate | line (iii) partner for `outside bounds` once validated; **currently no verdict** (detector absent) |
| **R-FM04** foreign / high-Z particle candidates | FM04 (5) | per-object BSE grey-level and size outlier screen on class-2 (stated Si) objects (F04 p90 tail as interim) | direction only: brighter-than-class-2 objects are higher-mean-Z *candidates* | 10.1007/978-1-4939-6676-9 goldstein2018 (C) BSE Z-contrast; 10.1007/s10921-025-01208-7 zangerle2025 (A) contamination harms cells | BSE channel; object not at a charging halo (edge_charging) | A02 redeposition, edge_charging, A03, Si vs SiOx | **`investigate` + EDS request only; never `outside bounds`** (identity unknowable by SEM grey level) |
| **R-FM10** composition proxy | FM10 (4), FM22 context | F02 c2 area fraction | direction only; no wt% conversion (PR #5 L3: commercial Si loading ~6–10 wt% upper range, 0 wt% exists) | 10.1002/batt.202300396 reynolds2023 (A) formulation sensitivity; 10.3390/batteries8050046 scheffler2022 (A) conductivity falls with Si content; PR #5 L3 (B) | class 2 = Si assumed and stated as such; Delesse (PR #5 russ2000, C) | A03 brightening, A04 threshold, Si/SiOx | `investigate` only; action = ask Polaron for nominal Si wt% |
| **R-FM02/21** particle–matrix gaps | FM02 (5), FM21 (4, conditional) | F11 c2 perimeter fraction adjacent to c0; F07 solidity | direction only: more class-2 perimeter bordering class 0 than Batch_3 = more detachment-like gaps | 10.1002/ente.202200852 weber2022 (A) network/cohesion; 10.3390/batteries8050046 scheffler2022 (A) springback with Si; PR #5 Müller 2018 detachment vocabulary (cycled, B) | fresh electrode; both classes from same map | A02, A03, A04 (F11 median is 0.001 — at resolution floor), A06 | `investigate` only (quantity at floor; cycled-electrode vocabulary) |
| **R-HET** lateral heterogeneity | FM13 non-uniformity, FM14 | F10 c0 fraction IQR over 512 px tiles | direction only: heterogeneity harms durability (PR #5 L5, Harris & Lu 2013, B) | PR #5 L5 (B); no cutoff anywhere | tiles used only as within-image descriptors, image stays the unit | A01 (stripes raise local IQR), A03 | `investigate` only; may be a within-family companion to R-FM13/14, never the second line |

### 3.2 Reference and statistics rules (how any material rule is tested)

| Rule | Serves | Quantity | Bound | Evidence | Verdict reachable |
|---|---|---|---|---|---|
| R-STAT1 | all | Hotelling T² / Mahalanobis on image-level features | **calibrated by image-level permutation**, never by F/χ² at n = 17, p ≳ 5 | PR #5 S1 Tracy–Young–Mason 1992, Champ 2005 (C) | none by itself; it is a gate |
| R-STAT2 | all | classical vs MCD distance | disagreement → `investigate` | PR #5 S2 Vargas 2003, Rousseeuw & Van Driessen 1999 (C) | `investigate` |
| R-STAT3 | all | hierarchy | tiles never independent; image-level resampling only | PR #5 S3 Caicedo 2017, Leek 2010 (C); Saravanan (D, preprint, `check`) | gate |
| R-COV | all | six acquisition covariates | covariate shift between batches is itself reported; `within bounds` is only claimable when covariates are balanced | PR #2 LOIO/LOGO (+0.129 gap); PR #5 roldan2024 (C) | gate / `investigate` |

### 3.3 Artefact rules (A01–A06) — they demote, never promote

| Rule | Serves | Quantity | Action | Evidence |
|---|---|---|---|---|
| R-A01 | A01 (5) | curtaining_score, hstripe_score | report per batch; residualise F09, F10, frac_c1, crack detector before testing | kim2019 (C), PR #5 roldan2024 (C) |
| R-A02 | A02 (5) | none measurable | standing caveat in every verdict involving brightness or gaps | delfino2024 (C, metadata), PR #5 Giannuzzi 1999 / Bassim 2011 (C) |
| R-A03 | A03 (4) | class-0 level, In-Lens vs BSE disagreement | forbid absolute class-0 bounds; flag images where detectors disagree | kim2019 (C), PR #5 prill2012 (C) |
| R-A04 | A04 (5) | threshold sensitivity vs Batch_3 MAD, two segmentation variants | G3 | pietsch2018 (C), PR #2 |
| R-A05 | A05 (4) | res_tag only | no nm thresholds; `*_nm_if25` labelling | fu1994 (C, metadata) |
| R-A06 | A06 (4) | none | 3D quantities on the cannot-decide list | taiwo2016 (C) |

## 4. Things this rulebook cannot decide (stated in every report)

| Cannot decide | Why | Modes affected |
|---|---|---|
| **Chemistry / phase identity** | no EDS; BSE grey ranks Z but does not identify (FMC18); Si vs SiOx indistinguishable; Polaron's class names are stated, not image-verified; consultant: unconfirmed | FM04, FM10, FM21, FM22 |
| **Adhesion / delamination to the collector** | collector interface not confirmed in frame | FM01, FM18, FM21 (adhesion part) |
| **Moisture / residual liquid** | no SEM signature in vacuum | FM15, FM16 |
| **3D structure** (tortuosity, connectivity, true agglomerate size, 3D porosity) | single 2D sections; stereological ambiguity | FM08 (size), FM14 (transport), A06 |
| **Electrochemical / electrical performance** (resistance, capacity, thermal behaviour, wetting) | not image quantities; literature gives directions in other systems | FM03, FM22, FM14 (wetting) |
| **Roll-, edge- and plan-view defects** (stripes, pinholes, wrinkles, imprints, cut edges, thickness, loading) | field of view is one cross-section of ~7000 px; no edge or surface | FM05, FM06, FM11, FM12, FM17, FM19, FM20 |
| **Binder distribution** | binder lumped into class 0/1; thickness axis unknown | FM09, FM02 (direct) |
| **Absolute porosity or composition levels** | class-0 0.10 is a measurement definition (shine-through, resin, binder lumping), not a material value; wt% needs identity and densities | FM10, FM13 |
| **Cycling-induced damage** | fresh electrodes | out of scope |
| **Instrument calibration** | no standard imaged | A05 |

## 5. Consultant importance weights — routing only

Weights (5/4/3/2, "4, conditional") are copied into `docs/FAILURE_MODE_MAP.md` with the consultant's caveat (FMC21). In this rulebook they:

- order which rules are evaluated and reported first (FM04 and FM02 before FM10; FM13/14 before FM21), and
- order reviewer attention and EDS/Polaron requests.

They are **not** a multiplier, prior, weight or term in any statistic, score, threshold or verdict. A weight-5 mode that is unobservable stays unobservable.

## 6. Changes relative to the earlier draft (removed / demoted) and why

| Draft item | Status here | Reason |
|---|---|---|
| L4 calendered-graphite porosity window 25–40 % (Meyer 2017) | **removed** | not found in the cited record (PR #5); class-0 0.10 is below every published value, so the gap is a measurement-definition issue (A03/A04); S10/S11/S13 give no window; sheng2014 wetting is non-monotonic → two-sided relative rule only (R-FM13/14) |
| L3 commercial Si 3–10 wt% lower limit | **removed**; upper range kept as context | 0 wt% exists in production (PR #5 L3, Günter 2022); area fraction → wt% needs unverified identity and densities (R-FM10 direction only) |
| L1 150 nm critical Si diameter as discriminator | **demoted to mechanism context, not a rule** | 150 nm = 6 px at the segmentation floor (PR #5); nm thresholds forbidden (A05); every resolvable class-2 object is above it |
| L5 heterogeneity harms durability | **kept as direction only** (R-HET) | review-grade (B), no cutoff |
| L2 detachment / isolation gaps (Müller 2018) | **kept as direction only**, folded into R-FM02/21 at `investigate` | cycled-electrode mechanism; our masks have no binder class, F11 sits at the resolution floor (median 0.001) |
| L6 flake orientation / anisotropy | **kept as within-dataset direction** (F09 inside R-FM13/14) | image axes vs collector normal unknown; A01 curtaining biases vertical chords |
| D1 cracks / pull-out / isolation detector with milling-direction exclusion | **kept as specification** (R-FM07); no verdict until validated and inter-annotator agreement measured | PR #5 found no published agreement figure (`not_found`); A01 confound |
| D2 delamination | **`not_applicable` → out of scope** (FM01) | collector interface not in frame; ledger records "not measured" |
| Any absolute Clark–Evans / count-density bound for agglomeration | **not introduced** | no literature value; F06/F05 acquisition-confounded (FMC19/20) |
| Crack rule on raw class-0 elongated objects | **demoted to detector specification** (R-FM07) | A01 curtaining mimics cracks; detector must be validated against curtaining_score first |
| Bright-blob contamination rule | **capped at `investigate` + EDS** (R-FM04) | identity not knowable from BSE grey; A02 confound |
| Hotelling T² with F-distribution limits | **replaced by permutation calibration** (R-STAT1) | PR #5 S1 |
| Consultant weights as score multipliers (any draft aggregation) | **forbidden** (§5) | handoff: weights have no specified aggregation |

## 7. What changes for the presentation

Say what we screen, what we cannot, and why — one sentence each.

**We can honestly claim to screen (as `investigate`/`within bounds` on relative, image-level evidence):**

- **FM13/FM14 compaction and 2D pore architecture** — F01/F08/F09/F10 compare each batch's class-0 geometry to Batch_3 with image-level permutation tests; relative only, because the absolute class-0 level is a measurement definition and 3D transport is not measured.
- **FM08 dispersion/agglomeration** — F06 Clark–Evans R and F05 are computed per image, but on current data they track acquisition group (p = 0.0077 / 0.0007) more than batch, so the honest statement is "measured, confounded, `investigate`".
- **FM04 foreign high-Z particle candidates** — a bright-object screen can nominate candidates for EDS; it cannot identify a contaminant and never yields `outside bounds`.
- **FM10 composition proxy** — class-2 (stated Si) area fraction is tracked relative to Batch_3; it is not a wt% and depends on an unverified phase identity.
- **FM02/FM21 particle–matrix gaps** — F11/F07 are tracked but sit at the resolution floor (median 0.001), so only a large shift would register, and it would still be `investigate`.
- **FM07 coating cracks** — we can show the detector design and why curtaining (A01) must be excluded; we cannot yet report a crack rate.

**We explicitly cannot screen (and will say so on the slide):**

- **FM01 delamination / FM18 cutting-induced coating loss** — no collector interface or manufacturing edge is in frame.
- **FM03 / FM22 electrical resistance** — electrical outcomes are not image quantities.
- **FM05, FM06, FM11, FM12, FM17, FM19, FM20** — roll-scale, edge and plan-view defects do not exist in a single cross-section of ~175 µm (if 25 nm/px).
- **FM09 binder distribution** — binder is not a segmented class and the thickness axis is unknown.
- **FM15 / FM16 moisture and residual liquid** — SEM in vacuum has no moisture signature.
- **Chemistry of any class or bright object** — no EDS; Polaron's phase names are stated, not verified, and the consultant records composition as unconfirmed.
- **Cycling-induced modes** — the material is fresh.

**Verdict framing for the slide:** on current validation every KPI is `investigate`; no mode currently reaches `outside bounds`, and only FM13/14, FM08 and FM07 could ever do so under §2. The consultant's weight-5 modes are mostly unobservable in this data; high importance and high measurability barely overlap, and that is the main finding to present.

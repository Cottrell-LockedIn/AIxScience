# Failure-mode map: consultant handoff vs what our images can carry

Status: docs-only review (no code or config changes). Companion to `docs/RULEBOOK.md`, `docs/evidence/claims_failure_modes.csv` and `docs/evidence/failure_mode_refs.bib`. Read with `docs/READ/Consultant Failure Modes Handoff.md` (the source of every weight below), PR #5 (`docs/EVIDENCE_BASE.md`, grades A–D), PR #3 (`src/qc/features.py`, F01–F11), PR #4 (`docs/FEATURE_DOSSIER.md`) and PR #2 (`results/validate/kpi_per_image/VALIDATION.md`).

## Identifier mapping (stated once, used everywhere)

| Prefix | Meaning | Source |
|---|---|---|
| **FM01–FM22** | Consultant's material / manufacturing failure modes. The handoff numbers them F01–F22; they are renamed FM01–FM22 here to avoid colliding with the repository's feature IDs. | handoff table "Material and manufacturing failure modes" |
| **A01–A06** | Consultant's preparation and measurement failure modes (artefacts). Kept as in the handoff. | handoff table "Preparation and measurement failure modes" |
| **F01–F11** | Repository measurement features implemented in `src/qc/features.py` (PR #3): F01 c0 area fraction, F02 c2 area fraction, F03 c2 equivalent-diameter median (px), F04 c2 equivalent-diameter p90 (px), F05 c2 count density per Mpx, F06 c2 Clark–Evans R, F07 c2 area-weighted solidity median, F08 c0 local-thickness median (px), F09 c0 chord anisotropy h/v, F10 c0 fraction IQR over 512 px tiles, F11 c2 perimeter fraction adjacent to c0. | PR #3 |
| **S01–S18** | Consultant's source register (kept as cross-reference; DOIs in `failure_mode_refs.bib`). | handoff |
| **FMC01–FMC22** | Claim rows added by this PR in `docs/evidence/claims_failure_modes.csv`. | this PR |
| **L*, S*, M* (PR #5)** | Claim ids in PR #5 `claims.csv`; referenced where a PR #5 finding is reused (e.g. L4 porosity). | PR #5 |

Phase wording: class 2 = silicon, class 1 = graphite, class 0 = void/pore is **stated by Polaron, not image-verified**; the consultant handoff states that composition and Si/SiOx remain **unconfirmed**. Both positions are recorded (FMC22) and not resolved here. "Class 2 (stated Si)" below means exactly that.

## What our data is

- 31 independent images (Batch_1 7, Batch_2 7, Batch_3 17 reference; image/stem is the unit, tiles are pseudo-replicates).
- One 2D FIB-SEM cross-section per image with BSE + In-Lens + ETD (or SE) views of the same field; 13 acquisition groups (height × resolution tag).
- Fresh (uncycled) electrode material; **no collector interface confirmed in frame** (docs/DATA_AUDIT.md C1 / handoff FM01 note), no manufacturing edge, no plan-view, no 3D stack, no EDS, no cycling data.
- Pixel units; nm only "if 25 nm/px is true" (`*_nm_if25` columns).
- Batch_3 is the reference but not error-free; three artefact covariates per image (curtaining_score, hstripe_score, edge_charging, noise_sigma, sharpness, mean grey) exist in `results/artefacts_per_image.parquet`.

## Observability classes used

- **directly observable** – the geometry that defines the mode is in the 2D section and a current feature or covariate measures it; identity caveats may still apply.
- **proxy only** – a measurable quantity *correlates with* the mode under stated assumptions (phase identity, 2D→3D, segmentation); it can raise a question, not settle one.
- **unobservable** – the mode is not in the frame, not in the imaging physics, or is a hidden/process/performance outcome.

Evidence grades are PR #5's: **A** peer-reviewed primary measurement, **B** review or related application, **C** method/standard/textbook, **D** preprint or single source. "consultant judgement" marks statements without a resolvable DOI.

## Material / manufacturing modes FM01–FM22

Weights are copied from the handoff. The handoff's caveat applies to every row: *weights are editorial ordinal estimates for research prioritisation, not probabilities, severities, risk-priority numbers or thresholds, with no specified aggregation* (FMC21). They are used in `docs/RULEBOOK.md` only as a routing/priority hint.

| ID | Consultant failure mode | Weight | Observability in our data | Carrier (features / covariate / detector) | Literature direction (grade) | Confounds that mimic it | Verdict consequence |
|---|---|---|---|---|---|---|---|
| FM01 | Loss of adhesion / coating–collector delamination | 5 | **unobservable** – needs the collector interface; DATA_AUDIT C1 and the handoff both say no interface is confirmed in frame; "an unidentified image boundary is not evidence that a collector interface is present" | none (would need interface localisation + gap detector) | Adhesion falls with binder depletion at the collector and with fast drying/thick coatings – S01 jaiser2016 (A, metadata only), S02 kumberg2019 (A) – direction only | A02 preparation damage, image boundary, resin gap | **out of scope**; cannot produce any verdict |
| FM02 | Insufficient coating cohesion / weak particle–binder network | 5 | **proxy only** – binder and carbon black are lumped into class 0/1; gaps around class-2 objects (F11) are at best a cohesion hint | F11 (class-2 perimeter adjacent to class 0), F07 solidity | Network redistribution changes cohesion and conductivity – S03 weber2022 (A), S08 reynolds2023 (A) – direction only | A02 redeposition, A03 shine-through, segmentation (A04), resin infiltration | `investigate` only |
| FM03 | Poor electronic connectivity / excessive resistance | 5 | **unobservable** – electrical property; routed through the FM08 proxy at most | none (via FM08 → F06/F05) | Agglomeration raises resistivity at equal composition – S04 kitamura2022 (A, metadata only) | same as FM08 | **out of scope** as a verdict target; FM08 `investigate` can mention it |
| FM04 | Foreign-particle contamination incl. metallic particles | 5 | **proxy only** – bright BSE objects are higher-Z *candidates* (goldstein2018, C); "bright particles are not chemically identified contaminants in this dataset" (handoff) | per-object BSE grey/size outlier screen (F04 p90 tail; not a dedicated detector yet) | Contamination harms capacity and thermal behaviour – S05 zangerle2025 (A) – direction only | A02 redeposition, edge_charging halos, Si/SiOx (stated class 2), In-Lens/BSE disagreement | `investigate` + **EDS request**; **never `outside bounds`** |
| FM05 | Cutting-edge burrs, dross, protrusions | 5 | **unobservable** – no manufacturing edge in frame; the FIB face is a preparation surface | none | Poor cut edges harmful – S07 lee2018 (B) | A02 (FIB-milled face), frame edge | **out of scope** |
| FM06 | Persistent coating stripes / uncoated line defects | 5 | **unobservable** – mm-scale plan-view line defects; one field is ~7000 px wide (~175 µm if 25 nm/px) | none | Line defects harm capacity/thermal – S05 zangerle2025 (A); taxonomy S06 schoo2023 (B) | n/a | **out of scope** |
| FM07 | Composite-matrix or coating cracks | 4 | **directly observable** in principle (crack geometry is in-section) **but artefact-confounded**: must be separated from A01 curtaining (vertical thin bands) and from a fissure inside one particle | artefact-aware crack detector (not implemented; must use curtaining_score and orientation relative to milling direction as covariates); no F01–F11 carries it | Cracking increases with drying rate and thickness – S02 kumberg2019 (A); processing/bending cracks – S06 schoo2023 (B) – direction only | **A01 curtaining**, A02, hstripe_score, resin shrinkage, particle fissure (handoff: one unresolved Batch_1 fissure candidate) | `investigate` now; eligible for `outside bounds` **only** after the detector is validated against A01 and a second independent line exists (RULEBOOK R-FM07) |
| FM08 | Persistent agglomerates / inadequate dispersion | 4 | **proxy only** – 2D adjacency cannot tell a persistent agglomerate from touching particles (handoff S04 note; taiwo2016 C) | F06 Clark–Evans R (primary), F05 count density, F03/F04 size tail | Poor dispersion raises resistance – S04 kitamura2022 (A, metadata only) – direction only | **acquisition group**: F06 permutation KW p = 0.0077 across 13 groups vs 0.052 across batches, ρ = 0.53 with BSE mean grey (FMC19); F05 p = 0.0007 (FMC20); PR #2 flags c2 count density / eqdiam as acquisition-confounded | `investigate` only until F06 is residualised on acquisition covariates and re-tested; eligible for `outside bounds` in principle only with a second non-class-2-count line (RULEBOOK R-FM08) |
| FM09 | Binder depletion / uneven binder / drying migration | 4 | **unobservable** – binder is lumped into class 0/1; the through-thickness axis is unknown without the collector or surface | none (F10 local IQR measures lateral heterogeneity, not a binder gradient) | Binder migrates to the surface during drying – S01 jaiser2016 (A, metadata only), S02 kumberg2019 (A) | A03, A04 | **out of scope** |
| FM10 | Unsuitable constituent proportions / formulation imbalance | 4 | **proxy only** – F02 class-2 (stated Si) area fraction is a composition proxy only if class 2 = Si, Delesse holds and densities are assumed (PR #5 L3) | F02 | Formulation changes adhesion, dispersion, conductivity – S08 reynolds2023 (A) – direction only, tested ranges are a research design space | A03 shine-through brightening, segmentation threshold (A04), Si vs SiOx | `investigate` only (ask Polaron for nominal wt%) |
| FM11 | Nonuniform coating thickness / areal loading | 4 | **unobservable** – no collector or free surface in frame, so no thickness | none | Loading/thickness control – S08 (A), S09 VDMA guide (consultant judgement, no DOI) | n/a | **out of scope** |
| FM12 | Web slips, wrinkles, tension interruptions | 4 | **unobservable** – roll-scale plan-view | none | Taxonomy – S06 schoo2023 (B) | n/a | **out of scope** |
| FM13 | Unsuitable or nonuniform compaction | 4 | **proxy only** – 2D class-0 fraction and pore-thickness proxies for density; absolute level unusable (class-0 0.10 is below every published porosity found in PR #5 L4 → measurement definition, not material) | F01, F08, F09 (plus F10 for non-uniformity) | More compaction → higher density/lower porosity – S10 guk2024 (A, metadata only); not monotonically better or worse – S11 sheng2014 (A, consultant full-text), S13 scheffler2022 (A) – **direction only, two-sided** | A03 shine-through (fills pores with subsurface signal), A04 segmentation (frac_c0 threshold sensitivity 1.24 × Batch_3 MAD in PR #2), A06 2D section, noise_sigma (ρ −0.63 with c0 region size) | `investigate`; eligible for `outside bounds` only via RULEBOOK R-FM13/14 (two independent families, both segmentation variants, covariates balanced) |
| FM14 | Pore architecture restricting wetting / transport | 4 | **directly observable (2D pore geometry only)** – F08/F09/F10 are measured; wetting, tortuosity and connectivity are **not** (taiwo2016 C, A06) | F08, F09, F10 (F01 shared with FM13) | Pore geometry matters alongside total porosity; wetting non-monotonic – S11 sheng2014 (A); Si shifts pore-size distribution more than porosity – S13 scheffler2022 (A) – direction only | A01 curtaining (vertical streaks bias F09), A03, A04, A06 | same as FM13 (joint rule R-FM13/14) |
| FM15 | Excessive retained moisture / uptake | 4 | **unobservable** – vacuum SEM has no moisture signature (handoff) | none | Hidden quality variable – S12 kosfeld2023 (A, metadata only) | n/a | **out of scope** |
| FM16 | Residual processing liquid / incomplete drying | 3 | **unobservable** | none | Process-level – S02 kumberg2019 (A); S09 (consultant judgement) | n/a | **out of scope** |
| FM17 | Edge coating thinning / incomplete coverage / dewetting | 3 | **unobservable** – manufacturing edge not established in the supplied fields (handoff) | none | Taxonomy – S06 schoo2023 (B) | frame edge, A02 | **out of scope** |
| FM18 | Cutting- or handling-induced coating loss / local delamination | 4 | **unobservable** – manufacturing damage and FIB preparation damage (A02) are indistinguishable origins without the edge | none | S07 lee2018 (B), S06 (B) | **A02**, frame edge | **out of scope** |
| FM19 | Pinholes / isolated uncoated spots | 2 | **unobservable** – plan-view surface defect | none | Point defects did not significantly affect cell behaviour – S05 zangerle2025 (A) | n/a | **out of scope** |
| FM20 | Local surface imprints / microcompression marks | 2 | **unobservable** – optical surface class | none | S06 schoo2023 (B) | n/a | **out of scope** |
| FM21 | Si-electrode compaction debonding, springback, reduced adhesion | 4, conditional | **proxy only**, conditional on class 2 = Si (unconfirmed): gaps at class-2/class-0 boundaries (F11) and particle shape (F07) are the only in-frame hints; collector adhesion itself is unobservable (FM01) | F11, F07 | More Si → more springback, altered pore-size distribution – S13 scheffler2022 (A) – direction only | A02, A03, A04; Si vs SiOx | `investigate` only |
| FM22 | Elevated resistance from Si content / contact network | 4, conditional | **unobservable** – electrical outcome; FM10 (F02) is the only related proxy | none (via F02) | Conductivity decreases with Si content independent of density – S13 scheffler2022 (A) | same as FM10 | **out of scope** as a verdict target |

Unresolved candidate (handoff): one moderate-confidence fissure inside a small pale particle in Batch_1. Not promoted to a mode, no weight; stays a review-aid annotation.

Cycling-induced modes (particle fracture, Li plating, dead Li, SEI growth, cathode degradation, used-cell thermal damage) are **out of scope** for a fresh-electrode dataset (handoff "Unresolved candidates" section).

### Counts (FM01–FM22)

| Class | n | Modes |
|---|---|---|
| directly observable | 2 | FM07 (artefact-confounded), FM14 (2D pore geometry only) |
| proxy only | 6 | FM02, FM04, FM08, FM10, FM13, FM21 |
| unobservable | 14 | FM01, FM03, FM05, FM06, FM09, FM11, FM12, FM15, FM16, FM17, FM18, FM19, FM20, FM22 |

Modes that can ever contribute to `outside bounds`: **FM13/FM14 (jointly), FM07, FM08** – and each only under the conditions in `docs/RULEBOOK.md`. On the present evidence (PR #2 validation: all 8 KPIs `investigate`; F06/F05 acquisition-confounded; no validated crack detector) **none of them currently can**. Everything else is `investigate`-only or out of scope.

## Preparation / measurement modes A01–A06

These are failures of the evidence, not of the electrode. Their weights refer to impact on interpretation (handoff). Their "verdict consequence" is always the same kind: they **gate or demote** a material verdict; they never produce `outside bounds` on their own.

| ID | Mode | Weight | Observability in our data | Carrier | Literature (grade) | What it mimics | Consequence |
|---|---|---|---|---|---|---|---|
| A01 | FIB curtaining | 5 | **directly observable** (per-image `curtaining_score`, BSE) | curtaining_score, hstripe_score covariates | Curtain artefacts in Si/C–graphite anode FIB-SEM, Fourier filtering – S14 kim2019 (C); PR #5 roldan2024 definition | FM07 cracks (vertical bands), F09 anisotropy, F10 local heterogeneity, frac_c1 (ρ −0.54 in PR #2) | any rule touching FM07/FM13/FM14 must show the batch contrast survives residualisation on curtaining_score |
| A02 | FIB redeposition / preparation-induced surface modification | 5 | **unobservable as a covariate** – no per-image measure exists; standing caveat | none | Lift-out preparation controls – S15 delfino2024 (C, metadata only); PR #5 Giannuzzi/Bassim | FM04 bright deposits, FM18 coating loss, FM02 gaps | grey-level-only evidence can never be the second line for `outside bounds` |
| A03 | Shine-through / subsurface structure in the section plane | 4 | **proxy only** – In-Lens vs BSE disagreement and the implausible class-0 level (0.10, PR #5 L4) are indirect signs | class-0 fraction level, detector disagreement (no dedicated covariate) | Manual shine-through removal before segmentation – S14 kim2019 (C); PR #5 prill2012 | FM13/FM14 (pores filled with subsurface signal → low class-0), FM10 (bright class-2 inflation) | absolute class-0 bounds are forbidden; FM13/FM14 rules are relative to Batch_3 only |
| A04 | Segmentation / preprocessing bias | 5 | **directly observable as uncertainty** – two segmentation variants and threshold sensitivity are computed (PR #2 `kpi_sensitivity`) | threshold sensitivity vs Batch_3 MAD | Binarisation changes microstructural parameters – S16 pietsch2018 (C) | any F01–F11 shift | a batch contrast must hold under both segmentation variants (RULEBOOK G3) |
| A05 | Dimensional calibration / understated uncertainty | 4 | **unobservable** – only the file resolution tag (25399944/25 → 25.00 nm/px) exists; no standard imaged | res_tag only | SEM calibration standard and uncertainty – S17 fu1994 (C, metadata only) | nm-scale claims (PR #5 L1 150 nm) | no rule uses nm thresholds; all bounds in px or dimensionless |
| A06 | 2D sections read as 3D structure | 4 | **unobservable** – single sections, no serial stack | none | 2D estimates are ambiguous; tortuosity/connectivity need 3D – S18 taiwo2016 (C) | FM08 agglomerate size, FM14 connectivity | 3D quantities are on the cannot-decide list; 2D descriptors are compared to Batch_3, not to 3D literature values |

### Counts (A01–A06)

directly observable 2 (A01, A04 as measured uncertainty) · proxy only 1 (A03) · unobservable 3 (A02, A05, A06).

## Contradictions and tensions found (recorded, not resolved)

1. **Phase identity.** Polaron (via AGENTS.md / PROJECT_STATE) names class 2 = Si, class 1 = graphite, class 0 = void/pore; the consultant says composition and Si/SiOx are unconfirmed and bright particles are not identified. PR #5 L3 adds that a 2022 automotive anode was silicon-free. All documents here write "class 2 (stated Si)" and keep FM21/FM22 conditional (FMC22).
2. **Porosity level.** PR #5 L4 found class-0 = 0.10 is below every published electrode porosity (0.25–0.48) and removed the earlier 25–40 % window; the consultant's FM13/FM14 sources (S10, S11, S13) give directions but no window either. Any absolute porosity bound is therefore unsupported from both sides and does not appear in the RULEBOOK.
3. **Fissure candidate.** The handoff declines to classify the Batch_1 particle fissure; PR #5 (Müller 2018 detachment, Heenan 2020 crack vocabulary) gives a cycled-electrode vocabulary that does not apply to fresh material. Kept as an annotation, not a mode.
4. **FM08 evidence vs data.** Kitamura 2022 supports "agglomeration → resistance" but our only agglomeration proxies (F06, F05, F03/F04) are acquisition-confounded in PR #2 and in this session's recomputation. The literature direction is valid; the measurement is not yet usable.
5. **Weights vs evidence.** Five of the six weight-5 modes (FM01, FM03, FM05, FM06, and FM04 as identity) are unobservable or identity-blocked in our data. The high-priority list and the measurable list barely overlap; the presentation must say so.
6. **Source register S17.** The handoff cites Fu, Croarkin & Vorburger (1994) without a DOI; Crossref resolves the title to 10.6028/jres.099.015 (used here). S09 (VDMA guide) has no DOI and is treated as consultant judgement.

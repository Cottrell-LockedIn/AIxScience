# Track 4 handoff: possible failure modes, supporting research and importance

Prepared: 4 October 2026. Scope: fresh, unused, line-sampled composite electrode material supplied through Polaron, examined after destructive preparation. A graphite-rich anode is the leading visual hypothesis; composition and optional silicon/SiOx remain unconfirmed.

This file contains the requested failure-mode/defect list, source support and qualitative importance weights. It does not contain a pass/fail ruleset, acceptance thresholds, classifier coefficients or a diagnosis of the supplied batches.

## Context and meaning of the weights

- The current material context supersedes the earlier description of batteries dismantled after manufacture: these are fresh electrode samples, with no established prior cell use or cycling.
- The industrial wet-processing route is relevant literature context, not a confirmed recipe. Binder, additive, collector and processing-liquid identities are unknown.
- The evidence summarized here validates mechanisms or relevant defect classes in the studies' tested systems. It does not establish their occurrence in these samples.
- Image features and annotations were described in supplied context; this handoff did not independently re-examine the image pixels or physical calibration.
- Polaron is identified as the material/data provider. Actual manufacturers, constituent suppliers and sites are not established.

**Importance is an editorial ordinal estimate of potential impact on electrode integrity, function or downstream safety:**

| Weight | Meaning |
|---|---|
| 5 | Very high potential importance |
| 4 | High potential importance |
| 3 | Moderate potential importance |
| 2 | Strongly context-dependent importance |

The weights are engineering judgments supplied for research prioritization, not values published by the cited papers. They are not occurrence probabilities, calibrated severity scores, empirical risk-priority numbers, normalized percentages or pass/fail thresholds. They have no specified mathematical aggregation. Importance can change with defect extent, formulation, location and intended product. Evidence strength is separate from importance.

## Material and manufacturing failure modes / defect families

IDs F01–F22 are identifiers for this handoff; they do not replace the M01–M15 identifiers in the earlier scoped knowledge pack.

| ID | Possible failure mode / defect family | Importance | Research support and scope |
|---|---|---:|---|
| F01 | Loss of adhesion / coating–current-collector delamination | 5 | [S01](#s01) links substrate adhesion to local binder concentration. [S02](#s02) experimentally examines adhesion loss across drying conditions and coating thicknesses. An unidentified image boundary is not evidence that a collector interface is present. |
| F02 | Insufficient coating cohesion / weak internal particle–binder network | 5 | [S03](#s03) measures graphite-electrode cohesion and adhesion changes arising from altered graphite/carbon-black/binder interactions. Cohesion concerns integrity within the coating; adhesion concerns its attachment to the collector. |
| F03 | Poor electronic connectivity / excessive electrode resistance | 5 | [S04](#s04) finds higher resistivity for agglomerated electrodes despite identical compositions. [S03](#s03) shows conductivity changes when carbon black is redistributed between particle surfaces and the carbon–binder network. |
| F04 | Foreign-particle contamination, including metallic particles | 5 | [S05](#s05) tests introduced anode particle contamination and reports downstream capacity and thermal effects. [S06](#s06) discusses equipment abrasion and other contamination sources. Bright particles are not chemically identified contaminants in this dataset. |
| F05 | Cutting-edge burrs, dross and protrusions | 5 | [S07](#s07) experimentally studies anode cutting geometry and discusses separator-integrity and electrical-stress concerns associated with poor edges. Laser-specific mechanisms depend on the actual cutting route. |
| F06 | Persistent coating stripes / extended uncoated line defects | 5 | [S05](#s05) experimentally tests anode line defects and downstream effects. [S06](#s06) describes line-like coating interruptions and their possible production origins. |
| F07 | Composite-matrix or coating cracks | 4 | [S02](#s02) studies cracking during drying of graphite-based coatings. [S06](#s06) discusses processing and bending-related coating cracks. Coating-scale cracking is distinct from a fissure inside one particle. |
| F08 | Persistent agglomerates / inadequate constituent dispersion | 4 | [S04](#s04) directly links mixing sequence, binder adsorption, dispersion, packing and electrode resistivity. The study does not establish whether adjacent particles in these sections form persistent agglomerates. |
| F09 | Binder depletion, uneven binder distribution or drying-driven migration | 4 | [S01](#s01) tracks binder gradients during drying. [S02](#s02) examines additive redistribution and adhesion. Relevant to compatible wet-processed formulations; the visible fine material is not identified as binder. |
| F10 | Unsuitable constituent proportions / formulation imbalance | 4 | [S08](#s08) investigates how graphite-anode formulation changes slurry and electrode properties. It validates formulation sensitivity rather than a universally correct composition. |
| F11 | Nonuniform coating thickness or areal loading | 4 | [S08](#s08) investigates formulation, slurry behaviour and coating outcomes. [S09](#s09) covers loading/thickness control in electrode production. Local sections do not establish whole-roll loading. |
| F12 | Web slips, wrinkles and tension-related coating interruptions | 4 | [S06](#s06) describes these electrode-manufacturing defect classes and their relation to substrate movement and coating coverage. This is a broader production study, not a graphite-only experiment. |
| F13 | Unsuitable or nonuniform compaction | 4 | [S10](#s10) demonstrates thickness-dependent changes in graphite-anode density and acoustic response under calendering. [S11](#s11) connects compaction with wetting. Greater compaction is not universally better or worse. |
| F14 | Pore architecture that restricts wetting or electrolyte transport | 4 | [S11](#s11) measures a non-monotonic wetting response to graphite-electrode compaction. Pore geometry matters alongside total porosity. This validates a structural/functional concern, not a diagnosis from dark regions in these images. |
| F15 | Excessive retained moisture / moisture uptake during production or handling | 4 | [S12](#s12) investigates moisture sorption, uptake kinetics and moisture levels along production. It establishes a hidden quality variable rather than an SEM appearance signature. |
| F16 | Residual processing liquid / incomplete drying | 3 | [S02](#s02) investigates thickness-dependent liquid removal during drying. [S09](#s09) describes drying and moisture management. Support is process-level; no residual-liquid failure is observed or quantified here. |
| F17 | Edge coating thinning, incomplete coverage or local dewetting | 3 | [S06](#s06) describes coating-edge defect origins. Importance depends on position and extent; the actual manufacturing edge has not been established in the supplied fields. |
| F18 | Cutting- or handling-induced coating loss / local delamination | 4 | [S07](#s07) discusses cutting-related delamination and tests cutting outcomes. [S06](#s06) discusses coating integrity in subsequent processing. Manufacturing and destructive-preparation damage remain different possible origins. |
| F19 | Pinholes / isolated uncoated spots | 2 | [S05](#s05) establishes pinholes as anode coating defects, but its tested point defects did not significantly affect cell behaviour. Inclusion as a defect family does not establish a universal performance penalty. |
| F20 | Local surface imprints / microcompression marks | 2 | [S06](#s06) identifies microcompression as an optical defect class. Its appearance alone does not establish material damage or a substantial performance penalty. |
| F21 | Silicon-containing-electrode compaction-induced debonding, springback and reduced collector adhesion | 4, conditional | [S13](#s13) connects silicon content, deformation, springback and adhesion changes in silicon–graphite electrodes. Applicable relevance remains conditional because Si/SiOx is unconfirmed here. |
| F22 | Elevated resistance associated with silicon content and contact-network changes | 4, conditional | [S13](#s13) measures composition- and compaction-dependent resistivity in graphite and silicon–graphite electrodes. Silicon presence itself is not a failure; the concern is inadequate electrical performance for the intended design. |

## Preparation and measurement failure modes

These are failures or limitations of image evidence, not electrode-material defects. Importance refers to potential impact on interpretation and measurement reliability, so these weights have a different subject from F01–F22.

| ID | Preparation / measurement failure mode | Importance | Research support and scope |
|---|---|---:|---|
| A01 | FIB curtaining | 5 | [S14](#s14) explicitly identifies curtain artifacts in Si/C–graphite anode FIB–SEM and develops filtering to reduce them. |
| A02 | FIB redeposition / preparation-induced surface modification | 5 | [S15](#s15) describes specimen-preparation methods and controls addressing redeposition and curtaining in electrode characterization. |
| A03 | Shine-through / subsurface structure mistaken for the section plane | 4 | [S14](#s14) reports manual removal of shine-through artifacts before segmentation. |
| A04 | Segmentation or preprocessing bias affecting derived structure | 5 | [S16](#s16) quantifies descriptor uncertainty from binarization choices in negative-electrode tomography. Its numerical uncertainties are not measurements of uncertainty in these SEM images. |
| A05 | Incorrect dimensional calibration / understated measurement uncertainty | 4 | [S17](#s17) establishes SEM calibration and measurement uncertainty concerns. Reported pixel sampling in the supplied context is not independently verified resolving power. |
| A06 | Misinterpreting 2D sections as representative 3D structure | 4 | [S18](#s18) examines geometric ambiguity in electrode characterization using 2D versus 3D methods. The reported FIB–SEM technique does not establish a registered serial 3D volume. |

## Unresolved candidates and descriptive variation

The supplied context reports one moderate-confidence fissure candidate inside a small pale particle in Batch 1, referenced by two annotation packages. Its chemical identity and origin remain unresolved. No directly applicable source in this handoff establishes that this particular appearance is manufacturing-induced graphite or silicon fracture. It is therefore not promoted to a validated manufacturing failure mode or assigned an established importance weight.

Particle section size, shape, fines, alignment, large cavities, dense regions and possible bands are relevant structural descriptors. The cited research supports sensitivity of electrode structure to processing; it does not establish that each of these appearances is intrinsically a failure. Their specific harmful manifestations are represented where supported in F08–F14.

Cycling-induced particle fracture, lithium plating, dead lithium, continued SEI growth, cathode-specific degradation and used-cell thermal degradation are outside the active fresh-electrode scope. Downstream cell tests in some cited papers support the potential consequences of an as-manufactured defect; they do not imply prior cell use of the supplied material.

## Source register

Access descriptions preserve the limits of this literature review. A source may support a defect taxonomy or material-property relationship without experimentally validating every proposed causal explanation.

### S01

**Jaiser, S.; Müller, M.; Baunach, M.; Bauer, W.; Scharfer, P.; Schabel, W. (2016). Investigation of film solidification and binder migration during drying of Li-Ion battery anodes.** *Journal of Power Sources*, 318, 210–219. DOI: 10.1016/j.jpowsour.2016.04.018.

[Publisher source](https://www.sciencedirect.com/science/article/abs/pii/S0378775316303561). Primary experimental work on a graphite/binder/carbon-black/solvent model system. Access: publisher abstract and indexed section excerpts; not a complete protocol audit.

### S02

**Kumberg, J. et al. (2019). Drying of Lithium-Ion Battery Anodes for Use in High-Energy Cells: Influence of Electrode Thickness on Drying Time, Adhesion, and Crack Formation.** *Energy Technology*, 7, 1900722. DOI: 10.1002/ente.201900722.

[Institutional full-text PDF](https://publikationen.bibliothek.kit.edu/1000099617/124500563). Primary experiments on aqueous graphite/carbon-black/CMC/SBR coatings. Access: full author PDF inspected. Results depend on formulation and thickness; study operating values are not acceptance limits for this material.

### S03

**Weber, M.; Moschner, R.; Kwade, A. (2023; first published online 2022). Modifying the Network Structures of High Energy Anodes for Lithium-Ion Batteries through Intensive Dry Mixing.** *Energy Technology*, 11, 2200852. DOI: 10.1002/ente.202200852.

[Publisher source](https://onlinelibrary.wiley.com/doi/abs/10.1002/ente.202200852). Primary graphite-anode study. Access: indexed publisher abstract and conclusions, supplemented by parallel source review. “Dry mixing” is a premixing operation followed by slurry processing; it is not evidence that the supplied electrodes used a solvent-free manufacturing route.

### S04

**Kitamura, K.; Tanaka, M.; Mori, T. (2022). Effects of the mixing sequence on the graphite dispersion and resistance of lithium-ion battery anodes.** *Journal of Colloid and Interface Science*. DOI: 10.1016/j.jcis.2022.06.006.

[Publisher source](https://www.sciencedirect.com/science/article/abs/pii/S0021979722009730). Primary graphite-anode mixing experiment. Access: publisher abstract, highlights and indexed sections. Supports different dispersion/resistivity outcomes despite identical constituent composition in the tested system.

### S05

**Zangerle et al. (2025). Detection of Anode Coating Defects in Batteries Electrode Production and their Effect on Cell Performance.** *Journal of Nondestructive Evaluation*, 44, article 66. DOI: 10.1007/s10921-025-01208-7.

[Author-institution publication page](https://portal.fis.tum.de/en/publications/detection-of-anode-coating-defects-in-batteries-electrode-product/). Primary anode-defect study using introduced line/pinhole defects and particle contamination, followed by cylindrical-cell evaluation. Access: institutional abstract and indexed primary-source material; complete performance protocol not audited in this handoff.

### S06

**Schoo, A.; Moschner, R.; Hülsmann, J.; Kwade, A. (2023). Coating Defects of Lithium-Ion Battery Electrodes and Their Inline Detection and Tracking.** *Batteries*, 9(2), 111. DOI: 10.3390/batteries9020111.

[Publisher source](https://www.mdpi.com/2313-0105/9/2/111). Inline detection/production study with a defect catalogue; cause and consequence discussions also draw on literature and expert experience. Access: indexed publisher sections and figures; direct page retrieval was limited. It is not exclusively an anode or graphite study. Cathode mud-crack mechanisms are not transferred here.

### S07

**Lee, D. (2018). Investigation of Physical Phenomena and Cutting Efficiency for Laser Cutting on Anode for Li-Ion Batteries.** *Applied Sciences*, 8(2), 266. DOI: 10.3390/app8020266.

[Publisher source](https://www.mdpi.com/2076-3417/8/2/266). Primary anode laser-cutting experiment; safety concerns and mechanical-cutting defects are also discussed in its introduction. Access: indexed publisher abstract and sections. No finding establishes that these samples were laser cut.

### S08

**Reynolds, C. D. et al. (2024; online publication 2023). Impact of formulation and slurry properties on lithium-ion electrode manufacturing.** *Batteries & Supercaps*, 7(2), e202300396. DOI: 10.1002/batt.202300396.

[Author-institution publication page](https://wrap.warwick.ac.uk/id/eprint/182109/). Primary graphite-anode formulation study. Access: institutional publication metadata/abstract and indexed author-PDF excerpts, supplemented by parallel source review. Collector-supported electrical measurements can include coating/interface contributions.

### S09

**VDMA Battery Production and PEM, RWTH Aachen University (2026). Production Process of a Lithium-Ion Battery Cell.**

[Industry process guide](https://www.vdma.eu/documents/34570/35405938/Production_Process_of_a_Lithium-Ion_Battery_Cell_2026.pdf/72b475da-b7c6-3b59-1405-236ef0e9efeb?filename=Production_Process_of_a_Lithium-Ion_Battery_Cell_2026.pdf). Industry reference rather than a primary failure experiment. Access: full guide inspected in the earlier scoped review; electrode-production material principally pp. 6–11. The route and process ranges are illustrative.

### S10

**Guk, E. et al. (2024). Investigation of calendaring parameters on the microstructure of graphite anodes within lithium-ion batteries: Insights from ultrasonic testing.** *Journal of Power Sources*, 614, 235063. DOI: 10.1016/j.jpowsour.2024.235063.

[Publisher source](https://www.sciencedirect.com/science/article/pii/S0378775324010152). Primary CMC/SBR graphite-anode manufacturing experiment. Access: publisher abstract and indexed methods/results; complete institutional PDF not inspected here. Shows process-dependent physical changes, not universal morphology-based failure categories.

### S11

**Sheng, Y. et al. (2014). Effect of Calendering on Electrode Wettability in Lithium-Ion Batteries.** *Frontiers in Energy Research*, 2, 56. DOI: 10.3389/fenrg.2014.00056.

[Publisher full text](https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2014.00056/full). Primary graphite/CMC/SBR/carbon-black electrode experiment. Access: full publisher text inspected. Directly measured wetting response is non-monotonic with compaction in this formulation.

### S12

**Moisture behavior of lithium-ion battery components along the production process (2023).** *Journal of Energy Storage*, 57, 106174. DOI: 10.1016/j.est.2022.106174.

[Publisher source](https://www.sciencedirect.com/science/article/pii/S2352152X22021636). Primary component moisture study and production campaign. Access: publisher abstract and indexed sections. Includes anodes as well as other cell components; moisture is not diagnosed by SEM appearance.

### S13

**Scheffler, S.; Jagau, R.; Müller, N.; Diener, A.; Kwade, A. (2022). Calendering of Silicon-Containing Electrodes and Their Influence on the Mechanical and Electrochemical Properties.** *Batteries*, 8(5), 46. DOI: 10.3390/batteries8050046.

[Publisher source](https://www.mdpi.com/2313-0105/8/5/46). Primary graphite-reference and silicon–graphite electrode experiments. Access: extensive indexed publisher methods/results/conclusions. Supports the conditional mechanical/electrical mechanisms above. Cycling-induced damage discussed elsewhere in the paper is outside the present diagnostic scope.

### S14

**Kim, D. et al. (2019). Image Segmentation for FIB-SEM Serial Sectioning of a Si/C–Graphite Composite Anode Microstructure Based on Preprocessing and Global Thresholding.** *Microscopy and Microanalysis*, 25(5), 1139–1154. DOI: 10.1017/S1431927619014752.

[PubMed record and primary abstract](https://pubmed.ncbi.nlm.nih.gov/31387658/). Primary anode FIB–SEM methods study. Access: indexed author abstract; full article not audited. Its study used serial sections for 3D reconstruction; multiple detector views of one field are a different form of data.

### S15

**Delfino et al. (2024). Lift-Out Specimen Preparation and Multiscale Correlative Investigation of Li-Ion Battery Electrodes Using Focused Ion Beam-Secondary Ion Mass Spectrometry Platforms.** *ACS Applied Materials & Interfaces*. DOI: 10.1021/acsami.4c12915.

[Publisher source](https://pubs.acs.org/doi/10.1021/acsami.4c12915). Primary correlative preparation/chemical-imaging study, including pristine graphite/Si–C material and a separately studied cycled condition. Access: indexed publisher sections, figures and conclusions; direct full-text access limited. The study knew its composition; it does not identify bright particles in these samples.

### S16

**Pietsch, P.; Ebner, M.; Marone, F.; Stampanoni, M.; Wood, V. (2018). Determining the uncertainty in microstructural parameters extracted from tomographic data.** *Sustainable Energy & Fuels*. DOI: 10.1039/C7SE00498B.

[Publisher full text](https://pubs.rsc.org/en/content/articlehtml/2018/se/c7se00498b). Primary study of negative-electrode X-ray tomography and binarization uncertainty. Access: full text inspected. Binarization uncertainty and unresolved physical features are distinct limitations.

### S17

**Fu, J.; Croarkin, M.; Vorburger, T. V. (1994). The Measurement and Uncertainty of a Calibration Standard for the SEM.**

[NIST publication record](https://www.nist.gov/publications/measurement-and-uncertainty-calibration-standard-sem). Primary metrology publication. Access: NIST abstract/publication record. Provides calibration context rather than a material-specific failure study.

### S18

**Taiwo, O. O. et al. (2016). Comparison of three-dimensional analysis and stereological techniques for quantifying lithium-ion battery electrode microstructures.** *Journal of Microscopy*. DOI: 10.1111/jmi.12389.

[Author-institution abstract](https://research.manchester.ac.uk/en/publications/comparison-of-three-dimensional-analysis-and-stereological-techni/). Primary comparison of electrode-structure characterization approaches. Access: institutional abstract; full text not audited here.

## Provenance

This handoff consolidates the scoped research package and the subsequent sourced failure-list response, adding the directly relevant graphite-network, formulation, anode-defect and silicon-containing calendering papers identified in the later review. Source text is summarized, not reproduced. No original article full text or images are bundled.

Dataset-specific facts originate in the user-supplied narrowed material context. Importance weights and organization of the list are the assistant's judgments; source support and access limitations remain explicit.

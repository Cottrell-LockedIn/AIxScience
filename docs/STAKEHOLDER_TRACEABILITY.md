# Investigate: stakeholders and evidence paths

The user-supplied 4 October materials-scientist handoff, sections 12 and 13,
defines investigation responsibilities. It does not identify a responsible
company, person, proven process cause or numerical likelihood of fault.

The existing `frontend/src/riskCatalog.json` remains the canonical mapping of
P01–P14 manufacturing/formation patterns and U01–U14 future-service scenarios
to features, sources, investigation roles, prerequisites and actions.

## Roles from the handoff

| ID | Stakeholder | Responsibility to investigate |
|---|---|---|
| R01 | Silicon / SiOx material supplier | Particle architecture, chemistry, incoming particle-size distribution and surface treatment. |
| R02 | Si–graphite composite producer / coating supplier | Granulation, encapsulation, carbon coating and composite mechanical robustness. |
| R03 | Electrode formulation and slurry-mixing team | Recipe, binder dispersion, mixing history, stability and settling. |
| R04 | Coating and drying team | Wet-film thickness, substrate wetting, drying profile and coating uniformity. |
| R05 | Calendering team | Densification, roll settings, porosity and mechanical damage. |
| R06 | Cell assembly, electrolyte filling and wetting team | Assembly compression, electrolyte quantity, vacuum fill, soak time and temperature. |
| R07 | Cell formation and electrochemical QC team | Initial charge/discharge protocol, formation efficiency, resistance and release capacity. |
| R08 | Microscopy, metrology and materials-validation team | Preparation artefacts, calibration, phase identity, segmentation and representative sampling. |
| R09 | BMS and charge-control team | Charge/discharge envelopes, SOC estimation, voltage termination and regenerative-charge limits. |
| R10 | Pack thermal and mechanical integration team | Cell temperature distribution, cooling, preload, compliance and pressure evolution. |
| R11 | Application owner and duty-cycle team | Actual load waveform, storage SOC, dwell, ambient exposure and required useful life. |
| R12 | Cell life-validation and diagnostics team | Matched duty-profile qualification, reference performance tests, mechanism confirmation and target-based acceptance. |

R08 supports every card through microscopy and measurement validation. This
shared prerequisite is separate from each pattern's explicit owner list; it
does not add an inferred process contributor to the canonical catalogue.

## Reading the diagram

Recorded image measurements are linked to an explicitly selected investigation
pattern. A pattern is a possible explanation to explore, not a detected defect.
Its stakeholder branches mean “involve this team to investigate,” not “this team
caused the problem.” Scientific references support mechanisms in the studies;
they do not prove the origin of a problem in the current specimen.

Primary trigger features, supporting measurements and missing independent
checks must remain distinct. Selected control envelopes are not qualified
manufacturing acceptance limits. No selected limit, missing measurements,
missing stage comparisons or missing operating context must never become a
pass or a confirmed failure.

For example, P01 links small/scarce mask-defined pores to a possible transport
or wetting concern. R05 checks electrode compression; R06 checks filling and
soaking; R07 checks resistance and formation performance. R08 checks that the
image and mask support the measurements. These are different investigation
roles, not three competing claims of blame.

The uploaded specimen is fresh from manufacturing, with no service use.
Future-service scenarios describe conditional questions about later operation;
they must not be presented as its measured history or observed failure.

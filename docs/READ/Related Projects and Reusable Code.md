# Related Projects and Reusable Code

## Best immediate references

| Project | What it offers | Licence/status | Recommended use |
|---|---|---|---|
| ImageRep | Phase-fraction representativity diagnostic using two-point correlation | BSD-3-Clause | Optional, only under stated assumptions |
| Anomalib | Maintained industrial anomaly-detection implementations | Apache-2.0 | Fast benchmark harness |
| PatchCore | Normal-only anomaly localization baseline | Apache-2.0; older reference repo | Baseline or conceptual reference |
| DINOv2 | Frozen patch-level visual representations | Apache-2.0 code/weights | Challenger after dataset inspection |
| LIBAD | Recent battery-manufacturing anomaly benchmark and DA-Core code | BSD-3 code; CC BY 4.0 gated dataset | Study evaluation and false-positive risks |
| Hierarch | Hierarchical bootstrap and permutation tools | MIT | Nested image/specimen statistics |
| scikit-image/OpenCV | Classical segmentation, morphology and texture | Permissive libraries | First-line interpretable pipeline |
| Streamlit | Rapid Python demonstration UI | Apache-2.0 | Default UI unless the team has a frontend specialist |

## Useful but conditional

| Project | Limitation |
|---|---|
| KontElPro | Direct SEM quality-regression reference, but AGPL-3.0-or-later and narrow LFP task |
| micro-sam | MIT and maintained, but trained primarily for biological microscopy |
| MATBOX | Broad microstructure analysis with BSD licence, but MATLAB and much of its strength is 3D |
| PoreSpy/TauFactor | Valuable for segmented porous 3D structures; not automatically valid for 2D SEM |
| GDCount | MIT SEM grain tool; very small project and must be validated |
| Google Microscope Image Quality | Useful focus-QC concept, but archived and biological-domain model |

## Reference-only unless licensing changes

- MatSAM: no clear repository licence found.
- Uncertainty-Aware Particle Segmentation for SEM: paper and code are relevant, but no repository licence was detected.
- Do not copy code from an unlicensed repository.

## Recent literature lessons

- Polaron reports automated separation of pore, single-crystal NMC, polycrystal NMC and crack regions in one OEM deployment, reducing analysis from eight hours to under five minutes. This is a vendor case study, not an independently reproduced benchmark.
- LIBAD shows that a strong-looking AUROC can coexist with unacceptable false positives. It is VIS/X-ray rather than SEM, so it is a warning rather than direct validation.
- Recent battery crack work supports frozen self-supervised encoders with lightweight heads, but uses three very large NMC cross-sections and remains a preprint.
- SEM calendering classification shows morphology can encode manufacturing state, but image-level splitting may not prove new-batch generalisation.
- ImageRep provides a strong Polaron-adjacent uncertainty idea, but only for segmented phase fraction.

## Skills and development references

- Use the installed `impeccable` skill when designing an actual interface.
- PyModel React frontend skills:
  https://github.com/PyModel/react-frontend-skills
- Scientific agent skills:
  https://github.com/K-Dense-AI/scientific-agent-skills
- Streamlit’s former agent-skills repository is archived; treat it as reference material only.

Inspect the exact skill, licence, dependencies and instructions before installation. Do not install broad skill packs wholesale during the event.

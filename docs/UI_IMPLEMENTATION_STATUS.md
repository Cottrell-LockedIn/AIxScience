# Cottrell UI implementation — 4 October 2026

Replaced the raw Streamlit JSON view with a React + TypeScript + Vite interface implementing the planning PRD's visual system and four-screen workflow. Backend uses FastAPI to adapt authentic saved model output. Setup exposes eleven selectable criteria plus disabled F12, optional material context and TIFF validation. Review records retain field/source identity. Results provide Overview, Investigate and Material details with export controls and a lazy Three.js view.

## Current scope
- Saved results, previews when source TIFFs are locally available, local screening limits, human review, result navigation, CSV/JSON and printable current-view report.
- New scientific inference is capability-gated. No production job orchestration, authenticated multiuser workspace, cloud storage or deployment is claimed.
- Mask artifacts remain unavailable; the 3D view shows one original image plane. Optional exact-layer support does not generate segmentation.
- Current automatic verdict remains Inspect further, in accordance with the PRD's unvalidated policy gate.

## Verification
- TypeScript and Vite production build pass.
- FastAPI exposes normalized real saved results and release capabilities.
- Browser inspection and independent review are being completed before handoff.

## Run
`./scripts/dev.sh` starts localhost:8501 (web) and :8502 (API). Git remote remains Cottrell-LockedIn/AIxScience. Working branch: codex/cottrell-prd-ui.

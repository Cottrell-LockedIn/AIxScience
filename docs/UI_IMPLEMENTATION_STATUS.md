# Cottrell implementation — 4 October 2026

## Implemented

React/TypeScript/Vite replaces the raw Streamlit JSON view. The light workspace implements setup → real processing → human region review → results, with the processing state reused for report finalization. `./scripts/dev.sh` starts the web app on localhost:8501 and API on :8502.

Original TIFF upload validates files, stores byte-preserving sources and runs the existing engine in a separate exploratory worker. Run state persists across browser reloads; cancellation is terminal. A source/config/artifact/environment fingerprint and model refit gate dispatch. No core `src/qc` recipe or official held-out output is changed.

Review has an enlarged original-image crop, full-field navigator, zoom controls, three highlighted threshold-proximity suggestions and exact 512 px close-ups. Manual region selection remains available. This separate diagnostic is not local classifier confidence. Reviews preserve source/run/method hashes and original coordinates.

Results provide Overview, Investigate and Material details. Exact model masks, phase layers and raw TIFFs are available per completed run. The Three.js view splits actual 2D layers with explicitly illustrative depth, bounded animation and reduced-motion support. Results styling fixes button text contrast, spacing and top-aligned desktop evidence placement.

The 11 native KPI values link to the supplied scientist's 14 manufacturing/formation patterns and 14 future-service scenarios. Selected criteria and supporting features are separate. Sources, required evidence, investigation roles, caveats and recommended checks remain visible; no numerical failure probability is assigned. Unknown evidence is not a pass. Aspect ratio is not measured in v1. Scale conversion is restricted to the attested source hash.

## Verification and limits

A real browser TIFF upload ran successfully through the engine, CPU fallback, review and results. Run 1656d9bdb6dd4dc29914304a060a4442 uses a training-source image to verify plumbing, not independent accuracy. Model refit max coefficient difference was 1.37e-14 (limit 1e-9). The official held-out artifact was not rerun.

TypeScript/Vite build and focused wrapper/region tests pass. Existing held-out tests: 27 passed, 3 skipped for absent raw TIFFs. One existing PC-profile permutation-artifact comparison remains different under the local unpinned scientific dependencies; see ENGINE_INTEGRATION_AUDIT.md. Modal has no authenticated local profile, so GPU execution is not verified here. No deployment, multiuser authentication or production lot-release policy is claimed.

Git target: Cottrell-LockedIn/AIxScience. Branch: codex/cottrell-prd-ui. Latest fetched main 0517998 merged at 0bfdc16 without conflicts. Local data and run artifacts remain ignored.

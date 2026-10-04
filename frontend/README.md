# Cottrell web application

Run the complete local app from the repository root:

```sh
uv pip install --python .venv/bin/python -r app/requirements-web.txt
npm --prefix frontend ci
./scripts/dev.sh
```

Open http://127.0.0.1:8501. Vite updates the browser when frontend source changes. The local API is on 8502. Both bind to localhost. Stop an old Streamlit process on 8501 first.

This React interface replaces the old JSON console. It implements setup, saved-result processing, optional region review, and Overview / Investigate / Material details results. It presents existing scientific outputs and validates new TIFFs; it does not re-run the protected heldout evaluation or provide new inference before the release bundle is approved. Original image availability controls previews. No artificial masks or defect probabilities are produced. The optional Three.js/R3F scene is lazy-loaded and presents original 2D evidence with explicit illustrative depth.

Validation: `npm --prefix frontend run build` (TypeScript and production bundle). API and responsive browser checks are recorded in docs/UI_IMPLEMENTATION_STATUS.md.

Sources and licence notices: React (MIT), Vite (MIT), Three.js (MIT), React Three Fiber (MIT), Lucide (ISC), Inter (OFL-1.1), FastAPI (MIT). The UI was authored for this event; no pre-event Matter code or artifacts were copied.

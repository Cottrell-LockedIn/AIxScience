# Cottrell hosted application

## Architecture

The React app is built from this repository. `site/worker.mjs` serves it on ChatGPT Sites and forwards same-origin `/api/*` requests to the separately hosted Python analysis service. Sites cannot execute the Python/scientific stack itself. `modal_web.py` contains the backend deployment adapter; see `HOSTED_BACKEND.md`.

The gateway requires two production runtime values, managed through Sites:

- `COTTRELL_API_URL`: verified HTTPS origin of the full analysis service, not only a GPU-embedding function.
- `COTTRELL_API_TOKEN`: secret shared only with the protected backend. Never put it in a frontend build variable or commit it.

The Worker forwards only content type, accept and range headers plus its own backend token. Browser authentication and cookies remain at Sites. Mutation requests must originate from the same Site. Backend redirects are not followed. API responses use `no-store`. Static app assets contain no private run data.

## Build and verify

1. `npm ci --prefix frontend` when frontend dependency inputs change or dependencies are missing.
2. `npm run test:site` verifies gateway routing, secret isolation, redirect handling, upload streaming and unavailable-backend behavior.
3. `npm run build` runs TypeScript/Vite then writes a standalone Cloudflare-compatible ES-module Worker to `dist/server/index.js`. The build enforces a conservative 3 MiB size ceiling.
4. Verify the hosted backend rejects unauthenticated access and completes an exploratory upload/run/result flow before publishing the API-backed app.
5. Use the Sites skill's source-sync, version and deployment workflow. Preserve `.openai/hosting.json` and its project identity. Runtime values must be set before deploying the saved version.

Local development continues through `scripts/dev.sh`; the original local backend is unchanged.

## GitHub source and future updates

Canonical source: https://github.com/Cottrell-LockedIn/AIxScience, branch `main`.

The Sites source repository is separate from GitHub. A GitHub push alone does not update the live Site. For each update, inspect the new GitHub revision, carry forward the Site identity and production runtime values, build and verify that exact source, then publish it through Sites. Backend changes additionally require a reviewed Modal redeployment before the matching frontend is published. Never silently replace the API with mock or saved-only results.

Do not claim continuous synchronization until a supported automatic update path is configured and verified. Credentials and backend secrets are not stored in this document or Git.

## Verified hosted flow — 4 October 2026

The protected API is deployed at `https://bedelau59--cottrell-analysis-api-hosted-api.modal.run`.
Unauthenticated and invalid-token requests were rejected. Two successive exploratory runs of the existing training-source field `b3esycq1` completed on `modal_l4_hosted`:

- `b4abb3d088b0436c8aa5273457707af6`: 148.7 seconds including first-worker startup.
- `056bbb1a67f54161bf06f676be08faaa`: 106.9 seconds on repeat use.

Both preserved the frozen refit check (maximum coefficient difference `9.71445146547012e-17`), served original previews and cropped images, and saved/read back a source-hash-bound skipped review separately from model output. These runs verify integration, not independent predictive accuracy. Their deployment source was `20216b3`; later wrapper changes retain the same scientific bundle.

Saved test-set original TIFFs are absent from this Mac's configured roots and are not baked into hosting. Their committed segmentation overlays now remain visible with explicit original-unavailable labels. Uploaded originals retain their image and 3D layer views. Saved TIFF lookup validates the recorded hash and tolerates duplicate discovery of the same file.

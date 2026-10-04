# Hosted Cottrell API

`modal_web.py` hosts the existing FastAPI API on Modal. It keeps the frozen
scientific source under `src/qc/` unchanged and supports only **exploratory**
uploads. The official held-out result remains a committed, read-only artifact.

The API uses two Modal Volumes:

- `cottrell-analysis-state` stores uploaded TIFFs, run state, exploratory
  result JSON, masks, overlays, review annotations, and hosted run accounting.
- `aixscience-weights` contains the checksum-verified
  `dinov2_vits14_pretrain.pth` used by the existing Modal workflow. If the
  Volume does not exist yet, the worker creates it and downloads only the
  public URL/digest pinned in `configs/v1.yaml`; it verifies the SHA-256 before
  using the file.

The web API does not bake original saved-result TIFFs into the image. Saved
numeric/model-card endpoints work from committed artifacts; a saved-image
preview returns `404` unless the corresponding original is supplied through an
exploratory upload. This is deliberate provenance and data-minimisation
behaviour.

## Deploy

Create an opaque, random server-to-server token. Do not put it in Git, a
frontend environment variable, browser storage, or a request URL. Create the
Modal Secret once:

```sh
modal secret create cottrell-api-token COTTRELL_API_TOKEN='replace-with-a-long-random-value'
```

Deploy the API from the repository root:

```sh
modal deploy modal_web.py
```

Modal prints the persistent `hosted_api` URL. Configure that exact HTTPS origin
as `COTTRELL_API_URL` in the ChatGPT Sites gateway, and configure the same
opaque value as `COTTRELL_API_TOKEN` in the gateway's server-side environment.
The gateway must forward it only as `X-Cottrell-Token`; browser requests must
continue to use the site's relative `/api/...` routes.

The API returns `401` unless `X-Cottrell-Token` matches the Modal Secret using
constant-time comparison. `/healthz` is the sole unauthenticated health route.

## Runtime behavior

`POST /api/uploads` and `/api/runs` retain their existing request/response
shape. Starting a run commits the upload to the state Volume and spawns a
separate, single-concurrency L4 worker. The worker uses the existing frozen
DINOv2 preprocessing/model functions directly on that L4; it does not nest a
second Modal App and it does not silently fall back to CPU. If CUDA or the
verified weights are unavailable, that exploratory run fails visibly.

The worker commits each visible stage and then its terminal files/state. The
web service serializes requests, reloads the Volume before every request, and
the GPU worker has one container. Uploads and review writes are rejected while
that worker is active, avoiding unsafe last-write-wins behavior on a shared
Volume. Cancellation is written as a separate durable control record before
Modal is asked to terminate the FunctionCall; the worker checks that record
before every state transition, so a late GPU completion cannot become accepted.
Before each worker refresh it commits masks, overlays and result files already
written by the frozen pipeline, preventing a Volume reload from discarding
those uncommitted artifacts.

The spawned Modal call ID is stored in a separate control file rather than the
worker-owned run state, so a fast-starting worker cannot have progress replaced
by the web request that launched it.

Each exploratory result uses the Git SHA baked into the deployment image. Its
hosted accounting row records only DINOv2 embedding wall time and its matching
L4 estimate; segmentation and file-processing wall time are not presented as
GPU cost.

## Before publishing

1. Confirm Modal authentication: `modal profile list`.
2. Confirm the weights volume contains the expected file and checksum (or
   allow the first worker to bootstrap it from the pinned public source).
3. Deploy, then call `GET <hosted_api_url>/healthz`.
4. Through the gateway, call `GET /api/capabilities` with the server-side
   header and verify the pinned bundle/refit gate reports ready.
5. Upload a disposable TIFF triplet, start one exploratory run, poll it to a
   terminal state, and inspect its recorded `embedding_backend` value:
   `modal_l4_hosted`.
6. Run a second disposable job in the same deployed service after the first
   completes. This verifies that a warm worker did not retain a previous job's
   progress wrappers or result state.

No deployment was performed merely by adding this adapter. The actual deployed
URL and a completed remote-GPU run must be recorded separately after deployment.

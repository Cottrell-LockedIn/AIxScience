# Cottrell local API

Start the saved-result service from the repository root:

```sh
.venv/bin/uvicorn app.api:app --host 127.0.0.1 --port 8502
```

It serves saved validation and held-out records at `GET /api/results`, and can
run a local exploratory analysis for validated TIFF uploads through `/api/runs`.
Each exploratory run is isolated under `.cottrell/`; it never overwrites the
canonical held-out evaluation. `GET /api/preview/...` and `GET /api/raw/...`
work only while the matching original TIFF is present on this machine.

`GET /api/capabilities` reports whether the local exploration bundle has passed
its artifact, configuration and model-refit checks. Its result is recorded as
exploration provenance, never as a claim that the original frozen environment
has been reproduced.

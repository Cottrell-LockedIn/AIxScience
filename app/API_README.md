# Cottrell local API

Start the saved-result service from the repository root:

```sh
.venv/bin/uvicorn app.api:app --host 127.0.0.1 --port 8502
```

It serves the committed `results/v1/heldout.json` record at `GET /api/results`.
It does not run a new scientific analysis. `POST /api/uploads` accepts TIFF files,
checks that they can be read, and only replays a saved result when an uploaded
file hash exactly matches a recorded held-out source file. `GET /api/preview/...`
and `GET /api/raw/...` work only while the matching original TIFF is present on
this machine; the response tells the UI when it is not.

The production inference bundle has not been proven in this local application,
so `GET /api/capabilities` reports `liveRunReady: false`.

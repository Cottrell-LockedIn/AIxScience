"""Hosted Cottrell API on Modal.

This is a deployment adapter.  It deliberately does not change ``src/qc`` or
the local FastAPI application.  The adapter mounts the committed inference
bundle, stores uploads/runs/reviews in a Modal Volume, and runs exploratory
jobs in a separate single-concurrency L4 function.

Deploy only after creating the ``cottrell-api-token`` Modal Secret described
in ``docs/HOSTED_BACKEND.md``.  The Sites gateway is the only intended caller;
the browser must never receive that token.
"""
from __future__ import annotations

import hmac
import os
import subprocess
from pathlib import Path
from typing import Any

import modal


APP_NAME = "cottrell-analysis-api"
STATE_VOLUME_NAME = "cottrell-analysis-state"
WEIGHTS_VOLUME_NAME = "aixscience-weights"
API_SECRET_NAME = "cottrell-api-token"
STATE_ROOT = "/mnt/cottrell-state"
WEIGHTS_ROOT = "/mnt/weights"
BUNDLE_ROOT = "/root/cottrell"

LOCAL_ROOT = Path(__file__).resolve().parent


def _bundle_git_sha() -> str:
    baked = os.environ.get("COTTRELL_BUNDLE_GIT_SHA")
    if baked:
        return baked
    if not modal.is_local():
        return "unknown"
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=LOCAL_ROOT, text=True
        ).strip()
    except Exception:  # deployment code must still load outside a checkout
        return "unknown"


BUNDLE_GIT_SHA = _bundle_git_sha()


def _tracked_bundle_files() -> set[Path]:
    """Return only committed files needed by the service image.

    ``results/`` is deliberately not copied wholesale: a developer can have
    ignored exploratory output or user TIFFs there.  Git's index is the
    deployable scientific-artifact allowlist.
    """
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "-z", "--", "src", "app", "configs", "results", "schema", "modal_app.py"],
            cwd=LOCAL_ROOT,
        )
    except Exception as exc:
        raise RuntimeError("Hosted deployment requires a Git checkout to build its artifact allowlist.") from exc
    return {Path(item.decode("utf-8")) for item in output.split(b"\0") if item}


# The remote container intentionally has no `.git` directory.  Enumerating
# files is a deploy-time operation only.
TRACKED_BUNDLE_FILES = _tracked_bundle_files() if modal.is_local() else set()


def _ignore_untracked_bundle_path(path: Path) -> bool:
    """Modal ``add_local_dir`` predicate: exclude untracked files and dirs."""
    try:
        relative = path.resolve().relative_to(LOCAL_ROOT.resolve())
    except ValueError:
        return True
    if relative == Path("."):
        return False
    # Keep a directory only when it contains a committed allowed descendant.
    return not any(item == relative or item.is_relative_to(relative) for item in TRACKED_BUNDLE_FILES)

# The scientific source and its committed artifacts are included in the image;
# raw TIFFs, local runs, credentials, and virtual environments are not.
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    # These are the exact numerical/image pins of the existing Modal encoder,
    # plus the wrapper's pinned local API dependencies.
    # The general requirements file permits a CPU torch wheel.  Pin the CUDA
    # build used by the existing Modal encoder after installing it.
    .pip_install(
        "numpy==2.4.6",
        "scipy==1.17.1",
        "scikit-image==0.26.0",
        "pandas==3.0.6",
        "pyarrow==25.0.1",
        "pillow==12.3.0",
        "matplotlib==3.11.2",
        "PyYAML==6.0.3",
        "scikit-learn==1.9.1",
        "opencv-python-headless==5.0.0.93",
        "tifffile==2026.9.20",
        "imagecodecs==2026.8.16",
        "jsonschema==4.26.0",
        "fastapi==0.142.2",
        "uvicorn==0.54.0",
        "python-multipart==0.0.32",
        "torch==2.14.1+cu130",
        "torchvision==0.29.1+cu130",
        extra_index_url="https://download.pytorch.org/whl/cu130",
    )
    .add_local_dir(
        LOCAL_ROOT,
        BUNDLE_ROOT,
        copy=True,
        ignore=_ignore_untracked_bundle_path,
    )
    .env(
        {
            "PYTHONPATH": f"{BUNDLE_ROOT}:{BUNDLE_ROOT}/src",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "COTTRELL_BUNDLE_GIT_SHA": BUNDLE_GIT_SHA,
        }
    )
)

app = modal.App(APP_NAME)
state_volume = modal.Volume.from_name(STATE_VOLUME_NAME, create_if_missing=True)
weights_volume = modal.Volume.from_name(WEIGHTS_VOLUME_NAME, create_if_missing=True)
api_secret = modal.Secret.from_name(API_SECRET_NAME, required_keys=["COTTRELL_API_TOKEN"])


def _state_paths() -> dict[str, Path]:
    root = Path(STATE_ROOT)
    return {
        "root": root,
        "uploads": root / "uploads",
        "runs": root / "runs",
        "controls": root / "controls",
        "calls": root / "calls",
        "reviews": root / "reviews.json",
        "modal_runs": root / "modal-runs.csv",
    }


def _configure_state_paths() -> tuple[Any, Any]:
    """Point the unmodified local wrapper modules at the mounted Volume."""
    import sys

    if BUNDLE_ROOT not in sys.path:
        sys.path.insert(0, BUNDLE_ROOT)
    src_root = f"{BUNDLE_ROOT}/src"
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    os.chdir(BUNDLE_ROOT)

    from app import api, jobs
    from qc import config as qc_config

    paths = _state_paths()
    paths["root"].mkdir(parents=True, exist_ok=True)
    jobs.STATE_ROOT = paths["root"]
    jobs.UPLOADS = paths["uploads"]
    jobs.RUNS = paths["runs"]
    api.REVIEWS_FILE = paths["reviews"]
    # ``api`` is imported before its paths are redirected, so reload only its
    # persisted annotation cache from the mounted Volume.
    api._REVIEWS = api._load_reviews()
    # Original source TIFFs are intentionally not baked into this public API.
    # Saved numerical records remain available, while image endpoints honestly
    # return 404 until their original TIFFs are uploaded in an exploratory run.
    api.POLARON_DATASET = paths["root"] / "no-saved-raw-tiffs"
    # The deployment image intentionally excludes .git. Preserve the commit
    # identity baked at deploy time for the engine's own provenance fields.
    qc_config.git_sha = lambda: os.environ.get("COTTRELL_BUNDLE_GIT_SHA", "unknown")
    return api, jobs


def _cancel_control_path(run_id: str) -> Path:
    return _state_paths()["controls"] / f"{run_id}.cancelled"


def _cancel_requested(run_id: str) -> bool:
    return _cancel_control_path(run_id).is_file()


def _persist_cancel_control(run_id: str) -> None:
    """Persist cancellation separately from mutable run state.

    The worker and web service live in different Modal containers.  Keeping the
    control record in a distinct file means a stale worker state snapshot cannot
    make a user cancellation disappear by writing its own ``state.json``.
    """
    path = _cancel_control_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text("cancelled\n", encoding="utf-8")
    os.replace(temporary, path)


def _call_control_path(run_id: str) -> Path:
    return _state_paths()["calls"] / f"{run_id}.call-id"


def _persist_call_control(run_id: str, call_id: str) -> None:
    """Store the Modal call ID apart from worker-owned ``state.json``."""
    path = _call_control_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(call_id + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _read_call_control(run_id: str) -> str | None:
    try:
        value = _call_control_path(run_id).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _is_pending_call_error(exc: BaseException) -> bool:
    """Modal 1.6 can surface a zero-timeout poll as either timeout class."""
    return isinstance(exc, (modal.exception.TimeoutError, TimeoutError))


def _append_hosted_modal_run(
    cfg: dict[str, Any],
    columns: list[str] | None,
    *,
    wall_s: float,
    n_inputs: int,
    hardware: str,
    cost: float,
    cost_source: str,
    exploratory: bool = False,
) -> None:
    """Keep hosted run accounting off immutable committed result artifacts."""
    import csv
    from datetime import datetime, timezone

    from qc import heldout

    fields = columns or heldout.V1_MODAL_RUN_COLUMNS
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "function": "dino_embed_heldout_exploratory" if exploratory else "dino_embed_heldout",
        "n_inputs": str(n_inputs),
        "wall_s": str(wall_s),
        "hardware": hardware,
        "git_sha": os.environ.get("COTTRELL_BUNDLE_GIT_SHA", BUNDLE_GIT_SHA),
        "config_hash": str(cfg["_hash"]),
        "est_cost_usd": str(cost),
        "cost_source": cost_source,
        "local_remote_max_abs_diff": "",
        "repeat_max_abs_diff": "",
    }
    path = _state_paths()["modal_runs"]
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        if write_header:
            writer.writeheader()
        writer.writerow({field: record.get(field, "") for field in fields})


def _hosted_gpu_embeddings(
    cfg: dict[str, Any],
    payloads: list[dict[str, Any]],
    allow_local_fallback: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the existing frozen DINOv2 operations on this job's L4 GPU.

    This has the same preprocessing and model loading functions as the existing
    Modal encoder, but avoids nesting a second Modal App from a Modal worker.
    There is intentionally no CPU fallback in the hosted path: a missing GPU or
    checksum-verified weight fails the exploratory job rather than changing the
    requested backend without making it visible.
    """
    import time

    import numpy as np
    import torch

    from qc import embed

    if not torch.cuda.is_available():
        raise RuntimeError("Hosted inference requires an L4 GPU, but CUDA is unavailable.")
    weights_cfg = cfg["embeddings"]
    weights_path = Path(WEIGHTS_ROOT) / embed.WEIGHT_FILENAME
    weights_volume.reload()
    if not weights_path.is_file():
        # The URL and digest are part of the committed frozen configuration.
        # Bootstrap only this verified public weight; never accept an arbitrary
        # upload into the model-weights Volume.
        embed.ensure_weights(weights_cfg, weights_path)
        weights_volume.commit()
    expected = str(weights_cfg["weights_sha256"]).lower()
    actual = embed._sha256(weights_path)
    if actual != expected:
        raise ValueError(f"DINOv2 weights SHA-256 mismatch: expected {expected}, got {actual}")

    torch.set_num_threads(1)
    model = embed.load_frozen_model(weights_cfg, weights_path, "cuda")
    started = time.perf_counter()
    vectors: dict[str, Any] = {}
    for payload in payloads:
        tiles = np.asarray(payload["tiles"])
        if tiles.dtype != np.uint8 or tiles.ndim != 3 or tiles.shape[1:] != (1024, 1024):
            raise ValueError("held-out DINOv2 tiles must be uint8 arrays shaped (n, 1024, 1024)")
        batches = [
            embed.embed_batch(model, list(tiles[start : start + 16]), int(weights_cfg["input_px"]), "cuda")
            for start in range(0, len(tiles), 16)
        ]
        vectors[str(payload["sample_id"])] = np.concatenate(batches, axis=0).astype(np.float32, copy=False)
    wall_s = time.perf_counter() - started
    # This is an estimate, matching the project's existing L4 accounting basis.
    estimated_cost = wall_s * 0.000222
    # The replacement intentionally bypasses heldout._embedding_vectors, which
    # normally writes this line. Preserve an embedding-only hosted run record;
    # do not charge the surrounding segmentation/job wall time as GPU time.
    from qc import heldout

    _append_hosted_modal_run(
        cfg,
        heldout.V1_MODAL_RUN_COLUMNS,
        wall_s=wall_s,
        n_inputs=len(payloads),
        hardware="L4",
        cost=estimated_cost,
        cost_source="https://modal.com/pricing; L4=$0.000222/GPU-s; embedding wall time only",
        exploratory=True,
    )
    return vectors, {
        "embedding_backend": "modal_l4_hosted",
        "embedding_error": None,
        "modal_wall_s": wall_s,
        "modal_container_s": wall_s,
        "modal_cost_usd": estimated_cost,
    }


def _install_hosted_inference_adapter() -> None:
    """Patch process-local extension points only; never modify ``src/qc``."""
    from qc import heldout

    heldout._embedding_vectors = _hosted_gpu_embeddings
    heldout._append_modal_run = _append_hosted_modal_run


@app.function(
    image=image,
    gpu="L4",
    cpu=4,
    memory=8192,
    timeout=60 * 60,
    max_containers=1,
    volumes={STATE_ROOT: state_volume, WEIGHTS_ROOT: weights_volume},
)
def run_exploratory(run_id: str) -> dict[str, str]:
    """Durably run one uploaded exploratory analysis and commit its artifacts."""
    state_volume.reload()
    _, jobs = _configure_state_paths()
    from qc import classify, heldout

    # app.worker.main intentionally wraps these extension points for progress
    # reporting, but does not restore them. A warm Modal container can process
    # another job, so preserve the pristine functions before any adapter/wrap.
    base_extract_features = heldout._extract_features
    base_embedding_vectors = heldout._embedding_vectors
    base_append_modal_run = heldout._append_modal_run
    base_predict_one = classify.predict_one
    _install_hosted_inference_adapter()
    from app import worker

    # A web request can cancel while the GPU is working.  Refresh the mounted
    # Volume before every state read/write so a stale worker cannot turn that
    # terminal cancellation back into a completed run.  Each stage update is
    # committed for honest polling progress instead of only at job completion.
    base_load_run = jobs.load_run
    base_update_run = jobs.update_run
    base_is_cancelled = jobs.is_cancelled

    def refresh_worker_state() -> None:
        # heldout.run writes masks, overlays and result JSON before its next
        # stage callback. Commit those files before reload, otherwise a Volume
        # refresh can discard the worker's own uncommitted artifacts.
        state_volume.commit()
        state_volume.reload()

    def worker_load_run(current_run_id: str):
        refresh_worker_state()
        return base_load_run(current_run_id)

    def worker_is_cancelled(current_run_id: str) -> bool:
        refresh_worker_state()
        return _cancel_requested(current_run_id) or base_is_cancelled(current_run_id)

    def worker_update_run(current_run_id: str, **changes: Any):
        refresh_worker_state()
        if _cancel_requested(current_run_id):
            # Ensure an old, pre-cancellation state snapshot cannot write a
            # completed/failed status after the user has cancelled.
            changes = {
                "state": "cancelled",
                "stage": "Cancelled",
                "error": "Cancelled by user.",
            }
        state = base_update_run(current_run_id, **changes)
        state_volume.commit()
        return state

    jobs.load_run = worker_load_run
    jobs.is_cancelled = worker_is_cancelled
    jobs.update_run = worker_update_run

    try:
        worker.main(run_id)
    finally:
        heldout._extract_features = base_extract_features
        heldout._embedding_vectors = base_embedding_vectors
        heldout._append_modal_run = base_append_modal_run
        classify.predict_one = base_predict_one
        # Restore job helpers too, so another warm invocation has a clean base.
        jobs.load_run = base_load_run
        jobs.is_cancelled = base_is_cancelled
        jobs.update_run = base_update_run
        # The input, state, result JSON, review artifacts, and hosted run log
        # only become visible to the web function after this explicit commit.
        state_volume.commit()
    state = jobs.load_run(run_id) or {}
    return {"id": run_id, "state": str(state.get("state", "unknown"))}


@app.function(
    image=image,
    cpu=2,
    memory=4096,
    timeout=10 * 60,
    max_containers=1,
    scaledown_window=300,
    secrets=[api_secret],
    volumes={STATE_ROOT: state_volume},
)
@modal.concurrent(max_inputs=1)
@modal.asgi_app()
def hosted_api():
    """Return the existing FastAPI surface, protected for the Sites gateway."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    state_volume.reload()
    api, jobs = _configure_state_paths()

    base_update_run = jobs.update_run

    def hosted_launch(run_id: str) -> dict[str, Any]:
        # The worker container must see the uploaded TIFF and queued state.
        state_volume.commit()
        call = run_exploratory.spawn(run_id)
        # The L4 worker may begin and commit a progress state before this web
        # handler resumes. Keep the call ID in its own control file instead of
        # writing a stale queued ``state.json`` over worker progress.
        _persist_call_control(run_id, str(call.object_id))
        state_volume.commit()
        return jobs.load_run(run_id) or {"id": run_id, "state": "queued", "stage": "Queued"}

    def hosted_reconcile(run_id: str) -> dict[str, Any] | None:
        state = jobs.load_run(run_id)
        if _cancel_requested(run_id):
            if state is not None and state.get("state") != "cancelled":
                state = base_update_run(
                    run_id,
                    state="cancelled",
                    stage="Cancelled",
                    error="Cancelled by user.",
                )
                state_volume.commit()
            return state
        if state is None or state.get("state") in jobs.TERMINAL:
            return state
        call_id = _read_call_control(run_id) or state.get("modalCallId")
        if not isinstance(call_id, str) or not call_id:
            return base_update_run(
                run_id,
                state="failed",
                stage="Failed",
                error="Hosted worker call was not recorded.",
            )
        try:
            # A zero-timeout get is a non-blocking worker health poll.  The
            # worker itself normally records success/failure before returning.
            modal.FunctionCall.from_id(call_id).get(timeout=0)
        except Exception as exc:
            if _is_pending_call_error(exc):
                return state
            failed = base_update_run(
                run_id,
                state="failed",
                stage="Failed",
                error=f"Hosted worker ended before a terminal state: {type(exc).__name__}: {exc}"[:1200],
            )
            state_volume.commit()
            return failed
        # The worker can finish and commit in the small window between the
        # zero-timeout result and this request. Refresh before failing it.
        state_volume.reload()
        refreshed = jobs.load_run(run_id)
        if refreshed is not None and refreshed.get("state") in jobs.TERMINAL:
            return refreshed
        failed = base_update_run(
            run_id,
            state="failed",
            stage="Failed",
            error="Hosted worker returned without recording a terminal state.",
        )
        state_volume.commit()
        return failed

    def hosted_cancel(run_id: str) -> dict[str, Any]:
        state = jobs.load_run(run_id)
        if state is None:
            raise FileNotFoundError(run_id)
        if state.get("state") not in jobs.TERMINAL:
            # Persist cancellation before requesting Modal termination.  If
            # cancellation races a finished GPU batch, the terminal guard in
            # jobs.update_run keeps this state authoritative.
            _persist_cancel_control(run_id)
            state_volume.commit()
            state = base_update_run(run_id, state="cancelled", stage="Cancelled", error="Cancelled by user.")
            state_volume.commit()
            call_id = _read_call_control(run_id) or state.get("modalCallId")
            if isinstance(call_id, str) and call_id:
                try:
                    modal.FunctionCall.from_id(call_id).cancel(terminate_containers=True)
                except Exception:
                    # The persisted cancellation is still valid if the call
                    # has already ended or Modal has accepted cancellation.
                    pass
        return state

    jobs.launch = hosted_launch
    jobs.reconcile = hosted_reconcile
    jobs.cancel = hosted_cancel

    @api.app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @api.app.middleware("http")
    async def hosted_authorization(request: Request, call_next):
        # This header is added by the Sites Worker; it is never a browser token.
        if request.url.path != "/healthz":
            expected = os.environ.get("COTTRELL_API_TOKEN", "")
            supplied = request.headers.get("x-cottrell-token", "")
            if not expected or not hmac.compare_digest(supplied, expected):
                return JSONResponse({"detail": "Unauthorized."}, status_code=401)
        # The worker uses another container and explicitly commits each stage;
        # reload before every serial web request to make polling truthful.
        state_volume.reload()
        mutable_shared_paths = (
            request.url.path.startswith("/api/uploads")
            or request.url.path.startswith("/api/reviews")
        )
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and mutable_shared_paths and jobs.active_run_exists():
            return JSONResponse(
                {"detail": "An exploratory analysis is running. Wait for it to finish before changing shared uploads or reviews."},
                status_code=409,
            )
        response = await call_next(request)
        # Uploads and reviews are the only web-side durable writes.  A run's
        # larger result set is committed by ``run_exploratory`` when complete.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path != "/api/runs":
            state_volume.commit()
        return response

    return api.app

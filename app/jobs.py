"""Small, local, persistent job registry for exploratory Cottrell runs."""
from __future__ import annotations

import json
import os
import hashlib
import importlib.metadata
import signal
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
import fcntl
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_ROOT = ROOT / ".cottrell"
UPLOADS = STATE_ROOT / "uploads"
RUNS = STATE_ROOT / "runs"
TERMINAL = {"completed", "failed", "cancelled"}


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(temp, path)


@contextmanager
def _locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def upload_path(upload_id: str) -> Path:
    return UPLOADS / upload_id


def run_path(run_id: str) -> Path:
    return RUNS / run_id


def run_state_path(run_id: str) -> Path:
    return run_path(run_id) / "state.json"


def load_run(run_id: str) -> dict[str, Any] | None:
    path = run_state_path(run_id)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_run(run_id: str, state: dict[str, Any]) -> None:
    with _locked(run_state_path(run_id).with_suffix(".lock")):
        _write(run_state_path(run_id), state)


def update_run(run_id: str, **changes: Any) -> dict[str, Any]:
    path = run_state_path(run_id)
    with _locked(path.with_suffix(".lock")):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FileNotFoundError(run_id) from exc
        # A cancellation/completion always wins a late worker-stage callback.
        if state.get("state") in TERMINAL and changes.get("state") not in {state.get("state"), None}:
            return state
        if state.get("state") in TERMINAL and changes.get("stage"):
            return state
        state.update(changes)
        state["updatedAt"] = time.time()
        _write(path, state)
        return state


def is_cancelled(run_id: str) -> bool:
    return (load_run(run_id) or {}).get("state") == "cancelled"


def _pid_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid < 2:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def reconcile(run_id: str) -> dict[str, Any] | None:
    state = load_run(run_id)
    if state is None or state.get("state") in TERMINAL:
        return state
    if state.get("state") == "queued" and not state.get("pid"):
        return state
    if not _pid_alive(state.get("pid")):
        return update_run(run_id, state="failed", stage="Failed", error="The local analysis worker stopped before producing a terminal result.")
    return state


def active_run_exists() -> bool:
    if not RUNS.is_dir():
        return False
    return any((reconcile(path.name) or {}).get("state") in {"queued", "running", "cancelling"} for path in RUNS.iterdir() if path.is_dir())


def create_run(upload_id: str, criteria: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    now = time.time()
    state = {
        "id": run_id,
        "uploadId": upload_id,
        "state": "queued",
        "stage": "Checking files",
        "criteria": criteria,
        "metadata": metadata,
        "createdAt": now,
        "updatedAt": now,
        "exploratory": True,
    }
    save_run(run_id, state)
    return state


def launch(run_id: str) -> dict[str, Any]:
    log = run_path(run_id) / "worker.log"
    with log.open("ab") as stream:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.worker", run_id], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return update_run(run_id, pid=process.pid)


def cancel(run_id: str) -> dict[str, Any]:
    state = load_run(run_id)
    if state is None:
        raise FileNotFoundError(run_id)
    if state.get("state") in TERMINAL:
        return state
    # Persist terminal cancellation first, then signal. A worker can no longer
    # overwrite this state after either the signal or a late callback.
    state = update_run(run_id, state="cancelled", stage="Cancelled", error="Cancelled by user.")
    pid = state.get("pid")
    if isinstance(pid, int):
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    return state


def exploration_bundle() -> dict[str, Any]:
    """Fingerprint the actual local exploration inputs, never a frozen claim."""
    files = [
        *sorted((ROOT / "src" / "qc").glob("*.py")), ROOT / "configs" / "v1.yaml",
        ROOT / "configs" / "features_v1.yaml", ROOT / "results" / "features_per_image.parquet",
        ROOT / "results" / "emb_per_image.parquet", ROOT / "results" / "artefacts_per_image.parquet",
        ROOT / "results" / "v1" / "final_model.csv", ROOT / "results" / "v1" / "heldout.json",
        ROOT / "schema" / "verdict.schema.json",
    ]
    digest = hashlib.sha256()
    missing = []
    for path in files:
        if not path.is_file():
            missing.append(str(path.relative_to(ROOT)))
            continue
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    fingerprint = digest.hexdigest()
    cache = STATE_ROOT / "bundle-verifications" / f"{fingerprint}.json"
    if cache.is_file():
        try:
            cached = json.loads(cache.read_text())
            if cached.get("missing") == missing:
                return cached
        except (OSError, json.JSONDecodeError):
            pass
    config_hash = hashlib.sha256((ROOT / "configs" / "v1.yaml").read_bytes()).hexdigest()[:12] if not missing else None
    canonical = json.loads((ROOT / "results" / "v1" / "heldout.json").read_text()) if not missing else {}
    refit_error: str | None = None
    refit_diff: float | None = None
    try:
        from qc import classify
        model = classify.final_model(classify.load_training())
        refit_diff = float(classify.check_frozen_model(model))
    except Exception as exc:  # a missing local dependency blocks dispatch
        refit_error = f"{type(exc).__name__}: {exc}"
    versions = {}
    for package in ("numpy", "pandas", "scikit-learn", "torch", "modal", "tifffile"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not installed"
    verified = not missing and canonical.get("run", {}).get("config_hash") == config_hash and refit_error is None and refit_diff is not None and refit_diff <= 1e-9
    record = {"kind": "verified exploration bundle", "fingerprint": fingerprint, "verified": verified, "missing": missing, "canonicalConfigHash": canonical.get("run", {}).get("config_hash"), "currentConfigHash": config_hash, "refitMaxAbsCoefficientDiff": refit_diff, "refitError": refit_error, "packageVersions": versions}
    _write(cache, record)
    return record

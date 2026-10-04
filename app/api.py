"""Read-only local API for the saved Cottrell evaluation.

This service intentionally does not run the scientific pipeline.  It exposes the
committed ``results/v1/heldout.json`` artifact and lets the UI replay a result
only when uploaded source bytes match a recorded hash.

Run from the repository root:
    .venv/bin/uvicorn app.api:app --host 127.0.0.1 --port 8502
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import tifffile
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HELDOUT = ROOT / "results" / "v1" / "heldout.json"
VALIDATION_DIR = ROOT / "results" / "v1" / "loio_images"
VALIDATION_FEATURES = ROOT / "results" / "features_per_image.parquet"
POLARON_DATASET = Path("/Users/bedelau/Documents/Codex/2026-10-03/i/outputs/polaron_dataset")
REVIEWS_FILE = ROOT / ".cottrell" / "reviews.json"
MAX_UPLOAD_BYTES = 128 * 1024 * 1024
MAX_DECODED_PIXELS = 25_000_000
MIN_TILER_DIMENSION = 1040  # 1024px tile plus the frozen reader's 8px crop.
MAX_PREVIEW_EDGE = 1600
CHANNELS = ("BSE", "ETD", "Inlens", "SE")
FEATURE_KEYS = {
    "F01": "F01_c0_area_fraction",
    "F02": "F02_c2_area_fraction",
    "F03": "F03_c2_eqdiam_median_px",
    "F04": "F04_c2_eqdiam_p90_px",
    "F05": "F05_c2_count_density_per_Mpx",
    "F06": "F06_c2_clark_evans_R",
    "F07": "F07_c2_solidity_area_weighted_median",
    "F08": "F08_c0_local_thickness_median_px",
    "F09": "F09_c0_chord_anisotropy_h_over_v",
    "F10": "F10_c0_fraction_iqr_512px",
    "F11": "F11_c2_perimeter_fraction_adjacent_c0",
}

app = FastAPI(title="Cottrell saved-result API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8501", "http://localhost:8501", "http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _sha256(data: bytes | Path) -> str:
    digest = hashlib.sha256()
    if isinstance(data, Path):
        with data.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    else:
        digest.update(data)
    return digest.hexdigest()


def _finite(value: Any) -> float | None:
    if isinstance(value, (int, float)) and np.isfinite(value):
        return float(value)
    return None


@lru_cache(maxsize=1)
def _saved() -> dict[str, Any]:
    if not HELDOUT.is_file():
        raise HTTPException(503, "Saved held-out evaluation is not available.")
    return json.loads(HELDOUT.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _recorded_files() -> dict[str, tuple[str, str]]:
    """Map source hash to (field id, channel), from the immutable saved run."""
    entries: dict[str, tuple[str, str]] = {}
    for original_path, digest in _saved()["run"].get("file_hashes", {}).items():
        match = re.search(r"img_([^_]+)_([A-Za-z0-9]+)\.tiff?$", original_path, re.I)
        if match:
            entries[digest] = (match.group(1), match.group(2))
    return entries


def _source_roots() -> list[Path]:
    candidates = [
        ROOT / "data",
        ROOT / "handoff",
        POLARON_DATASET,
        Path("/Users/bedelau/Documents/ChatGPT/Cottrell/handoff"),
        Path("/Users/bedelau/Documents/ChatGPT/Cottrell/research"),
        Path("/Users/bedelau/Documents/Codex/2026-10-03/i/outputs"),
    ]
    return [path for path in candidates if path.is_dir()]


@lru_cache(maxsize=64)
def _find_source(field_id: str, channel: str) -> Path | None:
    # File names are independently checked against the recorded source hash before use.
    pattern = re.compile(rf"(?:img_)?{re.escape(field_id)}_{re.escape(channel)}\.tiff?$", re.I)
    expected = {
        digest for digest, pair in _recorded_files().items()
        if pair == (field_id, channel)
    }
    for root in _source_roots():
        for suffix in ("*.tif", "*.tiff", "*.TIF", "*.TIFF"):
            for candidate in root.rglob(suffix):
                if pattern.fullmatch(candidate.name):
                    # Validation records identify their original by field/channel.
                    # Held-out records additionally require an exact recorded hash.
                    if not expected or _sha256(candidate) in expected:
                        return candidate
    return None


def _file_channel(field_id: str, channel: str) -> dict[str, Any]:
    source = _find_source(field_id, channel)
    expected = next(
        (digest for digest, pair in _recorded_files().items() if pair == (field_id, channel)),
        None,
    )
    result: dict[str, Any] = {
        "name": channel,
        "filename": f"img_{field_id}_{channel}.tif",
        "sha256": expected,
        "previewUrl": f"/api/preview/{field_id}/{channel}",
        "rawUrl": f"/api/raw/{field_id}/{channel}",
        "available": source is not None,
    }
    if source is not None:
        if expected is None:
            expected = _sha256(source)
            result["sha256"] = expected
        with tifffile.TiffFile(source) as image:
            result.update(width=int(image.pages[0].imagewidth), height=int(image.pages[0].imagelength))
    else:
        result.update(width=None, height=None)
    return result


def _plain_driver(driver: Any) -> dict[str, Any]:
    if not isinstance(driver, dict):
        return {"name": str(driver), "explanation": "Recorded evidence driver."}
    value = _finite(driver.get("value"))
    tag = driver.get("tag")
    direction = driver.get("direction")
    explanation = driver.get("explanation") or driver.get("reason")
    if not explanation:
        explanation = "This recorded model input supported the displayed batch match."
        if direction:
            explanation += f" Its recorded direction was {direction}."
        if tag:
            explanation += f" Evidence status: {tag}."
    return {
        "name": driver.get("name") or driver.get("feature") or "Recorded driver",
        "value": value,
        "explanation": explanation,
    }


def _normalise(image: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    subject = image["subject"]
    closed = image["verdict"]["closed_set"]
    numbers = closed.get("justification", {}).get("numbers", {})
    acquisition = image.get("acquisition", {})
    flagged = [name for name, item in acquisition.get("covariates", {}).items() if item.get("flag")]
    ood_label = image["verdict"].get("label", "unknown")
    baseline_reason = image["verdict"].get("reason", "Saved evaluation result.")
    features = {short: _finite(raw_inputs.get(full)) for short, full in FEATURE_KEYS.items()}
    channels = [_file_channel(subject["id"], channel) for channel in acquisition.get("detectors_present", [])]
    reliability = numbers.get("loio_reliability", {})
    drivers = [_plain_driver(value) for value in image.get("evidence", {}).get("drivers", [])]
    return {
        "id": subject["id"],
        "channels": channels,
        "features": features,
        "predictedBatch": closed.get("predicted_batch"),
        "probabilities": closed.get("probabilities", {}),
        "runnerUp": closed.get("runner_up"),
        "margin": _finite(closed.get("margin")),
        "confidenceTier": closed.get("tier"),
        "baseline": {"status": ood_label, "reason": baseline_reason},
        "acquisition": {
            "status": "check_needed" if flagged or acquisition.get("acquisition_drift_suspected") else "no_flag_recorded",
            "reason": "Outside reference range: " + ", ".join(flagged) if flagged else "No acquisition covariate was flagged in the saved result.",
        },
        "reliability": {"correct": reliability.get("pred_batch_correct"), "total": reliability.get("pred_batch_n")},
        "drivers": drivers,
        "caveats": image.get("caveats", []),
        "route": image.get("routing", {}).get("stakeholder", "Review owner not recorded"),
        "phaseIdentity": "stated by Polaron, not image-verified",
        "raw": image,
    }


@lru_cache(maxsize=1)
def _validation_records() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Three real LOIO records with their original local TIFF counterparts."""
    selected = ("b3esycq1", "fzrt2k6r", "71vgq3fw")
    table = pq.read_table(VALIDATION_FEATURES).to_pylist()
    features = {row["sample_id"]: row for row in table}
    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for field_id in selected:
        source = VALIDATION_DIR / f"{field_id}.json"
        if not source.is_file() or field_id not in features:
            continue
        records.append((json.loads(source.read_text(encoding="utf-8")), features[field_id]))
    return records


@app.get("/api/capabilities")
def capabilities() -> dict[str, Any]:
    return {
        "savedResultsReady": HELDOUT.is_file(),
        "liveRunReady": False,
        "uploadReplayReady": True,
        "reviewPersistenceReady": True,
        "reason": "This local build exposes saved evaluation results. A production inference bundle has not been installed or verified.",
        "acceptedTypes": [".tif", ".tiff"],
        "maxUploadBytes": MAX_UPLOAD_BYTES,
    }


@app.get("/api/results")
def results(dataset: str = "validation") -> dict[str, Any]:
    if dataset == "validation":
        records = _validation_records()
        return {
            "mode": "Saved validation",
            "run": {
                "source": "results/v1/loio_images/*.json",
                "kind": "leave-one-image-out saved predictions",
                "n_fields": len(records),
            },
            "fields": [_normalise(item, inputs) for item, inputs in records],
            "limitations": [
                "These are saved validation predictions for known training images, not a new batch inference.",
                "Batch-match probabilities are not defect probabilities.",
                "Phase identity: stated by Polaron, not image-verified.",
            ],
        }
    if dataset != "heldout":
        raise HTTPException(422, "dataset must be 'validation' or 'heldout'.")
    saved = _saved()
    return {
        "mode": "Saved evaluation",
        "run": saved["run"],
        "fields": [_normalise(item, saved["inputs"].get(item["subject"]["id"], {})) for item in saved["images"]],
        "limitations": [
            "Batch-match probabilities are not defect probabilities.",
            "This endpoint replays a saved evaluation; it does not perform new inference.",
            "Phase identity: stated by Polaron, not image-verified.",
        ],
    }


def _source_or_404(field_id: str, channel: str) -> Path:
    if channel not in CHANNELS or not re.fullmatch(r"[A-Za-z0-9-]+", field_id):
        raise HTTPException(404, "Unknown field or detector channel.")
    source = _find_source(field_id, channel)
    if source is None:
        raise HTTPException(404, "The recorded original TIFF is not present on this machine.")
    return source


@app.get("/api/raw/{field_id}/{channel}")
def raw(field_id: str, channel: str) -> FileResponse:
    source = _source_or_404(field_id, channel)
    return FileResponse(source, media_type="image/tiff", filename=source.name)


@app.get("/api/raw")
def raw_records(dataset: str = "validation") -> dict[str, Any]:
    """Download the exact saved JSON records behind the current result view."""
    if dataset == "validation":
        return {"mode": "Saved validation", "records": [record for record, _ in _validation_records()]}
    if dataset == "heldout":
        return {"mode": "Saved evaluation", "records": _saved()["images"], "run": _saved()["run"]}
    raise HTTPException(422, "dataset must be 'validation' or 'heldout'.")


@app.get("/api/preview/{field_id}/{channel}")
def preview(field_id: str, channel: str) -> Response:
    source = _source_or_404(field_id, channel)
    array = tifffile.imread(source, key=0)
    if array.ndim > 2 and array.shape[-1] not in (3, 4):
        array = array[0]
    if array.ndim not in (2, 3):
        raise HTTPException(422, "Unsupported TIFF layout for preview.")
    if array.dtype != np.uint8:
        low, high = np.percentile(array.astype(np.float64), (1, 99))
        if high <= low:
            high = low + 1
        array = np.clip((array - low) * 255 / (high - low), 0, 255).astype(np.uint8)
    image = Image.fromarray(array)
    image.thumbnail((MAX_PREVIEW_EDGE, MAX_PREVIEW_EDGE), Image.Resampling.LANCZOS)
    encoded = io.BytesIO()
    image.save(encoded, format="PNG", optimize=True)
    return Response(encoded.getvalue(), media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


def _field_channel_from_name(filename: str) -> tuple[str, str] | None:
    match = re.search(r"(?:img_)?([^_]+)_([A-Za-z0-9]+)\.tiff?$", filename, re.I)
    return (match.group(1), match.group(2)) if match else None


@app.post("/api/uploads")
async def uploads(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    received: list[dict[str, Any]] = []
    matches: dict[str, set[str]] = {}
    grouped: dict[str, set[str]] = {}
    for upload in files:
        filename = Path(upload.filename or "upload.tif").name
        if Path(filename).suffix.lower() not in {".tif", ".tiff"}:
            raise HTTPException(422, f"{filename}: only TIFF files are accepted.")
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{filename}: exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB limit.")
        try:
            with tifffile.TiffFile(io.BytesIO(data)) as tif:
                if len(tif.pages) != 1:
                    raise HTTPException(422, f"{filename}: exactly one TIFF frame is required.")
                page = tif.pages[0]
                shape, dtype = list(page.shape), str(page.dtype)
                width, height = int(page.imagewidth), int(page.imagelength)
                if width * height > MAX_DECODED_PIXELS:
                    raise HTTPException(422, f"{filename}: decoded image exceeds the {MAX_DECODED_PIXELS:,}-pixel limit.")
                if width < MIN_TILER_DIMENSION or height < MIN_TILER_DIMENSION:
                    raise HTTPException(422, f"{filename}: both dimensions must be at least {MIN_TILER_DIMENSION}px for the frozen tiler.")
                if page.dtype != np.uint8:
                    raise HTTPException(422, f"{filename}: only uint8 TIFF data is supported by the frozen reader.")
                if len(shape) == 2:
                    layout = "grayscale"
                elif len(shape) == 3 and shape[-1] == 3:
                    pixels = tif.asarray(key=0)
                    if not (np.array_equal(pixels[..., 0], pixels[..., 1]) and np.array_equal(pixels[..., 0], pixels[..., 2])):
                        raise HTTPException(422, f"{filename}: RGB TIFF channels must be identical grayscale values.")
                    layout = "RGB-identical-grayscale"
                else:
                    raise HTTPException(422, f"{filename}: use a 2D grayscale TIFF or RGB TIFF with identical channels; RGBA and other layouts are unsupported.")
        except (tifffile.TiffFileError, ValueError, OSError) as exc:
            raise HTTPException(422, f"{filename}: invalid or unreadable TIFF ({exc}).") from exc
        digest = _sha256(data)
        parsed = _field_channel_from_name(filename)
        if parsed is None:
            raise HTTPException(422, f"{filename}: name it img_<field-id>_<BSE|ETD|Inlens|SE>.tif so it can be grouped safely.")
        field_id, channel = parsed
        if channel not in CHANNELS:
            raise HTTPException(422, f"{filename}: unsupported detector channel '{channel}'.")
        if channel in grouped.setdefault(field_id, set()):
            raise HTTPException(422, f"{filename}: duplicate {channel} file for field {field_id}.")
        grouped[field_id].add(channel)
        replay = _recorded_files().get(digest)
        if replay:
            matches.setdefault(replay[0], set()).add(replay[1])
        received.append({"filename": filename, "sha256": digest, "bytes": len(data), "shape": shape, "dtype": dtype, "layout": layout, "recordedSource": replay is not None})
    missing_bse = [field_id for field_id, channels in grouped.items() if "BSE" not in channels]
    if missing_bse:
        raise HTTPException(422, "Each field needs one BSE TIFF. Missing BSE for: " + ", ".join(sorted(missing_bse)))
    saved = _saved()
    replay_fields = [
        _normalise(item, saved["inputs"].get(field_id, {}))
        for item in saved["images"]
        if (field_id := item["subject"]["id"]) in matches and "BSE" in matches[field_id]
    ]
    return {
        "mode": "Saved evaluation replay" if replay_fields else "Upload validated; live analysis unavailable",
        "uploads": received,
        "fields": replay_fields,
        "liveRunReady": False,
        "reason": "Exact recorded source hashes matched a saved result." if replay_fields else "Files were validated, but this build has no verified production inference bundle.",
    }


def _load_reviews() -> dict[str, list[dict[str, Any]]]:
    if not REVIEWS_FILE.is_file():
        return {}
    try:
        data = json.loads(REVIEWS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


_REVIEWS: dict[str, list[dict[str, Any]]] = _load_reviews()


def _save_reviews() -> None:
    REVIEWS_FILE.parent.mkdir(mode=0o700, exist_ok=True)
    temp = REVIEWS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(_REVIEWS, indent=2), encoding="utf-8")
    os.replace(temp, REVIEWS_FILE)


def _known_field(field_id: str) -> bool:
    return field_id in {item["subject"]["id"] for item in _saved()["images"]} or field_id in {
        item[0]["subject"]["id"] for item in _validation_records()
    }


def _store_review(field_id: str, review: dict[str, Any]) -> dict[str, Any]:
    if not _known_field(field_id):
        raise HTTPException(404, "Unknown saved-result field.")
    safe = {key: review.get(key) for key in ("tag", "note", "channel", "roi", "reviewer", "time", "timestamp", "taskVersion")}
    safe["fieldId"] = field_id
    _REVIEWS.setdefault(field_id, []).append(safe)
    _save_reviews()
    return {"saved": True, "review": safe, "note": "Review annotations do not change saved probabilities or measurements."}


@app.post("/api/reviews/{field_id}")
async def save_review(field_id: str, review: dict[str, Any]) -> dict[str, Any]:
    return _store_review(field_id, review)


@app.post("/api/reviews")
async def save_review_alias(review: dict[str, Any]) -> dict[str, Any]:
    field_id = review.get("fieldId") or review.get("field_id")
    if not isinstance(field_id, str):
        raise HTTPException(422, "fieldId is required.")
    return _store_review(field_id, review)

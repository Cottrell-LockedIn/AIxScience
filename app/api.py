"""Local API for exploratory Cottrell runs and immutable saved evidence.

Original TIFF uploads run the fixed scientific pipeline in isolated exploratory
workers. Saved validation/model-card endpoints only read committed artifacts.
Run: .venv/bin/uvicorn app.api:app --host 127.0.0.1 --port 8502
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time
import uuid
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

from app import jobs
from app.model_accuracy import router as model_accuracy_router

ROOT = Path(__file__).resolve().parents[1]
HELDOUT = ROOT / "results" / "v1" / "heldout.json"
EXPLORATORY_HELDOUT = ROOT / "results" / "v1_1" / "heldout_exploratory.json"
TEST_SET = ROOT / "results" / "v1_1" / "heldout_test_exploratory.json"
PC_TAGS = ROOT / "results" / "v1" / "pc_tags.json"
SAVED_MASKS = ROOT / "results" / "v1_1" / "masks"
VALIDATION_DIR = ROOT / "results" / "v1" / "loio_images"
VALIDATION_FEATURES = ROOT / "results" / "features_per_image.parquet"
POLARON_DATASET = Path("/Users/bedelau/Documents/Codex/2026-10-03/i/outputs/polaron_dataset")
REVIEWS_FILE = ROOT / ".cottrell" / "reviews.json"
MAX_UPLOAD_BYTES = 128 * 1024 * 1024
MAX_DECODED_PIXELS = 25_000_000
MIN_TILER_DIMENSION = 1040  # 1024px tile plus the frozen reader's 8px crop.
MAX_PREVIEW_EDGE = 1600
MAX_CROP_EDGE = 1024
CHANNELS = ("BSE", "ETD", "Inlens", "SE")
ID_RE = re.compile(r"[a-f0-9]{32}")
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

app = FastAPI(title="Cottrell analysis API", version="0.2.0")
app.include_router(model_accuracy_router)
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


def _id_or_422(value: str, label: str) -> str:
    if not ID_RE.fullmatch(value):
        raise HTTPException(422, f"Invalid {label}.")
    return value


@lru_cache(maxsize=1)
def _saved() -> dict[str, Any]:
    if not HELDOUT.is_file():
        raise HTTPException(503, "Saved held-out evaluation is not available.")
    return json.loads(HELDOUT.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _recorded_files() -> dict[str, tuple[str, str]]:
    """Map source hash to (field id, channel), from immutable saved runs."""
    entries: dict[str, tuple[str, str]] = {}
    for saved_path in (HELDOUT, TEST_SET):
        if not saved_path.is_file():
            continue
        saved = json.loads(saved_path.read_text(encoding="utf-8"))
        for original_path, digest in saved.get("run", {}).get("file_hashes", {}).items():
            match = re.search(r"img_([^_]+)_([A-Za-z0-9]+)\.tiff?$", original_path, re.I)
            if match:
                pair = (match.group(1), match.group(2))
                previous = entries.setdefault(digest, pair)
                if previous != pair:
                    raise RuntimeError(f"Recorded source hash maps to multiple fields: {digest}")
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
    validation_ids = {record[0]["subject"]["id"] for record in _validation_records()} if VALIDATION_DIR.is_dir() else set()
    # Validation displays only come from this explicitly selected local dataset
    # root; never from an arbitrary matching TIFF elsewhere on disk.
    roots = [POLARON_DATASET] if field_id in validation_ids else _source_roots()
    found: dict[Path, str] = {}
    for root in roots:
        for suffix in ("*.tif", "*.tiff", "*.TIF", "*.TIFF"):
            for candidate in root.rglob(suffix):
                if pattern.fullmatch(candidate.name):
                    # Validation records identify their original by field/channel.
                    # Held-out records additionally require an exact recorded hash.
                    digest = _sha256(candidate)
                    if not expected or digest in expected:
                        # POLARON_DATASET is itself below one configured parent root.
                        # Resolve before counting so that one local TIFF is never treated
                        # as an ambiguous pair merely because both roots discover it.
                        found[candidate.resolve()] = digest
    if len(found) == 1:
        return next(iter(found))
    # Separate paths are acceptable only when they are byte-identical to the one
    # recorded source. Prefer the stable lexical path; a different image can never
    # pass this branch because every candidate was hash-verified above.
    if found and len(set(found.values())) == 1 and next(iter(found.values())) in expected:
        return sorted(found, key=str)[0]
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
    image = _with_pc_sentences(image)
    return {
        "id": subject["id"],
        "mask": _saved_mask(subject["id"], _saved_segmentation_evidence(image)),
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
def _pc_sentences() -> dict[str, str]:
    """Committed Phase B PC profile sentences (results/v1/pc_tags.json), read-only."""
    if not PC_TAGS.is_file():
        return {}
    pcs = json.loads(PC_TAGS.read_text(encoding="utf-8")).get("pcs", {})
    return {name: item["sentence"] for name, item in pcs.items() if isinstance(item, dict) and item.get("sentence")}


def _with_pc_sentences(image: dict[str, Any]) -> dict[str, Any]:
    sentences = _pc_sentences()
    drivers = image.get("evidence", {}).get("drivers")
    if not sentences or not drivers:
        return image
    enriched = [
        {**driver, "pc_sentence": sentences[driver["name"]]} if driver.get("name") in sentences and "pc_sentence" not in driver else driver
        for driver in drivers
    ]
    return {**image, "evidence": {**image["evidence"], "drivers": enriched}}


def _saved_mask_file(field_id: str, kind: str) -> Path | None:
    if kind not in ("mask", "overlay") or not re.fullmatch(r"[A-Za-z0-9-]+", field_id):
        return None
    path = SAVED_MASKS / f"{field_id}_{kind}.png"
    return path if path.is_file() else None


def _field_segmentation(saved_path: Path, field_id: str) -> dict[str, Any] | None:
    """Return one committed segmentation record, without changing model outputs."""
    if not saved_path.is_file():
        return None
    try:
        for item in json.loads(saved_path.read_text(encoding="utf-8")).get("images", []):
            if item.get("subject", {}).get("id") == field_id:
                evidence = item.get("evidence", {}).get("segmentation_mask")
                return evidence if isinstance(evidence, dict) else None
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        return None
    return None


def _same_recorded_sources(official: dict[str, Any], replay: dict[str, Any]) -> bool:
    """Only bind a later saved artifact when every recorded TIFF hash is identical."""
    official_hashes = official.get("subject", {}).get("file_hashes")
    replay_hashes = replay.get("subject", {}).get("file_hashes")
    return (
        isinstance(official_hashes, dict)
        and bool(official_hashes)
        and official_hashes == replay_hashes
    )


def _saved_segmentation_evidence(image: dict[str, Any]) -> dict[str, Any] | None:
    """Find display artifacts while keeping the official prediction record immutable.

    The frozen official held-out JSON predates saved masks.  Its exact TIFF hashes
    match a separately committed exploratory replay, so that replay's mask may be
    displayed only with explicit provenance.  The prediction, measurements and
    confidence remain those from the official document passed to this function.
    """
    direct = image.get("evidence", {}).get("segmentation_mask")
    if isinstance(direct, dict):
        return direct
    field_id = image.get("subject", {}).get("id")
    if not isinstance(field_id, str) or not EXPLORATORY_HELDOUT.is_file():
        return None
    try:
        replay = next(
            item
            for item in json.loads(EXPLORATORY_HELDOUT.read_text(encoding="utf-8")).get("images", [])
            if item.get("subject", {}).get("id") == field_id
        )
    except (OSError, json.JSONDecodeError, StopIteration, AttributeError, TypeError):
        return None
    replay_evidence = replay.get("evidence", {}).get("segmentation_mask")
    if not isinstance(replay_evidence, dict) or not _same_recorded_sources(image, replay):
        return None
    return {
        **replay_evidence,
        "artifact_provenance": {
            "source": str(EXPLORATORY_HELDOUT.relative_to(ROOT)),
            "kind": "exploratory replay artifact",
            "source_hashes_match_official": True,
            "note": "The official frozen result did not retain a segmentation image. This display artifact was generated by a separately committed exploratory replay using the identical recorded TIFF hashes.",
        },
    }


def _saved_mask(field_id: str, evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    """Committed exploratory masks for the saved runs (results/v1_1/masks); hash-checked on serve."""
    if not evidence or _saved_mask_file(field_id, "mask") is None:
        return None
    overlay = f"/api/saved-mask/{field_id}/overlay" if _saved_mask_file(field_id, "overlay") else None
    layers = [{"id": "overlay", "label": "Segmentation overlay: void blue, silicon orange, graphite unshaded (Polaron-stated)", "imageUrl": overlay, "verified": True}] if overlay else []
    return {
        "maskUrl": f"/api/saved-mask/{field_id}/mask",
        "overlayUrl": overlay,
        "layers": layers,
        "offset": evidence.get("mask_offset_px"),
        "sha256": evidence.get("mask_sha256"),
        "width": (evidence.get("mask_shape") or [None, None])[1],
        "height": (evidence.get("mask_shape") or [None, None])[0],
        "note": evidence.get("note"),
        "provenance": evidence.get("artifact_provenance"),
    }


@app.get("/api/saved-mask/{field_id}/{kind}")
def saved_mask(field_id: str, kind: str) -> FileResponse:
    path = _saved_mask_file(field_id, kind)
    if path is None:
        raise HTTPException(404, "No committed mask for this saved field.")
    if kind == "mask":
        expected = None
        for source in (HELDOUT, EXPLORATORY_HELDOUT, TEST_SET):
            segmentation = _field_segmentation(source, field_id)
            if segmentation:
                expected = segmentation.get("mask_sha256")
        if expected and _sha256(path) != expected:
            raise HTTPException(409, "Committed mask checksum does not match the saved record.")
    return FileResponse(path, media_type="image/png")


def _run_source(run_id: str, field_id: str, channel: str) -> Path:
    _id_or_422(run_id, "run id")
    state = jobs.load_run(run_id)
    if state is None:
        raise HTTPException(404, "Unknown run.")
    upload_id = _id_or_422(str(state["uploadId"]), "upload id")
    root = jobs.upload_path(upload_id)
    manifest = root / "manifest.json"
    if manifest.is_file():
        try:
            files = json.loads(manifest.read_text(encoding="utf-8")).get("files", [])
            for item in files:
                if item.get("fieldId") == field_id and item.get("channel") == channel:
                    candidate = root / str(item["filename"])
                    if candidate.is_file():
                        return candidate
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            pass
    for suffix in (".tif", ".tiff", ".TIF", ".TIFF"):
        candidate = root / f"img_{field_id}_{channel}{suffix}"
        if candidate.is_file():
            return candidate
    raise HTTPException(404, "The original TIFF for this exploratory field is unavailable.")


def _run_channel(run_id: str, field_id: str, channel: str) -> dict[str, Any]:
    source = _run_source(run_id, field_id, channel)
    with tifffile.TiffFile(source) as image:
        width, height = int(image.pages[0].imagewidth), int(image.pages[0].imagelength)
    return {
        "name": channel, "filename": source.name, "sha256": _sha256(source), "width": width, "height": height,
        "available": True, "previewUrl": f"/api/runs/{run_id}/preview/{field_id}/{channel}",
        "rawUrl": f"/api/runs/{run_id}/raw/{field_id}/{channel}",
    }


def _normalise_run(run_id: str, image: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    field = _normalise(image, raw_inputs)
    field_id = str(field["id"])
    field["channels"] = [_run_channel(run_id, field_id, channel) for channel in image.get("acquisition", {}).get("detectors_present", [])]
    segmentation = image.get("evidence", {}).get("segmentation_mask")
    if isinstance(segmentation, dict):
        field.update({
            "overlayUrl": f"/api/runs/{run_id}/overlay/{field_id}",
            "originalCroppedPreviewUrl": f"/api/runs/{run_id}/cropped-preview/{field_id}",
            "layers": [
                {"id": "phase-0", "label": "Void / pore", "imageUrl": f"/api/runs/{run_id}/layer/{field_id}/0", "verified": True},
                {"id": "phase-1", "label": "Graphite", "imageUrl": f"/api/runs/{run_id}/layer/{field_id}/1", "verified": True},
                {"id": "phase-2", "label": "Silicon-containing", "imageUrl": f"/api/runs/{run_id}/layer/{field_id}/2", "verified": True},
            ],
            "maskMeta": {"maskUrl": f"/api/runs/{run_id}/mask/{field_id}", "cropOffsetPx": segmentation.get("mask_offset_px"), "offset": segmentation.get("mask_offset_px"), "sha256": segmentation.get("mask_sha256"), "shape": segmentation.get("mask_shape"), "note": segmentation.get("note")},
        })
        field["mask"] = {**field["maskMeta"], "overlayUrl": field["overlayUrl"], "originalCroppedPreviewUrl": field["originalCroppedPreviewUrl"], "layers": field["layers"], "width": segmentation["mask_shape"][1], "height": segmentation["mask_shape"][0]}
    return field


def _run_result(run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    state = jobs.load_run(run_id)
    if state is None:
        raise HTTPException(404, "Unknown run.")
    result = jobs.run_path(run_id) / "result.json"
    if not result.is_file():
        raise HTTPException(409, "This run has not produced a result yet.")
    return state, json.loads(result.read_text(encoding="utf-8"))


def _png_response(array: np.ndarray) -> Response:
    image = Image.fromarray(array)
    image.thumbnail((MAX_PREVIEW_EDGE, MAX_PREVIEW_EDGE), Image.Resampling.LANCZOS)
    encoded = io.BytesIO()
    image.save(encoded, format="PNG", optimize=True)
    return Response(encoded.getvalue(), media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


def _native_crop(source: Path, x: int, y: int, width: int, height: int) -> Response:
    """Crop source pixels first; bound only the returned display PNG."""
    if width < 1 or height < 1:
        raise HTTPException(422, "width and height must be positive source-pixel integers.")
    with tifffile.TiffFile(source) as tif:
        page = tif.pages[0]
        source_width, source_height = int(page.imagewidth), int(page.imagelength)
        if x < 0 or y < 0 or x >= source_width or y >= source_height:
            raise HTTPException(422, "x and y must fall inside the source image.")
        # Clamp the requested rectangle at the right/bottom source edge without
        # moving its origin; reported headers tell clients the actual bounds.
        right, bottom = min(source_width, x + width), min(source_height, y + height)
        image = tif.asarray(key=0)
    cropped = image[y:bottom, x:right]
    if cropped.ndim == 3 and cropped.shape[-1] == 1:
        cropped = cropped[..., 0]
    display = Image.fromarray(cropped)
    resampled = max(display.size) > MAX_CROP_EDGE
    if resampled:
        display.thumbnail((MAX_CROP_EDGE, MAX_CROP_EDGE), Image.Resampling.LANCZOS)
    encoded = io.BytesIO()
    display.save(encoded, format="PNG", compress_level=6)
    return Response(encoded.getvalue(), media_type="image/png", headers={
        "Cache-Control": "private, max-age=300",
        "X-Cottrell-Crop": f"{x},{y},{right - x},{bottom - y}",
        "X-Cottrell-Source-Coordinates": "native",
        "X-Cottrell-Display-Resampled": str(resampled).lower(),
    })


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
    bundle = jobs.exploration_bundle()
    ready = bool(bundle["verified"])
    return {
        "savedResultsReady": HELDOUT.is_file(),
        "liveRunReady": ready,
        "uploadReplayReady": True,
        "reviewPersistenceReady": True,
        "reason": "Local exploratory inference is available with the pinned engine bundle." if ready else "The local exploratory engine bundle is incomplete.",
        "explorationBundle": bundle,
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
    if dataset == "test":
        if not TEST_SET.is_file():
            raise HTTPException(404, "The saved test-set output is not present.")
        test = json.loads(TEST_SET.read_text(encoding="utf-8"))
        return {
            "mode": "Saved test-set output (6 images, frozen v1, exploratory label)",
            "run": test["run"],
            "fields": [_normalise(item, test["inputs"].get(item["subject"]["id"], {})) for item in test["images"]],
            "limitations": [
                "Frozen v1 model applied once to 6 never-seen images; true batches unknown at the time of the run.",
                "Batch-match probabilities are not defect probabilities.",
                "Phase identity: stated by Polaron, not image-verified.",
            ],
        }
    if dataset != "heldout":
        raise HTTPException(422, "dataset must be 'validation', 'heldout' or 'test'.")
    saved = _saved()
    return {
        "mode": "Saved official held-out evaluation (3 images)",
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


@app.get("/api/crop/{field_id}/{channel}")
def saved_crop(field_id: str, channel: str, x: int, y: int, width: int, height: int, dataset: str = "validation") -> Response:
    if dataset != "validation":
        raise HTTPException(422, "Only the explicitly bound validation dataset supports saved-image crops.")
    if field_id not in {record[0]["subject"]["id"] for record in _validation_records()}:
        raise HTTPException(404, "Unknown validation field.")
    return _native_crop(_source_or_404(field_id, channel), x, y, width, height)


@app.get("/api/runs/{run_id}/raw/{field_id}/{channel}")
def run_raw(run_id: str, field_id: str, channel: str) -> FileResponse:
    _run_result(run_id)
    source = _run_source(run_id, field_id, channel)
    return FileResponse(source, media_type="image/tiff", filename=source.name)


@app.get("/api/runs/{run_id}/preview/{field_id}/{channel}")
def run_preview(run_id: str, field_id: str, channel: str) -> Response:
    _run_result(run_id)
    array = tifffile.imread(_run_source(run_id, field_id, channel), key=0)
    if array.ndim == 3:
        array = array[..., 0]
    return _png_response(array.astype(np.uint8, copy=False))


@app.get("/api/runs/{run_id}/crop/{field_id}/{channel}")
def run_crop(run_id: str, field_id: str, channel: str, x: int, y: int, width: int, height: int) -> Response:
    _run_result(run_id)  # only a run-owned, persisted original may be cropped
    return _native_crop(_run_source(run_id, field_id, channel), x, y, width, height)


def _run_field(run_id: str, field_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _, result = _run_result(run_id)
    for image in result["images"]:
        if image["subject"]["id"] == field_id:
            evidence = image.get("evidence", {}).get("segmentation_mask")
            if not isinstance(evidence, dict):
                raise HTTPException(404, "No verified segmentation evidence for this field.")
            return result, image, evidence
    raise HTTPException(404, "Unknown field in this run.")


def _mask_path(run_id: str, field_id: str) -> tuple[Path, dict[str, Any]]:
    _, _, evidence = _run_field(run_id, field_id)
    path = jobs.run_path(run_id) / str(evidence["mask_path"])
    if not path.is_file():
        raise HTTPException(404, "Segmentation mask file is unavailable.")
    if _sha256(path) != evidence.get("mask_sha256"):
        raise HTTPException(409, "Segmentation mask checksum does not match the engine record.")
    return path, evidence


@lru_cache(maxsize=64)
def _review_regions_cached(run_id: str, field_id: str, source_hash: str, mask_hash: str) -> dict[str, Any]:
    """One hash-bound diagnostic calculation per source/mask pair per process."""
    from app.review_regions import generate_review_regions

    source = _run_source(run_id, field_id, "BSE")
    mask, _ = _mask_path(run_id, field_id)
    document = generate_review_regions(source, mask, jobs.run_path(run_id) / "review-regions")
    if document.get("sourceHash") != source_hash or document.get("maskHash") != mask_hash:
        raise HTTPException(409, "Review diagnostic hashes do not match the verified source evidence.")
    return document


@app.get("/api/runs/{run_id}/review-regions")
def review_regions(run_id: str, field: str) -> dict[str, Any]:
    _id_or_422(run_id, "run id")
    state, _ = _run_result(run_id)
    if state.get("state") != "completed":
        raise HTTPException(409, "Review regions are available only after a completed exploratory run.")
    source = _run_source(run_id, field, "BSE")
    mask, evidence = _mask_path(run_id, field)
    source_hash, mask_hash = _sha256(source), _sha256(mask)
    expected_hashes = set(_run_field(run_id, field)[1].get("subject", {}).get("file_hashes", {}).values())
    if source_hash not in expected_hashes or mask_hash != evidence.get("mask_sha256"):
        raise HTTPException(409, "Review regions require the exact BSE source and exact verified engine mask.")
    document = _review_regions_cached(run_id, field, source_hash, mask_hash)
    document = {**document, "runId": run_id, "fieldId": field, "diagnosticHash": hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()}
    return document


@app.get("/api/runs/{run_id}/overlay/{field_id}")
def run_overlay(run_id: str, field_id: str) -> FileResponse:
    _, _, evidence = _run_field(run_id, field_id)
    path = jobs.run_path(run_id) / str(evidence["overlay_path"])
    if not path.is_file():
        raise HTTPException(404, "Segmentation overlay is unavailable.")
    return FileResponse(path, media_type="image/png")


@app.get("/api/runs/{run_id}/mask/{field_id}")
def run_mask(run_id: str, field_id: str) -> FileResponse:
    path, _ = _mask_path(run_id, field_id)
    return FileResponse(path, media_type="image/png")


@app.get("/api/runs/{run_id}/cropped-preview/{field_id}")
def run_cropped_preview(run_id: str, field_id: str) -> Response:
    _, _, evidence = _run_field(run_id, field_id)
    source = _run_source(run_id, field_id, "BSE")
    image = tifffile.imread(source, key=0)
    if image.ndim == 3:
        image = image[..., 0]
    offset = int((evidence.get("mask_offset_px") or [0])[0])
    if offset:
        image = image[offset:-offset, offset:-offset]
    return _png_response(image.astype(np.uint8, copy=False))


@app.get("/api/runs/{run_id}/layer/{field_id}/{label}")
def run_layer(run_id: str, field_id: str, label: int) -> Response:
    if label not in {0, 1, 2}:
        raise HTTPException(404, "Unknown phase layer.")
    path, _ = _mask_path(run_id, field_id)
    mask = np.asarray(Image.open(path), dtype=np.uint8)
    rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
    rgba[mask == label] = ((31, 119, 180, 220) if label == 0 else (143, 143, 143, 220) if label == 1 else (255, 127, 14, 220))
    return _png_response(rgba)


def _field_channel_from_name(filename: str) -> tuple[str, str] | None:
    match = re.search(r"(?:img_)?([^_]+)_([A-Za-z0-9]+)\.tiff?$", filename, re.I)
    return (match.group(1), match.group(2)) if match else None


@app.post("/api/uploads")
async def uploads(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    received: list[dict[str, Any]] = []
    matches: dict[str, set[str]] = {}
    grouped: dict[str, set[str]] = {}
    pending: list[tuple[str, bytes]] = []
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
        received.append({"filename": filename, "fieldId": field_id, "channel": channel, "sha256": digest, "bytes": len(data), "shape": shape, "dtype": dtype, "layout": layout, "recordedSource": replay is not None})
        pending.append((filename, data))
    missing_bse = [field_id for field_id, channels in grouped.items() if "BSE" not in channels]
    if missing_bse:
        raise HTTPException(422, "Each field needs one BSE TIFF. Missing BSE for: " + ", ".join(sorted(missing_bse)))
    saved = _saved()
    replay_fields = [
        _normalise(item, saved["inputs"].get(field_id, {}))
        for item in saved["images"]
        if (field_id := item["subject"]["id"]) in matches and "BSE" in matches[field_id]
    ]
    upload_id = uuid.uuid4().hex
    upload_dir = jobs.upload_path(upload_id)
    upload_dir.mkdir(parents=True, exist_ok=False)
    for filename, data in pending:
        (upload_dir / filename).write_bytes(data)
    manifest = {"uploadId": upload_id, "createdAt": time.time(), "files": received, "validFields": [{"id": field_id, "channels": sorted(channels)} for field_id, channels in sorted(grouped.items())]}
    (upload_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "uploadId": upload_id,
        "mode": "Saved evaluation replay" if replay_fields else "Upload validated",
        "uploads": received,
        "validFields": manifest["validFields"],
        "fields": replay_fields,
        "liveRunReady": capabilities()["liveRunReady"],
        "reason": "Exact recorded source hashes matched a saved result." if replay_fields else "Files were validated and persisted for an exploratory local run.",
    }


@app.post("/api/runs")
async def start_run(payload: dict[str, Any]) -> dict[str, Any]:
    upload_id = payload.get("uploadId")
    if not isinstance(upload_id, str) or not ID_RE.fullmatch(upload_id) or not jobs.upload_path(upload_id).is_dir():
        raise HTTPException(422, "A valid uploadId is required.")
    manifest_path = jobs.upload_path(upload_id) / "manifest.json"
    if not manifest_path.is_file():
        raise HTTPException(422, "Upload manifest is missing.")
    bundle = jobs.exploration_bundle()
    if not bundle["verified"]:
        raise HTTPException(503, "The local exploratory engine bundle is not ready.")
    if jobs.active_run_exists():
        raise HTTPException(409, "One local exploratory run is already active.")
    criteria = payload.get("criteria")
    if not isinstance(criteria, (dict, list)):
        raise HTTPException(422, "criteria must be an object or a list of criterion rows.")
    if isinstance(criteria, list):
        for index, row in enumerate(criteria):
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                raise HTTPException(422, f"criteria[{index}] must include an id.")
            if row.get("enabled"):
                low, high = _finite(row.get("min")), _finite(row.get("max"))
                if low is None or high is None or low > high:
                    raise HTTPException(422, f"criteria[{index}] needs finite ordered minimum and maximum values.")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    metadata = {**metadata, "explorationBundle": bundle}
    state = jobs.create_run(upload_id, criteria, metadata)
    try:
        state = jobs.launch(state["id"])
    except Exception as exc:
        state = jobs.update_run(state["id"], state="failed", stage="Failed", error=f"Could not start local worker: {exc}")
    return {key: state.get(key) for key in ("id", "state", "stage")}


@app.get("/api/runs/{run_id}")
def run_status(run_id: str) -> dict[str, Any]:
    _id_or_422(run_id, "run id")
    state = jobs.reconcile(run_id)
    if state is None:
        raise HTTPException(404, "Unknown run.")
    response = {key: state.get(key) for key in ("id", "state", "stage", "error") if state.get(key) is not None}
    endpoint = state.get("updatedAt", time.time()) if state.get("state") in {"completed", "failed", "cancelled"} else time.time()
    response["elapsedSeconds"] = max(0, round(float(endpoint) - float(state.get("createdAt", endpoint)), 1))
    return response


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str) -> dict[str, Any]:
    _id_or_422(run_id, "run id")
    try:
        state = jobs.cancel(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Unknown run.") from exc
    return {key: state.get(key) for key in ("id", "state", "stage", "error")}


@app.get("/api/runs/{run_id}/results")
def run_results(run_id: str) -> dict[str, Any]:
    _id_or_422(run_id, "run id")
    state, result = _run_result(run_id)
    if state.get("state") != "completed":
        raise HTTPException(409, "This exploratory run is not complete.")
    run_info = {**result["run"], "id": run_id, "explorationBundle": state.get("metadata", {}).get("explorationBundle")}
    return {"mode": "Exploratory analysis", "run": run_info, "criteria": state.get("criteria", []), "metadata": state.get("metadata", {}), "reviews": [review for values in _REVIEWS.values() for review in values if review.get("runId") == run_id], "fields": [_normalise_run(run_id, image, result["inputs"].get(image["subject"]["id"], {})) for image in result["images"]], "limitations": ["This is an exploratory local run, not the official held-out evaluation.", "Batch-match probabilities are not defect probabilities.", "Phase identity: stated by Polaron, not image-verified."]}


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
    saved_ids: set[str] = {item["subject"]["id"] for item in _saved()["images"]}
    if TEST_SET.is_file():
        try:
            saved_ids.update(item["subject"]["id"] for item in json.loads(TEST_SET.read_text(encoding="utf-8"))["images"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            # The test-set report is optional. Its absence or corruption must not
            # make validation/run-backed review records unavailable.
            pass
    if field_id in saved_ids or field_id in {item[0]["subject"]["id"] for item in _validation_records()}:
        return True
    if jobs.RUNS.is_dir():
        for path in jobs.RUNS.iterdir():
            result = path / "result.json"
            if result.is_file():
                try:
                    if field_id in {item["subject"]["id"] for item in json.loads(result.read_text(encoding="utf-8"))["images"]}:
                        return True
                except (OSError, json.JSONDecodeError, KeyError):
                    continue
    return False


def _store_review(field_id: str, review: dict[str, Any]) -> dict[str, Any]:
    if not _known_field(field_id):
        raise HTTPException(404, "Unknown saved-result field.")
    run_id = review.get("runId")
    source_verified = False
    if run_id:
        _id_or_422(str(run_id), "run id")
        _, run_result = _run_result(str(run_id))
        match = next((item for item in run_result["images"] if item["subject"]["id"] == field_id), None)
        if match is None:
            raise HTTPException(422, "The review field does not belong to this run.")
        detector = review.get("detector", "BSE")
        source = _run_source(str(run_id), field_id, detector)
        if review.get("sourceHash") != _sha256(source):
            raise HTTPException(422, "The review source hash does not match the analysed image.")
        roi = review.get("roi")
        if roi is not None:
            if not isinstance(roi, dict) or any(not isinstance(roi.get(key), int) for key in ("x", "y", "width", "height")):
                raise HTTPException(422, "roi must have integer x, y, width and height source coordinates.")
            with tifffile.TiffFile(source) as tif:
                width, height = int(tif.pages[0].imagewidth), int(tif.pages[0].imagelength)
            if roi["x"] < 0 or roi["y"] < 0 or roi["width"] < 1 or roi["height"] < 1 or roi["x"] + roi["width"] > width or roi["y"] + roi["height"] > height:
                raise HTTPException(422, "roi is outside the analysed source-image bounds.")
        source_verified = True
        region_evidence = review.get("regionEvidence")
        if region_evidence is not None:
            if not isinstance(region_evidence, dict):
                raise HTTPException(422, "regionEvidence must be an object.")
            mask, evidence = _mask_path(str(run_id), field_id)
            diagnostic = _review_regions_cached(str(run_id), field_id, _sha256(source), _sha256(mask))
            diagnostic_hash = hashlib.sha256(json.dumps(diagnostic, sort_keys=True).encode()).hexdigest()
            diagnostic_id = region_evidence.get("diagnosticId", region_evidence.get("id"))
            if diagnostic_id != diagnostic.get("id") or region_evidence.get("method") != diagnostic.get("method") or region_evidence.get("hash", region_evidence.get("diagnosticHash")) != diagnostic_hash:
                raise HTTPException(422, "regionEvidence does not match the verified review diagnostic.")
            region_id = region_evidence.get("regionId")
            region = next((item for item in diagnostic.get("regions", []) if item.get("id") == region_id), None)
            if region is None or review.get("roi") != region.get("roi"):
                raise HTTPException(422, "regionEvidence regionId and roi must match one suggested diagnostic region.")
    elif not review.get("skipped"):
        validation_ids = {record[0]["subject"]["id"] for record in _validation_records()}
        if field_id not in validation_ids:
            raise HTTPException(422, "A non-run review needs a bound validation image, or must be saved as skipped.")
        detector = review.get("detector", review.get("channel", "BSE"))
        if detector not in CHANNELS:
            raise HTTPException(422, "Unsupported review detector channel.")
        source = _source_or_404(field_id, detector)
        if review.get("sourceHash") != _sha256(source):
            raise HTTPException(422, "The review source hash does not match the bound validation image.")
        roi = review.get("roi")
        if not isinstance(roi, dict) or any(not isinstance(roi.get(key), int) for key in ("x", "y", "width", "height")):
            raise HTTPException(422, "roi must have integer x, y, width and height source coordinates.")
        with tifffile.TiffFile(source) as tif:
            width, height = int(tif.pages[0].imagewidth), int(tif.pages[0].imagelength)
        if roi["x"] < 0 or roi["y"] < 0 or roi["width"] < 1 or roi["height"] < 1 or roi["x"] + roi["width"] > width or roi["y"] + roi["height"] > height:
            raise HTTPException(422, "roi is outside the bound validation source-image bounds.")
        source_verified = True
    safe = {key: review.get(key) for key in ("runId", "tag", "note", "channel", "detector", "sourceHash", "roi", "regionEvidence", "skipped", "taskType", "reviewer", "time", "timestamp", "taskVersion")}
    safe["channel"] = safe.get("detector") or safe.get("channel")
    safe["fieldId"] = field_id
    safe["sourceVerified"] = source_verified
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

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
VALIDATION_PREVIEWS = ROOT / "results" / "v1" / "validation_previews"
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
    saved_preview = _validation_preview(field_id, channel) if source is None else None
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
        "previewAvailable": source is not None or saved_preview is not None,
        "previewKind": "saved-micrograph" if saved_preview else "original",
    }
    if source is not None:
        if expected is None:
            expected = _sha256(source)
            result["sha256"] = expected
        with tifffile.TiffFile(source) as image:
            result.update(width=int(image.pages[0].imagewidth), height=int(image.pages[0].imagelength))
    elif saved_preview:
        _, metadata = saved_preview
        result.update(
            sha256=metadata["source_sha256"], width=metadata["width"], height=metadata["height"],
            previewWidth=metadata["preview_width"], previewHeight=metadata["preview_height"],
            previewProvenance={"source": f"results/v1/validation_previews/{metadata['filename']}", "method": metadata["method"], "sha256": metadata["preview_sha256"]},
        )
    else:
        result.update(width=None, height=None)
    return result


def _validation_preview(field_id: str, channel: str) -> tuple[Path, dict[str, Any]] | None:
    """Serve only hash-bound display previews for the selected validation fields."""
    if field_id not in {item[0]["subject"]["id"] for item in _validation_records()} or channel not in CHANNELS:
        return None
    manifest = VALIDATION_PREVIEWS / "manifest.json"
    if not manifest.is_file():
        return None
    metadata = json.loads(manifest.read_text(encoding="utf-8")).get("entries", {}).get(f"{field_id}_{channel}")
    if not metadata or metadata.get("filename") != f"{field_id}_{channel}.png":
        return None
    path = VALIDATION_PREVIEWS / metadata["filename"]
    if not path.is_file():
        return None
    if _sha256(path) != metadata.get("preview_sha256"):
        raise HTTPException(409, "Saved validation preview checksum does not match its manifest.")
    return path, metadata


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
    annotation_source = _saved_segmentation_annotation_source(
        field_id, "overlay" if overlay else "mask", evidence
    )
    return {
        "maskUrl": f"/api/saved-mask/{field_id}/mask",
        "compareUrl": f"/api/compare/saved/{field_id}",
        "overlayUrl": overlay,
        "layers": layers,
        "offset": evidence.get("mask_offset_px"),
        "sha256": evidence.get("mask_sha256"),
        "width": (evidence.get("mask_shape") or [None, None])[1],
        "height": (evidence.get("mask_shape") or [None, None])[0],
        "note": evidence.get("note"),
        "provenance": evidence.get("artifact_provenance"),
        # Drawing on a saved segmentation is deliberately in the artifact's own
        # pixel frame, not a claim about native TIFF coordinates or model output.
        "annotationSource": {key: value for key, value in annotation_source.items() if key != "coordinateSpace"},
    }


def _recorded_source_hash(field_id: str, channel: str) -> str | None:
    return next((digest for digest, pair in _recorded_files().items() if pair == (field_id, channel)), None)


def _saved_segmentation_annotation_source(field_id: str, artifact: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Describe a displayed committed artifact in its actual PNG coordinate frame."""
    path = _saved_mask_file(field_id, artifact)
    if path is None:  # guarded by callers; keeps the returned document honest.
        raise HTTPException(404, "No committed segmentation artifact for this saved field.")
    try:
        with Image.open(path) as image:
            width, height = image.size
    except (OSError, ValueError) as exc:
        raise HTTPException(409, "Saved segmentation artifact is unreadable.") from exc
    digest = _sha256(path)
    if artifact == "mask" and digest != evidence.get("mask_sha256"):
        raise HTTPException(409, "Committed mask checksum does not match the saved record.")
    source = {
        "kind": "saved-segmentation",
        "artifact": artifact,
        "sha256": digest,
        "width": width,
        "height": height,
        "coordinateSpace": "saved-preview",
    }
    source_hash = _recorded_source_hash(field_id, "BSE")
    if source_hash is not None:
        source["sourceHash"] = source_hash
    return source


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
        field["mask"] = {**field["maskMeta"], "overlayUrl": field["overlayUrl"], "originalCroppedPreviewUrl": field["originalCroppedPreviewUrl"], "layers": field["layers"], "compareUrl": f"/api/compare/run/{field_id}?run_id={run_id}", "width": segmentation["mask_shape"][1], "height": segmentation["mask_shape"][0]}
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
    if _find_source(field_id, channel) is None:
        saved_preview = _validation_preview(field_id, channel)
        if saved_preview:
            return FileResponse(saved_preview[0], media_type="image/png", headers={"Cache-Control": "private, max-age=300", "X-Cottrell-Preview": "saved-micrograph"})
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
    if dataset == "validation":
        known = {record[0]["subject"]["id"] for record in _validation_records()}
    elif dataset in ("heldout", "test"):
        source = HELDOUT if dataset == "heldout" else TEST_SET
        known = {item["subject"]["id"] for item in json.loads(source.read_text(encoding="utf-8")).get("images", [])} if source.is_file() else set()
    else:
        raise HTTPException(422, "dataset must be 'validation', 'heldout' or 'test'.")
    if field_id not in known:
        raise HTTPException(404, "Unknown saved field for this dataset.")
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
    if TEST_SET.is_file():
        try:
            if field_id in {item["subject"]["id"] for item in json.loads(TEST_SET.read_text(encoding="utf-8"))["images"]}:
                return True
        except (OSError, json.JSONDecodeError, KeyError):
            pass
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


def _review_roi(roi: Any, width: int, height: int, *, bounds_label: str) -> dict[str, int]:
    if not isinstance(roi, dict) or any(not isinstance(roi.get(key), int) for key in ("x", "y", "width", "height")):
        raise HTTPException(422, "roi must have integer x, y, width and height coordinates.")
    if roi["x"] < 0 or roi["y"] < 0 or roi["width"] < 1 or roi["height"] < 1 or roi["x"] + roi["width"] > width or roi["y"] + roi["height"] > height:
        raise HTTPException(422, f"roi is outside the {bounds_label} bounds.")
    return {key: roi[key] for key in ("x", "y", "width", "height")}


def _saved_segmentation_evidence_for_field(field_id: str) -> dict[str, Any] | None:
    """Resolve only a saved mask whose provenance remains bound to this field."""
    for saved_path in (HELDOUT, TEST_SET):
        if not saved_path.is_file():
            continue
        try:
            image = next(
                item for item in json.loads(saved_path.read_text(encoding="utf-8")).get("images", [])
                if item.get("subject", {}).get("id") == field_id
            )
        except (OSError, json.JSONDecodeError, StopIteration, AttributeError, TypeError):
            continue
        evidence = _saved_segmentation_evidence(image)
        if evidence is not None:
            return evidence
    return None


def _saved_micrograph_annotation_source(field_id: str, channel: str) -> dict[str, Any]:
    saved_preview = _validation_preview(field_id, channel)
    if saved_preview is None:
        raise HTTPException(422, "No hash-bound saved micrograph preview is available for this field and channel.")
    _, metadata = saved_preview
    return {
        "kind": "saved-micrograph",
        "sha256": metadata["preview_sha256"],
        "width": metadata["preview_width"],
        "height": metadata["preview_height"],
        "sourceHash": metadata.get("source_sha256"),
        "coordinateSpace": "saved-preview",
    }


def _verified_saved_annotation_source(field_id: str, review_source: Any, channel: str) -> dict[str, Any]:
    """Validate an annotation against a committed display artifact, never TIFF pixels."""
    if not isinstance(review_source, dict):
        raise HTTPException(422, "reviewSource must be an object.")
    kind = review_source.get("kind")
    if kind == "saved-micrograph":
        expected = _saved_micrograph_annotation_source(field_id, channel)
    elif kind == "saved-segmentation":
        artifact = review_source.get("artifact")
        if artifact not in ("mask", "overlay"):
            raise HTTPException(422, "saved-segmentation reviewSource.artifact must be mask or overlay.")
        evidence = _saved_segmentation_evidence_for_field(field_id)
        if evidence is None:
            raise HTTPException(422, "No provenance-bound saved segmentation artifact is available for this field.")
        expected = _saved_segmentation_annotation_source(field_id, artifact, evidence)
    else:
        raise HTTPException(422, "reviewSource.kind must be saved-micrograph or saved-segmentation.")
    if review_source.get("sha256") != expected["sha256"]:
        raise HTTPException(422, "reviewSource sha256 does not match the displayed saved artifact.")
    if review_source.get("width") != expected["width"] or review_source.get("height") != expected["height"]:
        raise HTTPException(422, "reviewSource dimensions do not match the displayed saved artifact coordinate frame.")
    supplied_source_hash = review_source.get("sourceHash")
    if supplied_source_hash is not None and supplied_source_hash != expected.get("sourceHash"):
        raise HTTPException(422, "reviewSource sourceHash does not match the recorded original source.")
    return expected


def _store_review(field_id: str, review: dict[str, Any]) -> dict[str, Any]:
    if not _known_field(field_id):
        raise HTTPException(404, "Unknown saved-result field.")
    run_id = review.get("runId")
    source_verified = False
    artifact_verified = False
    coordinate_space: str | None = None
    review_source = review.get("reviewSource")
    if review_source is not None:
        if run_id:
            raise HTTPException(422, "reviewSource is only for saved display artifacts, not exploratory runs.")
        detector = review.get("detector", review.get("channel", "BSE"))
        if detector not in CHANNELS:
            raise HTTPException(422, "Unsupported review detector channel.")
        expected_source = _verified_saved_annotation_source(field_id, review_source, detector)
        _review_roi(review.get("roi"), expected_source["width"], expected_source["height"], bounds_label="saved artifact coordinate frame")
        # A saved PNG can be verified byte-for-byte, while sourceVerified remains
        # false because no original TIFF was read for this annotation.
        source_verified = False
        artifact_verified = True
        coordinate_space = expected_source["coordinateSpace"]
    elif run_id:
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
    if review_source is not None:
        # Persist the server-resolved evidence, not merely client-provided labels.
        safe["reviewSource"] = expected_source
    safe["channel"] = safe.get("detector") or safe.get("channel")
    safe["fieldId"] = field_id
    safe["sourceVerified"] = source_verified
    safe["artifactVerified"] = artifact_verified
    if coordinate_space is not None:
        safe["coordinateSpace"] = coordinate_space
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


# ---------------------------------------------------------------------------
# Side-by-side comparison: this image next to one representative training image
# per batch, same mask-derived layer on each. Everything is read from the frozen
# mask the measurements came from (no new segmentation, no inferred layers).
# ---------------------------------------------------------------------------
REFERENCE_DIR = ROOT / "results" / "v1_1" / "reference"
TRAINING_KPIS = ROOT / "results" / "kpi_per_image.parquet"
COMPARE_ZOOM_PX = 600
COMPARE_FULL_WIDTH = 1400
CRACK_ASPECT_MIN = 5.0  # configs/v1.yaml kpi_extra.crack_aspect_min (Phase B c0_cracklike_frac)
COMPARE_LAYERS = [
    {"id": "bse", "label": "BSE", "legend": []},
    {"id": "phases", "label": "Phase mask", "legend": [["pore", "Pore / void"], ["silicon", "Silicon"], ["graphite", "Graphite (unshaded)"]]},
    {"id": "pore", "label": "Pores", "legend": [["pore", "Pore / void (class 0)"]]},
    {"id": "graphite", "label": "Graphite", "legend": [["graphite", "Graphite (class 1)"]]},
    {"id": "silicon", "label": "Silicon", "legend": [["silicon", "Silicon (class 2)"]]},
    {"id": "cracklike", "label": "Crack-like voids", "legend": [["crack", "Crack-like void: void component with major/minor axis >= 5 (Phase B c0_cracklike_frac)"]]},
]
COMPARE_COLORS = {"pore": (31, 119, 180), "silicon": (255, 127, 14), "graphite": (46, 160, 96), "crack": (220, 38, 38)}


@lru_cache(maxsize=1)
def _reference_manifest() -> dict[str, Any]:
    path = REFERENCE_DIR / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"references": []}


def _reference_entry(field_id: str) -> dict[str, Any]:
    for item in _reference_manifest().get("references", []):
        if item["id"] == field_id:
            return item
    raise HTTPException(404, "Unknown reference image.")


def _saved_evidence(field_id: str) -> dict[str, Any] | None:
    for source in (HELDOUT, TEST_SET):
        if source.is_file():
            for item in json.loads(source.read_text(encoding="utf-8")).get("images", []):
                if item["subject"]["id"] == field_id:
                    evidence = item.get("evidence", {}).get("segmentation_mask")
                    return evidence if isinstance(evidence, dict) else None
    return None


def _compare_source(scope: str, field_id: str, run_id: str | None) -> tuple[Path, Path, int, str]:
    """(BSE TIFF, mask PNG, border offset, cache key) for one comparable image; hash-bound."""
    if not re.fullmatch(r"[A-Za-z0-9-]+", field_id):
        raise HTTPException(404, "Unknown field.")
    if scope == "saved":
        mask = _saved_mask_file(field_id, "mask")
        evidence = _saved_evidence(field_id)
        if mask is None or evidence is None:
            raise HTTPException(404, "No committed mask for this saved field.")
        mask_sha = _sha256(mask)
        if evidence.get("mask_sha256") and mask_sha != evidence["mask_sha256"]:
            raise HTTPException(409, "Committed mask checksum does not match the saved record.")
        return _source_or_404(field_id, "BSE"), mask, int((evidence.get("mask_offset_px") or [0])[0]), f"saved:{field_id}:{mask_sha}"
    if scope == "reference":
        entry = _reference_entry(field_id)
        mask = ROOT / "results" / "v1_1" / str(entry["mask_path"])
        tif = ROOT / str(entry["source"]["path"])
        if not mask.is_file():
            raise HTTPException(404, "Reference mask is unavailable.")
        if not tif.is_file():
            raise HTTPException(404, "The reference training TIFF is not present on this machine.")
        mask_sha = _sha256(mask)
        if mask_sha != entry["mask_sha256"] or _sha256(tif) != entry["source"]["sha256"]:
            raise HTTPException(409, "Reference artefact checksum does not match the manifest.")
        return tif, mask, int(entry["mask_offset_px"][0]), f"reference:{field_id}:{mask_sha}"
    if scope == "run":
        if not run_id:
            raise HTTPException(422, "run_id is required for run fields.")
        mask, evidence = _mask_path(run_id, field_id)
        return _run_source(run_id, field_id, "BSE"), mask, int((evidence.get("mask_offset_px") or [0])[0]), f"run:{run_id}:{field_id}:{evidence.get('mask_sha256')}"
    raise HTTPException(404, "scope must be 'saved', 'reference' or 'run'.")


@lru_cache(maxsize=6)
def _compare_arrays(key: str, tif: str, mask_path: str, offset: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cropped grayscale BSE, class mask and crack-like void mask (full resolution)."""
    from skimage.measure import label, regionprops_table

    image = tifffile.imread(tif, key=0)
    if image.ndim == 3:
        image = image[..., 0]
    if offset:
        image = image[offset:-offset, offset:-offset]
    mask = np.asarray(Image.open(mask_path), dtype=np.uint8)
    if mask.shape != image.shape:
        raise HTTPException(409, "Mask and BSE image shapes differ; cannot align the comparison layers.")
    labels = label(mask == 0, connectivity=1)
    props = regionprops_table(labels, properties=("label", "major_axis_length", "minor_axis_length"))
    minor = np.asarray(props["minor_axis_length"], dtype=np.float64)
    aspect = np.divide(np.asarray(props["major_axis_length"], dtype=np.float64), minor, out=np.full_like(minor, np.inf), where=minor > 0)
    crack = np.isin(labels, np.asarray(props["label"])[aspect >= CRACK_ASPECT_MIN]) if len(minor) else np.zeros_like(mask, dtype=bool)
    return image.astype(np.uint8, copy=False), mask, crack


@lru_cache(maxsize=64)
def _zoom_origin(key: str, tif: str, mask_path: str, offset: int, size: int) -> tuple[int, int]:
    """Deterministic zoom window: the size x size window with the most pore + silicon area (stride 50 px).

    The same rule is applied to every image so the four panels are chosen alike; it is a
    display choice, not a measurement."""
    _, mask, _ = _compare_arrays(key, tif, mask_path, offset)
    height, width = mask.shape
    size = min(size, height, width)
    ys = list(range(0, height - size + 1, 50)) or [0]
    xs = list(range(0, width - size + 1, 50)) or [0]
    interest = (mask != 1).astype(np.int64)
    integral = np.zeros((height + 1, width + 1), dtype=np.int64)
    integral[1:, 1:] = interest.cumsum(axis=0).cumsum(axis=1)
    best, origin = -1, (0, 0)
    for y in ys:
        for x in xs:
            total = integral[y + size, x + size] - integral[y, x + size] - integral[y + size, x] + integral[y, x]
            if total > best:
                best, origin = int(total), (y, x)
    return origin


def _compare_stats_from(mask: np.ndarray, crack: np.ndarray) -> dict[str, float | int]:
    total = float(mask.size)
    void = float((mask == 0).sum())
    return {
        "poreFraction": void / total,
        "graphiteFraction": float((mask == 1).sum()) / total,
        "siliconFraction": float((mask == 2).sum()) / total,
        "crackLikeFractionOfVoid": float(crack.sum()) / void if void else 0.0,
        "crackLikeAreaFraction": float(crack.sum()) / total,
        "maskWidth": int(mask.shape[1]),
        "maskHeight": int(mask.shape[0]),
    }


@lru_cache(maxsize=1)
def _training_kpi_ranges() -> dict[str, dict[str, dict[str, float]]]:
    """Per-batch min / median / max of the Phase B per-image KPIs behind the comparison numbers (31 training images)."""
    if not TRAINING_KPIS.is_file():
        return {}
    table = pq.read_table(TRAINING_KPIS, columns=["batch", "frac_c0", "frac_c1", "frac_c2", "c0_cracklike_frac"]).to_pydict()
    keys = {"frac_c0": "poreFraction", "frac_c1": "graphiteFraction", "frac_c2": "siliconFraction", "c0_cracklike_frac": "crackLikeFractionOfVoid"}
    out: dict[str, dict[str, dict[str, float]]] = {}
    for batch in sorted(set(table["batch"])):
        rows = [i for i, b in enumerate(table["batch"]) if b == batch]
        out[batch] = {}
        for column, name in keys.items():
            values = np.asarray([table[column][i] for i in rows], dtype=np.float64)
            out[batch][name] = {"min": float(values.min()), "median": float(np.median(values)), "max": float(values.max()), "n": int(len(values))}
    return out


@lru_cache(maxsize=256)
def _compare_png(key: str, tif: str, mask_path: str, offset: int, layer: str, zoom: int) -> bytes:
    import cv2

    gray, mask, crack = _compare_arrays(key, tif, mask_path, offset)
    height, width = gray.shape
    if zoom:
        size = min(zoom, height, width)
        y0, x0 = _zoom_origin(key, tif, mask_path, offset, size)
        gray, mask, crack = gray[y0:y0 + size, x0:x0 + size], mask[y0:y0 + size, x0:x0 + size], crack[y0:y0 + size, x0:x0 + size]
    elif width > COMPARE_FULL_WIDTH:
        target = (COMPARE_FULL_WIDTH, max(1, round(height * COMPARE_FULL_WIDTH / width)))
        gray = cv2.resize(gray, target, interpolation=cv2.INTER_AREA)
        mask = cv2.resize(mask, target, interpolation=cv2.INTER_NEAREST)
        crack = cv2.resize(crack.astype(np.uint8), target, interpolation=cv2.INTER_NEAREST).astype(bool)
    rgb = np.repeat(gray[..., None], 3, axis=2).astype(np.float64)

    def tint(selected: np.ndarray, color: tuple[int, int, int], alpha: float) -> None:
        rgb[selected] = (1 - alpha) * rgb[selected] + alpha * np.asarray(color, dtype=np.float64)

    if layer in ("phases", "pore"):
        tint(mask == 0, COMPARE_COLORS["pore"], 0.45)
    if layer in ("phases", "silicon"):
        tint(mask == 2, COMPARE_COLORS["silicon"], 0.45)
    if layer == "graphite":
        tint(mask == 1, COMPARE_COLORS["graphite"], 0.4)
    if layer == "cracklike":
        tint(crack, COMPARE_COLORS["crack"], 0.85)
    encoded = io.BytesIO()
    Image.fromarray(np.rint(rgb).astype(np.uint8)).save(encoded, format="PNG", compress_level=6)
    return encoded.getvalue()


@app.get("/api/compare/references")
def compare_references() -> dict[str, Any]:
    manifest = _reference_manifest()
    references = []
    for item in manifest.get("references", []):
        tif = ROOT / str(item["source"]["path"])
        references.append({
            "id": item["id"],
            "batch": item["batch"],
            "compareUrl": f"/api/compare/reference/{item['id']}",
            "available": tif.is_file() and (ROOT / "results" / "v1_1" / str(item["mask_path"])).is_file(),
            "distanceToBatchCentre": item.get("distance_to_batch_centre"),
        })
    return {
        "selectionRule": manifest.get("selection_rule"),
        "segmentation": manifest.get("segmentation"),
        "layers": COMPARE_LAYERS,
        "colors": {name: list(color) for name, color in COMPARE_COLORS.items()},
        "zoomPx": COMPARE_ZOOM_PX,
        "references": references,
        "trainingRanges": _training_kpi_ranges(),
        "phaseIdentity": "stated by Polaron, not image-verified",
    }


@app.get("/api/compare/{scope}/{field_id}")
def compare_stats(scope: str, field_id: str, run_id: str | None = None) -> dict[str, Any]:
    tif, mask_path, offset, key = _compare_source(scope, field_id, run_id)
    _, mask, crack = _compare_arrays(key, str(tif), str(mask_path), offset)
    return {"id": field_id, "scope": scope, **_compare_stats_from(mask, crack), "phaseIdentity": "stated by Polaron, not image-verified"}


@app.get("/api/compare/{scope}/{field_id}/image")
def compare_image(scope: str, field_id: str, layer: str = "bse", zoom: int = 0, run_id: str | None = None) -> Response:
    if layer not in {item["id"] for item in COMPARE_LAYERS}:
        raise HTTPException(404, "Unknown comparison layer.")
    if zoom not in (0, COMPARE_ZOOM_PX):
        raise HTTPException(422, f"zoom must be 0 or {COMPARE_ZOOM_PX}.")
    tif, mask_path, offset, key = _compare_source(scope, field_id, run_id)
    return Response(_compare_png(key, str(tif), str(mask_path), offset, layer, zoom), media_type="image/png", headers={"Cache-Control": "private, max-age=600"})

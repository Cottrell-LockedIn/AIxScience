"""Read-only model-card data assembled from committed v1 artifacts.

The endpoint deliberately does no fitting, scoring, or graph generation.  It
only exposes the fixed LOIO summary and records which claims cannot be checked
from the stored held-out JSON itself.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results" / "v1" / "loio_summary.json"
HELDOUT = ROOT / "results" / "v1" / "heldout.json"
SOFTWARE = ROOT / "docs" / "SOFTWARE_FEATURES_RECOMMENDATION.md"
HANDOFF = ROOT / "docs" / "HANDOFF_MODEL_CAPABILITIES.md"
MODEL_IMPROVEMENTS = ROOT / "docs" / "PRD_MODEL_IMPROVEMENTS.md"
EXPLORATORY_SIX = ROOT / "results" / "v1_1" / "heldout_test_exploratory.json"
ACCURACY_DIR = ROOT / "results" / "v1" / "accuracy_tab"
METRICS = ACCURACY_DIR / "metrics.json"
FIGURES = {
    "accuracy_vs_baselines": "accuracy_vs_baselines.png",
    "by_tier": "accuracy_by_tier.png",
    "confusion_matrix": "confusion_matrix.png",
    "per_batch": "per_batch_precision_recall.png",
    "roc": "roc_one_vs_rest.png",
}

router = APIRouter(tags=["model accuracy"])


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(path: Path) -> dict[str, str | bool]:
    return {"path": str(path.relative_to(ROOT)), "sha256": _hash(path), "available": True}


def _ratio(value: str) -> dict[str, int | str]:
    correct, total = value.split("/", 1)
    return {"label": value, "correct": int(correct), "total": int(total)}


@lru_cache(maxsize=1)
def model_accuracy_payload() -> dict[str, Any]:
    if not METRICS.is_file():
        raise HTTPException(503, "The committed accuracy-tab metrics are unavailable.")
    if not SUMMARY.is_file():
        raise HTTPException(503, "The committed LOIO summary is unavailable.")
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    required = ("n_images", "loio_correct", "wilson95", "permutation_p", "confusion_matrix")
    missing = [key for key in required if key not in summary]
    if missing:
        raise HTTPException(503, f"LOIO summary is incomplete: {', '.join(missing)}")

    sources = [_source(METRICS), _source(SUMMARY)]
    if HELDOUT.is_file():
        sources.append(_source(HELDOUT))
    if SOFTWARE.is_file():
        sources.append(_source(SOFTWARE))
    if HANDOFF.is_file():
        sources.append(_source(HANDOFF))
    if MODEL_IMPROVEMENTS.is_file():
        sources.append(_source(MODEL_IMPROVEMENTS))
    if EXPLORATORY_SIX.is_file():
        sources.append(_source(EXPLORATORY_SIX))

    heldout_raw = metrics["heldout"]
    heldout_note = {
        "status": heldout_raw["status"],
        "correct": heldout_raw["accuracy"]["k"], "total": heldout_raw["accuracy"]["n"],
        "confidence_scoring_correct": heldout_raw["judging_score"]["k"], "confidence_scoring_total": heldout_raw["judging_score"]["n"],
        "label": f"{heldout_raw['accuracy']['str']} correct; {heldout_raw['judging_score']['str']} under confidence scoring",
        "source": "results/v1/accuracy_tab/metrics.json",
        "verification": heldout_raw["status"],
        "confidence_scoring_rubric": heldout_raw["rule"],
        "rows": heldout_raw["rows"],
    }
    six_count = None
    if EXPLORATORY_SIX.is_file():
        six_count = len(json.loads(EXPLORATORY_SIX.read_text(encoding="utf-8")).get("images", []))
    overall = metrics["overall"]
    return {
        "release": {
            "model_version": "v1-frozen",
            "git_sha": metrics["provenance"].get("git_sha"),
            "config_hash": metrics["provenance"].get("config_hash"),
            "model": metrics.get("model"),
            "evaluation": "Leave-one-image-out (LOIO) over the 31 recorded training images; whole images are the samples, not tiles.",
        },
        "loio": {
            "n_images": overall["n_images"],
            "correct": overall["accuracy"]["k"],
            "accuracy": overall["accuracy"]["value"],
            "accuracy_label": overall["accuracy"]["str"],
            "wilson95": overall["accuracy"]["wilson95"],
            "majority_baseline": {
                "label": overall["majority_baseline"]["str"],
                "correct": overall["majority_baseline"]["k"],
                "total": overall["majority_baseline"]["n"],
            },
            "balanced_accuracy": overall.get("balanced_accuracy"),
            "permutation": {"p": overall["permutation_p"], "n": overall.get("n_permutations"), "seed": summary.get("permutation_seed")},
            "confusion": metrics["confusion_matrix"],
            "per_batch_recall": {key: {"label": value["recall"]["str"], "correct": value["recall"]["k"], "total": value["recall"]["n"]} for key, value in metrics["per_batch"].items()},
            "precision_by_pred_batch": {key: {"label": value["precision"]["str"], "correct": value["precision"]["k"], "total": value["precision"]["n"]} for key, value in metrics["per_batch"].items()},
            "accuracy_by_tier": {key: {"label": value["str"], "correct": value["k"], "total": value["n"]} for key, value in metrics["by_tier"].items()},
            "precision_by_pred_batch_tier": {},
        },
        "heldout": heldout_note,
        "figures": {key: f"/api/model-accuracy/figures/{key}" for key in FIGURES},
        "exploratory_six_image_run": {
            "status": "predictions_only" if EXPLORATORY_SIX.is_file() else "not_committed",
            "n_predictions": six_count,
            "note": f"{six_count} exploratory predictions are stored without true labels; no accuracy can be calculated from this artifact." if six_count is not None else "No exploratory prediction artifact is committed.",
        },
        "missing": [
            "The 5/6 competition confidence score is a separate rubric, not conventional accuracy.",
            "This is a small, image-level validation set. It is not an unseen-lot guarantee, and Batch_1 versus Batch_2 discrimination is weak.",
        ],
        "provenance": {"sources": sources, "rendering": "Numbers are read from committed artifacts. No model is run by this endpoint."},
    }


@router.get("/api/model-accuracy")
def get_model_accuracy() -> dict[str, Any]:
    return model_accuracy_payload()


@router.get("/api/model-accuracy/figures/{figure_id}")
def get_model_accuracy_figure(figure_id: str) -> FileResponse:
    filename = FIGURES.get(figure_id)
    if filename is None:
        raise HTTPException(404, "Unknown saved accuracy figure.")
    path = ACCURACY_DIR / "figures" / filename
    if not path.is_file():
        raise HTTPException(404, "Saved accuracy figure is unavailable.")
    return FileResponse(path, media_type="image/png", filename=filename)

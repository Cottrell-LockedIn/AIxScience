import json
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]


def test_cli_info_runs():
    out = subprocess.check_output([sys.executable, "-m", "qc", "info"], cwd=ROOT, text=True)
    data = json.loads(out)
    assert data["stages"][0] == "audit" and data["config_hash"]


def test_verdict_schema_is_valid_and_accepts_minimal_example():
    schema = json.loads((ROOT / "schema" / "verdict.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    example = {
        "subject": {"kind": "batch", "id": "Batch_2", "batch": "Batch_2", "n_images": 7},
        "verdict": {"label": "investigate", "rule": "conflicting evidence: KPI within band, embedding outside"},
        "pipeline": {"git_sha": "abc1234", "config_path": "configs/v1.yaml", "config_hash": "deadbeef0000",
                     "timestamp_utc": "2026-10-03T12:00:00Z", "frozen": False},
        "acquisition": {"detectors_present": ["BSE", "Inlens", "ETD"], "pixel_size_nm": None,
                        "pixel_size_confirmed": False},
        "evidence": {"drivers": [{"name": "highz_area_fraction", "units": "fraction", "effect_size": 1.4,
                                   "direction": "higher"}]},
        "uncertainty": {"sampling": "n=7 images", "segmentation": "+/-0.4 pp under +/-10% threshold",
                        "decision_margin": "0.2 sd above 95% band"},
        "routing": {"stakeholder": "materials_expert_review", "reason": "conflicting evidence"},
        "next_action": "Review representative tiles; confirm high-Z phase identity with Polaron.",
    }
    jsonschema.validate(example, schema)


def test_download_listing_present():
    listing = json.loads((ROOT / "docs" / "Log" / "assets" / "drive_file_listing.json").read_text())
    assert set(listing) == {"Batch_1", "Batch_2", "Batch_3"}
    assert sum(len(v) for v in listing.values()) >= 90

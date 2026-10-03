from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(path: str | Path = "configs/v1.yaml") -> dict[str, Any]:
    p = (ROOT / path) if not Path(path).is_absolute() else Path(path)
    cfg = yaml.safe_load(p.read_text())
    cfg["_path"] = str(p.relative_to(ROOT))
    cfg["_hash"] = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    return cfg

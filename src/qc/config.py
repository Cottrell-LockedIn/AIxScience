"""Config loading plus the small provenance helpers every stage uses (config hash, git sha, paths)."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(path: str | Path = "configs/v1.yaml") -> dict[str, Any]:
    p = (ROOT / path) if not Path(path).is_absolute() else Path(path)
    cfg = yaml.safe_load(p.read_text())
    cfg["_path"] = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    cfg["_hash"] = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    return cfg


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True, cwd=ROOT).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def resolve(path: str | Path) -> Path:
    """Absolute path for a config entry: absolute paths pass through, relative ones hang off ROOT."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def stamp(df, cfg: dict[str, Any]):
    """Add the provenance columns every result file must carry."""
    df = df.copy()
    df["config_hash"] = cfg["_hash"]
    df["git_sha"] = git_sha()
    return df


def provenance(cfg: dict[str, Any]) -> dict[str, str]:
    return {"config_path": cfg["_path"], "config_hash": cfg["_hash"], "git_sha": git_sha()}

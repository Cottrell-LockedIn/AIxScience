"""python -m qc <stage> [--config configs/v1.yaml]

Stages run in the order of docs/FRAMEWORK.md Section 2b. Each stage reads and writes fixed files.
"""
from __future__ import annotations

import importlib
import json

import typer

from qc import config as _config

app = typer.Typer(no_args_is_help=True, add_completion=False)
STAGES = [
    "audit", "tiles", "artefacts", "segment", "kpi", "features",
    "embed", "register", "charging", "stats", "classify", "verdict",
    "robustness", "heldout",
]
PIPELINE_STAGES = [
    "audit", "tiles", "artefacts", "segment", "kpi", "features",
    "embed", "register", "charging",
]


def _run(stage: str, cfg_path: str) -> None:
    cfg = _config.load(cfg_path)
    typer.echo(f"[qc] {stage}  config={cfg['_path']}@{cfg['_hash']}  git={_config.git_sha()}")
    importlib.import_module(f"qc.{stage}").run(cfg)


for _s in (stage for stage in STAGES if stage != "heldout"):
    def _make(stage: str):
        def cmd(config: str = typer.Option("configs/v1.yaml", "--config", "-c")) -> None:
            _run(stage, config)
        cmd.__name__ = stage
        cmd.__doc__ = importlib.import_module(f"qc.{stage}").__doc__.splitlines()[0]
        return cmd
    app.command(name=_s)(_make(_s))


@app.command()
def heldout(
    config: str = typer.Option("configs/v1.yaml", "--config", "-c"),
    input_dir: str | None = typer.Option(None, "--input-dir"),
    out: str | None = typer.Option(None, "--out"),
    dryrun: bool = typer.Option(False, "--dryrun"),
    exploratory: bool = typer.Option(False, "--exploratory"),
) -> None:
    """Run frozen image-level inference on held-out TIFFs."""
    cfg = _config.load(config)
    typer.echo(f"[qc] heldout  config={cfg['_path']}@{cfg['_hash']}  git={_config.git_sha()}")
    importlib.import_module("qc.heldout").run(
        cfg,
        input_dir=input_dir,
        out_path=out,
        dryrun=dryrun,
        exploratory=exploratory,
    )


@app.command(name="pc-profiles")
def pc_profiles(config: str = typer.Option("configs/v1.yaml", "--config", "-c")) -> None:
    """Exploratory embedding PC correlation profiles and tags (output-only, model unchanged)."""
    _run("pc_profiles", config)


@app.command()
def run(config: str = typer.Option("configs/v1.yaml", "--config", "-c")) -> None:
    """Run data preparation, KPI, feature, registration and charging stages."""
    for s in PIPELINE_STAGES:
        _run(s, config)


@app.command()
def info(config: str = typer.Option("configs/v1.yaml", "--config", "-c")) -> None:
    """Print config hash, git sha and stage list."""
    cfg = _config.load(config)
    typer.echo(json.dumps({"config": cfg["_path"], "config_hash": cfg["_hash"], "git": _config.git_sha(),
                           "stages": STAGES}, indent=2))


if __name__ == "__main__":
    app()

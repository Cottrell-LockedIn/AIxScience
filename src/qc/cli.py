"""python -m qc <stage> [--config configs/v1.yaml]

Stages run in the order of docs/FRAMEWORK.md Section 2b. Each stage reads and writes fixed files.
"""
from __future__ import annotations

import importlib
import json

import typer

from qc import config as _config

app = typer.Typer(no_args_is_help=True, add_completion=False)
STAGES = ["audit", "tiles", "artefacts", "segment", "kpi", "features", "stats", "classify",
          "verdict", "robustness", "heldout"]


def _run(stage: str, cfg_path: str) -> None:
    cfg = _config.load(cfg_path)
    typer.echo(f"[qc] {stage}  config={cfg['_path']}@{cfg['_hash']}  git={_config.git_sha()}")
    importlib.import_module(f"qc.{stage}").run(cfg)


for _s in STAGES:
    def _make(stage: str):
        def cmd(config: str = typer.Option("configs/v1.yaml", "--config", "-c")) -> None:
            _run(stage, config)
        cmd.__name__ = stage
        cmd.__doc__ = importlib.import_module(f"qc.{stage}").__doc__.splitlines()[0]
        return cmd
    app.command(name=_s)(_make(_s))


@app.command()
def run(config: str = typer.Option("configs/v1.yaml", "--config", "-c")) -> None:
    """Run all stages S1-S8 in order (not robustness or heldout)."""
    for s in STAGES[:9]:
        _run(s, config)


@app.command()
def validate(features: str = typer.Option(..., "--features", help="image-level feature table (.parquet or .csv)"),
             out: str = typer.Option(None, "--out", help="output dir, default results/validate/<table-name>/"),
             artefacts: str = typer.Option("results/artefacts_per_image.parquet", "--artefacts"),
             images: str = typer.Option("results/audit/images.csv", "--images"),
             sensitivity: str = typer.Option("results/kpi_sensitivity.parquet", "--sensitivity"),
             seed: int = typer.Option(0, "--seed"), n_boot: int = typer.Option(1000, "--n-boot"),
             n_perm: int = typer.Option(10_000, "--n-perm"),
             rf: bool = typer.Option(False, "--rf", help="also fit a random forest in the LOIO/LOGO check"),
             config: str = typer.Option("configs/v1.yaml", "--config", "-c")) -> None:
    """Validation harness for any image-level feature table (stability, confounding, batch tests, LOIO/LOGO)."""
    cfg = _config.load(config)
    typer.echo(f"[qc] validate  config={cfg['_path']}@{cfg['_hash']}  git={_config.git_sha()}")
    importlib.import_module("qc.validate").run(cfg, features, out, artefacts, images, sensitivity, seed, n_boot, n_perm, rf)


@app.command()
def classify(features: str = typer.Option("results/features/features_f01_f11.parquet", "--features", help="image-level feature table"),
             out: str | None = typer.Option(None, "--out"),
             heldout: str | None = typer.Option(None, "--heldout", help="table of new images (sample_id + feature columns) to score with the frozen model"),
             seed: int = typer.Option(0, "--seed"), n_perm: int = typer.Option(200, "--n-perm"),
             rf: bool = typer.Option(False, "--rf", help="also fit a random forest"),
             config: str = typer.Option("configs/v1.yaml", "--config", "-c")) -> None:
    """Batch identification per feature family (LOIO/LOGO + permutation null), drivers, OOD screen vs each batch, held-out path (results/classify/)."""
    cfg = _config.load(config)
    typer.echo(f"[qc] classify  config={cfg['_path']}@{cfg['_hash']}  git={_config.git_sha()}")
    importlib.import_module("qc.classify").run(cfg, features, out, heldout=heldout, seed=seed, n_perm=n_perm, rf=rf)


@app.command()
def register(config: str = typer.Option("configs/v1.yaml", "--config", "-c")) -> None:
    """Check BSE / Inlens / ETD-SE pixel registration per image (results/registration/)."""
    _run("registration", config)


@app.command()
def charging(config: str = typer.Option("configs/v1.yaml", "--config", "-c")) -> None:
    """Flag class-2 BSE pixels that are also bright in both SE detectors (results/charging/); registered images only."""
    _run("charging", config)


@app.command()
def info(config: str = typer.Option("configs/v1.yaml", "--config", "-c")) -> None:
    """Print config hash, git sha and stage list."""
    cfg = _config.load(config)
    typer.echo(json.dumps({"config": cfg["_path"], "config_hash": cfg["_hash"], "git": _config.git_sha(),
                           "stages": STAGES}, indent=2))


if __name__ == "__main__":
    app()

"""Modal fan-out for image-level classify tables.

    modal run modal_app.py --n-perm 1000 --tables all
"""
from __future__ import annotations

import csv
import hashlib
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import modal

app = modal.App("aixscience-qc")

# versions pinned to the local .venv so Modal and local runs give identical numbers
classify_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "numpy==2.4.6",
        "pandas==3.0.6",
        "pyarrow==25.0.1",
        "scikit-learn==1.9.1",
        "scipy==1.17.1",
        "pyyaml==6.0.3",
        "typer==0.27.2",
        "tabulate==0.10.0",
        "joblib==1.6.0",
        "threadpoolctl==3.7.0",
    )
    .add_local_dir("src", remote_path="/root/src")
    .add_local_dir("configs", remote_path="/root/configs")
)

CLASSIFY_INPUTS = (
    "results/features/features_f01_f11.parquet",
    "results/kpi_per_image.parquet",
    "results/embeddings/dinov2_vits14_bse_by_image.parquet",
    "results/embeddings/dinov2_vits14_inlens_by_image.parquet",
    "results/embeddings/dinov2_vits14_setype_by_image.parquet",
    "results/artefacts_per_image.parquet",
    "results/audit/images.csv",
)
for input_path in CLASSIFY_INPUTS:
    classify_image = classify_image.add_local_file(input_path, f"/root/{input_path}")


@app.function(image=classify_image, cpu=16, timeout=60 * 60, max_containers=10)
def classify_table(table: str, table_family: str, n_perm: int, seed: int, git_sha: str,
                   config_hash: str) -> dict[str, bytes]:
    import sys
    import tempfile

    sys.path.insert(0, "/root/src")
    from qc import classify
    from qc import config as _config

    cfg = _config.load("configs/v1.yaml")
    cfg["_git_sha"] = git_sha
    cfg["_hash"] = config_hash
    with tempfile.TemporaryDirectory(prefix="classify-") as temp_dir:
        start = time.perf_counter()
        output_dir = classify.run(
            cfg,
            features=table,
            out=temp_dir,
            seed=seed,
            n_perm=n_perm,
            table_family=table_family,
            n_jobs=-1,
        )
        elapsed = time.perf_counter() - start
        outputs = {path.name: path.read_bytes() for path in output_dir.iterdir() if path.is_file()}
    outputs["__modal_seconds__"] = repr(elapsed).encode()
    return outputs


TABLES = {
    "features_f01_f11": ("results/features/features_f01_f11.parquet", "material"),
    "kpi_per_image": ("results/kpi_per_image.parquet", "material"),
    "dinov2_vits14_bse_by_image": ("results/embeddings/dinov2_vits14_bse_by_image.parquet", "embedding"),
    "dinov2_vits14_inlens_by_image": (
        "results/embeddings/dinov2_vits14_inlens_by_image.parquet",
        "embedding",
    ),
    "dinov2_vits14_setype_by_image": (
        "results/embeddings/dinov2_vits14_setype_by_image.parquet",
        "embedding",
    ),
}


@app.local_entrypoint()
def main(n_perm: int = 200, tables: str = "all", seed: int = 0) -> None:
    root = Path(__file__).resolve().parent
    selected = list(TABLES) if tables.strip().lower() == "all" else [name.strip() for name in tables.split(",")]
    unknown = sorted(set(selected) - TABLES.keys())
    if unknown:
        raise ValueError(f"unknown classify table(s): {', '.join(unknown)}; choose from {', '.join(TABLES)} or all")

    config_path = root / "configs/v1.yaml"
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()[:12]
    git_sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True, cwd=root).strip()
    arguments = [
        (TABLES[name][0], TABLES[name][1], n_perm, seed, git_sha, config_hash)
        for name in selected
    ]

    start = time.perf_counter()
    results = list(classify_table.starmap(arguments))
    total_seconds = time.perf_counter() - start
    classify_root = root / "results/classify"
    classify_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    runs_path = classify_root / "MODAL_RUNS.csv"
    write_header = not runs_path.exists()
    with runs_path.open("a", newline="") as runs_file:
        writer = csv.DictWriter(
            runs_file,
            fieldnames=("timestamp", "git_sha", "n_perm", "table", "seconds", "container_count"),
        )
        if write_header:
            writer.writeheader()
        for name, output in zip(selected, results):
            table_seconds = float(output.pop("__modal_seconds__").decode())
            output_dir = classify_root / name
            output_dir.mkdir(parents=True, exist_ok=True)
            for filename, content in output.items():
                (output_dir / filename).write_bytes(content)
            writer.writerow(
                {
                    "timestamp": timestamp,
                    "git_sha": git_sha,
                    "n_perm": n_perm,
                    "table": name,
                    "seconds": f"{table_seconds:.3f}",
                    "container_count": len(selected),
                }
            )
            print(f"{name}: {table_seconds:.1f}s -> {output_dir.relative_to(root)}")
    print(f"Modal fan-out: {total_seconds:.1f}s wall time, {len(selected)} table containers")

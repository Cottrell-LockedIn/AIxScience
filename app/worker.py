"""Worker entry point. It keeps exploratory analysis outside the web process."""
from __future__ import annotations

import sys
import traceback

from qc import classify, config, heldout

from app import jobs


def main(run_id: str) -> None:
    state = jobs.load_run(run_id)
    if state is None:
        raise SystemExit(f"Unknown run: {run_id}")
    upload = jobs.upload_path(str(state["uploadId"]))
    output = jobs.run_path(run_id) / "result.json"
    try:
        def stage(name: str) -> None:
            if jobs.is_cancelled(run_id):
                raise SystemExit("Cancelled by user.")
            jobs.update_run(run_id, state="running", stage=name)

        stage("Checking files")
        cfg = config.load("configs/v1.yaml")
        # These wrappers observe real engine boundaries without modifying qc/*.
        original_extract = heldout._extract_features
        original_embed = heldout._embedding_vectors
        original_predict = classify.predict_one

        def extract_with_stage(*args, **kwargs):
            stage("Measuring image structure")
            return original_extract(*args, **kwargs)

        def embed_with_stage(*args, **kwargs):
            stage("Reading image patterns (Modal GPU or CPU fallback)")
            return original_embed(*args, **kwargs)

        def predict_with_stage(*args, **kwargs):
            stage("Comparing with known batches")
            return original_predict(*args, **kwargs)

        heldout._extract_features = extract_with_stage
        heldout._embedding_vectors = embed_with_stage
        classify.predict_one = predict_with_stage
        # `heldout.run` owns its actual preprocessing, segmentation, embedding,
        # comparison and exploratory artifact export. The isolated output path
        # ensures it cannot overwrite a canonical scientific result.
        heldout.run(cfg, input_dir=upload, out_path=output, exploratory=True)
        stage("Preparing review")
        if not jobs.is_cancelled(run_id):
            jobs.update_run(run_id, state="completed", stage="Complete", resultPath=str(output))
    except BaseException as exc:  # worker status must survive engine failures
        current = jobs.load_run(run_id) or {}
        if current.get("state") == "cancelled":
            return
        message = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        jobs.update_run(run_id, state="failed", stage="Failed", error=message[:1200])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m app.worker <run-id>")
    main(sys.argv[1])

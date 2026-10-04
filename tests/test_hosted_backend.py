"""Static contracts for the deploy adapter; no Modal account is required."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hosted_adapter_keeps_core_pipeline_unmodified():
    source = (ROOT / "modal_web.py").read_text(encoding="utf-8")
    assert "heldout._embedding_vectors = _hosted_gpu_embeddings" in source
    assert "heldout._append_modal_run = _append_hosted_modal_run" in source
    assert "TRACKED_BUNDLE_FILES = _tracked_bundle_files()" in source
    assert "allow_local_fallback" in source
    assert "torch.cuda.is_available()" in source


def test_hosted_adapter_requires_gateway_token_and_persistent_state():
    source = (ROOT / "modal_web.py").read_text(encoding="utf-8")
    assert 'required_keys=["COTTRELL_API_TOKEN"]' in source
    assert 'request.headers.get("x-cottrell-token", "")' in source
    assert "hmac.compare_digest" in source
    assert "state_volume.commit()" in source
    assert "run_exploratory.spawn(run_id)" in source
    assert "modal.FunctionCall.from_id(call_id).cancel(terminate_containers=True)" in source
    assert "modal.FunctionCall.from_id(call_id).get(timeout=0)" in source
    assert "_persist_call_control(run_id, str(call.object_id))" in source
    assert "refreshed = jobs.load_run(run_id)" in source
    assert "def _persist_cancel_control" in source
    assert "if _cancel_requested(current_run_id):" in source
    assert "heldout._extract_features = base_extract_features" in source
    assert "classify.predict_one = base_predict_one" in source
    assert "@modal.concurrent(max_inputs=1)" in source
    assert 'gpu="L4"' in source
    assert 'request.url.path.startswith("/api/uploads")' in source
    assert "def refresh_worker_state()" in source
    assert "state_volume.commit()\n        state_volume.reload()" in source


def test_hosted_bundle_excludes_untracked_runtime_files_and_bootstraps_verified_weights():
    source = (ROOT / "modal_web.py").read_text(encoding="utf-8")
    assert '"git", "ls-files", "-z"' in source
    assert "ignore=_ignore_untracked_bundle_path" in source
    assert 'weights_volume = modal.Volume.from_name(WEIGHTS_VOLUME_NAME, create_if_missing=True)' in source
    assert "embed.ensure_weights(weights_cfg, weights_path)" in source
    assert 'qc_config.git_sha = lambda: os.environ.get("COTTRELL_BUNDLE_GIT_SHA", "unknown")' in source
    assert 'cost_source="https://modal.com/pricing; L4=$0.000222/GPU-s; embedding wall time only"' in source


def test_hosted_docs_do_not_claim_a_deployment():
    text = (ROOT / "docs" / "HOSTED_BACKEND.md").read_text(encoding="utf-8")
    assert "No deployment was performed merely by adding this adapter." in text
    assert "X-Cottrell-Token" in text

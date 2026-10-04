"""Local job-state checks; they do not start the scientific engine."""
from __future__ import annotations

from app import jobs


def test_cancel_is_terminal_and_late_worker_update_cannot_revive(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "STATE_ROOT", tmp_path)
    monkeypatch.setattr(jobs, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(jobs, "UPLOADS", tmp_path / "uploads")
    run = jobs.create_run("a" * 32, [], {})

    cancelled = jobs.cancel(run["id"])
    late = jobs.update_run(run["id"], state="running", stage="Comparing with known batches")

    assert cancelled["state"] == "cancelled"
    assert late["state"] == "cancelled"
    assert late["stage"] == "Cancelled"

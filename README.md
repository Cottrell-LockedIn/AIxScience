# AIxScience Track 4: batch-vs-baseline microstructure QC

Trustworthy, interpretable, uncertainty-aware QC for incoming electrode material from FIB-SEM cross-sections. Built during the AI x Science Hackathon (Track 4, Polaron).

Status: scaffold. Nothing below `results/` is real yet.

## Start here

- `AGENTS.md`: rules for humans and agents.
- `docs/FRAMEWORK.md`: plan, stage table, hard rules, parallel-agent plan, robustness protocol. Section 00 first.
- `docs/READ/Dataset First Look.md`: what the data is.

## Run

```bash
uv venv && source .venv/bin/activate && uv pip install -e .
python scripts/download_drive.py --channel BSE      # ~620 MB; omit --channel for everything (~1.7 GB)
python -m qc info
python -m qc run                                    # S1..S8 once implemented
pytest
streamlit run app/streamlit_app.py
```

## Layout

See `docs/FRAMEWORK.md` Section 3. Stages live in `src/qc/<stage>.py`; each docstring states what it reads, writes and who owns it.

## Attribution and licences

Our code: MIT (see `LICENSE`). Third-party: DINOv2 (Apache-2.0), scikit-image (BSD), ImageRep (BSD-3-Clause, Dahari et al., Advanced Science), Modal SDK. Method citations: `docs/READ/Method Evidence for Layers.md`. Data: provided by Polaron for the hackathon; not redistributed here.

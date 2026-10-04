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

Our code: MIT (see `LICENSE`). Third-party: DINOv2 repository code (Apache-2.0), scikit-image (BSD), ImageRep (BSD-3-Clause, Dahari et al., Advanced Science), Modal SDK. The pinned DINOv2 README does not separately state the license for the selected `dinov2_vits14_pretrain.pth` checkpoint; its FAIR Noncommercial Research License statement refers to XRay-DINO. See [`docs/LICENSES_DINOV2.md`](docs/LICENSES_DINOV2.md). Data: provided by Polaron for the hackathon; not redistributed here.

Methods: image area fractions use Delesse's principle; particle sizing uses ASTM E1245-style border exclusion; the count frame follows Gundersen (1977); spatial regularity uses Clark and Evans (1954) with Donnelly's (1978) edge correction; local thickness follows Hildebrand and Rueegsegger (1997). Translation registration uses phase correlation (Guizar-Sicairos et al., 2008, [DOI:10.1364/OL.33.000156](https://doi.org/10.1364/OL.33.000156)); rotation and scale use Fourier-Mellin log-polar registration (Reddy and Chatterji, 1996, [DOI:10.1109/83.506761](https://doi.org/10.1109/83.506761)). Frozen image embeddings use DINOv2 (Oquab et al., 2023, [arXiv:2304.07193](https://arxiv.org/abs/2304.07193)). See [`docs/READ/Method Evidence for Layers.md`](docs/READ/Method%20Evidence%20for%20Layers.md) for evidence and caveats.

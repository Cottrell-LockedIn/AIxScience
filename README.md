# AIxScience Track 4: batch-vs-baseline microstructure QC

Trustworthy, interpretable, uncertainty-aware QC for incoming electrode material from FIB-SEM cross-sections. Built during the AI x Science Hackathon (Track 4, Polaron).

Status: scaffold. Nothing below `results/` is real yet.

## Start here

- `AGENTS.md`: rules for humans and agents.
- `docs/FRAMEWORK.md`: plan, stage table, hard rules, parallel-agent plan, robustness protocol. Section 00 first.
- `docs/READ/Dataset First Look.md`: what the data is.

## Run

```bash
uv venv --python 3.11 && source .venv/bin/activate && uv pip install -e .
python scripts/download_drive.py --channel BSE      # ~620 MB; omit --channel for everything (~1.7 GB)
python -m qc info
qc run
modal run modal_app.py::main --task kpi
modal run modal_app.py::main --task features
modal run modal_app.py::main --task embed
qc stats
qc verdict
python -m pytest -q
streamlit run app/streamlit_app.py
```

## Regenerate Phase B

From a fresh Python 3.11 environment with the repository installed and `data/raw` available,
the verified regeneration sequence is:

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e .
qc run
modal run modal_app.py::main --task kpi
modal run modal_app.py::main --task features
modal run modal_app.py::main --task embed
qc stats
qc verdict
```

The Modal commands select `main`'s local entrypoint tasks; `kpi`, `features`, and `embed`
run KPI sensitivity, feature sensitivity, and frozen DINOv2 embeddings, respectively. The
`embed` task performs the one-image local/Modal parity and repeated-run checks before the
full embedding job.

Measured fresh-clone wall times:

| Stage | Wall time |
|---|---:|
| `qc run` audit | 6.93 s |
| `qc run` tiles | 14.25 s |
| `qc run` artefacts | 58.55 s |
| `qc run` segment | 78.97 s |
| `qc run` KPI | 144.08 s |
| `qc run` features | 545.24 s |
| `qc run` CPU embeddings | 657.99 s |
| `qc run` register | 104.29 s |
| `qc run` charging | 29.89 s |
| **`qc run` total** | **1,641.33 s** |
| Modal KPI sensitivity command | 98.35 s wall; 92.53 s Modal-reported |
| Modal feature sensitivity command | 150.47 s wall; 146.50 s Modal-reported |
| Modal embeddings command | 85.16 s wall; 56.21 s Modal-reported |
| `qc stats` | 100.44 s |
| `qc verdict` | 1.51 s |

The local CPU `embed` stage took about 658 s, compared with about 56 s for the Modal L4
full embedding run. Local `features` took about 545 s, compared with about 146 s for the
Modal feature-sensitivity run. The measured Modal cost estimates were $0.054036 for KPI
sensitivity, $0.020304 for feature labels, $0.060973 for feature images, and $0.119069 for
full embeddings ($0.254382 combined); these are estimates from Modal's published pricing,
not billed totals. The timed `qc run` stages were measured with a wrapper around the same
CLI stage dispatch path; Modal command wall times include startup/CLI overhead. The Modal
reported times above are remote execution timings.

## Phase C: classify and held-out

After Phase B outputs and the frozen classifier artifacts are available, fit and check the
image-level model, then process held-out TIFFs once from the tagged `v1-frozen` revision:

```bash
qc classify
python -m qc heldout --input-dir data/heldout --out results/v1/heldout.json
```

For a non-scoring training-image dry-run, specify a separate output path. Exploratory runs
use an automatically timestamped path under `results/v1/exploratory/`:

```bash
python -m qc heldout --input-dir /path/to/copied/images \
  --out results/v1/heldout_dryrun.json --dryrun
python -m qc heldout --input-dir /path/to/images \
  --exploratory
```

Held-out tiles are embedded on Modal L4; a local CPU fallback is recorded if Modal fails.
Each image is the independent observation, and held-out inference does not write tiles to
`data/tiles` or overwrite classifier training outputs.

## Layout

See `docs/FRAMEWORK.md` Section 3. Stages live in `src/qc/<stage>.py`; each docstring states what it reads, writes and who owns it.

## Attribution and licences

Our code: MIT (see `LICENSE`). Third-party: DINOv2 code and `dinov2_vits14` model weights (Apache-2.0), scikit-image (BSD), ImageRep (BSD-3-Clause, Dahari et al., Advanced Science), Modal SDK. XRay-DINO and Cell-DINO are separately licensed models and are not used here. See [`docs/LICENSES_DINOV2.md`](docs/LICENSES_DINOV2.md). Data: provided by Polaron for the hackathon; not redistributed here.

Methods: image area fractions use Delesse's principle; particle sizing uses ASTM E1245-style border exclusion; the count frame follows Gundersen (1977); spatial regularity uses Clark and Evans (1954) with Donnelly's (1978) edge correction; local thickness follows Hildebrand and Rueegsegger (1997). Translation registration uses phase correlation (Guizar-Sicairos et al., 2008, [DOI:10.1364/OL.33.000156](https://doi.org/10.1364/OL.33.000156)); rotation and scale use Fourier-Mellin log-polar registration (Reddy and Chatterji, 1996, [DOI:10.1109/83.506761](https://doi.org/10.1109/83.506761)). Frozen image embeddings use DINOv2 (Oquab et al., 2023, [arXiv:2304.07193](https://arxiv.org/abs/2304.07193)). See [`docs/READ/Method Evidence for Layers.md`](docs/READ/Method%20Evidence%20for%20Layers.md) for evidence and caveats.

"""One-screen QC console (Feature 4). Owner: P4. Reads results/v1/*.json only; never computes.

    streamlit run app/streamlit_app.py
"""
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "v1"

st.set_page_config(page_title="Electrode batch QC", layout="wide")
st.title("Electrode batch QC: batch vs reference")
files = sorted(RESULTS.glob("*.json"))
if not files:
    st.info("No results yet. Run `python -m qc run` to produce results/v1/*.json.")
else:
    pick = st.selectbox("Subject", [f.stem for f in files])
    st.json(json.loads((RESULTS / f"{pick}.json").read_text()))

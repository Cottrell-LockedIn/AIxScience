"""Reality-check figures (handoff brief step 5). No verdicts, no chemistry names.

Reads:  results/kpi_per_image.parquet, results/kpi_sensitivity.parquet, results/artefacts_per_image.parquet
Writes: results/audit/reality_check_fractions.png, results/audit/reality_check_artefacts.png
Prints a numeric summary (batch medians, within-batch IQR, separation ratio) to help write REALITY_CHECK.md.

Usage: python scripts/reality_check.py [configs/v1.yaml]
"""
from __future__ import annotations

import sys

import matplotlib
import numpy as np
import pandas as pd

from qc import config as _config

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RES = _config.ROOT / "results"
FRACS = ["frac_c0", "frac_c1", "frac_c2"]
NAMES = {"frac_c0": "class 0 (dark)", "frac_c1": "class 1 (mid)", "frac_c2": "class 2 (bright)"}


def order_images(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["batch", "sample_id"]).reset_index(drop=True)
    df["xpos"] = np.arange(len(df))
    return df


def separation_summary(df: pd.DataFrame, metric: str) -> str:
    g = df.groupby("batch")[metric]
    med, q1, q3 = g.median(), g.quantile(0.25), g.quantile(0.75)
    iqr = (q3 - q1).median()
    spread = med.max() - med.min()
    ratio = spread / iqr if iqr > 0 else float("inf")
    meds = ", ".join(f"{b}={m:.4g} (n={g.size()[b]})" for b, m in med.items())
    return f"{metric}: batch medians {meds}; median within-batch IQR {iqr:.3g}; max median gap / IQR = {ratio:.2f}"


def fig_fractions(kpi: pd.DataFrame, sens: pd.DataFrame, out) -> None:
    kpi = order_images(kpi)
    s = sens[sens["level"] == "image"].pivot_table(index=["batch", "sample_id"], columns="scale", values=FRACS)
    batches = sorted(kpi["batch"].unique())
    colors = {b: f"C{i}" for i, b in enumerate(batches)}
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    for ax, f in zip(axes, FRACS):
        for b in batches:
            d = kpi[kpi["batch"] == b]
            lo = np.array([s.loc[(b, sid), (f, 0.9)] for sid in d["sample_id"]])
            hi = np.array([s.loc[(b, sid), (f, 1.1)] for sid in d["sample_id"]])
            y = d[f].to_numpy()
            yerr = np.vstack([np.clip(y - np.minimum(lo, hi), 0, None), np.clip(np.maximum(lo, hi) - y, 0, None)])
            ax.errorbar(d["xpos"], y, yerr=yerr, fmt="o", color=colors[b], ms=5, capsize=2, lw=1,
                        label=f"{b} (n={len(d)} images)")
            ax.hlines(np.median(y), d["xpos"].min() - 0.4, d["xpos"].max() + 0.4, color=colors[b], lw=1.5, ls="--")
        ax.set_ylabel(f"{NAMES[f]}\narea fraction")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8, ncol=3)
    axes[-1].set_xticks(kpi["xpos"], kpi["sample_id"], rotation=90, fontsize=7)
    axes[-1].set_xlabel("image (8-char sample id), grouped by batch")
    fig.suptitle("Per-image class fractions on BSE (mean over tiles); dashed = batch median; "
                 "error bars = fractions with multi-Otsu thresholds scaled by 0.9 / 1.1", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def fig_artefacts(art: pd.DataFrame, out) -> None:
    panels = [("curtaining_score", "BSE"), ("edge_charging", "Inlens")]
    batches = sorted(art["batch"].unique())
    colors = {b: f"C{i}" for i, b in enumerate(batches)}
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, (metric, ch) in zip(axes, panels):
        d = art[art["channel"] == ch]
        for i, b in enumerate(batches):
            v = d.loc[d["batch"] == b, metric].to_numpy()
            ax.scatter(i + rng.uniform(-0.18, 0.18, len(v)), v, color=colors[b], s=26, alpha=0.85,
                       label=f"{b} (n={len(v)})")
            if len(v):
                ax.hlines(np.median(v), i - 0.3, i + 0.3, color=colors[b], lw=2)
        ax.set_xticks(range(len(batches)), batches)
        ax.set_title(f"{metric} on {ch} (per image, mean over tiles)", fontsize=10)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("Acquisition artefact covariates by batch; line = batch median; n = images", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def main(cfg_path: str = "configs/v1.yaml") -> None:
    kpi = pd.read_parquet(RES / "kpi_per_image.parquet")
    sens = pd.read_parquet(RES / "kpi_sensitivity.parquet")
    art = pd.read_parquet(RES / "artefacts_per_image.parquet")
    out = RES / "audit"
    fig_fractions(kpi, sens, out / "reality_check_fractions.png")
    fig_artefacts(art, out / "reality_check_artefacts.png")
    print("== fractions (per image) ==")
    for f in FRACS:
        print(separation_summary(kpi, f))
    s_img = sens[sens["level"] == "image"]
    for f in FRACS:
        p = s_img.pivot_table(index="sample_id", columns="scale", values=f)
        print(f"{f}: median |delta| for threshold x0.9 = {np.abs(p[0.9]-p[1.0]).median():.4f}, "
              f"x1.1 = {np.abs(p[1.1]-p[1.0]).median():.4f}")
    print("== artefacts (per image) ==")
    for metric, ch in [("curtaining_score", "BSE"), ("curtaining_score", "Inlens"), ("hstripe_score", "BSE"),
                       ("edge_charging", "Inlens"), ("noise_sigma", "BSE"), ("sharpness", "BSE")]:
        print(ch, separation_summary(art[art["channel"] == ch], metric))


if __name__ == "__main__":
    main(*sys.argv[1:])

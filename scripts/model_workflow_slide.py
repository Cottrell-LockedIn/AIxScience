"""Slide version of the model workflow: one 16:9 figure, six steps, one line of numbers.

Numbers are read from results/v1/loio_summary.json and results/v1/accuracy_tab/metrics.json.
Writes docs/Log/assets/model_workflow_slide.{png,svg}.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/Log/assets/model_workflow_slide"

loio = json.loads((ROOT / "results/v1/loio_summary.json").read_text())
met = json.loads((ROOT / "results/v1/accuracy_tab/metrics.json").read_text())

STEPS = [
    ("1  Input", "FIB-SEM TIFF\nBSE (+ other detectors)\nno user parameters", "#5b6b7f", "#eef1f6"),
    ("2  Tile", "1024 px tiles\nimage = unit of analysis", "#5b6b7f", "#eef1f6"),
    ("3  Three views", "Segment -> 11 measures\nDINOv2 fingerprint\nAcquisition flags", "#2f6db3", "#e8f0fb"),
    ("4  Classify", "One logistic regression\nfitted on 31 images\nno network training", "#2e8b57", "#e9f6ee"),
    ("5  Rules", "Bet + confidence tier\nOutside Batch_3 band?\nTop-3 drivers", "#c77d00", "#fdf3e1"),
    ("6  Output", "Traceable JSON\nmask overlay, provenance\nexpert routing", "#b3382f", "#fbe9e7"),
]


def main() -> None:
    fig = plt.figure(figsize=(16, 9), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(0.04, 0.93, "From one FIB-SEM image to a traceable batch verdict",
            fontsize=30, fontweight="bold", color="#202024", va="top")
    ax.text(0.04, 0.845, "Frozen recipe (tag v1-frozen). Classical segmentation + frozen DINOv2 features + one small classifier.",
            fontsize=16, color="#666670", va="top")

    n = len(STEPS)
    x0, x1, gap = 0.04, 0.96, 0.018
    w = (x1 - x0 - gap * (n - 1)) / n
    y, h = 0.44, 0.33
    for i, (title, body, edge, face) in enumerate(STEPS):
        x = x0 + i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.02",
                                    fc=face, ec=edge, lw=2.5))
        ax.text(x + w / 2, y + h - 0.035, title, ha="center", va="top", fontsize=19,
                fontweight="bold", color=edge)
        ax.text(x + w / 2, y + h / 2 - 0.03, body, ha="center", va="center", fontsize=12.5,
                color="#202024", linespacing=1.5)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((x + w + 0.002, y + h / 2), (x + w + gap - 0.002, y + h / 2),
                                         arrowstyle="-|>", mutation_scale=22, lw=2.2, color="#5b6b7f",
                                         shrinkA=0, shrinkB=0))

    # numbers band
    acc = loio["loio_accuracy_str"]
    lo, hi = [round(v * 100) for v in loio["wilson95"]]
    ref = met["reference_vs_rest"]["accuracy"]["str"]
    b3 = loio["precision_by_pred_batch"]["Batch_3"]
    high = loio["accuracy_by_tier"]["high"]
    held = met["heldout"]["accuracy"]["str"]
    score = met["heldout"]["judging_score"]["str"]
    p = loio["permutation_p"]

    by, bh = 0.12, 0.26
    ax.add_patch(FancyBboxPatch((0.04, by), 0.92, bh, boxstyle="round,pad=0,rounding_size=0.02",
                                fc="#f6f6f2", ec="#9a9a9a", lw=1.8, ls="--"))
    ax.text(0.06, by + bh - 0.03, "Validated honestly: leave-one-image-out on 31 images, frozen before the held-out images were opened",
            fontsize=15, fontweight="bold", color="#3b3b45", va="top")

    stats = [
        (f"{ref}", "Batch_3 vs rest", f"baseline detection, 84 %"),
        (f"{b3}", "Batch_3 bets right", "precision in validation"),
        (f"{acc}", "3-way accuracy", f"95 % CI {lo}-{hi} %, perm. p = {p:.3f}"),
        (f"{high}", "high-tier bets right", "confidence tier is a rule"),
        (f"{held}", "held-out images", f"confidence score {score}"),
    ]
    sx0, sw = 0.06, 0.88 / len(stats)
    for i, (big, label, small) in enumerate(stats):
        cx = sx0 + sw * (i + 0.5)
        ax.text(cx, by + 0.135, big, ha="center", va="center", fontsize=30, fontweight="bold", color="#202024")
        ax.text(cx, by + 0.075, label, ha="center", va="center", fontsize=13.5, color="#202024")
        ax.text(cx, by + 0.04, small, ha="center", va="center", fontsize=11, color="#666670")

    ax.text(0.04, 0.055, "Limits we state: Batch_1 vs Batch_2 near chance; embedding signal may reflect imaging conditions, not material\n"
            "(cannot be separated with 31 images); phases as stated by Polaron, not image-verified; lengths in px.",
            fontsize=11.5, color="#666670", va="top", linespacing=1.4)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT.with_suffix(".png"), dpi=200, facecolor="white")
    fig.savefig(OUT.with_suffix(".svg"), facecolor="white")
    print(OUT.with_suffix(".png"))


if __name__ == "__main__":
    main()

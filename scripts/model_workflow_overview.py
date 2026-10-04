"""Draw the v1 model workflow overview (docs/Log/assets/model_workflow_overview.{png,svg}).

Static figure for the pitch Q&A; numbers are copied from results/v1/loio_summary.json,
results/v1/heldout.json and docs/HANDOFF_MODEL_CAPABILITIES.md. Run: python scripts/model_workflow_overview.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parents[1] / "docs" / "Log" / "assets"

C = {
    "input": ("#eef1f5", "#5b6b7f"),
    "tile": ("#eef1f5", "#5b6b7f"),
    "seg": ("#e3f0fb", "#1f77b4"),
    "emb": ("#efe6f7", "#7040dc"),
    "cov": ("#f1f1ee", "#8a8a8a"),
    "clf": ("#e5f4e8", "#2e8b57"),
    "rules": ("#fdf1dc", "#c77d00"),
    "out": ("#fde9e3", "#c0392b"),
    "band": ("#f7f7f4", "#9a9a94"),
}


def box(ax, x, y, w, h, kind, title, lines, title_size=12.5, body_size=9.6, tag=None, body_gap=0.075):
    face, edge = C[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.015",
                                fc=face, ec=edge, lw=1.8, zorder=2))
    ax.text(x + 0.012, y + h - 0.02, title, ha="left", va="top", fontsize=title_size,
            fontweight="bold", color=edge, zorder=3)
    ax.text(x + 0.012, y + h - body_gap, "\n".join(lines), ha="left", va="top", fontsize=body_size,
            color="#202024", linespacing=1.35, zorder=3)
    if tag:
        ax.text(x + w - 0.012, y + 0.012, tag, ha="right", va="bottom", fontsize=8.2,
                style="italic", color=edge, zorder=3)


def arrow(ax, p, q, color="#5b6b7f", lw=1.8, style="-|>"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=16, lw=lw, color=color,
                                 connectionstyle="arc3,rad=0.0", zorder=4, shrinkA=2, shrinkB=2))


def main() -> None:
    fig = plt.figure(figsize=(20, 12), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    fig.text(0.03, 0.965, "AIxScience v1 model: from one FIB-SEM image to a traceable batch verdict",
             fontsize=20, fontweight="bold", color="#202024", va="top")
    fig.text(0.03, 0.925, "Frozen recipe (git tag v1-frozen, config hash 45629944e398). No neural-network training: unsupervised segmentation "
             "+ frozen DINOv2 features + one logistic regression on 31 training images.\n"
             "Unit of analysis = the whole image (n = 31: Batch_1 7, Batch_2 7, Batch_3 17 = supplier baseline); tiles are never independent samples.",
             fontsize=11.5, color="#666670", va="top", linespacing=1.4)

    # ---- row geometry
    top, h = 0.455, 0.43           # main row boxes
    # column x positions and widths
    x_in, w_in = 0.03, 0.105
    x_tile, w_tile = 0.148, 0.095
    x_br, w_br = 0.258, 0.315      # three stacked branch boxes
    x_clf, w_clf = 0.588, 0.12
    x_rul, w_rul = 0.722, 0.125
    x_out, w_out = 0.861, 0.114

    box(ax, x_in, top, w_in, h, "input", "1  Input",
        ["FIB-SEM TIFF, one file per",
         "detector channel:",
         "  BSE  (required)",
         "  Inlens / ETD / SE (optional)",
         "",
         "~7000 x 1700-2300 px, uint8",
         "nominal 25 nm/px (unconfirmed",
         "-> all lengths stay in px)",
         "",
         "SHA-256 of every file logged.",
         "8 px border crop."],
        tag="no user parameters")

    box(ax, x_tile, top, w_tile, h, "tile", "2  Tile",
        ["1024 px tiles,",
         "512 px stride,",
         "full tiles only",
         "(edge-anchored, 100 %",
         "coverage).",
         "",
         "~40-50 tiles / image.",
         "",
         "Tiles are internal",
         "pseudo-replicates,",
         "never samples."])

    # three branch boxes stacked
    bh = (h - 0.03) / 3
    y3 = top
    y2 = top + bh + 0.015
    y1 = top + 2 * bh + 0.03
    box(ax, x_br, y1, w_br, bh, "seg", "3a  Segment + measure  (classical, no training)",
        ["BSE tile -> median 5 px -> 3-class multi-Otsu -> drop objects < 20 px -> stitch into",
         "one image mask: 0 = void, 1 = graphite, 2 = silicon (stated by Polaron, not image-verified).",
         "11 physical measurements F01-F11 from the mask: void fraction, Si particle size / count /",
         "clustering / solidity, pore thickness, void anisotropy, patchiness, Si-void contact.",
         "Mask + colour overlay PNG saved so a scientist can see what was measured."],
        title_size=11, body_size=8.6, body_gap=0.042)
    box(ax, x_br, y2, w_br, bh, "emb", "3b  Embed  (frozen DINOv2 ViT-S/14, Apache-2.0)",
        ["Each BSE tile -> 384-d mean-pooled patch vector -> averaged per image (no fine-tuning).",
         "Runs on Modal L4 GPU (~18 s, ~USD 0.001 for 3 images); CPU fallback for exploratory runs.",
         "Pinned hub commit + SHA-256 weights check. PCA(29) fitted on training images only.",
         "The same vector feeds the out-of-baseline distance check in step 5."],
        title_size=11, body_size=8.6, body_gap=0.042)
    box(ax, x_br, y3, w_br, bh, "cov", "3c  Acquisition covariates  (reported, NOT model inputs)",
        ["8 per image: BSE noise sigma, sharpness, curtaining score, horizontal-stripe score,",
         "edge charging (BSE, Inlens), image height, nm/px tag.",
         "Each compared with the training 5th-95th percentile -> 'acquisition drift suspected'.",
         "Makes Polaron's 'artefact vs material' question visible instead of hiding it."],
        title_size=11, body_size=8.6, body_gap=0.042)

    box(ax, x_clf, top, w_clf, h, "clf", "4  Classify",
        ["StandardScaler(F01-F11)",
         "  (+)  PCA(29) of embedding",
         "-> LogisticRegression",
         "   L2, C = 1, class_weight =",
         "   balanced, multinomial,",
         "   seed 0",
         "",
         "Fitted on the 31 training",
         "images (7 / 7 / 17).",
         "No pickle: every run refits",
         "and checks coefficients",
         "against final_model.csv",
         "(diff 1e-16)."],
        tag="the only fitted object")

    box(ax, x_rul, top, w_rul, h, "rules", "5  Pre-registered rules",
        ["Bet = argmax probability",
         "  (always one of B1/B2/B3)",
         "Tier: high if p >= 0.75 and",
         "  perm p < 0.05 and within",
         "  Batch_3 bounds; else low",
         "Drivers: top-3 coef x input",
         "Out-of-baseline: energy",
         "  distance of embedding to",
         "  Batch_3 vs its own 95/99 %",
         "  band -> within / investigate",
         "  / outside (caps tier at low)",
         "Routing: materials expert /",
         "  microscopy team / none"],
        body_size=9.0)

    box(ax, x_out, top, w_out, h, "out", "6  Output per image",
        ["JSON (schema-validated):",
         " - predicted batch, P(B1/B2/B3),",
         "   confidence tier",
         " - LOIO track record for",
         "   that kind of bet",
         " - top-3 drivers (physical",
         "   or embedding PC + its tag)",
         " - 11 measurements vs",
         "   training ranges",
         " - in/out-of-baseline label",
         " - acquisition flags",
         " - mask + overlay PNG",
         " - provenance: git tag, config",
         "   hash, file SHA-256, cost"],
        body_size=8.8, tag="every number carries rule + evidence")

    # ---- arrows main row
    ymid = top + h / 2
    arrow(ax, (x_in + w_in, ymid), (x_tile, ymid))
    for yy, col in ((y1 + bh / 2, C["seg"][1]), (y2 + bh / 2, C["emb"][1]), (y3 + bh / 2, C["cov"][1])):
        arrow(ax, (x_tile + w_tile, ymid), (x_br, yy), color=col)
    arrow(ax, (x_br + w_br, y1 + bh / 2), (x_clf, ymid + 0.03), color=C["seg"][1])
    arrow(ax, (x_br + w_br, y2 + bh / 2), (x_clf, ymid - 0.03), color=C["emb"][1])
    # covariates and embedding distance go straight to rules
    arrow(ax, (x_br + w_br, y3 + bh / 2), (x_rul, top + 0.02), color=C["cov"][1])
    arrow(ax, (x_clf + w_clf, ymid), (x_rul, ymid), color=C["clf"][1])
    arrow(ax, (x_rul + w_rul, ymid), (x_out, ymid), color=C["rules"][1])
    ax.text(x_clf + w_clf / 2, top - 0.012, "covariates bypass the classifier: flags only", fontsize=8.2,
            color=C["cov"][1], style="italic", ha="center", va="top")

    # ---- validation / governance band
    by, bh2 = 0.07, 0.33
    ax.add_patch(FancyBboxPatch((0.03, by), 0.945, bh2, boxstyle="round,pad=0,rounding_size=0.015",
                                fc=C["band"][0], ec=C["band"][1], lw=1.4, ls="--", zorder=1))
    ax.text(0.042, by + bh2 - 0.02, "How we know it works, and how it is kept honest",
            fontsize=13.5, fontweight="bold", color="#202024", va="top")

    cols = [
        ("Validation: leave-one-image-out (31 folds)",
         ["Each image predicted by a model that never saw it;",
          "scaler + PCA refit inside every fold (no leakage).",
          "",
          "3-way accuracy 18/31 = 58 % (Wilson 95 % CI 41-74 %)",
          "  always-Batch_3 baseline 17/31; label-permutation",
          "  p = 0.035 (1000 shuffles, median 39 %)",
          "Batch_3 vs rest 26/31 = 84 %, ROC AUC 0.94",
          "'Batch_3' bets right 14/16; B1 bets 2/6; B2 bets 2/9",
          "High tier right 14/18 (78 %), low tier 4/13 (31 %)",
          "Batch_1 vs Batch_2 is near chance (2/7 recall each)."]),
        ("Freeze + provenance",
         ["Everything frozen before the held-out images were",
          "opened: git tag v1-frozen (afdbfc9), configs/v1.yaml",
          "+ features_v1.yaml hashed into every output row,",
          "DINOv2 weights SHA-256 pinned.",
          "",
          "Official held-out run allowed exactly once; the CLI",
          "refuses to overwrite results/v1/heldout.json, refuses",
          "a dirty tree, and refits + checks the coefficients.",
          "Later runs are labelled 'exploratory' in every file.",
          "Independent fresh-context review: PASS (Phase C)."]),
        ("Held-out result (3 official images)",
         ["Run once on Modal L4 at the tag, 18 s, USD 0.0014.",
          "Truth supplied afterwards: 2/3 correct.",
          "Judging confidence score 5/6: the one miss",
          "(3e122cbj, B2 -> B1) was flagged low tier because",
          "it sat outside the Batch_3 band, so it scored 1 not 0.",
          "",
          "6-image never-seen test set (exploratory): 2 x B3 high,",
          "4 x B1/B2 low (outside-baseline cap). Labels pending.",
          "",
          "Phase B (pre-registered stats, 2000 perms): B1 and B2",
          "differ from B3 in raw embeddings; difference vanishes",
          "after regressing out noise/sharpness -> stated as a limit."]),
    ]
    cw = 0.30
    for i, (t, lines) in enumerate(cols):
        x = 0.045 + i * 0.31
        ax.text(x, by + bh2 - 0.065, t, fontsize=11.5, fontweight="bold", color="#3b3b45", va="top")
        ax.text(x, by + bh2 - 0.10, "\n".join(lines), fontsize=9.0, color="#202024", va="top", linespacing=1.38)
        if i < 2:
            ax.plot([x + cw, x + cw], [by + 0.03, by + bh2 - 0.055], color="#d7d8d2", lw=1.2)

    fig.text(0.03, 0.035,
             "Phase names (void / graphite / silicon) are stated by Polaron and not image-verified; Si vs SiOx is "
             "indistinguishable in BSE. Batch_1 / Batch_2 are 'different from the Batch_3 baseline', never better or "
             "worse. Code: src/qc/{segment,features,embed,classify,heldout}.py",
             fontsize=9.2, color="#666670", va="bottom")

    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"model_workflow_overview.{ext}", facecolor="white")
    print(OUT / "model_workflow_overview.png")


if __name__ == "__main__":
    main()

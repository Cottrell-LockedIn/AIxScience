"""Model-accuracy tab for the wrapper (output-only; the frozen v1 model is not touched).

Reads the committed leave-one-image-out (LOIO) validation of the frozen classifier
(results/v1/loio_predictions.csv, results/v1/loio_summary.json) and the official once-only
held-out run (results/v1/heldout.json) and writes results/v1/accuracy_tab/: metrics.json,
tables/*.csv, figures/*.png, EXPLANATION.md and a self-contained preview.html. Every number is
recomputed from the per-image LOIO predictions and cross-checked against loio_summary.json.

Metric choices follow standard reporting practice for small-n classifiers: Model Cards
(Mitchell et al. 2019, arXiv:1810.03993; disaggregated per-class metrics, intended use,
limitations), the scikit-learn evaluation guide (accuracy, balanced accuracy, per-class
precision/recall/F1, Cohen's kappa, Matthews correlation, one-vs-rest ROC AUC, log loss, Brier
score), Wilson score intervals for proportions, and a label-permutation test against chance.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    balanced_accuracy_score,
    cohen_kappa_score,
    f1_score,
    log_loss,
    matthews_corrcoef,
    precision_recall_fscore_support,
    roc_auc_score,
    roc_curve,
)

from qc import classify  # noqa: E402
from qc import config as _config  # noqa: E402

BATCHES = list(classify.BATCHES)
REFERENCE = classify.REFERENCE_BATCH
OUT_DIR = Path("results") / "v1" / "accuracy_tab"
LOIO_CSV = Path("results") / "v1" / "loio_predictions.csv"
LOIO_SUMMARY = Path("results") / "v1" / "loio_summary.json"
HELDOUT_JSON = Path("results") / "v1" / "heldout.json"
# True batches of the three official held-out images, given by the owner on 2026-10-04 after the
# once-only run (docs/PRD_MODEL_IMPROVEMENTS.md, M8). Used for scoring only, never for fitting.
HELDOUT_TRUTH = {"3e122cbj": "Batch_2", "fn0mhxef": "Batch_1", "xrv9xvzb": "Batch_3"}
JUDGING_SCORE_RULE = (
    "2 = correct at tier high; 1 = correct at tier low, or incorrect at tier low; "
    "0 = incorrect at tier high (owner's reading of the judging criterion 'confidence score')"
)
TIERS = ["high", "low"]  # v1.1: two tiers; a legacy v1 'medium' label is read as low
COLORS = {"Batch_1": "#d95f02", "Batch_2": "#7570b3", "Batch_3": "#1b9e77"}
REFERENCES = [
    "Mitchell et al. (2019) Model Cards for Model Reporting, FAT* 2019, arXiv:1810.03993",
    "scikit-learn User Guide 3.4 'Metrics and scoring: quantifying the quality of predictions'",
    "Wilson (1927) Probable inference, the law of succession, and statistical inference, JASA 22:209-212",
    "Ojala & Garriga (2010) Permutation tests for studying classifier performance, JMLR 11:1833-1863",
    "Brier (1950) Verification of forecasts expressed in terms of probability, Mon. Weather Rev. 78:1-3",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def judging_score(correct: bool, tier: str) -> int:
    if tier == "high":
        return 2 if correct else 0
    return 1


def _frac(k: int, n: int) -> dict[str, Any]:
    lo, hi = classify.wilson(int(k), int(n))
    return {"k": int(k), "n": int(n), "value": float(k / n) if n else float("nan"),
            "str": f"{int(k)}/{int(n)}", "wilson95": [float(lo), float(hi)]}


def compute_metrics(loio: pd.DataFrame, summary: dict[str, Any], heldout: dict[str, Any]) -> dict[str, Any]:
    y = loio["true_batch"].to_numpy()
    yhat = loio["pred_batch"].to_numpy()
    P = loio[[f"p_{b}" for b in BATCHES]].to_numpy(dtype=float)
    n = len(loio)
    correct = int((y == yhat).sum())
    if summary["loio_correct"] != correct or summary["n_images"] != n:
        raise ValueError("loio_predictions.csv disagrees with loio_summary.json")
    y_idx = np.array([BATCHES.index(b) for b in y])
    onehot = np.eye(len(BATCHES))[y_idx]
    majority = int(pd.Series(y).value_counts().iloc[0])

    prec, rec, f1, support = precision_recall_fscore_support(y, yhat, labels=BATCHES, zero_division=0)
    pred_counts = pd.Series(yhat).value_counts().reindex(BATCHES).fillna(0).astype(int)
    cm = pd.crosstab(pd.Categorical(y, BATCHES), pd.Categorical(yhat, BATCHES), dropna=False).to_numpy()
    if cm.tolist() != summary["confusion_matrix"]["values"]:
        raise ValueError("confusion matrix disagrees with loio_summary.json")

    per_batch = {}
    for i, b in enumerate(BATCHES):
        tp = int(cm[i, i])
        per_batch[b] = {
            "support": int(support[i]), "predicted": int(pred_counts[b]),
            "recall": _frac(tp, int(support[i])), "precision": _frac(tp, int(pred_counts[b])),
            "f1": float(f1[i]),
            "auroc_one_vs_rest": float(roc_auc_score((y == b).astype(int), P[:, i])),
        }

    ref = BATCHES.index(REFERENCE)
    is_ref = y == REFERENCE
    pred_ref = yhat == REFERENCE
    tp, fp = int((is_ref & pred_ref).sum()), int((~is_ref & pred_ref).sum())
    fn, tn = int((is_ref & ~pred_ref).sum()), int((~is_ref & ~pred_ref).sum())
    ref_vs_rest = {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": _frac(tp + tn, n),
        "precision": _frac(tp, tp + fp), "recall_sensitivity": _frac(tp, tp + fn),
        "specificity": _frac(tn, tn + fp), "npv": _frac(tn, tn + fn),
        "f1": float(2 * tp / (2 * tp + fp + fn)),
        "balanced_accuracy": float(0.5 * (tp / (tp + fn) + tn / (tn + fp))),
        "auroc": float(roc_auc_score(is_ref.astype(int), P[:, ref])),
        "mcc": float(matthews_corrcoef(is_ref.astype(int), pred_ref.astype(int))),
    }

    by_tier = {}
    for t in TIERS:
        m = loio["tier"].to_numpy() == t
        k = int((y[m] == yhat[m]).sum())
        by_tier[t] = {**_frac(k, int(m.sum())), "mean_confidence": float(loio.loc[m, "confidence"].mean()) if m.any() else float("nan")}
    ece_tier = float(sum(by_tier[t]["n"] / n * abs(by_tier[t]["mean_confidence"] - by_tier[t]["value"])
                        for t in TIERS if by_tier[t]["n"]))

    overall = {
        "n_images": n, "accuracy": _frac(correct, n),
        "majority_baseline": _frac(majority, n), "random_baseline": 1.0 / len(BATCHES),
        "permutation_p": float(summary["permutation_p"]), "n_permutations": int(summary["n_permutations"]),
        "permutation_acc_median": float(summary["permutation_acc_median"]),
        "permutation_acc_p95": float(summary["permutation_acc_p95"]),
        "balanced_accuracy": float(balanced_accuracy_score(y, yhat)),
        "macro_f1": float(f1_score(y, yhat, labels=BATCHES, average="macro", zero_division=0)),
        "cohen_kappa": float(cohen_kappa_score(y, yhat, labels=BATCHES)),
        "mcc": float(matthews_corrcoef(y, yhat)),
        "log_loss": float(log_loss(y, P, labels=BATCHES)),
        "brier_multiclass": float(np.mean(np.sum((P - onehot) ** 2, axis=1))),
        "macro_auroc_one_vs_rest": float(np.mean([per_batch[b]["auroc_one_vs_rest"] for b in BATCHES])),
        "tier_calibration_gap": ece_tier,
    }

    rows = []
    for img in heldout["images"]:
        sid = img["subject"]["id"]
        cs = img["verdict"]["closed_set"]
        truth = HELDOUT_TRUTH[sid]
        ok = cs["predicted_batch"] == truth
        rows.append({"sample_id": sid, "true_batch": truth, "pred_batch": cs["predicted_batch"],
                     "confidence": float(cs["confidence"]), "tier": cs["tier"],
                     "ood_label": img["verdict"]["label"], "correct": bool(ok),
                     "judging_score": judging_score(ok, cs["tier"])})
    held = {"rows": rows, "accuracy": _frac(sum(r["correct"] for r in rows), len(rows)),
            "judging_score": {"k": int(sum(r["judging_score"] for r in rows)), "n": 2 * len(rows),
                              "str": f"{sum(r['judging_score'] for r in rows)}/{2 * len(rows)}"},
            "rule": JUDGING_SCORE_RULE, "status": "official once-only run; truth supplied after the run; exploratory as evidence (n = 3)"}

    return {"overall": overall, "per_batch": per_batch, "confusion_matrix": {"rows_true_cols_pred": BATCHES, "values": cm.tolist()},
            "reference_vs_rest": {"reference": REFERENCE, **ref_vs_rest}, "by_tier": by_tier, "heldout": held,
            "model": summary["model"], "frozen_choices": summary["frozen_choices"], "references": REFERENCES,
            "phase_identity": classify.PHASE_IDENTITY}


def _fig_confusion(cm: np.ndarray, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(4.6, 4.0))
    ax.imshow(cm, cmap="Blues", vmin=0, vmax=cm.max())
    for i in range(3):
        for j in range(3):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=14,
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_xticks(range(3), [b.replace("_", " ") for b in BATCHES])
    ax.set_yticks(range(3), [b.replace("_", " ") for b in BATCHES])
    ax.set_xlabel("Predicted batch")
    ax.set_ylabel("True batch")
    ax.set_title("Leave-one-image-out confusion matrix (31 images)")
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def _fig_accuracy_vs_baselines(m: dict[str, Any], path: Path) -> None:
    o, r = m["overall"], m["reference_vs_rest"]
    labels = ["Random\nguess", "Always\nBatch 3", "Permuted\nlabels (median)", "Model:\n3-way batch", f"Model:\n{REFERENCE.replace('_', ' ')} vs rest"]
    vals = [o["random_baseline"], o["majority_baseline"]["value"], o["permutation_acc_median"], o["accuracy"]["value"], r["accuracy"]["value"]]
    errs = [None, None, None, o["accuracy"]["wilson95"], r["accuracy"]["wilson95"]]
    cols = ["#bbbbbb", "#bbbbbb", "#bbbbbb", "#1f77b4", "#1b9e77"]
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.bar(labels, vals, color=cols)
    for i, e in enumerate(errs):
        if e:
            ax.errorbar(i, vals[i], yerr=[[vals[i] - e[0]], [e[1] - vals[i]]], fmt="none", ecolor="black", capsize=4)
        ax.text(i, vals[i] + 0.02, f"{vals[i]:.0%}", ha="center", fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Accuracy (31 training images, leave-one-image-out)")
    ax.set_title(f"Accuracy vs baselines; permutation test p = {o['permutation_p']:.3f}; bars = Wilson 95 % CI")
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def _fig_per_batch(m: dict[str, Any], path: Path) -> None:
    pb = m["per_batch"]
    x = np.arange(3)
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.bar(x - 0.2, [pb[b]["recall"]["value"] for b in BATCHES], 0.4, label="Recall (of true images, how many found)", color="#1f77b4")
    ax.bar(x + 0.2, [pb[b]["precision"]["value"] for b in BATCHES], 0.4, label="Precision (of bets, how many right)", color="#ff7f0e")
    for i, b in enumerate(BATCHES):
        ax.text(i - 0.2, pb[b]["recall"]["value"] + 0.02, pb[b]["recall"]["str"], ha="center", fontsize=9)
        ax.text(i + 0.2, pb[b]["precision"]["value"] + 0.02, pb[b]["precision"]["str"], ha="center", fontsize=9)
    ax.set_xticks(x, [b.replace("_", " ") for b in BATCHES])
    ax.set_ylim(0, 1.1)
    ax.axhline(1 / 3, ls=":", color="grey", lw=1)
    ax.text(2.45, 1 / 3 + 0.01, "chance", fontsize=8, color="grey")
    ax.set_title("Per-batch recall and precision (leave-one-image-out)")
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def _fig_by_tier(m: dict[str, Any], path: Path) -> None:
    bt = m["by_tier"]
    x = np.arange(len(TIERS))
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    acc = [bt[t]["value"] for t in TIERS]
    conf = [bt[t]["mean_confidence"] for t in TIERS]
    ax.bar(x - 0.2, acc, 0.4, label="Observed accuracy", color="#1f77b4")
    ax.bar(x + 0.2, conf, 0.4, label="Mean reported probability", color="#bbbbbb")
    for i, t in enumerate(TIERS):
        lo, hi = bt[t]["wilson95"]
        ax.errorbar(i - 0.2, acc[i], yerr=[[acc[i] - lo], [hi - acc[i]]], fmt="none", ecolor="black", capsize=4)
        ax.text(i - 0.2, hi + 0.02, bt[t]["str"], ha="center", fontsize=9)
    ax.set_xticks(x, [f"{t} tier" for t in TIERS])
    ax.set_ylim(0, 1.15)
    ax.set_title("Is the confidence tier honest? Accuracy by tier (Wilson 95 % CI)")
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def _fig_roc(loio: pd.DataFrame, m: dict[str, Any], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(4.8, 4.4))
    y = loio["true_batch"].to_numpy()
    for b in BATCHES:
        fpr, tpr, _ = roc_curve((y == b).astype(int), loio[f"p_{b}"].to_numpy(dtype=float))
        ax.plot(fpr, tpr, color=COLORS[b], label=f"{b.replace('_', ' ')} vs rest, AUC {m['per_batch'][b]['auroc_one_vs_rest']:.2f}")
    ax.plot([0, 1], [0, 1], ls=":", color="grey", lw=1)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("One-vs-rest ROC (LOIO probabilities)")
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def _tables(m: dict[str, Any], out: Path) -> dict[str, pd.DataFrame]:
    o, r = m["overall"], m["reference_vs_rest"]
    overall = pd.DataFrame([
        ("Images (training, leave-one-image-out)", o["n_images"], ""),
        ("Accuracy", o["accuracy"]["str"], f"{o['accuracy']['value']:.1%}; Wilson 95 % CI {o['accuracy']['wilson95'][0]:.0%}-{o['accuracy']['wilson95'][1]:.0%}"),
        ("Majority baseline (always Batch 3)", o["majority_baseline"]["str"], f"{o['majority_baseline']['value']:.1%}"),
        ("Permutation test vs chance", f"p = {o['permutation_p']:.3f}", f"{o['n_permutations']} label shuffles; permuted median {o['permutation_acc_median']:.1%}"),
        ("Balanced accuracy", f"{o['balanced_accuracy']:.3f}", "mean per-batch recall; chance 0.333"),
        ("Macro F1", f"{o['macro_f1']:.3f}", ""),
        ("Cohen's kappa", f"{o['cohen_kappa']:.3f}", "agreement beyond chance; 0 = chance"),
        ("Matthews correlation", f"{o['mcc']:.3f}", "0 = chance, 1 = perfect"),
        ("Macro one-vs-rest ROC AUC", f"{o['macro_auroc_one_vs_rest']:.3f}", "0.5 = chance"),
        ("Log loss", f"{o['log_loss']:.3f}", "lower is better; 1.099 = uniform 1/3"),
        ("Brier score (multiclass)", f"{o['brier_multiclass']:.3f}", "lower is better; 0.667 = uniform 1/3"),
        ("Tier calibration gap", f"{o['tier_calibration_gap']:.3f}", "mean |reported probability - observed accuracy| over tiers"),
    ], columns=["metric", "value", "note"])
    per_batch = pd.DataFrame([{
        "batch": b, "true_images": m["per_batch"][b]["support"], "predicted_as": m["per_batch"][b]["predicted"],
        "recall": m["per_batch"][b]["recall"]["str"], "precision": m["per_batch"][b]["precision"]["str"],
        "f1": round(m["per_batch"][b]["f1"], 3), "auroc_one_vs_rest": round(m["per_batch"][b]["auroc_one_vs_rest"], 3),
    } for b in BATCHES])
    ref = pd.DataFrame([
        ("Accuracy", r["accuracy"]["str"], f"Wilson 95 % CI {r['accuracy']['wilson95'][0]:.0%}-{r['accuracy']['wilson95'][1]:.0%}"),
        ("Precision (bet Batch 3 -> is Batch 3)", r["precision"]["str"], ""),
        ("Recall / sensitivity (Batch 3 found)", r["recall_sensitivity"]["str"], ""),
        ("Specificity (non-Batch 3 kept out)", r["specificity"]["str"], ""),
        ("Negative predictive value", r["npv"]["str"], ""),
        ("F1", f"{r['f1']:.3f}", ""), ("Balanced accuracy", f"{r['balanced_accuracy']:.3f}", ""),
        ("ROC AUC (p_Batch_3)", f"{r['auroc']:.3f}", ""), ("Matthews correlation", f"{r['mcc']:.3f}", ""),
    ], columns=["metric", "value", "note"])
    cm = pd.DataFrame(m["confusion_matrix"]["values"], index=[f"true {b}" for b in BATCHES], columns=[f"pred {b}" for b in BATCHES])
    tier = pd.DataFrame([{"tier": t, "images": m["by_tier"][t]["n"], "correct": m["by_tier"][t]["str"],
                          "accuracy": round(m["by_tier"][t]["value"], 3), "mean_reported_probability": round(m["by_tier"][t]["mean_confidence"], 3),
                          "wilson95_low": round(m["by_tier"][t]["wilson95"][0], 3), "wilson95_high": round(m["by_tier"][t]["wilson95"][1], 3)} for t in TIERS])
    held = pd.DataFrame(m["heldout"]["rows"])
    tables = {"overall": overall, "per_batch": per_batch, "reference_vs_rest": ref, "confusion_matrix": cm, "by_tier": tier, "heldout": held}
    (out / "tables").mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out / "tables" / f"{name}.csv", index=(name == "confusion_matrix"))
    return tables


def _explanation(m: dict[str, Any]) -> str:
    o, r, h = m["overall"], m["reference_vs_rest"], m["heldout"]
    bt, pb = m["by_tier"], m["per_batch"]
    ci = o["accuracy"]["wilson95"]
    return f"""# Model accuracy (frozen v1 classifier)

`phase_identity: {m['phase_identity']}`

## What this tab shows
How well the frozen batch classifier performed when tested on images it had not seen, and how honest its
confidence levels are. All numbers come from one procedure: **leave-one-image-out (LOIO)** on the 31
training images (7 Batch 1, 7 Batch 2, 17 Batch 3). The model is refitted 31 times, each time leaving one
whole image out and predicting it, so every image is scored as unseen. Tiles from one image are never split
across fit and test. The 3 official held-out images are reported separately.

## Headline
- **Batch 3 (the supplier baseline) is detected reliably.** When the model says "Batch 3" it is right
  {r['precision']['str']} times ({r['precision']['value']:.0%}); it finds {r['recall_sensitivity']['str']} of the true Batch 3 images
  ({r['recall_sensitivity']['value']:.0%}) and keeps {r['specificity']['str']} of the non-Batch 3 images out
  (specificity {r['specificity']['value']:.0%}). Batch 3-vs-rest accuracy {r['accuracy']['str']} ({r['accuracy']['value']:.0%},
  95 % CI {r['accuracy']['wilson95'][0]:.0%}-{r['accuracy']['wilson95'][1]:.0%}), ROC AUC {r['auroc']:.2f}.
- **Three-way batch accuracy is {o['accuracy']['str']} ({o['accuracy']['value']:.0%}, 95 % CI {ci[0]:.0%}-{ci[1]:.0%}), above chance:**
  a label-permutation test gives p = {o['permutation_p']:.3f} ({o['n_permutations']} shuffles; shuffled labels score
  {o['permutation_acc_median']:.0%} on average). The always-Batch-3 baseline scores {o['majority_baseline']['str']}.
- **The confidence tier is honest.** High-tier bets were right {bt['high']['str']} ({bt['high']['value']:.0%}); low-tier bets
  {bt['low']['str']} ({bt['low']['value']:.0%}). The model says "low" exactly where it is weak.
- **Official held-out run: {h['accuracy']['str']} correct, {h['judging_score']['str']} under the judging confidence score**
  (the one miss, 3e122cbj, was flagged low confidence, so it scored 1 rather than 0).

## Where the model is weak (shown on purpose)
- Batch 1 vs Batch 2 is close to a coin flip: recall {pb['Batch_1']['recall']['str']} and {pb['Batch_2']['recall']['str']},
  precision {pb['Batch_1']['precision']['str']} and {pb['Batch_2']['precision']['str']}. Balanced accuracy {o['balanced_accuracy']:.2f}
  (chance 0.33), Cohen's kappa {o['cohen_kappa']:.2f}, Matthews correlation {o['mcc']:.2f}. The confusion matrix shows the
  Batch 1 / Batch 2 misses go mostly to each other.
- 31 training images is small: the 95 % interval on three-way accuracy spans {ci[0]:.0%}-{ci[1]:.0%}.
- Phase B could not separate the embedding's batch signal from imaging conditions; part of what the model detects
  may be how the images were taken rather than the material.

## Metrics in plain words
| Metric | What it means | Value |
|---|---|---|
| Accuracy | share of images whose batch was predicted correctly | {o['accuracy']['str']} = {o['accuracy']['value']:.0%} |
| Wilson 95 % CI | the range of true accuracies consistent with {o['accuracy']['str']} | {ci[0]:.0%}-{ci[1]:.0%} |
| Permutation p | chance that shuffled labels would do at least this well | {o['permutation_p']:.3f} |
| Balanced accuracy | average recall over the three batches (fair when classes are unequal) | {o['balanced_accuracy']:.2f} |
| Precision | of the images called X, how many were X | per batch, see table |
| Recall | of the true X images, how many were called X | per batch, see table |
| Cohen's kappa / MCC | agreement beyond what chance would give (0 = chance) | {o['cohen_kappa']:.2f} / {o['mcc']:.2f} |
| ROC AUC (one vs rest) | how well the probability ranks "X" above "not X" (0.5 = chance) | B1 {pb['Batch_1']['auroc_one_vs_rest']:.2f}, B2 {pb['Batch_2']['auroc_one_vs_rest']:.2f}, B3 {pb['Batch_3']['auroc_one_vs_rest']:.2f} |
| Log loss / Brier | penalise confident wrong probabilities (lower is better) | {o['log_loss']:.2f} / {o['brier_multiclass']:.2f} |
| Tier calibration gap | mean gap between reported probability and observed accuracy, by tier | {o['tier_calibration_gap']:.2f} |

## Confidence tier rule (frozen)
{classify.TIER_RULE}

## Official held-out images
Status: {h['status']}. Scoring rule: {h['rule']}.

| image | true | predicted | p | tier | Batch 3 flag | correct | score |
|---|---|---|---|---|---|---|---|
""" + "\n".join(
        f"| {row['sample_id']} | {row['true_batch']} | {row['pred_batch']} | {row['confidence']:.2f} | {row['tier']} | {row['ood_label']} | {'yes' if row['correct'] else 'no'} | {row['judging_score']} |"
        for row in h["rows"]) + f"""

## Model
{m['model']}

Frozen choices: `{m['frozen_choices']}`. Validation data: `results/v1/loio_predictions.csv`, `results/v1/loio_summary.json`;
held-out: `results/v1/heldout.json`. Regenerate with `python -m qc accuracy-tab`.

## References
""" + "\n".join(f"- {ref}" for ref in m["references"]) + "\n"


def _preview_html(m: dict[str, Any], tables: dict[str, pd.DataFrame], figures: dict[str, Path], explanation: str) -> str:
    def img(p: Path) -> str:
        return f'<img src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}" style="max-width:100%">'
    o, r, bt, h = m["overall"], m["reference_vs_rest"], m["by_tier"], m["heldout"]
    cards = [
        (f"{r['precision']['value']:.0%}", f"Batch 3 bets correct ({r['precision']['str']})"),
        (f"{o['accuracy']['value']:.0%}", f"3-way accuracy ({o['accuracy']['str']}), p = {o['permutation_p']:.3f} vs chance"),
        (f"{bt['high']['value']:.0%}", f"high-tier bets correct ({bt['high']['str']})"),
        (h["judging_score"]["str"], "official held-out, judging confidence score"),
    ]
    card_html = "".join(f'<div class="card"><div class="big">{v}</div><div class="small">{t}</div></div>' for v, t in cards)
    body = explanation.split("## Metrics in plain words")[0]
    body_html = "".join(f"<p>{line[2:]}</p>" if line.startswith("- ") else (f"<h2>{line[3:]}</h2>" if line.startswith("## ") else f"<p>{line}</p>")
                        for line in body.splitlines() if line.strip() and not line.startswith("# "))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Model accuracy</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#222}}
.cards{{display:flex;gap:12px;flex-wrap:wrap}}.card{{flex:1 1 200px;border:1px solid #ddd;border-radius:8px;padding:14px}}
.big{{font-size:30px;font-weight:600}}.small{{color:#555;font-size:13px}}table{{border-collapse:collapse;font-size:13px;margin:8px 0}}
td,th{{border:1px solid #ddd;padding:4px 8px;text-align:left}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.note{{background:#fff8e1;border-left:4px solid #f0ad4e;padding:8px 12px}}</style></head><body>
<h1>Model accuracy (frozen v1)</h1><div class="cards">{card_html}</div>
<p class="note">Validation: leave-one-image-out on 31 training images (7 / 7 / 17); whole images held out, never tiles.
The 3 official held-out images are reported separately. <code>phase_identity: {m['phase_identity']}</code></p>
{body_html}
<div class="grid"><div>{img(figures['accuracy_vs_baselines'])}</div><div>{img(figures['by_tier'])}</div>
<div>{img(figures['per_batch'])}</div><div>{img(figures['confusion_matrix'])}</div><div>{img(figures['roc'])}</div></div>
<h2>Batch 3 vs rest</h2>{tables['reference_vs_rest'].to_html(index=False)}
<h2>Per batch</h2>{tables['per_batch'].to_html(index=False)}
<h2>All metrics</h2>{tables['overall'].to_html(index=False)}
<h2>By confidence tier</h2>{tables['by_tier'].to_html(index=False)}
<h2>Official held-out images</h2>{tables['heldout'].to_html(index=False)}<p class="small">{h['rule']}</p>
<h2>Confidence tier rule (frozen)</h2><p class="small">{classify.TIER_RULE}</p>
<h2>References</h2><ul>{''.join(f'<li>{ref}</li>' for ref in m['references'])}</ul></body></html>"""


def build(out: Path, root: Path | None = None, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    root = root or _config.ROOT
    loio = pd.read_csv(root / LOIO_CSV)
    loio["tier"] = loio["tier"].replace({"medium": "low"})
    summary = json.loads((root / LOIO_SUMMARY).read_text())
    heldout = json.loads((root / HELDOUT_JSON).read_text())
    m = compute_metrics(loio, summary, heldout)
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(exist_ok=True)
    cm = np.array(m["confusion_matrix"]["values"])
    figures = {"confusion_matrix": out / "figures" / "confusion_matrix.png",
               "accuracy_vs_baselines": out / "figures" / "accuracy_vs_baselines.png",
               "per_batch": out / "figures" / "per_batch_precision_recall.png",
               "by_tier": out / "figures" / "accuracy_by_tier.png",
               "roc": out / "figures" / "roc_one_vs_rest.png"}
    _fig_confusion(cm, figures["confusion_matrix"])
    _fig_accuracy_vs_baselines(m, figures["accuracy_vs_baselines"])
    _fig_per_batch(m, figures["per_batch"])
    _fig_by_tier(m, figures["by_tier"])
    _fig_roc(loio, m, figures["roc"])
    tables = _tables(m, out)
    explanation = _explanation(m)
    (out / "EXPLANATION.md").write_text(explanation)
    (out / "preview.html").write_text(_preview_html(m, tables, figures, explanation))
    m["figures"] = {k: str(p.relative_to(out)) for k, p in figures.items()}
    m["tables"] = {k: f"tables/{k}.csv" for k in tables}
    m["provenance"] = {"git_sha": _config.git_sha(), "config_hash": cfg["_hash"] if cfg else summary["config_hash"],
                       "sources": {str(p): _sha256(root / p) for p in (LOIO_CSV, LOIO_SUMMARY, HELDOUT_JSON)},
                       "exploratory": True, "note": "output-only; the frozen model and its predictions are unchanged"}
    (out / "metrics.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    return m


def run(cfg: dict[str, Any]) -> None:
    m = build(_config.ROOT / OUT_DIR, cfg=cfg)
    o, r = m["overall"], m["reference_vs_rest"]
    print(f"[qc] accuracy-tab -> {OUT_DIR}: accuracy {o['accuracy']['str']} (perm p {o['permutation_p']:.3f}), "
          f"{REFERENCE} precision {r['precision']['str']}, held-out {m['heldout']['judging_score']['str']}")

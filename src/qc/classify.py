"""S7 Phase C batch classifier (classify).

One frozen model (docs/Log/2026-10-04_phase_c.md "Frozen choices"): standardised F01-F11 plus
PCA(29) of the mean-pooled BSE DINOv2 embedding, multinomial L2 logistic regression, validated by
leave-one-image-out. Every image always gets a batch bet; the Batch_3 OOD flag sits beside it.

Reads:  results/features_per_image.parquet, results/emb_per_image.parquet,
        results/artefacts_per_image.parquet, results/audit/images.csv, results/stats/feature_status.csv
Writes: results/v1/loio_predictions.csv, results/v1/loio_summary.json, results/v1/confusion_matrix.csv,
        results/v1/final_model.csv, results/v1/loio_images/<sample_id>.json

Contract: image id (8-char sample id) is the independent unit. This module must never mix tiles
from one image across folds, splits or permutations. See docs/FRAMEWORK.md Section 00 hard rules.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from qc import config as _config
from qc import stats as _stats

BATCHES = ["Batch_1", "Batch_2", "Batch_3"]
REFERENCE_BATCH = "Batch_3"
F_COLS = [
    "F01_c0_area_fraction", "F02_c2_area_fraction", "F03_c2_eqdiam_median_px",
    "F04_c2_eqdiam_p90_px", "F05_c2_count_density_per_Mpx", "F06_c2_clark_evans_R",
    "F07_c2_solidity_area_weighted_median", "F08_c0_local_thickness_median_px",
    "F09_c0_chord_anisotropy_h_over_v", "F10_c0_fraction_iqr_512px",
    "F11_c2_perimeter_fraction_adjacent_c0",
]
EMB_COLS = [f"e{i:03d}" for i in range(384)]
N_PCS = 29
SEED = 0
N_PERMUTATIONS = 1000
TOP_DRIVERS = 3
COEF_TOL = 1e-9
LOG_PATH = "docs/Log/2026-10-04_phase_c.md"
OUT_DIR = Path("results") / "v1"
PHASE_IDENTITY = "stated by Polaron, not image-verified"
EMBEDDING_TAG = "embedding: acquisition and material not separable (Phase B residualisation)"

MODEL_RULE = (
    "StandardScaler(F01-F11) + PCA(n_components=29, svd_solver='full') of the raw mean-pooled BSE "
    "DINOv2 embedding, both fitted on the training images only; LogisticRegression(C=1.0, "
    "class_weight='balanced', solver='lbfgs', max_iter=10000, random_state=0), L2, multinomial."
)
BET_RULE = (
    "pred_batch = argmax of the image's predicted probability (out-of-fold for training images); "
    "always one of Batch_1, Batch_2, Batch_3. confidence = that probability; margin = top minus runner-up."
)
TIER_RULE = (
    "high if p_max >= 0.75 and LOIO permutation p < 0.05 and OOD label = within_bounds; otherwise low "
    "(p_max < 0.75, or LOIO permutation p >= 0.05, or OOD label = outside_bounds). Two tiers only: the v1 "
    "'medium' band (0.5 <= p_max < 0.75, 1/5 correct in LOIO) is reported as low since v1.1, a score-neutral "
    "presentation change; bets and probabilities are unchanged."
)
DRIVER_RULE = (
    "contribution_k = coef[pred_batch, k] x x_k (x_k = standardised F value or embedding PC score); "
    "top 3 by signed contribution, i.e. the largest support for the bet."
)
OOD_RULE = (
    "E1(x, R) = 2*mean_r||x - r|| - mean_{r != r'}||r - r'|| on L2-normalised BSE embeddings, "
    "R = Batch_3 training images other than x; band = 95/99 % quantiles (numpy linear) of E1 for each "
    "Batch_3 image against the other Batch_3 images in R. within_bounds if E1 <= band95, investigate if "
    "band95 < E1 <= band99, outside_bounds if E1 > band99; matches_known_batch = E1 <= band99. The flag "
    "never replaces pred_batch. The null has only 16-17 values, so band99 interpolates between the two "
    "largest null values; rank_p = (1 + #{null >= E1}) / (1 + n_null) is reported, minimum about 1/18."
)
COVARIATE_RULE = (
    "Flag an image covariate when it is strictly outside the 5th-95th percentile of the training images "
    "used for that prediction; reported only, not a model input."
)


@dataclass
class Model:
    scaler: StandardScaler
    pca: PCA
    lr: LogisticRegression


def design_names() -> list[str]:
    return F_COLS + [f"embedding PC {k + 1}" for k in range(N_PCS)]


def load_training() -> pd.DataFrame:
    root = _config.ROOT / "results"
    feats = pd.read_parquet(root / "features_per_image.parquet")
    feats = feats.loc[feats["scale"] == 1.0, ["sample_id", "batch", *F_COLS]]
    emb = pd.read_parquet(root / "emb_per_image.parquet")
    emb = emb.loc[emb["channel"] == "BSE", ["sample_id", "batch", *EMB_COLS]]
    frame = feats.merge(emb, on="sample_id", how="inner", validate="one_to_one", suffixes=("", "_emb"))
    if len(frame) != 31 or not (frame["batch"] == frame["batch_emb"]).all():
        raise ValueError(f"expected 31 matched images, got {len(frame)}")
    if frame["sample_id"].duplicated().any():
        raise ValueError("duplicate image ids")
    counts = frame["batch"].value_counts().to_dict()
    if counts != {"Batch_3": 17, "Batch_1": 7, "Batch_2": 7}:
        raise ValueError(f"unexpected batch counts {counts}")
    frame = frame.drop(columns="batch_emb").sort_values("sample_id", kind="stable").reset_index(drop=True)
    if not np.isfinite(frame[F_COLS + EMB_COLS].to_numpy(dtype=np.float64)).all():
        raise ValueError("non-finite training inputs")
    return frame


def fit_transform(xf: np.ndarray, xe: np.ndarray) -> tuple[StandardScaler, PCA, np.ndarray]:
    scaler = StandardScaler().fit(xf)
    pca = PCA(n_components=N_PCS, svd_solver="full").fit(xe)
    return scaler, pca, np.hstack([scaler.transform(xf), pca.transform(xe)])


def transform(scaler: StandardScaler, pca: PCA, xf: np.ndarray, xe: np.ndarray) -> np.ndarray:
    return np.hstack([scaler.transform(np.atleast_2d(xf)), pca.transform(np.atleast_2d(xe))])


def new_lr() -> LogisticRegression:
    return LogisticRegression(
        C=1.0, class_weight="balanced", solver="lbfgs", max_iter=10000, random_state=SEED
    )


def fit(xf: np.ndarray, xe: np.ndarray, y: np.ndarray) -> Model:
    scaler, pca, z = fit_transform(xf, xe)
    lr = new_lr().fit(z, y)
    if list(lr.classes_) != BATCHES:
        raise ValueError(f"classifier classes {list(lr.classes_)} != {BATCHES}")
    return Model(scaler, pca, lr)


def _arrays(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        frame[F_COLS].to_numpy(dtype=np.float64),
        frame[EMB_COLS].to_numpy(dtype=np.float64),
        frame["batch"].to_numpy(dtype=object),
    )


def fold_designs(xf: np.ndarray, xe: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Label-free per-fold (train design, test design); reused across label permutations."""
    out = []
    n = len(xf)
    for i in range(n):
        train = np.delete(np.arange(n), i)
        scaler, pca, z_train = fit_transform(xf[train], xe[train])
        out.append((z_train, transform(scaler, pca, xf[i], xe[i])))
    return out


def loio_accuracy(designs: list[tuple[np.ndarray, np.ndarray]], y: np.ndarray) -> float:
    n = len(y)
    hits = 0
    for i, (z_train, z_test) in enumerate(designs):
        lr = new_lr().fit(z_train, np.delete(y, i))
        hits += int(lr.predict(z_test)[0] == y[i])
    return hits / n


def permutation_p(designs, y: np.ndarray, observed: float, n_perm: int = N_PERMUTATIONS,
                  seed: int = SEED) -> tuple[float, np.ndarray]:
    rng = np.random.default_rng(seed)
    perms = [rng.permutation(y) for _ in range(n_perm)]
    accs = np.asarray(Parallel(n_jobs=-1)(delayed(loio_accuracy)(designs, p) for p in perms))
    return float((1 + np.sum(accs >= observed - 1e-12)) / (1 + n_perm)), accs


def unit(xe: np.ndarray) -> np.ndarray:
    xe = np.atleast_2d(np.asarray(xe, dtype=np.float64))
    return xe / np.linalg.norm(xe, axis=1, keepdims=True)


def e1(x: np.ndarray, ref: np.ndarray) -> float:
    cross = np.linalg.norm(ref - x, axis=1).mean()
    d = np.linalg.norm(ref[:, None, :] - ref[None, :, :], axis=2)
    within = d.sum() / (len(ref) * (len(ref) - 1))
    return float(2 * cross - within)


def reference_band(ref: np.ndarray) -> tuple[float, float, np.ndarray]:
    vals = np.array([e1(ref[i], np.delete(ref, i, axis=0)) for i in range(len(ref))])
    return float(np.quantile(vals, 0.95)), float(np.quantile(vals, 0.99)), vals


def ood(x_unit: np.ndarray, train_units: np.ndarray, train_batches: np.ndarray) -> dict[str, Any]:
    ref = train_units[train_batches == REFERENCE_BATCH]
    value = e1(x_unit, ref)
    band95, band99, null_vals = reference_band(ref)
    label = "within_bounds" if value <= band95 else ("investigate" if value <= band99 else "outside_bounds")
    dist = {b: e1(x_unit, train_units[train_batches == b]) for b in BATCHES}
    rank_p = float((1 + np.sum(null_vals >= value)) / (1 + len(null_vals)))
    return {
        "e1_to_batch3": value, "band95": band95, "band99": band99, "n_reference": int(len(ref)),
        "null_max": float(null_vals.max()), "label": label, "matches_known_batch": bool(value <= band99),
        "distance_to_each_batch": dist, "nearest_batch": min(dist, key=dist.get),
        "margin_to_band99": float(band99 - value), "rank_p": rank_p, "n_null": int(len(null_vals)),
    }


def tier(p_max: float, perm_p: float, ood_label: str) -> tuple[str, str]:
    if p_max < 0.5:
        return "low", f"p_max={p_max:.3f} < 0.5"
    if perm_p >= 0.05:
        return "low", f"LOIO permutation p={perm_p:.4f} >= 0.05 (model not shown to beat chance)"
    if ood_label == "outside_bounds":
        return "low", "outside the Batch_3 embedding band (OOD caps the tier at low)"
    if p_max < 0.75:
        return "low", f"p_max={p_max:.3f} < 0.75 (v1 'medium' band, reported as low since v1.1)"
    return "high", f"p_max={p_max:.3f} >= 0.75 and LOIO permutation p={perm_p:.4f} < 0.05"


def drivers(model: Model, z: np.ndarray, raw_f: np.ndarray, pred: str,
            status: dict[str, str]) -> list[dict[str, Any]]:
    k = BATCHES.index(pred)
    contrib = model.lr.coef_[k] * z
    names = design_names()
    order = np.argsort(-contrib, kind="stable")[:TOP_DRIVERS]
    out = []
    for j in order:
        name = names[j]
        is_f = j < len(F_COLS)
        out.append({
            "name": name,
            "units": ("px-based image feature; model_input is the fold-standardised value" if is_f
                      else "model_input is the raw PC score (not standardised; embedding units)"),
            "value": float(raw_f[j]) if is_f else float(z[j]),
            "model_input": float(z[j]),
            "coefficient": float(model.lr.coef_[k, j]),
            "effect_size": float(contrib[j]),
            "direction": "higher" if z[j] >= 0 else "lower",
            "tag": (f"material (segmentation-derived; Phase B status: {status.get(name, 'n/a')})"
                    if is_f else EMBEDDING_TAG),
        })
    return out


def covariate_frame(ids: list[str], batches: list[str]) -> tuple[pd.DataFrame, list[str]]:
    stats_cfg, _, _ = _stats._load_stats_config()
    expected = pd.Series(batches, index=ids)
    frame, names = _stats._load_covariates(stats_cfg, ids, expected)
    return frame.set_index("sample_id"), names


def covariate_block(values: dict[str, float], train: pd.DataFrame, names: list[str],
                    evidence: list[dict[str, str]]) -> dict[str, Any]:
    out = {}
    for n in names:
        p05, p95 = float(np.quantile(train[n], 0.05)), float(np.quantile(train[n], 0.95))
        v = float(values[n])
        flag = bool(v < p05 or v > p95)
        out[n] = {"value": v, "training_p05": p05, "training_p95": p95, "flag": flag,
                  "justification": {"rule": COVARIATE_RULE,
                                    "numbers": {"value": v, "training_p05": p05, "training_p95": p95,
                                                "n_training_images": int(len(train)), "flag": flag},
                                    "evidence": evidence}}
    return out


def feature_status() -> dict[str, str]:
    fs = pd.read_csv(_config.ROOT / "results" / "stats" / "feature_status.csv")
    fs = fs[fs["table"] == "features"]
    return dict(zip(fs["feature"], fs["status"]))


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return centre - half, centre + half


RELIABILITY_RULE = (
    "Reported, not a rule change: precision of the frozen model's LOIO bets on the same predicted batch "
    "(and within the same tier), from results/v1/loio_predictions.csv, excluding this image."
)


def loio_reliability(pred_batch: str, tier_name: str, exclude: str | None) -> dict[str, Any]:
    t = pd.read_csv(_config.ROOT / OUT_DIR / "loio_predictions.csv")
    t = t[t["sample_id"] != exclude]
    same = t[t["pred_batch"] == pred_batch]
    same_tier = same[same["tier"] == tier_name]
    return {
        "pred_batch_correct": int(same["correct"].sum()), "pred_batch_n": int(len(same)),
        "pred_batch_tier_correct": int(same_tier["correct"].sum()), "pred_batch_tier_n": int(len(same_tier)),
        "selector_pred_batch": f"pred_batch == '{pred_batch}' and sample_id != '{exclude}'",
        "selector_pred_batch_tier": f"pred_batch == '{pred_batch}' and tier == '{tier_name}' and sample_id != '{exclude}'",
    }


def predict_one(model: Model, xf: np.ndarray, xe: np.ndarray, status: dict[str, str]) -> dict[str, Any]:
    z = transform(model.scaler, model.pca, xf, xe)[0]
    proba = model.lr.predict_proba(z[None, :])[0]
    order = np.argsort(-proba, kind="stable")
    pred, runner = BATCHES[order[0]], BATCHES[order[1]]
    return {
        "pred_batch": pred, "runner_up": runner,
        "probabilities": {b: float(p) for b, p in zip(BATCHES, proba)},
        "confidence": float(proba[order[0]]), "margin": float(proba[order[0]] - proba[order[1]]),
        "drivers": drivers(model, z, np.asarray(xf, dtype=np.float64), pred, status),
    }


def image_document(
    *, sample_id: str, true_batch: str | None, n_tiles: int | None, pred: dict[str, Any],
    ood_res: dict[str, Any], perm_p: float, loio_k: int, loio_n: int, covariates: dict[str, Any],
    detectors: list[str], evidence_file: str, selector: str, cfg: dict[str, Any], frozen: bool,
    exploratory: bool, git_tag: str | None, kind_note: str,
) -> dict[str, Any]:
    t, t_reason = tier(pred["confidence"], perm_p, ood_res["label"])
    rel = loio_reliability(pred["pred_batch"], t, sample_id)
    ev_row = [{"file": evidence_file, "selector": selector}]
    model_ev = [{"file": "results/v1/loio_summary.json", "selector": "loio_accuracy, permutation_p"},
                {"file": "results/v1/final_model.csv", "selector": "all rows"},
                {"file": LOG_PATH, "selector": "Frozen choices"}]
    probs = pred["probabilities"]
    top = pred["drivers"]
    driver_txt = ", ".join(f"{d['name']} ({d['effect_size']:+.2f})" for d in top)
    acq_flags = [n for n, c in covariates.items() if c["flag"]]
    mainly_acq = sum(d["tag"] == EMBEDDING_TAG for d in top) >= 2
    reason = (
        f"Bet {pred['pred_batch']} with p={pred['confidence']:.3f} (runner-up {pred['runner_up']} "
        f"p={probs[pred['runner_up']]:.3f}, margin {pred['margin']:.3f}); tier {t} because {t_reason}. "
        f"In LOIO (this image excluded), bets on {pred['pred_batch']} were right "
        f"{rel['pred_batch_correct']}/{rel['pred_batch_n']}, and {rel['pred_batch_tier_correct']}/"
        f"{rel['pred_batch_tier_n']} at tier {t}. "
        f"Top drivers: {driver_txt}."
        + (" Most top drivers are embedding components, whose batch signal could not be separated from "
           "acquisition in Phase B; the bet stands." if mainly_acq else "")
        + f" Batch_3 embedding check: E1={ood_res['e1_to_batch3']:.4f} vs band95 {ood_res['band95']:.4f} / "
          f"band99 {ood_res['band99']:.4f} -> {ood_res['label']}"
        + (" (outside the Batch_3 distribution; the bet still stands)." if ood_res["label"] == "outside_bounds" else ".")
        + (f" Acquisition covariates outside the training 5-95 % range: {', '.join(acq_flags)}." if acq_flags else "")
    )
    if ood_res["label"] == "outside_bounds":
        stakeholder, route = "materials_expert_review", "BSE embedding above the Batch_3 upper band (band99)"
    elif acq_flags:
        stakeholder, route = "microscopy_team", f"acquisition covariates out of training range: {', '.join(acq_flags)}"
    else:
        stakeholder, route = "none", "at or below the Batch_3 upper band (band99) and no acquisition covariate flagged"
    next_action = {
        "materials_expert_review": "Review this image against Batch_3 before accepting the material; "
                                   "check acquisition settings first.",
        "microscopy_team": "Check the acquisition settings for this image before interpreting the bet.",
        "none": "No action beyond recording the bet.",
    }[stakeholder]
    lo, hi = wilson(loio_k, loio_n)
    return {
        "subject": {"kind": "image", "id": sample_id, "batch": true_batch, "n_images": 1,
                    **({"n_tiles": int(n_tiles)} if n_tiles is not None else {}), "note": kind_note},
        "verdict": {
            "label": ood_res["label"], "rule": OOD_RULE, "reason": reason,
            "closed_set": {
                "predicted_batch": pred["pred_batch"], "confidence": pred["confidence"],
                "probabilities": probs, "runner_up": pred["runner_up"], "margin": pred["margin"],
                "tier": t, "note": "assumes the image is from one of the known batches",
                "justification": {
                    "rule": f"{BET_RULE} Tier: {TIER_RULE} Model: {MODEL_RULE}",
                    "numbers": {**probs, "margin": pred["margin"], "tier_reason": t_reason,
                                "loio_accuracy": f"{loio_k}/{loio_n}", "loio_permutation_p": perm_p,
                                "chance_majority": "17/31", "ood_label": ood_res["label"],
                                "loio_reliability": {k: v for k, v in rel.items() if not k.startswith("selector")}},
                    "evidence": ev_row + model_ev + [
                        {"file": "results/v1/loio_predictions.csv", "selector": rel["selector_pred_batch"],
                         "rule": RELIABILITY_RULE},
                        {"file": "results/v1/loio_predictions.csv", "selector": rel["selector_pred_batch_tier"]}]},
            },
            "open_set": {
                "nearest_batch": ood_res["nearest_batch"],
                "distance_to_each_batch": ood_res["distance_to_each_batch"],
                "null_band_95": ood_res["band95"], "null_band_99": ood_res["band99"],
                "matches_known_batch": ood_res["matches_known_batch"],
                "justification": {"rule": OOD_RULE,
                                  "numbers": {k: ood_res[k] for k in ("e1_to_batch3", "band95", "band99",
                                                                     "n_reference", "null_max", "rank_p",
                                                                     "n_null")},
                                  "evidence": ev_row + [{"file": "results/emb_per_image.parquet",
                                                         "selector": "channel == 'BSE'"}]},
            },
            "justification": {"rule": OOD_RULE,
                              "numbers": {"e1_to_batch3": ood_res["e1_to_batch3"], "band95": ood_res["band95"],
                                          "band99": ood_res["band99"]},
                              "evidence": ev_row},
        },
        "pipeline": {
            "git_sha": _config.git_sha(), "git_tag": git_tag, "config_path": cfg["_path"],
            "config_hash": cfg["_hash"], "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "frozen": frozen, "exploratory": exploratory,
            "model_revisions": {"dinov2_hub_ref": str(cfg["embeddings"]["hub_ref"]),
                                "dinov2_weights_sha256": str(cfg["embeddings"]["weights_sha256"]),
                                "classifier": MODEL_RULE},
        },
        "acquisition": {"detectors_present": detectors, "pixel_size_nm": None, "pixel_size_confirmed": False,
                        "covariates": covariates, "acquisition_drift_suspected": bool(acq_flags)},
        "evidence": {
            "drivers": [{**d, "justification": {"rule": DRIVER_RULE,
                                                "numbers": {"coefficient": d["coefficient"],
                                                            "model_input": d["model_input"],
                                                            "contribution": d["effect_size"]},
                                                "evidence": ev_row + model_ev[1:2]}} for d in top],
            "embedding": {"backbone": "dinov2_vits14", "energy_distance": ood_res["e1_to_batch3"]},
        },
        "uncertainty": {
            "sampling": f"model trained on n=31 images; LOIO accuracy {loio_k}/{loio_n} "
                        f"(Wilson 95 % CI {lo:.2f}-{hi:.2f}), permutation p={perm_p:.4f}",
            "segmentation": "F-feature drivers carry their Phase B status; 17/23 Phase B features were "
                            "dropped for +/-10 % threshold sensitivity (results/stats/feature_status.csv)",
            "decision_margin": f"probability margin {pred['margin']:.3f} to {pred['runner_up']}; "
                               f"E1 is {ood_res['margin_to_band99']:+.4f} from band99",
        },
        "routing": {"stakeholder": stakeholder, "reason": route},
        "next_action": next_action,
        "caveats": [
            f"phase_identity: {PHASE_IDENTITY}; Si vs SiOx is indistinguishable in BSE; binder and "
            "conductive additive are lumped.",
            "Pixel size unconfirmed; all lengths in px.",
            "Embedding batch differences vanished after acquisition residualisation in Phase B; "
            "embedding drivers may reflect acquisition rather than material.",
            "Batch_1 / Batch_2 are variations relative to the Batch_3 baseline, not better or worse.",
        ],
    }


def validate(doc: dict[str, Any]) -> None:
    import jsonschema

    schema = json.loads((_config.ROOT / "schema" / "verdict.schema.json").read_text())
    jsonschema.validate(doc, schema)


def final_model(frame: pd.DataFrame) -> Model:
    xf, xe, y = _arrays(frame)
    return fit(xf, xe, y)


def coefficient_table(model: Model) -> pd.DataFrame:
    rows = []
    for k, b in enumerate(BATCHES):
        rows.append({"batch": b, "term": "intercept", "coefficient": float(model.lr.intercept_[k])})
        for name, c in zip(design_names(), model.lr.coef_[k]):
            rows.append({"batch": b, "term": name, "coefficient": float(c)})
    return pd.DataFrame(rows)


def check_frozen_model(model: Model) -> float:
    committed = pd.read_csv(_config.ROOT / OUT_DIR / "final_model.csv")
    now = coefficient_table(model)
    diff = float(np.max(np.abs(committed["coefficient"].to_numpy() - now["coefficient"].to_numpy())))
    if list(committed["term"]) != list(now["term"]) or diff > COEF_TOL:
        raise RuntimeError(f"refit final model differs from results/v1/final_model.csv (max |diff| {diff:.3g})")
    return diff


def run(cfg: dict[str, Any]) -> None:
    out = _config.ROOT / OUT_DIR
    (out / "loio_images").mkdir(parents=True, exist_ok=True)
    frame = load_training()
    ids = frame["sample_id"].tolist()
    xf, xe, y = _arrays(frame)
    units = unit(xe)
    status = feature_status()
    cov, cov_names = covariate_frame(ids, frame["batch"].tolist())
    n_tiles = pd.read_parquet(_config.ROOT / "results" / "kpi_per_image.parquet").set_index("sample_id")["n_tiles"]
    detectors = (pd.read_parquet(_config.ROOT / "results" / "artefacts_per_image.parquet")
                 .groupby("sample_id")["channel"].apply(lambda s: sorted(s)).to_dict())

    designs = fold_designs(xf, xe)
    rows, preds = [], []
    for i, sid in enumerate(ids):
        train = np.delete(np.arange(len(ids)), i)
        model = fit(xf[train], xe[train], y[train])
        z_train, z_test = designs[i]
        if not np.allclose(transform(model.scaler, model.pca, xf[i], xe[i]), z_test):
            raise AssertionError("fold design mismatch")
        pred = predict_one(model, xf[i], xe[i], status)
        o = ood(units[i], units[train], y[train])
        preds.append((pred, o, train))
        rows.append({
            "sample_id": sid, "true_batch": y[i], "pred_batch": pred["pred_batch"],
            "correct": bool(pred["pred_batch"] == y[i]),
            **{f"p_{b}": pred["probabilities"][b] for b in BATCHES},
            "confidence": pred["confidence"], "runner_up": pred["runner_up"], "margin": pred["margin"],
            **{f"driver{j + 1}": d["name"] for j, d in enumerate(pred["drivers"])},
            **{f"driver{j + 1}_contribution": d["effect_size"] for j, d in enumerate(pred["drivers"])},
            "ood_e1": o["e1_to_batch3"], "ood_band95": o["band95"], "ood_band99": o["band99"],
            "ood_label": o["label"], "matches_known_batch": o["matches_known_batch"],
            "nearest_batch_e1": o["nearest_batch"],
        })
    table = pd.DataFrame(rows)
    k = int(table["correct"].sum())
    observed = k / len(ids)
    if not math.isclose(observed, loio_accuracy(designs, y)):
        raise AssertionError("fast LOIO path disagrees with the full LOIO")
    perm_p, perm_accs = permutation_p(designs, y, observed)

    tiers = [tier(pred["confidence"], perm_p, o["label"])[0] for pred, o, _ in preds]
    table["tier"] = tiers
    table = _config.stamp(table, cfg)
    table.to_csv(out / "loio_predictions.csv", index=False)
    for i, sid in enumerate(ids):
        pred, o, train = preds[i]
        cov_block = covariate_block(cov.loc[sid].to_dict(), cov.loc[[ids[j] for j in train]], cov_names,
                                    [{"file": "results/artefacts_per_image.parquet", "selector": f"sample_id == '{sid}'"},
                                     {"file": "results/audit/images.csv", "selector": f"sample_id == '{sid}'"}])
        doc = image_document(
            sample_id=sid, true_batch=y[i], n_tiles=int(n_tiles[sid]), pred=pred, ood_res=o, perm_p=perm_p,
            loio_k=k, loio_n=len(ids), covariates=cov_block, detectors=detectors[sid],
            evidence_file="results/v1/loio_predictions.csv", selector=f"sample_id == '{sid}'", cfg=cfg,
            frozen=False, exploratory=False, git_tag=None,
            kind_note="training image, out-of-fold (leave-one-image-out) prediction",
        )
        validate(doc)
        (out / "loio_images" / f"{sid}.json").write_text(json.dumps(doc, indent=2) + "\n")

    cm = pd.crosstab(pd.Categorical(table["true_batch"], BATCHES), pd.Categorical(table["pred_batch"], BATCHES),
                     rownames=["true"], colnames=["pred"], dropna=False)
    cm.to_csv(out / "confusion_matrix.csv")
    lo, hi = wilson(k, len(ids))
    summary = {
        "n_images": len(ids), "loio_correct": k, "loio_accuracy": observed, "loio_accuracy_str": f"{k}/{len(ids)}",
        "wilson95": [lo, hi], "chance_majority": 17 / 31,
        "per_batch_recall": {b: f"{int(((table.true_batch == b) & table.correct).sum())}/{int((table.true_batch == b).sum())}"
                             for b in BATCHES},
        "balanced_accuracy": float(np.mean([((table.true_batch == b) & table.correct).sum() / (table.true_batch == b).sum()
                                            for b in BATCHES])),
        "permutation_p": perm_p, "n_permutations": N_PERMUTATIONS, "permutation_seed": SEED,
        "permutation_acc_median": float(np.median(perm_accs)), "permutation_acc_p95": float(np.quantile(perm_accs, 0.95)),
        "confusion_matrix": {"rows_true_cols_pred": BATCHES, "values": cm.to_numpy().tolist()},
        "tier_counts": pd.Series(tiers).value_counts().to_dict(),
        "precision_by_pred_batch": {b: f"{int(table[table.pred_batch == b].correct.sum())}/{int((table.pred_batch == b).sum())}"
                                    for b in BATCHES},
        "precision_by_pred_batch_tier": {f"{b}|{t}": f"{int(g.correct.sum())}/{len(g)}"
                                         for (b, t), g in table.groupby(["pred_batch", "tier"])},
        "accuracy_by_tier": {t: f"{int(g.correct.sum())}/{len(g)}" for t, g in table.groupby("tier")},
        "ood_label_counts": table["ood_label"].value_counts().to_dict(),
        "model": MODEL_RULE, "n_pcs": N_PCS, "frozen_choices": LOG_PATH,
        "config_hash": cfg["_hash"], "git_sha": _config.git_sha(),
    }
    (out / "loio_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    _config.stamp(coefficient_table(final_model(frame)), cfg).to_csv(out / "final_model.csv", index=False)
    print(f"classify: LOIO {k}/{len(ids)} (perm p={perm_p:.4f}); confusion\n{cm}\n-> {OUT_DIR}/")

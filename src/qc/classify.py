"""Batch identification and out-of-distribution screening (classify). Owner: P1.

Usage: python -m qc classify --features results/features/features_f01_f11.parquet [--heldout new_images.parquet]

The judged question (Polaron, docs/READ/Polaron Clarification Batch Baseline and Judging.md): what differs between
the batches, and can a held-back image be categorised as Batch_1 / Batch_2 / Batch_3, or as matching none of them
(out of the Batch_3 baseline distribution)? This stage answers it per *feature family* so the driver of any
separation is named: `material` (the feature columns of the table), `acquisition` (the artefact covariates),
`material+acquisition`. Embedding tables can be passed as a further family with --extra.

Reads:  the image-level feature table, results/artefacts_per_image.parquet, results/audit/images.csv
Writes: results/classify/<table-name>/
        accuracy.csv     family x split (LOIO, LOGO) x model: accuracy, balanced accuracy, per-batch recall,
                         majority chance, permutation null (labels shuffled at image level) mean / 95th pct / p
        predictions.csv  out-of-fold prediction and class probabilities per image x family x split
        drivers.csv      standardised logistic-regression coefficients averaged over LOIO folds, per feature x
                         batch, tagged material / acquisition - the "what differs" table
        ood.csv          per image x family: robust distance to each batch (leave-self-out when the image is in
                         that batch), calibrated against that batch's own leave-one-out distances;
                         `nearest_batch`, `in_distribution_of`, `matches_none`
        heldout.csv      (with --heldout) frozen-model prediction + OOD screen for new images, with provenance
        CLASSIFY.md      summary

Hard rules (docs/FRAMEWORK.md Section 00): the image is the unit; folds and permutations act on whole images and on
whole acquisition groups for LOGO; imputer/scaler/model are fitted inside each fold; LOIO is the estimate for
held-back images from the *same* sessions, LOGO for a genuinely new session; accuracy is never reported without
its permutation null and the majority-chance baseline; no good/bad claim follows from a batch label.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from qc import config as _config
from qc.validate import (COVARIATES, REFERENCE_BATCH, _model, assemble, grouped_folds, mad, read_table, sha256)

OOD_ALPHA = 0.05  # an image is "in distribution" of a batch if its distance is not beyond that batch's LOO (1-alpha) quantile


# ---------------------------------------------------------------------------------------------------- families
def families(df: pd.DataFrame, feats: list[str], extra: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    covs = [c for c in COVARIATES if c in df.columns]
    fam = {"material": list(feats), "acquisition": covs, "material+acquisition": list(feats) + covs}
    for name, cols in (extra or {}).items():
        fam[name] = list(cols)
        fam[f"{name}+acquisition"] = list(cols) + covs
    return {k: v for k, v in fam.items() if v}


def tag(col: str) -> str:
    return "acquisition" if col in COVARIATES else "material"


# -------------------------------------------------------------------------------------------------- classifier
def oof_predict(X: np.ndarray, y: np.ndarray, units: pd.Series, kind: str, seed: int,
                classes: list[str]) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    """Out-of-fold labels, class probabilities (n x k) and per-fold standardised coefficients (logreg only)."""
    pred = np.empty(len(y), dtype=object)
    proba = np.full((len(y), len(classes)), np.nan)
    coefs = []
    for train, test in grouped_folds(units):
        assert not set(train) & set(test)
        m = _model(kind, seed).fit(X[train], y[train])
        pred[test] = m.predict(X[test])
        p = m.predict_proba(X[test])
        for j, c in enumerate(m.classes_):
            proba[test, classes.index(c)] = p[:, j]
        if kind == "logreg":
            coefs.append(m[-1].coef_)  # inputs are standardised by the pipeline scaler, so coefficients are comparable
    return pred, proba, coefs


def _scores(pred: np.ndarray, y: np.ndarray, classes: list[str]) -> dict[str, float]:
    return {"accuracy": float((pred == y).mean()),
            "balanced_accuracy": float(np.mean([(pred[y == c] == c).mean() for c in classes])),
            **{f"recall_{c}": float((pred[y == c] == c).mean()) for c in classes}}


def permutation_null(X: np.ndarray, y: np.ndarray, units: pd.Series, kind: str, seed: int, classes: list[str],
                     n_perm: int, rng: np.random.Generator) -> np.ndarray:
    """Accuracy under image-level label shuffling (the whole image, i.e. all its detector views, keeps one label)."""
    null = np.empty(n_perm)
    for i in range(n_perm):
        yp = rng.permutation(y)
        pred, _, _ = oof_predict(X, yp, units, kind, seed, classes)
        null[i] = (pred == yp).mean()
    return null


def batch_id(df: pd.DataFrame, fams: dict[str, list[str]], seed: int, n_perm: int, models: Iterable[str] = ("logreg",)
             ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    y = df["batch"].to_numpy()
    classes = sorted(pd.unique(y))
    chance = float(max((y == c).mean() for c in classes))
    acc_rows, pred_rows, drv_rows = [], [], []
    for fam, cols in fams.items():
        X = df[cols].to_numpy(float)
        for kind in models:
            for split, units in (("LOIO", df["sample_id"]), ("LOGO", df["acq_group"])):
                pred, proba, coefs = oof_predict(X, y, units, kind, seed, classes)
                null = permutation_null(X, y, units, kind, seed, classes, n_perm, rng) if n_perm else np.array([np.nan])
                sc = _scores(pred, y, classes)
                acc_rows.append({"family": fam, "model": kind, "split": split, "n_images": len(y),
                                 "n_folds": len(pd.unique(units)), "n_features": len(cols), **sc, "chance_majority": chance,
                                 "null_mean": float(np.mean(null)) if n_perm else np.nan,
                                 "null_p95": float(np.percentile(null, 95)) if n_perm else np.nan,
                                 "p_perm": float((1 + np.sum(null >= sc["accuracy"] - 1e-12)) / (len(null) + 1)) if n_perm else np.nan,
                                 "n_perm": n_perm})
                for i, sid in enumerate(df["sample_id"]):
                    pred_rows.append({"sample_id": sid, "batch": y[i], "family": fam, "model": kind, "split": split,
                                      "pred": pred[i], "correct": bool(pred[i] == y[i]),
                                      **{f"p_{c}": float(proba[i, j]) for j, c in enumerate(classes)}})
                if coefs and split == "LOIO":
                    C = np.mean(np.stack(coefs), axis=0)  # (k, n_cols); binary logreg gives (1, n_cols)
                    for j, col in enumerate(cols):
                        for k, c in enumerate(classes if C.shape[0] > 1 else classes[-1:]):
                            drv_rows.append({"family": fam, "feature": col, "driver_type": tag(col), "batch": c,
                                             "coef_std": float(C[k, j]), "abs_coef_std": float(abs(C[k, j]))})
    drv = pd.DataFrame(drv_rows)
    if len(drv):
        drv = drv.sort_values(["family", "batch", "abs_coef_std"], ascending=[True, True, False]).reset_index(drop=True)
        drv["rank_in_batch"] = drv.groupby(["family", "batch"]).cumcount() + 1
    return pd.DataFrame(acc_rows), pd.DataFrame(pred_rows), drv


# ---------------------------------------------------------------------------------------------------------- OOD
def robust_distance(x: np.ndarray, ref: np.ndarray) -> float:
    """RMS robust z of x against the reference rows (median / MAD per column; NaN-safe; constant columns skipped)."""
    med = np.nanmedian(ref, axis=0)
    m = np.array([mad(ref[:, j]) for j in range(ref.shape[1])])
    ok = np.isfinite(x) & np.isfinite(med) & (m > 0)
    if not ok.any():
        return np.nan
    z = (x[ok] - med[ok]) / m[ok]
    return float(np.sqrt(np.mean(z ** 2)))


def batch_loo_distances(X: np.ndarray, idx: np.ndarray) -> np.ndarray:
    return np.array([robust_distance(X[i], X[np.setdiff1d(idx, [i])]) for i in idx])


def ood_table(df: pd.DataFrame, fams: dict[str, list[str]], reference: str = REFERENCE_BATCH,
              alpha: float = OOD_ALPHA) -> pd.DataFrame:
    """Distance of every image to every batch. For an image inside batch b the distance to b is leave-self-out; the
    calibration null for batch b is the LOO distance distribution of b's own images, so p_b = fraction of b's LOO
    distances >= d (an image is in distribution of b if p_b >= alpha). `matches_none` = in distribution of no batch."""
    batches = sorted(df["batch"].unique())
    rows = []
    for fam, cols in fams.items():
        X = df[cols].to_numpy(float)
        idx = {b: np.flatnonzero(df["batch"].values == b) for b in batches}
        loo = {b: batch_loo_distances(X, idx[b]) for b in batches}
        for i, sid in enumerate(df["sample_id"]):
            row: dict[str, Any] = {"sample_id": sid, "batch": df["batch"].iat[i], "family": fam, "n_features": len(cols)}
            for b in batches:
                ref_idx = np.setdiff1d(idx[b], [i])
                d = robust_distance(X[i], X[ref_idx])
                null = loo[b][idx[b] != i] if df["batch"].iat[i] == b else loo[b]
                p = float((np.sum(null >= d - 1e-12)) / len(null)) if len(null) and np.isfinite(d) else np.nan
                row[f"d_{b}"] = d
                row[f"p_{b}"] = p
                row[f"n_ref_{b}"] = int(len(ref_idx))
            ds = {b: row[f"d_{b}"] for b in batches}
            ps = {b: row[f"p_{b}"] for b in batches}
            row["nearest_batch"] = min(ds, key=lambda b: (np.inf if np.isnan(ds[b]) else ds[b]))
            inside = [b for b in batches if np.isfinite(ps[b]) and ps[b] >= alpha]
            row["in_distribution_of"] = "|".join(inside) if inside else "none"
            row["matches_none"] = not inside
            row["in_reference"] = bool(np.isfinite(ps[reference]) and ps[reference] >= alpha)
            rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------------ held-out
def score_heldout(df: pd.DataFrame, held: pd.DataFrame, fams: dict[str, list[str]], seed: int, kind: str = "logreg",
                  alpha: float = OOD_ALPHA) -> pd.DataFrame:
    """Frozen models (fitted on all known images) applied to new rows; OOD screen against each batch's LOO null."""
    y = df["batch"].to_numpy()
    batches = sorted(pd.unique(y))
    rows = []
    for fam, cols in fams.items():
        missing = [c for c in cols if c not in held.columns]
        if missing:
            raise ValueError(f"held-out table lacks columns for family {fam}: {missing}")
        X, Xh = df[cols].to_numpy(float), held[cols].to_numpy(float)
        m = _model(kind, seed).fit(X, y)
        pred, proba = m.predict(Xh), m.predict_proba(Xh)
        idx = {b: np.flatnonzero(y == b) for b in batches}
        loo = {b: batch_loo_distances(X, idx[b]) for b in batches}
        for i, sid in enumerate(held["sample_id"]):
            row: dict[str, Any] = {"sample_id": sid, "family": fam, "model": kind, "pred_batch": pred[i],
                                   **{f"p_{c}": float(proba[i, j]) for j, c in enumerate(m.classes_)}}
            for b in batches:
                d = robust_distance(Xh[i], X[idx[b]])
                row[f"d_{b}"] = d
                row[f"p_ood_{b}"] = float(np.sum(loo[b] >= d - 1e-12) / len(loo[b])) if np.isfinite(d) else np.nan
            inside = [b for b in batches if np.isfinite(row[f"p_ood_{b}"]) and row[f"p_ood_{b}"] >= alpha]
            row["in_distribution_of"] = "|".join(inside) if inside else "none"
            row["matches_none"] = not inside
            row["verdict"] = ("matches none of the known batches -> investigate" if not inside else
                              f"in distribution of {row['in_distribution_of']}; classifier says {pred[i]}")
            rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------------- report
def _md(df: pd.DataFrame, floatfmt: str = ".3g") -> str:
    return df.to_markdown(index=False, floatfmt=floatfmt)


def write_report(out: Path, name: str, acc: pd.DataFrame, drv: pd.DataFrame, ood: pd.DataFrame,
                 held: pd.DataFrame | None, prov: dict[str, Any]) -> None:
    batches = sorted(ood["batch"].unique())
    summ = ood.groupby(["family", "batch"]).agg(n=("sample_id", "size"), matches_none=("matches_none", "sum"),
                                                in_reference=("in_reference", "sum")).reset_index()
    top = (drv[drv["rank_in_batch"] <= 3][["family", "batch", "rank_in_batch", "feature", "driver_type", "coef_std"]]
           if len(drv) else pd.DataFrame())
    lines = [f"# Batch identification and OOD screen: `{name}`", "",
             f"Provenance: {', '.join(f'{k}={v}' for k, v in prov.items())}", "",
             "Target (Polaron): what differs between batches; categorise held-back images as Batch_1/2/3 or `matches none`. "
             f"{REFERENCE_BATCH} is the supplier's promised baseline; Batch_1/2 are different, not worse. No good/bad claim follows.",
             "",
             "Reading guide: LOIO = estimate for held-back images from the same acquisition sessions; LOGO = estimate for a new "
             "session. `p_perm` is the image-level label-permutation p of the accuracy; an accuracy inside the null band means "
             "the family does not identify the batch. Drivers are standardised logistic-regression coefficients tagged "
             "material or acquisition, so a separation is never reported without saying what carries it.",
             "", "## Accuracy per feature family", "",
             _md(acc[["family", "model", "split", "n_features", "accuracy", "balanced_accuracy", "chance_majority",
                      "null_mean", "null_p95", "p_perm"] + [f"recall_{b}" for b in batches]]),
             "", "## Top-3 drivers per batch (LOIO, logreg)", "", _md(top) if len(top) else "n/a",
             "", f"## Out-of-distribution screen (robust RMS z to each batch, alpha = {OOD_ALPHA})", "",
             _md(summ),
             "", "Per image: `ood.csv` (`in_distribution_of`, `matches_none`, `in_reference`)."]
    if held is not None:
        lines += ["", "## Held-out images (frozen model on all known images)", "",
                  _md(held[["sample_id", "family", "pred_batch", "in_distribution_of", "matches_none", "verdict"]])]
    (out / "CLASSIFY.md").write_text("\n".join(lines) + "\n")


def run_tables(features: pd.DataFrame, artefacts: pd.DataFrame, images: pd.DataFrame, seed: int = 0, n_perm: int = 200,
               models: Iterable[str] = ("logreg",), heldout: pd.DataFrame | None = None,
               extra: dict[str, list[str]] | None = None) -> dict[str, pd.DataFrame]:
    df, feats = assemble(features, artefacts, images)
    fams = families(df, feats, extra)
    acc, pred, drv = batch_id(df, fams, seed, n_perm, models)
    ood = ood_table(df, fams)
    out = {"assembled": df, "accuracy": acc, "predictions": pred, "drivers": drv, "ood": ood, "_fams": fams}
    if heldout is not None:
        out["heldout"] = score_heldout(df, heldout, fams, seed)
    return out


def run(cfg: dict[str, Any], features: str = "results/features/features_f01_f11.parquet", out: str | None = None,
        artefacts: str = "results/artefacts_per_image.parquet", images: str = "results/audit/images.csv",
        heldout: str | None = None, seed: int = 0, n_perm: int = 200, rf: bool = False) -> Path:
    fpath = _config.resolve(features)
    name = fpath.stem
    out_dir = _config.resolve(out) if out else _config.ROOT / "results" / "classify" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    held = None
    if heldout:
        hpath = _config.resolve(heldout)
        held = read_table(hpath)
        if "batch" in held.columns:
            held = held.drop(columns=["batch"])
        held_art = read_table(_config.resolve(artefacts))
        from qc.validate import covariate_table
        cov = covariate_table(held_art)
        held = held.merge(cov[cov["sample_id"].isin(held["sample_id"])], on="sample_id", how="left")
    tabs = run_tables(read_table(fpath), read_table(_config.resolve(artefacts)), read_table(_config.resolve(images)),
                      seed=seed, n_perm=n_perm, models=("logreg", "rf") if rf else ("logreg",), heldout=held)
    for key in ("accuracy", "predictions", "drivers", "ood") + (("heldout",) if held is not None else ()):
        _config.stamp(tabs[key], cfg).to_csv(out_dir / f"{key}.csv", index=False)
    prov = {**_config.provenance(cfg), "features": str(fpath.relative_to(_config.ROOT)) if fpath.is_relative_to(_config.ROOT) else str(fpath),
            "features_sha256": sha256(fpath)[:12], "seed": seed, "n_perm": n_perm, "heldout": heldout or "none"}
    write_report(out_dir, name, tabs["accuracy"], tabs["drivers"], tabs["ood"], tabs.get("heldout"), prov)
    a = tabs["accuracy"].set_index(["family", "split"])["accuracy"]
    print(f"classify: {len(tabs['assembled'])} images, families={list(tabs['_fams'])} -> {out_dir.relative_to(_config.ROOT)}/ "
          f"LOIO material {a.get(('material', 'LOIO'), np.nan):.2f} / acquisition {a.get(('acquisition', 'LOIO'), np.nan):.2f} "
          f"/ both {a.get(('material+acquisition', 'LOIO'), np.nan):.2f}", file=sys.stderr)
    return out_dir

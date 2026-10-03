"""Validation harness for any image-level feature table (validate). Owner: P1.

Usage: python -m qc validate --features results/kpi_per_image.parquet [--out results/validate/<table-name>/]

Reads:  the feature table (one row per image: sample_id, batch, numeric feature columns; `*_sd`, n_tiles and
        provenance columns are ignored as features),
        results/artefacts_per_image.parquet   (acquisition covariates, joined on sample_id),
        results/audit/images.csv              (acquisition group = (height, XResolution tag)),
        results/kpi_sensitivity.parquet       (threshold-perturbation sensitivity, used where a feature has it)
Writes: results/validate/<table-name>/
        stability.csv     per feature: bootstrap rank-stability of batch medians, CV within the reference batch,
                          threshold sensitivity (median over images of the +/-10 % threshold shift)
        confound.csv      per feature: Spearman rho with each acquisition covariate; image-level permutation
                          association with acquisition group vs with batch; `acquisition_confounded` flag
        batch_tests.csv   per feature x (Batch_k vs reference) x (reference set) x (raw / residualised):
                          robust effect size (median shift / MAD of reference), permutation p, BH q
        loio_logo.csv     logistic-regression batch prediction under leave-one-image-out and
                          leave-one-acquisition-group-out, with and without the covariates as inputs
        reference_loo.csv per reference-batch image x feature: robust z against the other reference images
        decisions.csv     keep / drop / investigate per feature with the reasons
        VALIDATION.md     human-readable summary

Hard rules honoured here (docs/FRAMEWORK.md Section 00): the image (8-char sample id) is the independent unit;
every bootstrap, permutation and fold operates on whole images (and on whole acquisition groups for LOGO);
scaling and imputation are fitted inside each fold; artefact covariates are measured and modelled, never used to
alter the images; n is reported on every statistic; `investigate` is a first-class outcome.
Phase names (class 2 = silicon, class 1 = graphite, class 0 = void/pore) are stated by Polaron, not image-verified.
Units are pixels; nm only if 25 nm/px is true.
"""
from __future__ import annotations

import hashlib
import sys
import warnings
from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from qc import config as _config

META_COLS = {"sample_id", "batch", "channel", "detector", "n_tiles", "config_hash", "git_sha", "tile_id", "y", "x",
             "scale", "level", "acq_group"}
COVARIATES = {  # output name: (channel, source column) in results/artefacts_per_image.parquet
    "noise_sigma": ("BSE", "noise_sigma"),
    "sharpness": ("BSE", "sharpness"),
    "curtaining_score": ("BSE", "curtaining_score"),
    "hstripe_score": ("BSE", "hstripe_score"),
    "edge_charging_inlens": ("Inlens", "edge_charging"),
    "mean_grey": ("BSE", "mean"),
}
REFERENCE_BATCH = "Batch_3"
LOO_FLAGGED = ("vc2whyaq", "ufdvpb81", "hzumfsms")  # Batch_3 images flagged by the C4 leave-one-out check
MAD_SCALE = 1.4826
RULE = {"rank_stability_min": 0.7, "sens_to_mad_max": 0.5, "alpha": 0.05, "loo_z": 3.0, "rho_covariate": 0.5}


# ----------------------------------------------------------------------------------------------------------- splits
def grouped_folds(units: Iterable[Any]) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Leave-one-unit-out folds over any label vector. Every row whose unit equals the held-out one is in the test
    fold, so passing sample_id gives leave-one-image-out (also for tile-level tables, where the id repeats) and
    passing the acquisition group gives leave-one-acquisition-group-out. Units are visited in sorted order."""
    units = np.asarray(list(units))
    for u in sorted(pd.unique(units)):
        test = np.flatnonzero(units == u)
        train = np.flatnonzero(units != u)
        yield train, test


def loio_folds(sample_ids: Iterable[str]) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    return grouped_folds(sample_ids)


def logo_folds(acq_groups: Iterable[str]) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    return grouped_folds(acq_groups)


# ----------------------------------------------------------------------------------------------------------- inputs
def read_table(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in META_COLS and not c.endswith("_sd")
            and pd.api.types.is_numeric_dtype(df[c])]


def acquisition_groups(images: pd.DataFrame) -> pd.Series:
    """acq_group = '<height>|<XResolution tag>' per sample_id (the 13 session-like groups of docs/DATA_AUDIT.md)."""
    g = images["height"].astype(str) + "|" + images["res_tag"].astype(str)
    return pd.Series(g.values, index=images["sample_id"].values, name="acq_group")


def covariate_table(artefacts: pd.DataFrame) -> pd.DataFrame:
    """One row per sample_id with the COVARIATES columns; a covariate whose channel is missing for an image falls
    back to the image's BSE value of the same source column (and is NaN if that is missing too)."""
    out = pd.DataFrame(index=sorted(artefacts["sample_id"].unique()))
    for name, (channel, col) in COVARIATES.items():
        primary = artefacts[artefacts["channel"] == channel].set_index("sample_id")[col]
        fallback = artefacts[artefacts["channel"] == "BSE"].set_index("sample_id")[col]
        out[name] = primary.reindex(out.index).fillna(fallback.reindex(out.index))
    out.index.name = "sample_id"
    return out.reset_index()


def assemble(features: pd.DataFrame, artefacts: pd.DataFrame, images: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    if features["sample_id"].duplicated().any():
        raise ValueError("feature table must have exactly one row per sample_id (image-level table)")
    feats = feature_columns(features)
    df = features[["sample_id", "batch"] + feats].merge(covariate_table(artefacts), on="sample_id", how="left",
                                                         validate="one_to_one")
    df["acq_group"] = df["sample_id"].map(acquisition_groups(images))
    if df["acq_group"].isna().any():
        missing = df.loc[df["acq_group"].isna(), "sample_id"].tolist()
        raise ValueError(f"no acquisition group (height, res_tag) for {missing}")
    return df.sort_values(["batch", "sample_id"]).reset_index(drop=True), feats


def threshold_sensitivity(sens: pd.DataFrame | None, feats: list[str]) -> pd.Series:
    """Per feature: median over images of max |f(scaled thresholds) - f(nominal)|; NaN where not measured."""
    out = pd.Series(np.nan, index=feats, name="threshold_sensitivity")
    if sens is None:
        return out
    img = sens[sens["level"] == "image"] if "level" in sens else sens
    nominal = img[np.isclose(img["scale"], 1.0)].set_index("sample_id")
    for f in feats:
        if f not in img.columns:
            continue
        dev = []
        for scale, g in img[~np.isclose(img["scale"], 1.0)].groupby("scale"):
            g = g.set_index("sample_id")
            dev.append((g[f] - nominal[f].reindex(g.index)).abs())
        if dev:
            out[f] = float(pd.concat(dev, axis=1).max(axis=1).median())
    return out


# ------------------------------------------------------------------------------------------------------- statistics
def mad(x: np.ndarray) -> float:
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    return float(MAD_SCALE * np.median(np.abs(x - np.median(x)))) if len(x) else np.nan


def rank_stability(df: pd.DataFrame, feats: list[str], rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    """Image-level bootstrap within each batch; Spearman between the observed ranking of batch medians and the
    ranking in each resample, averaged over resamples (plus the fraction of resamples with the identical order)."""
    batches = sorted(df["batch"].unique())
    idx = {b: np.flatnonzero(df["batch"].values == b) for b in batches}
    X = df[feats].to_numpy(float)
    obs = np.vstack([np.nanmedian(X[idx[b]], axis=0) for b in batches])  # (n_batch, n_feat)
    obs_rank = stats.rankdata(obs, axis=0)
    boot_rank = np.empty((n_boot, len(batches), len(feats)))
    for i in range(n_boot):
        med = [np.nanmedian(X[rng.choice(idx[b], size=len(idx[b]), replace=True)], axis=0) for b in batches]
        boot_rank[i] = stats.rankdata(np.vstack(med), axis=0)
    rows = []
    for j, f in enumerate(feats):
        if np.isnan(obs[:, j]).any() or len(batches) < 2 or np.ptp(obs[:, j]) == 0:
            rho = np.full(n_boot, np.nan)
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", stats.ConstantInputWarning)  # tied medians in a resample -> rho undefined -> 0
                rho = np.array([stats.spearmanr(obs_rank[:, j], boot_rank[i, :, j]).statistic for i in range(n_boot)])
            rho = np.nan_to_num(rho, nan=0.0)
        same = np.mean([(boot_rank[i, :, j] == obs_rank[:, j]).all() for i in range(n_boot)])
        rows.append({"feature": f, "rank_stability": float(np.mean(rho)) if np.isfinite(rho).all() else np.nan,
                     "rank_order_preserved_frac": float(same),
                     **{f"median_{b}": float(obs[k, j]) for k, b in enumerate(batches)}})
    return pd.DataFrame(rows)


def _kw_h(ranks: np.ndarray, onehot: np.ndarray, sizes: np.ndarray) -> np.ndarray:
    """Kruskal-Wallis H for each row of `ranks` (n_perm x n) given group one-hot (n x k). No tie correction;
    the permutation null carries the same ties, so p is exact anyway."""
    n = ranks.shape[1]
    sums = ranks @ onehot
    return 12.0 / (n * (n + 1)) * ((sums ** 2) / sizes).sum(axis=1) - 3 * (n + 1)


def perm_association(x: np.ndarray, labels: np.ndarray, rng: np.random.Generator, n_perm: int) -> dict[str, float]:
    """Image-level permutation test of association between a feature and a categorical label (Kruskal-Wallis H).
    Returns the observed H, its permutation p, and the null-standardised z (comparable across label sets with
    different numbers of levels, which raw H is not)."""
    ok = ~np.isnan(x)
    x, labels = x[ok], labels[ok]
    codes, uniq = pd.factorize(labels)
    if len(uniq) < 2 or len(x) < 3 or np.ptp(x) == 0:
        return {"H": np.nan, "p": np.nan, "z": np.nan}
    onehot = np.eye(len(uniq))[codes]
    sizes = onehot.sum(axis=0)
    r = stats.rankdata(x)
    h_obs = _kw_h(r[None, :], onehot, sizes)[0]
    perm = rng.permuted(np.tile(r, (n_perm, 1)), axis=1)
    h_null = _kw_h(perm, onehot, sizes)
    p = (1 + np.sum(h_null >= h_obs - 1e-12)) / (n_perm + 1)
    sd = h_null.std()
    z = (h_obs - h_null.mean()) / sd if sd > 0 else np.nan
    return {"H": float(h_obs), "p": float(p), "z": float(z)}


def perm_association_within(x: np.ndarray, labels: np.ndarray, strata: np.ndarray, rng: np.random.Generator,
                            n_perm: int) -> float:
    """Permutation p for `labels` explaining the feature beyond `strata`: the feature is centred on the stratum
    median and label assignments are shuffled within each stratum (image-level)."""
    ok = ~np.isnan(x)
    x, labels, strata = x[ok], labels[ok], strata[ok]
    codes, uniq = pd.factorize(labels)
    if len(uniq) < 2 or np.ptp(x) == 0:
        return np.nan
    resid = x.copy()
    for s in np.unique(strata):
        m = strata == s
        resid[m] = x[m] - np.median(x[m])
    r = stats.rankdata(resid)
    onehot = np.eye(len(uniq))[codes]
    sizes = onehot.sum(axis=0)
    h_obs = _kw_h(r[None, :], onehot, sizes)[0]
    perm_codes = np.tile(codes, (n_perm, 1))
    for s in np.unique(strata):
        m = np.flatnonzero(strata == s)
        if len(m) > 1:
            perm_codes[:, m] = rng.permuted(perm_codes[:, m], axis=1)
    h_null = np.empty(n_perm)
    for i in range(n_perm):
        oh = np.eye(len(uniq))[perm_codes[i]]
        h_null[i] = _kw_h(r[None, :], oh, oh.sum(axis=0))[0]
    return float((1 + np.sum(h_null >= h_obs - 1e-12)) / (n_perm + 1))


def confound(df: pd.DataFrame, feats: list[str], rng: np.random.Generator, n_perm: int) -> pd.DataFrame:
    covs = [c for c in COVARIATES if c in df.columns]
    rows = []
    for f in feats:
        x = df[f].to_numpy(float)
        row: dict[str, Any] = {"feature": f, "n_images": int(np.isfinite(x).sum())}
        for c in covs:
            y = df[c].to_numpy(float)
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() >= 4 and np.ptp(x[ok]) > 0 and np.ptp(y[ok]) > 0:
                res = stats.spearmanr(x[ok], y[ok])
                row[f"rho_{c}"], row[f"p_{c}"] = float(res.statistic), float(res.pvalue)
            else:
                row[f"rho_{c}"], row[f"p_{c}"] = np.nan, np.nan
        g = perm_association(x, df["acq_group"].to_numpy(), rng, n_perm)
        b = perm_association(x, df["batch"].to_numpy(), rng, n_perm)
        row.update(H_group=g["H"], p_group=g["p"], z_group=g["z"], H_batch=b["H"], p_batch=b["p"], z_batch=b["z"])
        row["p_group_within_batch"] = perm_association_within(x, df["acq_group"].to_numpy(), df["batch"].to_numpy(),
                                                              rng, n_perm)
        rhos = {c: row[f"rho_{c}"] for c in covs}
        finite = [abs(v) for v in rhos.values() if np.isfinite(v)]
        row["max_abs_rho_covariate"] = float(max(finite)) if finite else np.nan
        row["strongest_covariate"] = max(rhos, key=lambda c: abs(np.nan_to_num(rhos[c]))) if covs else ""
        row["covariate_correlated"] = bool(any(abs(np.nan_to_num(rhos[c])) >= RULE["rho_covariate"]
                                               and np.nan_to_num(row[f"p_{c}"], nan=1.0) < RULE["alpha"] for c in covs))
        row["group_stronger_than_batch"] = bool(np.nan_to_num(g["z"], nan=-np.inf) > np.nan_to_num(b["z"], nan=-np.inf))
        row["acquisition_confounded"] = bool(row["group_stronger_than_batch"] and np.nan_to_num(g["p"], nan=1.0) < RULE["alpha"])
        rows.append(row)
    return pd.DataFrame(rows)


def residualise(df: pd.DataFrame, feats: list[str]) -> pd.DataFrame:
    """OLS residuals of each feature on the standardised acquisition covariates (fitted on all images; covariate
    NaNs are median-imputed). Residuals keep the feature's overall median so effect sizes stay on the same scale."""
    covs = [c for c in COVARIATES if c in df.columns]
    C = df[covs].to_numpy(float)
    C = np.where(np.isnan(C), np.nanmedian(C, axis=0), C)
    C = (C - C.mean(axis=0)) / np.where(C.std(axis=0) > 0, C.std(axis=0), 1.0)
    A = np.column_stack([np.ones(len(df)), C])
    out = df[["sample_id", "batch", "acq_group"]].copy()
    for f in feats:
        y = df[f].to_numpy(float)
        ok = np.isfinite(y)
        res = np.full_like(y, np.nan)
        if ok.sum() > A.shape[1]:
            beta, *_ = np.linalg.lstsq(A[ok], y[ok], rcond=None)
            res[ok] = y[ok] - A[ok] @ beta + np.median(y[ok])
        out[f] = res
    return out


def bh_q(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    if ok.sum():
        pv = p[ok]
        order = np.argsort(pv)
        m = len(pv)
        ranked = pv[order] * m / np.arange(1, m + 1)
        q_sorted = np.minimum.accumulate(ranked[::-1])[::-1]
        qq = np.empty(m)
        qq[order] = np.minimum(q_sorted, 1.0)
        q[ok] = qq
    return q


def _two_sample_perm(x: np.ndarray, y: np.ndarray, rng: np.random.Generator, n_perm: int) -> float:
    """Permutation p (image-level) for |median(x) - median(y)|."""
    pooled = np.concatenate([x, y])
    obs = abs(np.median(x) - np.median(y))
    perm = rng.permuted(np.tile(pooled, (n_perm, 1)), axis=1)
    null = np.abs(np.median(perm[:, :len(x)], axis=1) - np.median(perm[:, len(x):], axis=1))
    return float((1 + np.sum(null >= obs - 1e-12)) / (n_perm + 1))


def batch_tests(df: pd.DataFrame, feats: list[str], rng: np.random.Generator, n_perm: int,
                reference: str = REFERENCE_BATCH, exclude: Iterable[str] = LOO_FLAGGED) -> pd.DataFrame:
    exclude = set(exclude)
    tables = {"raw": df, "residualised": residualise(df, feats)}
    rows = []
    for variant, tab in tables.items():
        for refset, ref_rows in (("all", tab[tab["batch"] == reference]),
                                 ("excl_loo_flagged", tab[(tab["batch"] == reference) & ~tab["sample_id"].isin(exclude)])):
            for batch in sorted(b for b in tab["batch"].unique() if b != reference):
                test_rows = tab[tab["batch"] == batch]
                fam = []
                for f in feats:
                    x = test_rows[f].to_numpy(float)
                    r = ref_rows[f].to_numpy(float)
                    x, r = x[np.isfinite(x)], r[np.isfinite(r)]
                    ref_mad = mad(r)
                    shift = np.median(x) - np.median(r) if len(x) and len(r) else np.nan
                    effect = shift / ref_mad if ref_mad and ref_mad > 0 else np.nan
                    p = _two_sample_perm(x, r, rng, n_perm) if len(x) > 1 and len(r) > 1 else np.nan
                    fam.append({"feature": f, "variant": variant, "reference_set": refset, "comparison": f"{batch}_vs_{reference}",
                                "n_test": len(x), "n_ref": len(r), "median_test": float(np.median(x)) if len(x) else np.nan,
                                "median_ref": float(np.median(r)) if len(r) else np.nan, "mad_ref": ref_mad,
                                "median_shift": float(shift), "effect_shift_over_mad": float(effect), "p_perm": p})
                fam_df = pd.DataFrame(fam)
                fam_df["q_bh"] = bh_q(fam_df["p_perm"].to_numpy())
                rows.append(fam_df)
    return pd.concat(rows, ignore_index=True)


def reference_loo(df: pd.DataFrame, feats: list[str], reference: str = REFERENCE_BATCH) -> pd.DataFrame:
    ref = df[df["batch"] == reference].reset_index(drop=True)
    rows = []
    for i, sid in enumerate(ref["sample_id"]):
        others = ref.drop(index=i)
        for f in feats:
            o = others[f].to_numpy(float)
            o = o[np.isfinite(o)]
            med, m = (np.median(o), mad(o)) if len(o) else (np.nan, np.nan)
            v = float(ref.loc[i, f])
            z = (v - med) / m if m and m > 0 else np.nan
            rows.append({"sample_id": sid, "feature": f, "value": v, "median_others": med, "mad_others": m,
                         "n_others": len(o), "robust_z": z, "flag": bool(abs(z) > RULE["loo_z"]) if np.isfinite(z) else False})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------------- classifier
def _model(kind: str, seed: int) -> Pipeline:
    if kind == "logreg":
        clf = LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced", random_state=seed)
    elif kind == "rf":
        clf = RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=seed, min_samples_leaf=2)
    else:
        raise ValueError(kind)
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), clf)


def cv_predict(X: np.ndarray, y: np.ndarray, folds: Iterable[tuple[np.ndarray, np.ndarray]], kind: str,
               seed: int) -> np.ndarray:
    """Out-of-fold predictions; imputer, scaler and model are fitted on the training rows of each fold only."""
    pred = np.empty(len(y), dtype=object)
    for train, test in folds:
        assert not set(train) & set(test)
        m = _model(kind, seed).fit(X[train], y[train])
        pred[test] = m.predict(X[test])
    return pred


def loio_logo(df: pd.DataFrame, feats: list[str], seed: int, models: Iterable[str] = ("logreg",)) -> pd.DataFrame:
    covs = [c for c in COVARIATES if c in df.columns]
    y = df["batch"].to_numpy()
    classes = sorted(pd.unique(y))
    rows = []
    for kind in models:
        for split, units in (("LOIO", df["sample_id"]), ("LOGO", df["acq_group"])):
            for with_cov in (False, True):
                cols = feats + (covs if with_cov else [])
                X = df[cols].to_numpy(float)
                pred = cv_predict(X, y, grouped_folds(units), kind, seed)
                row = {"model": kind, "split": split, "covariates": "with" if with_cov else "without",
                       "n_images": len(y), "n_folds": len(pd.unique(units)), "n_features": len(cols),
                       "accuracy": float((pred == y).mean()),
                       "balanced_accuracy": float(np.mean([(pred[y == c] == c).mean() for c in classes])),
                       "chance_majority": float(max((y == c).mean() for c in classes))}
                for c in classes:
                    row[f"recall_{c}"] = float((pred[y == c] == c).mean())
                rows.append(row)
    return pd.DataFrame(rows)


def leakage_gaps(ll: pd.DataFrame, model: str = "logreg") -> dict[str, float]:
    t = ll[ll["model"] == model].set_index(["split", "covariates"])["accuracy"]
    return {"loio_minus_logo_without_cov": float(t[("LOIO", "without")] - t[("LOGO", "without")]),
            "loio_minus_logo_with_cov": float(t[("LOIO", "with")] - t[("LOGO", "with")]),
            "with_minus_without_cov_loio": float(t[("LOIO", "with")] - t[("LOIO", "without")]),
            "with_minus_without_cov_logo": float(t[("LOGO", "with")] - t[("LOGO", "without")])}


# -------------------------------------------------------------------------------------------------------- decisions
def decide(stab: pd.DataFrame, conf: pd.DataFrame, feats: list[str]) -> pd.DataFrame:
    s = stab.set_index("feature")
    c = conf.set_index("feature")
    rows = []
    for f in feats:
        reasons = []
        degenerate = bool(s.loc[f, "degenerate"])
        rs, sens, m3 = s.loc[f, "rank_stability"], s.loc[f, "threshold_sensitivity"], s.loc[f, f"mad_{REFERENCE_BATCH}"]
        confounded = bool(c.loc[f, "acquisition_confounded"])
        if degenerate:
            decision = "drop"
            reasons.append("degenerate (constant, all-NaN or zero MAD in reference batch)")
        else:
            if not (np.isfinite(rs) and rs >= RULE["rank_stability_min"]):
                reasons.append(f"rank-stability {rs:.2f} < {RULE['rank_stability_min']}")
            if confounded:
                reasons.append(f"acquisition_confounded (z_group {c.loc[f, 'z_group']:.1f} > z_batch {c.loc[f, 'z_batch']:.1f}, "
                               f"p_group {c.loc[f, 'p_group']:.4f})")
            if not np.isfinite(sens):
                reasons.append("no threshold-sensitivity measurement for this feature")
            elif not (np.isfinite(m3) and m3 > 0 and sens < RULE["sens_to_mad_max"] * m3):
                reasons.append(f"threshold sensitivity {sens:.3g} >= {RULE['sens_to_mad_max']} x {REFERENCE_BATCH} MAD {m3:.3g}")
            decision = "keep" if not reasons else "investigate"
        notes = []
        if bool(c.loc[f, "covariate_correlated"]):
            notes.append(f"abs(rho) >= {RULE['rho_covariate']} with {c.loc[f, 'strongest_covariate']} "
                         f"(rho {c.loc[f, 'rho_' + c.loc[f, 'strongest_covariate']]:+.2f}); compare raw vs residualised batch tests")
        rows.append({"feature": f, "decision": decision, "rank_stability": rs, "acquisition_confounded": confounded,
                     "threshold_sensitivity": sens, f"mad_{REFERENCE_BATCH}": m3,
                     "sens_over_mad": sens / m3 if np.isfinite(sens) and m3 > 0 else np.nan,
                     "reasons": "; ".join(reasons), "notes": "; ".join(notes)})
    return pd.DataFrame(rows)


def stability(df: pd.DataFrame, feats: list[str], sens: pd.DataFrame | None, sensitivity_tables: pd.DataFrame | None,
              rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    stab = rank_stability(df, feats, rng, n_boot)
    ref = df[df["batch"] == REFERENCE_BATCH]
    ts = threshold_sensitivity(sens, feats)
    rows = []
    for f in feats:
        r = ref[f].to_numpy(float)
        r = r[np.isfinite(r)]
        m = mad(r)
        mean = r.mean() if len(r) else np.nan
        rows.append({"feature": f, f"n_{REFERENCE_BATCH}": len(r), f"mean_{REFERENCE_BATCH}": mean,
                     f"sd_{REFERENCE_BATCH}": r.std(ddof=1) if len(r) > 1 else np.nan,
                     f"cv_{REFERENCE_BATCH}": r.std(ddof=1) / abs(mean) if len(r) > 1 and mean else np.nan,
                     f"mad_{REFERENCE_BATCH}": m,
                     f"robust_cv_{REFERENCE_BATCH}": m / abs(np.median(r)) if len(r) and np.median(r) else np.nan,
                     "threshold_sensitivity": ts[f],
                     "degenerate": bool(len(r) < 3 or not np.isfinite(m) or m == 0 or np.ptp(df[f].dropna()) == 0)})
    out = stab.merge(pd.DataFrame(rows), on="feature")
    if sensitivity_tables is not None:
        out = out.merge(sensitivity_tables, on="feature", how="left")
    return out


# ----------------------------------------------------------------------------------------------------------- report
def _md(df: pd.DataFrame, floatfmt: str = ".3g") -> str:
    return df.to_markdown(index=False, floatfmt=floatfmt)


def write_report(out: Path, name: str, df: pd.DataFrame, feats: list[str], stab: pd.DataFrame, conf: pd.DataFrame,
                 bt: pd.DataFrame, ll: pd.DataFrame, loo: pd.DataFrame, dec: pd.DataFrame, prov: dict[str, Any]) -> None:
    n_b = df.groupby("batch").size()
    gaps = leakage_gaps(ll)
    flagged = (loo[loo["flag"]].groupby("sample_id")
               .apply(lambda g: ", ".join(f"{r.feature} z={r.robust_z:+.1f}" for r in g.itertuples()), include_groups=False)
               .rename("flags").reset_index()) if loo["flag"].any() else pd.DataFrame(columns=["sample_id", "flags"])
    bt_raw = bt[(bt["variant"] == "raw") & (bt["reference_set"] == "all")]
    bt_res = bt[(bt["variant"] == "residualised") & (bt["reference_set"] == "all")]
    bt_ex = bt[(bt["variant"] == "raw") & (bt["reference_set"] == "excl_loo_flagged")]
    cov_cols = [f"rho_{c}" for c in COVARIATES if f"rho_{c}" in conf.columns]
    acc = ll[ll["model"] == "logreg"].set_index(["split", "covariates"])["accuracy"]
    sig_raw = bt_raw[bt_raw["q_bh"] < RULE["alpha"]]
    sig_res = bt_res[bt_res["q_bh"] < RULE["alpha"]]
    counts = dec["decision"].value_counts().to_dict()
    headline = [
        f"- Decisions: {counts}. Confounded with acquisition group: "
        f"{', '.join(conf.loc[conf['acquisition_confounded'], 'feature']) or 'none'}.",
        f"- Raw batch effects with q < {RULE['alpha']} (vs {REFERENCE_BATCH}, all images): "
        + (", ".join(f"{r.feature} {r.comparison} effect {r.effect_shift_over_mad:+.2f} MAD (p {r.p_perm:.3g}, q {r.q_bh:.3g})"
                     for r in sig_raw.itertuples()) or "none")
        + f". After residualising on the covariates: "
        + (", ".join(f"{r.feature} {r.comparison} effect {r.effect_shift_over_mad:+.2f} MAD (q {r.q_bh:.3g})"
                     for r in sig_res.itertuples()) or "none") + ".",
        f"- Batch classifier accuracy (chance = majority {ll['chance_majority'].iloc[0]:.3f}): LOIO {acc[('LOIO', 'without')]:.3f} / "
        f"LOGO {acc[('LOGO', 'without')]:.3f} without covariates; LOIO {acc[('LOIO', 'with')]:.3f} / LOGO {acc[('LOGO', 'with')]:.3f} "
        f"with covariates. LOIO - LOGO gap {gaps['loio_minus_logo_without_cov']:+.3f} (without) / {gaps['loio_minus_logo_with_cov']:+.3f} (with); "
        f"with - without covariates gap {gaps['with_minus_without_cov_loio']:+.3f} (LOIO) / {gaps['with_minus_without_cov_logo']:+.3f} (LOGO).",
        f"- {REFERENCE_BATCH} images flagged by leave-one-out (|z| > {RULE['loo_z']}): "
        + (", ".join(f"{r.sample_id} ({r.flags})" for r in flagged.itertuples()) or "none") + ".",
    ]
    lines = [
        f"# Validation of `{name}`",
        "",
        f"Inputs: {prov['features']} (sha256 {prov['features_sha256'][:12]}), covariates from {prov['artefacts']}, "
        f"acquisition groups from {prov['images']}, threshold sensitivity from {prov['sensitivity']}. "
        f"Config {prov['config_hash']}, git {prov['git_sha']}, seed {prov['seed']}, {prov['n_boot']} bootstrap resamples, "
        f"{prov['n_perm']} permutations.",
        "",
        "## Headline",
        "",
        *headline,
        "",
        "## Hard rules applied",
        "",
        f"- The image (8-character id) is the independent unit: n = {len(df)} images "
        f"({', '.join(f'{b} {n}' for b, n in n_b.items())}). Tiles are pseudo-replicates and never enter any resample, "
        "permutation or fold here; every statistic below is image-level.",
        f"- Acquisition group = (image height, XResolution tag) from the audit: {df['acq_group'].nunique()} groups; "
        "leave-one-acquisition-group-out keeps every image of a group (all its detector views) on one side of the split.",
        "- Scaling, imputation and the classifier are fitted inside each fold only.",
        "- Phase identities (class 2 bright = silicon, class 1 mid = graphite, class 0 dark = void/pore) are stated by Polaron, "
        "not image-verified; Si vs SiOx is indistinguishable in BSE; binder/additive is lumped into class 0/1. No further chemistry claims.",
        "- Units are pixels. nm values would hold only if 25 nm/px is true (tag written by software, unconfirmed).",
        f"- {REFERENCE_BATCH} is the reference batch but not error-free: the leave-one-out check flags {', '.join(LOO_FLAGGED)}; "
        "batch tests are reported with and without them.",
        "- Acquisition covariates (noise, sharpness, curtaining, stripe, edge charging, mean grey) are measured and kept as "
        "covariates; images are never altered.",
        "- p-values are image-level permutation p with the effect size next to them; `investigate` is a first-class outcome.",
        "",
        "## Decision table (pre-declared rule)",
        "",
        f"keep if rank-stability >= {RULE['rank_stability_min']} AND not acquisition_confounded AND threshold sensitivity "
        f"< {RULE['sens_to_mad_max']} x {REFERENCE_BATCH} MAD; drop if degenerate; otherwise investigate. "
        "A feature without a threshold-sensitivity measurement cannot satisfy the third condition and is `investigate`.",
        "",
        _md(dec[["feature", "decision", "rank_stability", "acquisition_confounded", "threshold_sensitivity",
                 f"mad_{REFERENCE_BATCH}", "sens_over_mad", "reasons", "notes"]]),
        "",
        f"Counts: {dec['decision'].value_counts().to_dict()}",
        "",
        "## Stability (stability.csv)",
        "",
        "rank_stability = mean Spearman between the observed ranking of batch medians and the ranking in each image-level "
        "bootstrap resample (resampling images within batch); rank_order_preserved_frac = share of resamples with the "
        f"identical order. cv_{REFERENCE_BATCH} = sd/mean over {REFERENCE_BATCH} images; threshold_sensitivity = median over "
        "images of the largest |change| under +/-10 % threshold scaling (only measured for the class fractions).",
        "",
        _md(stab[["feature", "rank_stability", "rank_order_preserved_frac"] + [c for c in stab.columns if c.startswith("median_")]
                 + [f"cv_{REFERENCE_BATCH}", f"mad_{REFERENCE_BATCH}", "threshold_sensitivity", "degenerate"]]),
        "",
        "## Acquisition confounding (confound.csv)",
        "",
        "Spearman rho with each covariate (BSE channel; edge charging from Inlens). Association with acquisition group vs "
        "with batch: Kruskal-Wallis H with an image-level permutation null; z = (H - mean null) / sd null makes the two "
        "comparable despite the different number of levels. acquisition_confounded = z_group > z_batch and p_group < "
        f"{RULE['alpha']}. p_group_within_batch: do groups still explain the feature after centring on batch medians "
        "(labels shuffled within batch)?",
        "",
        _md(conf[["feature"] + cov_cols + ["z_group", "p_group", "z_batch", "p_batch", "p_group_within_batch",
                                           "acquisition_confounded", "covariate_correlated"]]),
        "",
        f"covariate_correlated (informational, not part of the keep rule) = some abs(rho) >= {RULE['rho_covariate']} with p < "
        f"{RULE['alpha']}; for such features compare the raw and residualised batch tests below.",
        "",
        "## Batch tests (batch_tests.csv)",
        "",
        f"Effect = (median test batch - median {REFERENCE_BATCH}) / MAD({REFERENCE_BATCH}, scaled 1.4826); p = image-level "
        "permutation p of the median difference; q = Benjamini-Hochberg across features within each comparison.",
        "",
        f"Raw features, all {REFERENCE_BATCH} images:",
        "",
        _md(bt_raw[["feature", "comparison", "n_test", "n_ref", "effect_shift_over_mad", "p_perm", "q_bh"]]),
        "",
        f"Raw features, {REFERENCE_BATCH} without {', '.join(LOO_FLAGGED)}:",
        "",
        _md(bt_ex[["feature", "comparison", "n_test", "n_ref", "effect_shift_over_mad", "p_perm", "q_bh"]]),
        "",
        f"Residualised on the acquisition covariates, all {REFERENCE_BATCH} images:",
        "",
        _md(bt_res[["feature", "comparison", "n_test", "n_ref", "effect_shift_over_mad", "p_perm", "q_bh"]]),
        "",
        "## Session-leakage evidence: LOIO vs LOGO (loio_logo.csv)",
        "",
        "Logistic regression (balanced class weights, median imputation + standardisation fitted inside each fold) predicting "
        f"batch from the {len(feats)} features, with and without the {len([c for c in COVARIATES if c in df.columns])} "
        "acquisition covariates as extra inputs. chance_majority = accuracy of always predicting the largest batch.",
        "",
        _md(ll),
        "",
        "Gaps (accuracy): " + "; ".join(f"{k} = {v:+.3f}" for k, v in gaps.items()),
        "",
        "Reading: a positive LOIO - LOGO gap means part of the LOIO accuracy comes from images of the same acquisition "
        "session being in the training set; a positive with - without gap means the covariates themselves carry batch "
        "information. Both are evidence that acquisition, not only material, separates the batches.",
        "",
        f"## Reference batch leave-one-out (reference_loo.csv), |z| > {RULE['loo_z']}",
        "",
        _md(flagged) if len(flagged) else "No image flagged.",
        "",
        f"Expected from the C4 check: {', '.join(LOO_FLAGGED)}.",
        "",
    ]
    (out / "VALIDATION.md").write_text("\n".join(lines))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tables(features: pd.DataFrame, artefacts: pd.DataFrame, images: pd.DataFrame, sens: pd.DataFrame | None,
               seed: int = 0, n_boot: int = 1000, n_perm: int = 10_000, models: Iterable[str] = ("logreg",),
               sensitivity_tables: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """All validation tables from in-memory inputs (used by the CLI and by tests)."""
    rng = np.random.default_rng(seed)
    df, feats = assemble(features, artefacts, images)
    stab = stability(df, feats, sens, sensitivity_tables, rng, n_boot)
    conf = confound(df, feats, rng, n_perm)
    bt = batch_tests(df, feats, rng, n_perm)
    ll = loio_logo(df, feats, seed, models)
    loo = reference_loo(df, feats)
    dec = decide(stab, conf, feats)
    return {"assembled": df, "stability": stab, "confound": conf, "batch_tests": bt, "loio_logo": ll,
            "reference_loo": loo, "decisions": dec, "_feats": feats}


def run(cfg: dict[str, Any], features: str, out: str | None = None, artefacts: str = "results/artefacts_per_image.parquet",
        images: str = "results/audit/images.csv", sensitivity: str | None = "results/kpi_sensitivity.parquet",
        seed: int = 0, n_boot: int = 1000, n_perm: int = 10_000, rf: bool = False) -> Path:
    fpath = _config.resolve(features)
    name = fpath.stem
    out_dir = _config.resolve(out) if out else _config.ROOT / "results" / "validate" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    sens_path = _config.resolve(sensitivity) if sensitivity else None
    sens = read_table(sens_path) if sens_path and sens_path.exists() else None
    tabs = run_tables(read_table(fpath), read_table(_config.resolve(artefacts)), read_table(_config.resolve(images)),
                      sens, seed=seed, n_boot=n_boot, n_perm=n_perm, models=("logreg", "rf") if rf else ("logreg",))
    for key in ("stability", "confound", "batch_tests", "loio_logo", "reference_loo", "decisions"):
        _config.stamp(tabs[key], cfg).to_csv(out_dir / f"{key}.csv", index=False)
    prov = {**_config.provenance(cfg), "features": str(fpath.relative_to(_config.ROOT)) if fpath.is_relative_to(_config.ROOT) else str(fpath),
            "features_sha256": sha256(fpath), "artefacts": artefacts, "images": images,
            "sensitivity": sensitivity if sens is not None else "none", "seed": seed, "n_boot": n_boot, "n_perm": n_perm}
    write_report(out_dir, name, tabs["assembled"], tabs["_feats"], tabs["stability"], tabs["confound"], tabs["batch_tests"],
                 tabs["loio_logo"], tabs["reference_loo"], tabs["decisions"], prov)
    dec = tabs["decisions"]
    print(f"validate: {len(tabs['assembled'])} images, {len(tabs['_feats'])} features -> {out_dir.relative_to(_config.ROOT)}/ "
          f"({dec['decision'].value_counts().to_dict()})", file=sys.stderr)
    return out_dir

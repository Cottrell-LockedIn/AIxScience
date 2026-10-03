"""Image-level reference comparisons (stats). Owner: P1.

Reads:  F01-F11, KPI, and frozen-embedding tables with one row per image.
Writes: results/stats/<table_name>/{pair_tests,distance_matrix,null_bands,consistency,STATS.md}
        plus shifts.csv for material tables.

The image is the independent unit. Scaling is label-free across all images; permutations move whole image labels.
"""
from __future__ import annotations

import os
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.spatial.distance import cdist, pdist, squareform

from qc import config as _config
from qc import validate as _validate
from qc.features import PHASE_IDENTITY

try:
    from threadpoolctl import threadpool_limits
except ImportError:  # pragma: no cover - threadpoolctl is a project dependency
    threadpool_limits = None

MAD_SCALE = 1.4826
METRICS = ("median_shift", "energy_distance", "mmd2_unbiased")
DEFAULT_TABLES = {
    "features_f01_f11": ("results/features/features_f01_f11.parquet", "material"),
    "kpi_per_image": ("results/kpi_per_image.parquet", "material"),
    "dinov2_vits14_bse_by_image": ("results/embeddings/dinov2_vits14_bse_by_image.parquet", "embedding"),
    "dinov2_vits14_inlens_by_image": ("results/embeddings/dinov2_vits14_inlens_by_image.parquet", "embedding"),
    "dinov2_vits14_setype_by_image": ("results/embeddings/dinov2_vits14_setype_by_image.parquet", "embedding"),
}


def energy_distance_v_statistic(x: np.ndarray, y: np.ndarray) -> float:
    """V-statistic energy distance for one- or multi-dimensional observations."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    if y.ndim == 1:
        y = y[:, None]
    return float(2 * cdist(x, y).mean() - cdist(x, x).mean() - cdist(y, y).mean())


def mmd2_unbiased_from_kernel(kernel: np.ndarray, idx_a: np.ndarray, idx_b: np.ndarray) -> float:
    """Unbiased two-sample MMD² from a precomputed kernel matrix."""
    ka = kernel[np.ix_(idx_a, idx_a)]
    kb = kernel[np.ix_(idx_b, idx_b)]
    kab = kernel[np.ix_(idx_a, idx_b)]
    na, nb = len(idx_a), len(idx_b)
    if na < 2 or nb < 2:
        raise ValueError("unbiased MMD² needs at least two images in each group")
    within_a = (ka.sum() - np.trace(ka)) / (na * (na - 1))
    within_b = (kb.sum() - np.trace(kb)) / (nb * (nb - 1))
    return float(within_a + within_b - 2 * kab.mean())


def _metric_values(x: np.ndarray, distances: np.ndarray, kernel: np.ndarray, idx_a: np.ndarray,
                   idx_b: np.ndarray, reference_scale: np.ndarray) -> dict[str, float]:
    median_delta = np.median(x[idx_a], axis=0) - np.median(x[idx_b], axis=0)
    valid = np.isfinite(reference_scale) & (reference_scale > 0)
    median_shift = float(np.sqrt(np.mean((median_delta[valid] / reference_scale[valid]) ** 2))) if valid.any() else np.nan
    energy = (2 * distances[np.ix_(idx_a, idx_b)].mean()
              - distances[np.ix_(idx_a, idx_a)].mean()
              - distances[np.ix_(idx_b, idx_b)].mean())
    return {
        "median_shift": median_shift,
        "energy_distance": float(energy),
        "mmd2_unbiased": mmd2_unbiased_from_kernel(kernel, idx_a, idx_b),
    }


def _permuted_metrics(seed_i: int, x: np.ndarray, distances: np.ndarray, kernel: np.ndarray,
                     n_a: int, reference_scale: np.ndarray) -> tuple[float, float, float]:
    def calculate() -> tuple[float, float, float]:
        order = np.random.default_rng(seed_i).permutation(len(x))
        values = _metric_values(x, distances, kernel, order[:n_a], order[n_a:], reference_scale)
        return tuple(values[m] for m in METRICS)

    if threadpool_limits is None:
        return calculate()
    with threadpool_limits(limits=1):
        return calculate()


def _null_split_metrics(seed_i: int, x: np.ndarray, distances: np.ndarray, kernel: np.ndarray,
                        n_a: int, reference_scale: np.ndarray) -> tuple[float, float, float]:
    def calculate() -> tuple[float, float, float]:
        rng = np.random.default_rng(seed_i)
        idx_a = rng.choice(len(x), size=n_a, replace=False)
        idx_b = np.setdiff1d(np.arange(len(x)), idx_a, assume_unique=True)
        values = _metric_values(x, distances, kernel, idx_a, idx_b, reference_scale)
        return tuple(values[m] for m in METRICS)

    if threadpool_limits is None:
        return calculate()
    with threadpool_limits(limits=1):
        return calculate()


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    """BH-adjust p-values while preserving their input order."""
    p = np.asarray(p_values, dtype=float)
    if p.ndim != 1 or not np.isfinite(p).all():
        raise ValueError("BH adjustment requires a finite one-dimensional p-value array")
    order = np.argsort(p, kind="stable")
    ranks = np.arange(1, len(p) + 1, dtype=float)
    adjusted_sorted = np.minimum.accumulate((p[order] * len(p) / ranks)[::-1])[::-1]
    adjusted = np.empty_like(adjusted_sorted)
    adjusted[order] = np.minimum(adjusted_sorted, 1.0)
    return adjusted


def consistency_statistics(batches: np.ndarray, distances: np.ndarray) -> pd.DataFrame:
    """Mean within-batch pairwise distance and leave-one-image-out jackknife SE."""
    batches = np.asarray(batches)
    rows = []
    for batch in sorted(pd.unique(batches)):
        idx = np.flatnonzero(batches == batch)
        n = len(idx)
        if n < 2:
            raise ValueError(f"batch {batch!r} needs at least two images for consistency")
        within = distances[np.ix_(idx, idx)]
        mean_distance = float(within[np.triu_indices(n, k=1)].mean())
        loo = []
        for i in range(n):
            keep = np.delete(idx, i)
            if len(keep) < 2:
                loo.append(np.nan)
            else:
                d = distances[np.ix_(keep, keep)]
                loo.append(float(d[np.triu_indices(len(keep), k=1)].mean()))
        loo = np.asarray(loo, dtype=float)
        if np.isfinite(loo).all():
            se = float(np.sqrt((n - 1) / n * np.sum((loo - loo.mean()) ** 2)))
        else:
            se = np.nan
        rows.append({"batch": batch, "n_images": n, "mean_pairwise_euclidean": mean_distance, "jackknife_se": se})

    result = pd.DataFrame(rows).sort_values(["mean_pairwise_euclidean", "batch"]).reset_index(drop=True)
    result["rank"] = np.arange(1, len(result) + 1)
    result["rank_separable"] = False
    for i in range(len(result) - 1):
        se_a, se_b = result.loc[i, "jackknife_se"], result.loc[i + 1, "jackknife_se"]
        gap = abs(result.loc[i, "mean_pairwise_euclidean"] - result.loc[i + 1, "mean_pairwise_euclidean"])
        if np.isfinite(se_a) and np.isfinite(se_b):
            result.loc[i, "rank_separable"] = bool(gap > 2 * np.sqrt(se_a ** 2 + se_b ** 2))
    return result


def _distance_matrix_table(batches: list[str], pair_values: dict[tuple[str, str], dict[str, float]]) -> pd.DataFrame:
    rows = []
    for metric in METRICS:
        for batch_a in batches:
            for batch_b in batches:
                key = tuple(sorted((batch_a, batch_b)))
                value = 0.0 if batch_a == batch_b else pair_values[key][metric]
                rows.append({"metric": metric, "batch_a": batch_a, "batch_b": batch_b, "value": value})
    return pd.DataFrame(rows)


def analyze_table(df: pd.DataFrame, n_perm: int = 1000, n_null_splits: int = 1000, seed: int = 0,
                  n_jobs: int = -1, reference: str = _validate.REFERENCE_BATCH) -> dict[str, Any]:
    """Compute pair tests, null bands, symmetric distances, consistency and feature shifts in memory."""
    if "sample_id" not in df or "batch" not in df:
        raise ValueError("stats input must contain sample_id and batch")
    if df["sample_id"].isna().any() or df["sample_id"].duplicated().any():
        raise ValueError("stats input must have one non-null row per unique sample_id")
    if df["batch"].isna().any():
        raise ValueError("stats input contains missing batch labels")
    if n_perm < 1 or n_null_splits < 1:
        raise ValueError("n_perm and n_null_splits must be positive")

    columns = _validate.feature_columns(df)
    if not columns:
        raise ValueError("stats input contains no numeric feature columns")
    raw_all = df[columns].to_numpy(dtype=float)
    if not np.isfinite(raw_all).all():
        raise ValueError("stats input features must be finite; resolve missing or infinite values before analysis")

    center = np.median(raw_all, axis=0)
    mad_all = np.median(np.abs(raw_all - center), axis=0)
    nonzero = mad_all > 0
    zero_mad_columns = [c for c, keep in zip(columns, nonzero) if not keep]
    if not nonzero.any():
        raise ValueError("all numeric feature columns have zero MAD")
    used_columns = [c for c, keep in zip(columns, nonzero) if keep]
    x = raw_all[:, nonzero]
    global_scale = MAD_SCALE * mad_all[nonzero]
    z = (x - center[nonzero]) / global_scale

    labels = df["batch"].astype(str).to_numpy()
    batches = sorted(pd.unique(labels).tolist())
    if reference not in batches:
        raise ValueError(f"reference batch {reference!r} is absent; found {batches}")
    if len(batches) != 3:
        raise ValueError(f"stats expects exactly three batches; found {batches}")
    reference_idx = np.flatnonzero(labels == reference)
    if len(reference_idx) < 3:
        raise ValueError(f"reference batch {reference!r} needs at least three images for null splits")
    x_reference = x[reference_idx]
    reference_center = np.median(x_reference, axis=0)
    reference_scale = MAD_SCALE * np.median(np.abs(x_reference - reference_center), axis=0)

    all_distances = squareform(pdist(z, metric="euclidean"))
    bandwidth = float(np.median(all_distances[np.triu_indices(len(df), k=1)]))
    if not np.isfinite(bandwidth) or bandwidth <= 0:
        raise ValueError("median pairwise Euclidean distance must be positive for the Gaussian MMD kernel")
    kernel = np.exp(-(all_distances ** 2) / (2 * bandwidth ** 2))

    rng = np.random.default_rng(seed)
    pair_values: dict[tuple[str, str], dict[str, float]] = {}
    pair_records = []
    for batch_a, batch_b in combinations(batches, 2):
        idx_a = np.flatnonzero(labels == batch_a)
        idx_b = np.flatnonzero(labels == batch_b)
        pair = f"{batch_a} vs {batch_b}"
        observed = _metric_values(x, all_distances, kernel, idx_a, idx_b, reference_scale)
        pair_values[(batch_a, batch_b)] = observed

        idx_pair = np.concatenate((idx_a, idx_b))
        x_pair = x[idx_pair]
        distances_pair = all_distances[np.ix_(idx_pair, idx_pair)]
        kernel_pair = kernel[np.ix_(idx_pair, idx_pair)]
        seeds = rng.integers(0, 2**32 - 1, size=n_perm, dtype=np.uint32)
        if threadpool_limits is None:
            for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
                os.environ[variable] = "1"
        null = np.asarray(Parallel(n_jobs=n_jobs)(
            delayed(_permuted_metrics)(int(seed_i), x_pair, distances_pair, kernel_pair, len(idx_a), reference_scale)
            for seed_i in seeds
        ), dtype=float)
        for j, metric in enumerate(METRICS):
            p_perm = float((1 + np.sum(null[:, j] >= observed[metric])) / (n_perm + 1))
            pair_records.append({"pair": pair, "metric": metric, "value": observed[metric], "p_perm": p_perm})

    p_bh = benjamini_hochberg(np.asarray([row["p_perm"] for row in pair_records]))
    batch3_n = len(reference_idx)
    split_n_a = min(7, batch3_n // 2)
    split_n_b = batch3_n - split_n_a
    if split_n_a < 2 or split_n_b < 2:
        raise ValueError("reference batch is too small for a 7/10-style split null")
    reference_distances = all_distances[np.ix_(reference_idx, reference_idx)]
    reference_kernel = kernel[np.ix_(reference_idx, reference_idx)]
    split_seeds = rng.integers(0, 2**32 - 1, size=n_null_splits, dtype=np.uint32)
    null_splits = np.asarray(Parallel(n_jobs=n_jobs)(
        delayed(_null_split_metrics)(int(seed_i), x_reference, reference_distances, reference_kernel,
                                     split_n_a, reference_scale)
        for seed_i in split_seeds
    ), dtype=float)
    band_by_metric = {
        metric: (float(np.percentile(null_splits[:, j], 95)), float(np.percentile(null_splits[:, j], 99)))
        for j, metric in enumerate(METRICS)
    }
    null_bands = pd.DataFrame([
        {"metric": metric, "n_splits": n_null_splits, "split_n_a": split_n_a, "split_n_b": split_n_b,
         "null_p95": band_by_metric[metric][0], "null_p99": band_by_metric[metric][1]}
        for metric in METRICS
    ])
    for i, row in enumerate(pair_records):
        p95, p99 = band_by_metric[row["metric"]]
        is_reference_pair = reference in row["pair"].split(" vs ")
        row["p_bh"] = float(p_bh[i])
        row["null_p95"] = p95
        row["null_p99"] = p99
        row["above_p95"] = bool(row["value"] > p95) if is_reference_pair else None
        row["above_p99"] = bool(row["value"] > p99) if is_reference_pair else None
    pair_tests = pd.DataFrame(pair_records, columns=[
        "pair", "metric", "value", "p_perm", "p_bh", "null_p95", "null_p99", "above_p95", "above_p99",
    ])

    shifts = []
    for i, feature in enumerate(used_columns):
        row: dict[str, Any] = {"feature": feature, "reference_scale": float(reference_scale[i])}
        for batch in batches:
            if batch == reference:
                continue
            idx = np.flatnonzero(labels == batch)
            delta = float(np.median(x[idx, i]) - np.median(x[reference_idx, i]))
            row[f"standardized_shift_{batch}_vs_{reference}"] = delta / reference_scale[i] if reference_scale[i] > 0 else np.nan
        shifts.append(row)

    consistency = consistency_statistics(labels, all_distances)
    distance_matrix = _distance_matrix_table(batches, pair_values)
    return {
        "pair_tests": pair_tests,
        "null_bands": null_bands,
        "distance_matrix": distance_matrix,
        "consistency": consistency,
        "shifts": pd.DataFrame(shifts),
        "summary": {
            "batches": batches,
            "n_images": len(df),
            "feature_columns": used_columns,
            "zero_mad_columns": zero_mad_columns,
            "reference_zero_mad_columns": [c for c, s in zip(used_columns, reference_scale) if s <= 0],
            "reference_batch": reference,
            "mmd_bandwidth": bandwidth,
            "seed": seed,
            "n_perm": n_perm,
            "n_null_splits": n_null_splits,
            "split_n_a": split_n_a,
            "split_n_b": split_n_b,
        },
    }


def _format_value(value: float) -> str:
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def write_report(path: Path, table_name: str, results: dict[str, Any], cfg: dict[str, Any]) -> None:
    summary = results["summary"]
    provenance = _config.provenance(cfg)
    pair_tests = results["pair_tests"].set_index(["pair", "metric"])
    null_bands = results["null_bands"].set_index("metric")
    consistency = results["consistency"].sort_values("rank")
    zero_mad = ", ".join(summary["zero_mad_columns"]) if summary["zero_mad_columns"] else "none"
    zero_reference_mad = ", ".join(summary["reference_zero_mad_columns"]) if summary["reference_zero_mad_columns"] else "none"
    null_text = "; ".join(
        f"{metric}={_format_value(null_bands.loc[metric, 'null_p95'])}/{_format_value(null_bands.loc[metric, 'null_p99'])}"
        for metric in METRICS
    )
    pair_lines = []
    for batch in summary["batches"]:
        if batch == summary["reference_batch"]:
            continue
        pair = f"{batch} vs {summary['reference_batch']}"
        measures = "; ".join(
            f"{metric}={_format_value(pair_tests.loc[(pair, metric), 'value'])}, p={_format_value(pair_tests.loc[(pair, metric), 'p_perm'])}"
            for metric in METRICS
        )
        pair_lines.append(f"{pair}: {measures}")
    rank_text = "; ".join(
        f"{row.batch}={_format_value(row.mean_pairwise_euclidean)} (rank {row.rank}, SE {_format_value(row.jackknife_se)}, separable={str(bool(row.rank_separable)).lower()})"
        for row in consistency.itertuples()
    )
    lines = [
        f"# Stats: {table_name}",
        f"config_hash: {provenance['config_hash']}",
        f"git_sha: {provenance['git_sha']}",
        f"reference_batch: {summary['reference_batch']}; source: Polaron clarification; config auto resolved",
        f"phase_identity: {PHASE_IDENTITY}",
        f"images: {summary['n_images']}; features used: {len(summary['feature_columns'])}; zero-MAD columns dropped: {zero_mad}",
        "robust z: median and 1.4826*MAD per feature across all images, without batch labels",
        f"Gaussian MMD bandwidth: {_format_value(summary['mmd_bandwidth'])} (median pairwise Euclidean distance over all robust-z images)",
        f"permutations: {summary['n_perm']} image-label draws per pair; seed={summary['seed']}; plus-one p; BH over 9 pair/metric tests",
        f"Batch_3 null: {summary['n_null_splits']} random {summary['split_n_a']}/{summary['split_n_b']} splits, size-matched to 7-image batches; smaller reference side gives wider/conservative bands than 7/17",
        f"null p95/p99: {null_text}",
        *pair_lines,
        f"zero Batch_3-MAD columns excluded from median shift: {zero_reference_mad}",
        f"consistency rank ascending (mean pairwise Euclidean): {rank_text}",
    ]
    path.write_text("\n".join(lines) + "\n")


def _stamp_output(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    out = _config.stamp(df, cfg)
    out["phase_identity"] = PHASE_IDENTITY
    return out


def run(cfg: dict[str, Any], all_tables: bool = True, table: str | None = None, seed: int = 0,
        n_perm: int = 1000, n_null_splits: int = 1000, n_jobs: int = -1) -> None:
    if all_tables and table:
        raise ValueError("choose --all or a single --table, not both")
    if all_tables:
        tables = DEFAULT_TABLES
    elif table in DEFAULT_TABLES:
        tables = {table: DEFAULT_TABLES[table]}
    else:
        raise ValueError(f"choose --all or one of {', '.join(DEFAULT_TABLES)}")

    for name, (input_path, table_family) in tables.items():
        df = _validate.read_table(_config.resolve(input_path))
        results = analyze_table(df, n_perm=n_perm, n_null_splits=n_null_splits, seed=seed, n_jobs=n_jobs)
        out_dir = _config.ROOT / "results" / "stats" / name
        out_dir.mkdir(parents=True, exist_ok=True)
        for key in ("pair_tests", "null_bands", "distance_matrix", "consistency"):
            _stamp_output(results[key], cfg).to_csv(out_dir / f"{key}.csv", index=False)
        if table_family != "embedding":
            _stamp_output(results["shifts"], cfg).to_csv(out_dir / "shifts.csv", index=False)
        write_report(out_dir / "STATS.md", name, results, cfg)
        ranks = ", ".join(f"{row.batch}:{row.rank}" for row in results["consistency"].itertuples())
        print(f"stats: {name} images={results['summary']['n_images']} features={len(results['summary']['feature_columns'])} "
              f"pairs={len(results['pair_tests'])} ranks=({ranks}) -> {out_dir.relative_to(_config.ROOT)}")

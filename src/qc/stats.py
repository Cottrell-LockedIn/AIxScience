"""Image-level B4 contrasts and B5 validation gates."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy.spatial.distance import cdist

from qc import config as _config

PHASE_IDENTITY = "stated by Polaron, not image-verified"
PAIR_ORDER = (
    ("Batch_1", "Batch_2"),
    ("Batch_1", "Batch_3"),
    ("Batch_2", "Batch_3"),
)
TABLE_ORDER = ("kpi", "features", "emb_BSE", "emb_Inlens", "emb_ETD", "covariates")
STATISTIC_ORDER = ("rms_z", "energy", "mmd2")
EMBEDDING_CHANNELS = ("BSE", "Inlens", "ETD")
STRUCTURAL_FAILURE_MODES = {
    "FM03", "FM07", "FM08", "FM10", "FM11", "FM13", "FM14", "FM21",
}


def benjamini_hochberg(p_values: Any) -> np.ndarray:
    """Benjamini–Hochberg adjusted p-values, retaining the input shape."""
    values = np.asarray(p_values, dtype=np.float64)
    flat = values.ravel()
    adjusted = np.full(flat.shape, np.nan, dtype=np.float64)
    valid = np.flatnonzero(np.isfinite(flat))
    if valid.size == 0:
        return adjusted.reshape(values.shape)
    order = valid[np.argsort(flat[valid], kind="stable")]
    ranked = flat[order] * len(order) / np.arange(1, len(order) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adjusted[order] = np.minimum(ranked, 1.0)
    return adjusted.reshape(values.shape)


def mad(values: Any) -> float:
    """Median absolute deviation, ignoring non-finite values."""
    array = np.asarray(values, dtype=np.float64)
    array = array[np.isfinite(array)]
    if not array.size:
        return float("nan")
    center = float(np.median(array))
    return float(np.median(np.abs(array - center)))


def robust_scale(reference: Any, all_values: Any | None = None) -> float:
    """Return 1.4826*MAD(reference), with the preregistered all-image fallback."""
    scale = 1.4826 * mad(reference)
    if scale == 0 and all_values is not None:
        scale = 1.4826 * mad(all_values)
    return float(scale)


def validate_image_table(
    frame: pd.DataFrame,
    name: str,
    *,
    key_columns: tuple[str, ...] = ("sample_id",),
    image_level: bool = True,
) -> None:
    """Reject tile-level input and duplicate image-level keys."""
    required = {"sample_id", "batch"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{name} is missing required columns: {sorted(missing)}")
    if "level" in frame.columns and not frame["level"].eq("image").all():
        raise ValueError(f"{name} contains non-image rows")
    if "tile_id" in frame.columns and frame["tile_id"].notna().any():
        raise ValueError(f"{name} contains tile-level rows")
    if image_level and ("y" in frame.columns or "x" in frame.columns) and "level" not in frame.columns:
        raise ValueError(f"{name} appears to be tile-level data")
    missing_keys = set(key_columns) - set(frame.columns)
    if missing_keys:
        raise ValueError(f"{name} is missing key columns: {sorted(missing_keys)}")
    if frame.duplicated(list(key_columns)).any():
        raise ValueError(f"{name} contains duplicate image keys: {key_columns}")


def residualize(values: Any, covariates: Any) -> np.ndarray:
    """OLS residuals using standardized, label-free covariates and an intercept."""
    y = np.asarray(values, dtype=np.float64)
    one_dimensional = y.ndim == 1
    if one_dimensional:
        y = y[:, None]
    x = np.asarray(covariates, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if y.ndim != 2 or x.ndim != 2 or y.shape[0] != x.shape[0]:
        raise ValueError("values and covariates must be 2-D arrays with matching rows")
    if not np.isfinite(y).all() or not np.isfinite(x).all():
        raise ValueError("residualisation requires finite image-level values")
    mean = x.mean(axis=0)
    scale = x.std(axis=0, ddof=0)
    scale[scale == 0] = 1.0
    standardized = (x - mean) / scale
    design = np.column_stack([np.ones(len(standardized)), standardized])
    coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
    result = y - design @ coefficients
    return result[:, 0] if one_dimensional else result


def pairwise_distance_matrix(vectors: Any) -> np.ndarray:
    """Euclidean image-distance matrix with an exact zero diagonal."""
    values = np.asarray(vectors, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError("vectors must be a 2-D array")
    result = cdist(values, values, metric="euclidean")
    np.fill_diagonal(result, 0.0)
    return result


def permutation_test_z(
    values_a: Any,
    values_b: Any,
    scale: float,
    *,
    seed: int = 20261003,
    n_permutations: int = 2000,
) -> tuple[float, float]:
    """Two-sided median-shift z permutation test for two image-level vectors."""
    a = np.asarray(values_a, dtype=np.float64)
    b = np.asarray(values_b, dtype=np.float64)
    if scale <= 0 or not np.isfinite(scale):
        return float("nan"), float("nan")
    observed = (float(np.median(a)) - float(np.median(b))) / scale
    pooled = np.concatenate([a, b])
    rng = np.random.default_rng(seed)
    priorities = rng.random((n_permutations, len(pooled)))
    order = np.argsort(priorities, axis=1, kind="stable")
    n_a = len(a)
    permuted = (
        np.median(pooled[order[:, :n_a]], axis=1)
        - np.median(pooled[order[:, n_a:]], axis=1)
    ) / scale
    p_value = (1 + np.count_nonzero(np.abs(permuted) >= abs(observed))) / (1 + n_permutations)
    return float(observed), float(p_value)


def _pair_name(batch_a: str, batch_b: str) -> str:
    return f"{batch_a}_vs_{batch_b}"


def _scale_from_frame(frame: pd.DataFrame, feature: str, reference_batch: str) -> float:
    reference = frame.loc[frame["batch"] == reference_batch, feature].to_numpy(dtype=np.float64)
    all_values = frame[feature].to_numpy(dtype=np.float64)
    return robust_scale(reference, all_values)


def _all_finite(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    if not np.isfinite(frame[columns].to_numpy(dtype=np.float64)).all():
        raise ValueError(f"{name} contains missing or non-finite required values")


def _load_stats_config() -> tuple[dict[str, Any], Path, str]:
    path = _config.ROOT / "configs" / "stats_v1.yaml"
    raw = path.read_bytes()
    config = yaml.safe_load(raw)
    return config, path, hashlib.sha256(raw).hexdigest()[:12]


def _read_feature_tables(
    stats_cfg: dict[str, Any],
) -> tuple[dict[str, pd.DataFrame], dict[str, list[str]]]:
    tables: dict[str, pd.DataFrame] = {}
    features: dict[str, list[str]] = {}
    for name in ("kpi", "features"):
        table_cfg = stats_cfg["tables"][name]
        frame = pd.read_parquet(_config.ROOT / table_cfg["file"])
        columns = [
            feature for feature in stats_cfg["features"]
            if feature.startswith("F") == (name == "features")
        ]
        missing = set(columns) - set(frame.columns)
        if missing:
            raise ValueError(f"{table_cfg['file']} is missing preregistered columns: {sorted(missing)}")
        if name == "features" and "scale" in frame.columns:
            frame = frame.loc[np.isclose(frame["scale"].astype(float), 1.0)].copy()
        validate_image_table(frame, table_cfg["file"])
        _all_finite(frame, columns, table_cfg["file"])
        tables[name] = frame.sort_values("sample_id", kind="stable").reset_index(drop=True)
        features[name] = columns
    common_ids = set(tables["kpi"]["sample_id"]) & set(tables["features"]["sample_id"])
    if common_ids != set(tables["kpi"]["sample_id"]) or common_ids != set(tables["features"]["sample_id"]):
        raise ValueError("KPI and feature image IDs do not match")
    kpi_batches = tables["kpi"].set_index("sample_id")["batch"].sort_index()
    feature_batches = tables["features"].set_index("sample_id")["batch"].sort_index()
    if not kpi_batches.equals(feature_batches):
        raise ValueError("KPI and feature batch labels do not match by sample_id")
    return tables, features


def _read_sensitivity_tables(
    stats_cfg: dict[str, Any],
    feature_columns: dict[str, list[str]],
) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    expected_scales = {0.9, 1.0, 1.1}
    for name in ("kpi", "features"):
        path = _config.ROOT / stats_cfg["tables"][name]["sensitivity"]
        frame = pd.read_parquet(path)
        if name == "kpi":
            if "level" not in frame.columns:
                raise ValueError(f"{path} is missing required column 'level'")
            frame = frame.loc[frame["level"] == "image"].copy()
        validate_image_table(frame, str(path), key_columns=("sample_id", "scale"))
        missing = set(feature_columns[name]) - set(frame.columns)
        if missing:
            raise ValueError(f"{path} is missing preregistered columns: {sorted(missing)}")
        if set(np.round(frame["scale"].astype(float), 6)) != expected_scales:
            raise ValueError(f"{path} must contain sensitivity scales 0.9, 1.0 and 1.1")
        _all_finite(frame, feature_columns[name], str(path))
        sample_counts = frame.groupby("sample_id", sort=False)["scale"].nunique()
        if not sample_counts.eq(3).all():
            raise ValueError(f"{path} does not contain all three scales for every image")
        result[name] = frame.sort_values(["sample_id", "scale"], kind="stable").reset_index(drop=True)
    return result


def _load_covariates(
    stats_cfg: dict[str, Any],
    image_ids: list[str],
    expected_batches: pd.Series,
) -> tuple[pd.DataFrame, list[str]]:
    rows = pd.DataFrame({"sample_id": image_ids})
    rows["batch"] = rows["sample_id"].map(expected_batches)
    covariate_names: list[str] = []

    art_cfg = stats_cfg["covariates"]["from_artefacts_per_image"]
    art_path = _config.ROOT / "results" / "artefacts_per_image.parquet"
    art = pd.read_parquet(art_path)
    required_art = {"sample_id", "batch", "channel"}
    if required_art - set(art.columns):
        raise ValueError(f"{art_path} is missing columns: {sorted(required_art - set(art.columns))}")
    for spec in art_cfg:
        column = str(spec["column"])
        channel = str(spec["channel"])
        if column not in art.columns:
            raise ValueError(f"{art_path} is missing preregistered column {column!r}")
        selected = art.loc[art["channel"] == channel, ["sample_id", "batch", column]].copy()
        validate_image_table(selected, f"{art_path}:{channel}")
        if not selected["sample_id"].isin(image_ids).all():
            raise ValueError(f"{art_path}:{channel} contains unexpected image IDs")
        if not selected.set_index("sample_id")["batch"].sort_index().equals(expected_batches.sort_index()):
            raise ValueError(f"{art_path}:{channel} batch labels do not match the image table")
        name = f"{column}_{channel}"
        selected = selected.rename(columns={column: name}).drop(columns="batch")
        rows = rows.merge(selected, on="sample_id", how="left", validate="one_to_one")
        covariate_names.append(name)

    images_path = _config.ROOT / "results" / "audit" / "images.csv"
    images = pd.read_csv(images_path)
    validate_image_table(images, str(images_path))
    for column in stats_cfg["covariates"]["from_images_csv"]:
        if column not in images.columns:
            raise ValueError(f"{images_path} is missing preregistered column {column!r}")
        selected = images[["sample_id", column]].copy()
        rows = rows.merge(selected, on="sample_id", how="left", validate="one_to_one")
        covariate_names.append(str(column))
    if rows[covariate_names].isna().any().any():
        missing = rows[covariate_names].isna().sum()
        raise ValueError(f"required covariates contain missing values: {missing[missing > 0].to_dict()}")
    _all_finite(rows, covariate_names, "covariate table")
    return rows, covariate_names


def _make_pair_plans(
    all_ids: list[str],
    batch_by_id: dict[str, str],
    base_seed: int,
    n_permutations: int,
) -> dict[str, dict[str, Any]]:
    plans: dict[str, dict[str, Any]] = {}
    for pair_index, (batch_a, batch_b) in enumerate(PAIR_ORDER):
        ids = [sample_id for sample_id in all_ids if batch_by_id[sample_id] in (batch_a, batch_b)]
        seed = base_seed + pair_index
        rng = np.random.default_rng(seed)
        plans[_pair_name(batch_a, batch_b)] = {
            "batch_a": batch_a,
            "batch_b": batch_b,
            "seed": seed,
            "ids": ids,
            "priorities": rng.random((n_permutations, len(ids))),
        }
    return plans


def _plan_subset(
    plan: dict[str, Any],
    available_ids: list[str],
    excluded_ids: set[str] | None = None,
) -> tuple[list[str], np.ndarray]:
    excluded = excluded_ids or set()
    positions_by_id = {sample_id: position for position, sample_id in enumerate(plan["ids"])}
    kept_ids = [
        sample_id for sample_id in available_ids
        if sample_id in positions_by_id and sample_id not in excluded
    ]
    positions = [positions_by_id[sample_id] for sample_id in kept_ids]
    priorities = plan["priorities"][:, positions]
    return kept_ids, priorities


def _scalar_test(
    frame: pd.DataFrame,
    feature: str,
    plan: dict[str, Any],
    scale: float,
    *,
    excluded_ids: set[str] | None = None,
) -> dict[str, Any]:
    batch_a = plan["batch_a"]
    batch_b = plan["batch_b"]
    ids, priorities = _plan_subset(plan, frame["sample_id"].astype(str).tolist(), excluded_ids)
    indexed = frame.set_index(frame["sample_id"].astype(str), drop=False)
    rows = indexed.loc[ids]
    values = rows[feature].to_numpy(dtype=np.float64)
    labels = rows["batch"].astype(str).to_numpy()
    finite = np.isfinite(values)
    values = values[finite]
    labels = labels[finite]
    ids_finite = np.asarray(ids, dtype=object)[finite]
    priorities = priorities[:, finite]
    if scale <= 0 or not np.isfinite(scale):
        return {"z": float("nan"), "p": float("nan"), "z_perm": None,
                "median_a": float("nan"), "median_b": float("nan"),
                "n_a": 0, "n_b": 0}
    mask_a = labels == batch_a
    mask_b = labels == batch_b
    n_a, n_b = int(mask_a.sum()), int(mask_b.sum())
    if n_a == 0 or n_b == 0:
        return {"z": float("nan"), "p": float("nan"), "z_perm": None,
                "median_a": float("nan"), "median_b": float("nan"),
                "n_a": n_a, "n_b": n_b}
    median_a = float(np.median(values[mask_a]))
    median_b = float(np.median(values[mask_b]))
    observed = (median_a - median_b) / scale
    order = np.argsort(priorities, axis=1, kind="stable")
    perm_a = np.median(values[order[:, :n_a]], axis=1)
    perm_b = np.median(values[order[:, n_a:]], axis=1)
    z_perm = (perm_a - perm_b) / scale
    p_value = (1 + np.count_nonzero(np.abs(z_perm) >= abs(observed))) / (1 + len(z_perm))
    return {
        "z": float(observed),
        "p": float(p_value),
        "z_perm": z_perm,
        "median_a": median_a,
        "median_b": median_b,
        "n_a": n_a,
        "n_b": n_b,
        "ids": ids_finite.tolist(),
    }


def _energy_from_distances(distance: np.ndarray, idx_a: np.ndarray, idx_b: np.ndarray) -> float:
    cross = distance[np.ix_(idx_a, idx_b)].mean()
    within_a = distance[np.ix_(idx_a, idx_a)].sum() / (len(idx_a) * (len(idx_a) - 1))
    within_b = distance[np.ix_(idx_b, idx_b)].sum() / (len(idx_b) * (len(idx_b) - 1))
    return float(2 * cross - within_a - within_b)


def _mmd2_from_kernel(kernel: np.ndarray, idx_a: np.ndarray, idx_b: np.ndarray) -> float:
    within_a = kernel[np.ix_(idx_a, idx_a)].sum() - np.trace(kernel[np.ix_(idx_a, idx_a)])
    within_b = kernel[np.ix_(idx_b, idx_b)].sum() - np.trace(kernel[np.ix_(idx_b, idx_b)])
    within_a /= len(idx_a) * (len(idx_a) - 1)
    within_b /= len(idx_b) * (len(idx_b) - 1)
    cross = kernel[np.ix_(idx_a, idx_b)].mean()
    return float(within_a + within_b - 2 * cross)


def _rbf_kernel(vectors: np.ndarray) -> tuple[np.ndarray, float]:
    distances = pairwise_distance_matrix(vectors)
    upper = distances[np.triu_indices(len(distances), k=1)]
    bandwidth = float(np.median(upper))
    if not np.isfinite(bandwidth) or bandwidth <= 0:
        raise ValueError("RBF median pairwise embedding distance must be positive")
    kernel = np.exp(-0.5 * np.square(distances / bandwidth))
    return kernel, bandwidth


def _embedding_permutation_tests(
    frame: pd.DataFrame,
    vectors: np.ndarray,
    plan: dict[str, Any],
    *,
    excluded_ids: set[str] | None = None,
) -> dict[str, Any]:
    available_ids = frame["sample_id"].astype(str).tolist()
    ids, priorities = _plan_subset(plan, available_ids, excluded_ids)
    positions = {sample_id: i for i, sample_id in enumerate(available_ids)}
    source = np.asarray([positions[sample_id] for sample_id in ids], dtype=int)
    vectors = vectors[source]
    labels = frame.set_index(frame["sample_id"].astype(str))["batch"].astype(str).reindex(ids).to_numpy()
    batch_a, batch_b = plan["batch_a"], plan["batch_b"]
    idx_a = np.flatnonzero(labels == batch_a)
    idx_b = np.flatnonzero(labels == batch_b)
    if len(idx_a) < 2 or len(idx_b) < 2:
        raise ValueError("embedding permutation test requires at least two images per group")
    distances = cdist(vectors, vectors, metric="euclidean")
    kernel, bandwidth = _rbf_kernel(vectors)
    observed = {
        "energy": _energy_from_distances(distances, idx_a, idx_b),
        "mmd2": _mmd2_from_kernel(kernel, idx_a, idx_b),
    }
    order = np.argsort(priorities, axis=1, kind="stable")
    permuted = {"energy": np.empty(len(order)), "mmd2": np.empty(len(order))}
    for i, assignment in enumerate(order):
        a = assignment[:len(idx_a)]
        b = assignment[len(idx_a):]
        permuted["energy"][i] = _energy_from_distances(distances, a, b)
        permuted["mmd2"][i] = _mmd2_from_kernel(kernel, a, b)
    p_values = {
        statistic: float((1 + np.count_nonzero(values >= observed[statistic])) / (1 + len(values)))
        for statistic, values in permuted.items()
    }
    return {
        "observed": observed,
        "p": p_values,
        "permuted": permuted,
        "bandwidth": bandwidth,
        "n_a": len(idx_a),
        "n_b": len(idx_b),
    }


def _band_position(value: float, band95: float, band99: float, *, absolute: bool = False) -> str:
    if not np.isfinite(value) or not np.isfinite(band95) or not np.isfinite(band99):
        return "not_applicable"
    tested = abs(value) if absolute else value
    if tested <= band95:
        return "within"
    if tested > band99:
        return "outside"
    return "between"


def _split_plan(
    reference_ids: list[str],
    n_first: int,
    n_second: int,
    n_splits: int,
    seed: int,
) -> list[tuple[list[str], list[str]]]:
    if len(reference_ids) < n_first + n_second:
        raise ValueError(
            f"cannot draw registered null split {n_first}+{n_second} from {len(reference_ids)} images"
        )
    rng = np.random.default_rng(seed)
    ids = np.asarray(reference_ids, dtype=object)
    splits = []
    for _ in range(n_splits):
        first = rng.choice(ids, size=n_first, replace=False).tolist()
        first_set = set(first)
        second = [sample_id for sample_id in reference_ids if sample_id not in first_set]
        if len(second) > n_second:
            second = rng.choice(np.asarray(second, dtype=object), size=n_second, replace=False).tolist()
        splits.append((first, second))
    return splits


def _split_scalar_bands(
    frame: pd.DataFrame,
    feature: str,
    scale: float,
    splits: list[tuple[list[str], list[str]]],
) -> tuple[float, float, np.ndarray]:
    indexed = frame.set_index(frame["sample_id"].astype(str))[feature]
    values = []
    for first, second in splits:
        a = indexed.reindex(first).to_numpy(dtype=np.float64)
        b = indexed.reindex(second).to_numpy(dtype=np.float64)
        values.append(abs((np.median(a) - np.median(b)) / scale))
    array = np.asarray(values, dtype=np.float64)
    return float(np.quantile(array, 0.95)), float(np.quantile(array, 0.99)), array


def _split_embedding_bands(
    vectors: np.ndarray,
    ids: list[str],
    splits: list[tuple[list[str], list[str]]],
) -> dict[str, tuple[float, float, np.ndarray]]:
    positions = {sample_id: i for i, sample_id in enumerate(ids)}
    distances = cdist(vectors, vectors, metric="euclidean")
    kernel, _ = _rbf_kernel(vectors)
    values = {"energy": [], "mmd2": []}
    for first, second in splits:
        idx_a = np.asarray([positions[sample_id] for sample_id in first], dtype=int)
        idx_b = np.asarray([positions[sample_id] for sample_id in second], dtype=int)
        values["energy"].append(_energy_from_distances(distances, idx_a, idx_b))
        values["mmd2"].append(_mmd2_from_kernel(kernel, idx_a, idx_b))
    result = {}
    for statistic, entries in values.items():
        array = np.asarray(entries, dtype=np.float64)
        result[statistic] = (
            float(np.quantile(array, 0.95)),
            float(np.quantile(array, 0.99)),
            array,
        )
    return result


def _reference_loo(
    frame: pd.DataFrame,
    table: str,
    feature: str,
    family: str,
    reference_batch: str,
    threshold: float,
) -> list[dict[str, Any]]:
    reference = frame.loc[frame["batch"] == reference_batch].sort_values("sample_id", kind="stable")
    rows: list[dict[str, Any]] = []
    values = reference[feature].to_numpy(dtype=np.float64)
    ids = reference["sample_id"].astype(str).tolist()
    for index, sample_id in enumerate(ids):
        others = np.delete(values, index)
        median_other = float(np.median(others))
        scale_other = 1.4826 * mad(others)
        value = float(values[index])
        if scale_other == 0:
            robust_z = 0.0 if value == median_other else float(np.copysign(np.inf, value - median_other))
        else:
            robust_z = (value - median_other) / scale_other
        rows.append({
            "table": table,
            "feature": feature,
            "family": family,
            "sample_id": sample_id,
            "value": value,
            "median_other16": median_other,
            "scale_other16": scale_other,
            "robust_z": float(robust_z),
            "outlier": bool(abs(robust_z) > threshold),
        })
    return rows


def _embedding_reference_outliers(
    frame: pd.DataFrame,
    vectors: np.ndarray,
    reference_batch: str,
    threshold: float,
) -> list[dict[str, Any]]:
    reference = frame.loc[frame["batch"] == reference_batch].sort_values("sample_id", kind="stable")
    ids = reference["sample_id"].astype(str).tolist()
    positions = {sample_id: i for i, sample_id in enumerate(frame["sample_id"].astype(str))}
    subset = vectors[[positions[sample_id] for sample_id in ids]]
    distances = cdist(subset, subset, metric="euclidean")
    mean_distances = (distances.sum(axis=1) - np.diag(distances)) / max(len(ids) - 1, 1)
    rows: list[dict[str, Any]] = []
    for i, sample_id in enumerate(ids):
        others = np.delete(mean_distances, i)
        center = float(np.median(others))
        scale = 1.4826 * mad(others)
        robust_z = 0.0 if scale == 0 and mean_distances[i] == center else (
            float(np.inf) if scale == 0 else float((mean_distances[i] - center) / scale)
        )
        rows.append({
            "sample_id": sample_id,
            "mean_distance_to_other_reference": float(mean_distances[i]),
            "median_other16": center,
            "scale_other16": scale,
            "robust_z": robust_z,
            "outlier": bool(robust_z > threshold),
        })
    return rows


def _sensitivity_summary(
    frame: pd.DataFrame,
    feature: str,
) -> float:
    values = frame.pivot(index="sample_id", columns="scale", values=feature)
    expected = (0.9, 1.0, 1.1)
    if not set(expected).issubset(values.columns):
        raise ValueError(f"sensitivity data for {feature} is missing a required scale")
    change = np.maximum(
        np.abs(values[0.9].to_numpy() - values[1.0].to_numpy()),
        np.abs(values[1.1].to_numpy() - values[1.0].to_numpy()),
    )
    return float(np.median(change))


def _rank_stability(
    frame: pd.DataFrame,
    feature: str,
    batches: list[str],
    n_bootstrap: int,
    seed: int,
) -> float:
    values = {
        batch: frame.loc[frame["batch"] == batch, feature].to_numpy(dtype=np.float64)
        for batch in batches
    }
    if any(not len(array) for array in values.values()):
        return float("nan")
    observed = tuple(np.argsort(
        [np.median(values[batch]) for batch in batches], kind="stable"
    ))
    rng = np.random.default_rng(seed)
    matches = 0
    for _ in range(n_bootstrap):
        medians = [
            np.median(rng.choice(values[batch], size=len(values[batch]), replace=True))
            for batch in batches
        ]
        matches += tuple(np.argsort(medians, kind="stable")) == observed
    return float(matches / n_bootstrap)


def _jackknife_se(values: list[float]) -> float:
    array = np.asarray(values, dtype=np.float64)
    array = array[np.isfinite(array)]
    if len(array) < 2:
        return float("nan")
    mean = array.mean()
    return float(np.sqrt((len(array) - 1) / len(array) * np.square(array - mean).sum()))


def _stamp(frame: pd.DataFrame, cfg: dict[str, Any], stats_hash: str) -> pd.DataFrame:
    result = _config.stamp(frame, cfg)
    result["stats_config_hash"] = stats_hash
    result["phase_identity"] = PHASE_IDENTITY
    return result


def _unique_null_bands(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    keys = ["table", "feature", "channel", "statistic", "residualised"]
    return frame.drop_duplicates(subset=keys, keep="first").reset_index(drop=True)


def _record_scalar_row(
    table: str,
    feature: str,
    family: str,
    pair: str,
    raw: dict[str, Any],
    resid: dict[str, Any],
    scale: float,
    band95: float,
    band99: float,
    outlier_ids: list[str],
    loo: dict[str, Any],
    sens_f: float,
    sens_ratio: float,
    prevalence: str,
) -> dict[str, Any]:
    return {
        "table": table,
        "feature": feature,
        "family": family,
        "pair": pair,
        "median_a": raw["median_a"],
        "median_b": raw["median_b"],
        "s_f": scale,
        "z": raw["z"],
        "p_perm": raw["p"],
        "p_bh": np.nan,
        "band95": band95,
        "band99": band99,
        "band_position": _band_position(raw["z"], band95, band99, absolute=True),
        "z_resid": resid["z"],
        "p_resid": resid["p"],
        "n_loo_outliers": len(outlier_ids),
        "loo_outlier_ids": ";".join(outlier_ids),
        "z_loo": loo["z"],
        "p_loo": loo["p"],
        "sens_f": sens_f,
        "sens_ratio": sens_ratio,
        "prevalence_images_outside_band": prevalence,
    }


def _make_distance_matrix(
    records: list[dict[str, Any]],
    table_counts: dict[str, dict[str, int]],
    stats_cfg: dict[str, Any],
) -> pd.DataFrame:
    lookup = {
        (row["table"], row["statistic"], row["residualised"], row["pair"]): row
        for row in records
    }
    rows: list[dict[str, Any]] = []
    for table in TABLE_ORDER:
        for statistic in STATISTIC_ORDER:
            for residualised in (False, True):
                applicable = (
                    statistic == "rms_z" and table in {"kpi", "features"}
                    and (not residualised or table in {"kpi", "features"})
                ) or (
                    statistic == "rms_z" and table == "covariates" and not residualised
                ) or (
                    statistic in {"energy", "mmd2"} and table.startswith("emb_")
                )
                for batch_a in ("Batch_1", "Batch_2", "Batch_3"):
                    for batch_b in ("Batch_1", "Batch_2", "Batch_3"):
                        n_a = table_counts[table].get(batch_a, 0)
                        n_b = table_counts[table].get(batch_b, 0)
                        pair = _pair_name(batch_a, batch_b)
                        if batch_a == batch_b:
                            value, p_perm, p_bh = 0.0, 1.0, 1.0
                            band95 = band99 = np.nan
                            band_position = "diagonal"
                        elif not applicable:
                            value = p_perm = p_bh = band95 = band99 = np.nan
                            band_position = "not_applicable"
                        else:
                            ordered = (batch_a, batch_b)
                            canonical = next(
                                pair_spec for pair_spec in PAIR_ORDER
                                if set(pair_spec) == set(ordered)
                            )
                            source = lookup.get((
                                table, statistic, residualised, _pair_name(*canonical)
                            ))
                            if source is None:
                                value = p_perm = p_bh = band95 = band99 = np.nan
                                band_position = "not_applicable"
                            else:
                                value = source["value"]
                                p_perm = source["p_perm"]
                                p_bh = source["p_bh"]
                                band95, band99 = source["band95"], source["band99"]
                                band_position = source["band_position"]
                        rows.append({
                            "table": table,
                            "statistic": statistic,
                            "batch_a": batch_a,
                            "batch_b": batch_b,
                            "pair": pair,
                            "value": value,
                            "p_perm": p_perm,
                            "p_bh": p_bh,
                            "band95": band95,
                            "band99": band99,
                            "band_position": band_position,
                            "n_a": n_a,
                            "n_b": n_b,
                            "residualised": residualised,
                            "applicable": bool(applicable),
                        })
    return pd.DataFrame(rows)


def run(cfg: dict[str, Any]) -> None:
    started = time.perf_counter()
    stats_cfg, stats_path, stats_hash = _load_stats_config()
    reference_batch = cfg["stats"]["reference_batch"]
    if reference_batch != "Batch_3":
        raise ValueError(f"unexpected reference batch {reference_batch!r}")
    n_permutations = int(stats_cfg["permutations"])
    null_config = stats_cfg.get("null", stats_cfg.get(None))
    if not isinstance(null_config, dict):
        raise ValueError("stats_v1.yaml must define the null-band configuration")
    n_splits = int(null_config["splits"])
    null_sizes = [int(size) for size in null_config["sizes"]]
    n_bootstrap = int(stats_cfg["bootstrap"]["replicates"])
    base_seed = int(stats_cfg["seed"])
    scale_factor = float(stats_cfg["scale"]["consistency_factor"])
    alpha = float(stats_cfg["multiple_testing"]["alpha"])
    loo_threshold = float(stats_cfg["gates"]["G4"]["loo_outlier_robust_z"])
    feature_map = stats_cfg["features"]

    tables, table_features = _read_feature_tables(stats_cfg)
    sensitivities = _read_sensitivity_tables(stats_cfg, table_features)
    all_ids = tables["kpi"]["sample_id"].astype(str).tolist()
    batch_by_id = dict(zip(
        tables["kpi"]["sample_id"].astype(str),
        tables["kpi"]["batch"].astype(str),
        strict=True,
    ))
    batches = ["Batch_1", "Batch_2", "Batch_3"]
    if len(all_ids) != 31 or len(set(all_ids)) != 31:
        raise ValueError(f"expected 31 unique image IDs, found {len(set(all_ids))}")
    if {batch: sum(value == batch for value in batch_by_id.values()) for batch in batches} != {
        "Batch_1": 7, "Batch_2": 7, "Batch_3": 17,
    }:
        raise ValueError("image-level batch counts do not match the preregistered 7/7/17")

    expected_batches = tables["kpi"].set_index("sample_id")["batch"]
    covariates, covariate_features = _load_covariates(stats_cfg, all_ids, expected_batches)
    covariate_matrix = covariates[covariate_features].to_numpy(dtype=np.float64)
    standardized_covariates = (covariate_matrix - covariate_matrix.mean(axis=0)) / np.where(
        covariate_matrix.std(axis=0, ddof=0) == 0,
        1.0,
        covariate_matrix.std(axis=0, ddof=0),
    )

    pair_plans = _make_pair_plans(
        all_ids, batch_by_id, base_seed, n_permutations
    )
    reference_ids = sorted(
        tables["kpi"].loc[tables["kpi"]["batch"] == reference_batch, "sample_id"].astype(str)
    )
    scalar_splits = _split_plan(
        reference_ids, null_sizes[0], null_sizes[1], n_splits, base_seed
    )

    distance_records: list[dict[str, Any]] = []
    null_band_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    covariate_rows: list[dict[str, Any]] = []
    gate_rows: list[dict[str, Any]] = []
    reference_loo_rows: list[dict[str, Any]] = []
    scalar_results: dict[tuple[str, str, str], dict[str, Any]] = {}
    raw_scales: dict[tuple[str, str], float] = {}
    residual_scales: dict[tuple[str, str], float] = {}
    residual_tables: dict[str, pd.DataFrame] = {}
    band_lookup: dict[tuple[str, str, str, bool], tuple[float, float]] = {}
    sensitivity_values: dict[tuple[str, str], float] = {}
    stability_values: dict[tuple[str, str], float] = {}

    for table_name in ("kpi", "features"):
        frame = tables[table_name]
        columns = table_features[table_name]
        residual_values = residualize(
            frame[columns].to_numpy(dtype=np.float64), standardized_covariates
        )
        residual = frame[["sample_id", "batch"]].copy()
        residual[columns] = residual_values
        residual_tables[table_name] = residual
        scales = {}
        resid_scales = {}
        outliers_by_feature: dict[str, list[str]] = {}
        for feature in columns:
            family = str(feature_map[feature]["family"])
            scale = _scale_from_frame(frame, feature, reference_batch)
            resid_scale = _scale_from_frame(residual, feature, reference_batch)
            raw_scales[(table_name, feature)] = scale
            residual_scales[(table_name, feature)] = resid_scale
            scales[feature], resid_scales[feature] = scale, resid_scale
            loo_rows = _reference_loo(
                frame, table_name, feature, family, reference_batch, loo_threshold
            )
            reference_loo_rows.extend(loo_rows)
            outliers_by_feature[feature] = [
                row["sample_id"] for row in loo_rows if row["outlier"]
            ]
            if scale > 0 and np.isfinite(scale):
                b95, b99, _ = _split_scalar_bands(frame, feature, scale, scalar_splits)
                band_lookup[(table_name, feature, "z", False)] = (b95, b99)
                null_band_rows.append({
                    "table": table_name, "feature": feature, "channel": "",
                    "statistic": "|z|", "residualised": False, "band95": b95, "band99": b99,
                })
            if resid_scale > 0 and np.isfinite(resid_scale):
                b95, b99, _ = _split_scalar_bands(residual, feature, resid_scale, scalar_splits)
                band_lookup[(table_name, feature, "z", True)] = (b95, b99)
                null_band_rows.append({
                    "table": table_name, "feature": feature, "channel": "",
                    "statistic": "|z|", "residualised": True, "band95": b95, "band99": b99,
                })
            sens = _sensitivity_summary(sensitivities[table_name], feature)
            sensitivity_values[(table_name, feature)] = sens
            stability_values[(table_name, feature)] = _rank_stability(
                frame, feature, batches, n_bootstrap, base_seed + 1000
            )

        for pair_index, (batch_a, batch_b) in enumerate(PAIR_ORDER):
            pair = _pair_name(batch_a, batch_b)
            plan = pair_plans[pair]
            raw_feature_results: dict[str, dict[str, Any]] = {}
            resid_feature_results: dict[str, dict[str, Any]] = {}
            for feature in columns:
                family = str(feature_map[feature]["family"])
                scale = scales[feature]
                resid_scale = resid_scales[feature]
                raw = _scalar_test(frame, feature, plan, scale)
                resid = _scalar_test(residual, feature, plan, resid_scale)
                raw_feature_results[feature] = raw
                resid_feature_results[feature] = resid
                scalar_results[(table_name, feature, pair)] = raw

                outlier_ids = outliers_by_feature[feature]
                if batch_b == reference_batch and outlier_ids:
                    reference_remaining = frame.loc[
                        (frame["batch"] == reference_batch)
                        & ~frame["sample_id"].astype(str).isin(outlier_ids),
                        feature,
                    ].to_numpy(dtype=np.float64)
                    all_remaining = frame.loc[
                        ~frame["sample_id"].astype(str).isin(outlier_ids), feature
                    ].to_numpy(dtype=np.float64)
                    loo_scale = robust_scale(reference_remaining, all_remaining)
                    loo = _scalar_test(
                        frame, feature, plan, loo_scale, excluded_ids=set(outlier_ids)
                    )
                elif batch_b == reference_batch:
                    loo = raw
                else:
                    loo = {"z": np.nan, "p": np.nan}

                if batch_b == reference_batch:
                    reference_values = frame.loc[frame["batch"] == reference_batch, feature].to_numpy()
                    low, high = np.quantile(reference_values, [0.025, 0.975])
                    batch_values = frame.loc[frame["batch"] == batch_a, feature].to_numpy()
                    prevalence_n = int(np.isfinite(batch_values).sum())
                    prevalence_k = int(np.count_nonzero((batch_values < low) | (batch_values > high)))
                    prevalence = f"{prevalence_k}/{prevalence_n}"
                    band95, band99 = band_lookup.get(
                        (table_name, feature, "z", False), (np.nan, np.nan)
                    )
                    feature_rows.append(_record_scalar_row(
                        table_name, feature, family, pair, raw, resid, scale,
                        band95, band99, outlier_ids, loo, sensitivity_values[(table_name, feature)],
                        sensitivity_values[(table_name, feature)] / scale if scale > 0 else np.nan,
                        prevalence,
                    ))
                else:
                    feature_rows.append(_record_scalar_row(
                        table_name, feature, family, pair, raw, resid, scale,
                        np.nan, np.nan, outlier_ids, {"z": np.nan, "p": np.nan},
                        sensitivity_values[(table_name, feature)],
                        sensitivity_values[(table_name, feature)] / scale if scale > 0 else np.nan,
                        "",
                    ))

            for residualised, feature_results, scale_map in (
                (False, raw_feature_results, scales),
                (True, resid_feature_results, resid_scales),
            ):
                included = [
                    feature for feature in columns
                    if scale_map[feature] > 0
                    and np.isfinite(feature_results[feature]["z"])
                    and feature_results[feature]["z_perm"] is not None
                ]
                if not included:
                    continue
                z_values = np.asarray([feature_results[name]["z"] for name in included])
                z_permuted = np.stack([
                    feature_results[name]["z_perm"] for name in included
                ], axis=1)
                d_observed = float(np.sqrt(np.mean(np.square(z_values))))
                d_permuted = np.sqrt(np.mean(np.square(z_permuted), axis=1))
                p_value = float(
                    (1 + np.count_nonzero(d_permuted >= d_observed))
                    / (1 + len(d_permuted))
                )
                if batch_b == reference_batch:
                    band_values = []
                    for first, second in scalar_splits:
                        z_split = []
                        indexed = frame.set_index(frame["sample_id"].astype(str))
                        source_frame = residual if residualised else frame
                        indexed = source_frame.set_index(source_frame["sample_id"].astype(str))
                        for feature in included:
                            v_a = indexed.loc[first, feature].to_numpy(dtype=np.float64)
                            v_b = indexed.loc[second, feature].to_numpy(dtype=np.float64)
                            z_split.append(
                                (np.median(v_a) - np.median(v_b)) / scale_map[feature]
                            )
                        band_values.append(float(np.sqrt(np.mean(np.square(z_split)))))
                    band_array = np.asarray(band_values)
                    band95 = float(np.quantile(band_array, 0.95))
                    band99 = float(np.quantile(band_array, 0.99))
                    null_band_rows.append({
                        "table": table_name, "feature": "", "channel": "",
                        "statistic": "rms_z", "residualised": residualised,
                        "band95": band95, "band99": band99,
                    })
                else:
                    band95 = band99 = np.nan
                distance_records.append({
                    "table": table_name,
                    "statistic": "rms_z",
                    "pair": pair,
                    "residualised": residualised,
                    "value": d_observed,
                    "p_perm": p_value,
                    "p_bh": np.nan,
                    "band95": band95,
                    "band99": band99,
                    "band_position": _band_position(d_observed, band95, band99),
                    "n_a": int((frame["batch"] == batch_a).sum()),
                    "n_b": int((frame["batch"] == batch_b).sum()),
                    "family": "aggregate",
                })

    for feature in covariate_features:
        scale = _scale_from_frame(covariates, feature, reference_batch)
        raw_scales[("covariates", feature)] = scale
        b95, b99, _ = _split_scalar_bands(
            covariates, feature, scale, scalar_splits
        )
        band_lookup[("covariates", feature, "z", False)] = (b95, b99)
        null_band_rows.append({
            "table": "covariates", "feature": feature, "channel": "",
            "statistic": "|z|", "residualised": False, "band95": b95, "band99": b99,
        })
    for pair_index, (batch_a, batch_b) in enumerate(PAIR_ORDER):
        pair = _pair_name(batch_a, batch_b)
        plan = pair_plans[pair]
        pair_rows = []
        z_results = {}
        for feature in covariate_features:
            scale = raw_scales[("covariates", feature)]
            raw = _scalar_test(covariates, feature, plan, scale)
            z_results[feature] = raw
            if batch_b == reference_batch:
                ref_values = covariates.loc[covariates["batch"] == reference_batch, feature].to_numpy()
                p05, p95 = np.quantile(ref_values, [0.05, 0.95])
                band95, band99 = band_lookup[("covariates", feature, "z", False)]
                pair_rows.append({
                    "table": "covariates",
                    "feature": feature,
                    "family": "covariate",
                    "pair": pair,
                    "median_a": raw["median_a"],
                    "median_b": raw["median_b"],
                    "s_f": scale,
                    "z": raw["z"],
                    "p_perm": raw["p"],
                    "p_bh": np.nan,
                    "band95": band95,
                    "band99": band99,
                    "band_position": _band_position(raw["z"], band95, band99, absolute=True),
                    "z_resid": np.nan,
                    "p_resid": np.nan,
                    "n_loo_outliers": 0,
                    "loo_outlier_ids": "",
                    "z_loo": np.nan,
                    "p_loo": np.nan,
                    "reference_p05": float(p05),
                    "reference_p95": float(p95),
                })
            else:
                pair_rows.append({
                    "table": "covariates",
                    "feature": feature,
                    "family": "covariate",
                    "pair": pair,
                    "median_a": raw["median_a"],
                    "median_b": raw["median_b"],
                    "s_f": scale,
                    "z": raw["z"],
                    "p_perm": raw["p"],
                    "p_bh": np.nan,
                    "band95": np.nan,
                    "band99": np.nan,
                    "band_position": "not_applicable",
                    "z_resid": np.nan,
                    "p_resid": np.nan,
                    "n_loo_outliers": 0,
                    "loo_outlier_ids": "",
                    "z_loo": np.nan,
                    "p_loo": np.nan,
                    "reference_p05": np.nan,
                    "reference_p95": np.nan,
                })
        covariate_rows.extend(pair_rows)
        included = [feature for feature in covariate_features if raw_scales[("covariates", feature)] > 0]
        if included:
            z_values = np.asarray([z_results[name]["z"] for name in included])
            z_permuted = np.stack([z_results[name]["z_perm"] for name in included], axis=1)
            d_observed = float(np.sqrt(np.mean(np.square(z_values))))
            d_permuted = np.sqrt(np.mean(np.square(z_permuted), axis=1))
            p_value = float(
                (1 + np.count_nonzero(d_permuted >= d_observed))
                / (1 + len(d_permuted))
            )
            if batch_b == reference_batch:
                band_values = []
                for first, second in scalar_splits:
                    z_split = []
                    for feature in included:
                        v_a = covariates.set_index("sample_id").loc[first, feature].to_numpy()
                        v_b = covariates.set_index("sample_id").loc[second, feature].to_numpy()
                        z_split.append(
                            (np.median(v_a) - np.median(v_b))
                            / raw_scales[("covariates", feature)]
                        )
                    band_values.append(float(np.sqrt(np.mean(np.square(z_split)))))
                band95 = float(np.quantile(band_values, 0.95))
                band99 = float(np.quantile(band_values, 0.99))
                null_band_rows.append({
                    "table": "covariates", "feature": "", "channel": "",
                    "statistic": "rms_z", "residualised": False,
                    "band95": band95, "band99": band99,
                })
            else:
                band95 = band99 = np.nan
            distance_records.append({
                "table": "covariates", "statistic": "rms_z", "pair": pair,
                "residualised": False, "value": d_observed, "p_perm": p_value,
                "p_bh": np.nan, "band95": band95, "band99": band99,
                "band_position": _band_position(d_observed, band95, band99),
                "n_a": int((covariates["batch"] == batch_a).sum()),
                "n_b": int((covariates["batch"] == batch_b).sum()),
                "family": "covariates",
            })

    # Raw scalar and covariate tests are adjusted only inside their preregistered families.
    feature_frame = pd.DataFrame(feature_rows)
    feature_frame["p_bh"] = benjamini_hochberg(feature_frame["p_perm"].to_numpy())
    covariate_frame = pd.DataFrame(covariate_rows)
    covariate_frame["p_bh"] = benjamini_hochberg(covariate_frame["p_perm"].to_numpy())

    acquisition_rows: list[dict[str, Any]] = []
    drift_by_pair: dict[str, bool] = {}
    for batch_a, batch_b in PAIR_ORDER:
        pair = _pair_name(batch_a, batch_b)
        rows = covariate_frame.loc[covariate_frame["pair"] == pair]
        drifting = rows.loc[rows["p_bh"] < alpha, "feature"].astype(str).tolist()
        drift = bool(drifting)
        drift_by_pair[pair] = drift
        acquisition_rows.append({
            "pair": pair,
            "drift": drift,
            "drifting_covariates": json.dumps(drifting, separators=(",", ":")),
        })
    # Per-feature gates use the image-level permutation, sensitivity, acquisition and LOO results.
    percolation = stats_cfg["percolation_rule"]
    percolation_column = str(percolation["column"])
    if percolation_column not in tables["kpi"].columns:
        raise ValueError(f"{stats_cfg['tables']['kpi']['file']} is missing {percolation_column!r}")
    percolation_values = tables["kpi"][percolation_column].to_numpy(dtype=np.float64)
    percolating_count = int(np.count_nonzero(percolation_values > float(percolation["per_image_threshold"])))
    percolation_share = percolating_count / len(percolation_values)
    graphite_percolates = percolation_share > float(percolation["max_share_of_images"])

    status_rows: list[dict[str, Any]] = []
    for table_name in ("kpi", "features"):
        for feature in table_features[table_name]:
            family = str(feature_map[feature]["family"])
            g5_modes = set(feature_map[feature].get("g5", []))
            if not g5_modes or not g5_modes.issubset(STRUCTURAL_FAILURE_MODES):
                raise ValueError(f"{feature} has a G5 mode not registered as 2-D observable")
            g5_pass = not (
                feature_map[feature].get("requires_not_percolating", False)
                and graphite_percolates
            )
            sens_f = sensitivity_values[(table_name, feature)]
            scale = raw_scales[(table_name, feature)]
            sens_ratio = sens_f / scale if scale > 0 else np.nan
            rank_stability = stability_values[(table_name, feature)]
            per_pair: list[dict[str, Any]] = []
            for batch_a, batch_b in (PAIR_ORDER[1], PAIR_ORDER[2]):
                pair = _pair_name(batch_a, batch_b)
                contrast = feature_frame.loc[
                    (feature_frame["table"] == table_name)
                    & (feature_frame["feature"] == feature)
                    & (feature_frame["pair"] == pair)
                ].iloc[0]
                drift = drift_by_pair[pair]
                g2 = bool(
                    (not drift)
                    or (
                        np.sign(contrast["z_resid"]) == np.sign(contrast["z"])
                        and contrast["p_resid"] < alpha
                    )
                )
                g3 = bool(np.isfinite(sens_f) and scale > 0 and sens_f < 0.5 * scale)
                loo_ids = [
                    sample_id for sample_id in str(contrast["loo_outlier_ids"]).split(";")
                    if sample_id
                ]
                if not loo_ids:
                    g4 = True
                else:
                    g4 = bool(
                        np.sign(contrast["z_loo"]) == np.sign(contrast["z"])
                        and ((contrast["p_loo"] < alpha) == (contrast["p_perm"] < alpha))
                    )
                p_bh = contrast["p_bh"]
                g1 = bool(np.isfinite(p_bh) and p_bh < alpha)
                if not g5_pass or (np.isfinite(sens_ratio) and sens_ratio >= 1.0):
                    pair_status = "drop"
                elif rank_stability >= float(stats_cfg["gates"]["keep"]["rank_stability_min"]) and g2 and g3 and g4:
                    pair_status = "keep"
                else:
                    pair_status = "investigate"
                gate = {
                    "table": table_name,
                    "feature": feature,
                    "family": family,
                    "pair": pair,
                    "G1": g1,
                    "G2": g2,
                    "G3": g3,
                    "G4": g4,
                    "G5": g5_pass,
                    "sens_f": sens_f,
                    "s_f": scale,
                    "sens_ratio": sens_ratio,
                    "rank_stability": rank_stability,
                    "status_pair": pair_status,
                }
                gate_rows.append(gate)
                per_pair.append(gate)
            if not scale > 0 or not np.isfinite(scale):
                status, reason = "drop", "excluded: Batch_3 and all-image MAD scales are zero"
            elif not g5_pass:
                status, reason = (
                    "drop",
                    f"G5 failed: class 1 percolates in {percolating_count}/{len(percolation_values)} images",
                )
            elif np.isfinite(sens_ratio) and sens_ratio >= 1.0:
                status, reason = "drop", f"sensitivity ratio={sens_ratio:.6g} >= 1.0"
            elif (
                rank_stability >= float(stats_cfg["gates"]["keep"]["rank_stability_min"])
                and any(row["G2"] and row["G3"] and row["G4"] for row in per_pair)
            ):
                status, reason = (
                    "keep",
                    f"rank stability={rank_stability:.6g}; G2, G3 and G4 pass for at least one vs-Batch_3 pair",
                )
            else:
                status, reason = (
                    "investigate",
                    f"rank stability={rank_stability:.6g}; keep-rule requirements are not all met",
                )
            status_rows.append({
                "table": table_name,
                "feature": feature,
                "family": family,
                "status": status,
                "reason": reason,
            })

    # Apply the aggregate-distance BH family to the two tables and three pairs.
    aggregate_raw = [
        index for index, row in enumerate(distance_records)
        if row["family"] == "aggregate" and not row["residualised"]
    ]
    aggregate_resid = [
        index for index, row in enumerate(distance_records)
        if row["family"] == "aggregate" and row["residualised"]
    ]
    for indexes in (aggregate_raw, aggregate_resid):
        adjusted = benjamini_hochberg([distance_records[index]["p_perm"] for index in indexes])
        for index, p_bh in zip(indexes, adjusted, strict=True):
            distance_records[index]["p_bh"] = float(p_bh)

    # Embedding inputs are image-level, channel-specific vectors. SE is never pooled with ETD.
    embedding_path = _config.ROOT / stats_cfg["tables"]["embedding"]["file"]
    embedding_frame = pd.read_parquet(embedding_path)
    required_embedding = {"sample_id", "batch", "channel"}
    if required_embedding - set(embedding_frame.columns):
        raise ValueError(f"{embedding_path} is missing columns: {sorted(required_embedding - set(embedding_frame.columns))}")
    embedding_columns = [
        column for column in embedding_frame.columns
        if column.startswith("e") and column[1:].isdigit()
    ]
    if len(embedding_columns) != 384:
        raise ValueError(f"{embedding_path} must contain 384 embedding dimensions")
    embedding_frame = embedding_frame.loc[
        embedding_frame["channel"].isin(EMBEDDING_CHANNELS)
    ].copy()
    embedding_permutation_rows: list[dict[str, Any]] = []
    embedding_outliers: dict[str, list[str]] = {}
    embedding_data: dict[str, dict[str, Any]] = {}
    for channel in EMBEDDING_CHANNELS:
        frame = embedding_frame.loc[embedding_frame["channel"] == channel].copy()
        validate_image_table(frame, f"{embedding_path}:{channel}")
        _all_finite(frame, embedding_columns, f"{embedding_path}:{channel}")
        frame = frame.sort_values("sample_id", kind="stable").reset_index(drop=True)
        if channel in {"BSE", "Inlens"} and len(frame) != 31:
            raise ValueError(f"{channel} must contain 31 image-level embedding vectors")
        if channel == "ETD" and len(frame) != 27:
            raise ValueError(f"ETD must contain exactly 27 image-level embedding vectors")
        if set(frame["batch"]) != set(batches):
            raise ValueError(f"{channel} is missing one or more batches")
        vectors = frame[embedding_columns].to_numpy(dtype=np.float64)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise ValueError(f"{channel} has a zero-norm image embedding")
        vectors = vectors / norms
        cov_for_channel = standardized_covariates[
            [all_ids.index(sample_id) for sample_id in frame["sample_id"].astype(str)]
        ]
        residual_vectors = residualize(vectors, cov_for_channel)
        residual_frame = frame[["sample_id", "batch"]].copy()
        residual_data = {
            "frame": frame,
            "vectors": vectors,
            "residual_frame": residual_frame,
            "residual_vectors": residual_vectors,
        }
        embedding_data[channel] = residual_data
        outlier_rows = _embedding_reference_outliers(
            frame, vectors, reference_batch, loo_threshold
        )
        embedding_outliers[channel] = [
            row["sample_id"] for row in outlier_rows if row["outlier"]
        ]
        b3_frame = frame.loc[frame["batch"] == reference_batch].sort_values("sample_id", kind="stable")
        b3_ids = b3_frame["sample_id"].astype(str).tolist()
        split_sizes = (
            (null_sizes[0], len(b3_ids) - null_sizes[0])
            if channel == "ETD"
            else tuple(null_sizes)
        )
        channel_splits = _split_plan(
            b3_ids, split_sizes[0], split_sizes[1], n_splits, base_seed
        )
        for residualised, current_vectors in (
            (False, vectors),
            (True, residual_vectors),
        ):
            ids = frame["sample_id"].astype(str).tolist()
            positions = {sample_id: i for i, sample_id in enumerate(ids)}
            b3_vectors = current_vectors[[positions[sample_id] for sample_id in b3_ids]]
            split_ids = [tuple((a, b)) for a, b in channel_splits]
            split_stats = _split_embedding_bands(b3_vectors, b3_ids, split_ids)
            for statistic, (band95, band99, _) in split_stats.items():
                embedding_table = f"emb_{channel}"
                band_lookup[(embedding_table, statistic, "embedding", residualised)] = (band95, band99)
                null_band_rows.append({
                    "table": embedding_table, "feature": "", "channel": channel,
                    "statistic": statistic, "residualised": residualised,
                    "band95": band95, "band99": band99,
                })

        for batch_a, batch_b in PAIR_ORDER:
            pair = _pair_name(batch_a, batch_b)
            plan = pair_plans[pair]
            raw_tests = _embedding_permutation_tests(
                frame, vectors, plan
            )
            resid_tests = _embedding_permutation_tests(
                frame, residual_vectors, plan
            )
            if batch_b == reference_batch and embedding_outliers[channel]:
                raw_loo = _embedding_permutation_tests(
                    frame, vectors, plan, excluded_ids=set(embedding_outliers[channel])
                )
                resid_loo = _embedding_permutation_tests(
                    frame, residual_vectors, plan, excluded_ids=set(embedding_outliers[channel])
                )
            else:
                raw_loo, resid_loo = raw_tests, resid_tests
            for residualised, current, loo_current in (
                (False, raw_tests, raw_loo),
                (True, resid_tests, resid_loo),
            ):
                for statistic in ("energy", "mmd2"):
                    table = f"emb_{channel}"
                    value = current["observed"][statistic]
                    p_value = current["p"][statistic]
                    if batch_b == reference_batch:
                        band95, band99 = band_lookup[
                            (table, statistic, "embedding", residualised)
                        ]
                    else:
                        band95 = band99 = np.nan
                    distance_records.append({
                        "table": table,
                        "statistic": statistic,
                        "pair": pair,
                        "residualised": residualised,
                        "value": value,
                        "p_perm": p_value,
                        "p_bh": np.nan,
                        "band95": band95,
                        "band99": band99,
                        "band_position": _band_position(value, band95, band99),
                        "n_a": current["n_a"],
                        "n_b": current["n_b"],
                        "family": "embedding",
                    })
                    embedding_permutation_rows.append({
                        "channel": channel,
                        "pair": pair,
                        "residualised": residualised,
                        "statistic": statistic,
                        "value": value,
                        "p_perm": p_value,
                        "p_loo": loo_current["p"][statistic],
                        "n_a": current["n_a"],
                        "n_b": current["n_b"],
                        "band95": band95,
                        "band99": band99,
                        "band_position": _band_position(value, band95, band99),
                    })

    embedding_raw_indexes = [
        index for index, row in enumerate(distance_records)
        if row["family"] == "embedding" and not row["residualised"]
    ]
    embedding_resid_indexes = [
        index for index, row in enumerate(distance_records)
        if row["family"] == "embedding" and row["residualised"]
    ]
    for indexes in (embedding_raw_indexes, embedding_resid_indexes):
        adjusted = benjamini_hochberg([distance_records[index]["p_perm"] for index in indexes])
        for index, p_bh in zip(indexes, adjusted, strict=True):
            distance_records[index]["p_bh"] = float(p_bh)
    embedding_raw_bh = {
        (row["table"], row["statistic"], row["pair"]): row["p_bh"]
        for row in distance_records
        if row["family"] == "embedding" and not row["residualised"]
    }

    # Covariate aggregate-distance p-values are displayed but do not alter the covariate
    # feature-wise BH calls used to determine acquisition drift.
    covariate_d_rows = [
        row for row in distance_records
        if row["table"] == "covariates" and row["statistic"] == "rms_z"
    ]
    covariate_d_adjusted = benjamini_hochberg([row["p_perm"] for row in covariate_d_rows])
    for row, p_bh in zip(covariate_d_rows, covariate_d_adjusted, strict=True):
        row["p_bh"] = float(p_bh)

    # G5 percolation status is reflected in the feature-status rows and each pair gate.
    embedding_gate_rows: list[dict[str, Any]] = []
    for batch_a, batch_b in (PAIR_ORDER[1], PAIR_ORDER[2]):
        pair = _pair_name(batch_a, batch_b)
        rows_pair = [
            row for row in embedding_permutation_rows
            if row["channel"] == "BSE" and row["pair"] == pair and not row["residualised"]
        ]
        energy = next(row for row in rows_pair if row["statistic"] == "energy")
        mmd = next(row for row in rows_pair if row["statistic"] == "mmd2")
        p_energy_bh = embedding_raw_bh[("emb_BSE", "energy", pair)]
        p_mmd_bh = embedding_raw_bh[("emb_BSE", "mmd2", pair)]
        g1 = bool(p_energy_bh < alpha and p_mmd_bh < alpha)
        drift = drift_by_pair[pair]
        resid_rows = [
            row for row in embedding_permutation_rows
            if row["channel"] == "BSE" and row["pair"] == pair and row["residualised"]
        ]
        resid_energy = next(row for row in resid_rows if row["statistic"] == "energy")
        resid_mmd = next(row for row in resid_rows if row["statistic"] == "mmd2")
        g2 = bool(
            not drift or (resid_energy["p_perm"] < alpha and resid_mmd["p_perm"] < alpha)
        )
        g4 = bool(
            not embedding_outliers["BSE"]
            or (
                (energy["p_perm"] < alpha) == (energy["p_loo"] < alpha)
                and (mmd["p_perm"] < alpha) == (mmd["p_loo"] < alpha)
            )
        )
        embedding_gate_rows.append({
            "channel": "BSE",
            "pair": pair,
            "G1": g1,
            "G2": g2,
            "G4": g4,
            "outlier_ids": ";".join(embedding_outliers["BSE"]),
            "energy": energy["value"],
            "energy_p_perm": energy["p_perm"],
            "energy_p_bh": p_energy_bh,
            "energy_p_loo": energy["p_loo"],
            "mmd2": mmd["value"],
            "mmd2_p_perm": mmd["p_perm"],
            "mmd2_p_bh": p_mmd_bh,
            "mmd2_p_loo": mmd["p_loo"],
        })

    # Consistency: robust feature spread and mean BSE embedding distance, with image jackknife SE.
    consistency_rows: list[dict[str, Any]] = []
    all_scalar_features = [
        (table_name, feature)
        for table_name in ("kpi", "features")
        for feature in table_features[table_name]
        if raw_scales[(table_name, feature)] > 0
    ]
    bse = embedding_data["BSE"]
    bse_frame = bse["frame"]
    bse_ids = bse_frame["sample_id"].astype(str).tolist()
    bse_vectors = bse["vectors"]
    bse_distances = cdist(bse_vectors, bse_vectors)
    for batch in batches:
        feature_scores = []
        for table_name, feature in all_scalar_features:
            frame = tables[table_name]
            values = frame.loc[frame["batch"] == batch, feature].to_numpy(dtype=np.float64)
            feature_scores.append(
                scale_factor * mad(values) / raw_scales[(table_name, feature)]
            )
        c_feat = float(np.median(feature_scores)) if feature_scores else np.nan
        feat_loo = []
        for sample_id in tables["kpi"].loc[tables["kpi"]["batch"] == batch, "sample_id"].astype(str):
            values_per_feature = []
            for table_name, feature in all_scalar_features:
                frame = tables[table_name]
                subset = frame.loc[frame["batch"] == batch]
                keep = subset["sample_id"].astype(str) != sample_id
                values_per_feature.append(
                    scale_factor * mad(subset.loc[keep, feature].to_numpy(dtype=np.float64))
                    / raw_scales[(table_name, feature)]
                )
            feat_loo.append(float(np.median(values_per_feature)))
        c_feat_se = _jackknife_se(feat_loo)

        bse_positions = [
            index for index, label in enumerate(bse_frame["batch"].astype(str))
            if label == batch
        ]
        within = bse_distances[np.ix_(bse_positions, bse_positions)]
        c_emb = float(within.sum() / (len(bse_positions) * (len(bse_positions) - 1)))
        emb_loo = []
        for index in bse_positions:
            remaining = [position for position in bse_positions if position != index]
            matrix = bse_distances[np.ix_(remaining, remaining)]
            emb_loo.append(float(matrix.sum() / (len(remaining) * (len(remaining) - 1))))
        c_emb_se = _jackknife_se(emb_loo)
        consistency_rows.append({
            "batch": batch,
            "C_feat": c_feat,
            "C_feat_se": c_feat_se,
            "C_emb": c_emb,
            "C_emb_se": c_emb_se,
        })
    consistency_frame = pd.DataFrame(consistency_rows)
    feat_rank = consistency_frame["C_feat"].rank(method="min").astype(int).to_numpy()
    emb_rank = consistency_frame["C_emb"].rank(method="min").astype(int).to_numpy()
    ranks = {}
    for index, row in consistency_frame.iterrows():
        ranks[row["batch"]] = {
            "C_feat": int(feat_rank[index]),
            "C_emb": int(emb_rank[index]),
        }
    separable_flags: dict[str, dict[str, bool]] = {"C_feat": {}, "C_emb": {}}
    for metric, se_column in (("C_feat", "C_feat_se"), ("C_emb", "C_emb_se")):
        for left, right in (("Batch_1", "Batch_2"), ("Batch_2", "Batch_3")):
            a = consistency_frame.set_index("batch").loc[left]
            b = consistency_frame.set_index("batch").loc[right]
            separated = bool(
                a[metric] + 1.96 * a[se_column] < b[metric] - 1.96 * b[se_column]
                or b[metric] + 1.96 * b[se_column] < a[metric] - 1.96 * a[se_column]
            )
            separable_flags[metric][f"{left}|{right}"] = separated
    consistency_frame["ranks"] = consistency_frame["batch"].map(
        lambda batch: json.dumps(ranks[batch], sort_keys=True, separators=(",", ":"))
    )
    consistency_frame["separable_flags"] = json.dumps(
        separable_flags, sort_keys=True, separators=(",", ":")
    )

    # Expand the registered statistics into the requested full long-format matrix.
    table_counts: dict[str, dict[str, int]] = {
        name: frame["batch"].value_counts().to_dict()
        for name, frame in tables.items()
    }
    table_counts["covariates"] = covariates["batch"].value_counts().to_dict()
    for channel, item in embedding_data.items():
        table_counts[f"emb_{channel}"] = item["frame"]["batch"].value_counts().to_dict()
    distance_frame = _make_distance_matrix(distance_records, table_counts, stats_cfg)

    # Stamp and write all ten registered CSV outputs.
    gates_frame = pd.DataFrame(gate_rows)
    status_frame = pd.DataFrame(status_rows)
    embedding_gates_frame = pd.DataFrame(embedding_gate_rows)
    acquisition_frame = pd.DataFrame(acquisition_rows)
    loo_frame = pd.DataFrame(reference_loo_rows)
    null_frame = _unique_null_bands(null_band_rows)
    for frame_name, frame in (
        ("distance_matrix", distance_frame),
        ("feature_contrasts", feature_frame),
        ("covariate_contrasts", covariate_frame),
        ("acquisition_drift", acquisition_frame),
        ("null_bands", null_frame),
        ("gates", gates_frame),
        ("feature_status", status_frame),
        ("embedding_gates", embedding_gates_frame),
        ("consistency", consistency_frame),
        ("reference_loo", loo_frame),
    ):
        output = _stamp(frame, cfg, stats_hash)
        output_path = _config.ROOT / "results" / "stats" / f"{frame_name}.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output.to_csv(output_path, index=False)

    elapsed = time.perf_counter() - started
    print(
        f"stats: {len(feature_frame)} feature contrasts, {len(covariate_frame)} covariate contrasts, "
        f"{len(distance_frame)} distance rows, 10 CSV outputs; {elapsed:.2f}s "
        f"(stats_config={stats_path.name}@{stats_hash})"
    )

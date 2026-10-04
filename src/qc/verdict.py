"""B7 batch verdicts from the committed image-level statistics tables."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from jsonschema import Draft202012Validator

from qc import config as _config

ALPHA = 0.05
REFERENCE_BATCH = "Batch_3"
PAIR_BY_BATCH = {
    "Batch_1": "Batch_1_vs_Batch_3",
    "Batch_2": "Batch_2_vs_Batch_3",
}
RULE_OUTSIDE = (
    "at least two lines from different families (`phase_fraction`, `silicon_particle`, "
    "`void_morphology`, `graphite_morphology`, `embedding`), each from a feature with "
    "status keep (embedding: passes its gates), and no acquisition drift for that pair."
)
RULE_WITHIN = (
    "no feature (any status) and no BSE embedding statistic is beyond band95 with BH p < 0.05, "
    "and no acquisition drift."
)
RULE_INVESTIGATE = (
    "everything else. Signals from features that failed any gate can only give investigate."
)
RULE_INVESTIGATE_ACQUISITION = (
    "Acquisition drift alone gives investigate routed to the microscopy team."
)
RULE_REFERENCE = (
    "each Batch_3 image is scored against the other 16 (robust z as in G4). "
    "Batch_3 is never outside_bounds; it is investigate if any Batch_3 image is a leave-one-out "
    "outlier on features from ≥ 2 families, otherwise within_bounds."
)
RULE_ACQUISITION_DRIFT = (
    "**Acquisition drift** for a pair = any covariate with BH-adjusted p < 0.05."
)
RULE_DRIVER = (
    "Select feature contrasts with BH p < 0.05 ordered by absolute z; if none is significant, "
    "select the five largest absolute z values."
)
RULE_ACQUISITION_RANGE = (
    "Flag a batch covariate when its median is strictly outside the Batch_3 5th–95th percentile range."
)
RULE_CONSTANTS = (
    RULE_OUTSIDE,
    RULE_WITHIN,
    RULE_INVESTIGATE,
    RULE_INVESTIGATE_ACQUISITION,
    RULE_REFERENCE,
    RULE_ACQUISITION_DRIFT,
)
STATS_FILES = (
    "distance_matrix.csv",
    "feature_contrasts.csv",
    "covariate_contrasts.csv",
    "acquisition_drift.csv",
    "gates.csv",
    "feature_status.csv",
    "embedding_gates.csv",
    "reference_loo.csv",
)


def _as_bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _finite_float(value: Any, name: str) -> float:
    number = _as_float(value)
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return number


def _json_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (bool, int, float, str)):
        if isinstance(value, float) and not np.isfinite(value):
            return None
        return value
    return str(value)


def _read_stats(root: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    dtype = {"config_hash": str, "git_sha": str, "stats_config_hash": str}
    for filename in STATS_FILES:
        path = root / "results" / "stats" / filename
        if not path.is_file():
            raise FileNotFoundError(f"required B4/B5 table is missing: {path}")
        frames[filename.removesuffix(".csv")] = pd.read_csv(path, dtype=dtype)
    return frames


def _row_number_dict(row: pd.Series | dict[str, Any], columns: list[str]) -> dict[str, Any]:
    return {column: _json_value(row[column]) for column in columns}


def _selector_evidence(
    frames: dict[str, pd.DataFrame],
    filename: str,
    selector: str,
    number_columns: list[str],
) -> dict[str, Any]:
    key = Path(filename).name.removesuffix(".csv")
    if key not in frames:
        raise ValueError(f"selector references an unavailable stats table: {filename}")
    selected = frames[key].query(selector, engine="python")
    if selected.empty:
        raise ValueError(f"evidence selector matched no rows: {filename}: {selector}")
    if len(selected) != 1:
        raise ValueError(
            f"evidence selector must identify one row, matched {len(selected)}: {filename}: {selector}"
        )
    row = selected.iloc[0]
    return {
        "file": f"results/stats/{Path(filename).name}",
        "selector": selector,
        "numbers": _row_number_dict(row, number_columns),
    }


def validate_evidence_selectors(
    documents: list[dict[str, Any]],
    root: Path | None = None,
) -> None:
    """Execute every emitted pandas-query selector and compare attached row values."""
    root = root or _config.ROOT
    cache: dict[str, pd.DataFrame] = {}

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            if {"file", "selector"}.issubset(item):
                filename = str(item["file"])
                if filename not in cache:
                    cache[filename] = pd.read_csv(
                        root / filename,
                        dtype={"config_hash": str, "git_sha": str, "stats_config_hash": str},
                    )
                selected = cache[filename].query(str(item["selector"]), engine="python")
                if selected.empty:
                    raise ValueError(f"evidence selector matched no rows: {filename}: {item['selector']}")
                numbers = item.get("numbers", {})
                row = selected.iloc[0]
                for column, expected in numbers.items():
                    if column not in row.index:
                        raise ValueError(f"selector number column {column!r} is absent from {filename}")
                    actual = row[column]
                    if expected is None:
                        if pd.notna(actual):
                            raise ValueError(
                                f"selector number mismatch {filename}:{column}: {actual!r} != null"
                            )
                    elif isinstance(expected, bool):
                        if _as_bool(actual) != expected:
                            raise ValueError(
                                f"selector number mismatch {filename}:{column}: {actual!r} != {expected!r}"
                            )
                    elif isinstance(expected, (int, float)):
                        if not np.isclose(_as_float(actual), float(expected), rtol=1e-9, atol=1e-12):
                            raise ValueError(
                                f"selector number mismatch {filename}:{column}: {actual!r} != {expected!r}"
                            )
                    elif str(actual) != str(expected):
                        raise ValueError(
                            f"selector number mismatch {filename}:{column}: {actual!r} != {expected!r}"
                        )
            else:
                for value in item.values():
                    visit(value)
        elif isinstance(item, list):
            for value in item:
                visit(value)

    visit(documents)


def _sorted_feature_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            -abs(_as_float(row.get("z", 0.0))),
            str(row.get("feature", "")),
        ),
    )


def _beyond_band95(row: dict[str, Any]) -> bool:
    return (
        _as_float(row.get("p_bh")) < ALPHA
        and str(row.get("band_position")) in {"between", "outside"}
    )


def decide_verdict(batch: str, stats: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Apply the preregistered section 4 label rules using only stats CSV rows."""
    if batch == REFERENCE_BATCH:
        loo = stats["reference_loo"]
        outliers = loo.loc[loo["outlier"].map(_as_bool)].copy()
        family_counts = outliers.groupby("sample_id")["family"].nunique()
        qualifying_ids = set(family_counts.loc[family_counts >= 2].index.astype(str))
        label = "investigate" if qualifying_ids else "within_bounds"
        return {
            "batch": batch,
            "label": label,
            "rule": RULE_REFERENCE,
            "reference_outliers": outliers.to_dict("records"),
            "qualifying_outlier_ids": sorted(qualifying_ids),
            "feature_rows": [],
            "feature_significant": [],
            "feature_beyond95": [],
            "feature_lines": [],
            "embedding_rows": [],
            "embedding_beyond95": [],
            "embedding_line": False,
            "acquisition_drift": False,
            "drift_row": None,
            "drift_covariate_rows": [],
            "line_families": set(),
        }

    if batch not in PAIR_BY_BATCH:
        raise ValueError(f"unsupported batch {batch!r}")
    pair = PAIR_BY_BATCH[batch]
    contrasts = stats["feature_contrasts"]
    feature_rows_frame = contrasts.loc[contrasts["pair"] == pair].copy()
    if feature_rows_frame.empty:
        raise ValueError(f"no feature contrasts exist for {pair}")
    statuses = stats["feature_status"].set_index(["table", "feature"])["status"].to_dict()
    feature_rows = feature_rows_frame.to_dict("records")
    for row in feature_rows:
        row["status"] = statuses.get((row["table"], row["feature"]), "investigate")
    feature_significant = [
        row for row in feature_rows if _as_float(row.get("p_bh")) < ALPHA
    ]
    feature_beyond95 = [row for row in feature_rows if _beyond_band95(row)]
    feature_lines = [
        row for row in feature_rows
        if str(row.get("band_position")) == "outside"
        and _as_float(row.get("p_bh")) < ALPHA
        and row.get("status") == "keep"
    ]

    distance = stats["distance_matrix"]
    embedding_rows_frame = distance.loc[
        (distance["table"] == "emb_BSE")
        & (distance["residualised"].map(_as_bool) == False)  # noqa: E712
        & (distance["batch_a"] == batch)
        & (distance["batch_b"] == REFERENCE_BATCH)
        & distance["statistic"].isin(["energy", "mmd2"])
    ].copy()
    embedding_rows = embedding_rows_frame.to_dict("records")
    embedding_beyond95 = [row for row in embedding_rows if _beyond_band95(row)]
    gates = stats["embedding_gates"]
    gate_match = gates.loc[gates["pair"] == pair]
    if gate_match.empty:
        raise ValueError(f"no BSE embedding gate row exists for {pair}")
    embedding_gate = gate_match.iloc[0]
    embedding_passes = all(_as_bool(embedding_gate[name]) for name in ("G1", "G2", "G4"))
    embedding_line = bool(
        embedding_passes
        and any(
            str(row.get("band_position")) == "outside"
            and _as_float(row.get("p_bh")) < ALPHA
            for row in embedding_rows
        )
    )

    drift_match = stats["acquisition_drift"].loc[
        stats["acquisition_drift"]["pair"] == pair
    ]
    if drift_match.empty:
        raise ValueError(f"no acquisition-drift row exists for {pair}")
    drift_row = drift_match.iloc[0].to_dict()
    acquisition_drift = _as_bool(drift_row["drift"])
    drifting_names = json.loads(str(drift_row["drifting_covariates"]))
    drift_covariate_rows = stats["covariate_contrasts"].loc[
        (stats["covariate_contrasts"]["pair"] == pair)
        & (stats["covariate_contrasts"]["feature"].isin(drifting_names))
    ].to_dict("records")
    lines = list(feature_lines)
    if embedding_line:
        lines.append({"family": "embedding", "feature": "BSE DINOv2 embedding"})
    line_families = {str(row["family"]) for row in lines}

    if len(lines) >= 2 and len(line_families) >= 2 and not acquisition_drift:
        label, rule = "outside_bounds", RULE_OUTSIDE
    elif not feature_beyond95 and not embedding_beyond95 and not acquisition_drift:
        label, rule = "within_bounds", RULE_WITHIN
    elif acquisition_drift and not feature_beyond95 and not embedding_beyond95:
        label, rule = "investigate", RULE_INVESTIGATE_ACQUISITION
    else:
        label, rule = "investigate", RULE_INVESTIGATE
    return {
        "batch": batch,
        "pair": pair,
        "label": label,
        "rule": rule,
        "feature_rows": feature_rows,
        "feature_significant": _sorted_feature_rows(feature_significant),
        "feature_beyond95": feature_beyond95,
        "feature_lines": _sorted_feature_rows(feature_lines),
        "embedding_rows": embedding_rows,
        "embedding_beyond95": embedding_beyond95,
        "embedding_line": embedding_line,
        "embedding_gate": embedding_gate.to_dict(),
        "acquisition_drift": acquisition_drift,
        "drift_row": drift_row,
        "drift_covariate_rows": drift_covariate_rows,
        "line_families": line_families,
    }


def _feature_units(feature: str) -> str:
    name = feature.lower()
    if "_px2" in name or "area_mean_px" in name:
        return "px²"
    if "_px" in name:
        return "px"
    if "per_mpx" in name:
        return "per Mpx"
    if "fraction" in name or "frac_" in name or "frac" in name:
        return "fraction"
    return "dimensionless"


def _format_p(value: Any) -> str:
    return f"{_finite_float(value, 'p_bh'):.3g}"


def _format_feature_reason(row: dict[str, Any]) -> str:
    return (
        f"{row['feature']} (z={_finite_float(row['z'], 'z'):.3g}, "
        f"band={row['band_position']}, BH p={_format_p(row['p_bh'])})"
    )


def _reason_for_decision(decision: dict[str, Any]) -> str:
    if decision["batch"] == REFERENCE_BATCH:
        outliers = decision["reference_outliers"]
        qualifying = decision["qualifying_outlier_ids"]
        top = sorted(
            outliers,
            key=lambda row: (-abs(_as_float(row["robust_z"])), str(row["feature"])),
        )[:5]
        drivers = ", ".join(
            f"{row['feature']} on {row['sample_id']} (robust z={_finite_float(row['robust_z'], 'robust_z'):.3g})"
            for row in top
        )
        if qualifying:
            return (
                f"Batch_3 has {len(qualifying)} of 17 images with leave-one-out outliers "
                f"across at least two families; drivers are {drivers} at robust |z| > 3.5."
            )
        if outliers:
            return (
                f"Batch_3 has {len(outliers)} leave-one-out feature outliers across "
                f"{len({row['family'] for row in outliers})} families, but no image spans two families; "
                f"drivers are {drivers} at robust |z| > 3.5."
            )
        return (
            "none is significant among 17 Batch_3 leave-one-out feature checks at robust |z| > 3.5; "
            "no image has outliers in at least two families."
        )

    significant = decision["feature_significant"]
    rows_for_reason = significant[:5] if significant else _sorted_feature_rows(decision["feature_rows"])[:5]
    feature_text = ", ".join(_format_feature_reason(row) for row in rows_for_reason)
    if significant:
        sentence = f"different from Batch_3 in {feature_text}"
    else:
        sentence = (
            f"none is significant among feature contrasts; top |z| contrasts are {feature_text}; "
            "no difference beyond the null band in feature contrasts was supported at BH p < 0.05"
        )

    embedding_rows = {
        str(row["statistic"]): row for row in decision["embedding_rows"]
    }
    if embedding_rows:
        e = embedding_rows.get("energy")
        m = embedding_rows.get("mmd2")
        if e is not None and m is not None:
            sentence += (
                f"; BSE embedding energy={_finite_float(e['value'], 'energy'):.3g} "
                f"(band={e['band_position']}, BH p={_format_p(e['p_bh'])}) and "
                f"MMD²={_finite_float(m['value'], 'mmd2'):.3g} "
                f"(band={m['band_position']}, BH p={_format_p(m['p_bh'])})"
            )
    if decision["acquisition_drift"]:
        drifting = decision["drift_covariate_rows"]
        drift_text = ", ".join(
            f"{row['feature']} (BH p={_format_p(row['p_bh'])})"
            for row in drifting
        )
        sentence += f"; acquisition drift is flagged in {drift_text}"
    return sentence.rstrip(".") + "."


def _driver_justification(
    frames: dict[str, pd.DataFrame],
    row: dict[str, Any],
    pair: str,
) -> dict[str, Any]:
    table = str(row["table"])
    feature = str(row["feature"])
    feature_selector = (
        f"table == '{table}' and feature == '{feature}' and pair == '{pair}'"
    )
    status_selector = f"table == '{table}' and feature == '{feature}'"
    gate_selector = (
        f"table == '{table}' and feature == '{feature}' and pair == '{pair}'"
    )
    columns = [
        "median_a", "median_b", "z", "p_bh", "band99", "band_position",
        "prevalence_images_outside_band", "sens_ratio",
    ]
    evidence = [
        _selector_evidence(
            frames, "feature_contrasts.csv", feature_selector, columns
        ),
        _selector_evidence(
            frames, "feature_status.csv", status_selector, ["status", "family"]
        ),
        _selector_evidence(
            frames, "gates.csv", gate_selector,
            ["G1", "G2", "G3", "G4", "G5", "rank_stability", "status_pair"],
        ),
    ]
    return {
        "rule": RULE_DRIVER,
        "numbers": {
            "z": _finite_float(row["z"], "z"),
            "p_bh": _finite_float(row["p_bh"], "p_bh"),
            "band99": _finite_float(row["band99"], "band99"),
            "band_position": str(row["band_position"]),
            "status": str(row["status"]),
            "family": str(row["family"]),
        },
        "evidence": evidence,
    }


def _make_feature_driver(
    frames: dict[str, pd.DataFrame],
    row: dict[str, Any],
    pair: str,
) -> dict[str, Any]:
    return {
        "name": str(row["feature"]),
        "units": _feature_units(str(row["feature"])),
        "value": _finite_float(row["median_a"], "median_a"),
        "reference_median": _finite_float(row["median_b"], "median_b"),
        "effect_size": _finite_float(row["z"], "z"),
        "direction": "higher" if _as_float(row["z"]) > 0 else "lower",
        "prevalence_images_outside_band": str(row["prevalence_images_outside_band"]),
        "threshold_sensitivity": _finite_float(row["sens_ratio"], "sens_ratio"),
        "p_bh": _finite_float(row["p_bh"], "p_bh"),
        "band_position": str(row["band_position"]),
        "band99": _finite_float(row["band99"], "band99"),
        "status": str(row["status"]),
        "family": str(row["family"]),
        "justification": _driver_justification(frames, row, pair),
    }


def _make_reference_driver(
    frames: dict[str, pd.DataFrame],
    row: dict[str, Any],
) -> dict[str, Any]:
    table = str(row["table"])
    feature = str(row["feature"])
    sample_id = str(row["sample_id"])
    selector = (
        f"table == '{table}' and feature == '{feature}' and sample_id == '{sample_id}'"
    )
    status_selector = f"table == '{table}' and feature == '{feature}'"
    gate_selector = (
        f"table == '{table}' and feature == '{feature}' and "
        "pair == 'Batch_1_vs_Batch_3'"
    )
    gate_row = frames["gates"].query(gate_selector, engine="python").iloc[0]
    status_row = frames["feature_status"].query(
        status_selector, engine="python"
    ).iloc[0]
    numbers = ["sample_id", "value", "median_other16", "scale_other16", "robust_z", "outlier"]
    return {
        "name": feature,
        "sample_id": sample_id,
        "units": _feature_units(feature),
        "value": _finite_float(row["value"], "reference value"),
        "reference_median": _finite_float(row["median_other16"], "reference median"),
        "effect_size": _finite_float(row["robust_z"], "robust_z"),
        "direction": "higher" if _as_float(row["robust_z"]) > 0 else "lower",
        "prevalence_images_outside_band": "1/17",
        "family": str(row["family"]),
        "status": str(status_row["status"]),
        "threshold_sensitivity": _finite_float(
            gate_row["sens_ratio"], "reference feature sens_ratio"
        ),
        "justification": {
            "rule": RULE_REFERENCE,
            "numbers": {
                "robust_z": _finite_float(row["robust_z"], "robust_z"),
                "outlier": _as_bool(row["outlier"]),
                "sample_id": sample_id,
                "threshold_sensitivity": _finite_float(
                    gate_row["sens_ratio"], "reference feature sens_ratio"
                ),
            },
            "evidence": [
                _selector_evidence(frames, "reference_loo.csv", selector, numbers),
                _selector_evidence(
                    frames, "feature_status.csv", status_selector, ["status", "family"]
                ),
                _selector_evidence(
                    frames, "gates.csv", gate_selector, ["sens_ratio", "s_f", "G4"]
                ),
            ],
        },
    }


def _decision_evidence(
    frames: dict[str, pd.DataFrame],
    decision: dict[str, Any],
    batch: str,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    drift_row = decision["drift_row"]
    drift_pair = (
        decision["pair"]
        if batch != REFERENCE_BATCH
        else "Batch_1_vs_Batch_3"
    )
    evidence.append(_selector_evidence(
        frames,
        "acquisition_drift.csv",
        f"pair == '{drift_pair}'",
        ["pair", "drift", "drifting_covariates"],
    ))

    if batch == REFERENCE_BATCH:
        loo_rows = decision["reference_outliers"]
        if not loo_rows:
            ref = frames["reference_loo"].sort_values(
                ["table", "feature", "sample_id"], kind="stable"
            ).iloc[0]
            loo_rows = [ref.to_dict()]
        for row in loo_rows[:5]:
            table, feature, sample_id = row["table"], row["feature"], row["sample_id"]
            selector = (
                f"table == '{table}' and feature == '{feature}' and sample_id == '{sample_id}'"
            )
            evidence.append(_selector_evidence(
                frames, "reference_loo.csv", selector,
                ["sample_id", "family", "robust_z", "outlier"],
            ))
        return evidence

    contrast_candidates = (
        decision["feature_lines"]
        or decision["feature_significant"]
        or _sorted_feature_rows(decision["feature_rows"])[:1]
    )
    for row in contrast_candidates[:5]:
        table, feature, pair = row["table"], row["feature"], decision["pair"]
        selector = (
            f"table == '{table}' and feature == '{feature}' and pair == '{pair}'"
        )
        evidence.append(_selector_evidence(
            frames, "feature_contrasts.csv", selector,
            ["z", "p_bh", "band99", "band_position"],
        ))
        status_selector = f"table == '{table}' and feature == '{feature}'"
        evidence.append(_selector_evidence(
            frames, "feature_status.csv", status_selector, ["status", "family"]
        ))
    for statistic in ("energy", "mmd2"):
        selector = (
            f"table == 'emb_BSE' and statistic == '{statistic}' and "
            f"batch_a == '{batch}' and batch_b == 'Batch_3' and residualised == False"
        )
        evidence.append(_selector_evidence(
            frames, "distance_matrix.csv", selector,
            ["value", "p_bh", "band99", "band_position"],
        ))
    evidence.append(_selector_evidence(
        frames,
        "embedding_gates.csv",
        f"channel == 'BSE' and pair == '{decision['pair']}'",
        ["G1", "G2", "G4", "outlier_ids"],
    ))
    return evidence


def _make_verdict_justification(
    frames: dict[str, pd.DataFrame],
    decision: dict[str, Any],
    n_images: int,
) -> dict[str, Any]:
    if decision["batch"] == REFERENCE_BATCH:
        qualifying = decision["qualifying_outlier_ids"]
        numbers = {
            "n_images": n_images,
            "n_reference_loo_outliers": len(decision["reference_outliers"]),
            "n_images_with_outliers_in_at_least_two_families": len(qualifying),
        }
    else:
        numbers = {
            "n_images": n_images,
            "n_feature_lines": len(decision["feature_lines"]),
            "n_distinct_line_families": len(decision["line_families"]),
            "n_feature_signals_beyond_band95": len(decision["feature_beyond95"]),
            "n_embedding_signals_beyond_band95": len(decision["embedding_beyond95"]),
            "acquisition_drift_suspected": decision["acquisition_drift"],
        }
    return {
        "rule": decision["rule"],
        "numbers": numbers,
        "evidence": _decision_evidence(frames, decision, decision["batch"]),
    }


def _make_embedding_evidence(
    frames: dict[str, pd.DataFrame],
    decision: dict[str, Any],
    n_permutations: int,
) -> dict[str, Any]:
    if decision["batch"] == REFERENCE_BATCH:
        energy_selector = (
            "table == 'emb_BSE' and statistic == 'energy' and batch_a == 'Batch_3' "
            "and batch_b == 'Batch_3' and residualised == False"
        )
        mmd_selector = (
            "table == 'emb_BSE' and statistic == 'mmd2' and batch_a == 'Batch_3' "
            "and batch_b == 'Batch_3' and residualised == False"
        )
        energy = frames["distance_matrix"].query(energy_selector, engine="python").iloc[0]
        mmd = frames["distance_matrix"].query(mmd_selector, engine="python").iloc[0]
        return {
            "backbone": "dinov2_vits14",
            "energy_distance": _finite_float(energy["value"], "Batch_3 diagonal energy"),
            "mmd": _finite_float(mmd["value"], "Batch_3 diagonal mmd2"),
            "permutation_p": _finite_float(energy["p_bh"], "Batch_3 diagonal energy p_bh"),
            "energy_p_bh": _finite_float(energy["p_bh"], "Batch_3 diagonal energy p_bh"),
            "mmd2_p_bh": _finite_float(mmd["p_bh"], "Batch_3 diagonal mmd2 p_bh"),
            "energy_band_position": str(energy["band_position"]),
            "mmd2_band_position": str(mmd["band_position"]),
            "n_permutations": n_permutations,
            "justification": {
                "rule": (
                    "Batch_3 is the reference; diagonal embedding distances are descriptive "
                    "and do not determine its leave-one-out verdict."
                ),
                "numbers": {
                    "energy_distance": _finite_float(energy["value"], "Batch_3 diagonal energy"),
                    "energy_p_bh": _finite_float(energy["p_bh"], "Batch_3 diagonal energy p_bh"),
                    "mmd2": _finite_float(mmd["value"], "Batch_3 diagonal mmd2"),
                    "mmd2_p_bh": _finite_float(mmd["p_bh"], "Batch_3 diagonal mmd2 p_bh"),
                    "n_permutations": n_permutations,
                },
                "evidence": [
                    _selector_evidence(
                        frames,
                        "distance_matrix.csv",
                        energy_selector,
                        ["value", "p_bh", "band_position"],
                    ),
                    _selector_evidence(
                        frames,
                        "distance_matrix.csv",
                        mmd_selector,
                        ["value", "p_bh", "band_position"],
                    )
                ],
            },
        }
    by_statistic = {str(row["statistic"]): row for row in decision["embedding_rows"]}
    energy = by_statistic["energy"]
    mmd = by_statistic["mmd2"]
    pair = decision["pair"]
    energy_selector = (
        f"table == 'emb_BSE' and statistic == 'energy' and batch_a == '{decision['batch']}' "
        "and batch_b == 'Batch_3' and residualised == False"
    )
    mmd_selector = (
        f"table == 'emb_BSE' and statistic == 'mmd2' and batch_a == '{decision['batch']}' "
        "and batch_b == 'Batch_3' and residualised == False"
    )
    gate_selector = f"channel == 'BSE' and pair == '{pair}'"
    return {
        "backbone": "dinov2_vits14",
        "energy_distance": _finite_float(energy["value"], "BSE energy"),
        "mmd": _finite_float(mmd["value"], "BSE mmd2"),
        "permutation_p": _finite_float(energy["p_bh"], "BSE energy p_bh"),
        "energy_p_bh": _finite_float(energy["p_bh"], "BSE energy p_bh"),
        "mmd2_p_bh": _finite_float(mmd["p_bh"], "BSE mmd2 p_bh"),
        "energy_band_position": str(energy["band_position"]),
        "mmd2_band_position": str(mmd["band_position"]),
        "n_permutations": n_permutations,
        "justification": {
            "rule": "Only BSE embeddings count for verdicts; Inlens and ETD are secondary.",
            "numbers": {
                "energy_distance": _finite_float(energy["value"], "BSE energy"),
                "energy_p_bh": _finite_float(energy["p_bh"], "BSE energy p_bh"),
                "mmd2": _finite_float(mmd["value"], "BSE mmd2"),
                "mmd2_p_bh": _finite_float(mmd["p_bh"], "BSE mmd2 p_bh"),
                "n_permutations": n_permutations,
            },
            "evidence": [
                _selector_evidence(
                    frames, "distance_matrix.csv", energy_selector,
                    ["value", "p_bh", "band99", "band_position"],
                ),
                _selector_evidence(
                    frames, "distance_matrix.csv", mmd_selector,
                    ["value", "p_bh", "band99", "band_position"],
                ),
                _selector_evidence(
                    frames, "embedding_gates.csv", gate_selector,
                    ["G1", "G2", "G4", "outlier_ids"],
                ),
            ],
        },
    }


def _make_acquisition(
    frames: dict[str, pd.DataFrame],
    batch: str,
    image_index: pd.DataFrame,
    covariate_names: list[str],
) -> dict[str, Any]:
    if batch == REFERENCE_BATCH:
        cov_pair = PAIR_BY_BATCH["Batch_1"]
        drift_pair = cov_pair
    else:
        cov_pair = PAIR_BY_BATCH[batch]
        drift_pair = cov_pair
    cov_rows = frames["covariate_contrasts"].loc[
        frames["covariate_contrasts"]["pair"] == cov_pair
    ]
    covariates: dict[str, Any] = {}
    for name in covariate_names:
        matched = cov_rows.loc[cov_rows["feature"] == name]
        if matched.empty:
            raise ValueError(f"covariate contrast is missing {name!r} for {cov_pair}")
        row = matched.iloc[0]
        value_column = "median_b" if batch == REFERENCE_BATCH else "median_a"
        value = _finite_float(row[value_column], f"{name} batch median")
        lower = _finite_float(row["reference_p05"], f"{name} reference p05")
        upper = _finite_float(row["reference_p95"], f"{name} reference p95")
        flag = value < lower or value > upper
        selector = f"feature == '{name}' and pair == '{cov_pair}'"
        covariates[name] = {
            "value": value,
            "training_p05": lower,
            "training_p95": upper,
            "flag": flag,
            "justification": {
                "rule": RULE_ACQUISITION_RANGE,
                "numbers": {
                    "value": value,
                    "training_p05": lower,
                    "training_p95": upper,
                    "flag": flag,
                },
                "evidence": [
                    _selector_evidence(
                        frames,
                        "covariate_contrasts.csv",
                        selector,
                        ["median_a", "median_b", "reference_p05", "reference_p95", "p_bh"],
                    )
                ],
            },
        }
    drift_matches = frames["acquisition_drift"].loc[
        frames["acquisition_drift"]["pair"] == drift_pair
    ]
    if drift_matches.empty:
        raise ValueError(f"acquisition drift table is missing {drift_pair}")
    drift_row = drift_matches.iloc[0]
    drift = False if batch == REFERENCE_BATCH else _as_bool(drift_row["drift"])
    drift_justification = {
        "rule": RULE_ACQUISITION_DRIFT,
        "numbers": {
            "acquisition_drift_suspected": drift,
            "drifting_covariates": str(drift_row["drifting_covariates"]),
            "reference_batch": REFERENCE_BATCH,
        },
        "evidence": [
            _selector_evidence(
                frames,
                "acquisition_drift.csv",
                f"pair == '{drift_pair}'",
                ["pair", "drift", "drifting_covariates"],
            )
        ],
    }
    channels = sorted(
        image_index.loc[
            (image_index["batch"].astype(str) == batch), "channel"
        ].astype(str).unique()
    )
    return {
        "detectors_present": channels,
        "pixel_size_nm": None,
        "pixel_size_confirmed": False,
        "covariates": covariates,
        "acquisition_drift_suspected": drift,
        "drift_justification": drift_justification,
    }


def _uncertainty(
    frames: dict[str, pd.DataFrame],
    decision: dict[str, Any],
    n_images: int,
) -> dict[str, str]:
    gates = frames["gates"]
    if decision["batch"] == REFERENCE_BATCH:
        max_ratio = pd.to_numeric(gates["sens_ratio"], errors="coerce").max()
        outliers = decision["reference_outliers"]
        margin = max(
            (abs(_as_float(row["robust_z"])) - 3.5 for row in outliers),
            default=float("nan"),
        )
        top_rank = pd.to_numeric(gates["rank_stability"], errors="coerce").max()
        g4 = "reference LOO rule"
        rank_label = "maximum reported"
        margin_label = "top reference robust |z| minus 3.5"
    else:
        pair = decision["pair"]
        relevant_gates = gates.loc[gates["pair"] == pair]
        max_ratio = pd.to_numeric(relevant_gates["sens_ratio"], errors="coerce").max()
        top = (
            decision["feature_significant"][0]
            if decision["feature_significant"]
            else _sorted_feature_rows(decision["feature_rows"])[0]
        )
        band99 = _as_float(top.get("band99"))
        margin = abs(_as_float(top.get("z"))) - band99 if np.isfinite(band99) else float("nan")
        gate_match = relevant_gates.loc[
            (relevant_gates["table"] == top["table"])
            & (relevant_gates["feature"] == top["feature"])
        ]
        top_rank = (
            _as_float(gate_match.iloc[0]["rank_stability"])
            if not gate_match.empty else float("nan")
        )
        g4 = (
            f"{top['feature']}={_as_bool(gate_match.iloc[0]['G4'])}"
            if not gate_match.empty else "not available"
        )
        rank_label = "top-feature"
        margin_label = "top-feature absolute z minus band99"
    ratio_text = f"{max_ratio:.4g}" if np.isfinite(max_ratio) else "not available"
    rank_text = f"{top_rank:.4g}" if np.isfinite(top_rank) else "not available"
    margin_text = f"{margin:.4g}" if np.isfinite(margin) else "not applicable"
    return {
        "sampling": f"n={n_images} images; resampling unit is image, not tile.",
        "segmentation": f"maximum feature threshold-sensitivity ratio={ratio_text}.",
        "decision_margin": f"{margin_label}={margin_text}; G4={g4}.",
        "robustness": f"{rank_label} bootstrap rank stability={rank_text}; G4 outcome={g4}.",
    }


def _routing(decision: dict[str, Any]) -> tuple[str, str, str]:
    label = decision["label"]
    if label == "outside_bounds":
        return (
            "materials_expert_review",
            "At least two kept lines span distinct evidence families without acquisition drift.",
            "Route the measured differences to independent materials expert review; do not assign supplier blame.",
        )
    if label == "within_bounds":
        return "none", "No registered escalation condition was met.", "No escalation is indicated by these exploratory results."
    if decision["acquisition_drift"] and not decision["feature_beyond95"] and not decision["embedding_beyond95"]:
        return (
            "microscopy_team",
            "Acquisition drift was flagged without a material signal beyond the null band.",
            "Review acquisition covariates and detector conditions with the microscopy team.",
        )
    return (
        "materials_expert_review",
        "The result requires material-level review under the preregistered investigate rule.",
        "Review the listed image-level evidence with an independent materials expert.",
    )


def build_verdicts(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    root = _config.ROOT
    frames = _read_stats(root)
    stats_cfg = yaml.safe_load((root / "configs" / "stats_v1.yaml").read_text())
    n_permutations = int(stats_cfg["permutations"])
    decisions = {
        batch: decide_verdict(batch, frames)
        for batch in ("Batch_1", "Batch_2", "Batch_3")
    }
    images_path = root / "results" / "audit" / "images.csv"
    images = pd.read_csv(images_path)
    image_required = {"sample_id", "batch", "sha256_BSE"}
    if image_required - set(images.columns):
        raise ValueError(f"{images_path} is missing columns: {sorted(image_required - set(images.columns))}")
    if images["sample_id"].duplicated().any():
        raise ValueError(f"{images_path} contains duplicate sample_id values")
    if images["sha256_BSE"].isna().any():
        raise ValueError(f"{images_path} contains missing sha256_BSE values")
    image_index = pd.read_parquet(root / "results" / "emb_index.parquet")
    index_required = {"sample_id", "batch", "channel", "tile_id"}
    if index_required - set(image_index.columns):
        raise ValueError(f"emb_index.parquet is missing columns: {sorted(index_required - set(image_index.columns))}")
    covariate_names = sorted(
        frames["covariate_contrasts"]["feature"].astype(str).unique().tolist()
    )
    schema = json.loads((root / "schema" / "verdict.schema.json").read_text())
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    features_config_path = root / "configs" / "features_v1.yaml"
    features_hash = hashlib.sha256(features_config_path.read_bytes()).hexdigest()[:12]
    stats_hash = hashlib.sha256(
        (root / "configs" / "stats_v1.yaml").read_bytes()
    ).hexdigest()[:12]
    embeddings_cfg = cfg["embeddings"]
    model_revisions = {
        "dinov2_hub_ref": str(embeddings_cfg["hub_ref"]),
        "dinov2_weights_sha256": str(embeddings_cfg["weights_sha256"]),
        "stats_config_hash": stats_hash,
        "features_config_hash": features_hash,
    }

    documents: list[dict[str, Any]] = []
    for batch in ("Batch_1", "Batch_2", "Batch_3"):
        decision = decisions[batch]
        batch_images = images.loc[images["batch"].astype(str) == batch].copy()
        if batch_images.empty:
            raise ValueError(f"{images_path} contains no rows for {batch}")
        batch_index = image_index.loc[
            (image_index["batch"].astype(str) == batch)
            & (image_index["channel"] == "BSE")
        ]
        if batch_index.empty:
            raise ValueError(f"emb_index.parquet contains no BSE tiles for {batch}")
        n_images = len(batch_images)
        n_tiles = len(batch_index)
        sample_ids = batch_images["sample_id"].astype(str).tolist()
        file_hashes = dict(zip(
            sample_ids,
            batch_images["sha256_BSE"].astype(str).tolist(),
            strict=True,
        ))
        if batch == REFERENCE_BATCH:
            driver_rows = sorted(
                decision["reference_outliers"],
                key=lambda row: (
                    -abs(_as_float(row["robust_z"])),
                    str(row["feature"]),
                ),
            )[:5]
            drivers = [_make_reference_driver(frames, row) for row in driver_rows]
        else:
            candidates = decision["feature_significant"]
            if not candidates:
                candidates = _sorted_feature_rows(decision["feature_rows"])
            drivers = [
                _make_feature_driver(frames, row, decision["pair"])
                for row in candidates[:5]
            ]

        acquisition = _make_acquisition(
            frames, batch, image_index, covariate_names
        )
        stakeholder, routing_reason, next_action = _routing(decision)
        if batch == REFERENCE_BATCH:
            label_rule = RULE_REFERENCE
        else:
            label_rule = decision["rule"]
        verdict = {
            "label": decision["label"],
            "rule": label_rule,
            "reason": _reason_for_decision(decision),
            "justification": _make_verdict_justification(frames, decision, n_images),
        }
        document = {
            "subject": {
                "kind": "batch",
                "id": batch,
                "batch": batch,
                "n_images": n_images,
                "n_tiles": n_tiles,
                "file_hashes": file_hashes,
            },
            "verdict": verdict,
            "pipeline": {
                "git_sha": _config.git_sha(),
                "config_path": cfg["_path"],
                "config_hash": cfg["_hash"],
                "timestamp_utc": timestamp,
                "frozen": False,
                "exploratory": True,
                "model_revisions": model_revisions,
            },
            "acquisition": acquisition,
            "evidence": {
                "drivers": drivers,
                "embedding": _make_embedding_evidence(
                    frames, decision, n_permutations
                ),
            },
            "uncertainty": _uncertainty(frames, decision, n_images),
            "routing": {"stakeholder": stakeholder, "reason": routing_reason},
            "next_action": next_action,
            "caveats": [
                "phase_identity: stated by Polaron, not image-verified",
                "Units are px; pixel size is unconfirmed and pixel_size_nm is null.",
                "BSE cannot distinguish Si from SiOx.",
                "Exploratory; not frozen.",
                "Independent review pending.",
            ],
        }
        documents.append(document)
    validate_documents(documents, schema)
    validate_evidence_selectors(documents, root)
    return documents


def validate_documents(
    documents: list[dict[str, Any]],
    schema: dict[str, Any] | None = None,
) -> None:
    if schema is None:
        schema = json.loads((_config.ROOT / "schema" / "verdict.schema.json").read_text())
    validator = Draft202012Validator(schema)
    for document in documents:
        errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
        if errors:
            error = errors[0]
            location = ".".join(str(part) for part in error.path) or "<root>"
            raise ValueError(f"verdict schema error at {location}: {error.message}")


def run(cfg: dict[str, Any]) -> None:
    documents = build_verdicts(cfg)
    output_dir = _config.ROOT / "results" / "verdicts"
    output_dir.mkdir(parents=True, exist_ok=True)
    for document in documents:
        output_path = output_dir / f"{document['subject']['batch']}.json"
        output_path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        )
    print(
        "verdict: " + ", ".join(
            f"{document['subject']['batch']}={document['verdict']['label']}"
            for document in documents
        )
    )

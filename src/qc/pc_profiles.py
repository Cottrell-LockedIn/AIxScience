"""Exploratory embedding PC correlation profiles (M9-lite; PRD_MODEL_IMPROVEMENTS section 0.3).

Descriptive only: for every PCA component of the frozen v1 model this stage reports Spearman correlations
with the 11 measurements (F01-F11), the 8 pre-registered acquisition covariates and the Phase B KPIs over the
31 training images, then applies a fixed code-level tag rule. Nothing here touches the model, the verdict or
any probability; the frozen prediction is only read (``classify.final_model`` is refit and checked against
``results/v1/final_model.csv``).

Reads:  results/features_per_image.parquet, results/emb_per_image.parquet, results/artefacts_per_image.parquet,
        results/audit/images.csv, results/kpi_per_image.parquet, results/v1/final_model.csv
Writes: results/v1/pc_profiles.csv, results/v1/pc_tags.json

Contract: image id is the unit (n = 31). All claims are exploratory and `review_status: unreviewed` until an
independent reviewer checks the tags (AGENTS.md).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from qc import classify
from qc import config as _config

# Tag rule constants (cited in the output). With n = 31, |rho| = 0.36 is already p ~ 0.05 and 0.7 is p ~ 1e-5;
# the thresholds are deliberately strict.
MATERIAL_MIN_ABS_RHO = 0.7
MATERIAL_MAX_P_BH = 0.05
MATERIAL_MAX_COVARIATE_ABS_RHO = 0.5
IMAGING_MIN_ABS_RHO = 0.5
N_PERMUTATIONS = 2000
SEED = 0
N_IMAGES = 31
UNRESOLVED_TAG = "unresolved image-texture component"
REVIEW_STATUS = "unreviewed"
OUT_DIR = Path("results") / "v1"
PROFILES_CSV = OUT_DIR / "pc_profiles.csv"
TAGS_JSON = OUT_DIR / "pc_tags.json"
CAVEAT = (
    "Tags are descriptive correlations over 31 training images; Phase B could not separate the embedding's "
    "batch signal from acquisition (BH p 0.75 / 0.96 after residualisation)"
)
TAG_RULE = (
    f"material:<F-id> if |rho| >= {MATERIAL_MIN_ABS_RHO} and BH p < {MATERIAL_MAX_P_BH} with a measurement and "
    f"|rho| < {MATERIAL_MAX_COVARIATE_ABS_RHO} with every covariate; imaging:<covariate> if |rho| >= "
    f"{IMAGING_MIN_ABS_RHO} with a covariate and that |rho| exceeds every measurement |rho|; otherwise "
    f"'{UNRESOLVED_TAG}'. rho = Spearman over the 31 training images; p_perm = two-sided permutation p from "
    f"{N_PERMUTATIONS} label-free shuffles of the variable (seed {SEED}), p = (1 + #{{|rho_perm| >= |rho|}}) / "
    f"(1 + {N_PERMUTATIONS}); p_bh = Benjamini-Hochberg within each PC across all its variables."
)
KPI_COLS = [
    "frac_c0", "frac_c1", "frac_c2", "c2_count_density_per_Mpx", "c2_eqdiam_median_px", "c2_eqdiam_p90_px",
    "c0_region_eqdiam_median_px", "c0_region_area_mean_px", "c1_flake_eqdiam_median_px",
    "c1_flake_aspect_median", "c1_largest_component_frac", "c0_cracklike_frac", "c2_tpc_length_px",
]
PLAIN_NAMES = {
    "F01_c0_area_fraction": "void area fraction",
    "F02_c2_area_fraction": "silicon area fraction",
    "F03_c2_eqdiam_median_px": "silicon particle size (median eq. diameter, px)",
    "F04_c2_eqdiam_p90_px": "silicon particle size (p90 eq. diameter, px)",
    "F05_c2_count_density_per_Mpx": "silicon particle count density",
    "F06_c2_clark_evans_R": "silicon spatial regularity (Clark-Evans R)",
    "F07_c2_solidity_area_weighted_median": "silicon particle solidity",
    "F08_c0_local_thickness_median_px": "void local thickness (px)",
    "F09_c0_chord_anisotropy_h_over_v": "void chord anisotropy",
    "F10_c0_fraction_iqr_512px": "void fraction heterogeneity (IQR over 512 px windows)",
    "F11_c2_perimeter_fraction_adjacent_c0": "silicon perimeter touching void",
    "noise_sigma_BSE": "BSE noise sigma",
    "sharpness_BSE": "BSE sharpness",
    "curtaining_score_BSE": "BSE curtaining score",
    "hstripe_score_BSE": "BSE horizontal-stripe score",
    "edge_charging_BSE": "BSE edge charging",
    "edge_charging_Inlens": "Inlens edge charging",
    "height": "image height (px)",
    "nm_per_px_if_tag_true": "pixel size (nm/px, if the file tag is true)",
}


def pc_name(k: int) -> str:
    return f"embedding PC {k}"


def spearman_profile(scores: np.ndarray, v: np.ndarray, rng: np.random.Generator,
                     n_perm: int = N_PERMUTATIONS) -> tuple[np.ndarray, np.ndarray]:
    """Spearman rho of one variable against every PC column plus a two-sided permutation p per PC.

    `scores` is n x n_pcs, `v` is length n. The shuffles are of `v` only (label-free), shared across PCs so
    the null is identical for every PC of the same variable.
    """
    rs = rankdata(scores, axis=0)
    rs = (rs - rs.mean(axis=0)) / rs.std(axis=0)
    rv = rankdata(v)
    rv = (rv - rv.mean()) / rv.std()
    n = len(v)
    rho = rs.T @ rv / n
    perms = np.stack([rng.permutation(rv) for _ in range(n_perm)])
    null = perms @ rs / n
    p = (1 + (np.abs(null) >= np.abs(rho)[None, :]).sum(axis=0)) / (1 + n_perm)
    return rho, p


def bh_adjust(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=np.float64)
    m = len(p)
    order = np.argsort(p, kind="stable")
    ranked = p[order] * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(adjusted, 1.0)
    return out


def tag_pc(measurements: dict[str, tuple[float, float]],
           covariates: dict[str, tuple[float, float]]) -> str:
    """Apply the tag rule to {name: (rho, p_bh)} dicts for the measurements and covariates of one PC."""
    if not measurements or not covariates:
        raise ValueError("tag_pc needs at least one measurement and one covariate")
    top_m = max(measurements, key=lambda n: abs(measurements[n][0]))
    top_c = max(covariates, key=lambda n: abs(covariates[n][0]))
    m_rho, m_p = measurements[top_m]
    c_rho = covariates[top_c][0]
    if abs(m_rho) >= MATERIAL_MIN_ABS_RHO and m_p < MATERIAL_MAX_P_BH and abs(c_rho) < MATERIAL_MAX_COVARIATE_ABS_RHO:
        return f"material:{top_m[:3]}"
    if abs(c_rho) >= IMAGING_MIN_ABS_RHO and abs(c_rho) > abs(m_rho):
        return f"imaging:{top_c}"
    return UNRESOLVED_TAG


def sentence(k: int, tag: str, top_m: dict[str, Any], top_c: dict[str, Any]) -> str:
    name_m = PLAIN_NAMES.get(top_m["name"], top_m["name"])
    name_c = PLAIN_NAMES.get(top_c["name"], top_c["name"])
    if tag.startswith("material:"):
        return (f"PC{k}: tracks {name_m} {top_m['name'][:3]} (rho {top_m['rho']:.2f}); descriptive, not causal.")
    if tag.startswith("imaging:"):
        return (f"PC{k}: image-texture component most correlated with {name_c} (rho {top_c['rho']:.2f}); "
                f"not separable from imaging conditions (Phase B).")
    blocked = (abs(top_m["rho"]) >= MATERIAL_MIN_ABS_RHO and top_m["p_bh"] < MATERIAL_MAX_P_BH
               and abs(top_c["rho"]) >= MATERIAL_MAX_COVARIATE_ABS_RHO)
    why = ("a material tag is blocked because a covariate reaches |rho| >= "
           f"{MATERIAL_MAX_COVARIATE_ABS_RHO}" if blocked else "neither meets the tag thresholds")
    return (f"PC{k}: unresolved image-texture component; strongest correlations are {name_m} "
            f"{top_m['name'][:3]} (rho {top_m['rho']:.2f}) and {name_c} (rho {top_c['rho']:.2f}), {why}; "
            f"not separable from imaging conditions (Phase B).")


def load_kpis(ids: list[str]) -> pd.DataFrame:
    kpi = pd.read_parquet(_config.ROOT / "results" / "kpi_per_image.parquet")
    kpi = kpi.set_index("sample_id").loc[ids, KPI_COLS]
    if not np.isfinite(kpi.to_numpy(dtype=np.float64)).all():
        raise ValueError("non-finite KPI values")
    return kpi


def _variables(frame: pd.DataFrame) -> tuple[list[tuple[str, str, np.ndarray]], pd.DataFrame]:
    ids, batches = frame["sample_id"].tolist(), frame["batch"].tolist()
    cov, cov_names = classify.covariate_frame(ids, batches)
    cov = cov.loc[ids]
    kpi = load_kpis(ids)
    variables = [(c, "measurement", frame[c].to_numpy(dtype=np.float64)) for c in classify.F_COLS]
    variables += [(c, "covariate", cov[c].to_numpy(dtype=np.float64)) for c in cov_names]
    variables += [(c, "kpi", kpi[c].to_numpy(dtype=np.float64)) for c in KPI_COLS]
    return variables, cov


def compute(frame: pd.DataFrame, model: classify.Model) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Long-format profile table and per-PC tag dictionary (no provenance columns yet)."""
    if len(frame) != N_IMAGES:
        raise ValueError(f"expected {N_IMAGES} training images, got {len(frame)}")
    scores = model.pca.transform(frame[classify.EMB_COLS].to_numpy(dtype=np.float64))
    n_pcs = scores.shape[1]
    variables, _ = _variables(frame)
    rng = np.random.default_rng(SEED)
    rows = []
    for name, kind, v in variables:
        rho, p = spearman_profile(scores, v, rng)
        for j in range(n_pcs):
            rows.append({"pc": pc_name(j + 1), "variable": name, "kind": kind,
                         "rho": float(rho[j]), "p_perm": float(p[j])})
    table = pd.DataFrame(rows)
    table["p_bh"] = np.nan
    for pc, idx in table.groupby("pc", sort=False).groups.items():
        table.loc[idx, "p_bh"] = bh_adjust(table.loc[idx, "p_perm"].to_numpy())
    order = {pc_name(j + 1): j for j in range(n_pcs)}
    table = table.sort_values(["pc", "kind", "variable"], key=lambda s: s.map(order) if s.name == "pc" else s,
                              kind="stable").reset_index(drop=True)

    coefs = classify.coefficient_table(model)
    evr = model.pca.explained_variance_ratio_
    pcs: dict[str, Any] = {}
    for j in range(n_pcs):
        name = pc_name(j + 1)
        sub = table[table["pc"] == name]

        def _top(kind: str) -> dict[str, Any]:
            s = sub[sub["kind"] == kind]
            r = s.iloc[int(np.argmax(np.abs(s["rho"].to_numpy())))]
            return {"name": str(r["variable"]), "rho": float(r["rho"]), "p_bh": float(r["p_bh"])}

        def _dict(kind: str) -> dict[str, tuple[float, float]]:
            s = sub[sub["kind"] == kind]
            return {str(r.variable): (float(r.rho), float(r.p_bh)) for r in s.itertuples()}

        top_m, top_c, top_k = _top("measurement"), _top("covariate"), _top("kpi")
        tag = tag_pc(_dict("measurement"), _dict("covariate"))
        pcs[name] = {
            "tag": tag,
            "explained_variance_ratio": float(evr[j]),
            "lr_coef_abs_max": float(coefs.loc[coefs["term"] == name, "coefficient"].abs().max()),
            "top_measurement": top_m,
            "top_covariate": top_c,
            "top_kpi": top_k,
            "sentence": sentence(j + 1, tag, top_m, top_c),
        }
    return table, pcs


def provenance(cfg: dict[str, Any]) -> dict[str, Any]:
    return {"config_hash": cfg["_hash"], "git_sha": _config.git_sha(), "n_images": N_IMAGES,
            "exploratory": True, "phase_identity": classify.PHASE_IDENTITY, "review_status": REVIEW_STATUS}


def build(cfg: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = classify.load_training()
    model = classify.final_model(frame)
    coef_diff = classify.check_frozen_model(model)
    table, pcs = compute(frame, model)
    prov = provenance(cfg)
    for key, value in prov.items():
        table[key] = value
    doc = {
        **prov,
        "model": "v1 final model refit from committed parquet; max |coefficient diff| vs results/v1/final_model.csv "
                 f"= {coef_diff:.3g}",
        "n_pcs": len(pcs),
        "n_variables": int(table["variable"].nunique()),
        "variables_by_kind": {k: int(v) for k, v in table.drop_duplicates("variable")["kind"].value_counts().items()},
        "tag_rule": TAG_RULE,
        "thresholds": {
            "material_min_abs_rho": MATERIAL_MIN_ABS_RHO,
            "material_max_p_bh": MATERIAL_MAX_P_BH,
            "material_max_covariate_abs_rho": MATERIAL_MAX_COVARIATE_ABS_RHO,
            "imaging_min_abs_rho": IMAGING_MIN_ABS_RHO,
            "n_permutations": N_PERMUTATIONS,
            "seed": SEED,
        },
        "caveat": CAVEAT,
        "note": "Descriptive tags only; they do not change the model, the drivers or any verdict. The KPI block "
                "is reported for context and is not used by the tag rule.",
        "tag_counts": {t: int(sum(p["tag"].split(":")[0] == t for p in pcs.values()))
                       for t in ("material", "imaging", UNRESOLVED_TAG)},
        "pcs": pcs,
    }
    return table, doc


def run(cfg: dict[str, Any]) -> None:
    out = _config.ROOT / OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    table, doc = build(cfg)
    table.to_csv(_config.ROOT / PROFILES_CSV, index=False, float_format="%.10g")
    (_config.ROOT / TAGS_JSON).write_text(json.dumps(doc, indent=2) + "\n")
    print(f"[pc_profiles] {len(table)} rows -> {PROFILES_CSV}; tags: {doc['tag_counts']} -> {TAGS_JSON}")
    for name, p in doc["pcs"].items():
        print(f"  {name}: {p['tag']} | {p['sentence']}")

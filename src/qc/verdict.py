"""Decision layer: one traceable verdict per image (and per batch), recommended next action, append-only ledger.

Usage: python -m qc verdict [--classify results/classify/features_f01_f11] [--embedding results/classify/dinov2_vits14_bse_by_image]
       python -m qc decide --id <sample_id|batch> --disposition accepted|rejected|hold --by <name> [--note ...]

Reads:  results/classify/<material>/{predictions,ood,accuracy}.csv, optionally the same for an embedding family,
        results/validate/<material>/decisions.csv (acquisition_confounded per feature), the material feature table,
        results/artefacts_per_image.parquet, results/audit/images.csv, schema/verdict.schema.json
Writes: results/verdict/images/<sample_id>.json  (validated against the schema)
        results/verdict/batches/<batch>.json
        results/verdict/VERDICT.md
        results/verdict/ledger.jsonl              append-only; one line per verdict issued (status `pending`) and one
                                                  line per human disposition (`qc decide`); never rewritten

Decision rule (docs/RULEBOOK.md Sections 1-3, applied per image, relative to Batch_3):
  line (i)  class-0 geometry  : any of F01, F08, F09, F10 with |robust z vs Batch_3| > Z_LINE and not acquisition-confounded
  line (ii) class-2 statistics: any of F02-F07, F11 likewise
  drift     : >= DRIFT_MIN_FLAGS acquisition covariates outside the Batch_3 p05-p95 training range
  outside_bounds = lines (i) and (ii) both fire and no drift           (two independent families, RULEBOOK Section 2)
  investigate    = one line fires, or `matches none` in the open-set screen, or drift, or the image is outside the
                   Batch_3 distribution without a second line
  within_bounds  = inside the Batch_3 distribution, no line fires, no drift - *for the quantities tested*; the
                   cannot-decide list (RULEBOOK Section 4) is attached to every verdict.
The label is a screening outcome. `accepted` / `rejected` are human entries in the ledger, never written by code.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qc import config as _config
from qc.validate import COVARIATES, REFERENCE_BATCH, covariate_table, mad, read_table

Z_LINE = 3.0
DRIFT_MIN_FLAGS = 2
LINE_FAMILIES = {"class-0 geometry": ("F01", "F08", "F09", "F10"),
                 "class-2 statistics": ("F02", "F03", "F04", "F05", "F06", "F07", "F11")}
STATS_TABLES = ("features_f01_f11", "kpi_per_image", "dinov2_vits14_bse_by_image",
                "dinov2_vits14_inlens_by_image", "dinov2_vits14_setype_by_image")
CANNOT_DECIDE = [
    "phase_identity: stated by Polaron, not image-verified (no EDS; Si vs SiOx indistinguishable)",
    "adhesion to the current collector and delamination (interface not in the field of view)",
    "electrical resistance and electrochemical performance (not image quantities)",
    "moisture, residual solvent, binder distribution (not resolvable in BSE)",
    "3D porosity, tortuosity and connectivity (2D sections only)",
    "coating thickness, edge burrs, stripes (coating edge not in frame)",
    "14 of the consultant's 22 failure modes are unobservable in this data (docs/FAILURE_MODE_MAP.md)",
]
ACTIONS = {
    "drift": ("microscopy_team", "re-image or confirm acquisition settings: {k} covariates outside the Batch_3 range ({names}); "
              "differences cannot be attributed to the material until acquisition is balanced"),
    "none": ("materials_expert_review", "image matches none of the known batches on {fam}: hold, request EDS on bright phase and the "
             "supplier's composition sheet; a second independent line is needed before `outside bounds`"),
    "outside": ("powder_supplier", "outside the Batch_3 baseline on two independent families ({lines}): hold the batch, request "
                "supplier CoA / EDS, schedule a cell test; drivers: {drivers}"),
    "one_line": ("materials_expert_review", "differs from Batch_3 on one family ({lines}); drivers: {drivers}. Needed next: a second "
                 "line (other feature family, defect detector or Polaron measurement) before any `outside bounds`"),
    "other_batch": ("materials_expert_review", "inside the {batch} distribution but outside Batch_3 on {fam} (closed-set prediction "
                    "{pred}, confidence {conf:.2f}); review drivers {drivers}; request supplier lot information"),
    "within": ("none", "consistent with the promised Batch_3 baseline for the quantities tested (closed-set {pred}, confidence "
               "{conf:.2f}); accept for these quantities; cannot-decide list attached"),
}


# ------------------------------------------------------------------------------------------------- building blocks
def robust_z_table(feats: pd.DataFrame, cols: list[str], reference: str = REFERENCE_BATCH) -> pd.DataFrame:
    """Per image x feature robust z vs the reference batch; reference images are scored leave-self-out."""
    ref = feats[feats["batch"] == reference]
    rows = []
    for _, r in feats.iterrows():
        R = ref[ref["sample_id"] != r["sample_id"]]
        row = {"sample_id": r["sample_id"]}
        for c in cols:
            x, v = R[c].to_numpy(float), r[c]
            m = mad(x)
            row[c] = float((v - np.nanmedian(x)) / m) if m > 0 and np.isfinite(v) else np.nan
        rows.append(row)
    return pd.DataFrame(rows).set_index("sample_id")


def lines_fired(z: pd.Series, confounded: dict[str, bool]) -> dict[str, list[str]]:
    out = {}
    for fam, prefixes in LINE_FAMILIES.items():
        hits = [c for c in z.index if c[:3] in prefixes and abs(z[c]) > Z_LINE and not confounded.get(c, False)]
        if hits:
            out[fam] = hits
    return out


def covariate_block(cov: pd.Series, ref_cov: pd.DataFrame) -> tuple[dict[str, Any], int, list[str]]:
    block, flags = {}, []
    for c in COVARIATES:
        if c not in cov.index or not np.isfinite(cov[c]):
            continue
        lo, hi = np.nanpercentile(ref_cov[c], 5), np.nanpercentile(ref_cov[c], 95)
        f = bool(cov[c] < lo or cov[c] > hi)
        block[c] = {"value": float(cov[c]), "training_p05": float(lo), "training_p95": float(hi), "flag": f}
        if f:
            flags.append(c)
    return block, len(flags), flags


def best_family(acc: pd.DataFrame, alpha: float = 0.05) -> str:
    """Closed-set family: highest LOIO accuracy among families whose permutation p < alpha; else the table family."""
    a = acc[(acc["split"] == "LOIO") & (acc["model"] == "logreg")].sort_values("accuracy", ascending=False)
    ok = a[a["p_perm"] < alpha]
    return str((ok if len(ok) else a).iloc[0]["family"])


def decide_image(sid: str, batch: str | None, pred_row: pd.Series | None, ood_row: pd.Series, z: pd.Series,
                 confounded: dict[str, bool], cov_block: dict[str, Any], n_flags: int, flag_names: list[str],
                 fam: str, agree: tuple[int, int], sens: dict[str, float]) -> dict[str, Any]:
    lines = lines_fired(z, confounded)
    drift = n_flags >= DRIFT_MIN_FLAGS
    matches_none = bool(ood_row["matches_none"])
    in_ref = bool(ood_row["in_reference"])
    pred = str(pred_row["pred"]) if pred_row is not None else str(ood_row["nearest_batch"])
    conf = float(pred_row[f"p_{pred}"]) if pred_row is not None and f"p_{pred}" in pred_row else float("nan")
    top = z.dropna().abs().sort_values(ascending=False).head(5)
    drivers = [{"name": c, "units": "robust z vs Batch_3 (MAD)", "value": float(z[c]), "reference_median": 0.0,
                "effect_size": float(z[c]), "direction": "higher" if z[c] > 0 else "lower",
                "threshold_sensitivity": float(sens[c]) if c in sens and np.isfinite(sens.get(c, np.nan)) else None}
               for c in top.index]
    drivers = [{k: v for k, v in d.items() if v is not None} for d in drivers]
    dtxt = ", ".join(f"{d['name']} {d['effect_size']:+.1f} MAD" for d in drivers[:3]) or "none"
    ltxt = "; ".join(f"{k}: {', '.join(v)}" for k, v in lines.items()) or "none"
    if drift:
        label, key, rule = "investigate", "drift", f"R-COV / G2: {n_flags} acquisition covariates outside Batch_3 p05-p95 -> at most investigate"
    elif len(lines) >= 2:
        label, key, rule = "outside_bounds", "outside", "RULEBOOK S2: two independent families each |z| > 3 vs Batch_3, not confounded, acquisition balanced"
    elif matches_none:
        label, key, rule = "investigate", "none", f"open-set: outside every known batch at alpha 0.05 on {fam}"
    elif len(lines) == 1:
        label, key, rule = "investigate", "one_line", "RULEBOOK S2: one line fired; second independent line missing"
    elif not in_ref:
        label, key, rule = "investigate", "other_batch", f"open-set: outside the Batch_3 distribution on {fam}; no feature line fired"
    else:
        label, key, rule = "within_bounds", "within", "no line fired, inside the Batch_3 distribution, covariates balanced -> within bounds for the quantities tested"
    stakeholder, action = ACTIONS[key]
    action = action.format(k=n_flags, names=", ".join(flag_names), fam=fam, lines=ltxt, drivers=dtxt, pred=pred, conf=conf,
                           batch=str(ood_row["in_distribution_of"]).split("|")[0])
    batches = [c[2:] for c in ood_row.index if c.startswith("d_")]
    return {
        "subject": {"kind": "image", "id": sid, "batch": batch, "n_images": 1},
        "verdict": {"label": label, "rule": rule,
                    "closed_set": {"predicted_batch": pred, "confidence": conf if np.isfinite(conf) else 0.0,
                                   "note": f"family {fam}; assumes the image is from one of the known batches"},
                    "open_set": {"nearest_batch": str(ood_row["nearest_batch"]),
                                 "distance_to_each_batch": {b: float(ood_row[f"d_{b}"]) for b in batches},
                                 "null_band_95": float("nan") if not np.isfinite(ood_row.get("p_Batch_3", np.nan)) else 0.05,
                                 "matches_known_batch": not matches_none}},
        "acquisition": {"covariates": cov_block, "acquisition_drift_suspected": drift},
        "evidence": {"drivers": drivers, "lines_fired": lines},
        "uncertainty": {"sampling": f"n = 1 image; reference n = {int(ood_row['n_ref_Batch_3'])} Batch_3 images, leave-self-out",
                        "segmentation": ("threshold sensitivity per driver in evidence.drivers" if sens else "not measured for these features"),
                        "decision_margin": f"p vs Batch_3 LOO null = {float(ood_row['p_Batch_3']):.3f} (alpha 0.05)",
                        "robustness": f"closed-set prediction agreed by {agree[0]} of {agree[1]} families"},
        "routing": {"stakeholder": stakeholder, "reason": rule},
        "next_action": action,
        "caveats": CANNOT_DECIDE,
    }


def _clean(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o):
        return None
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def validate_schema(doc: dict[str, Any], schema_path: Path) -> None:
    import jsonschema
    jsonschema.validate(_clean(doc), json.loads(schema_path.read_text()))


def append_ledger(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(_clean(entry), sort_keys=True) + "\n")


def batch_verdict(batch: str, docs: list[dict[str, Any]], pipeline: dict[str, Any]) -> dict[str, Any]:
    labels = [d["verdict"]["label"] for d in docs]
    n = len(docs)
    fired = {}
    for d in docs:
        for fam in d["evidence"]["lines_fired"]:
            fired[fam] = fired.get(fam, 0) + 1
    two = [f for f, k in fired.items() if k >= max(2, n / 2)]
    drift = sum(d["acquisition"]["acquisition_drift_suspected"] for d in docs)
    none_ct = sum(not d["verdict"]["open_set"]["matches_known_batch"] for d in docs)
    out_ref = sum(d["verdict"]["label"] != "within_bounds" for d in docs)
    if drift >= n / 2:
        label, rule, stake = "investigate", f"acquisition drift in {drift}/{n} images -> at most investigate (R-COV)", "microscopy_team"
    elif len(two) >= 2:
        label, rule, stake = "outside_bounds", f"two families fire in >= half the images: {two}", "powder_supplier"
    elif len(two) == 1 or none_ct or labels.count("investigate") >= n / 2:
        label, rule, stake = "investigate", f"lines in >= half the images: {two or 'none'}; matches-none {none_ct}/{n}; investigate {labels.count('investigate')}/{n}", "materials_expert_review"
    else:
        label, rule, stake = "within_bounds", f"{labels.count('within_bounds')}/{n} images within bounds, no family fires in >= half", "none"
    evidence = {"drivers": [], "images_outside_reference": f"{out_ref}/{n}", "lines_fired_counts": fired}
    evidence["stats_pair_tests"] = stats_pair_test_refs(batch)
    return {"subject": {"kind": "batch", "id": batch, "batch": batch, "n_images": n},
            "verdict": {"label": label, "rule": rule},
            "pipeline": pipeline, "acquisition": {"acquisition_drift_suspected": bool(drift >= n / 2)},
            "evidence": evidence,
            "uncertainty": {"sampling": f"n = {n} images", "segmentation": "see image verdicts",
                            "decision_margin": f"{none_ct}/{n} images match no known batch"},
            "routing": {"stakeholder": stake, "reason": f"The {batch} batch is labeled {label} because {rule.rstrip('.')}."},
            "next_action": ("batch-level label is a screening outcome; the human disposition (accept / reject / hold) is "
                            "entered with `qc decide` once downstream evidence (cell test, EDS, CoA) exists"),
            "caveats": CANNOT_DECIDE}


def stats_pair_test_refs(batch: str) -> list[dict[str, str]]:
    if batch == REFERENCE_BATCH:
        pairs = ("Batch_1 vs Batch_3", "Batch_2 vs Batch_3")
    elif batch in {"Batch_1", "Batch_2"}:
        pairs = (f"{batch} vs {REFERENCE_BATCH}",)
    else:
        return []
    return [{"table": table, "path": f"results/stats/{table}/pair_tests.csv", "pair": pair}
            for table in STATS_TABLES for pair in pairs]


# -------------------------------------------------------------------------------------------------------- driver
def run(cfg: dict[str, Any], classify_dir: str = "results/classify/features_f01_f11",
        embedding_dir: str | None = "results/classify/dinov2_vits14_bse_by_image",
        features: str = "results/features/features_f01_f11.parquet", validate_dir: str = "results/validate/features_f01_f11",
        artefacts: str = "results/artefacts_per_image.parquet", images: str = "results/audit/images.csv",
        out: str = "results/verdict", frozen: bool = False) -> Path:
    R = _config.resolve
    cdir, out_dir = R(classify_dir), R(out)
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    (out_dir / "batches").mkdir(parents=True, exist_ok=True)
    acc, pred, ood = (pd.read_csv(cdir / f"{k}.csv") for k in ("accuracy", "predictions", "ood"))
    fam = best_family(acc)
    feats = read_table(R(features))
    cols = [c for c in feats.columns if c[:1] == "F" and c[1:3].isdigit()]
    z = robust_z_table(feats, cols)
    dec = pd.read_csv(R(validate_dir) / "decisions.csv") if (R(validate_dir) / "decisions.csv").exists() else pd.DataFrame()
    confounded = dict(zip(dec.get("feature", []), dec.get("acquisition_confounded", []).astype(bool))) if len(dec) else {}
    sens = dict(zip(dec.get("feature", []), dec.get("threshold_sensitivity", []))) if len(dec) else {}
    cov = covariate_table(read_table(R(artefacts))).set_index("sample_id")
    img = pd.read_csv(R(images)).set_index("sample_id")
    ref_cov = cov.loc[[s for s in cov.index if img.loc[s, "batch"] == REFERENCE_BATCH]]
    edirs = {"material": cdir}
    if embedding_dir and (R(embedding_dir) / "predictions.csv").exists():
        edirs["embedding"] = R(embedding_dir)
    preds = {k: pd.read_csv(d / "predictions.csv") for k, d in edirs.items()}
    pipeline = {**{k: str(v) for k, v in _config.provenance(cfg).items()}, "config_path": str(cfg["_path"]), "config_hash": cfg["_hash"],
                "git_sha": _config.git_sha(), "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                "frozen": frozen, "exploratory": not frozen, "model_revisions": {"closed_set_family": fam}}
    pipeline = {k: v for k, v in pipeline.items() if k in {"git_sha", "git_tag", "config_path", "config_hash", "lock_hash",
                                                           "timestamp_utc", "frozen", "exploratory", "model_revisions"}}
    schema = _config.ROOT / "schema" / "verdict.schema.json"
    run_id = pipeline["timestamp_utc"]
    docs: dict[str, dict[str, Any]] = {}
    sel = pred[(pred["family"] == fam) & (pred["split"] == "LOIO") & (pred["model"] == "logreg")].set_index("sample_id")
    o_sel = ood[ood["family"] == fam].set_index("sample_id")
    for sid in feats["sample_id"]:
        batch = str(img.loc[sid, "batch"])
        votes = []
        for k, p in preds.items():
            sub = p[(p["sample_id"] == sid) & (p["split"] == "LOIO") & (p["model"] == "logreg")]
            votes += sub["pred"].tolist()
        pr = sel.loc[sid] if sid in sel.index else None
        agree = (votes.count(pr["pred"]) if pr is not None else 0, len(votes))
        block, nflag, names = covariate_block(cov.loc[sid], ref_cov[ref_cov.index != sid])
        doc = decide_image(sid, batch, pr, o_sel.loc[sid], z.loc[sid], confounded, block, nflag, names, fam, agree, sens)
        doc["pipeline"] = pipeline
        doc["acquisition"]["detectors_present"] = str(img.loc[sid, "channels"]).split("+")
        doc["acquisition"]["pixel_size_confirmed"] = False
        doc = _clean(doc)
        validate_schema(doc, schema)
        (out_dir / "images" / f"{sid}.json").write_text(json.dumps(doc, indent=1))
        append_ledger(out_dir / "ledger.jsonl", {"run_id": run_id, "kind": "verdict", "subject": sid, "batch": batch,
                                                 "label": doc["verdict"]["label"], "predicted_batch": doc["verdict"]["closed_set"]["predicted_batch"],
                                                 "matches_known_batch": doc["verdict"]["open_set"]["matches_known_batch"],
                                                 "stakeholder": doc["routing"]["stakeholder"], "status": "pending",
                                                 "git_sha": pipeline["git_sha"], "config_hash": cfg["_hash"], "frozen": frozen})
        docs[sid] = doc
    bdocs = {}
    for b in sorted(img["batch"].unique()):
        bd = _clean(batch_verdict(b, [d for d in docs.values() if d["subject"]["batch"] == b], pipeline))
        validate_schema(bd, schema)
        (out_dir / "batches" / f"{b}.json").write_text(json.dumps(bd, indent=1))
        append_ledger(out_dir / "ledger.jsonl", {"run_id": run_id, "kind": "verdict", "subject": b, "batch": b, "label": bd["verdict"]["label"],
                                                 "stakeholder": bd["routing"]["stakeholder"], "status": "pending",
                                                 "git_sha": pipeline["git_sha"], "config_hash": cfg["_hash"], "frozen": frozen})
        bdocs[b] = bd
    tab = pd.DataFrame([{"sample_id": s, "batch": d["subject"]["batch"], "label": d["verdict"]["label"],
                         "closed_set": d["verdict"]["closed_set"]["predicted_batch"],
                         "confidence": round(d["verdict"]["closed_set"]["confidence"], 2),
                         "nearest": d["verdict"]["open_set"]["nearest_batch"],
                         "matches_known": d["verdict"]["open_set"]["matches_known_batch"],
                         "drift": d["acquisition"]["acquisition_drift_suspected"],
                         "lines": "; ".join(d["evidence"]["lines_fired"]) or "-", "stakeholder": d["routing"]["stakeholder"],
                         "next_action": d["next_action"][:110]} for s, d in docs.items()])
    tab.to_csv(out_dir / "verdicts.csv", index=False)
    lines = [f"# Verdicts (screening labels, not dispositions) - closed-set family `{fam}`, {'frozen' if frozen else 'exploratory'}", "",
             f"Provenance: git={pipeline['git_sha']} config={cfg['_hash']} run={run_id}", CANNOT_DECIDE[0], "",
             "Label counts per batch:", "", tab.groupby(["batch", "label"]).size().unstack(fill_value=0).to_markdown(), "",
             "Batch-level:", "", *[f"- **{b}**: `{d['verdict']['label']}` - {d['verdict']['rule']} -> {d['routing']['stakeholder']}" for b, d in bdocs.items()], "",
             "Per image (`next_action` truncated; full text in `images/<id>.json`):", "", tab.to_markdown(index=False), "",
             "Every verdict carries the cannot-decide list; `accepted`/`rejected` exist only as human lines in `ledger.jsonl` (`qc decide`)."]
    (out_dir / "VERDICT.md").write_text("\n".join(lines) + "\n")
    print(f"verdict: {len(docs)} images, {len(bdocs)} batches -> {out_dir.relative_to(_config.ROOT)}/ "
          f"{tab['label'].value_counts().to_dict()}", file=sys.stderr)
    return out_dir


def decide(cfg: dict[str, Any], subject: str, disposition: str, by: str, note: str = "", out: str = "results/verdict") -> None:
    if disposition not in {"accepted", "rejected", "hold"}:
        raise ValueError("disposition must be accepted | rejected | hold")
    append_ledger(_config.resolve(out) / "ledger.jsonl",
                  {"kind": "disposition", "subject": subject, "status": disposition, "decided_by": by, "note": note,
                   "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                   "git_sha": _config.git_sha(), "config_hash": cfg["_hash"]})
    print(f"decide: {subject} -> {disposition} by {by} (appended to ledger)", file=sys.stderr)

import json

import numpy as np
import pandas as pd
import pytest

from qc import classify, config as _config, pc_profiles

ROOT = _config.ROOT


def test_tag_rule_material_imaging_unresolved_on_synthetic_vectors():
    rng = np.random.default_rng(1)
    pc = rng.normal(size=(31, 1))
    base = pc[:, 0]
    rank_rng = np.random.default_rng(0)

    def rho_p(v):
        rho, p = pc_profiles.spearman_profile(pc, v, rank_rng, n_perm=200)
        return float(rho[0]), float(p[0])

    noise = rng.normal(size=31)
    material = rho_p(np.exp(base))                       # monotone: rho = 1
    weak_cov = rho_p(0.1 * base + noise)                 # weak
    imaging = rho_p(-base + 0.2 * noise)                 # strong negative
    assert material[0] == pytest.approx(1.0)
    assert abs(weak_cov[0]) < 0.5
    assert imaging[0] < -0.7

    assert pc_profiles.tag_pc({"F01_c0_area_fraction": material}, {"noise_sigma_BSE": weak_cov}) == "material:F01"
    assert pc_profiles.tag_pc({"F01_c0_area_fraction": weak_cov}, {"noise_sigma_BSE": imaging}) == "imaging:noise_sigma_BSE"
    assert pc_profiles.tag_pc({"F01_c0_area_fraction": weak_cov},
                              {"noise_sigma_BSE": weak_cov}) == pc_profiles.UNRESOLVED_TAG
    # strong measurement but a covariate at |rho| >= 0.5 blocks the material tag; imaging only if it beats the measurement
    assert pc_profiles.tag_pc({"F01_c0_area_fraction": material},
                              {"noise_sigma_BSE": imaging}) == pc_profiles.UNRESOLVED_TAG
    # BH p too large blocks the material tag
    assert pc_profiles.tag_pc({"F01_c0_area_fraction": (0.8, 0.2)},
                              {"noise_sigma_BSE": weak_cov}) == pc_profiles.UNRESOLVED_TAG


def test_bh_adjust_matches_hand_example():
    out = pc_profiles.bh_adjust(np.array([0.01, 0.04, 0.03, 0.5]))
    # sorted 0.01*4/1, 0.03*4/2, 0.04*4/3, 0.5 -> step-down minima 0.04, 0.0533, 0.0533, 0.5
    assert out == pytest.approx([0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.5])


@pytest.fixture(scope="module")
def regenerated():
    frame = classify.load_training()
    model = classify.final_model(frame)
    return pc_profiles.compute(frame, model), pc_profiles.compute(frame, model)


def test_regeneration_is_deterministic_and_matches_committed_outputs(regenerated):
    (table_a, pcs_a), (table_b, pcs_b) = regenerated
    pd.testing.assert_frame_equal(table_a, table_b)
    assert json.dumps(pcs_a, sort_keys=True) == json.dumps(pcs_b, sort_keys=True)

    committed = pd.read_csv(ROOT / pc_profiles.PROFILES_CSV, dtype={"git_sha": str, "config_hash": str})
    assert list(committed[["pc", "variable", "kind"]].itertuples(index=False, name=None)) == \
        list(table_a[["pc", "variable", "kind"]].itertuples(index=False, name=None))
    for col in ("rho", "p_perm", "p_bh"):
        assert np.max(np.abs(committed[col].to_numpy() - table_a[col].to_numpy())) < 1e-9
    assert (committed["n_images"] == 31).all() and committed["exploratory"].all()
    assert (committed["phase_identity"] == classify.PHASE_IDENTITY).all()

    doc = json.loads((ROOT / pc_profiles.TAGS_JSON).read_text())
    assert doc["n_images"] == 31 and doc["exploratory"] is True
    assert doc["phase_identity"] == classify.PHASE_IDENTITY
    assert doc["review_status"] in {"unreviewed", "reviewed"}
    assert doc["caveat"] == pc_profiles.CAVEAT
    assert set(doc["pcs"]) == set(pcs_a)
    for name, p in pcs_a.items():
        c = doc["pcs"][name]
        assert c["tag"] == p["tag"] and c["sentence"] == p["sentence"]
        assert c["explained_variance_ratio"] == pytest.approx(p["explained_variance_ratio"])
        assert c["lr_coef_abs_max"] == pytest.approx(p["lr_coef_abs_max"])
        for key in ("top_measurement", "top_covariate"):
            assert c[key]["name"] == p[key]["name"]
            assert c[key]["rho"] == pytest.approx(p[key]["rho"])


def test_every_driver_pc_in_heldout_and_loio_has_a_tag():
    doc = json.loads((ROOT / pc_profiles.TAGS_JSON).read_text())
    heldout = json.load(open(ROOT / "results" / "v1" / "heldout.json"))
    names = {d["name"] for img in heldout["images"] for d in img["evidence"]["drivers"]}
    loio = pd.read_csv(ROOT / "results" / "v1" / "loio_predictions.csv", dtype=str)
    names |= set(loio[["driver1", "driver2", "driver3"]].to_numpy().ravel())
    pc_names = {n for n in names if n.startswith("embedding PC ")}
    assert pc_names
    for n in pc_names:
        entry = doc["pcs"][n]
        assert entry["tag"].startswith(("material:", "imaging:")) or entry["tag"] == pc_profiles.UNRESOLVED_TAG
        assert entry["sentence"].startswith(f"PC{n.split()[-1]}:")

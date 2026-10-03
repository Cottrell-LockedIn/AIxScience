"""Synthetic checks for classify: a planted batch effect is identified above its permutation null, a label-free
family sits inside the null, drivers are tagged, OOD leave-self-out never uses the image itself, a far-away held-out
image is `matches none`, and no fold splits an image or acquisition group."""
import numpy as np
import pandas as pd

from qc import classify
from tests.test_validate import synthetic


def _tables(seed=0):
    feats, artefacts, images, _ = synthetic(seed)
    feats = feats.drop(columns=["const_feat"])
    return feats, artefacts, images


def test_batch_effect_identified_and_noise_not():
    feats, artefacts, images = _tables()
    tabs = classify.run_tables(feats, artefacts, images, seed=0, n_perm=30)
    acc = tabs["accuracy"].set_index(["family", "split"])
    mat = acc.loc[("material", "LOIO")]
    assert mat["accuracy"] > mat["null_p95"] and mat["p_perm"] < 0.05
    assert mat["accuracy"] > mat["chance_majority"]
    # acquisition covariates track acquisition group, not batch, in the synthetic data -> inside the null band
    acq = acc.loc[("acquisition", "LOIO")]
    assert acq["p_perm"] > 0.05 or acq["accuracy"] <= acq["null_p95"] + 0.1


def test_drivers_tagged_and_batch_feat_leads():
    feats, artefacts, images = _tables()
    tabs = classify.run_tables(feats, artefacts, images, seed=0, n_perm=0)
    drv = tabs["drivers"]
    assert set(drv["driver_type"]) == {"material", "acquisition"}
    # the planted effect is monotone (0 / 1.5 / 3), so it is the top driver for the two extreme batches; the middle
    # batch is not linearly separable on it and may be carried by another coefficient
    both = drv[(drv["family"] == "material+acquisition") & (drv["rank_in_batch"] == 1)].set_index("batch")
    assert both.loc["Batch_1", "feature"] == "batch_feat" and both.loc["Batch_3", "feature"] == "batch_feat"
    assert (both["driver_type"] == both["feature"].map(classify.tag)).all()


def test_ood_leave_self_out_and_reference_flag():
    feats, artefacts, images = _tables()
    tabs = classify.run_tables(feats, artefacts, images, seed=0, n_perm=0)
    ood = tabs["ood"]
    own = ood[ood["family"] == "material"]
    for b in ("Batch_1", "Batch_2", "Batch_3"):
        n_b = (own["batch"] == b).sum()
        assert (own.loc[own["batch"] == b, f"n_ref_{b}"] == n_b - 1).all()
        assert (own.loc[own["batch"] != b, f"n_ref_{b}"] == n_b).all()
    # Batch_1 images sit 3 units from Batch_3 on batch_feat (sd 0.3): they must be outside the reference distribution
    assert not own.loc[own["batch"] == "Batch_1", "in_reference"].any()
    assert own.loc[own["batch"] == "Batch_3", "in_reference"].mean() >= 0.8


def test_heldout_far_image_matches_none_and_near_image_classified():
    feats, artefacts, images = _tables()
    held = pd.DataFrame({"sample_id": ["new_far", "new_b3"], "batch_feat": [50.0, 3.0], "acq_feat": [0.0, 0.0],
                         "noise_feat": [0.0, 0.0]})
    tabs = classify.run_tables(feats, artefacts, images, seed=0, n_perm=0,
                               heldout=held.assign(**{c: 0.0 for c in classify.COVARIATES}))
    h = tabs["heldout"].set_index(["sample_id", "family"])
    assert h.loc[("new_far", "material"), "matches_none"]
    assert h.loc[("new_b3", "material"), "pred_batch"] == "Batch_3"
    assert not h.loc[("new_b3", "material"), "matches_none"]


def test_folds_keep_units_together():
    feats, artefacts, images = _tables()
    df, _ = classify.assemble(feats, artefacts, images)
    for units in (df["sample_id"], df["acq_group"]):
        for train, test in classify.grouped_folds(units):
            assert len(set(units.iloc[test])) == 1
            assert not set(units.iloc[train]) & set(units.iloc[test])

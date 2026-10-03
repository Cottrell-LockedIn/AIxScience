"""Synthetic checks for the validation harness: a planted batch effect must be kept, a planted acquisition-only effect
must be flagged, a constant feature dropped, and no fold may split an image or an acquisition group."""
import numpy as np
import pandas as pd

from qc import validate

BATCHES = ["Batch_1"] * 7 + ["Batch_2"] * 7 + ["Batch_3"] * 17
# 10 acquisition groups; g3, g5, g7 cross batch boundaries like the real (height, res_tag) groups do
GROUPS = ["g0", "g0", "g1", "g1", "g2", "g3", "g3",
          "g3", "g4", "g4", "g5", "g5", "g6", "g6",
          "g5", "g7", "g7", "g7", "g8", "g8", "g8", "g8", "g9", "g9", "g9", "g2", "g2", "g6", "g6", "g1", "g0"]


def synthetic(seed=0):
    rng = np.random.default_rng(seed)
    n = len(BATCHES)
    ids = [f"img{i:05d}" for i in range(n)]
    batch_level = {"Batch_1": 0.0, "Batch_2": 1.5, "Batch_3": 3.0}
    group_level = {g: v for g, v in zip(sorted(set(GROUPS)), rng.normal(0, 2.0, len(set(GROUPS))))}
    batch_feat = np.array([batch_level[b] for b in BATCHES]) + rng.normal(0, 0.3, n)
    acq_feat = np.array([group_level[g] for g in GROUPS]) + rng.normal(0, 0.3, n)
    feats = pd.DataFrame({"sample_id": ids, "batch": BATCHES, "batch_feat": batch_feat, "acq_feat": acq_feat,
                          "noise_feat": rng.normal(0, 1, n), "const_feat": 1.0,
                          "batch_feat_sd": 0.1, "n_tiles": 40, "config_hash": "abc", "git_sha": "def"})
    # covariates: noise tracks the acquisition group (as in the real data), the others are unrelated
    rows = []
    for sid, g in zip(ids, GROUPS):
        base = {"sample_id": sid, "batch": BATCHES[ids.index(sid)], "noise_sigma": 30 + 3 * group_level[g] + rng.normal(0, 0.3),
                "sharpness": rng.normal(2000, 100), "curtaining_score": rng.uniform(0.01, 0.05),
                "hstripe_score": rng.uniform(0.01, 0.05), "mean": rng.normal(60, 3)}
        rows.append({**base, "channel": "BSE", "edge_charging": rng.normal(0, 1)})
        rows.append({**base, "channel": "Inlens", "edge_charging": rng.normal(-1, 1)})
    artefacts = pd.DataFrame(rows)
    heights = {g: 1600 + 50 * i for i, g in enumerate(sorted(set(GROUPS)))}
    images = pd.DataFrame({"sample_id": ids, "batch": BATCHES, "height": [heights[g] for g in GROUPS],
                           "res_tag": ["25399944/25"] * n})
    # threshold sensitivity: batch_feat barely moves under +/-10 % thresholds (scale 0.9 / 1.0 / 1.1)
    sens = pd.concat([pd.DataFrame({"sample_id": ids, "batch": BATCHES, "scale": s, "level": "image",
                                    "batch_feat": batch_feat + (0.0 if s == 1.0 else 0.02 * np.sign(s - 1))})
                      for s in (0.9, 1.0, 1.1)], ignore_index=True)
    return feats, artefacts, images, sens


def _check_folds(folds, units):
    units = np.asarray(units)
    seen = []
    for train, test in folds:
        assert len(set(train) & set(test)) == 0
        assert len(test) > 0 and len(train) > 0
        assert len(set(units[test])) == 1, "a test fold must hold exactly one unit"
        assert not set(units[test]) & set(units[train]), "unit split across train and test"
        seen.extend(test)
    assert sorted(seen) == list(range(len(units))), "every row is tested exactly once"


def test_folds_never_split_an_image_or_group():
    feats, artefacts, images, _ = synthetic()
    df, _ = validate.assemble(feats, artefacts, images)
    _check_folds(validate.loio_folds(df["sample_id"]), df["sample_id"])
    _check_folds(validate.logo_folds(df["acq_group"]), df["acq_group"])
    assert sum(1 for _ in validate.logo_folds(df["acq_group"])) == len(set(GROUPS))
    # tile-level table: the same image id repeats; all its tiles must land in the same test fold
    tiles = df.loc[np.repeat(np.arange(len(df)), 3), "sample_id"].to_numpy()
    _check_folds(validate.loio_folds(tiles), tiles)
    tile_groups = df.loc[np.repeat(np.arange(len(df)), 3), "acq_group"].to_numpy()
    _check_folds(validate.logo_folds(tile_groups), tile_groups)


def test_feature_columns_skip_meta_and_sd():
    feats, *_ = synthetic()
    assert validate.feature_columns(feats) == ["batch_feat", "acq_feat", "noise_feat", "const_feat"]


def test_planted_effects_are_classified():
    feats, artefacts, images, sens = synthetic()
    tabs = validate.run_tables(feats, artefacts, images, sens, seed=0, n_boot=200, n_perm=2000)
    dec = tabs["decisions"].set_index("feature")
    conf = tabs["confound"].set_index("feature")
    assert dec.loc["batch_feat", "decision"] == "keep", dec.loc["batch_feat"].to_dict()
    assert not conf.loc["batch_feat", "acquisition_confounded"]
    assert dec.loc["acq_feat", "decision"] == "investigate"
    assert conf.loc["acq_feat", "acquisition_confounded"], conf.loc["acq_feat"].to_dict()
    assert conf.loc["acq_feat", "covariate_correlated"] and conf.loc["acq_feat", "strongest_covariate"] == "noise_sigma"
    assert dec.loc["const_feat", "decision"] == "drop"
    assert dec.loc["noise_feat", "decision"] == "investigate"
    # batch tests: the planted shift is large and survives residualisation; the noise feature does not reach q < 0.05
    bt = tabs["batch_tests"]
    raw = bt[(bt.variant == "raw") & (bt.reference_set == "all") & (bt.feature == "batch_feat")]
    assert (raw["effect_shift_over_mad"] < -2).all() and (raw["q_bh"] < 0.05).all()
    res = bt[(bt.variant == "residualised") & (bt.reference_set == "all") & (bt.feature == "batch_feat")]
    assert (res["q_bh"] < 0.05).all()
    assert (bt.loc[bt.feature == "noise_feat", "q_bh"] > 0.05).all()
    assert set(bt["reference_set"]) == {"all", "excl_loo_flagged"} and set(bt["n_ref"]) == {17}  # no LOO ids present
    # the batch feature gives a near-perfect leakage-free classifier; LOIO and LOGO both hold
    ll = tabs["loio_logo"].set_index(["split", "covariates"])
    assert ll.loc[("LOIO", "without"), "accuracy"] > 0.9 and ll.loc[("LOGO", "without"), "accuracy"] > 0.9
    assert set(tabs["loio_logo"]["n_folds"]) == {31, len(set(GROUPS))}
    loo = tabs["reference_loo"]
    assert len(loo) == 17 * 4 and (loo["n_others"] == 16).all()


def test_bh_and_mad():
    q = validate.bh_q(np.array([0.01, 0.04, 0.03, 0.5]))
    assert np.allclose(q, [0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.5])
    assert np.isclose(validate.mad(np.array([1, 2, 3, 4, 100.0])), 1.4826 * 1.0)

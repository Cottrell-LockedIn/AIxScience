"""Synthetic checks for qc.charging: a bright blob present in all three channels is flagged, one present only in
BSE is kept, and the masked label image / particle-removal count follow."""
import numpy as np

from qc import charging as C

FP = {"connectivity": 8, "min_object_px": 20}
P = dict(C.DEFAULTS)


def synthetic(seed=0, shape=(600, 600)):
    """Label image with two class-2 discs on a class-1 background plus a class-0 hole; SE channels where only
    disc A glows (bright in Inlens AND SE), disc B is at background level in both SE channels. Disc A is < 1 % of
    the image so that even the p99 threshold lies below the glow."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[: shape[0], : shape[1]]
    disc_a = (yy - 100) ** 2 + (xx - 100) ** 2 <= 30**2
    disc_b = (yy - 450) ** 2 + (xx - 450) ** 2 <= 30**2
    hole = (yy - 100) ** 2 + (xx - 450) ** 2 <= 20**2
    lab = np.ones(shape, np.uint8)
    lab[disc_a | disc_b] = 2
    lab[hole] = 0
    inlens = rng.normal(100, 5, shape)
    se = rng.normal(100, 5, shape)
    inlens[disc_a] += 80
    se[disc_a] += 80
    return lab, disc_a, disc_b, C.robust_z(inlens, lab != C._features.UNANALYSED), C.robust_z(se, lab != C._features.UNANALYSED)


def test_blob_bright_in_all_three_channels_is_flagged_and_bse_only_blob_is_kept():
    lab, disc_a, disc_b, zi, zs = synthetic()
    masks, diag = C.build_masks(lab, zi, zs, P)
    for pct in (90, 95, 99):
        m = masks[f"bright_both_p{pct}"]
        assert m[disc_a].mean() > 0.95, pct          # glowing blob flagged
        assert m[disc_b].mean() < 0.02, pct          # BSE-only blob kept
        assert not m[lab != 2].any()                 # flags restricted to class 2
    masked = C.apply_mask(lab, masks["bright_both_p95"])
    assert (masked[disc_b] == 2).mean() > 0.98             # chance flags only (~p^2 of the noise)
    assert (masked[disc_a] == 1).mean() > 0.95
    assert C.particles_removed(lab, masks["bright_both_p95"], FP) == 1
    assert diag["frac_c2_dark_both_p50"] < 0.3      # disc B sits at the SE median: roughly a quarter dark-in-both


def test_edge_glow_only_flags_bright_class2_near_void():
    lab, disc_a, disc_b, zi, zs = synthetic()
    masks, _ = C.build_masks(lab, zi, zs, P)
    for n in (3, 5, 10):
        assert not masks[f"edge_glow_n{n}"].any()   # glowing disc A is far from the class-0 hole
    lab2 = lab.copy()
    lab2[95:105, 125:140] = 0                        # carve a void touching disc A
    masks2, _ = C.build_masks(lab2, zi, zs, P)
    e3 = masks2["edge_glow_n3"]
    assert e3.any() and (lab2[e3] == 2).all()
    assert e3.sum() <= masks2["edge_glow_n5"].sum() <= masks2["edge_glow_n10"].sum()
    assert C.near_class(lab2, 0, 3)[95:105, 125:140].all()


def test_features_unmasked_equal_qc_features_definitions_and_masked_drop_area():
    lab, disc_a, disc_b, zi, zs = synthetic()
    rows, _, _ = C.evaluate(lab, zi, zs, P, FP)
    by = {r["variant"]: r for r in rows}
    none = by["none"]
    assert abs(none["F02_unmasked"] - (lab == 2).sum() / (lab != C._features.UNANALYSED).sum()) < 1e-9
    m95 = by["bright_both_p95"]
    assert m95["F02_masked"] < m95["F02_unmasked"] * 0.6
    assert m95["n_c2_particles_removed"] == 1
    assert m95["frac_c2_area_flagged"] > 0.45

# Devin Challenge: Paper Comparison

Challenge wording: "pick a published scientific paper, have Devin reproduce a key result, then push past it."

Date: 2026-10-03. Verification details in `../Log/2026-10-03_ideation_verification.md`.

## Candidates

| | A. ImageRep | B. Crack quantification via foundation-model transfer | C. Hierarchical bootstrap for nested data | D. LIBAD / DA-Core |
|---|---|---|---|---|
| Reference | Dahari et al., Advanced Science; PMC12442635 | Tegetmeyer-Kleine et al., arXiv 2608.27162 | PMC9098003 (hierarchical bootstrap, multi-level data) | Sui et al., arXiv 2608.07958 |
| Peer reviewed | Yes | No, under review | Yes | No |
| Code | github.com/tldr-group/ImageRep, BSD-3 | git.rwth-aachen.de (behind an anti-bot challenge page; licence not readable without a browser) | author GitHub, MIT (small) | github.com/evenrose/LIBAD, BSD-3 |
| Data needed | None beyond repo: fitted statistics ship as JSON; synthetic `binary_blobs` used by the repo's own tests | 1.13 GB Figshare zip (CC BY 4.0) plus model weights | Simulated data, generated in code | Gated Hugging Face dataset, multi-GB, 4 modalities |
| Compute for the key result | CPU, minutes | GPU for decoder training and 120-megapixel inference | CPU, seconds | GPU, hours across 10 splits |
| Key result to reproduce | Predicted 95% phase-fraction error bound covers true error at about the stated confidence (validation figures) | Late intergranular crack coverage 4.6% cycled vs 0.5% initial / calendar-aged | Hierarchical bootstrap gives correct false-positive rate where naive pooling of nested samples does not | DA-Core FPR95 54.3% vs 60.4% at coreset ratio 0.05 |
| "Go further" that feeds Track 4 | Batch-level phase-fraction uncertainty; gate `reject` on combined sampling uncertainty; apply to hackathon images | Crack KPI on hackathon images, if they are NMC cross-sections at similar scale | Image-level permutation / hierarchical bootstrap for batch comparison (already needed by L1) | Density-aware coreset for a PatchCore memory bank on hackathon tiles |
| Judge recognition | Very high: authors are the Imperial TLDR group, which founded Polaron | Medium: battery community, not Polaron | Low: statistics paper, neuroscience venue | Low to medium |
| Risk for Devin | Low | High: clone may fail on the bot wall; 1 GB download; GPU time competes with Modal budget; code licence unknown | Low, but thin story | High: gated dataset, heavy compute |
| Time estimate | 1 to 2 h agent time | 4 to 8 h, uncertain | under 1 h | 6 h or more |

## Assessment

**A (ImageRep) is the recommendation.** It is the only candidate that is simultaneously peer reviewed, permissively licensed, reproducible on CPU in minutes with nothing but the repo, directly recognisable to the Polaron judges, and whose extension (single image -> batch) is work the track needs anyway. The honest weakness: it only covers one KPI type (a segmented phase fraction), and its assumptions (binary segmentation, >= 200 px, feature size <= 70 px, non-periodic) may not hold on the hackathon images. That is fine: reporting where the assumptions fail is itself a result.

**B (crack preprint)** is scientifically the closest to the sponsor's crack case study, but the practical barriers are real: the code host blocks automated clients, the paper is unreviewed, the data is 1 GB, and the reproduction needs GPU training time. If the hackathon images turn out to be NMC cross-sections with visible intra-particle cracks, B becomes attractive as an **exploratory v2 KPI** rather than as the Devin reproduction target. A human can fetch the code through a browser and check the licence at the event.

**C (hierarchical bootstrap)** is trivial to reproduce and is a good fallback if A fails for an unexpected reason. It can also be done *inside* the Track 4 work by L1 without being badged as the Devin challenge.

**D (LIBAD)** is not recommended: gated data, heavy compute, no SEM, preprint.

## Combination worth considering

Primary: A. Secondary if time remains after T+14: C's method applied to the hackathon data as the statistical layer for A's batch extension (so the "go further" step has both uncertainty propagation and a valid nested test). B only if the data invites it.

## Devin workflow evidence to collect (for the write-up)

- Prompt(s) given to Devin, session links or CLI logs.
- Exact commit of ImageRep pinned, environment lock.
- Devin's reproduction script, numbers table versus paper, deviations and reasons.
- The extension code and its result on the hackathon data.
- What a human corrected, if anything. Judges reward a transparent agent workflow, not only a matching number.

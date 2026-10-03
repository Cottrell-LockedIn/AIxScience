# Questions for Polaron (ordered by impact on our workflow)

Each question states what we will do with the answer. Log answers in `DATA_AUDIT.md` as organiser-provided.

## Must ask (changes the pipeline)

1. **Is the pixel size 25 nm/px?** The TIFF resolution tag implies it, but there is no microscope metadata. -> Decides whether KPIs are reported in um or in px.
2. **What is the bright phase in BSE?** Silicon, SiOx, or something else? Any nominal Si wt% per batch? -> Decides whether "high-Z phase fraction" can be named and compared against a specification.
3. **Is one of the three batches the approved reference / known-good supplier?** -> Decides whether W1 is reference-vs-incoming or pairwise.
4. **Are the three held-back images each from one of the three batches, or could one be from a new batch?** -> Decides whether "matches none" must be a supported output.
5. **Are the three detector files per id the same field of view, acquired in the same session?** -> Decides whether we can fuse BSE + Inlens per pixel.
6. **Why do some samples have `SE` instead of `ETD`?** Different microscope, detector setting or session? -> Acquisition covariate; may confound batch classification.
7. **Were all batches imaged under the same beam conditions (kV, current, dwell, working distance)?** -> Same reason; if not, we report it as acquisition drift.

## Should ask (changes KPIs or wording)

8. **Which direction is the current collector / coating surface in the image?** (top or bottom) -> Enables porosity gradient and flake orientation KPIs with physical meaning.
9. **Are the images cropped to the coating thickness?** Image heights vary 1904 to 2316 px. -> If yes, height is a free coating-thickness KPI.
10. **Which features do you consider artefacts here?** Curtaining and edge brightening were mentioned; anything else (redeposition, smearing, polishing scratches)? -> Artefact covariate list.
11. **Are the samples pristine or cycled?** -> Decides whether cracks are expected to be a manufacturing signal or a cycling signal.
12. **What would you measure first by hand on these images?** -> Sanity-check our KPI priority against their expert intuition.

## Nice to ask (helps the pitch)

13. Which stakeholder would receive a verdict like "high-Z particle fraction outside reference bounds"? (powder supplier vs cell maker) -> Routing vocabulary for Feature 3.
14. Is there a physics-based quantity they would like to see from a 2D slice (tortuosity factor via TauFactor, effective conductivity)? -> Decides whether the TauFactor layer is worth the time.
15. May we include small crops of the images in our slides and README? -> Data redistribution rule.
16. For the held-back images: will we receive all three detector channels or only one? -> Pipeline must tolerate a missing channel.

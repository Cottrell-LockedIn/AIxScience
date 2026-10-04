# Local criteria controls

`src/criteria.ts` contains presentation-layer starting ranges for F01–F11. They are evaluated against values already emitted by the engine and do not modify segmentation, feature extraction, embeddings, classifier probabilities, or the verdict policy.

- F01 5–80%; F02 0–60%; F03 5–1200 px; F04 5–2000 px; F05 0–30,000/Mpx.
- F06 0–3, F07 0–1, F08 2–1200 px, F09 0.1–10, F10 0–100 percentage points, F11 0–100%.
- F12 remains disabled because aspect ratio is not emitted by the present engine.

The F05 value is already a density in particles/Mpx and is never multiplied in the UI. Pixel-to-micron conversion is shown only for `img_4ih2ggld_BSE.tif` with SHA-256 `a7fa8987f58071205743249f0b089912c3cdab5289d48aa4dc21e5b73aa21b09`, where 0.025 µm/px has been attested. All other images remain in pixels until they include their own attestation.

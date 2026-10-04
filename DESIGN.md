# Cottrell design system

The user's latest direction is a warm light workspace with white surfaces, precise scientific tables, generous but purposeful space, Inter typography, violet actions and amber review markers. The original dark planning reference is superseded. Setup, processing, region review and results share the same visual language. Results have Overview, Investigate and Material details views.

Tokens: background #f7f7f4; surface #ffffff; text #202024; secondary #666670; borders #d7d8d2; action #7040dc; warning text #8a5600. Spacing 6/12/18/24/36/60 px. Inter Variable is self-hosted. Actions use 180 ms ease-out; the material split settles within 220 ms. Reduced-motion disables nonessential animation. The generated transparent Cottrell mark is recorded in frontend/public/cottrell-logo.md.

Results use a top-aligned, sticky evidence panel on desktop, one column on mobile, readable wrapped text and explicit button foreground colours. Review uses native-coordinate image crops, an overview navigator, highlighted regions and 512 px detail crops. Local threshold proximity identifies review suggestions; it is not a model-confidence heatmap.

The material view separates the original image and the exact three segmentation layers when available. Plane separation is illustrative depth from one 2D field, not a reconstructed 3D electrode volume. No synthetic scientific image or fabricated class layer is displayed.

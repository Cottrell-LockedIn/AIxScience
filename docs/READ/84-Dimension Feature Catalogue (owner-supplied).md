# Owner-supplied candidate catalogue

These dimensions are not labels or ground truth.

Feature list:

PROJECT SCOPE: ALL 84 MICROSTRUCTURE DIMENSIONS

The project scope is the complete 84-dimension catalogue below. Treat these dimensions as things the vision system should learn to notice, describe and help measure across the image set. They are not 84 mutually exclusive segmentation classes: some are visible objects, some are calculated from reviewed geometry, and some require chemical, 3D, structural or functional evidence beyond a single SEM image.

For every dimension, distinguish:
- directly observed image evidence
- a visual candidate or hypothesis
- a metric derived from reviewed masks or geometry
- not assessable from the available image
- external evidence required

A model may discover visual proxies or nominate regions for review, but it must not present a proxy as confirmed chemistry, 3D structure, material performance or failure cause. Preserve uncertainty and evidence requirements. Unknown or unreviewed regions are not negative examples.

DATA CONTEXT
The current inventory is 93 RGB SEM TIFFs from three batches, grouped into 31 filename field stems. BSE, ETD, Inlens and some SE images with a shared stem are different detector views, not independent specimens. A shared stem does not establish registration; preserve detector identity and verify alignment before transferring geometry. Keep all views of a stem together in train/validation/test splits.

These are fresh, unused manufacturing electrodes that were destructively prepared. Preparation and acquisition artifacts can resemble real features. No source-linked EDS maps or chemistry ground truth were found. BSE contrast can support a composition hypothesis but cannot identify silicon by itself; ETD/Inlens/SE can help inspect relief but do not establish phase identity. TIFF tags suggest roughly 25 nm/pixel, but calibration is unverified, so report pixels unless calibrated. Do not infer cycling damage, SEI, plated lithium, lithiation state or failure probability from these images.

84 DIMENSIONS

A. Particles

P01. Particle identity and boundaries — instance masks and neutral contrast classes.
P02. 2D section-profile sizes and outliers — area, equivalent diameter, Feret lengths, quantiles, fine and oversize tails.
P03. Aspect ratio and section-intercept width — major/minor axes; thickness only with suitable known orientation.
P04. Roundness, angularity and solidity — circularity, convexity, concavity and corner curvature.
P05. Projected particle orientation — long-axis angles, dispersion and 2D alignment; coating direction must be known to interpret it.
P06. Perimeter texture and faceting — resolved boundary roughness and facet lengths; not 3D surface area.
P07. Fragments, chips and fines — fragment instances and local fine-particle fraction.
P08. Agglomerate architecture — candidate cluster envelope, internal gaps, constituent sizes and compactness.
P09. Apparent planar spacing and coordination — in-plane distances and section-biased neighbour/contact counts.
P10. Lamellar or internal texture — resolved bands, internal boundaries and orientation contrast; not crystal identity.

B. Pores and gaps

V01. Apparent void area fraction — resolved dark void-like area divided by valid image area; dark contrast is not uniquely a pore.
V02. Pore-body size distribution — equivalent size, local thickness and distribution tails.
V03. Pore shape and orientation — slit, wedge, rounded or elongated shape; aspect ratio and angle.
V04. Interparticle versus intraparticle location — relationship to segmented particle boundaries.
V05. Pore throats and constrictions — in-plane neck width, minimum aperture and throat/body ratio.
V06. Channels, junctions and endpoints — 2D skeleton segments and branch/endpoint density.
V07. Isolated-looking and dead-end-looking pores — connected components and endpoints in the section; not proof of 3D isolation.
V08. Void clusters and large cavities — cluster size, spacing and cavity masks.
V09. Dense bands and pore-rich bands — windowed void fractions and directional profiles.
V10. Surface apertures and pore entrances — opening size/density only at a verified free surface.
V11. Void shape around a particle — halo width, perimeter fraction and asymmetric clearance.
V12. Resolved pore topology statistics — 2D Euler characteristic, chord lengths and lineal-path descriptors.

C. Discontinuities and damage

D01. Intraparticle fissures — mask or centreline inside a particle; cause remains unknown.
D02. Interparticle/coating cracks — extended discontinuities across multiple particle boundaries.
D03. Crack aperture and opening profile — width distribution along each resolved fissure.
D04. Crack length, branching and orientation — length density, branch/tip count and alignment.
D05. Cleavage and exfoliation-like separation — repeated lamellar gaps; preparation remains an alternative explanation.
D06. Chipping, fragmentation and spallation — debris/fragment geometry and adjacent missing-material region.
D07. Missing-particle cavity; mechanical pull-out candidate — particle-shaped cavity; call it pull-out only with preparation evidence.
D08. Correlated damage around an inclusion or cluster — spatial relations among inclusion, gap and crack masks.

D. Contacts and interfaces

I01. Particle-particle contact — apparent touching length and gap-versus-contact geometry; touch does not prove conductivity.
I02. Contact-poor or apparently isolated particle — low contact perimeter or coordination in the section; 3D may change the interpretation.
I03. Particle-fine-matrix interface — coverage, discontinuities and separation gaps; matrix identity may be unknown.
I04. Carbon-binder coverage and bridges — confirmed CBD masks and coverage/bridge/neck geometry; requires chemical or contrast confirmation.
I05. Bare patches and binder-rich islands — confirmed phase coverage on active-particle boundaries; requires phase identification.
I06. Coating-current-collector interface — contact continuity and gap length/width if the collector is visible.
I07. Delamination and layer separation — gap morphology, lifted layer and candidate debonded length; not a strength measurement.
I08. Interface perimeter and junction geometry — particle/pore/matrix boundary lengths and junction density.

E. Heterogeneity and coating

H01. Local packing and contrast-phase fractions — windowed area fractions and their distributions.
H02. Spatial clustering and segregation — pair correlation, neighbour statistics and cluster maps.
H03. Depth gradients — particle, void and confirmed-phase profiles; requires a known collector/free-surface direction.
H04. Local coating thickness and waviness — surface-to-collector distance profile.
H05. Skin layers, compaction and lamination bands — dense bands, interfaces and orientation changes.
H06. Pinholes, craters, missing coating and exposed foil — masks and local coverage loss.
H07. Ribs, streaks, edge beads, wrinkles and blisters — mesoscale surface/cross-section geometry.
H08. Spatial statistics at multiple scales — window-size dependence, two-point correlation and anisotropy.
H09. Unknown inclusions or foreign fibres — unusual contrast/shape masks; embedded-versus-superficial status and chemistry may be unknown.
H10. Collector wrinkles, pits, tears and burrs — collector defects only where collector/edge is present.

F. Conditional silicon dimensions

S01. Si-containing particle size and dispersion — size/distribution of chemically confirmed instances.
S02. Si agglomerate density and architecture — cluster envelope, internal voids and neighbouring phases; requires chemical confirmation.
S03. Graphite enclosure of Si — fraction of confirmed Si perimeter adjacent to graphite; 3D enclosure needs 3D evidence.
S04. Si-contact/free-volume neighbourhood — contact and available-gap map around confirmed Si; requires chemical and 3D evidence.
S05. Internal Si pore architecture — directional channels, slits, dispersed pores and ligament thickness; requires suitable resolution and chemical confirmation.
S06. Core-shell morphology and shell defects — shell thickness, discontinuities and core porosity; requires chemical/high-resolution evidence.

G. Chemical and crystallographic dimensions

C01. Graphite/Si/SiOx/other phase identity — elemental or phase identity from suitable chemical measurements, not ordinary brightness alone.
C02. Binder and conductive additive distribution — requires registered chemistry or calibrated contrast maps.
C03. Graphite crystal orientation and texture — requires suitable structural characterization such as diffraction or Raman/TEM.
C04. Graphitic disorder and grain structure — crystallite size, defects and stacking from Raman/XRD/TEM or equivalent.
C05. Elemental contamination and deposits — requires chemistry-specific measurement and standards.
C06. Surface oxide/coating chemistry and thickness — requires suitable chemical and structural measurement.
C07. Binder chemistry and mechanical state — requires spectroscopy, thermal or mechanical characterization.
C08. Residual moisture/solvent and surface condition — requires moisture, thermal or spectroscopy measurements.
C09. Wetting affinity and contact angle — requires controlled surface/wetting measurements; dry SEM geometry is insufficient.
C10. SEI, plated lithium and lithiation state — future formed/cycled samples and appropriate air-free/operando evidence only; not assignable to the supplied fresh electrodes.

H. Three-dimensional and functional targets

T01. Open/closed pore fractions and connectivity — requires tomography/serial sections and a defined connection boundary.
T02. Pore bodies, throats and constrictivity — requires a resolved 3D pore network.
T03. Transport tortuosity tensor — requires 3D transport modelling or suitable experiments; a 2D path ratio is not transport tortuosity.
T04. Accessible surface and contact areas — requires 3D phase geometry and an accessibility definition.
T05. Electronic percolation and contact resistance — requires 3D contact/CBD network and electrical validation.
T06. Electrolyte filling, trapped gas and accessible volume — requires time-resolved wetting imaging or validated simulation.
T07. Local expansion, residual strain and stress — requires registered states and suitable mechanical measurements/models.
T08. Adhesion and cohesive strength — requires peel, indentation or another suitable mechanical test.
T09. Ionic/electronic/thermal effective properties — requires validated models and experiments.
T10. Reaction/current hotspots and plating susceptibility — requires a microstructure-resolved model and electrochemical validation.

I. Preparation and acquisition controls

Q01. Curtaining and milling streaks — directional artifact masks.
Q02. Redeposition, smearing and surface veils — obscured/coated-region masks, with cause tied to preparation evidence.
Q03. Protective cap, embedding material and exterior — separate non-electrode masks.
Q04. Section fracture, preparation debris and mechanical pull-out — artifact candidates; pull-out interpretation requires preparation history.
Q05. Charging and detector-dependent contrast — contrast anomalies and cross-detector checks.
Q06. Pore shadow and subsurface show-through — ambiguous boundary/void regions.
Q07. Drift, blur, scan defects and stitching seams — quality masks and registration checks.
Q08. Beam damage and altered surface rims — suspected regions; diagnosis needs repeated-dose or chemical evidence.
Q09. Clipping, saturation and unresolved fine features — invalid/uncertain masks and an explicit resolution limit.
Q10. Frame-edge truncation and section bias — partial-object flags, consistent window rules and orientation metadata.

DISCOVERY GUIDANCE
Use unlabeled data to learn recurring visual structure across the full 84-dimension scope. Preserve spatial relationships and instance geometry where possible, and distinguish measured descriptors from inferred concepts. For dimensions requiring chemistry, 3D, structural characterization or functional testing, the image model should learn candidate visual correlates and mark the dimension as requiring that evidence; it should not manufacture a confirmed label from pixels alone.
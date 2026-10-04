export type MetricDefinition = {
  id: string
  label: string
  technical: string
  meaning: string
  unit: string
  caveat?: string
}

export const metricDefinitions: Record<string, MetricDefinition> = {
  F01: { id: 'F01', label: 'void area fraction', technical: 'F01_c0_area_fraction (Class-0 area fraction)', meaning: 'How much of the image is assigned to the dark class.', unit: '%', caveat: 'The dark phase is supplier-stated as void or pore and is not image-verified.' },
  F02: { id: 'F02', label: 'silicon area fraction', technical: 'F02_c2_area_fraction (Class-2 area fraction)', meaning: 'How much of the image is assigned to the bright class.', unit: '%', caveat: 'The bright phase is supplier-stated as silicon and is not image-verified.' },
  F03: { id: 'F03', label: 'silicon particle equivalent diameter, median', technical: 'F03_c2_eqdiam_median_px (Median equivalent circular diameter (ECD))', meaning: 'The middle bright-object size across the image.', unit: 'pixels', caveat: 'This is the bright segmented class, not confirmed silicon; a micrometre value is shown only when this image source has an attested scale.' },
  F04: { id: 'F04', label: 'silicon particle equivalent diameter, 90th percentile', technical: 'F04_c2_eqdiam_p90_px (90th-percentile equivalent circular diameter (ECD))', meaning: 'A size near the upper end: nine in ten bright objects are smaller.', unit: 'pixels', caveat: 'This is the bright segmented class, not confirmed silicon; a micrometre value is shown only when this image source has an attested scale.' },
  F05: { id: 'F05', label: 'silicon particle count density', technical: 'F05_c2_count_density_per_Mpx (Class-2 object density)', meaning: 'How many bright objects appear per million image pixels.', unit: 'objects per megapixel' },
  F06: { id: 'F06', label: 'silicon Clark-Evans nearest-neighbour ratio', technical: 'F06_c2_clark_evans_R (Clark–Evans nearest-neighbour ratio (Donnelly edge correction))', meaning: 'Whether bright objects are closer together or farther apart than a random pattern.', unit: 'ratio' },
  F07: { id: 'F07', label: 'silicon particle solidity, area-weighted median', technical: 'F07_c2_solidity_area_weighted_median (Area-weighted median solidity)', meaning: 'How filled-in rather than indented the bright-object outlines are.', unit: 'ratio' },
  F08: { id: 'F08', label: 'void local thickness, median', technical: 'F08_c0_local_thickness_median_px (Median void local thickness)', meaning: 'The middle width of the dark regions in this 2D image.', unit: 'pixels', caveat: 'The dark phase is supplier-stated as void or pore. This is a 2D image measurement, not a 3D electrode thickness.' },
  F09: { id: 'F09', label: 'void chord-length anisotropy', technical: 'F09_c0_chord_anisotropy_h_over_v (Mean horizontal/vertical void chord ratio)', meaning: 'Whether dark regions extend more horizontally or vertically in the image.', unit: 'ratio', caveat: 'The dark phase is supplier-stated as void or pore. This describes image orientation, not a 3D material direction.' },
  F10: { id: 'F10', label: 'void fraction heterogeneity', technical: 'F10_c0_fraction_iqr_512px (Interquartile range (IQR) of void fraction in 512-pixel windows)', meaning: 'How much dark-area share changes across 512-pixel windows in the image.', unit: 'percentage points', caveat: 'The dark phase is supplier-stated as void or pore and is not image-verified.' },
  F11: { id: 'F11', label: 'silicon perimeter fraction adjacent to void', technical: 'F11_c2_perimeter_fraction_adjacent_c0 (Class-2 boundary touching class 0)', meaning: 'How much bright-object edge meets the dark class.', unit: '%' },
}

export function metricDefinition(id?: string) { return metricDefinitions[id || ''] }
export function metricLabel(id?: string) { return metricDefinition(id)?.label || 'Segmentation-derived measurement' }
export function metricTechnicalName(id?: string) { return metricDefinition(id)?.technical || (id || 'Technical name not supplied') }
export function metricMeaning(id?: string) { return metricDefinition(id)?.meaning || 'A measurement derived from the segmentation mask.' }
export function metricUnit(id?: string) { return metricDefinition(id)?.unit || 'native units' }

export function formatBatchLabel(value?: string) {
  return typeof value === 'string' ? value.replace(/^Batch_/, 'Batch ') : 'Not supplied'
}

export function formatMetricValue(id: string, value: unknown, calibrated = false) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not supplied'
  const definition = metricDefinition(id)
  const displayed = ['F01', 'F02', 'F10', 'F11'].includes(id) ? value * 100 : value
  const digits = ['F01', 'F02', 'F10', 'F11'].includes(id) ? 1 : 3
  const native = `${displayed.toLocaleString(undefined, { maximumFractionDigits: digits })} ${definition?.unit || ''}`.trim()
  return calibrated && ['F03', 'F04', 'F08'].includes(id) ? `${native} · ${(value * 0.025).toFixed(3)} µm` : native
}

export const roleLanguage: Record<string, { label: string; meaning: string }> = {
  R01: { label: 'Supplier', meaning: 'Review supplied material and its accompanying records.' },
  R02: { label: 'Composite or coating supplier', meaning: 'Review supplied composite or coating inputs and records.' },
  R03: { label: 'Slurry mixing', meaning: 'Review the documented mixing step and its records; this is an investigation route, not a confirmed cause.' },
  R04: { label: 'Coating and drying', meaning: 'Review coating and drying records as an investigation route.' },
  R05: { label: 'Electrode rolling and pressing', meaning: 'Review electrode rolling and pressing records (technical term: calendering) as an investigation route.' },
  R06: { label: 'Assembly, filling and wetting', meaning: 'Review assembly, filling and wetting records as an investigation route.' },
}

export function roleLabel(id?: string) { return roleLanguage[id || '']?.label || (id || 'Review owner') }
export function roleMeaning(id?: string) { return roleLanguage[id || '']?.meaning || 'A possible review owner; it does not establish process origin.' }

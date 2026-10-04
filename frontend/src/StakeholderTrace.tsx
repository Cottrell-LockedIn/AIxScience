import { ExternalLink, FlaskConical, Microscope } from 'lucide-react'
import { evidenceSources, type RiskGuide } from './riskCatalog'
import type { Criterion, ResultField } from './Results'
import { formatMetricValue, metricLabel } from './metricLanguage'
import './StakeholderTrace.css'
import './StakeholderTrace.extra.css'

const roleDetails: Record<string, { short: string; full: string; responsibility: string }> = {
  R01: { short: 'Supplier', full: 'Silicon / SiOx material supplier', responsibility: 'Particle architecture, chemistry, incoming particle-size distribution and surface treatment.' },
  R02: { short: 'Composite/coating supplier', full: 'Si–graphite composite producer / coating supplier', responsibility: 'Granulation, encapsulation, carbon coating and composite mechanical robustness.' },
  R03: { short: 'Slurry mixing', full: 'Electrode formulation and slurry-mixing team', responsibility: 'Recipe, binder dispersion, mixing history, stability and settling.' },
  R04: { short: 'Coating/drying', full: 'Coating and drying team', responsibility: 'Wet-film thickness, substrate wetting, drying profile and coating uniformity.' },
  R05: { short: 'Electrode rolling and pressing', full: 'Calendering team', responsibility: 'Densification, roll settings, porosity and mechanical damage (technical term: calendering).' },
  R06: { short: 'Assembly/filling/wetting', full: 'Cell assembly, electrolyte filling and wetting team', responsibility: 'Assembly compression, electrolyte quantity, vacuum fill, soak time and temperature.' },
  R07: { short: 'Formation/electrochemical QC', full: 'Cell formation and electrochemical QC team', responsibility: 'Initial charge/discharge protocol, formation efficiency, resistance and release capacity.' },
  R08: { short: 'Microscopy/materials validation', full: 'Microscopy, metrology and materials-validation team', responsibility: 'Preparation artefacts, calibration, phase identity, segmentation and representative sampling.' },
  R09: { short: 'BMS/charge control', full: 'BMS and charge-control team', responsibility: 'Charge/discharge envelopes, SOC estimation, voltage termination and regenerative-charge limits.' },
  R10: { short: 'Pack thermal/mechanical', full: 'Pack thermal and mechanical integration team', responsibility: 'Cell temperature distribution, cooling, preload, compliance and pressure evolution.' },
  R11: { short: 'Application/duty-cycle', full: 'Application owner and duty-cycle team', responsibility: 'Actual load waveform, storage SOC, dwell, ambient exposure and required useful life.' },
  R12: { short: 'Life validation/diagnostics', full: 'Cell life-validation and diagnostics team', responsibility: 'Matched duty-profile qualification, reference performance tests, mechanism confirmation and target-based acceptance.' },
}

type Props = { risk: RiskGuide; field: ResultField; criteria: Criterion[] }

function measurement(feature: string, field: ResultField, criteria: Criterion[]) {
  if (feature === 'AR_VOID') return { value: 'Not measured in v1', state: 'Unavailable in this analysis' }
  const raw = field.features[feature]
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return { value: 'Unavailable', state: 'Measurement unavailable' }
  const criterion = criteria.find((item) => item.id === feature && item.enabled !== false)
  const scale = criterion?.scale ?? 1
  const value = raw * scale
  if (!criterion) return { value: formatMetricValue(feature, raw), state: 'Unassessed hypothesis · no selected limit' }
  const within = (criterion.min == null || value >= criterion.min) && (criterion.max == null || value <= criterion.max)
  return { value: formatMetricValue(feature, raw), state: within ? 'Within selected limit' : 'Outside selected limit' }
}

export default function StakeholderTrace({ risk, field, criteria }: Props) {
  const primary = risk.features
  const supporting = risk.supporting || []
  const owners = [...risk.owners]
  const sources = risk.sources.map((id) => ({ id, source: evidenceSources[id] })).filter((item) => item.source)
  return <section id="stakeholder-trace" className="stakeholder-trace" aria-labelledby="stakeholder-trace-title">
    <header className="stakeholder-trace__head">
      <div><span>Selected investigation path</span><h2 id="stakeholder-trace-title">{risk.id} · {risk.title}</h2></div>
      <p><b>Exploring hypothesis</b><br />Required confirming evidence has not been supplied. This path is an expert investigation aid, not causal proof or blame.</p>
    </header>

    <div className="trace-legend" aria-label="Relationship legend"><span><i className="trace-line solid" />Recorded measurement</span><span><i className="trace-line dashed" />Hypothesis or investigation link</span></div>

    <div className="trace-stage trace-stage--measures">
      <div className="trace-stage__label"><b>Measured KPI</b><span>Solid links show values recorded for {field.id}.</span></div>
      <div className="trace-measurements">
        {primary.length ? primary.map((feature) => <Measurement key={feature} feature={feature} kind="Primary feature" field={field} criteria={criteria} />) : <div className="trace-empty">No v1 feature independently supports this pattern.</div>}
        {supporting.map((feature) => <Measurement key={feature} feature={feature} kind="Supporting context" field={field} criteria={criteria} />)}
      </div>
    </div>

    <div className="trace-link trace-link--dashed" aria-hidden="true"><span>hypothesized investigation link</span></div>
    <div className="trace-stage trace-stage--hypothesis">
      <div className="trace-stage__label"><b>Possible mechanism / issue</b><span>Pattern not confirmed for this field.</span></div>
      <article className="trace-hypothesis"><FlaskConical size={18} aria-hidden="true" /><div><strong>{risk.id} · {risk.title}</strong><p>{risk.caveat}</p></div></article>
      {sources.length > 0 && <div className="trace-sources" aria-label="Mechanism context sources">{sources.map(({ id, source }) => <a key={id} href={source.url} target="_blank" rel="noreferrer"><span><b>{id}</b> · mechanism context</span><strong>{source.title}</strong><small>{source.finding}</small><ExternalLink size={13} aria-hidden="true" /></a>)}</div>}
    </div>

    <div className="trace-link trace-link--dashed" aria-hidden="true"><span>investigate jointly when evidence prerequisites are met</span></div>
    <div className="trace-stage trace-stage--teams">
      <div className="trace-stage__label"><b>Investigation teams</b><span>Named catalog contributors, not responsibility assignments.</span></div>
      <div className="trace-teams">{owners.map((owner) => { const role = roleDetails[owner]; return <article className="trace-team" key={owner}><small>{owner}</small><strong>{role?.short || owner}</strong><span>{role?.full || 'Catalog investigation team'}</span><p><b>Why involved:</b> This team checks {role ? role.responsibility.charAt(0).toLowerCase() + role.responsibility.slice(1) : 'the relevant records and evidence.'}</p></article> })}</div>
    </div>

    <div className="trace-link trace-link--dashed" aria-hidden="true"><span>validate before any conclusion</span></div>
    <div className="trace-gate"><Microscope size={19} aria-hidden="true" /><div><span>Validation gate · R08 · Microscopy, metrology and materials validation</span><strong>Confirm the image interpretation before acting on this hypothesis.</strong><p>Check preparation artefacts, calibration, phase identity, segmentation and representative sampling.</p></div></div>
    <div className="trace-checks"><b>Checks needed before a conclusion</b><p>{risk.requires}</p><b>Collective investigation action</b><p>{risk.action}</p></div>
  </section>
}

function Measurement({ feature, kind, field, criteria }: { feature: string; kind: string; field: ResultField; criteria: Criterion[] }) {
  const item = measurement(feature, field, criteria)
  const label = feature === 'AR_VOID' ? 'Void-region elongation (aspect ratio)' : metricLabel(feature)
  return <article className={`trace-measure trace-measure--${kind.startsWith('Primary') ? 'primary' : 'supporting'}`}><small>{kind}</small><strong>{feature} · {label}</strong><b>{item.value}</b><span>{item.state}</span></article>
}

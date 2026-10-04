import { useMemo, useState } from 'react'
import { ChevronDown, CircleAlert, ExternalLink } from 'lucide-react'
import { evidenceSources, ownerNames, riskCatalog, type RiskGuide } from './riskCatalog'
import type { Criterion, ResultField } from './Results'
import './KpiGuidance.css'
import './KpiGuidance.extra.css'

const calibrationHash = 'a7fa8987f58071205743249f0b089912c3cdab5289d48aa4dc21e5b73aa21b09'
const units: Record<string, string> = { F01: '%', F02: '%', F03: 'px', F04: 'px', F05: '/Mpx', F06: 'ratio', F07: 'ratio', F08: 'px', F09: 'ratio', F10: 'pp', F11: '%' }
const labels: Record<string, string> = { F01: 'Dark-area share', F02: 'Bright-area share', F03: 'Bright-object median size', F04: 'Bright-object p90 size', F05: 'Bright-object density', F06: 'Bright-object clustering', F07: 'Bright-object fullness', F08: 'Dark-region thickness', F09: 'Dark-region H/V ratio', F10: 'Dark-area variation', F11: 'Bright–dark contact' }
type Props = { field: ResultField; criteria: Criterion[] }

function display(feature: string, raw: number | null | undefined, calibrated: boolean) {
  if (feature === 'AR_VOID') return 'Not measured in v1'
  if (raw == null || !Number.isFinite(raw)) return 'Unavailable'
  const scale = ['F01', 'F02', 'F10', 'F11'].includes(feature) ? 100 : 1
  const value = raw * scale
  const native = `${value.toLocaleString(undefined, { maximumFractionDigits: 3 })} ${units[feature] || ''}`
  if (calibrated && ['F03', 'F04', 'F08'].includes(feature)) return `${native} · ${(raw * 0.025).toFixed(3)} µm`
  return native
}

export default function KpiGuidance({ field, criteria }: Props) {
  const [tab, setTab] = useState<'manufacturing' | 'service'>('manufacturing')
  const [expanded, setExpanded] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const calibrated = field.channels.some((channel) => channel.sha256 === calibrationHash && /bse/i.test(channel.name))
  const selected = useMemo(() => new Map(criteria.filter((item) => item.enabled).map((item) => [item.id, item])), [criteria])
  const manufacturing = riskCatalog.filter((risk) => risk.id.startsWith('P'))
  const service = riskCatalog.filter((risk) => risk.id.startsWith('U'))
  const shown = (tab === 'manufacturing' ? manufacturing : service).slice(0, expanded ? undefined : 4)
  const controlState = (feature: string) => {
    const control = selected.get(feature)
    const raw = field.features[feature]
    if (!control) return 'No selected limit'
    if (typeof raw !== 'number' || !Number.isFinite(raw)) return 'Measurement unavailable'
    const value = raw * (control.scale ?? 1)
    return value < (control.min ?? -Infinity) || value > (control.max ?? Infinity) ? 'Outside selected limit' : 'Within selected limit'
  }
  const pDescriptor = (risk: RiskGuide) => {
    if (risk.id === 'P01') {
      const f01 = selected.get('F01'), f08 = selected.get('F08'), a = field.features.F01, b = field.features.F08
      if (typeof a !== 'number' || !Number.isFinite(a) || typeof b !== 'number' || !Number.isFinite(b)) return 'Not assessable: measurement unavailable'
      return f01 && f08 && typeof a === 'number' && typeof b === 'number' && a * (f01.scale ?? 1) < (f01.min ?? -Infinity) && b * (f08.scale ?? 1) < (f08.min ?? -Infinity) ? 'Descriptive hypothesis: review' : f01 && f08 ? 'No low-F01 / narrow-F08 hypothesis' : 'Not assessable: select F01 and F08 limits'
    }
    if (risk.id === 'P03') { const f10 = selected.get('F10'), value = field.features.F10; if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not assessable: measurement unavailable'; return f10 && typeof value === 'number' && value * (f10.scale ?? 1) > (f10.max ?? Infinity) ? 'Descriptive hypothesis: review' : f10 ? 'No high-F10 hypothesis' : 'Not assessable: select an F10 limit' }
    return 'Not assessable: context needed'
  }
  return <section className="kpi-guidance" aria-labelledby="kpi-guidance-title">
    <div className="kpi-guidance__head"><div><span>Investigation guidance</span><h2 id="kpi-guidance-title">Evidence before conclusions</h2><p>These patterns prioritize investigation. They do not establish specimen failure, process origin, a defect probability, or an automatic Pass result.</p></div><div className="kpi-tabs" role="tablist" aria-label="KPI guidance scope"><button role="tab" aria-selected={tab === 'manufacturing'} onClick={() => { setTab('manufacturing'); setExpanded(false) }}>Manufacturing · 14</button><button role="tab" aria-selected={tab === 'service'} onClick={() => { setTab('service'); setExpanded(false) }}>Future service · 14</button></div></div>
    <div className="kpi-measures"><strong>All v1 measurements</strong>{Object.keys(labels).map((id) => <span key={id}><b>{id} · {labels[id]}</b> {display(id, field.features[id], calibrated)} · {controlState(id)}</span>)}</div>
    <p className="kpi-calibration">{calibrated ? 'Scale attested only for this BSE source: 0.025 µm/px. Physical values shown for F03, F04 and F08.' : <><CircleAlert size={14} /> No per-image scale attestation. Measurements remain in native pixels.</>}</p>
    <div className="kpi-list">{shown.map((risk) => <article key={risk.id}><button className="kpi-row" onClick={() => setOpen(open === risk.id ? null : risk.id)} aria-expanded={open === risk.id}><span>{risk.id}</span><strong>{risk.title}</strong><em>{risk.id.startsWith('P') ? pDescriptor(risk) : 'Loading context needed'}</em><ChevronDown size={16} /></button>{open === risk.id && <Drawer risk={risk} field={field} controlState={controlState} />}</article>)}</div>
    {(tab === 'manufacturing' ? manufacturing : service).length > 4 && <button className="catalog-toggle" onClick={() => setExpanded(!expanded)}>{expanded ? 'Show fewer patterns' : `Show all ${tab === 'manufacturing' ? manufacturing.length : service.length} patterns`}</button>}
  </section>
}

function Drawer({ risk, field, controlState }: { risk: RiskGuide; field: ResultField; controlState: (feature: string) => string }) {
  const allFeatures = [...risk.features, ...(risk.supporting || [])]
  return <div className="kpi-drawer"><p><b>Candidate review owners:</b> {risk.owners.map((owner) => ownerNames[owner]).join(' · ')}</p><p><b>Current image evidence:</b> {allFeatures.length ? allFeatures.map((feature) => `${feature}: ${display(feature, field.features[feature], false)} (${controlState(feature)})`).join(' · ') : 'No v1 image feature supports this pattern.'}</p>{risk.supporting?.length ? <p><b>Supporting context only:</b> {risk.supporting.join(', ')}. These features do not independently trigger the pattern.</p> : null}<p><b>Evidence still needed:</b> {risk.requires}</p><p><b>Next action:</b> {risk.action}</p><p><b>Measurement reliability:</b> F01–F07 change with segmentation settings; F08–F11 still need checking. Silicon object identity is not independently validated.</p><p><b>Scientific mechanism support:</b> The linked studies support a possible mechanism, not this sample’s diagnosis.</p><p><b>Specimen failure:</b> Not established. <b>Process origin:</b> Not established.</p><p className="kpi-caveat">{risk.caveat}</p><p className="kpi-source-note">Scientific references supplied in the materials-scientist handoff; study observations are not specimen thresholds.</p><div className="source-links">{risk.sources.map((id) => { const source = evidenceSources[id]; return <a key={id} href={source.url} target="_blank" rel="noreferrer"><ExternalLink size={14} /><span><b>{id}</b> {source.title}<small>{source.finding} {source.caveat}</small></span></a> })}</div></div>
}

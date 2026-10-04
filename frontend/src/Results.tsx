import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import {
  ArrowDownToLine, ArrowLeft, ArrowRight, Check, ChevronDown, Download,
  Expand, Eye, FileDown, Info, Printer, ShieldAlert, Sparkles, TriangleAlert,
} from 'lucide-react'
import './Results.css'
import './Results.mask.css'
import './Results.polish.css'
import KpiGuidance from './KpiGuidance'
import ModelOutput from './ModelOutput'
import StakeholderTrace from './StakeholderTrace'
import { riskCatalog, type RiskGuide } from './riskCatalog'

const MaterialScene = lazy(() => import('./MaterialScene'))

type ProbabilityMap = Record<string, number>
type FeatureMap = Record<string, number | null | undefined>

export type ResultChannel = {
  name: string; filename: string; previewUrl?: string; rawUrl?: string; width?: number; height?: number; sha256?: string; available?: boolean
}
type MaskLayer = { id: string; label: string; imageUrl: string; verified: true }
type MaskArtifact = { maskUrl?: string; overlayUrl?: string; originalCroppedPreviewUrl?: string; layers?: MaskLayer[]; offset?: [number, number]; sha256?: string; width?: number; height?: number; note?: string }
export type ResultField = {
  id: string; channels: ResultChannel[]; features: FeatureMap; predictedBatch?: string
  probabilities?: ProbabilityMap; runnerUp?: string; margin?: number; confidenceTier?: string
  baseline?: { status?: string; reason?: string }; acquisition?: { status?: string; reason?: string }
  reliability?: { correct?: number; total?: number }; drivers?: { name: string; value?: number; explanation?: string }[]
  caveats?: string[]; route?: string; phaseIdentity?: Record<string, string> | string; raw?: unknown; mask?: MaskArtifact
}
export type ResultsData = { reviews?: Review[]; mode?: string; run?: Record<string, any>; fields?: ResultField[]; limitations?: string[]; metadata?: Record<string, string> }
export type Criterion = { id: string; label: string; min?: number; max?: number; unit?: string; enabled?: boolean; scale?: number }
export type Review = { tag?: string; note?: string; roi?: unknown; skipped?: boolean; [key: string]: unknown }

type Props = { data: ResultsData; criteria?: Criterion[]; review?: Review; onNew?: () => void }
type View = 'overview' | 'investigate' | 'material' | 'model'
const materialViews: View[] = ['model', 'material']

const views: { id: View; label: string }[] = [
  { id: 'overview', label: 'Overview' }, { id: 'model', label: 'Model output' }, { id: 'material', label: 'Material details' }, { id: 'investigate', label: 'Investigate' },
]
const routeName: Record<string, string> = {
  materials_expert_review: 'Materials expert', microscopy_team: 'Microscopy team', none: 'No model escalation',
}
const featureLabels: Record<string, string> = {
  F01: 'Dark-area share', F02: 'Bright-area share', F03: 'Typical bright-object size', F04: 'Larger bright-object size',
  F05: 'Bright-object count', F06: 'Bright-object clustering', F07: 'Bright-object shape fullness', F08: 'Typical width of dark regions',
  F09: 'Dark-region length ratio', F10: 'Variation in dark-area coverage', F11: 'Bright boundary touching dark regions',
}

const pct = (value?: number) => value == null || !Number.isFinite(value) ? 'Unavailable' : `${(value * 100).toFixed(1)}%`
const valueText = (value: number | null | undefined, scale = 1, unit = '') => value == null || !Number.isFinite(value)
  ? 'Unavailable' : `${(value * scale).toLocaleString(undefined, { maximumFractionDigits: scale >= 1000 ? 2 : 3 })}${unit ? ` ${unit}` : ''}`
const statusText = (status?: string) => status ? status.replace(/[_-]/g, ' ') : 'Not supplied'
const hasAcquisitionConcern = (status?: string) => Boolean(status && !['no_flag_recorded', 'pass', 'ok', 'available'].includes(status.toLowerCase()))
const phaseText = (phase?: ResultField['phaseIdentity']) => typeof phase === 'string' ? phase : phase?.provenance || phase?.description || 'Phase identity not supplied'

export default function Results({ data, criteria = [], review, onNew }: Props) {
  const initialParams = new URLSearchParams(window.location.search)
  const initialView = views.some((item) => item.id === initialParams.get('view')) ? initialParams.get('view') as View : 'overview'
  const [view, setView] = useState<View>(initialView)
  const fields = data.fields ?? []
  const [fieldId, setFieldId] = useState(() => initialParams.get('field') || fields[0]?.id || '')
  const field = fields.find((item) => item.id === fieldId) ?? fields[0]
  const [selectedCriterion, setSelectedCriterion] = useState<string | null>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [selectedRiskId, setSelectedRiskId] = useState('P01')

  useEffect(() => {
    const sync = () => { const search = new URLSearchParams(window.location.search); setView((views.some((x) => x.id === search.get('view')) ? search.get('view') : 'overview') as View); setFieldId(search.get('field') || fields[0]?.id || '') }
    window.addEventListener('popstate', sync); return () => window.removeEventListener('popstate', sync)
  }, [fields])
  useEffect(() => {
    const next = new URLSearchParams(window.location.search); next.set('view', view); if (field?.id) next.set('field', field.id)
    window.history.replaceState({}, '', `${window.location.pathname}?${next.toString()}${window.location.hash}`)
  }, [view, field?.id])
  useEffect(() => {
    const f10 = criteria.find((item) => item.id === 'F10' && item.enabled !== false)
    const raw = field?.features?.F10
    const preferP03 = !!f10 && typeof raw === 'number' && Number.isFinite(raw) && raw * (f10.scale ?? 1) > (f10.max ?? Infinity)
    setSelectedRiskId(preferP03 ? 'P03' : 'P01')
  }, [field?.id, criteria])

  const navigate = (nextView: View, nextFieldId = field?.id || '') => {
    const next = new URLSearchParams(window.location.search)
    next.set('view', nextView)
    if (nextFieldId) next.set('field', nextFieldId)
    window.history.pushState({}, '', `${window.location.pathname}?${next.toString()}${window.location.hash}`)
    setView(nextView); setFieldId(nextFieldId); setExpanded(false)
  }
  const selectView = (next: View) => navigate(next)
  const activeCriteria = criteria.filter((item) => item.enabled !== false)
  const measured = activeCriteria.map((criterion) => {
    const raw = field?.features?.[criterion.id]
    const finite = typeof raw === 'number' && Number.isFinite(raw)
    const actual = finite ? raw * (criterion.scale ?? 1) : null
    const within = actual != null && (criterion.min == null || actual >= criterion.min) && (criterion.max == null || actual <= criterion.max)
    return { criterion, actual, finite, within }
  })
  const outside = measured.filter((item) => item.finite && !item.within).length
  const unavailable = measured.filter((item) => !item.finite).length
  const probabilities = Object.entries(field?.probabilities ?? {}).sort(([a], [b]) => a.localeCompare(b))
  const topProbability = field?.predictedBatch ? field.probabilities?.[field.predictedBatch] : undefined
  const imageChannel = field?.channels?.find((channel) => /bse/i.test(channel.name + channel.filename)) || field?.channels?.[0]
  const preview = imageChannel?.available === false ? undefined : imageChannel?.previewUrl
  const originalImage = imageChannel?.available === false ? undefined : field?.mask?.originalCroppedPreviewUrl || preview
  const savedArtifact = !originalImage && field?.mask?.overlayUrl
    ? { url: field.mask.overlayUrl, kind: 'saved-overlay' as const }
    : !preview && field?.mask?.maskUrl ? { url: field.mask.maskUrl, kind: 'saved-mask' as const } : undefined
  const selectedReview = review?.fieldId === field?.id && (!data.run?.id || review?.runId === data.run.id) ? review : data.reviews?.filter(r => r.fieldId === field?.id).at(-1)
  const run = data.run ?? {}
  const modelRevision = String(run.git_tag || run.git_sha || (field?.raw as any)?.pipeline?.git_tag || (field?.raw as any)?.pipeline?.git_sha || run.model_version || 'Not supplied')
  const verdictReason = hasAcquisitionConcern(field?.acquisition?.status)
    ? 'The image needs an acquisition check before a material conclusion.'
    : unavailable ? 'Some required measurements were unavailable in this analysis.'
      : outside ? `${outside} selected ${outside === 1 ? 'check is' : 'checks are'} outside the chosen range.`
        : 'This screening result needs a reviewed policy before it can be accepted.'
  const issueBands = useMemo(() => buildIssues(field, measured, selectedReview), [field, measured, selectedReview])
  const selectedRisk = riskCatalog.find((risk) => risk.id === selectedRiskId) || riskCatalog[0]
  const exportFile = (kind: 'json' | 'csv') => {
    const raw = kind === 'json' ? JSON.stringify({ data, criteria, review }, null, 2) : toCsv(field, measured, { modelRevision, criteriaRevision: 'v1 local controls', review: selectedReview })
    const blob = new Blob([raw], { type: kind === 'json' ? 'application/json' : 'text/csv' })
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `cottrell-${field?.id || 'results'}.${kind}`; link.click(); URL.revokeObjectURL(link.href)
  }
  if (!field) return <div className="results results-empty"><p>No scored field was supplied for this run.</p>{onNew && <button onClick={onNew}>Start a new analysis</button>}</div>

  return <div className={`results ${expanded ? 'results--expanded' : ''}`}>
    <header className="results__header">
      <a className="wordmark" href="#/results" aria-label="Cottrell results">Cottrell<span>·</span></a>
      <div className="header-field"><label htmlFor="result-field">Field</label><select id="result-field" value={field.id} onChange={(event) => navigate(view, event.target.value)}>{fields.map((item) => <option key={item.id} value={item.id}>{item.id}</option>)}</select><ChevronDown aria-hidden="true" /></div>
      <div className="header-meta"><span>{data.mode || 'Mode not supplied'}</span><span>Model {modelRevision}</span>{run.embedding_backend && <span>{run.embedding_backend === 'local_cpu_fallback' ? 'Local CPU · GPU unavailable' : String(run.embedding_backend)}</span>}<span className="status-dot">Result ready</span></div>
      <div className="export-actions"><button onClick={() => window.print()} title="Print or save PDF"><Printer size={17} /> <span>Report</span></button><button onClick={() => exportFile('csv')} title="Download measurements CSV"><FileDown size={17} /><span>CSV</span></button><button onClick={() => exportFile('json')} title="Download run JSON"><Download size={17} /><span>JSON</span></button>{imageChannel?.rawUrl && <a className="source-download" href={imageChannel.rawUrl} download title="Download recorded source TIFF"><Download size={17} /><span>TIFF</span></a>}</div>
    </header>

    <nav className="result-tabs" aria-label="Result views">
      {views.map((item, index) => <button key={item.id} className={view === item.id ? 'is-active' : ''} onClick={() => selectView(item.id)} aria-current={view === item.id ? 'page' : undefined}><span>{item.label}</span><small>{String(index + 1).padStart(2, '0')}</small></button>)}
      <span className="result-tabs__line" />
    </nav>

    <section id="top" className="results__content" aria-live="polite">
      <div className="results__copy">
        {view === 'overview' && <Overview field={field} measured={measured} selectedCriterion={selectedCriterion} setSelectedCriterion={setSelectedCriterion} verdictReason={verdictReason} outside={outside} unavailable={unavailable} topProbability={topProbability} probabilities={probabilities} criteriaVersion="v1 local controls" />}
        {view === 'investigate' && <Investigate issues={issueBands} field={field} criteria={criteria} selectedRiskId={selectedRisk.id} onRiskSelect={(risk: RiskGuide) => setSelectedRiskId(risk.id)} />}
        {view === 'material' && <MaterialDetails field={field} metadata={data.metadata} detailsOpen={detailsOpen} setDetailsOpen={setDetailsOpen} />}
        {view === 'model' && <ModelOutput field={field} run={run} />}
      </div>
      <aside className="results__visual" aria-label="Evidence visual">
        <div className="visual-topline"><span>{materialViews.includes(view) ? savedArtifact ? `Saved segmentation ${savedArtifact.kind === 'saved-overlay' ? 'overlay' : 'mask'} · original TIFF unavailable` : 'Material perspective · separated analysis layers' : view === 'investigate' ? 'Stakeholder trace' : 'Evidence lens'}</span><button onClick={() => setExpanded(!expanded)} aria-pressed={expanded}><Expand size={16} />{expanded ? 'Restore view' : 'Expand visual'}</button></div>
        {materialViews.includes(view) ? (originalImage || savedArtifact?.url) ? <Suspense fallback={<div className="visual-unavailable"><p>Preparing material view…</p></div>}><MaterialScene imageUrl={originalImage || savedArtifact!.url} fieldId={field.id} layers={savedArtifact ? [] : field.mask?.layers || []} imageKind={savedArtifact?.kind || 'original'} /></Suspense> : <UnavailableImage channel={imageChannel} /> : view === 'investigate' ? <StakeholderTrace risk={selectedRisk} field={field} criteria={criteria} /> : <EvidenceLens imageUrl={preview} channel={imageChannel} criterion={measured.find((item) => item.criterion.id === selectedCriterion)?.criterion} field={field} />}
      </aside>
    </section>

    <footer className="results__footer"><span>Image-level screening · model output is not a probability of future material failure.</span><div>{view !== 'overview' && <button onClick={() => selectView(views[views.findIndex((item) => item.id === view) - 1].id)}><ArrowLeft size={17} /> Previous</button>}{view !== views[views.length - 1].id && <button className="next-view" onClick={() => selectView(views[views.findIndex((item) => item.id === view) + 1].id)}>Next: {views[views.findIndex((item) => item.id === view) + 1].label}<ArrowRight size={17} /></button>}</div></footer>
  </div>
}

function Overview({ field, measured, selectedCriterion, setSelectedCriterion, verdictReason, outside, unavailable, topProbability, probabilities, criteriaVersion }: any) {
  const visible = measured
  return <>
    <section className="verdict-band"><span className="screening-label">Image-level screening</span><h1>Inspect further</h1><p className="verdict-reason">{verdictReason}</p><p className="fact-line">Closest known batch <strong>{field.predictedBatch || 'Unavailable'}</strong> · {pct(topProbability)} batch-match probability · {field.confidenceTier || 'Tier not supplied'} · validation {field.reliability?.correct ?? '—'}/{field.reliability?.total ?? '—'}</p><div className="result-context"><span>Baseline: <b>{statusText(field.baseline?.status)}</b></span><span>Acquisition: <b>{statusText(field.acquisition?.status)}</b></span></div><button className="primary-action" onClick={() => document.getElementById('criteria')?.scrollIntoView({ behavior: 'auto' })}>Review selected checks <ArrowDownToLine size={17} /></button></section>
    <section id="criteria" className="criteria-section"><div className="section-heading"><div><h2>Selected checks</h2><p>{measured.length - outside - unavailable} within range · {outside} outside range{unavailable ? ` · ${unavailable} unavailable` : ''}</p></div><span className="range-note">{criteriaVersion} · selected limits only</span></div>{visible.length ? <div className="criteria-list">{visible.map(({ criterion, actual, finite, within }: any) => <button key={criterion.id} className={`criterion-row ${selectedCriterion === criterion.id ? 'is-selected' : ''}`} onClick={() => setSelectedCriterion(criterion.id)}><span className="criterion-mark">{!finite ? <TriangleAlert size={16} /> : within ? <Check size={16} /> : <ShieldAlert size={16} />}</span><span className="criterion-name"><strong>{criterion.label}</strong><small>{finite ? valueText(actual, 1, criterion.unit) : 'Measurement unavailable'}</small></span><span className="criterion-range">{criterion.min ?? '—'}–{criterion.max ?? '—'} {criterion.unit || ''}</span><span className={`criterion-state ${finite && within ? 'pass' : 'review'}`}>{!finite ? 'Unavailable' : within ? 'Within range' : 'Outside range'}</span><Eye size={16} /></button>)}</div> : <p className="empty-copy">No selected criteria were supplied. The model result remains available below.</p>}</section>
    <section className="comparison-section"><div className="section-heading"><div><h2>Batch-match comparison</h2><p>Image similarity to the known batches, not a defect probability.</p></div></div><div className="probability-bars">{probabilities.length ? probabilities.map(([batch, probability]: [string, any]) => <div className="probability-row" key={batch}><span>{batch}</span><i><b style={{ width: `${Math.max(0, Math.min(100, probability * 100))}%` }} /></i><strong>{pct(probability)}</strong></div>) : <p className="empty-copy">Batch probabilities were not supplied.</p>}</div><p className="phase-provenance">Phase identity: {phaseText(field.phaseIdentity)}</p><details id="model-details"><summary>Model details <Info size={15} /></summary><p>Runner-up: {field.runnerUp || 'Unavailable'} · Margin: {pct(field.margin)}</p>{field.caveats?.length ? <ul>{field.caveats.map((caveat: string) => <li key={caveat}>{caveat}</li>)}</ul> : <p>No caveats were supplied.</p>}</details></section>
  </>
}

function Investigate({ issues, field, criteria, selectedRiskId, onRiskSelect }: { issues: any[]; field: ResultField; criteria: Criterion[]; selectedRiskId: string; onRiskSelect: (risk: RiskGuide) => void }) {
  return <><section className="investigate-intro"><span className="screening-label">Workflow priority</span><h1>What to inspect next</h1><p>These are review priorities based on recorded evidence. They do not assign cause or blame.</p></section><div className="issue-list">{issues.map((issue, index) => <article className="issue-band" key={issue.title}><span className="issue-index">{String(index + 1).padStart(2, '0')}</span><div><h2>{issue.title}</h2><dl><div><dt>Review with</dt><dd>{issue.owner}</dd></div><div><dt>Evidence</dt><dd>{issue.evidence}</dd></div><div><dt>Why this matters</dt><dd>{issue.reason}</dd></div><div><dt>Next action</dt><dd>{issue.next}</dd></div></dl></div></article>)}</div><section className="driver-section"><h2>Recorded model signals</h2>{field.drivers?.length ? field.drivers.slice(0, 3).map((driver) => <div className="driver" key={driver.name}><Sparkles size={16} /><p><strong>{featureLabels[driver.name.split('_')[0]] || driver.name.replace('embedding PC', 'Image-pattern signal')}</strong> {/embedding/i.test(driver.name) ? 'This image pattern helped match the field to a known batch. It may reflect microscope settings as well as the material.' : 'This measurement supported the batch match. Review its mask before relying on it; it does not establish a defect.'}</p></div>) : <p className="empty-copy">No model drivers were supplied.</p>}</section><KpiGuidance field={field} criteria={criteria} selectedRiskId={selectedRiskId} onRiskSelect={onRiskSelect} /></>
}

function MaterialDetails({ field, metadata, detailsOpen, setDetailsOpen }: { field: ResultField; metadata?: Record<string, string>; detailsOpen: boolean; setDetailsOpen: (value: boolean) => void }) {
  const dark = field.features.F01; const bright = field.features.F02; const mid = typeof dark === 'number' && typeof bright === 'number' ? 1 - dark - bright : null
  const chemistry = metadata?.chemistry || 'Unknown'; const history = metadata?.history || 'Unknown'
  const raw = field.raw as any
  return <><section className="material-intro"><span className="screening-label">Field inventory</span><h1>Material details</h1><p>Labels come from the analysis record. They are not inferred as chemical composition.</p></section><div className="inventory" role="region" aria-label="Field material inventory" tabIndex={0}><div className="inventory-head"><span>Display name</span><span>Reported chemistry</span><span>State of charge</span><span>Material history</span><span>Classes</span></div><div className="inventory-row"><strong>{field.id}</strong><span>{chemistry}</span><span>Unknown</span><span>{history}</span><span className="class-chips"><i>Dark</i><i>Mid</i><i>Bright</i></span></div>{field.channels.map((channel) => <div className="channel-row" key={channel.filename}><span>{channel.name}</span><span>{channel.filename}</span><span>{channel.available === false ? 'Original TIFF unavailable' : channel.width && channel.height ? `${channel.width} × ${channel.height}px` : 'Dimensions not supplied'}</span></div>)}</div><p className="phase-provenance">Phase identity: {phaseText(field.phaseIdentity)}</p><div className="class-table"><div><span className="swatch dark" /><strong>Dark</strong><span>Pore (Polaron-stated)</span><b>{pct(dark as number)}</b></div><div><span className="swatch mid" /><strong>Mid-tone</strong><span>Graphite (Polaron-stated)</span><b>{pct(mid as number)} <small>derived</small></b></div><div><span className="swatch bright" /><strong>Bright</strong><span>Silicon (Polaron-stated)</span><b>{pct(bright as number)}</b></div></div>{field.mask?.layers?.length ? <div className="layer-list" aria-label="Verified segmentation layers">{field.mask.layers.map((layer) => <span key={layer.id}>{layer.label} · model mask</span>)}</div> : <p className="empty-copy">Segmentation layers unavailable for this engine release.</p>}<button className="details-toggle" onClick={() => setDetailsOpen(!detailsOpen)} aria-expanded={detailsOpen}>Analysis provenance <ChevronDown size={17} /></button>{detailsOpen && <div className="provenance"><p>Model release: {String(raw?.pipeline?.git_tag || raw?.pipeline?.git_sha || 'Not supplied')}</p>{field.mask && <p>Mask artifact: {field.mask.sha256 || 'Hash not supplied'} · offset {field.mask.offset?.join(', ') || 'not supplied'}</p>}{field.channels.map((channel) => <p key={channel.filename}>{channel.filename} · SHA-256 {channel.sha256 || 'Not supplied'}</p>)}</div>}</>
}

function EvidenceLens({ imageUrl, channel, criterion, field }: { imageUrl?: string; channel?: ResultChannel; criterion?: Criterion; field: ResultField }) {
  const acquisition = field.acquisition
  const [showMask, setShowMask] = useState(false)
  const [opacity, setOpacity] = useState(65)
  const mask = field.mask
  const overlay = mask?.overlayUrl || mask?.maskUrl
  const original = channel?.available === false ? undefined : mask?.originalCroppedPreviewUrl || imageUrl
  const savedArtifact = !original && overlay ? { url: overlay, label: mask?.overlayUrl ? 'Saved segmentation overlay' : 'Saved segmentation mask' } : undefined
  return <div className="evidence-lens">{original ? <div className="image-stack"><img src={original} alt={`Microscope field ${field.id}`} />{showMask && overlay && <img className="mask-overlay" src={overlay} style={{ opacity: opacity / 100 }} alt="Exact segmentation mask overlay" />}</div> : savedArtifact ? <div className="image-stack image-stack--saved-overlay"><img src={savedArtifact.url} alt={`${savedArtifact.label} for ${field.id}`} /></div> : <UnavailableImage channel={channel} />}<div className="lens-caption"><span>{savedArtifact ? `${savedArtifact.label} · original TIFF unavailable` : criterion ? `Evidence for ${criterion.label}` : 'Original image view'}</span><p>{savedArtifact ? 'This is the committed segmentation artifact from the saved run. It is not the original micrograph or a ground-truth label.' : hasAcquisitionConcern(acquisition?.status) ? `Acquisition check: ${statusText(acquisition?.status)}.` : overlay ? 'Exact segmentation mask is exploratory, not ground truth.' : 'Segmentation overlay unavailable for this engine release.'}</p></div>{overlay && !savedArtifact && <div className="mask-controls"><label><input type="checkbox" checked={showMask} onChange={(event) => setShowMask(event.target.checked)} /> Show exact mask</label><label>Opacity <input type="range" min="15" max="100" value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} disabled={!showMask} /><output>{opacity}%</output></label><a href={mask?.maskUrl || overlay} download><Download size={15} /> Download mask</a></div>}{savedArtifact && <div className="mask-controls"><a href={mask?.maskUrl || savedArtifact.url} download><Download size={15} /> Download saved mask</a></div>}</div>
}

function UnavailableImage({ channel }: { channel?: ResultChannel }) {
  return <div className="visual-unavailable"><Eye size={28} /><p>Original image unavailable</p><small>{channel?.available === false ? 'The recorded TIFF is not present on this machine.' : 'The run record did not supply a displayable preview.'}</small></div>
}

function EvidenceTree({ issues, field }: { issues: any[]; field: ResultField }) {
  return <div className="evidence-tree"><div className="tree-node source"><small>Input</small><strong>{field.id}</strong><span>{field.channels.length} recorded channel{field.channels.length === 1 ? '' : 's'}</span></div>{issues.map((issue) => <div className="tree-branch" key={issue.title}><i /><div className="tree-node"><small>Finding</small><strong>{issue.title}</strong><span>{issue.owner}</span></div><div className="tree-action"><ArrowRight size={16} /> {issue.next}</div></div>)}<p className="tree-note">Solid links are recorded workflow relationships. Cause not established.</p></div>
}

function buildIssues(field: ResultField, measured: any[], review?: Review) {
  const issues: any[] = []
  if (!field) return issues
  const acquisition = field.acquisition
  if (hasAcquisitionConcern(acquisition?.status)) issues.push({ title: 'Check image acquisition', owner: 'Microscopy team', evidence: acquisition?.reason || statusText(acquisition?.status), reason: 'Image conditions can change what the model sees.', next: 'Compare the original image and microscope settings.' })
  if (field.baseline?.status && !/pass|within|ok/i.test(field.baseline.status)) issues.push({ title: 'Compare with the reference', owner: routeName[field.route || ''] || 'Materials expert', evidence: field.baseline.reason || statusText(field.baseline.status), reason: 'The image differs from its available reference. This may also reflect imaging conditions.', next: 'Review the field beside the reference image.' })
  const out = measured.find((item) => item.finite && !item.within)
  if (out) issues.push({ title: `Review ${out.criterion.label.toLowerCase()}`, owner: routeName[field.route || ''] || 'Materials expert', evidence: `${valueText(out.actual, 1, out.criterion.unit)} is outside the selected ${out.criterion.min}–${out.criterion.max} ${out.criterion.unit || ''} range.`, reason: 'This selected image measure needs an expert check before a disposition.', next: 'Inspect the measurement and confirm the selected limits.' })
  if (review?.skipped || review?.tag?.toLowerCase().replace(/\s+/g, '_') === 'not_sure') issues.push({ title: 'Resolve the reviewer selection', owner: 'Materials expert', evidence: review.note || 'A review region was not confirmed.', reason: 'The report preserves this unresolved review state.', next: 'Record a region selection or retain the documented skip.' })
  return issues.length ? issues.slice(0, 3) : [{ title: 'No additional issue identified', owner: 'Materials expert', evidence: 'The engine did not raise an acquisition or reference flag for this field.', reason: 'This does not validate a manufacturing acceptance decision.', next: 'Review the selected criteria and supporting evidence below.' }]
}

function toCsv(field: ResultField | undefined, measured: any[], context: { modelRevision: string; criteriaRevision: string; review?: Review }) {
  const rows = [['field', 'model_revision', 'criteria_revision', 'review_field', 'measure', 'value', 'unit', 'minimum', 'maximum', 'status']]
  const reviewField = typeof context.review?.fieldId === 'string' ? context.review.fieldId : ''
  measured.forEach((item) => rows.push([field?.id || '', context.modelRevision, context.criteriaRevision, reviewField, item.criterion.label, item.actual == null ? '' : String(item.actual), item.criterion.unit || '', String(item.criterion.min ?? ''), String(item.criterion.max ?? ''), !item.finite ? 'Unavailable' : item.within ? 'Within range' : 'Outside range']))
  return rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n')
}

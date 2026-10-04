import type { ResultField } from './Results'
import MetricGlossary from './MetricGlossary'
import { formatBatchLabel, formatMetricValue, metricLabel, metricMeaning, metricTechnicalName, metricUnit } from './metricLanguage'
import './ModelOutput.css'
import './ModelOutput.refine.css'
import './ModelOutput.precision.css'

type Props = { field: ResultField; run?: Record<string, any> }

type RawDriver = { name?: string; value?: number; effect_size?: number; direction?: string; tag?: string; units?: string; pc_sentence?: string; justification?: any }
type Raw = {
  verdict?: any; uncertainty?: Record<string, string>; acquisition?: any; evidence?: { drivers?: RawDriver[] }; routing?: any
  next_action?: string; caveats?: string[]; pipeline?: Record<string, any>
}

const pct = (value: unknown, digits = 1) => typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : 'Not supplied'
const marginText = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)} percentage points` : 'Not supplied'
const number = (value: unknown, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'Not supplied'
const pretty = (value: unknown) => typeof value === 'string' ? value.replaceAll('_', ' ') : 'Not supplied'

/** Renders only the current engine record; validation language comes from its own justification/uncertainty fields. */
export default function ModelOutput({ field, run }: Props) {
  const raw = (field.raw || {}) as Raw
  const closed = raw.verdict?.closed_set || {}
  const open = raw.verdict?.open_set || {}
  const rawDrivers = raw.evidence?.drivers || []
  const probabilities = Object.entries(closed.probabilities || field.probabilities || {}).sort(([a], [b]) => String(a).localeCompare(String(b)))
  const prediction = closed.predicted_batch || field.predictedBatch
  const confidence = closed.confidence ?? (prediction ? field.probabilities?.[prediction] : undefined)
  const tier = closed.tier || field.confidenceTier
  const loio = closed.justification?.numbers?.loio_reliability || field.reliability
  const pipeline = raw.pipeline || run || {}
  const acquisitionFlags = Object.entries(raw.acquisition?.covariates || {}).filter(([, value]: any) => value?.flag)
  const tierReason = closed.justification?.numbers?.tier_reason
  const validationText = raw.uncertainty?.sampling
  const pValue = closed.justification?.numbers?.loio_permutation_p
  const interval = parseWilson(validationText)
  const baselineNumbers = open.justification?.numbers || raw.verdict?.justification?.numbers || {}
  const baselineRankP = baselineNumbers.rank_p
  const guidance = makeGuidance({ tier, prediction, confidence, runnerUp: closed.runner_up || field.runnerUp, margin: closed.margin ?? field.margin, label: raw.verdict?.label, flags: acquisitionFlags.map(([name]) => name), reliability: loio })
  const rawAvailable = Boolean(raw.verdict || field.predictedBatch)

  if (!rawAvailable) return <section className="model-output model-output--empty"><p>The run record did not include model output for this field.</p><small>Prediction, probabilities, uncertainty and traceable evidence are unavailable rather than estimated.</small></section>

  return <div className="model-output">
    <section className="model-output__hero">
      <div>
        <span className="screening-label">{pipeline.exploratory ? 'Exploratory run · locked recipe' : pipeline.frozen ? 'Frozen evaluation' : 'Recorded model output'} · image level</span>
        <h1 title={typeof prediction === 'string' ? prediction : undefined}>{formatBatchLabel(prediction)}</h1>
        <p>{plainLead(prediction, confidence, tier, raw.verdict?.label)}</p>
      </div>
      <dl className="model-output__signal">
        <div><dt>Best match among known batches</dt><dd>{pct(confidence)}</dd></div>
        <div><dt>Recorded confidence tier</dt><dd className={`tier tier--${String(tier || 'unknown').toLowerCase()}`}>{tier || 'Not supplied'}</dd></div>
        <div><dt>Lead over next closest batch</dt><dd title="Difference in percentage points">{marginText(closed.margin ?? field.margin)}</dd></div>
      </dl>
    </section>

    <section className="model-guidance" aria-label="Plain-English guidance"><span className="screening-label">Plain-English guidance</span><p>{guidance}</p><small>Guidance built from the recorded tier, reference status, imaging flags and validation record. It does not change the model’s bet.</small></section>

    <section className="model-output__section">
      <div className="model-output__heading"><div><h2>Known-batch matches <small>Batch probability (closed-set)</small></h2><p>How strongly the model prefers each of the three batches it was trained to recognise. These are not defect or failure probabilities.</p></div><span>Next closest: <b title={closed.runner_up || field.runnerUp || undefined}>{formatBatchLabel(closed.runner_up || field.runnerUp)}</b></span></div>
      {probabilities.length ? <div className="model-probabilities">{probabilities.map(([batch, probability]) => <div className={batch === prediction ? 'model-probability is-selected' : 'model-probability'} key={batch}><div><strong title={batch}>{formatBatchLabel(batch)}</strong>{batch === prediction && <small>Selected by model</small>}</div><i aria-hidden="true"><b style={{ width: `${Math.min(100, Math.max(0, Number(probability) * 100))}%` }} /></i><output>{pct(probability)}</output></div>)}</div> : <p className="model-output__missing">Batch probabilities were not supplied by this run.</p>}
      {closed.note && <p className="model-output__note">{closed.note}</p>}
    </section>

    <section className="model-output__section model-output__split">
      <div>
        <div className="model-output__heading"><div><h2>How to read this confidence</h2><p>Confidence measures the model’s preference among known batches for this image.</p></div></div>
        <dl className="model-facts">
          <div><dt>Why this tier was assigned</dt><dd>{tierReason || 'Not supplied by this run.'}</dd></div>
          <div><dt>When the model chose this batch (LOIO precision)</dt><dd>{loio?.correct != null && loio?.total != null ? `${loio.correct} of ${loio.total} such predictions were correct in leave-one-image-out testing` : loio?.pred_batch_correct != null && loio?.pred_batch_n != null ? `${loio.pred_batch_correct} of ${loio.pred_batch_n} such predictions were correct in leave-one-image-out testing` : 'Not supplied'}</dd></div>
          <div><dt>When it chose this batch at this tier</dt><dd>{loio?.pred_batch_tier_correct != null && loio?.pred_batch_tier_n != null ? `${loio.pred_batch_tier_correct} of ${loio.pred_batch_tier_n} such predictions were correct in leave-one-image-out testing` : 'Not supplied'}</dd></div>
        </dl>
      </div>
      <aside className="model-validation">
        <span className="screening-label">Model-wide testing, not this image</span>
        <h3>How the model performed in testing</h3>
        <dl>
          <div><dt>Correct batch matches (LOIO accuracy)</dt><dd>{closed.justification?.numbers?.loio_accuracy || 'Not supplied'}</dd></div>
          <div><dt>Accuracy uncertainty range (95% Wilson confidence interval)</dt><dd>{interval || 'Not supplied in this run'}</dd></div>
          <div><dt>Shuffled-label test (permutation p-value)</dt><dd>{pValue == null ? 'Not supplied' : number(pValue, 4)}</dd></div>
          <div><dt>Per-image confidence interval</dt><dd>Not provided by this model</dd></div>
        </dl>
        <p>{validationText ? `${validationText} The Wilson interval is the uncertainty around the model’s overall test accuracy. The shuffled-label test asks whether the observed accuracy is stronger than labels randomly reassigned; it is not the probability that this match is correct.` : 'This run does not carry model-level validation statistics.'}</p>
      </aside>
    </section>

    <section className="model-output__section">
      <div className="model-output__heading"><div><h2>What influenced this match</h2><p>The strongest inputs behind the selected batch. They explain the batch match, not material quality or cause.</p></div></div>
      {rawDrivers.length ? <div className="model-drivers">{rawDrivers.slice(0, 3).map((driver, index) => <Driver key={`${driver.name}-${index}`} driver={driver} index={index} />)}</div> : <p className="model-output__missing">No driver list was supplied by this run.</p>}
    </section>

    <section className="model-output__section model-output__checks">
      <div><span className="screening-label">Separate checks</span><h2>Reference and acquisition</h2><dl className="model-facts"><div><dt>Batch 3 reference status</dt><dd>{pretty(raw.verdict?.label || field.baseline?.status)}</dd></div><div><dt>Closest image-pattern reference</dt><dd title={open.nearest_batch}>{formatBatchLabel(open.nearest_batch)}</dd></div><div><dt>Batch 3 upper reference band</dt><dd>{open.matches_known_batch == null ? 'Not supplied' : open.matches_known_batch ? 'At or below the Batch 3 upper band' : 'Above the Batch 3 upper band'}</dd></div><div><dt>Reference distance test (rank p-value)</dt><dd>{baselineRankP == null ? 'Not supplied' : `${number(baselineRankP, 3)} · reference distance only`}</dd></div><div><dt>Imaging differences to check</dt><dd>{acquisitionFlags.length ? acquisitionFlags.map(([name]) => name).join(', ') : raw.acquisition ? 'None recorded' : 'Not supplied'}</dd></div></dl></div>
      <div className="model-output__action"><span className="screening-label">Recorded next step</span><p>{raw.next_action || 'Not supplied by this run.'}</p><small>{raw.routing?.reason || 'Routing reason not supplied.'}</small></div>
    </section>

    <details className="model-output__trace"><summary>Native model evidence and limitations</summary><div><p><b>Recipe:</b> {pipeline.git_tag || pipeline.git_sha || 'Not supplied'} · config {pipeline.config_hash || 'Not supplied'} · {pipeline.exploratory ? 'Exploratory run' : pipeline.frozen ? 'Frozen run' : 'Run status not supplied'}.</p><p><b>Native explanation:</b> {raw.verdict?.reason || 'Not supplied by this run.'}</p><p><b>Model rule:</b> {closed.justification?.rule || 'Not supplied by this run.'}</p>{raw.caveats?.length ? <ul>{raw.caveats.map((caveat, index) => <li key={index}>{caveat}</li>)}</ul> : <p>No caveats were supplied by this run.</p>}<EvidenceList items={[...(closed.justification?.evidence || []), ...(open.justification?.evidence || [])]} /><p className="model-output__note">A reported 95% confidence interval and permutation p-value describe validation across the training-image evaluation. They do not quantify uncertainty or defect risk for this individual image.</p></div></details>
    <MetricGlossary />
  </div>
}

function plainLead(prediction: unknown, confidence: unknown, tier: unknown, baseline: unknown) {
  const name = typeof prediction === 'string' ? formatBatchLabel(prediction) : 'a known batch'
  const level = typeof tier === 'string' ? tier.toLowerCase() : 'recorded'
  const reference = baseline === 'outside_bounds' ? ' It is also outside the recorded Batch 3 reference range.' : baseline === 'investigate' ? ' Its Batch 3 reference comparison needs review.' : ''
  return `This image most closely matches ${name} among the model’s three known batches (${pct(confidence)} model probability; recorded ${level} tier). This number is not calibrated as the chance of being correct or having a defect.${reference}`
}

function makeGuidance({ tier, prediction, confidence, runnerUp, margin, label, flags, reliability }: any) {
  const flagText = flags.length ? flags.join(', ') : 'no acquisition flags recorded'
  const record = reliability?.pred_batch_correct != null && reliability?.pred_batch_n != null ? `${reliability.pred_batch_correct}/${reliability.pred_batch_n}` : 'not supplied'
  if (flags.length) return `Imaging differs from the training images (${flagText}); re-image or confirm settings before interpreting the batch match.`
  if (tier === 'low' && label === 'outside_bounds' && prediction !== 'Batch_3') return `Probably not Batch 3 because this image is outside its reference range. ${formatBatchLabel(prediction)} versus ${formatBatchLabel(runnerUp)} remains provisional: this type of match was correct ${record} times in testing. Image more sections or compare the 11 measurements with the Batch 1 and Batch 2 ranges.`
  if (tier === 'low' && label === 'outside_bounds') return 'This is an unusual image: the model selected Batch 3 but the image is outside the Batch 3 reference range. Check imaging first; if clear, send it for materials review as a possible new variation.'
  if (tier === 'low' && typeof confidence === 'number' && confidence < .5) return `No batch is strongly favoured (best match ${pct(confidence)}). Treat this as undecided, image more sections, and review ${formatBatchLabel(runnerUp)} as an alternative.`
  if (tier === 'low') return `The model recorded low confidence in ${formatBatchLabel(prediction)}. Treat the identity as provisional and compare more sections before acting.`
  if (tier === 'medium') return `The recorded run assigned medium confidence to ${formatBatchLabel(prediction)} (${pct(confidence)} model probability; ${marginText(margin)} lead). Confirm with a second image before acting.`
  if (tier === 'high' && (prediction === 'Batch_1' || prediction === 'Batch_2')) return `The model has a high recorded tier for ${formatBatchLabel(prediction)}, but Batch 1 and Batch 2 identities should remain provisional. Use this as a prompt to compare more sections and the recorded measurements, not as a quality verdict.`
  return `The model’s recorded tier supports a ${formatBatchLabel(prediction)} match. Review the reference and acquisition checks alongside the image before drawing a material conclusion.`
}

function isEmbedding(name?: string) { return /embedding\s*pc/i.test(name || '') }
function featureId(name?: string) { return (name || '').match(/F(?:0[1-9]|1[01])/i)?.[0]?.toUpperCase() }
function Driver({ driver, index }: { driver: RawDriver; index: number }) {
  const id = featureId(driver.name)
  const embedding = isEmbedding(driver.name)
  const rawValue = id ? formatMetricValue(id, driver.value) : number(driver.value)
  return <article><span>{String(index + 1).padStart(2, '0')}</span><div><h3>{embedding ? 'Image-pattern signal' : metricLabel(id)}</h3><small className="model-driver__technical">{embedding ? (driver.name || 'Signal ID not supplied') : <><code>{id}</code> · {metricTechnicalName(id)} · {metricUnit(id)}</>}</small><p>{driver.pc_sentence || (embedding ? plainDriverTag(driver) : metricMeaning(id))}</p><small>{embedding ? 'This is an image-pattern component. It does not establish a physical cause.' : `Segmentation-derived measurement. ${driver.tag?.includes('drop') ? 'Sensitive to mask thresholds; ' : ''}Review the mask before relying on it.`}</small></div><dl><div><dt>Recorded value</dt><dd>{rawValue}</dd></div><div><dt>Support for match</dt><dd>{number(driver.effect_size)}</dd></div></dl></article>
}
function plainDriverTag(driver: RawDriver) {
  if (isEmbedding(driver.name)) return 'This image pattern helped the model match the field to a known batch. Acquisition and material effects could not be separated.'
  return 'This measured image feature supported the selected batch match.'
}
function EvidenceList({ items }: { items: any[] }) {
  const unique = items.filter((item, index) => item?.file && items.findIndex((other) => other?.file === item.file && other?.selector === item.selector) === index)
  return unique.length ? <div className="model-evidence"><b>Evidence record</b><ul>{unique.map((item, index) => <li key={`${item.file}-${index}`}><code>{item.file}</code>{item.selector ? ` · ${item.selector}` : ''}</li>)}</ul></div> : <p>Evidence file and selector were not supplied by this run.</p>
}

function parseWilson(value?: string) {
  if (!value) return undefined
  const match = value.match(/(?:Wilson\s+)?95\s*%\s*CI\s*[(:]?\s*([0-9.]+)\s*[-–,]\s*([0-9.]+)/i)
  return match ? `${(Number(match[1]) * 100).toFixed(0)}%–${(Number(match[2]) * 100).toFixed(0)}%` : undefined
}

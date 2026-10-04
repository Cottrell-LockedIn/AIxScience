import type { ResultField } from './Results'
import './ModelOutput.css'
import './ModelOutput.refine.css'

type Props = { field: ResultField; run?: Record<string, any> }

type RawDriver = { name?: string; value?: number; effect_size?: number; direction?: string; tag?: string; units?: string; pc_sentence?: string; justification?: any }
type Raw = {
  verdict?: any; uncertainty?: Record<string, string>; acquisition?: any; evidence?: { drivers?: RawDriver[] }; routing?: any
  next_action?: string; caveats?: string[]; pipeline?: Record<string, any>
}

const pct = (value: unknown, digits = 1) => typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : 'Not supplied'
const marginText = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)} pp` : 'Not supplied'
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
        <h1>{prediction || 'Prediction unavailable'}</h1>
        <p>{plainLead(prediction, confidence, tier, raw.verdict?.label)}</p>
      </div>
      <dl className="model-output__signal">
        <div><dt>Top model probability · known batches</dt><dd>{pct(confidence)}</dd></div>
        <div><dt>Confidence tier</dt><dd className={`tier tier--${String(tier || 'unknown').toLowerCase()}`}>{tier || 'Not supplied'}</dd></div>
        <div><dt>Lead over runner-up</dt><dd title="Difference in percentage points">{marginText(closed.margin ?? field.margin)}</dd></div>
      </dl>
    </section>

    <section className="model-guidance" aria-label="Plain-English guidance"><span className="screening-label">Plain-English guidance</span><p>{guidance}</p><small>Guidance built from the recorded tier, reference status, imaging flags and validation record. It does not change the model’s bet.</small></section>

    <section className="model-output__section">
      <div className="model-output__heading"><div><h2>Known-batch probabilities</h2><p>These are closed-set matches to the three batches the model knows. They are not defect or failure probabilities.</p></div><span>Runner-up: <b>{closed.runner_up || field.runnerUp || 'Not supplied'}</b></span></div>
      {probabilities.length ? <div className="model-probabilities">{probabilities.map(([batch, probability]) => <div className={batch === prediction ? 'model-probability is-selected' : 'model-probability'} key={batch}><div><strong>{batch}</strong>{batch === prediction && <small>Selected by model</small>}</div><i aria-hidden="true"><b style={{ width: `${Math.min(100, Math.max(0, Number(probability) * 100))}%` }} /></i><output>{pct(probability)}</output></div>)}</div> : <p className="model-output__missing">Batch probabilities were not supplied by this run.</p>}
      {closed.note && <p className="model-output__note">{closed.note}</p>}
    </section>

    <section className="model-output__section model-output__split">
      <div>
        <div className="model-output__heading"><div><h2>How to read this confidence</h2><p>Confidence measures the model’s preference among known batches for this image.</p></div></div>
        <dl className="model-facts">
          <div><dt>Tier basis</dt><dd>{tierReason || 'Not supplied by this run.'}</dd></div>
          <div><dt>Same-bet validation record</dt><dd>{loio?.correct != null && loio?.total != null ? `${loio.correct}/${loio.total} correct in leave-one-image-out validation` : loio?.pred_batch_correct != null && loio?.pred_batch_n != null ? `${loio.pred_batch_correct}/${loio.pred_batch_n} correct in leave-one-image-out validation` : 'Not supplied'}</dd></div>
          <div><dt>Same bet and tier</dt><dd>{loio?.pred_batch_tier_correct != null && loio?.pred_batch_tier_n != null ? `${loio.pred_batch_tier_correct}/${loio.pred_batch_tier_n} correct in leave-one-image-out validation` : 'Not supplied'}</dd></div>
        </dl>
      </div>
      <aside className="model-validation">
        <span className="screening-label">Validation, not a per-image interval</span>
        <h3>Model evidence</h3>
        <dl>
          <div><dt>Leave-one-image-out result</dt><dd>{closed.justification?.numbers?.loio_accuracy || 'Not supplied'}</dd></div>
          <div><dt>95% confidence interval</dt><dd>{interval || 'Not supplied in this run'}</dd></div>
          <div><dt>Permutation p-value</dt><dd>{pValue == null ? 'Not supplied' : number(pValue, 4)}</dd></div>
          <div><dt>Per-image confidence interval</dt><dd>Not provided by this model</dd></div>
        </dl>
        <p>{validationText || 'This run does not carry model-level validation statistics.'}</p>
      </aside>
    </section>

    <section className="model-output__section">
      <div className="model-output__heading"><div><h2>Signals supporting the match</h2><p>These are the largest signed inputs to the selected batch. They explain the batch match, not material quality.</p></div></div>
      {rawDrivers.length ? <div className="model-drivers">{rawDrivers.slice(0, 3).map((driver, index) => <article key={`${driver.name}-${index}`}><span>{String(index + 1).padStart(2, '0')}</span><div><h3>{driverPlainName(driver.name)}</h3><small>{driver.name || "Signal ID not supplied"} · {driver.units || "Units not supplied"}</small><p>{driver.pc_sentence || plainDriverTag(driver)}</p><small>{isEmbedding(driver.name) ? 'This is an image-pattern component. It does not establish a physical cause.' : `Segmentation-derived measurement. ${driver.tag?.includes('drop') ? 'Sensitive to mask thresholds; ' : ''}review the mask before relying on it.`}</small></div><dl><div><dt>Raw value</dt><dd>{number(driver.value)}</dd></div><div><dt>Support</dt><dd>{number(driver.effect_size)}</dd></div></dl></article>)}</div> : <p className="model-output__missing">No driver list was supplied by this run.</p>}
    </section>

    <section className="model-output__section model-output__checks">
      <div><span className="screening-label">Separate checks</span><h2>Reference and acquisition</h2><dl className="model-facts"><div><dt>Batch_3 baseline status</dt><dd>{pretty(raw.verdict?.label || field.baseline?.status)}</dd></div><div><dt>Nearest batch by embedding</dt><dd>{open.nearest_batch || 'Not supplied'}</dd></div><div><dt>Batch 3 upper reference band</dt><dd>{open.matches_known_batch == null ? 'Not supplied' : open.matches_known_batch ? 'At or below the Batch 3 upper band' : 'Above the Batch 3 upper band'}</dd></div><div><dt>Baseline rank p-value</dt><dd>{baselineRankP == null ? 'Not supplied' : `${number(baselineRankP, 3)} (baseline distance only)`}</dd></div><div><dt>Acquisition flags</dt><dd>{acquisitionFlags.length ? acquisitionFlags.map(([name]) => name).join(', ') : raw.acquisition ? 'None recorded' : 'Not supplied'}</dd></div></dl></div>
      <div className="model-output__action"><span className="screening-label">Recorded next step</span><p>{raw.next_action || 'Not supplied by this run.'}</p><small>{raw.routing?.reason || 'Routing reason not supplied.'}</small></div>
    </section>

    <details className="model-output__trace"><summary>Native model evidence and limitations</summary><div><p><b>Recipe:</b> {pipeline.git_tag || pipeline.git_sha || 'Not supplied'} · config {pipeline.config_hash || 'Not supplied'} · {pipeline.exploratory ? 'Exploratory run' : pipeline.frozen ? 'Frozen run' : 'Run status not supplied'}.</p><p><b>Native explanation:</b> {raw.verdict?.reason || 'Not supplied by this run.'}</p><p><b>Model rule:</b> {closed.justification?.rule || 'Not supplied by this run.'}</p>{raw.caveats?.length ? <ul>{raw.caveats.map((caveat, index) => <li key={index}>{caveat}</li>)}</ul> : <p>No caveats were supplied by this run.</p>}<EvidenceList items={[...(closed.justification?.evidence || []), ...(open.justification?.evidence || [])]} /><p className="model-output__note">A reported 95% confidence interval and permutation p-value describe validation across the training-image evaluation. They do not quantify uncertainty or defect risk for this individual image.</p></div></details>
  </div>
}

function plainLead(prediction: unknown, confidence: unknown, tier: unknown, baseline: unknown) {
  const name = typeof prediction === 'string' ? prediction : 'a known batch'
  const level = typeof tier === 'string' ? tier.toLowerCase() : 'recorded'
  const reference = baseline === 'outside_bounds' ? ' It is also outside the recorded Batch_3 reference range.' : baseline === 'investigate' ? ' Its Batch_3 reference comparison needs review.' : ''
  return `This image most closely matches ${name} among the model’s three known batches (${pct(confidence)} model probability; recorded ${level} tier). This number is not calibrated as the chance of being correct or having a defect.${reference}`
}

function makeGuidance({ tier, prediction, confidence, runnerUp, margin, label, flags, reliability }: any) {
  const flagText = flags.length ? flags.join(', ') : 'no acquisition flags recorded'
  const record = reliability?.pred_batch_correct != null && reliability?.pred_batch_n != null ? `${reliability.pred_batch_correct}/${reliability.pred_batch_n}` : 'not supplied'
  if (flags.length) return `Imaging differs from the training images (${flagText}); re-image or confirm settings before interpreting the batch match.`
  if (tier === 'low' && label === 'outside_bounds' && prediction !== 'Batch_3') return `Probably not Batch_3 because this image is outside its reference range. ${prediction} versus ${runnerUp || 'the runner-up'} remains provisional: this type of bet was right ${record} times in testing. Image more sections or compare the 11 measurements with the Batch_1 and Batch_2 ranges.`
  if (tier === 'low' && label === 'outside_bounds') return 'This is an unusual image: the model selected Batch_3 but the image is outside the Batch_3 reference range. Check imaging first; if clear, send it for materials review as a possible new variation.'
  if (tier === 'low' && typeof confidence === 'number' && confidence < .5) return `No batch is strongly favoured (best match ${pct(confidence)}). Treat this as undecided, image more sections, and review ${runnerUp || 'the runner-up'} as an alternative.`
  if (tier === 'low') return `The model recorded low confidence in ${prediction || 'the selected batch'}. Treat the identity as provisional and compare more sections before acting.`
  if (tier === 'medium') return `The recorded run assigned medium confidence to ${prediction || 'the selected batch'} (${pct(confidence)} model probability; ${marginText(margin)} lead). Confirm with a second image before acting.`
  if (tier === 'high' && (prediction === 'Batch_1' || prediction === 'Batch_2')) return `The model has a high recorded tier for ${prediction}, but Batch_1 and Batch_2 identities should remain provisional. Use this as a prompt to compare more sections and the recorded measurements, not as a quality verdict.`
  return `The model’s recorded tier supports a ${prediction || 'known-batch'} match. Review the reference and acquisition checks alongside the image before drawing a material conclusion.`
}

function isEmbedding(name?: string) { return /embedding\s*pc/i.test(name || '') }
function driverPlainName(name?: string) {
  if (isEmbedding(name)) return 'Image-pattern signal'
  const names: Record<string, string> = {F01:'Dark-area share', F02:'Bright-area share', F03:'Typical bright-object size', F04:'Bright-object size at the 90th percentile', F05:'Bright-object count per image area', F06:'Bright-object spacing', F07:'Bright-object outline fullness', F08:'Typical dark-region width', F09:'Horizontal versus vertical dark-region spans', F10:'Variation in dark-area share', F11:'Bright-object boundary touching dark regions'}
  return names[(name || '').slice(0,3)] || 'Segmentation-derived measurement'
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

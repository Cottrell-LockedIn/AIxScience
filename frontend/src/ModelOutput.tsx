import type { ResultField } from './Results'
import './ModelOutput.css'
import './ModelOutput.refine.css'
import './ModelOutput.precision.css'
import MetricGlossary from './MetricGlossary'
import { metricLabel, metricTechnicalName } from './metricLanguage'

type Props = { field: ResultField; run?: Record<string, any> }

type RawDriver = { name?: string; value?: number; model_input?: number; coefficient?: number; effect_size?: number; direction?: string; tag?: string; units?: string; pc_sentence?: string; justification?: any }
type Covariate = { value?: number; training_p05?: number; training_p95?: number; flag?: boolean }
type Raw = {
  verdict?: any; uncertainty?: Record<string, string>; acquisition?: any; evidence?: { drivers?: RawDriver[]; embedding?: any }; routing?: any
  next_action?: string; caveats?: string[]; pipeline?: Record<string, any>
}
type EvidenceItem = { file?: string; selector?: string }

const pct = (value: unknown, digits = 1) => typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : 'Not supplied'
const marginText = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)} pp` : 'Not supplied'
const number = (value: unknown, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'Not supplied'
const signed = (value: unknown, digits = 2) => typeof value === 'number' && Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${value.toFixed(digits)}` : 'Not supplied'
const pretty = (value: unknown) => typeof value === 'string' ? value.replaceAll('_', ' ') : 'Not supplied'

/** Renders only the current engine record (frozen v1 output); every number shown is read from the run JSON, nothing is re-estimated. */
export default function ModelOutput({ field, run }: Props) {
  const raw = (field.raw || {}) as Raw
  const closed = raw.verdict?.closed_set || {}
  const open = raw.verdict?.open_set || {}
  const rawDrivers = raw.evidence?.drivers || []
  const probabilities = Object.entries(closed.probabilities || field.probabilities || {}).sort(([a], [b]) => String(a).localeCompare(String(b)))
  const prediction = closed.predicted_batch || field.predictedBatch
  const confidence = closed.confidence ?? (prediction ? field.probabilities?.[prediction] : undefined)
  const tier = closed.tier || field.confidenceTier
  const runnerUp = closed.runner_up || field.runnerUp
  const margin = closed.margin ?? field.margin
  const numbers = closed.justification?.numbers || {}
  const loio = numbers.loio_reliability || field.reliability
  const pipeline = raw.pipeline || run || {}
  const covariates = Object.entries((raw.acquisition?.covariates || {}) as Record<string, Covariate>)
  const acquisitionFlags = covariates.filter(([, value]) => value?.flag)
  const tierReason = numbers.tier_reason
  const validationText = raw.uncertainty?.sampling
  const pValue = numbers.loio_permutation_p
  const interval = parseWilson(validationText)
  const baselineLabel = raw.verdict?.label || field.baseline?.status
  const baselineNumbers = open.justification?.numbers || raw.verdict?.justification?.numbers || {}
  const e1 = baselineNumbers.e1_to_batch3 ?? raw.evidence?.embedding?.energy_distance ?? open.distance_to_each_batch?.Batch_3
  const band95 = open.null_band_95 ?? baselineNumbers.null_band_95
  const band99 = open.null_band_99 ?? baselineNumbers.null_band_99
  const distances = Object.entries(open.distance_to_each_batch || {}).sort(([a], [b]) => String(a).localeCompare(String(b)))
  const closedEvidence: EvidenceItem[] = closed.justification?.evidence || []
  const openEvidence: EvidenceItem[] = open.justification?.evidence || []
  const guidance = makeGuidance({ tier, prediction, confidence, runnerUp, label: baselineLabel, flags: acquisitionFlags.map(([name]) => name), reliability: loio })
  const rawAvailable = Boolean(raw.verdict || field.predictedBatch)

  if (!rawAvailable) return <section className="model-output model-output--empty"><p>The run record did not include model output for this field.</p><small>Prediction, probabilities, uncertainty and traceable evidence are unavailable rather than estimated.</small></section>

  return <div className="model-output">
    {/* 1. The bet */}
    <section className="model-output__hero">
      <div>
        <span className="screening-label">{pipeline.exploratory ? 'Exploratory run · frozen recipe' : pipeline.frozen ? 'Frozen evaluation' : 'Recorded model output'} · image {field.id}</span>
        <h1>{prediction || 'Prediction unavailable'}</h1>
        <p>{plainLead(prediction, confidence, tier, baselineLabel)}</p>
      </div>
      <dl className="model-output__signal">
        <div><dt>Confidence tier</dt><dd className={`tier tier--${String(tier || 'unknown').toLowerCase()}`}>{tier || 'Not supplied'}</dd></div>
        <div><dt>Probability of the bet</dt><dd>{pct(confidence)}</dd></div>
        <div><dt>Runner-up · lead</dt><dd>{runnerUp || 'Not supplied'} · {marginText(margin)}</dd></div>
      </dl>
    </section>
    <p className="model-output__tier-reason"><b>Why this tier:</b> {tierReason || 'Not supplied by this run.'} <span className="muted">Two tiers only: high needs p ≥ 0.75, a validation record better than chance, and an image inside the Batch_3 band; anything else is low.</span></p>

    {/* 2. Probability for each batch */}
    <section className="model-output__section">
      <div className="model-output__heading"><div><h2>Probability for each batch</h2><p>Closed-set: the three probabilities sum to 100 %. They are similarity to the known batches, not defect or failure probabilities.</p></div><span>Sum: <b>{pct(probabilities.reduce((sum, [, p]) => sum + (Number(p) || 0), 0), 0)}</b></span></div>
      {probabilities.length ? <div className="model-probabilities">{probabilities.map(([batch, probability]) => <div className={batch === prediction ? 'model-probability is-selected' : 'model-probability'} key={batch}><div><strong>{batch}</strong>{batch === prediction && <small>Model bet</small>}{batch === runnerUp && <small>Runner-up</small>}</div><i aria-hidden="true"><b style={{ width: `${Math.min(100, Math.max(0, Number(probability) * 100))}%` }} /></i><output>{pct(probability)}</output></div>)}</div> : <p className="model-output__missing">Batch probabilities were not supplied by this run.</p>}
      <EvidenceLine items={closedEvidence} />
    </section>

    {/* 3. Batch_3 baseline check */}
    <section className="model-output__section">
      <div className="model-output__heading"><div><h2>Batch_3 baseline check</h2><p>Independent of the bet: is this image inside the spread of the Batch_3 training images in BSE-embedding space? The flag never replaces the bet; it caps the tier at low when outside.</p></div><span>Status: <b className={`status status--${String(baselineLabel || 'unknown')}`}>{pretty(baselineLabel)}</b></span></div>
      <dl className="model-facts">
        <div><dt>Distance to Batch_3 (E1)</dt><dd>{number(e1, 4)}</dd></div>
        <div><dt>Batch_3 bands · 95 % / 99 %</dt><dd>{number(band95, 4)} / {number(band99, 4)}</dd></div>
        <div><dt>Reading</dt><dd>{typeof e1 === 'number' && typeof band99 === 'number' ? e1 <= (band95 ?? band99) ? 'E1 at or below the 95 % band: inside the Batch_3 spread.' : e1 <= band99 ? 'E1 between the 95 % and 99 % bands: investigate.' : `E1 is ${(e1 - band99).toFixed(4)} above the 99 % band: outside the Batch_3 spread.` : 'Band comparison not supplied.'}</dd></div>
        <div><dt>Rank p (baseline distance only)</dt><dd>{baselineNumbers.rank_p == null ? 'Not supplied' : `${number(baselineNumbers.rank_p, 3)} · minimum ≈ 1/18 with 17 Batch_3 images`}</dd></div>
        <div><dt>Nearest batch by embedding</dt><dd>{open.nearest_batch || 'Not supplied'}</dd></div>
        <div><dt>Distance to each batch</dt><dd>{distances.length ? distances.map(([batch, d]) => `${batch} ${number(d, 3)}`).join(' · ') : 'Not supplied'}</dd></div>
      </dl>
      <EvidenceLine items={openEvidence} />
    </section>

    {/* 4. Validation record behind the confidence */}
    <section className="model-output__section model-output__split">
      <div>
        <div className="model-output__heading"><div><h2>Validation behind this confidence</h2><p>Leave-one-image-out (LOIO) on the 31 training images, computed before this image was seen. These are model-level numbers; there is no per-image confidence interval.</p></div></div>
        <dl className="model-facts">
          <div><dt>Same-bet record ({prediction || 'bet'})</dt><dd>{loio?.correct != null && loio?.total != null ? `${loio.correct}/${loio.total} correct when the model bet ${prediction}` : loio?.pred_batch_correct != null && loio?.pred_batch_n != null ? `${loio.pred_batch_correct}/${loio.pred_batch_n} correct when the model bet ${prediction}` : 'Not supplied'}</dd></div>
          <div><dt>Same bet at tier {tier || '—'}</dt><dd>{loio?.pred_batch_tier_correct != null && loio?.pred_batch_tier_n != null ? loio.pred_batch_tier_n > 0 ? `${loio.pred_batch_tier_correct}/${loio.pred_batch_tier_n} correct` : 'No validation bet of this type at this tier (0 cases)' : 'Not supplied'}</dd></div>
          <div><dt>Overall LOIO accuracy</dt><dd>{numbers.loio_accuracy || 'Not supplied'}</dd></div>
          <div><dt>Wilson 95 % CI (accuracy)</dt><dd>{interval || 'Not supplied in this run'}</dd></div>
          <div><dt>Permutation p-value</dt><dd>{pValue == null ? 'Not supplied' : `${number(pValue, 4)} (vs shuffled labels)`}</dd></div>
          <div><dt>Full accuracy tables</dt><dd><a href="#/accuracy">Model Accuracy tab</a>: confusion matrix, per-batch precision/recall, ROC, tier calibration.</dd></div>
        </dl>
      </div>
      <aside className="model-validation">
        <span className="screening-label">Plain-English guidance</span>
        <h3>What to do with this result</h3>
        <p>{guidance}</p>
        <dl><div><dt>Recorded next step</dt><dd>{raw.next_action || 'Not supplied by this run.'}</dd></div><div><dt>Routed to</dt><dd>{pretty(raw.routing?.stakeholder) } · {raw.routing?.reason || 'Routing reason not supplied.'}</dd></div></dl>
        <small>Built from the recorded tier, baseline status, imaging flags and validation record. It does not change the model’s bet.</small>
      </aside>
    </section>

    {/* 5. Main reasons */}
    <section className="model-output__section">
      <div className="model-output__heading"><div><h2>Main reasons for the bet</h2><p>The three inputs with the largest signed contribution to {prediction || 'the selected batch'} (contribution = standardised input × coefficient). Embedding components carry the Phase B explanation of what they correlate with.</p></div></div>
      {rawDrivers.length ? <div className="model-drivers">{rawDrivers.slice(0, 3).map((driver, index) => <article key={`${driver.name}-${index}`}><span>{String(index + 1).padStart(2, '0')}</span><div><h3>{driverPlainName(driver.name)}</h3><small>{driver.name || 'Signal ID not supplied'} · direction {driver.direction || 'not supplied'}</small><p>{driver.pc_sentence || plainDriverTag(driver)}</p><small>{isEmbedding(driver.name) ? 'Image-pattern component; acquisition and material effects could not be separated in Phase B.' : `Segmentation-derived measurement (${driver.tag || 'status not supplied'}). Review the mask before relying on it.`}</small></div><dl><div><dt>Value</dt><dd>{number(driver.value)}</dd></div><div><dt>Coefficient</dt><dd>{signed(driver.coefficient)}</dd></div><div><dt>Contribution</dt><dd>{signed(driver.effect_size)}</dd></div></dl></article>)}</div> : <p className="model-output__missing">No driver list was supplied by this run.</p>}
      <EvidenceLine items={rawDrivers.slice(0, 3).flatMap((driver) => driver.justification?.evidence || [])} />
    </section>

    {/* 6. Imaging covariates */}
    <section className="model-output__section">
      <div className="model-output__heading"><div><h2>Imaging conditions vs the training images</h2><p>Reported only, not model inputs. A covariate is flagged when it falls strictly outside the 5th–95th percentile of the 31 training images; flagged imaging means the batch match may reflect the microscope rather than the material.</p></div><span>Flags: <b>{raw.acquisition ? acquisitionFlags.length : '—'}</b></span></div>
      {covariates.length ? <table className="model-covariates"><thead><tr><th>Covariate</th><th>This image</th><th>Training 5–95 %</th><th>Status</th></tr></thead><tbody>{covariates.map(([name, c]) => <tr key={name} className={c?.flag ? 'is-flagged' : ''}><td>{name.replaceAll('_', ' ')}</td><td>{number(c?.value, 3)}</td><td>{number(c?.training_p05, 3)} – {number(c?.training_p95, 3)}</td><td>{c?.flag ? 'Outside training range' : 'Within range'}</td></tr>)}</tbody></table> : <p className="model-output__missing">Acquisition covariates were not supplied by this run.</p>}
      <p className="model-output__note">Pixel size {raw.acquisition?.pixel_size_confirmed ? `${raw.acquisition.pixel_size_nm} nm (confirmed)` : 'unconfirmed; all lengths in px'} · detectors {raw.acquisition?.detectors_present?.join(', ') || 'not supplied'}.</p>
    </section>

    {/* 7. Record */}
    <details className="model-output__trace"><summary>Provenance, model rule, caveats and evidence files</summary><div><p><b>Recipe:</b> {pipeline.git_tag || pipeline.git_sha || 'Not supplied'} · config {pipeline.config_hash || 'Not supplied'} · {pipeline.exploratory ? 'Exploratory run' : pipeline.frozen ? 'Frozen run' : 'Run status not supplied'}.</p><p><b>Native explanation:</b> {raw.verdict?.reason || 'Not supplied by this run.'}</p><p><b>Model rule:</b> {closed.justification?.rule || 'Not supplied by this run.'}</p><p><b>Baseline rule:</b> {open.justification?.rule || raw.verdict?.rule || 'Not supplied by this run.'}</p>{raw.uncertainty && <p><b>Uncertainty:</b> {Object.entries(raw.uncertainty).map(([k, v]) => `${k}: ${v}`).join(' · ')}</p>}{raw.caveats?.length ? <ul>{raw.caveats.map((caveat, index) => <li key={index}>{caveat}</li>)}</ul> : <p>No caveats were supplied by this run.</p>}<EvidenceList items={[...closedEvidence, ...openEvidence]} /><p className="model-output__note">The 95 % confidence interval and permutation p-value describe validation across the training images. They do not quantify uncertainty or defect risk for this individual image.</p></div></details>
    <MetricGlossary />
  </div>
}

function plainLead(prediction: unknown, confidence: unknown, tier: unknown, baseline: unknown) {
  const name = typeof prediction === 'string' ? prediction : 'a known batch'
  const level = typeof tier === 'string' ? tier.toLowerCase() : 'recorded'
  const reference = baseline === 'outside_bounds' ? ' It is outside the Batch_3 baseline band.' : baseline === 'investigate' ? ' Its Batch_3 baseline comparison needs review.' : baseline === 'within_bounds' ? ' It is inside the Batch_3 baseline band.' : ''
  return `The model bets ${name} with probability ${pct(confidence)} at ${level} confidence.${reference} The probability is the model’s preference among the three known batches, not a calibrated chance of being correct.`
}

function makeGuidance({ tier, prediction, confidence, runnerUp, label, flags, reliability }: any) {
  const record = reliability?.pred_batch_correct != null && reliability?.pred_batch_n != null ? `${reliability.pred_batch_correct}/${reliability.pred_batch_n}` : reliability?.correct != null && reliability?.total != null ? `${reliability.correct}/${reliability.total}` : 'not supplied'
  if (flags.length) return `Imaging differs from the training images (${flags.join(', ')}); re-image or confirm microscope settings before interpreting the batch match.`
  if (tier === 'low' && label === 'outside_bounds' && prediction !== 'Batch_3') return `Probably not Batch_3: the image is outside the Batch_3 band (14/16 precision for that separation in validation). ${prediction} versus ${runnerUp || 'the runner-up'} is provisional: bets on ${prediction} were right ${record} times in validation. Image more sections and compare the 11 measurements with the Batch_1 and Batch_2 ranges.`
  if (tier === 'low' && label === 'outside_bounds') return 'Unusual image: the model bets Batch_3 but the image is outside the Batch_3 band. Check imaging first; if clear, send for materials review as a possible new variation.'
  if (tier === 'low' && typeof confidence === 'number' && confidence < .5) return `No batch is strongly favoured (best match ${pct(confidence)}). Treat as undecided, image more sections, and review ${runnerUp || 'the runner-up'} as an alternative.`
  if (tier === 'low') return `Low confidence in ${prediction || 'the selected batch'} (bets on it were right ${record} times in validation). Treat the identity as provisional and compare more sections before acting.`
  if (tier === 'high' && (prediction === 'Batch_1' || prediction === 'Batch_2')) return `High tier for ${prediction}, but Batch_1 and Batch_2 identities should stay provisional (right ${record} times in validation). Use it as a prompt to compare more sections and the recorded measurements, not as a quality verdict.`
  return `High confidence that this image matches ${prediction || 'the known batch'} (bets on it were right ${record} times in validation). Review the baseline and imaging checks alongside the image before drawing a material conclusion.`
}

function isEmbedding(name?: string) { return /embedding\s*pc/i.test(name || '') }
function driverPlainName(name?: string) {
  if (isEmbedding(name)) return `Image-pattern component ${(name || '').replace(/\D+/g, '') || ''}`.trim()
  const names: Record<string, string> = {F01:'Dark-area share (void fraction)', F02:'Bright-area share (silicon fraction)', F03:'Typical bright-object size', F04:'Bright-object size at the 90th percentile', F05:'Bright-object count per image area', F06:'Bright-object spacing (clustering)', F07:'Bright-object outline fullness', F08:'Typical dark-region width', F09:'Horizontal versus vertical dark-region spans', F10:'Variation in dark-area share', F11:'Bright-object boundary touching dark regions'}
  const id = (name || '').match(/F(?:0[1-9]|1[01])/i)?.[0]?.toUpperCase()
  return id ? `${metricLabel(id)} (${metricTechnicalName(id)})` : names[(name || '').slice(0,3)] || 'Segmentation-derived measurement'
}
function plainDriverTag(driver: RawDriver) {
  if (isEmbedding(driver.name)) return 'This image pattern helped the model match the field to a known batch. Acquisition and material effects could not be separated.'
  return 'This measured image feature supported the selected batch match.'
}
function uniqueEvidence(items: EvidenceItem[]) {
  return items.filter((item, index) => item?.file && items.findIndex((other) => other?.file === item.file && other?.selector === item.selector) === index)
}
function EvidenceLine({ items }: { items: EvidenceItem[] }) {
  const unique = uniqueEvidence(items)
  return unique.length ? <p className="model-output__evidence"><b>Evidence:</b> {unique.slice(0, 3).map((item, index) => <span key={`${item.file}-${index}`}><code>{item.file}</code>{item.selector ? ` · ${item.selector}` : ''}</span>)}</p> : null
}
function EvidenceList({ items }: { items: EvidenceItem[] }) {
  const unique = uniqueEvidence(items)
  return unique.length ? <div className="model-evidence"><b>Evidence record</b><ul>{unique.map((item, index) => <li key={`${item.file}-${index}`}><code>{item.file}</code>{item.selector ? ` · ${item.selector}` : ''}</li>)}</ul></div> : <p>Evidence file and selector were not supplied by this run.</p>
}

function parseWilson(value?: string) {
  if (!value) return undefined
  const match = value.match(/(?:Wilson\s+)?95\s*%\s*CI\s*[(:]?\s*([0-9.]+)\s*[-–,]\s*([0-9.]+)/i)
  return match ? `${(Number(match[1]) * 100).toFixed(0)}%–${(Number(match[2]) * 100).toFixed(0)}%` : undefined
}

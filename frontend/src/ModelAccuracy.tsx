import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowLeft, CheckCircle2, CircleHelp, Database, FlaskConical, RefreshCw } from 'lucide-react'
import './ModelAccuracy.css'
import './ModelAccuracy.figures.css'

type Ratio = { label: string; correct: number; total: number }
type AccuracyData = {
  release: { model_version: string; git_sha?: string; config_hash?: string; evaluation: string }
  loio: { n_images: number; correct: number; accuracy: number; accuracy_label: string; wilson95: [number, number]; majority_baseline: Ratio; balanced_accuracy?: number; permutation: { p: number; n?: number; seed?: number }; confusion: { rows_true_cols_pred: string[]; values: number[][] }; per_batch_recall: Record<string, Ratio>; precision_by_pred_batch: Record<string, Ratio>; accuracy_by_tier: Record<string, Ratio> }
  heldout: { status: string; correct: number | null; total: number | null; confidence_scoring_correct: number | null; confidence_scoring_total: number | null; label: string; source: string; verification: string; confidence_scoring_rubric: string }
  exploratory_six_image_run?: { status: string; n_predictions?: number; note: string }
  figures?: Record<string, string>
  missing: string[]
  provenance: { sources: { path: string; sha256: string }[]; rendering: string }
}

const percentage = (correct: number, total: number) => total ? Math.round((correct / total) * 100) : 0
const label = (name: string) => name.replace('Batch_', 'Batch ').replace(/^./, (value) => value.toUpperCase())

export default function ModelAccuracy({ onBack }: { onBack?: () => void }) {
  const [data, setData] = useState<AccuracyData | null>(null)
  const [error, setError] = useState('')
  const load = () => {
    setError('')
    fetch('/api/model-accuracy').then(async response => {
      if (!response.ok) throw new Error('The saved model-card data is unavailable.')
      return response.json()
    }).then(setData).catch(problem => setError(problem.message || 'The saved model-card data is unavailable.'))
  }
  useEffect(load, [])
  if (error) return <section className="model-accuracy"><div className="accuracy-empty"><AlertTriangle size={26}/><h1>Model accuracy is unavailable</h1><p>{error}</p><button onClick={load}><RefreshCw size={16}/> Retry</button></div></section>
  if (!data) return <section className="model-accuracy"><div className="accuracy-empty"><RefreshCw className="spin" size={24}/><p>Opening the saved model card…</p></div></section>
  const { loio } = data
  return <section className="model-accuracy">
    <header className="accuracy-header">
      <div>{onBack && <button className="accuracy-back" onClick={onBack}><ArrowLeft size={16}/> Current results</button>}<span className="accuracy-eyebrow">Fixed model card · v1-frozen</span><h1>Model accuracy</h1><p>{data.release.evaluation}</p></div>
      <div className="accuracy-release"><span>Recipe locked</span><small>{data.release.git_sha || 'SHA unavailable'} · {data.release.config_hash || 'config unavailable'}</small></div>
    </header>

    <section className="accuracy-warning" role="note"><CircleHelp size={19}/><p><strong>Read this first.</strong> These are batch-match validation results, not a defect probability, lot-release decision, or guarantee on new material.</p></section>

    <section className="accuracy-kpis" aria-label="Core validation metrics">
      <Metric title="LOIO accuracy" value={`${(loio.accuracy * 100).toFixed(1)}%`} note={`${loio.accuracy_label} · 95% Wilson ${(loio.wilson95[0] * 100).toFixed(0)}–${(loio.wilson95[1] * 100).toFixed(0)}%`} />
      <Metric title="Majority reference" value={loio.majority_baseline.label} note="Always predict Batch 3" />
      <Metric title="Permutation p-value" value={`p = ${loio.permutation.p.toFixed(3)}`} note={`${loio.permutation.n || '—'} fixed permutations`} />
      <Metric title="Balanced accuracy" value={loio.balanced_accuracy == null ? '—' : `${(loio.balanced_accuracy * 100).toFixed(1)}%`} note={`${loio.n_images} images · tiles not independent`} />
    </section>

    <section className="accuracy-grid">
      <article className="accuracy-card confusion-card"><header><div><span className="card-kicker">Classification record</span><h2>Where the model was right</h2></div><small>Rendered from saved results</small></header><p>Rows are the recorded batch. Columns are the model’s predicted batch.</p><div className="confusion-wrap"><table><thead><tr><th scope="col">Actual ↓ / predicted →</th>{loio.confusion.rows_true_cols_pred.map(batch => <th scope="col" key={batch}>{label(batch)}</th>)}</tr></thead><tbody>{loio.confusion.values.map((row, index) => <tr key={loio.confusion.rows_true_cols_pred[index]}><th scope="row">{label(loio.confusion.rows_true_cols_pred[index])}</th>{row.map((value, column) => <td className={index === column ? 'correct-cell' : ''} key={column}>{value}</td>)}</tr>)}</tbody></table></div><p className="chart-caption">Batch 1 and Batch 2 are often confused in this saved validation set.</p></article>

      <article className="accuracy-card"><header><div><span className="card-kicker">Reliability by prediction</span><h2>Batch-match track record</h2></div><small>LOIO only</small></header><BarRows values={loio.precision_by_pred_batch} /><p className="chart-caption">“Batch 3” predictions were correct more often than Batch 1 or Batch 2 predictions in this data.</p></article>

      <article className="accuracy-card"><header><div><span className="card-kicker">Reliability by tier</span><h2>Confidence tier track record</h2></div><small>LOIO only</small></header><BarRows values={loio.accuracy_by_tier} /><p className="chart-caption">A tier is a rule-based model label. It is not a calibrated failure likelihood.</p></article>

      <article className="accuracy-card heldout-card"><header><div><span className="card-kicker">Held-out record</span><h2>Reported separately</h2></div><small>Exploratory</small></header><div className="heldout-score"><strong>{data.heldout.correct == null ? '—' : `${data.heldout.correct}/${data.heldout.total}`}</strong><span>{data.heldout.status === 'not_available' ? 'record unavailable' : 'documented correct'}</span></div><p>{data.heldout.verification}</p><dl><div><dt>Auxiliary confidence score</dt><dd>{data.heldout.confidence_scoring_correct == null ? 'Unavailable' : `${data.heldout.confidence_scoring_correct}/${data.heldout.confidence_scoring_total}`}</dd></div><div><dt>Scoring rule</dt><dd>{data.heldout.confidence_scoring_rubric}</dd></div>{data.exploratory_six_image_run && <div><dt>Six-image exploratory run</dt><dd>{data.exploratory_six_image_run.note}</dd></div>}</dl></article>
    </section>

    {data.figures && <section className="saved-figures" aria-label="Saved validation figures"><div className="saved-figures__heading"><div><span className="card-kicker">Committed analysis figures</span><h2>Validation detail</h2></div><p>Saved model-trainer figures. They report the fixed v1 validation, without rerunning the model.</p></div><div className="saved-figures__grid">{[
      ['accuracy_vs_baselines', 'Accuracy and references'], ['by_tier', 'Tier accuracy in this saved validation; not proof of calibrated probabilities (gap 0.216)'], ['confusion_matrix', 'Confusion matrix'], ['per_batch', 'Batch precision and recall'], ['roc', 'One-vs-rest ROC curves'],
    ].map(([id, title]) => <figure key={id}>{data.figures?.[id] ? <img src={data.figures[id]} loading="lazy" decoding="async" alt={`${title}; saved model accuracy figure`} /> : <div className="saved-figure-missing">This saved figure is unavailable.</div>}<figcaption>{title}<span>Saved result</span></figcaption></figure>)}</div></section>}

    <section className="accuracy-card limitations-card"><header><div><span className="card-kicker">What is missing</span><h2>Limits of this evidence</h2></div><AlertTriangle size={19}/></header><ul>{data.missing.map(item => <li key={item}>{item}</li>)}</ul></section>

    <details className="accuracy-provenance"><summary><Database size={16}/> Sources and provenance</summary><p>{data.provenance.rendering}</p><ul>{data.provenance.sources.map(source => <li key={source.path}><code>{source.path}</code><span>{source.sha256}</span></li>)}</ul></details>
  </section>
}

function Metric({ title, value, note }: { title: string; value: string; note: string }) { return <article className="metric"><span>{title}</span><strong>{value}</strong><small>{note}</small></article> }
function BarRows({ values }: { values: Record<string, Ratio> }) { return <div className="accuracy-bars">{Object.entries(values).map(([name, value]) => <div className="accuracy-bar" key={name}><div><span>{label(name)}</span><strong>{value.label}</strong></div><i aria-label={`${label(name)}: ${value.label}`}><b style={{ width: `${percentage(value.correct, value.total)}%` }} /></i></div>)}</div> }

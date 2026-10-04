import { metricDefinitions } from './metricLanguage'
import './MetricGlossary.css'

export default function MetricGlossary() {
  return <details className="metric-glossary">
    <summary>Measurement guide <span>Plain labels with technical definitions</span></summary>
    <p className="metric-glossary__intro">These 11 image measurements describe a segmented 2D field. They are evidence for review, not material quality measurements or diagnoses.</p>
    <div className="metric-glossary__list">
      {Object.values(metricDefinitions).map(metric => <article key={metric.id}>
        <div><code>{metric.id}</code><h3>{metric.label}</h3></div>
        <p>{metric.meaning}</p>
        <small><b>{metric.technical}</b> · {metric.unit}{metric.caveat ? ` · ${metric.caveat}` : ''}</small>
      </article>)}
    </div>
    <p className="metric-glossary__caveat">Phase identities are stated by Polaron and not image-verified: class 2 is bright/silicon, class 1 is mid-tone/graphite, and class 0 is dark/void or pore. BSE cannot distinguish Si from SiOx; binder and conductive additive are grouped with classes 0 or 1.</p>
  </details>
}

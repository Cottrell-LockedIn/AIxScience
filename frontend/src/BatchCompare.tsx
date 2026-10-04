import { useEffect, useState } from "react";
import "./BatchCompare.css";

type Layer = { id: string; label: string; legend: [string, string][] };
type Reference = { id: string; batch: string; compareUrl: string; available: boolean };
type Range = { min: number; median: number; max: number; n: number };
type References = {
  selectionRule?: string;
  segmentation?: string;
  layers: Layer[];
  colors: Record<string, number[]>;
  zoomPx: number;
  references: Reference[];
  trainingRanges: Record<string, Record<string, Range>>;
  phaseIdentity: string;
};
type Stats = {
  poreFraction: number;
  graphiteFraction: number;
  siliconFraction: number;
  crackLikeFractionOfVoid: number;
  maskWidth: number;
  maskHeight: number;
};

export type BatchCompareProps = {
  fieldId: string;
  /** `/api/compare/<scope>/<id>[?run_id=…]`; absent when this record has no verified mask. */
  compareUrl?: string;
  batchLabel?: string;
};

const BATCH_CLASS: Record<string, string> = { Batch_1: "b1", Batch_2: "b2", Batch_3: "b3" };
const pct = (value?: number) => (typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)} %` : "—");
const batchName = (batch?: string) => (batch ? batch.replace("_", " ") : "—");

function imageUrl(base: string, layer: string, zoom: number) {
  const [path, query] = base.split("?");
  const params = new URLSearchParams(query || "");
  params.set("layer", layer);
  params.set("zoom", String(zoom));
  return `${path}/image?${params.toString()}`;
}

function useStats(url?: string) {
  const [stats, setStats] = useState<Stats | null>(null);
  useEffect(() => {
    setStats(null);
    if (!url) return;
    const controller = new AbortController();
    fetch(url, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => setStats(data))
      .catch(() => setStats(null));
    return () => controller.abort();
  }, [url]);
  return stats;
}

function Panel({ title, subtitle, batch, base, layer, zoom, unavailable }: {
  title: string; subtitle: string; batch?: string; base?: string; layer: string; zoom: number; unavailable?: string;
}) {
  const stats = useStats(base);
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [base, layer, zoom]);
  return (
    <figure className={`batch-compare__panel ${zoom ? "is-zoomed" : ""}`}>
      {base && !failed ? (
        <img src={imageUrl(base, layer, zoom)} alt={`${title}: ${layer} layer`} onError={() => setFailed(true)} loading="lazy" />
      ) : (
        <div className="batch-compare__missing">{unavailable || "Image or verified mask not available on this machine."}</div>
      )}
      <figcaption>
        <strong className={batch ? `batch-compare__batch ${BATCH_CLASS[batch] || ""}` : ""}>{title}</strong> <span>{subtitle}</span>
        {stats && (
          <small>
            pore {pct(stats.poreFraction)} · graphite {pct(stats.graphiteFraction)} · silicon {pct(stats.siliconFraction)} · crack-like {pct(stats.crackLikeFractionOfVoid)} of void
          </small>
        )}
      </figcaption>
    </figure>
  );
}

/** This image beside one representative training image per batch, same mask-derived layer on each. */
export default function BatchCompare({ fieldId, compareUrl, batchLabel }: BatchCompareProps) {
  const [refs, setRefs] = useState<References | null>(null);
  const [layer, setLayer] = useState("phases");
  const [zoom, setZoom] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/compare/references")
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(String(response.status)))))
      .then((data: References) => setRefs(data))
      .catch(() => setError("Comparison references are unavailable from the API."));
  }, []);

  const layers = refs?.layers || [];
  const current = layers.find((item) => item.id === layer);
  const zoomPx = refs?.zoomPx || 600;
  const ranges = refs?.trainingRanges || {};

  return (
    <div className="batch-compare" aria-label={`Compare ${fieldId} with each batch`}>
      <div className="batch-compare__controls" role="tablist" aria-label="Comparison layer">
        {layers.map((item) => (
          <button key={item.id} type="button" role="tab" aria-selected={item.id === layer} className={item.id === layer ? "is-active" : ""} onClick={() => setLayer(item.id)}>
            {item.label}
          </button>
        ))}
        <label className="batch-compare__zoom">
          <input type="checkbox" checked={zoom} onChange={(event) => setZoom(event.target.checked)} /> zoom ({zoomPx} px window with the most pore + silicon area, full resolution)
        </label>
      </div>
      {current && current.legend.length > 0 && (
        <ul className="batch-compare__legend">
          {current.legend.map(([color, text]) => (
            <li key={color}><i style={{ background: `rgb(${(refs?.colors[color] || [128, 128, 128]).join(",")})` }} />{text}</li>
          ))}
        </ul>
      )}
      {error && <p className="batch-compare__note">{error}</p>}
      <div className="batch-compare__grid">
        <Panel
          title="This image"
          subtitle={batchLabel ? `→ bet ${batchName(batchLabel)} · ${fieldId}` : fieldId}
          base={compareUrl}
          layer={layer}
          zoom={zoom ? zoomPx : 0}
          unavailable="Original TIFF or verified mask not present on this machine, so no layer can be drawn."
        />
        {(refs?.references || []).map((reference) => (
          <Panel
            key={reference.id}
            title={`${batchName(reference.batch)} representative`}
            subtitle={`img_${reference.id}`}
            batch={reference.batch}
            base={reference.available ? reference.compareUrl : undefined}
            layer={layer}
            zoom={zoom ? zoomPx : 0}
            unavailable="Training TIFF not present on this machine."
          />
        ))}
      </div>
      {Object.keys(ranges).length > 0 && (
        <table className="batch-compare__ranges" aria-label="Training ranges per batch">
          <thead><tr><th>Training range (min · median · max)</th><th>Pore</th><th>Silicon</th><th>Crack-like of void</th></tr></thead>
          <tbody>
            {Object.entries(ranges).map(([batch, row]) => (
              <tr key={batch}>
                <th className={`batch-compare__batch ${BATCH_CLASS[batch] || ""}`}>{batchName(batch)} (n = {row.poreFraction?.n})</th>
                {(["poreFraction", "siliconFraction", "crackLikeFractionOfVoid"] as const).map((key) => (
                  <td key={key}>{row[key] ? `${pct(row[key].min)} · ${pct(row[key].median)} · ${pct(row[key].max)}` : "—"}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="batch-compare__notes">
        <p>Phase identity: {refs?.phaseIdentity || "stated by Polaron, not image-verified"}. Si vs SiOx indistinguishable in BSE; binder and conductive additive are lumped into the dark/mid classes.</p>
        <p>Representative = training image nearest its batch centre in the model's input space. Layers are drawn from the one fixed-threshold mask the measurements came from; it is evidence of what was measured, not ground truth. "Crack-like" is an image-morphology label (thin void component), not a verified crack.</p>
      </div>
    </div>
  );
}

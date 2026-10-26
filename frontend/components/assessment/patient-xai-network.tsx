"use client";
import { useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { FEATURE_LABELS, formatFeatureValue } from "@/lib/utils";
import type { PatientInput, PredictionResponse } from "@/lib/types";

const WIDTH = 760, HEIGHT = 520, NODE_RADIUS = 197;
const cx = 380, cy = 260;

export function PatientXaiNetwork({ result, patient }: { result: PredictionResponse; patient: PatientInput }) {
  const factors = useMemo(() => result.shap_values.slice(0, 8), [result.shap_values]);
  const [selectedFeature, setSelectedFeature] = useState<string | null>(null);
  const selected = factors.find(factor => factor.feature === selectedFeature) || factors[0];
  if (!factors.length) return <Card><h3 className="card-title">Patient-specific contribution graph</h3><div className="alert alert-info" role="status">This assessment does not include explanation values, so its graph cannot be displayed.</div></Card>;
  const points = factors.map((factor, index) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * index / factors.length);
    return { factor, x: cx + NODE_RADIUS * Math.cos(angle), y: cy + NODE_RADIUS * Math.sin(angle) };
  });
  const nodeColor = (contribution: number) => contribution > 0 ? "var(--risk-high)" : contribution < 0 ? "var(--risk-low)" : "var(--gray-500)";

  return <Card className="patient-network-card">
    <div className="patient-network-heading"><div><h3 className="card-title">Patient-specific contribution graph</h3><p className="card-description">Connected features are the largest SHAP contributions for this assessment. Values are on the hybrid model’s probability scale; +0.010 represents about +1 percentage point of model output.</p></div><span className="patient-network-badge">Individual assessment</span></div>
    <div className="patient-network-layout">
      <div className="patient-network-visual">
        <svg className="patient-network-svg" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="group" aria-label="Interactive graph of this assessment's model probability and its top eight feature contributions">
          <title>Patient-specific SHAP contributions</title>
          <desc>The central node is the model probability. Each connected feature node shows an entered value. Signed edge labels are SHAP contributions, not causal effects.</desc>
          {points.map(({ factor, x, y }) => {
            const color = nodeColor(factor.contribution);
            const midX = (x + cx) / 2, midY = (y + cy) / 2;
            const label = FEATURE_LABELS[factor.feature] || factor.feature;
            const active = selected?.feature === factor.feature;
            return <g key={factor.feature} className={`patient-network-node ${active ? "is-selected" : ""}`} tabIndex={0} role="button" aria-pressed={active} aria-label={`${label}, entered ${formatFeatureValue(factor.feature, patient[factor.feature] as number)}, SHAP contribution ${factor.contribution > 0 ? "plus " : ""}${factor.contribution.toFixed(5)}; ${factor.contribution > 0 ? "raises" : factor.contribution < 0 ? "lowers" : "does not change"} model output`} onClick={() => setSelectedFeature(factor.feature)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedFeature(factor.feature); } }}>
              <line x1={x} y1={y} x2={cx} y2={cy} stroke={color} strokeWidth={active ? 2.4 : 1.5} opacity={active ? .82 : .48}/>
              <rect x={midX - 29} y={midY - 11} width="58" height="22" rx="7" className="patient-network-edge-label" stroke={color}/>
              <text x={midX} y={midY + 4} textAnchor="middle" className="patient-network-edge-text" fill={color}>{factor.contribution > 0 ? "+" : ""}{factor.contribution.toFixed(3)}</text>
              <rect className="patient-network-node-box" x={x - 66} y={y - 35} width="132" height="70" rx="14" stroke={color}/>
              <text x={x} y={y - 7} textAnchor="middle" className="patient-network-feature">{label}</text>
              <text x={x} y={y + 15} textAnchor="middle" className="patient-network-value">{formatFeatureValue(factor.feature, patient[factor.feature] as number)}</text>
            </g>;
          })}
          <circle cx={cx} cy={cy} r="68" className="patient-network-center"/>
          <text x={cx} y={cy - 8} textAnchor="middle" className="patient-network-center-label">MODEL OUTPUT</text>
          <text x={cx} y={cy + 20} textAnchor="middle" className="patient-network-center-value">{(result.probability * 100).toFixed(1)}%</text>
        </svg>
        <div className="patient-network-legend" aria-label="Graph legend"><span><i className="patient-network-positive"/> Raises model output</span><span><i className="patient-network-negative"/> Lowers model output</span><span>Center: predicted probability</span></div>
      </div>
      <aside className="patient-network-detail" aria-live="polite">
        <label htmlFor="patient-network-select">Inspect a feature</label>
        <select id="patient-network-select" className="select" value={selected?.feature || ""} onChange={event => setSelectedFeature(event.target.value)}>
          {factors.map(factor => <option key={factor.feature} value={factor.feature}>{FEATURE_LABELS[factor.feature] || factor.feature}</option>)}
        </select>
        {selected && <><h4>{FEATURE_LABELS[selected.feature] || selected.feature}</h4><dl className="patient-network-stats"><div><dt>Entered value</dt><dd>{formatFeatureValue(selected.feature, patient[selected.feature] as number)}</dd></div><div><dt>SHAP contribution</dt><dd className={selected.contribution > 0 ? "patient-network-up" : selected.contribution < 0 ? "patient-network-down" : ""}>{selected.contribution > 0 ? "+" : ""}{selected.contribution.toFixed(5)}</dd></div><div><dt>Model effect</dt><dd>{selected.contribution > 0 ? "Raises output" : selected.contribution < 0 ? "Lowers output" : "Neutral"}</dd></div></dl></>}
        <p>Only features with SHAP values are connected. The probability-space values come from a finite-evaluation permutation SHAP explanation, so small approximation differences can occur. Signed values show how the model output moves for this record.</p>
      </aside>
    </div>
    <p className="patient-network-note">This is an individual prediction explanation. It is not the dataset-level Risk Factor Network and does not show correlations or prove medical causation.</p>
  </Card>;
}

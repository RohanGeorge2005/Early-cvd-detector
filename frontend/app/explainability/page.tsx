"use client";
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, ScanEye, Sparkles } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAssessment } from "@/components/providers";
import { Card } from "@/components/ui/card";
import { LocalWaterfall, ShapDistribution } from "@/components/xai/shap-visuals";
import { FEATURE_LABELS, formatFeatureValue } from "@/lib/utils";
import type { GlobalXAI } from "@/lib/types";

export default function ExplainabilityPage() {
  const [global, setGlobal] = useState<GlobalXAI | null>(null);
  const [error, setError] = useState("");
  const [view, setView] = useState<"simple" | "technical">("simple");
  const [scope, setScope] = useState<"global" | "patient">("global");
  const { patient, result } = useAssessment();
  useEffect(() => {
    api.globalXai().then(setGlobal).catch((e) => setError(e instanceof ApiError ? e.message : "Global explanation unavailable."));
  }, []);
  const max = Math.max(...(global?.feature_importance.map((f) => f.importance) || [1]), 1e-9);
  const shapMax = Math.max(...(result?.shap_values.map((f) => Math.abs(f.contribution)) || [1]), 1e-9);

  return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <div className="page-heading">
      <div className="eyebrow"><ScanEye size={14} /> Model interpretation</div>
      <h1 className="page-title">Explainability</h1>
      <p className="page-subtitle">See which inputs influenced the model across the dataset or in a single assessment. Contributions describe model behavior; they do not establish cause and effect.</p>
    </div>

    <div className="scope-tabs" role="tablist" aria-label="Explanation scope">
      <button id="tab-global" role="tab" aria-controls="panel-global" aria-selected={scope === "global"} className={scope === "global" ? "scope-tab active" : "scope-tab"} onClick={() => setScope("global")}>Across the dataset</button>
      <button id="tab-patient" role="tab" aria-controls="panel-patient" aria-selected={scope === "patient"} className={scope === "patient" ? "scope-tab active" : "scope-tab"} onClick={() => setScope("patient")}>This assessment</button>
    </div>

    {scope === "global" && <section id="panel-global" role="tabpanel" aria-labelledby="tab-global">
    <div className="section-heading"><div><h2>Global feature importance</h2><p>Mean absolute SHAP contribution across sampled training records.</p></div><span className="badge">Global SHAP</span></div>
    {global ? <>
      <Card>
        <div className="explain-bars">{global.feature_importance.map((f) => <div className="explain-row" key={f.feature}>
          <span className="explain-feature">{FEATURE_LABELS[f.feature.replace(/^numeric__|^categorical__/g, "")] || f.feature}</span>
          <div className="prob-track"><div className="prob-fill" style={{ width: `${Math.max(1, f.importance / max * 100)}%` }} /></div>
          <span className="explain-value">{f.importance.toFixed(4)}</span>
        </div>)}</div>
        <p className="card-description" style={{ marginTop: 14 }}>{global.causation_note || "Importance describes model contributions and is not evidence of causality."}{global.method ? ` · Method: ${global.method}.` : ""}</p>
      </Card>
      {!!global.feature_distributions?.length && <div style={{ marginTop: 13 }}><ShapDistribution global={global} /></div>}
    </> : <Card className="empty-state"><div className="empty-icon"><Sparkles size={20} /></div><h3>Global SHAP values unavailable</h3><p>{error || "Loading the trained model explanation…"} No example feature rankings are substituted.</p></Card>}
    </section>}

    {scope === "patient" && <section id="panel-patient" role="tabpanel" aria-labelledby="tab-patient">
    <div className="section-heading">
      <div><h2>Contributors to this assessment</h2><p>Positive contributions raise the model output; negative contributions lower it.</p></div>
      <div style={{ display: "flex", gap: 5 }}>
        <button className={`button ${view === "simple" ? "button-primary" : "button-ghost"}`} aria-pressed={view === "simple"} onClick={() => setView("simple")}>Simple</button>
        <button className={`button ${view === "technical" ? "button-primary" : "button-ghost"}`} aria-pressed={view === "technical"} onClick={() => setView("technical")}>Technical</button>
      </div>
    </div>
    {result && patient ? <>
      <LocalWaterfall result={result} patient={patient} />
      <div className="grid-2" style={{ marginTop: 13 }}>
        <Card>
          <h3 className="card-title">Contribution direction</h3><p className="card-description">SHAP contributions to the final hybrid model output.</p>
          <div className="explain-bars" style={{ marginTop: 16 }}>{result.shap_values.map((f) => {
            const positive = f.contribution >= 0; const width = Math.abs(f.contribution) / shapMax * 49;
            return <div className="explain-row" key={f.feature}>
              <span className="explain-feature">{FEATURE_LABELS[f.feature] || f.feature}</span>
              <div className="explain-track"><i className="explain-bar" style={{ left: positive ? "50%" : `calc(50% - ${width}%)`, width: `${width}%`, "--bar-color": positive ? "var(--coral)" : "var(--green)" } as CSSProperties} /></div>
              <span className="explain-value">{f.contribution > 0 ? "+" : ""}{f.contribution.toFixed(4)}</span>
            </div>;
          })}</div>
        </Card>
        <Card>
          <h3 className="card-title">{view === "simple" ? "Plain-language view" : "Technical SHAP values"}</h3>
          <p className="card-description">This assessment: {(result.probability * 100).toFixed(1)}% model probability · {result.risk_category} model-based category.</p>
          {view === "simple" ? <div className="contribution-list" style={{ marginTop: 14 }}>{result.shap_values.slice(0, 7).map((f) => <div className="contribution-row" key={f.feature}>
            {f.contribution >= 0 ? <ArrowUpRight className="up" size={14} /> : <ArrowDownRight className="down" size={14} />}
            <span>{FEATURE_LABELS[f.feature] || f.feature}</span><small>{formatFeatureValue(f.feature, patient[f.feature])} · {f.direction}</small>
          </div>)}</div> : <div className="table-wrap" style={{ marginTop: 13 }}><table className="data-table"><thead><tr><th>Feature</th><th>Value</th><th>SHAP</th><th>Direction</th></tr></thead><tbody>{result.shap_values.map((f) => <tr key={f.feature}>
            <td>{FEATURE_LABELS[f.feature] || f.feature}</td><td>{formatFeatureValue(f.feature, patient[f.feature])}</td><td>{f.contribution > 0 ? "+" : ""}{f.contribution.toFixed(6)}</td><td>{f.direction}</td>
          </tr>)}</tbody></table></div>}
        </Card>
      </div>
    </> : <Card className="empty-state"><div className="empty-icon"><Sparkles size={20} /></div><h3>No patient explanation in this session</h3><p>Complete a risk assessment to view patient-specific hybrid SHAP contributions. The app does not generate a sample explanation.</p></Card>}
    <div className="help-reading"><strong>How to read this</strong><p>The bars show each feature’s contribution relative to the model baseline. The displayed direction describes how the model responded to these inputs; changing a value does not guarantee a change in health outcome.</p></div>
    </section>}
    <div className="alert alert-info">A feature contribution can reflect associations learned from training data. It should not be interpreted as the effect of changing that feature.</div>
  </motion.div>;
}

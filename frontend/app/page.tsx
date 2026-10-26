"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Clock3, Database, FileText, Plus, ShieldCheck } from "lucide-react";
import { useAssessment } from "@/components/providers";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { DatasetAudit, PerformanceResponse } from "@/lib/types";

function displayDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function Dashboard() {
  const { assessments } = useAssessment();
  const [modelReady, setModelReady] = useState<boolean | null>(null);
  const [audit, setAudit] = useState<DatasetAudit | null>(null);
  const [performance, setPerformance] = useState<PerformanceResponse | null>(null);
  const testCount = useMemo(() => {
    const matrix = performance?.metrics[performance.selected_model]?.confusion_matrix;
    return matrix?.flat().reduce((sum, count) => sum + count, 0) ?? null;
  }, [performance]);

  useEffect(() => {
    api.health().then(response => setModelReady(response.model_ready)).catch(() => setModelReady(false));
    api.datasetAudit().then(setAudit).catch(() => setAudit(null));
    api.performance().then(setPerformance).catch(() => setPerformance(null));
  }, []);

  const deployedMetric = performance?.metrics[performance.selected_model];
  return <div>
    <header className="dashboard-header">
      <div><h1>Overview</h1><p>Assessment activity and model readiness for this research session.</p></div>
      <Link href="/assessment"><Button><Plus size={17}/> New assessment</Button></Link>
    </header>

    <div className="dashboard-grid">
      <section aria-labelledby="recent-heading">
        <div className="section-heading" style={{ marginTop: 0 }}>
          <div><h2 id="recent-heading">Recent assessments</h2><p>Held in memory for this session only.</p></div>
          <Link href="/reports" className="text-link">View reports <ArrowRight size={14}/></Link>
        </div>
        <Card className="table-card">
          {assessments.length ? <div className="table-wrap"><table className="session-table">
            <thead><tr><th scope="col">Date and time</th><th scope="col">Model</th><th scope="col">Model-based category</th><th scope="col">Probability</th><th scope="col"><span className="sr-only">Open</span></th></tr></thead>
            <tbody>{assessments.slice(0, 6).map(record => <tr key={record.id}>
              <td data-label="Date and time">{displayDate(record.assessedAt)}</td><td data-label="Model">Hybrid AI · {record.result.tree_component}</td>
              <td data-label="Category"><span className={`risk-tag risk-${record.result.risk_category.toLowerCase()}`}>{record.result.risk_category.toLowerCase()} risk</span></td>
              <td data-label="Probability" className="numeric-cell">{(record.result.probability * 100).toFixed(1)}%</td>
              <td data-label="Details"><Link href="/reports" className="table-action" aria-label={`Open ${displayDate(record.assessedAt)} assessment`}>Open</Link></td>
            </tr>)}</tbody>
          </table></div> : <div className="dashboard-empty">
            <div><Clock3 size={19}/></div><h3>No assessments in this session</h3>
            <p>Completed assessments will appear here until you close or refresh this app.</p>
            <Link href="/assessment"><Button variant="secondary">Start an assessment <ArrowRight size={14}/></Button></Link>
          </div>}
        </Card>
      </section>

      <aside className="dashboard-aside" aria-label="Model and dataset status">
        <Card>
          <div className="card-heading-row"><h2 className="card-title">Model status</h2><span className={`status-label ${modelReady ? "" : "status-label-muted"}`}><i className="status-dot"/>{modelReady === null ? "Checking" : modelReady ? "Ready" : "Unavailable"}</span></div>
          <div className="dashboard-stat"><span>Deployed output</span><strong>{performance?.selected_model || (modelReady ? "Hybrid AI" : "—")}</strong></div>
          <div className="dashboard-stat"><span>Model version</span><strong>{"Not exposed by API"}</strong></div>
          <p className="card-description">{modelReady ? "Predictions use the locally loaded model artifacts." : modelReady === null ? "Checking the local prediction service." : "Start the FastAPI service and check trained model artifacts."}</p>
        </Card>

        <Card>
          <div className="card-heading-row"><h2 className="card-title">Evaluation snapshot</h2><Link href="/analytics" className="quiet-link">Details</Link></div>
          {deployedMetric ? <>
            <div className="evaluation-value">{deployedMetric.roc_auc.toFixed(3)} <span>ROC-AUC</span></div>
            <p className="card-description">{performance?.selected_model} · held-out test set{testCount ? ` · n=${testCount.toLocaleString()}` : ""}</p>
          </> : <p className="card-description">Held-out performance metrics will appear when the evaluation metadata is available.</p>}
        </Card>

        <Card>
          <div className="card-heading-row"><h2 className="card-title">Dataset</h2><Database size={16} aria-hidden="true"/></div>
          {audit?.available ? <>
            <div className="evaluation-value">{audit.rows_after_cleaning?.toLocaleString() ?? "—"}<span>records after cleaning</span></div>
            <p className="card-description">{audit.columns ?? "—"} columns · {audit.duplicate_rows_removed?.toLocaleString() ?? 0} duplicates removed</p>
          </> : <p className="card-description">Dataset audit is not available from the local API.</p>}
        </Card>

        <Card className="session-note"><ShieldCheck size={17}/><p>Assessment data stays in this app session. It is cleared when the page is refreshed and is not saved as patient history.</p><Link href="/about">Privacy and limitations</Link></Card>
      </aside>
    </div>

    <section className="overview-lower">
      <div className="section-heading"><div><h2>Explore the model</h2><p>Inspect evaluation results and feature contributions.</p></div></div>
      <div className="overview-links">
        <Link href="/analytics"><Card><Database size={18}/><strong>Model analytics</strong><span>Metrics, ROC curves, and class balance</span><ArrowRight size={15}/></Card></Link>
        <Link href="/explainability"><Card><FileText size={18}/><strong>Explainability</strong><span>Global and patient-level SHAP views</span><ArrowRight size={15}/></Card></Link>
        <Link href="/hybrid-ai"><Card><ShieldCheck size={18}/><strong>Hybrid AI</strong><span>How the trained model combines outputs</span><ArrowRight size={15}/></Card></Link>
      </div>
    </section>
    <p className="screen-disclaimer">Risk bands use configurable cutoffs. SHAP contributions describe model behavior and do not show cause and effect.</p>
  </div>;
}

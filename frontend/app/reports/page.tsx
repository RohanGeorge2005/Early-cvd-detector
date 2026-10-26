"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Download, FileText, LoaderCircle, Search, ShieldCheck, X } from "lucide-react";
import { useAssessment } from "@/components/providers";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PatientXaiNetwork } from "@/components/assessment/patient-xai-network";

export default function ReportsPage() {
  const { assessments, markReportGenerated } = useAssessment();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("newest");
  const [selectedId, setSelectedId] = useState<string | null>(assessments[0]?.id ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [url, setUrl] = useState("");
  const selected = assessments.find(record => record.id === selectedId) ?? null;

  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  useEffect(() => { if (!selectedId && assessments[0]) setSelectedId(assessments[0].id); }, [assessments, selectedId]);

  const rows = useMemo(() => {
    const matching = assessments.filter(record => {
      const value = `${record.result.tree_component} ${record.result.risk_category} ${record.assessedAt}`.toLowerCase();
      return value.includes(query.toLowerCase()) && (filter === "all" || (filter === "pdf" ? record.reportGenerated : !record.reportGenerated));
    });
    return matching.sort((a, b) => sort === "oldest" ? a.assessedAt.localeCompare(b.assessedAt) : a.assessedAt.localeCompare(b.assessedAt) * -1);
  }, [assessments, filter, query, sort]);

  async function generate() {
    if (!selected) return;
    setLoading(true); setError("");
    try {
      const blob = await api.report(selected.id);
      const nextUrl = URL.createObjectURL(blob);
      setUrl(old => { if (old) URL.revokeObjectURL(old); return nextUrl; });
      markReportGenerated(selected.id);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Report generation failed.");
    } finally { setLoading(false); }
  }

  function selectAssessment(id: string) {
    setSelectedId(id); setError("");
    if (url) { URL.revokeObjectURL(url); setUrl(""); }
  }

  return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <div className="page-heading"><div className="eyebrow"><FileText size={14}/> Reports</div><h1 className="page-title">Assessment reports</h1><p className="page-subtitle">Review assessments completed during this app session, then generate a PDF for the selected record. This list clears when the app is refreshed.</p></div>

    <section aria-labelledby="reports-table-heading">
      <div className="section-heading" style={{ marginTop: 0 }}><div><h2 id="reports-table-heading">Session assessments</h2><p>{assessments.length} {assessments.length === 1 ? "assessment" : "assessments"} in memory · no patient history is saved</p></div></div>
      {assessments.length > 0 ? <>
        <div className="table-controls report-controls">
          <label className="report-search"><Search size={16}/><input className="input" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search model or category" aria-label="Search assessments"/>{query && <button className="icon-button" aria-label="Clear search" onClick={() => setQuery("")}><X size={15}/></button>}</label>
          <label><span className="sr-only">Filter PDF status</span><select className="select" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All records</option><option value="pdf">PDF generated</option><option value="pending">PDF not generated</option></select></label>
          <label><span className="sr-only">Sort assessments</span><select className="select" value={sort} onChange={event => setSort(event.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></label>
        </div>
        <Card className="report-table-card"><div className="table-wrap"><table className="session-table report-table"><thead><tr><th scope="col">Date and time</th><th scope="col">Model</th><th scope="col">Category</th><th scope="col">Probability</th><th scope="col">PDF</th><th scope="col">Model version</th><th scope="col"><span className="sr-only">Details</span></th></tr></thead><tbody>
          {rows.map(record => <tr key={record.id} className={record.id === selectedId ? "selected-row" : ""}>
            <td data-label="Date and time">{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(record.assessedAt))}</td>
            <td data-label="Model">{record.result.tree_component} + MLP</td>
            <td data-label="Category"><span className={`risk-tag risk-${record.result.risk_category.toLowerCase()}`}>{record.result.risk_category.toLowerCase()} risk</span></td>
            <td data-label="Probability" className="numeric-cell">{(record.result.probability * 100).toFixed(1)}%</td>
            <td data-label="PDF">{record.reportGenerated ? <span className="status-label">Generated</span> : <span className="report-status-pending">Not generated</span>}</td>
            <td data-label="Model version">{record.result.model_version}</td>
            <td data-label="Details"><button className="table-action" aria-pressed={record.id === selectedId} onClick={() => selectAssessment(record.id)}>{record.id === selectedId ? "Selected" : "View"}</button></td>
          </tr>)}
          {!rows.length && <tr><td colSpan={7} className="table-empty">No assessments match these filters.</td></tr>}
        </tbody></table></div></Card>
      </> : <Card className="empty-state"><div className="empty-icon"><FileText size={20}/></div><h3>No assessment reports in this session</h3><p>Complete a model assessment first. Completed results stay in memory until you close or refresh this app.</p><Link href="/assessment" style={{ marginTop: 14 }}><Button>Start an assessment <ArrowRight size={14}/></Button></Link></Card>}
    </section>

    {selected && <section className="report-detail" aria-labelledby="report-detail-heading">
      <div className="section-heading"><div><h2 id="report-detail-heading">Selected assessment</h2><p>Created {new Intl.DateTimeFormat(undefined, { dateStyle: "full", timeStyle: "short" }).format(new Date(selected.assessedAt))}</p></div><Button onClick={generate} disabled={loading}>{loading ? <><LoaderCircle className="spinner"/> Creating PDF…</> : <><FileText size={15}/> Generate PDF</>}</Button></div>
      <div className="dashboard-grid report-detail-grid">
        <Card><div className="card-heading-row"><h3 className="card-title">Assessment result</h3><span className={`risk-tag risk-${selected.result.risk_category.toLowerCase()}`}>{selected.result.risk_category.toLowerCase()} risk</span></div>
          <div className="report-probability">{(selected.result.probability * 100).toFixed(1)}<span>%</span></div>
          <p className="card-description">10-year model probability · {selected.result.binary_label}</p>
          <div className="model-list"><div><div className="model-row-head"><span>Assessment ID</span><b>{selected.id.slice(0, 12)}</b></div><div className="model-row-head"><span>Selected model component</span><b>{selected.result.tree_component}</b></div><div className="model-row-head"><span>MLP component</span><b>{(selected.result.dl_probability * 100).toFixed(1)}%</b></div><div className="model-row-head"><span>Model version</span><b>{selected.result.model_version}</b></div><div className="model-row-head"><span>Component agreement</span><b>{selected.result.model_consensus ? "Agree" : "Disagree"}</b></div></div></div>
          <p className="report-model-note">Risk category and binary prediction use separate thresholds and can differ. Categories are model-based and not clinically validated.</p>
        </Card>
        <Card><h3 className="card-title">Key contributing factors</h3><p className="card-description">SHAP describes model behavior, not medical causation.</p><div className="contribution-list" style={{ marginTop: 14 }}>{selected.result.top_factors.slice(0, 5).map(factor => <div className="contribution-row" key={factor.feature}><span className={factor.contribution >= 0 ? "contribution-up" : "contribution-down"} aria-hidden="true">{factor.contribution >= 0 ? "↑" : "↓"}</span><span>{factor.feature}</span><small>{factor.contribution > 0 ? "+" : ""}{factor.contribution.toFixed(3)}</small></div>)}</div></Card>
      </div>
      <div style={{ marginTop: 13 }}><PatientXaiNetwork key={selected.id} result={selected.result} patient={selected.patient}/></div>
      {error && <div className="alert" role="alert">{error}</div>}
      {url && <><div className="section-heading"><div><h2>PDF preview</h2><p>The generated PDF includes patient inputs, model output, explanation, limitations, and disclaimer.</p></div><a className="button button-secondary" href={url} download="xai-cvd-assessment.pdf"><Download size={15}/> Download PDF</a></div><Card className="pdf-preview-card"><iframe title="Explainable cardiovascular risk PDF report" src={url}/></Card></>}
    </section>}

    <p className="screen-disclaimer"><ShieldCheck size={15}/> Report files may contain sensitive health measurements. Download them only to a private device. Records and PDF previews remain in this browser session.</p>
  </motion.div>;
}

"use client";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ChartNoAxesCombined, RefreshCw } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { PerformanceResponse } from "@/lib/types";
import type { DatasetAudit, GlobalXAI } from "@/lib/types";

const RocChart = dynamic(() => import("@/components/charts/analytics-charts").then(module => module.RocChart), { ssr: false, loading: () => <div className="skeleton"/> });
const ConfusionMatrix = dynamic(() => import("@/components/charts/analytics-charts").then(module => module.ConfusionMatrix), { ssr: false, loading: () => <div className="skeleton"/> });
const ImportanceChart = dynamic(() => import("@/components/charts/analytics-charts").then(module => module.ImportanceChart), { ssr: false, loading: () => <div className="skeleton"/> });
const ClassBalance = dynamic(() => import("@/components/charts/analytics-charts").then(module => module.ClassBalance), { ssr: false, loading: () => <div className="skeleton"/> });

type MetricKey = "accuracy" | "precision" | "recall" | "f1" | "roc_auc";
const metricOptions: { key: MetricKey; label: string }[] = [
  { key: "accuracy", label: "Accuracy" }, { key: "precision", label: "Precision" }, { key: "recall", label: "Recall" }, { key: "f1", label: "F1" }, { key: "roc_auc", label: "ROC-AUC" },
];

export default function AnalyticsPage() {
  const [data, setData] = useState<PerformanceResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState("");
  const [global, setGlobal] = useState<GlobalXAI | null>(null);
  const [audit, setAudit] = useState<DatasetAudit | null>(null);
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<MetricKey>("roc_auc");
  const [sortDirection, setSortDirection] = useState<"high" | "low">("high");

  async function load() {
    setLoading(true); setError("");
    const [performance, xai, dataset] = await Promise.allSettled([api.performance(), api.globalXai(), api.datasetAudit()]);
    if (performance.status === "fulfilled") { setData(performance.value); setActive(Object.keys(performance.value.metrics)[0] || ""); }
    else setError(performance.reason instanceof ApiError ? performance.reason.message : "Model performance is unavailable.");
    if (xai.status === "fulfilled") setGlobal(xai.value);
    if (dataset.status === "fulfilled") setAudit(dataset.value);
    setLoading(false);
  }
  useEffect(() => { void load(); }, []);

  const models = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.metrics).filter(([name]) => name.toLowerCase().includes(query.trim().toLowerCase())).sort(([nameA, a], [nameB, b]) => {
      const delta = a[sortKey] - b[sortKey];
      return delta === 0 ? nameA.localeCompare(nameB) : (sortDirection === "high" ? -delta : delta);
    });
  }, [data, query, sortDirection, sortKey]);

  const selectedMetric = data?.metrics[data.selected_model];
  const testCount = selectedMetric?.confusion_matrix.flat().reduce((sum, count) => sum + count, 0);
  return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <div className="page-heading"><div className="eyebrow"><ChartNoAxesCombined size={14}/> Model evaluation</div><h1 className="page-title">Model analytics</h1><p className="page-subtitle">Compare saved model outputs on the held-out test set. Metrics are read from the trained artifacts; they are not live clinical performance estimates.</p></div>

    {loading ? <div className="grid-2"><div className="skeleton"/><div className="skeleton"/></div> : error ? <Card className="empty-state"><div className="empty-icon"><ChartNoAxesCombined size={20}/></div><h2>Evaluation data unavailable</h2><p>{error} No placeholder values are shown.</p><Button variant="secondary" onClick={() => void load()} style={{ marginTop: 15 }}><RefreshCw size={15}/> Retry</Button></Card> : data && <>
      <div className="analytics-summary">
        <Card className="analytics-selected"><span className="summary-label">Deployed model output</span><strong>{data.selected_model}</strong><span>{data.selected_tree_model || "Tree component not recorded"} with tabular MLP</span></Card>
        <div className="analytics-summary-side">
          <Card><span className="summary-label">Selected output · ROC-AUC</span><strong>{selectedMetric?.roc_auc.toFixed(3) ?? "—"}</strong><span>Held-out split{testCount ? ` · n=${testCount.toLocaleString()}` : ""}</span></Card>
          <Card><span className="summary-label">Best evaluation composite</span><strong>{data.best_model_by_composite}</strong><span>Composite ranking from saved metadata</span></Card>
        </div>
      </div>

      <div className="section-heading"><div><h2>Model comparison</h2><p>All models use the same saved evaluation split. Sort by a metric or filter the model list.</p></div></div>
      <div className="table-controls analytics-controls">
        <label className="report-search"><span className="sr-only">Filter models</span><input className="input" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Filter models" aria-label="Filter models"/></label>
        <label><span className="sr-only">Sort metric</span><select className="select" value={sortKey} onChange={event => setSortKey(event.target.value as MetricKey)}>{metricOptions.map(option => <option key={option.key} value={option.key}>Sort: {option.label}</option>)}</select></label>
        <label><span className="sr-only">Sort direction</span><select className="select" value={sortDirection} onChange={event => setSortDirection(event.target.value as "high" | "low")}><option value="high">Highest first</option><option value="low">Lowest first</option></select></label>
      </div>
      <Card className="analytics-table-card"><div className="table-wrap"><table className="data-table analytics-table"><caption className="sr-only">Model comparison metrics on the held-out test split</caption><thead><tr><th scope="col">Model</th>{metricOptions.map(option => <th scope="col" key={option.key}>{option.label}</th>)}</tr></thead><tbody>
        {models.map(([name, metric]) => <tr key={name} className={name === data.best_model_by_composite ? "best-row" : ""}>
          <td>{name}{name === data.selected_model && <span className="table-meta">Deployed output</span>}{name === data.best_model_by_composite && <span className="table-meta">Best composite</span>}</td>
          {metricOptions.map(option => <td className="numeric-cell" data-label={option.label} key={option.key}>{metric[option.key].toFixed(3)}</td>)}
        </tr>)}
        {!models.length && <tr><td className="table-empty" colSpan={6}>No models match that filter.</td></tr>}
      </tbody></table></div></Card>

      <div className="analytics-chart-layout">
        <RocChart metrics={data.metrics}/>
        <Card className="calibration-note"><h2 className="card-title">Calibration</h2><p className="card-description">A calibration curve is not present in the saved evaluation response, so no calibration values are plotted. Do not interpret ranking discrimination as calibration.</p><p className="card-description">The displayed probability is a model output. The current API does not return calibration bins or a Brier score.</p></Card>
      </div>
      {global && global.feature_importance.length > 0 && <div className="analytics-wide-chart"><ImportanceChart data={global.feature_importance}/></div>}
      {audit?.available && <div className="analytics-wide-chart"><ClassBalance audit={audit}/></div>}

      <div className="section-heading"><div><h2>Confusion matrix</h2><p>Counts at the saved classification threshold. Rows are actual class; columns are predicted class.</p></div><label><span className="sr-only">Select model confusion matrix</span><select className="select" aria-label="Select model confusion matrix" value={active} onChange={event => setActive(event.target.value)} style={{ width: "auto", minWidth: 180 }}>{Object.keys(data.metrics).map(name => <option key={name}>{name}</option>)}</select></label></div>
      {active && data.metrics[active] && <div className="analytics-wide-chart"><ConfusionMatrix name={active} metric={data.metrics[active]}/></div>}
      <p className="screen-disclaimer">These retrospective results describe model performance on one held-out dataset split. They do not establish clinical utility or external validity.</p>
    </>}
  </motion.div>;
}

"use client";

import { useEffect, useState } from "react";
import { Activity, Network, RefreshCw } from "lucide-react";
import { RiskFactorGraph } from "@/components/network/risk-factor-graph";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import type { RiskNetworkResponse } from "@/lib/types";

export default function RiskNetworkPage() {
  const [data, setData] = useState<RiskNetworkResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function loadNetwork() {
    setLoading(true); setError("");
    try { setData(await api.riskNetwork()); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Risk-factor associations could not be loaded."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void loadNetwork(); }, []);

  return <div className="risk-network-page">
    <div className="page-heading"><div className="eyebrow"><Network size={14}/> Dataset exploration</div><h1 className="page-title">Risk Factor Network</h1><p className="page-subtitle">Explore statistically supported associations among the predictors used by this application. The graph is descriptive; it does not change model predictions.</p></div>
    {loading ? <div className="network-loading" aria-label="Loading risk-factor network"><div className="skeleton"/><div className="skeleton"/></div> : error ? <Card className="network-error" role="alert"><div className="empty-icon"><Activity size={20}/></div><h2>Network data unavailable</h2><p>{error} No sample data or placeholder relationships are shown.</p><Button variant="secondary" onClick={() => void loadNetwork()}><RefreshCw size={15}/> Retry</Button></Card> : !data || data.nodes.length === 0 ? <Card className="network-error"><h2>No predictor data found</h2><p>The source dataset did not contain the expected predictor fields. Check the dataset schema and reload this page.</p></Card> : <>
      <div className="network-data-summary"><span><b>{data.rows.toLocaleString()}</b> cleaned dataset records</span><span><b>{data.feature_count}</b> model predictors</span><span><b>{data.edge_count}</b> FDR-significant associations</span><span>Source: {data.source_file}</span></div>
      <Card className="network-method-note"><p><b>How to read this graph.</b> Nodes are the model’s dataset predictors; edges connect pairs with an absolute Spearman correlation above your selected threshold and Benjamini–Hochberg adjusted q ≤ 0.05. Edge thickness represents |ρ|. The outcome <code>TenYearCHD</code> is intentionally excluded.</p><p>Pairwise complete rows are used, with at least {data.minimum_pairwise_observations} observations per tested pair. {data.p_value_method || "Spearman p-values use the library's asymptotic approximation."} The raw p-value is shown separately from the BH-adjusted q-value. Feature summaries and associations describe this dataset; correlation does not establish causation or clinical importance.</p></Card>
      {data.edges.length === 0 ? <Card className="network-error"><h2>No statistically supported relationships</h2><p>No predictor pairs passed the minimum sample and multiple-testing criteria. The page does not create illustrative substitute edges.</p></Card> : <RiskFactorGraph data={data}/>}
      <p className="screen-disclaimer">Educational and research use only. Dataset-level associations are separate from individual model explanations and model predictions.</p>
    </>}
  </div>;
}

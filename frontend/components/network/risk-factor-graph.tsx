"use client";

import { useEffect, useMemo, useRef, useState, type PointerEvent, type WheelEvent } from "react";
import { Minus, Plus, RotateCcw, Search, Maximize } from "lucide-react";
import { Card } from "@/components/ui/card";
import type { NetworkEdge, NetworkNode, RiskNetworkResponse } from "@/lib/types";

const categoryColors: Record<string, string> = {
  Demographics: "var(--brand-600)", Lifestyle: "var(--info)",
  "Medical history": "var(--purple)", "Clinical measures": "var(--warning)",
};
const categoryOrder = ["Demographics", "Lifestyle", "Medical history", "Clinical measures"];
const center = { x: 450, y: 320 };

function nodePositions(nodes: NetworkNode[]) {
  return Object.fromEntries(nodes.map((node, index) => {
    const angle = -Math.PI / 2 + index * (Math.PI * 2 / Math.max(1, nodes.length));
    const radius = 225;
    return [node.id, { x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius }];
  }));
}

function formatValue(value: number | null, unit: string) {
  if (value === null) return "—";
  const rounded = Number.isInteger(value) ? value.toLocaleString() : value.toFixed(1);
  return unit === "yes/no" || unit === "encoded category" || unit === "ordinal level" ? rounded : `${rounded} ${unit}`;
}

function relationshipText(edge: NetworkEdge, featureId: string) {
  const other = edge.source === featureId ? edge.target : edge.source;
  return { other, direction: edge.correlation > 0 ? "Positive" : "Negative" };
}

export function RiskFactorGraph({ data }: { data: RiskNetworkResponse }) {
  const [threshold, setThreshold] = useState(0.2);
  const [view, setView] = useState<"all" | "strongest">("all");
  const [direction, setDirection] = useState<"all" | "positive" | "negative">("all");
  const [showEdgeLabels, setShowEdgeLabels] = useState(false);
  const [query, setQuery] = useState("");
  const [categories, setCategories] = useState<string[]>(categoryOrder);
  const [selectedId, setSelectedId] = useState(data.nodes[0]?.id || "");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const positions = useMemo(() => nodePositions(data.nodes), [data.nodes]);

  const visibleNodes = useMemo(() => data.nodes.filter(node => categories.includes(node.category)), [data.nodes, categories]);
  const visibleIds = useMemo(() => new Set(visibleNodes.map(node => node.id)), [visibleNodes]);
  const eligibleEdges = useMemo(() => data.edges.filter(edge => edge.strength >= threshold && visibleIds.has(edge.source) && visibleIds.has(edge.target) && (direction === "all" || (direction === "positive" ? edge.correlation > 0 : edge.correlation < 0))), [data.edges, threshold, visibleIds, direction]);
  const visibleEdges = useMemo(() => view === "strongest" ? eligibleEdges.slice(0, 12) : eligibleEdges, [eligibleEdges, view]);
  const searchMatches = useMemo(() => {
    const term = query.trim().toLowerCase();
    return new Set(visibleNodes.filter(node => !term || `${node.label} ${node.id} ${node.category}`.toLowerCase().includes(term)).map(node => node.id));
  }, [visibleNodes, query]);
  const selected = visibleNodes.find(node => node.id === selectedId) || visibleNodes[0];
  const selectedEdges = selected ? visibleEdges.filter(edge => edge.source === selected.id || edge.target === selected.id).sort((a, b) => b.strength - a.strength) : [];
  const connectedIds = useMemo(() => new Set(selected ? [selected.id, ...selectedEdges.map(edge => edge.source === selected.id ? edge.target : edge.source)] : []), [selected, selectedEdges]);

  useEffect(() => {
    if (selected && selected.id !== selectedId) setSelectedId(selected.id);
  }, [selected, selectedId]);

  function reset() {
    setThreshold(0.2); setQuery(""); setCategories(categoryOrder); setZoom(1); setPan({ x: 0, y: 0 }); setView("all"); setDirection("all"); setShowEdgeLabels(false);
    setSelectedId(data.nodes[0]?.id || "");
  }
  function toggleCategory(category: string) {
    setCategories(current => current.includes(category) ? current.filter(item => item !== category) : [...current, category]);
  }
  function onPointerDown(event: PointerEvent<SVGSVGElement>) {
    if ((event.target as Element).closest("[data-network-node]")) return;
    drag.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!drag.current) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const scaleX = 900 / rect.width;
    const scaleY = 650 / rect.height;
    setPan({ x: drag.current.panX + (event.clientX - drag.current.x) * scaleX, y: drag.current.panY + (event.clientY - drag.current.y) * scaleY });
  }
  function onPointerUp(event: PointerEvent<SVGSVGElement>) {
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }
  function onWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault(); setZoom(current => Math.max(0.75, Math.min(1.8, current + (event.deltaY < 0 ? 0.08 : -0.08))));
  }

  return <>
    <div className="network-controls">
      <label className="network-search"><Search size={16}/><span className="sr-only">Search risk factors</span><input value={query} onChange={event => { const value = event.target.value; setQuery(value); const term = value.trim().toLowerCase(); const match = visibleNodes.find(node => `${node.label} ${node.id} ${node.category}`.toLowerCase().includes(term)); if (term && match) setSelectedId(match.id); }} placeholder="Search risk factors" aria-label="Search risk factors"/></label>
      <label className="network-threshold"><span>Minimum |ρ| <b>{threshold.toFixed(2)}</b></span><input type="range" min="0.05" max="0.75" step="0.01" value={threshold} onChange={event => setThreshold(Number(event.target.value))} aria-label="Minimum absolute Spearman correlation"/><span className="network-threshold-hint">Only FDR-significant relationships are eligible.</span></label>
      <button className="network-reset" type="button" onClick={reset}><RotateCcw size={15}/> Reset filters</button>
    </div>
    <div className="network-view-controls" role="group" aria-label="Relationship display controls">
      <label>Relationships<select className="select" value={view} onChange={event => setView(event.target.value as "all" | "strongest")}><option value="all">All eligible ({eligibleEdges.length})</option><option value="strongest">12 strongest</option></select></label>
      <label>Direction<select className="select" value={direction} onChange={event => setDirection(event.target.value as "all" | "positive" | "negative")}><option value="all">Positive and negative</option><option value="positive">Positive only</option><option value="negative">Negative only</option></select></label>
      <label className="network-label-toggle"><input type="checkbox" checked={showEdgeLabels} onChange={event => setShowEdgeLabels(event.target.checked)}/> Show edge labels</label>
    </div>
    <div className="network-category-filters" role="group" aria-label="Filter feature categories">
      {categoryOrder.map(category => <label className="network-category-option" key={category}><input type="checkbox" checked={categories.includes(category)} onChange={() => toggleCategory(category)}/><i style={{ background: categoryColors[category] }}/>{category}</label>)}
    </div>
    {visibleNodes.length === 0 ? <Card className="network-empty"><h2>No categories selected</h2><p>Choose at least one feature category to display the network.</p><button type="button" onClick={() => setCategories(categoryOrder)}>Show all categories</button></Card> : <div className="network-layout">
      <Card className="network-graph-card">
        <div className="network-graph-heading"><div><h2>Dataset associations</h2><p>{visibleNodes.length} of {data.feature_count} features · {visibleEdges.length} of {eligibleEdges.length} eligible relationships shown</p></div><div className="network-zoom" aria-label="Graph zoom controls"><button type="button" onClick={() => setZoom(value => Math.max(0.75, value - 0.1))} aria-label="Zoom out"><Minus size={16}/></button><span>{Math.round(zoom * 100)}%</span><button type="button" onClick={() => setZoom(value => Math.min(1.8, value + 0.1))} aria-label="Zoom in"><Plus size={16}/></button><button type="button" onClick={() => {setZoom(1);setPan({x:0,y:0});}} aria-label="Fit graph to screen"><Maximize size={15}/></button></div></div>
        <svg className="risk-network-svg" viewBox="0 0 900 650" role="group" aria-label={`Interactive network graph with ${visibleNodes.length} cardiovascular predictors and ${visibleEdges.length} statistically significant Spearman associations. Drag to pan and use the mouse wheel or zoom buttons to zoom.`} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp} onWheel={onWheel}>
          <g transform={`translate(${center.x + pan.x} ${center.y + pan.y}) scale(${zoom}) translate(${-center.x} ${-center.y})`}>
            {visibleEdges.map(edge => {
              const a = positions[edge.source], b = positions[edge.target];
              if (!a || !b) return null;
              const focused = selected ? connectedIds.has(edge.source) && connectedIds.has(edge.target) : false;
              const signed = edge.correlation >= 0;
              const midX = (a.x + b.x) / 2, midY = (a.y + b.y) / 2;
              return <g key={`${edge.source}-${edge.target}`} opacity={selected ? (focused ? 0.95 : 0.1) : 0.55}>
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={signed ? "var(--info)" : "var(--purple)"} strokeWidth={focused ? 2 + edge.strength * 5 : 1 + edge.strength * 3}>
                <title>{`${data.nodes.find(node => node.id === edge.source)?.label} – ${data.nodes.find(node => node.id === edge.target)?.label}: Spearman ρ ${edge.correlation.toFixed(2)}, n=${edge.sample_size}, q=${edge.q_value.toExponential(2)}`}</title>
                </line>
                {showEdgeLabels && <g pointerEvents="none"><rect x={midX-24} y={midY-10} width="48" height="19" rx="5" className="network-edge-label-bg"/><text x={midX} y={midY+4} textAnchor="middle" className="network-edge-label">{edge.correlation > 0 ? "+" : ""}{edge.correlation.toFixed(2)}</text></g>}
              </g>;
            })}
            {visibleNodes.map(node => {
              const point = positions[node.id];
              if (!point) return null;
              const isSelected = selected?.id === node.id;
              const matched = searchMatches.has(node.id);
              const dimmed = Boolean(query.trim()) && !matched;
              const related = connectedIds.has(node.id);
              return <g key={node.id} className={`network-node${isSelected ? " selected" : ""}`} data-network-node="true" tabIndex={0} role="button" aria-label={`${node.label}, ${node.category}; select for dataset statistics and associations`} aria-pressed={isSelected} opacity={dimmed || (selected && !related) ? 0.28 : 1} onClick={() => setSelectedId(node.id)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedId(node.id); } }}>
                <circle cx={point.x} cy={point.y} r={isSelected ? 29 : 24} fill={categoryColors[node.category] || "var(--brand-600)"} stroke={isSelected ? "var(--text)" : "var(--surface)"} strokeWidth={isSelected ? 3 : 2}/>
                <text x={point.x} y={point.y + 4} textAnchor="middle" className="network-node-code">{node.id === "currentSmoker" ? "SMK" : node.id === "prevalentStroke" ? "STR" : node.id === "prevalentHyp" ? "HTN" : node.id === "cigsPerDay" ? "CIG" : node.id === "totChol" ? "CHOL" : node.id === "sysBP" ? "SYS" : node.id === "diaBP" ? "DIA" : node.id === "heartRate" ? "HR" : node.id === "BPMeds" ? "MED" : node.id.slice(0, 4).toUpperCase()}</text>
                <text x={point.x} y={point.y + 43} textAnchor="middle" className="network-node-label">{node.short_label}</text>
                <title>{`${node.label} · ${node.category}`}</title>
              </g>;
            })}
          </g>
        </svg>
        <div className="network-legend" aria-label="Graph legend">
          {categoryOrder.map(category => <span key={category}><i style={{ background: categoryColors[category] }}/>{category}</span>)}
          <span><i className="network-edge-positive"/>Positive ρ</span><span><i className="network-edge-negative"/>Negative ρ</span>
        </div>
        <p className="network-hint">Select a node for details. Drag to pan; use the wheel or controls to zoom. Unrelated nodes and edges fade when a feature is selected. Edge color and sign indicate association direction, not health risk.</p>
      </Card>
      {query.trim() && searchMatches.size === 0 && <p className="network-search-empty" role="status">No risk factor matches “{query}”. Try another feature name.</p>}
      <Card className="network-details" aria-live="polite">
        {!selected ? <div className="network-empty"><h2>No feature matches</h2><p>Change the category filters to see nodes.</p></div> : <>
          <label className="network-node-select">Selected feature<select aria-label="Select risk factor details" value={selected.id} onChange={event => setSelectedId(event.target.value)}>{visibleNodes.map(node => <option key={node.id} value={node.id}>{node.label} · {node.category}</option>)}</select></label>
          <div className="network-detail-category"><i style={{ background: categoryColors[selected.category] }}/>{selected.category}</div>
          <h2>{selected.label}</h2><p className="network-detail-description">{selected.description}</p>
          <div className="network-stat-grid"><div><span>Observed</span><b>{selected.statistics.observations.toLocaleString()}</b></div><div><span>Missing</span><b>{selected.statistics.missing.toLocaleString()}</b></div>
            {selected.statistics.value_one_label ? <div className="network-stat-wide"><span>{selected.statistics.value_one_label} · code 1</span><b>{selected.statistics.value_one_percent?.toFixed(1)}% ({selected.statistics.value_one_count?.toLocaleString()})</b></div> : <><div><span>Mean</span><b>{formatValue(selected.statistics.mean, selected.unit)}</b></div><div><span>Median</span><b>{formatValue(selected.statistics.median, selected.unit)}</b></div><div className="network-stat-wide"><span>Observed range</span><b>{formatValue(selected.statistics.minimum, selected.unit)}–{formatValue(selected.statistics.maximum, selected.unit)}</b></div></>}
          </div>
          <h3>Strongest displayed associations</h3>
          <p className="network-detail-note">Pairwise Spearman rank correlation · pairwise complete observations. Raw p-values are unadjusted; q-values use Benjamini–Hochberg FDR across {data.tested_pair_count} tested pairs (q ≤ 0.05). Small: |ρ| &lt; 0.30; moderate: 0.30–&lt;0.50; large: ≥ 0.50 (descriptive conventions only).</p>
          {selectedEdges.length ? <ul className="network-association-list">{selectedEdges.slice(0, 8).map(edge => {
            const relation = relationshipText(edge, selected.id);
            const otherNode = data.nodes.find(node => node.id === relation.other);
            const sourceLabel = data.nodes.find(node => node.id === edge.source)?.label || edge.source;
            const targetLabel = data.nodes.find(node => node.id === edge.target)?.label || edge.target;
            const magnitude = edge.strength < .3 ? "small" : edge.strength < .5 ? "moderate" : "large";
            return <li key={`${edge.source}-${edge.target}`}><button type="button" onClick={() => setSelectedId(relation.other)}><span>{sourceLabel} → {targetLabel}</span><b>{relation.direction} · ρ {edge.correlation.toFixed(2)} ({magnitude})</b><small>n={edge.sample_size.toLocaleString()} · raw p={edge.p_value.toExponential(1)} · BH q={edge.q_value.toExponential(1)}</small></button></li>;
          })}</ul> : <p className="network-no-edges">No association meets the current strength threshold for this feature. Lower the threshold to explore more qualifying relationships.</p>}
          <p className="network-warning">Association is not causation. Binary variables are encoded 0/1; direction follows the source dataset’s encoding. This graph is descriptive and does not show an individual prediction.</p>
        </>}
      </Card>
    </div>}
  </>;
}

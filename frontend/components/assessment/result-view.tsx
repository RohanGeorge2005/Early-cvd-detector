"use client";
import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, Check, TriangleAlert } from "lucide-react";
import type { CSSProperties } from "react";
import { Card } from "@/components/ui/card";
import { LocalWaterfall } from "@/components/xai/shap-visuals";
import { PatientXaiNetwork } from "@/components/assessment/patient-xai-network";
import { FEATURE_LABELS, formatFeatureValue } from "@/lib/utils";
import type { PatientInput, PredictionResponse } from "@/lib/types";

const riskColor = { LOW:"var(--risk-low)", MODERATE:"var(--risk-moderate)", HIGH:"var(--risk-high)" };
export function ResultView({ result, patient }: { result: PredictionResponse; patient: PatientInput }) {
  const color = riskColor[result.risk_category]; const outputs = Object.entries(result.model_outputs);
  const top = result.shap_values.slice(0, 8); const max = Math.max(...top.map(f=>Math.abs(f.contribution)), 1e-9);
  return <div style={{marginTop:25}}>
    <div className="result-heading"><div><div className="eyebrow">Assessment result</div><h2 className="page-title" style={{fontSize:27}}>10-year CHD estimate</h2></div><Link href="/explainability" className="text-link">Full explanation <span aria-hidden="true">→</span></Link></div>
    <div className="grid-2" style={{alignItems:"stretch",marginTop:15}}>
      <div className="risk-result"><div className="risk-gauge" style={{"--p":`${Math.max(0,Math.min(1,result.probability))*100}%`,"--risk-color":color} as CSSProperties} role="img" aria-label={`${(result.probability*100).toFixed(0)} percent model-estimated 10-year CHD probability`}><div className="risk-gauge-inner"><strong className="risk-percent">{(result.probability*100).toFixed(0)}%</strong><span className="risk-label">Model probability</span></div></div><span className={`risk-tag risk-${result.risk_category.toLowerCase()}`}>{result.risk_category.toLowerCase()} model-based category</span><span className="risk-small">Category bands are configurable and not clinically validated.</span><span className="binary-result">Binary model output: <strong>{result.binary_label}</strong></span></div>
      <Card><div className="card-heading-row"><h3 className="card-title">Model agreement</h3><span className={`agreement-label ${result.model_consensus ? "agreement-match" : "agreement-mixed"}`}>{result.model_consensus ? <Check size={14}/> : <TriangleAlert size={14}/>} {result.model_consensus ? "Components agree" : "Components differ"}</span></div><p className="card-description">Tree model and MLP outputs provide a simple indication of model disagreement. This is not a calibrated confidence interval.</p><div className="model-list">{outputs.map(([name,p])=><div key={name}><div className="model-row-head"><span>{name}</span><b>{(p*100).toFixed(1)}%</b></div><div className="prob-track"><div className="prob-fill" style={{width:`${p*100}%`}}/></div></div>)}</div><p className="card-description">Blend: {result.tree_component} {(result.alpha*100).toFixed(0)}% · MLP {((1-result.alpha)*100).toFixed(0)}%.</p><p className="threshold-note">The category uses probability bands; the binary label uses a {Math.round(result.model_threshold*100)}% model threshold. They can differ.</p></Card>
    </div>
    <div className="grid-2" style={{marginTop:13,alignItems:"start"}}>
      <Card><h3 className="card-title">Factors contributing to the prediction</h3><p className="card-description">Patient-specific SHAP contributions · not causal explanations</p><div className="explain-bars" style={{marginTop:17}}>{top.map(f=>{const pos=f.contribution>=0;const width=Math.abs(f.contribution)/max*49;return <div className="explain-row" key={f.feature}><span className="explain-feature" title={FEATURE_LABELS[f.feature]}>{FEATURE_LABELS[f.feature]||f.feature}</span><div className="explain-track"><i className="explain-bar" style={{left:pos?"50%":`calc(50% - ${width}%)`,width:`${width}%`,"--bar-color":pos?"var(--coral)":"var(--green)"} as CSSProperties}/></div><span className="explain-value">{f.contribution>0?"+":""}{f.contribution.toFixed(3)}</span></div>})}</div><div className="contribution-list" style={{marginTop:15}}>{top.slice(0,5).map(f=><div className="contribution-row" key={f.feature}>{f.contribution>=0?<ArrowUpRight className="up" size={14}/>:<ArrowDownRight className="down" size={14}/>}<span>{FEATURE_LABELS[f.feature]||f.feature}</span><small>{formatFeatureValue(f.feature,patient[f.feature as keyof PatientInput] as number)} · {f.direction}</small></div>)}</div></Card>
      <Card><h3 className="card-title">Discussion points</h3><p className="card-description">General educational topics based on the entered values</p><div className="decision-list" style={{marginTop:15}}>{result.decision_support.map((item,i)=><div className="decision-row" key={i}><span>{String(i+1).padStart(2,"0")}</span><p>{item}</p></div>)}</div><p className="card-description" style={{marginTop:14}}>Review these topics with a qualified healthcare professional.</p></Card>
    </div>
    <div style={{marginTop:13}}><PatientXaiNetwork key={result.assessment_id} result={result} patient={patient}/></div>
    <div style={{marginTop:13}}><LocalWaterfall result={result} patient={patient}/></div>
  </div>;
}

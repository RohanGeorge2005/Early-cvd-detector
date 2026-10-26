"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { Activity, ArrowDown, ChevronDown, ChevronUp, GitMerge, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";

const stages = [
  { title: "Patient data", detail: "The API accepts exactly the 15 predictors defined by the supplied CHD dataset. It does not request identifiers, ECG, imaging, or wearable data." },
  { title: "Trained preprocessing", detail: "The fitted preprocessing pipeline is loaded from the saved bundle. It applies the same transformations used during training." },
  { title: "Tree model", detail: "Logistic Regression, Random Forest, and XGBoost are evaluated. A tree branch is selected using validation performance." },
  { title: "Tabular neural network", detail: "A trained multilayer perceptron produces another probability from the same 15 inputs." },
  { title: "Hybrid estimate", detail: "The saved blend weight combines the tree and MLP outputs. This is a model output, not a clinical risk score." },
  { title: "Explanation and insights", detail: "Permutation SHAP describes feature contributions to the hybrid output. Educational suggestions do not prescribe treatment." },
];

export default function HybridPage() {
  const [expanded, setExpanded] = useState<number | null>(null);
  return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <div className="page-heading"><div className="eyebrow"><GitMerge size={14}/> Model architecture</div><h1 className="page-title">Hybrid AI</h1><p className="page-subtitle">A selected tree model and a tabular neural network contribute to the final model estimate. The diagram describes the saved model pipeline; it does not show example probabilities.</p></div>

    <Card className="hybrid-flow hybrid-architecture-card"><div className="architecture">
      <div className="architecture-node">Patient data<small>15 validated dataset predictors</small></div><div className="architecture-arrow"><ArrowDown size={17}/></div>
      <div className="architecture-node">Trained preprocessing<small>Fitted transformations from training</small></div><div className="architecture-arrow"><ArrowDown size={17}/></div>
      <div className="architecture-fork"><div className="architecture-node">Tree model<small>Selected from Logistic Regression, Random Forest, XGBoost</small></div><div className="architecture-node">Tabular MLP<small>Trained feed-forward model</small></div></div>
      <div className="architecture-arrow"><ArrowDown size={17}/></div>
      <div className="architecture-node">Validation-weighted blend<small>α × tree probability + (1−α) × MLP probability</small></div><div className="architecture-arrow"><ArrowDown size={17}/></div>
      <div className="architecture-node">Model probability · SHAP explanation · model-based category · educational insights</div>
    </div></Card>

    <section className="about-section" aria-labelledby="pipeline-heading"><div className="section-heading"><div><h2 id="pipeline-heading">Pipeline details</h2><p>Open a stage for its inputs and interpretation.</p></div></div>
      <div className="pipeline-list">{stages.map((stage, index) => <Card key={stage.title} className="pipeline-stage"><button aria-expanded={expanded === index} onClick={() => setExpanded(expanded === index ? null : index)}><span className="pipeline-number">{String(index + 1).padStart(2, "0")}</span><strong>{stage.title}</strong>{expanded === index ? <ChevronUp size={17}/> : <ChevronDown size={17}/>}</button>{expanded === index && <p>{stage.detail}</p>}</Card>)}</div>
    </section>

    <section className="about-section" aria-labelledby="meaning-heading"><div className="section-heading"><div><h2 id="meaning-heading">How to read the output</h2><p>Keep model estimates separate from clinical interpretation.</p></div></div>
      <div className="output-meaning-grid"><Card><Activity size={18}/><h3>Probability</h3><p>The model’s estimated target probability for a 10-year CHD outcome in this dataset.</p></Card><Card><Sparkles size={18}/><h3>Feature contribution</h3><p>SHAP values describe which inputs moved the model output higher or lower; they do not establish cause and effect.</p></Card><Card><GitMerge size={18}/><h3>Risk category</h3><p>Low, moderate, and high are configurable model bands that have not been clinically validated.</p></Card></div>
    </section>
  </motion.div>;
}

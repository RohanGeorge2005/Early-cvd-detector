"use client";
import { motion } from "framer-motion";
import { Database, FileSearch, LockKeyhole, ShieldCheck } from "lucide-react";
import { Card } from "@/components/ui/card";

const facts = [
  { icon: Database, title: "Dataset and inputs", body: "The model uses the 15 predictors defined by the supplied Framingham-style dataset and the TenYearCHD target. The assessment form does not ask for patient identifiers, ECG, imaging, or wearable data." },
  { icon: FileSearch, title: "Model and evaluation", body: "Logistic Regression, Random Forest, and XGBoost are compared with a tabular MLP and a validation-weighted hybrid output. Evaluation values come from a held-out split in the saved model metadata." },
  { icon: ShieldCheck, title: "Explanations and categories", body: "SHAP values describe how inputs contributed to a model output. They are not causal explanations. Low, moderate, and high are configurable model-based probability bands without clinical validation." },
  { icon: LockKeyhole, title: "Privacy and session handling", body: "Assessment inputs are held in application memory and sent to the configured local FastAPI service only when you request a prediction or PDF. The app does not save a patient history; in-memory session activity clears on refresh." },
];

export default function AboutPage() {
  return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <div className="page-heading"><div className="eyebrow">Scope, methods, and limitations</div><h1 className="page-title">About XAI-CVD</h1><p className="page-subtitle">An academic project exploring how machine learning and explainability can support cardiovascular risk research.</p></div>
    <div className="about-disclaimer" role="note"><ShieldCheck size={19}/><div><strong>Educational and research prototype only</strong><p>This system does not provide a medical diagnosis and should not replace advice from a qualified healthcare professional. Do not use it to make clinical decisions.</p></div></div>
    <div className="about-facts">{facts.map(({ icon: Icon, title, body }) => <Card key={title} className="about-fact"><Icon size={19} aria-hidden="true"/><div><h2>{title}</h2><p>{body}</p></div></Card>)}</div>

    <section className="about-section" aria-labelledby="method-heading"><div className="section-heading"><div><h2 id="method-heading">How the assessment works</h2><p>Training is separate from prediction; the web app loads the saved model bundle.</p></div></div>
      <Card className="method-card"><ol className="method-steps"><li><span>1</span><div><strong>Patient inputs</strong><p>Validate the dataset’s 15 predictors.</p></div></li><li><span>2</span><div><strong>Trained preprocessing</strong><p>Apply saved transformations fitted during training.</p></div></li><li><span>3</span><div><strong>Model outputs</strong><p>Combine the selected tree model and tabular MLP using the saved blend weight.</p></div></li><li><span>4</span><div><strong>Explanation and report</strong><p>Return probability, SHAP contributions, model category, decision-support notes, and an optional PDF.</p></div></li></ol></Card>
    </section>

    <section className="about-section" aria-labelledby="limits-heading"><div className="section-heading"><div><h2 id="limits-heading">Limitations to keep in view</h2><p>Interpretation depends on the supplied dataset, the fitted model, and the entered values.</p></div></div>
      <Card><ul className="limitation-list"><li>Model performance on a held-out split does not show how well it will work in a different population or clinical setting.</li><li>A probability is a model estimate, not an individualized clinical risk calculation.</li><li>SHAP explains associations learned by the model. It does not prove medical causation or predict the effect of changing an input.</li><li>Model-based categories and simple decision-support topics have not been clinically validated.</li></ul></Card>
    </section>
  </motion.div>;
}

"use client";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, CheckCircle2, FileText, LoaderCircle, TriangleAlert, Upload } from "lucide-react";
import { ResultView } from "@/components/assessment/result-view";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAssessment } from "@/components/providers";
import { api, ApiError } from "@/lib/api";
import type { PatientFeature, PatientInput, ReportField, ReportJob, PredictionResponse } from "@/lib/types";

const LIMIT = 10 * 1024 * 1024;
const SPECS: { key: PatientFeature; label: string; unit: string; min: number; max: number; choices?: [number, string][] }[] = [
  { key:"gender", label:"Sex", unit:"", min:0, max:1, choices:[[0,"Female"],[1,"Male"]] },
  { key:"age", label:"Age", unit:"years", min:18, max:120 },
  { key:"education", label:"Education level", unit:"", min:1, max:4, choices:[[1,"Level 1"],[2,"Level 2"],[3,"Level 3"],[4,"Level 4"]] },
  { key:"currentSmoker", label:"Current smoker", unit:"", min:0, max:1, choices:[[0,"No"],[1,"Yes"]] },
  { key:"cigsPerDay", label:"Cigarettes per day", unit:"/day", min:0, max:100 },
  { key:"BPMeds", label:"Blood pressure medication", unit:"", min:0, max:1, choices:[[0,"No"],[1,"Yes"]] },
  { key:"prevalentStroke", label:"Previous stroke", unit:"", min:0, max:1, choices:[[0,"No"],[1,"Yes"]] },
  { key:"prevalentHyp", label:"Hypertension history", unit:"", min:0, max:1, choices:[[0,"No"],[1,"Yes"]] },
  { key:"diabetes", label:"Diabetes", unit:"", min:0, max:1, choices:[[0,"No"],[1,"Yes"]] },
  { key:"totChol", label:"Total cholesterol", unit:"mg/dL", min:50, max:700 },
  { key:"sysBP", label:"Systolic blood pressure", unit:"mmHg", min:50, max:300 },
  { key:"diaBP", label:"Diastolic blood pressure", unit:"mmHg", min:30, max:200 },
  { key:"BMI", label:"Body mass index", unit:"kg/m²", min:10, max:100 },
  { key:"heartRate", label:"Resting heart rate", unit:"bpm", min:25, max:250 },
  { key:"glucose", label:"Glucose", unit:"mg/dL", min:20, max:1000 },
];
const emptyValues = () => Object.fromEntries(SPECS.map(field => [field.key, ""])) as Record<PatientFeature, string>;
const allowedTypes = ".pdf,.jpg,.jpeg,.png,.csv,.xlsx";
const allowedExtensions = new Set(["pdf", "jpg", "jpeg", "png", "csv", "xlsx"]);

function confidenceName(value: number) { return value >= .85 ? "High" : value >= .65 ? "Review" : "Low"; }
function fieldValidity(spec: typeof SPECS[number], raw: string): string | null {
  if (!raw.trim()) return "Required — enter a value from the report or another trusted source.";
  const value = Number(raw);
  if (!Number.isFinite(value)) return "Enter a valid number.";
  if (value < spec.min || value > spec.max) return `Outside accepted input range (${spec.min}–${spec.max}${spec.unit ? ` ${spec.unit}` : ""}).`;
  if (spec.choices && !spec.choices.some(([choice]) => choice === value)) return "Choose one of the listed values.";
  return null;
}

export default function ReportAnalysisPage() {
  const { setPatient, setResult, recordAssessment } = useAssessment();
  const [job, setJob] = useState<ReportJob | null>(null);
  const [selectedName, setSelectedName] = useState("");
  const [values, setValues] = useState<Record<PatientFeature, string>>(emptyValues);
  const [progress, setProgress] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [assessment, setAssessment] = useState<{ patient: PatientInput; result: PredictionResponse } | null>(null);
  const fields: ReportField[] = job?.result?.fields || [];
  const problems = useMemo(() => SPECS.flatMap(spec => {
    const issue = fieldValidity(spec, values[spec.key]);
    return issue ? [{ key: spec.key, issue }] : [];
  }), [values]);

  async function processFile(file?: File) {
    if (!file) return;
    setError(""); setAssessment(null); setJob(null); setProgress(0); setConfirmed(false); setValues(emptyValues()); setSelectedName(""); setPatient(null); setResult(null);
    const ext = file.name.split(".").pop()?.toLowerCase() || "";
    if (!allowedExtensions.has(ext)) { setError("Choose a PDF, JPG, PNG, CSV or XLSX report."); return; }
    if (file.size <= 0 || file.size > LIMIT) { setError("Choose a non-empty file no larger than 10 MB."); return; }
    setSelectedName(file.name); setBusy(true);
    try {
      let current = await api.uploadReport(file, setProgress);
      setJob(current);
      const startedAt = Date.now();
      while (current.status === "processing") {
        if (Date.now() - startedAt > 5 * 60_000) throw new ApiError("Extraction is taking longer than expected. You can retry the upload.");
        await new Promise(resolve => setTimeout(resolve, 800));
        current = await api.reportExtraction(current.analysis_id);
        setJob(current); setProgress(old => Math.max(old, current.progress));
      }
      if (current.status === "failed") throw new ApiError(current.error || "Report extraction failed.");
      if (!current.result) throw new ApiError("The extraction completed without reviewable fields. Try another file.");
      setValues(Object.fromEntries(current.result.fields.map(field => [field.feature, field.value === null ? "" : String(field.value)])) as Record<PatientFeature, string>);
      setProgress(100);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Report extraction failed. Check the file and try again.");
    } finally { setBusy(false); }
  }

  async function assessConfirmed() {
    setError("");
    if (problems.length || !confirmed) { setError("Complete every field, correct flagged values, and confirm that you reviewed the extracted values before assessing."); return; }
    const patient = Object.fromEntries(SPECS.map(spec => [spec.key, Number(values[spec.key])])) as unknown as PatientInput;
    setBusy(true);
    try {
      const result = await api.predict(patient);
      setPatient(patient); setResult(result); recordAssessment(patient, result); setAssessment({ patient, result });
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "The assessment could not be completed.");
    } finally { setBusy(false); }
  }

  const edit = (field: PatientFeature, value: string) => {
    setValues(current => ({ ...current, [field]: value })); setConfirmed(false); setAssessment(null); setPatient(null); setResult(null);
  };
  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault(); setDragging(false); void processFile(event.dataTransfer.files?.[0]);
  };

  return <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}}>
    <div className="page-heading"><div className="eyebrow"><FileText size={14}/> Report upload</div><h1 className="page-title">Report analysis</h1><p className="page-subtitle">Extract candidate values from a medical report, review every field, then explicitly confirm before a model assessment. Files are processed locally and not saved by the app.</p></div>
    <Card className={`report-dropzone ${dragging ? "report-dropzone-active" : ""}`} onDragOver={(event: React.DragEvent<HTMLDivElement>) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={handleDrop}>
      <div className="empty-icon"><Upload size={20}/></div><h2>Upload a patient report</h2><p>Drag a file here or choose one from your device. Supported: PDF, JPG, PNG, CSV, XLSX · up to 10 MB.</p>
      <label className="button button-secondary report-file-button">Choose report<input type="file" accept={allowedTypes} disabled={busy} onChange={event => { void processFile(event.currentTarget.files?.[0]); event.currentTarget.value = ""; }}/></label>
      {selectedName && <div className="report-selected"><FileText size={13}/><span>{selectedName}</span></div>}
      {busy && <div className="report-progress" role="status"><div className="report-progress-head"><span><LoaderCircle size={13} className="spinner"/> {job?.stage || "Uploading report"}</span><b>{Math.round(progress)}%</b></div><div className="report-progress-track"><i style={{width:`${progress}%`}}/></div></div>}
    </Card>
    {error && <div className="alert" role="alert">{error}</div>}
    {job?.status === "failed" && job.error && <div className="alert" role="alert">{job.error}</div>}
    {job?.status === "completed" && job.result && <>
      <div className="section-heading"><div><h2>Review and confirm extracted values</h2><p>Every model input is required. Missing values remain blank; the system never fills them automatically.</p></div></div>
      <div className="alert alert-info">{job.result.extraction_note} Confirmed values will be sent to the local prediction API.</div>
      <Card className="table-wrap"><table className="data-table report-review-table"><thead><tr><th>Model input</th><th>Proposed value</th><th>Confidence</th><th>Source evidence</th></tr></thead><tbody>
        {SPECS.map(spec => {
          const field = fields.find(item => item.feature === spec.key);
          const issue = fieldValidity(spec, values[spec.key]);
          const confidence = field?.confidence || 0;
          return <tr key={spec.key} className={issue ? "report-row-flagged" : ""}>
            <td><strong>{spec.label}</strong><small>{spec.unit || "Dataset coded value"}</small>{issue && <small className="report-field-error">{issue}</small>}</td>
            <td>{spec.choices ? <select className="select report-review-input" aria-label={spec.label} value={values[spec.key]} onChange={event => edit(spec.key, event.target.value)}><option value="">Not provided</option>{spec.choices.map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select> : <input className="input report-review-input" aria-label={spec.label} type="number" min={spec.min} max={spec.max} step="any" value={values[spec.key]} onChange={event => edit(spec.key, event.target.value)}/>}</td>
            <td><span className={`confidence-pill confidence-${confidenceName(confidence).toLowerCase()}`}>{field?.status === "missing" ? "Missing" : `${confidenceName(confidence)} · ${Math.round(confidence*100)}%`}</span>{field?.source_unit && field.source_unit.toLowerCase().includes("mmol") && <small>Converted to {spec.unit}</small>}</td>
            <td><span className="report-source">{field?.source_snippet || "No source value found"}</span>{field?.page && <small>Page {field.page}</small>}{field?.issues.map((item,index) => <small className="report-field-error" key={index}>{item}</small>)}</td>
          </tr>;
        })}
      </tbody></table></Card>
      <Card className="report-confirm-card"><div className="report-confirm-copy"><strong>Required before prediction</strong><span>{problems.length ? `${problems.length} input${problems.length===1?" is":"s are"} missing or invalid. Complete them above.` : "All 15 inputs are within accepted bounds. Review each source and confirm."}</span></div><label className="report-confirm-check"><input type="checkbox" checked={confirmed} disabled={problems.length>0 || busy} onChange={event => { setConfirmed(event.target.checked); setAssessment(null); }}/><span>I reviewed and confirm all 15 values are correct for this assessment.</span></label><Button onClick={assessConfirmed} disabled={busy || problems.length>0 || !confirmed}>{busy ? <><LoaderCircle className="spinner"/> Assessing…</> : <>Confirm & assess <ArrowRight size={14}/></>}</Button></Card>
    </>}
    {assessment && <><ResultView patient={assessment.patient} result={assessment.result}/><Card className="report-next-step"><CheckCircle2 size={17}/><div><strong>Assessment added to this session</strong><span>It is now available on the Reports page for PDF preview and download. No report history is stored between sessions.</span></div><a className="button button-secondary" href="/reports">Open Reports <ArrowRight size={13}/></a></Card></>}
    <div className="alert alert-info" style={{marginTop:16}}><TriangleAlert size={13} style={{verticalAlign:"middle",marginRight:5}}/>Extraction can misread scanned or poorly formatted reports. Verify each proposed value against its source before confirming.</div>
  </motion.div>;
}

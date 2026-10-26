"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, FileText, HeartPulse, LoaderCircle, RotateCcw } from "lucide-react";
import { useAssessment } from "@/components/providers";
import { ResultView } from "@/components/assessment/result-view";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import type { PatientInput } from "@/lib/types";

const defaults: PatientInput = { gender:0, age:50, education:2, currentSmoker:0, cigsPerDay:0, BPMeds:0, prevalentStroke:0, prevalentHyp:0, diabetes:0, totChol:200, sysBP:120, diaBP:80, BMI:25, heartRate:70, glucose:100 };
const stepNames = ["Patient profile","Lifestyle","Medical history","Measurements","Assessment"];
type Field = {key:keyof PatientInput;label:string;type?:string;options?:[number,string][];min?:number;max?:number;unit?:string};
const fields: Field[][] = [
  [{key:"gender",label:"Gender",type:"seg",options:[[0,"Female"],[1,"Male"]]},{key:"age",label:"Age",min:18,max:120,unit:"years"},{key:"education",label:"Education level",type:"select",options:[[1,"Level 1"],[2,"Level 2"],[3,"Level 3"],[4,"Level 4"]]}],
  [{key:"currentSmoker",label:"Current smoker",type:"seg",options:[[0,"No"],[1,"Yes"]]},{key:"cigsPerDay",label:"Cigarettes per day",min:0,max:100,unit:"per day"}],
  [{key:"BPMeds",label:"On blood pressure medication",type:"seg",options:[[0,"No"],[1,"Yes"]]},{key:"prevalentStroke",label:"Previous stroke",type:"seg",options:[[0,"No"],[1,"Yes"]]},{key:"prevalentHyp",label:"Hypertension",type:"seg",options:[[0,"No"],[1,"Yes"]]},{key:"diabetes",label:"Diabetes",type:"seg",options:[[0,"No"],[1,"Yes"]]}],
  [{key:"totChol",label:"Total cholesterol",min:50,max:700,unit:"mg/dL"},{key:"sysBP",label:"Systolic blood pressure",min:50,max:300,unit:"mmHg"},{key:"diaBP",label:"Diastolic blood pressure",min:30,max:200,unit:"mmHg"},{key:"BMI",label:"Body mass index",min:10,max:100,unit:"kg/m²"},{key:"heartRate",label:"Resting heart rate",min:25,max:250,unit:"bpm"},{key:"glucose",label:"Fasting glucose",min:20,max:1000,unit:"mg/dL"}],
];
export default function AssessmentPage() {
  const {patient,setPatient,result,setResult,recordAssessment}=useAssessment(); const [values,setValues]=useState<PatientInput>(patient||defaults); const [step,setStep]=useState(0); const [loading,setLoading]=useState(false); const [error,setError]=useState("");
  const [patientId,setPatientId]=useState<string|null>(null); const [patientRef,setPatientRef]=useState("");
  useEffect(()=>{const id=new URLSearchParams(window.location.search).get("patientId");setPatientId(id);if(id){api.patient(id).then(p=>setPatientRef(`${p.patient_ref} · ${p.profile?.name||""}`)).catch(e=>setError(e instanceof ApiError?e.message:"Unable to verify patient record."));}},[]);
  const update=(key:keyof PatientInput,value:number)=>{setValues(v=>({...v,[key]:value}));setResult(null);setPatient(null);};
  function validateStep(index:number) {
    for (const field of fields[index] || []) {
      const value = values[field.key];
      if (!Number.isFinite(value) || (field.min !== undefined && value < field.min) || (field.max !== undefined && value > field.max)) {
        return `${field.label} must be within ${field.min ?? "the accepted"}–${field.max ?? "entry"} ${field.unit || "range"}. These bounds catch entry errors; they are not clinical thresholds.`;
      }
    }
    return "";
  }
  async function assess(){const issue=fields.map((_,index)=>validateStep(index)).find(Boolean);if(issue){setError(issue);return;}setLoading(true);setError("");try{const response=patientId?(await api.patientAssessment(patientId,values)).result:await api.predict(values);setPatient({...values});setResult(response);recordAssessment(values,response);setStep(4);}catch(e){setError(e instanceof ApiError?e.message:"Assessment could not be completed.");}finally{setLoading(false);}}
  const labels:Array<[string,string]>=[["Profile",`${values.age} years · ${values.gender?"Male":"Female"}`],["Lifestyle",`${values.currentSmoker?"Smoker":"Non-smoker"} · ${values.cigsPerDay}/day`],["Medical history",[values.BPMeds&&"BP meds",values.prevalentStroke&&"Stroke",values.prevalentHyp&&"Hypertension",values.diabetes&&"Diabetes"].filter(Boolean).join(", ")||"None selected"],["Measurements",`Chol ${values.totChol} · BP ${values.sysBP}/${values.diaBP} · BMI ${values.BMI}`],["Additional",`HR ${values.heartRate} · glucose ${values.glucose}`]];
  return <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}}><div className="page-heading"><div className="eyebrow"><HeartPulse size={14}/> {patientId?`Saved patient assessment · ${patientRef||"Verifying record…"}`:"Session-only inputs · 15 dataset predictors"}</div><h1 className="page-title">Cardiovascular risk assessment</h1><p className="page-subtitle">{patientId?"This assessment will be stored in the selected patient's encrypted local record.":"Enter the dataset predictors in five short steps. Values are held in application memory for this session and sent to the local FastAPI service only when you assess."}</p><Link href="/report-analysis"><Button variant="secondary"><FileText size={14}/> Upload a medical report instead</Button></Link></div>
    <div className="stepper" aria-label={`Step ${step+1} of 5`}>{stepNames.map((name,i)=><div key={name} style={{display:"contents"}}><div className={`step-chip ${step===i?"active":""} ${step>i?"done":""}`} aria-current={step===i?"step":undefined}><b>{step>i?"✓":`0${i+1}`}</b><span>{name}</span></div>{i<4&&<div className="step-connector"/>}</div>)}</div>
    <div className="assessment-layout"><Card className="form-card"><AnimatePresence mode="wait"><motion.div key={step} initial={{opacity:0,x:8}} animate={{opacity:1,x:0}} exit={{opacity:0,x:-8}} transition={{duration:.16}}>
      <h2>{step<4?stepNames[step]:"Review and assess"}</h2><p>{step<4?"Enter the values provided for this assessment. Input bounds catch entry errors; they are not diagnostic thresholds.":"Review the current form values, then request an assessment from the trained model."}</p>
      {step<4?<div className="field-grid">{fields[step].map(field=><div className="field" key={field.key}><label htmlFor={field.key}>{field.label}{field.unit?` · ${field.unit}`:""}</label>{field.type==="seg"?<div className="segmented" role="group" aria-label={field.label}>{field.options!.map(([value,label])=><button key={value} type="button" aria-pressed={values[field.key]===value} className={`segment ${values[field.key]===value?"selected":""}`} onClick={()=>update(field.key,value)}>{label}</button>)}</div>:field.type==="select"?<select id={field.key} className="select" value={values[field.key]} onChange={e=>update(field.key,Number(e.target.value))}>{field.options!.map(([v,label])=><option key={v} value={v}>{label}</option>)}</select>:<input id={field.key} className="input" type="number" min={field.min} max={field.max} step="any" value={values[field.key]} onChange={e=>update(field.key,Number(e.target.value))} aria-describedby={`${field.key}-help`}/>}<small id={`${field.key}-help`}>Allowed entry range {field.min!==undefined?`${field.min}–${field.max} ${field.unit}`:"as encoded in the dataset"} · not a clinical threshold</small></div>)}</div>:<div className="review-list">{labels.map(([label,value])=><div key={label} className="review-row"><span>{label}</span><b>{value}</b></div>)}</div>}
    </motion.div></AnimatePresence>
    {error&&<div className="alert" role="alert">{error}</div>}
    <div className="form-actions">{step>0?<Button variant="ghost" onClick={()=>{setStep(s=>s-1);setError("");}}><ArrowLeft size={14}/> Back</Button>:<span/>}{step<4?<Button onClick={()=>{const issue=validateStep(step);if(issue){setError(issue);return;}setStep(s=>s+1);setError("");}}>Continue <ArrowRight size={14}/></Button>:<Button onClick={assess} disabled={loading}>{loading?<><LoaderCircle className="spinner" size={14}/> Requesting assessment…</>:<>Assess cardiovascular risk <ArrowRight size={14}/></>}</Button>}</div>
    </Card><div style={{display:"grid",gap:12}}><Card><div className="eyebrow">Live review</div><h3 className="card-title" style={{marginTop:6}}>Current form values</h3><p className="card-description">Step {String(step+1).padStart(2,"0")} of 05 · kept in memory</p><div className="review-list" style={{marginTop:10}}>{labels.map(([label,value])=><div key={label} className="review-row"><span>{label}</span><b>{value}</b></div>)}</div><div className="alert alert-info">These fields are an editable starting profile. Confirm all values before requesting a prediction.</div></Card><Card><div className="eyebrow">Assessment status</div><h3 className="card-title" style={{marginTop:6}}>{result?"Assessment prepared":"Not assessed"}</h3><p className="card-description">{result?"Current output is from the connected trained model.":"Complete all steps to request a result. No probability is estimated before submission."}</p>{result&&<div className="review-row" style={{marginTop:12}}><span>Current estimate</span><b>{(result.probability*100).toFixed(0)}% · {result.risk_category}</b></div>}</Card></div></div>
    {result&&patient&&<ResultView result={result} patient={patient}/>}
    {result&&<div style={{display:"flex",justifyContent:"flex-end",marginTop:15}}><Button variant="secondary" onClick={()=>{setResult(null);setStep(0);setValues({...defaults});}}><RotateCcw size={13}/> Start a new assessment</Button></div>}
  </motion.div>;
}

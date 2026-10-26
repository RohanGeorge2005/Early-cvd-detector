"use client";
import { createContext, useContext, useMemo, useState } from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";
import type { AssessmentRecord, PatientInput, PredictionResponse } from "@/lib/types";

interface AssessmentState {
  patient: PatientInput | null;
  setPatient: Dispatch<SetStateAction<PatientInput | null>>;
  result: PredictionResponse | null;
  setResult: Dispatch<SetStateAction<PredictionResponse | null>>;
  assessments: AssessmentRecord[];
  recordAssessment: (patient: PatientInput, result: PredictionResponse) => void;
  markReportGenerated: (id: string) => void;
}
const AssessmentContext = createContext<AssessmentState | null>(null);
export function Providers({ children }: { children: ReactNode }) {
  const [patient, setPatient] = useState<PatientInput | null>(null);
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [assessments, setAssessments] = useState<AssessmentRecord[]>([]);
  const recordAssessment = (nextPatient: PatientInput, nextResult: PredictionResponse) => {
    const id = nextResult.assessment_id;
    setAssessments(records => [{ id, assessedAt: nextResult.assessed_at, patient: { ...nextPatient }, result: nextResult, reportGenerated: false }, ...records]);
  };
  const markReportGenerated = (id: string) => setAssessments(records => records.map(record => record.id === id ? { ...record, reportGenerated: true } : record));
  const value = useMemo(() => ({ patient, setPatient, result, setResult, assessments, recordAssessment, markReportGenerated }), [patient, result, assessments]);
  return <AssessmentContext.Provider value={value}>{children}</AssessmentContext.Provider>;
}
export function useAssessment() {
  const value = useContext(AssessmentContext);
  if (!value) throw new Error("useAssessment must be used inside Providers");
  return value;
}

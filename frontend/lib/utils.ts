import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }

export const FEATURE_LABELS: Record<string, string> = {
  gender:"Gender", age:"Age", education:"Education", currentSmoker:"Current smoker", cigsPerDay:"Cigarettes per day",
  BPMeds:"Blood pressure medication", prevalentStroke:"Previous stroke", prevalentHyp:"Hypertension", diabetes:"Diabetes",
  totChol:"Total cholesterol", sysBP:"Systolic blood pressure", diaBP:"Diastolic blood pressure", BMI:"BMI", heartRate:"Resting heart rate", glucose:"Fasting glucose",
};
export const formatFeatureValue = (key: string, value: number) => {
  if (["gender","currentSmoker","BPMeds","prevalentStroke","prevalentHyp","diabetes"].includes(key)) return key === "gender" ? (value ? "Male" : "Female") : value ? "Yes" : "No";
  if (key === "education") return `Level ${value}`;
  const unit: Record<string,string> = {age:"years",cigsPerDay:"per day",totChol:"mg/dL",sysBP:"mmHg",diaBP:"mmHg",BMI:"kg/m²",heartRate:"bpm",glucose:"mg/dL"};
  return `${value} ${unit[key] || ""}`.trim();
};

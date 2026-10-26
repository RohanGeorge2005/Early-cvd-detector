export interface PatientInput {
  gender: number; age: number; education: number; currentSmoker: number;
  cigsPerDay: number; BPMeds: number; prevalentStroke: number;
  prevalentHyp: number; diabetes: number; totChol: number; sysBP: number;
  diaBP: number; BMI: number; heartRate: number; glucose: number;
}
export interface AssessmentRecord {
  id: string;
  assessedAt: string;
  patient: PatientInput;
  result: PredictionResponse;
  reportGenerated: boolean;
}
export type PatientFeature = keyof PatientInput;
export interface ReportField {
  feature: PatientFeature; label: string; value: number | null; unit: string | null;
  source_unit: string | null; confidence: number;
  status: "found" | "missing" | "ambiguous" | "out_of_range" | "low_confidence";
  source_snippet: string | null; page: number | null; issues: string[];
}
export interface ReportExtraction {
  fields: ReportField[]; requires_user_confirmation: boolean; extraction_note: string;
}
export interface ReportJob {
  analysis_id: string; status: "processing" | "completed" | "failed";
  progress: number; stage: string; result?: ReportExtraction | null; error?: string | null;
}

export interface Factor { feature: keyof PatientInput; value?: number; contribution: number; direction?: string }
export interface PredictionResponse {
  assessment_id: string; assessed_at: string; model_version: string;
  prediction: 0 | 1; probability: number; risk_category: "LOW" | "MODERATE" | "HIGH";
  binary_label: string; model_threshold: number; alpha: number; tree_component: string;
  ml_probability: number; dl_probability: number; hybrid_probability: number;
  model_outputs: Record<string, number>; model_consensus: boolean;
  model_consensus_count: number; model_consensus_total: number; model_agreement_note: string;
  top_factors: Factor[]; top_features: Factor[]; shap_values: Factor[];
  shap_base_value: number; feature_order: string[]; decision_support: string[]; disclaimer: string;
}

export interface ModelMetric {
  accuracy: number; precision: number; recall: number; f1: number; roc_auc: number;
  confusion_matrix: number[][]; roc_curve: { fpr: number[]; tpr: number[]; thresholds?: number[] };
}
export interface PerformanceResponse {
  selected_model: string; selected_tree_model?: string; best_model_by_composite: string;
  comparison: Record<string, unknown>; metrics: Record<string, ModelMetric>;
}
export interface GlobalXAI { method?: string; feature_importance: { feature: string; importance: number }[]; feature_distributions?: { feature: string; q05: number; q25: number; median: number; q75: number; q95: number }[]; causation_note?: string }
export interface DatasetAudit { available: boolean; rows_before_cleaning?: number; rows_after_cleaning?: number; columns?: number; duplicate_rows_removed?: number; class_distribution?: Record<string, number> }
export interface NetworkNode {
  id: string; label: string; short_label: string; category: string; unit: string;
  description: string;
  statistics: { observations: number; missing: number; mean: number | null; median: number | null;
    minimum: number | null; maximum: number | null; value_one_label?: string;
    value_one_count?: number; value_one_percent?: number };
}
export interface NetworkEdge {
  source: string; target: string; correlation: number; strength: number;
  p_value: number; q_value: number; sample_size: number; method: string;
}
export interface RiskNetworkResponse {
  source_file: string; rows: number; feature_count: number; target_excluded: boolean;
  minimum_pairwise_observations: number; association_method: string; multiple_testing: string;
  p_value_method?: string;
  tested_pair_count: number; edge_count: number; nodes: NetworkNode[]; edges: NetworkEdge[];
}

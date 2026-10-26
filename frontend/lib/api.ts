import type { DatasetAudit, GlobalXAI, PatientInput, PerformanceResponse, PredictionResponse, ReportJob, RiskNetworkResponse } from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || (typeof window !== "undefined" ? `${window.location.protocol}//${window.location.hostname}:8000` : "http://localhost:8000")).replace(/\/$/, "");
export class ApiError extends Error {
  constructor(message: string, public status?: number) { super(message); this.name = "ApiError"; }
}

function uploadReport(file: File, onProgress: (percent: number) => void): Promise<ReportJob> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const body = new FormData(); body.append("file", file);
    xhr.open("POST", `${API_URL}/api/reports/upload`);
    xhr.upload.onprogress = event => {
      if (event.lengthComputable) onProgress(Math.min(35, Math.round(event.loaded / event.total * 35)));
    };
    xhr.onerror = () => reject(new ApiError("Cannot reach the local report extraction API."));
    xhr.ontimeout = () => reject(new ApiError("The report upload timed out."));
    xhr.timeout = 120_000;
    xhr.onload = () => {
      let response: ReportJob & { detail?: string };
      try { response = JSON.parse(xhr.responseText); }
      catch { reject(new ApiError(`Upload failed (${xhr.status}).`)); return; }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new ApiError(response.detail || `Upload failed (${xhr.status}).`, xhr.status)); return;
      }
      onProgress(Math.max(35, response.progress || 35)); resolve(response);
    };
    xhr.send(body);
  });
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 30_000): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers = new Headers(init?.headers);
    if (init?.method && init.method !== "GET") {
      const csrf = document.cookie.split(";").map(item => item.trim()).find(item => item.startsWith("xai_csrf="))?.split("=").slice(1).join("=");
      if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
    }
    const response = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: "include", signal: controller.signal, cache: "no-store" });
    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      try { const body = await response.json(); detail = body.detail || detail; } catch { /* keep status message */ }
      throw new ApiError(detail, response.status);
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") throw new ApiError("The API request timed out. Please try again.");
    throw new ApiError("Cannot reach the XAI-CVD API. Start the FastAPI server and try again.");
  } finally { clearTimeout(timeout); }
}

export const api = {
  health: () => request<{ status: string; model_ready: boolean }>("/health"),
  predict: (patient: PatientInput) => request<PredictionResponse>("/predict", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patient),
  }, 120_000),
  performance: () => request<PerformanceResponse>("/model-performance"),
  globalXai: () => request<GlobalXAI>("/xai/global"),
  datasetAudit: () => request<DatasetAudit>("/dataset-audit"),
  riskNetwork: () => request<RiskNetworkResponse>("/risk-factor-network"),
  authStatus: () => request<{ authenticated: boolean; user: { id: string; username: string; role: string; patient_id?: string | null } | null }>("/api/auth/status"),
  login: (username: string, password: string) => request<{ user: { id: string; username: string; role: string; patient_id?: string | null } }>("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) }),
  activatePortal: (token: string, username: string, password: string) => request<{ user: { id: string; username: string; role: string } }>("/api/portal/activate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, username, password }) }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  patients: (search = "", offset = 0, limit = 25) => request<{ items: PatientSummary[]; total: number; offset: number; limit: number }>(`/api/patients?search=${encodeURIComponent(search)}&offset=${offset}&limit=${limit}`),
  createPatient: (profile: PatientProfile) => request<PatientSummary>("/api/patients", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profile) }),
  patient: (id: string) => request<PatientSummary & { profile: PatientProfile; created_at: string }>(`/api/patients/${encodeURIComponent(id)}`),
  updatePatient: (id: string, profile: Partial<PatientProfile>) => request<PatientSummary>(`/api/patients/${encodeURIComponent(id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profile) }),
  assessments: (id: string) => request<{ items: StoredAssessment[] }>(`/api/patients/${encodeURIComponent(id)}/assessments`),
  patientReports: (id: string) => request<{ items: PatientReport[] }>(`/api/patients/${encodeURIComponent(id)}/reports`),
  patientAssessment: (id: string, values: PatientInput) => request<StoredAssessment>(`/api/patients/${encodeURIComponent(id)}/assessments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) }, 120_000),
  invitePortal: (id: string) => request<{ activation_code: string; expires_at: string; notice: string }>(`/api/patients/${encodeURIComponent(id)}/portal-invite`, { method: "POST" }),
  revokePortal: (id: string) => request<{ portal_active: boolean }>(`/api/patients/${encodeURIComponent(id)}/portal-revoke`, { method: "POST" }),
  portalHome: () => request<PortalHome>("/api/portal/me"),
  reviewQueue: () => request<{ items: PatientReport[] }>("/api/reports/review-queue"),
  reviewReport: (id: string) => request<PatientReport>(`/api/reports/${encodeURIComponent(id)}/review`, { method: "POST" }),
  releaseReport: (id: string) => request<PatientReport>(`/api/reports/${encodeURIComponent(id)}/release`, { method: "POST" }),
  createPatientReport: (assessmentId: string) => request<PatientReport>(`/api/assessments/${encodeURIComponent(assessmentId)}/report`, { method: "POST" }, 120_000),
  reportPdf: (patientId: string, reportId: string) => requestBlob(`/api/patients/${encodeURIComponent(patientId)}/reports/${encodeURIComponent(reportId)}/pdf`),
  portalReportPdf: (reportId: string) => requestBlob(`/api/portal/reports/${encodeURIComponent(reportId)}/pdf`),
  uploadReport,
  reportExtraction: (analysisId: string) => request<ReportJob>(`/api/reports/${encodeURIComponent(analysisId)}`),
  report: async (assessmentId: string): Promise<Blob> => {
    const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 120_000);
    try {
      const response = await fetch(`${API_URL}/generate-assessment-report`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ assessment_id: assessmentId }), signal: controller.signal });
      if (!response.ok) {
        let detail = `Report request failed (${response.status})`;
        try { detail = (await response.json()).detail || detail; } catch { /* keep status message */ }
        throw new ApiError(detail, response.status);
      }
      return await response.blob();
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError("Could not reach the report service. Check that the API is running.");
    } finally { clearTimeout(timeout); }
  },
};

async function requestBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_URL}${path}`, { credentials: "include", cache: "no-store" });
  if (!response.ok) throw new ApiError(response.status === 401 ? "Please sign in to access this record." : `Request failed (${response.status}).`, response.status);
  return response.blob();
}

export interface PatientProfile { name: string; date_of_birth?: string | null; email?: string | null; phone?: string | null; preferred_contact?: string; consent_recorded: boolean; consent_note?: string; }
export interface PatientSummary { id: string; patient_ref: string; profile?: PatientProfile; created_at: string; assessment_count: number; latest_assessment?: string | null; latest_report_status?: string | null; portal_active: boolean; }
export interface StoredAssessment { assessment_id: string; patient_id: string; assessed_at: string; model_version: string; patient: PatientInput; result: PredictionResponse; }
export interface PatientReport { report_id: string; patient_id: string; assessment_id: string; version: number; status: string; created_at: string; reviewed_at?: string | null; released_at?: string | null; }
export interface PortalHome { patient: { id: string; patient_ref: string; name: string }; assessments: Array<{ assessment_id: string; assessed_at: string; model_version: string; risk_category: string; probability: number; released_report?: PatientReport | null }>; reports: PatientReport[]; measurements: Array<Record<string, unknown>>; }

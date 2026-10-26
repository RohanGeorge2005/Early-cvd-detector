import * as FileSystem from "expo-file-system/legacy";

export type User = { id: string; username: string; role: "patient"; patient_id: string };
export type AuthResult = { user: User; access_token: string; token_type: "bearer"; expires_at: string };
export type Report = { report_id: string; assessment_id: string; version: number; status: string; created_at: string };
export type AssessmentSummary = { assessment_id: string; assessed_at: string; model_version: string; probability: number; risk_category: string; released_report?: Report | null };
export type PortalHome = { patient: { id: string; patient_ref: string; name: string }; assessments: AssessmentSummary[]; reports: Report[]; measurements: Measurement[] };
export type Measurement = { assessment_id: string; date: string; totChol: number | null; sysBP: number | null; diaBP: number | null; BMI: number | null; heartRate: number | null; glucose: number | null };
export type Factor = { feature: string; contribution: number; value?: number };
export type AssessmentDetail = { assessment_id: string; assessed_at: string; model_version: string; patient: Record<string, number>; probability: number; risk_category: string; binary_label: string; shap_values: Factor[]; shap_base_value: number; decision_support: string[]; disclaimer: string };
export type Profile = { patient_ref: string; name: string; email: string; phone: string; preferred_contact: string; notification_preferences: { portal_updates: boolean; email: boolean; sms: boolean } };

const base = (process.env.EXPO_PUBLIC_API_URL || "").trim().replace(/\/$/, "");
function apiBase(): string {
  if (!base) throw new Error("Set EXPO_PUBLIC_API_URL in mobile/.env.local to your computer's LAN address and API port 8000.");
  let host: string;
  try { host = new URL(base).hostname; } catch { throw new Error("EXPO_PUBLIC_API_URL must be a valid http(s) URL."); }
  if (["localhost", "127.0.0.1", "::1"].includes(host)) throw new Error("A phone cannot reach the computer through localhost. Set the computer's LAN IPv4 address.");
  if (!base.startsWith("https://") && !isPrivateAddress(host)) throw new Error("Use HTTPS except for a private LAN development address.");
  return base;
}
function isPrivateAddress(host: string) { return /^10\./.test(host) || /^192\.168\./.test(host) || /^172\.(1[6-9]|2\d|3[01])\./.test(host); }
async function request<T>(path: string, token?: string | null, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers }, cache: "no-store" });
  } catch { throw new Error("Cannot reach the XAI-CVD API. Check the LAN address, Wi-Fi, backend, and firewall."); }
  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try { detail = (await response.json()).detail || detail; } catch { /* retain status */ }
    if (response.status === 401) throw new Error("Your session expired. Sign in again.");
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}
export const mobileApi = {
  login: (username: string, password: string) => request<AuthResult>("/api/mobile/auth/login", null, { method: "POST", body: JSON.stringify({ username, password }) }),
  activate: (token: string, username: string, password: string) => request<AuthResult>("/api/mobile/auth/activate", null, { method: "POST", body: JSON.stringify({ token, username, password }) }),
  logout: (token: string) => request<{ ok: boolean }>("/api/mobile/auth/logout", token, { method: "POST" }),
  home: (token: string) => request<PortalHome>("/api/portal/me", token),
  profile: (token: string) => request<Profile>("/api/portal/profile", token),
  savePreferences: (token: string, profile: Pick<Profile, "preferred_contact" | "notification_preferences">) => request<Profile>("/api/portal/preferences", token, { method: "PATCH", body: JSON.stringify(profile) }),
  assessment: (id: string, token: string) => request<AssessmentDetail>(`/api/portal/assessments/${encodeURIComponent(id)}`, token),
  async reportPdf(id: string, token: string): Promise<string> {
    const directory = FileSystem.cacheDirectory;
    if (!directory) throw new Error("The device has no available private file directory for this report.");
    const path = `${directory}xai-cvd-report-${id.slice(0, 8)}.pdf`;
    let download: Awaited<ReturnType<typeof FileSystem.downloadAsync>>;
    try { download = await FileSystem.downloadAsync(`${apiBase()}/api/portal/reports/${encodeURIComponent(id)}/pdf`, path, { headers: { Authorization: `Bearer ${token}` } }); }
    catch { throw new Error("Could not reach the report service."); }
    if (download.status === 401) { await FileSystem.deleteAsync(path, { idempotent: true }); throw new Error("Your session expired. Sign in again."); }
    if (download.status < 200 || download.status >= 300) { await FileSystem.deleteAsync(path, { idempotent: true }); throw new Error("This released report is not available."); }
    return path;
  },
  async clearReportCache() {
    const directory = FileSystem.cacheDirectory;
    if (!directory) return;
    const names = await FileSystem.readDirectoryAsync(directory).catch(() => []);
    await Promise.all(names.filter(name => name.startsWith("xai-cvd-report-") && name.endsWith(".pdf")).map(name => FileSystem.deleteAsync(`${directory}${name}`, { idempotent: true }).catch(() => {})));
  },
};

"use client";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function LoginPage() {
  const router = useRouter(); const [username, setUsername] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); setError(""); try { const { user } = await api.login(username, password); router.replace(user.role === "patient" ? "/portal" : "/patients"); } catch (e) { setError(e instanceof ApiError ? e.message : "Sign in failed."); } finally { setBusy(false); } }
  return <div className="page-shell" style={{ maxWidth: 520, margin: "45px auto" }}><div className="page-heading"><h1 className="page-title">Staff sign in</h1><p className="page-subtitle">Local research workspace accounts are created by the system operator.</p></div><Card><form onSubmit={submit} className="field-grid" style={{ gridTemplateColumns: "1fr" }}><label className="field">Username<input autoComplete="username" className="input" value={username} onChange={e => setUsername(e.target.value)} required /></label><label className="field">Password<input autoComplete="current-password" type="password" className="input" value={password} onChange={e => setPassword(e.target.value)} required /></label>{error && <div className="alert" role="alert">{error}</div>}<Button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button></form></Card><p className="card-description" style={{ marginTop: 14 }}>This demo does not send email. Patients activate portal access using an in-person code provided by staff.</p></div>;
}

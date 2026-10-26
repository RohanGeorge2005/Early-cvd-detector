import * as SecureStore from "expo-secure-store";
import { router } from "expo-router";
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { AuthResult, mobileApi, User } from "./api";

type Session = { token: string; expiresAt: string };
type AuthState = { token: string | null; ready: boolean; user: User | null; signIn: (u: string, p: string) => Promise<void>; activate: (code: string, u: string, p: string) => Promise<void>; signOut: () => Promise<void>; expireSession: () => Promise<void> };
const KEY = "xai-cvd-patient-session-v1";
const Context = createContext<AuthState | null>(null);
async function save(auth: AuthResult): Promise<Session> {
  const session = { token: auth.access_token, expiresAt: auth.expires_at };
  await SecureStore.setItemAsync(KEY, JSON.stringify(session), { keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK });
  return session;
}
export function AuthProvider({ children }: React.PropsWithChildren) {
  const [session, setSession] = useState<Session | null>(null); const [user, setUser] = useState<User | null>(null); const [ready, setReady] = useState(false);
  useEffect(() => { let alive = true; SecureStore.getItemAsync(KEY).then(raw => { if (!alive) return; if (!raw) return; try { const stored = JSON.parse(raw) as Session; if (Date.parse(stored.expiresAt) > Date.now()) setSession(stored); else void SecureStore.deleteItemAsync(KEY); } catch { void SecureStore.deleteItemAsync(KEY); } }).catch(() => {}).finally(() => { if (alive) setReady(true); }); return () => { alive = false; }; }, []);
  async function accept(auth: AuthResult) { const stored = await save(auth); setSession(stored); setUser(auth.user); }
  async function signIn(username: string, password: string) { await accept(await mobileApi.login(username.trim(), password)); }
  async function activate(code: string, username: string, password: string) { await accept(await mobileApi.activate(code.trim(), username.trim(), password)); }
  async function clear() { await SecureStore.deleteItemAsync(KEY).catch(() => {}); await mobileApi.clearReportCache(); setSession(null); setUser(null); }
  async function signOut() { const token = session?.token; if (token) await mobileApi.logout(token).catch(() => {}); await clear(); router.replace("/login"); }
  async function expireSession() { await clear(); router.replace("/login"); }
  useEffect(() => { if (!session) return; const delay = Date.parse(session.expiresAt) - Date.now(); if (delay <= 0) { void expireSession(); return; } const timer = setTimeout(() => { void expireSession(); }, delay); return () => clearTimeout(timer); }, [session?.expiresAt]);
  const value = useMemo(() => ({ token: session?.token ?? null, user, ready, signIn, activate, signOut, expireSession }), [session, user, ready]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useAuth() { const value = useContext(Context); if (!value) throw new Error("useAuth must be used inside AuthProvider"); return value; }

"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Activity, BrainCircuit, ChartNoAxesCombined, ChevronLeft, ClipboardList, FileText, HeartPulse, HelpCircle, Menu, Moon, Network, Search, ShieldCheck, Sun, X, Sparkles, Users, UserRound } from "lucide-react";
import { clsx } from "clsx";
import type { ReactNode } from "react";
import { useAssessment } from "@/components/providers";
import { api } from "@/lib/api";

const groups = [
  { label: "Care team", items: [
    { label: "Patients", href: "/patients", icon: Users },
  ] },
  { label: "Assess", items: [
    { label: "Risk assessment", href: "/assessment", icon: HeartPulse },
    { label: "Report analysis", href: "/report-analysis", icon: FileText },
  ] },
  { label: "Analyze", items: [
    { label: "Hybrid AI", href: "/hybrid-ai", icon: BrainCircuit },
    { label: "Model analytics", href: "/analytics", icon: ChartNoAxesCombined },
    { label: "Explainability", href: "/explainability", icon: Sparkles },
    { label: "Risk Factor Network", href: "/risk-network", icon: Network },
  ] },
  { label: "Reports", items: [
    { label: "Reports", href: "/reports", icon: ClipboardList },
    { label: "Clinical review", href: "/reports/review", icon: ShieldCheck },
    { label: "About", href: "/about", icon: HelpCircle },
  ] },
];
const allPages = [{ label: "Overview", href: "/", icon: Activity }, ...groups.flatMap(group => group.items)];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const portalMode = pathname.startsWith("/portal");
  const { result } = useAssessment();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [shortcut, setShortcut] = useState("Ctrl K");
  const [sessionUser, setSessionUser] = useState<{ username: string; role: string } | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const current = allPages.find(page => page.href === pathname) || { label: "XAI-CVD", href: "/", icon: Activity };

  useEffect(() => {
    const saved = window.localStorage.getItem("xai-cvd-theme");
    if (saved === "dark" || saved === "light") setTheme(saved);
    if (navigator.platform.toLowerCase().includes("mac")) setShortcut("⌘ K");
  }, []);
  useEffect(() => {
    window.localStorage.setItem("xai-cvd-theme", theme);
  }, [theme]);
  useEffect(() => {
    if (searchOpen) searchRef.current?.focus();
  }, [searchOpen]);
  useEffect(() => { api.authStatus().then(status => setSessionUser(status.authenticated ? status.user : null)).catch(() => setSessionUser(null)); }, [pathname]);
  async function signOut() { try { await api.logout(); } catch { /* Expired sessions are cleared by the next page load. */ } setSessionUser(null); window.location.assign(portalMode ? "/portal/login" : "/login"); }
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); setSearchOpen(open => !open); setQuery("");
      }
      if (event.key === "Escape") { setSearchOpen(false); setMobileOpen(false); }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
  const visiblePages = allPages.filter(page => page.label.toLowerCase().includes(query.toLowerCase()));

  return <div className={clsx("app-frame", theme === "light" ? "theme-light" : "theme-dark")}>
    {mobileOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <aside className={clsx("sidebar", collapsed && "sidebar-collapsed", mobileOpen && "sidebar-mobile-open")}>
      <div className="brand-row">
        <Link href="/" className="brand-lockup" onClick={() => setMobileOpen(false)}>
          <span className="brand-mark"><HeartPulse size={19}/></span>
          {!collapsed && <span><b>XAI-CVD</b><small>Cardiovascular Intelligence</small></span>}
        </Link>
        <button className="icon-button collapse-button" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={() => setCollapsed(!collapsed)}><ChevronLeft size={17}/></button>
        <button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18}/></button>
      </div>
      <nav aria-label={portalMode ? "Patient portal navigation" : "Main navigation"}>
        {portalMode ? <>
          <Link href="/portal" title={collapsed ? "My overview" : undefined} aria-current={pathname === "/portal" ? "page" : undefined} className={clsx("nav-link", pathname === "/portal" && "nav-active")} onClick={() => setMobileOpen(false)}><Activity size={18}/>{!collapsed && <span>My overview</span>}</Link>
          <Link href="/portal/login" className="nav-link" onClick={() => setMobileOpen(false)}><UserRound size={18}/>{!collapsed && <span>Portal sign in</span>}</Link>
        </> : <>
          <Link href="/" title={collapsed ? "Overview" : undefined} aria-current={pathname === "/" ? "page" : undefined} className={clsx("nav-link", pathname === "/" && "nav-active")} onClick={() => setMobileOpen(false)}><Activity size={18}/>{!collapsed && <span>Overview</span>}{pathname === "/" && <i aria-hidden="true"/>}</Link>
          {groups.map(group => <div className="nav-group" key={group.label}>
            {!collapsed && <div className="nav-group-label">{group.label}</div>}
            {group.items.map(({ label, href, icon: Icon }) => {
              const active = pathname === href || pathname.startsWith(`${href}/`);
              return <Link key={href} href={href} title={collapsed ? label : undefined} aria-current={active ? "page" : undefined} className={clsx("nav-link", active && "nav-active")} onClick={() => setMobileOpen(false)}><Icon size={18}/>{!collapsed && <span>{label}</span>}{active && <i aria-hidden="true"/>}</Link>;
            })}
          </div>)}
          <div className="nav-group"><div className="nav-group-label">Patient access</div><Link href="/portal/login" className="nav-link" onClick={() => setMobileOpen(false)}><UserRound size={18}/><span>Patient portal</span></Link></div>
        </>}
      </nav>
      <div className="sidebar-spacer"/>
      <button className="icon-button sidebar-search" title={`Search pages (${shortcut.replace(" ", "+")})`} aria-label="Search pages" onClick={() => setSearchOpen(true)}><Search size={17}/>{!collapsed && <span>Search pages <kbd>{shortcut}</kbd></span>}</button>
      <div className="theme-row">
        {!collapsed && <span>Appearance</span>}
        <button className="theme-toggle" aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`} onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
          {theme === "light" ? <Moon size={16}/> : <Sun size={16}/>}{!collapsed && <span>{theme === "light" ? "Light" : "Dark"}</span>}
        </button>
      </div>
    </aside>
    <main className="main-column">
      <header className="topbar">
        <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={20}/></button>
        <div className="breadcrumb"><span>Workspace</span><b>/</b><strong>{current.label}</strong></div>
        <div className="topbar-right">
          <button className="command-button" aria-label={`Search pages (${shortcut.replace(" ", "+")})`} onClick={() => setSearchOpen(true)}><Search size={15}/><span>Search</span><kbd>{shortcut}</kbd></button>
          {sessionUser && !portalMode && <><span className="online-pill">{sessionUser.username} · {sessionUser.role.replaceAll("_", " ")}</span><button className="command-button" onClick={signOut}>Sign out</button></>}
          <span className="online-pill"><i/> Local app</span>
        </div>
      </header>
      {pathname !== "/about" && pathname !== "/login" && !pathname.startsWith("/portal") && <div className={clsx("disclaimer-banner", pathname === "/assessment" && result && "disclaimer-result")} role="note"><ShieldCheck size={15}/><span><b>Research decision support only.</b> Not a diagnosis or a substitute for professional medical advice.</span></div>}
      <div className="page-content">{children}</div>
      <footer className="footer"><span>Explainable AI Engine for Early Cardiovascular Disease Risk Detection</span><span>Prediction ≠ diagnosis · SHAP ≠ causation</span></footer>
    </main>

    {searchOpen && <div className="command-overlay" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) setSearchOpen(false); }}>
      <section className="command-dialog" role="dialog" aria-modal="true" aria-label="Search pages">
        <div className="command-search"><Search size={18}/><input ref={searchRef} value={query} onChange={event => setQuery(event.target.value)} placeholder="Search pages…" aria-label="Search pages"/><button className="icon-button" aria-label="Close search" onClick={() => setSearchOpen(false)}><X size={17}/></button></div>
        <div className="command-results"><div className="command-group">Pages</div>
          {visiblePages.map(({ label, href, icon: Icon }) => <Link href={href} key={href} onClick={() => setSearchOpen(false)}><Icon size={17}/><span>{label}</span></Link>)}
          {visiblePages.length === 0 && <p className="command-empty">No matching pages.</p>}
        </div>
      </section>
    </div>}
  </div>;
}

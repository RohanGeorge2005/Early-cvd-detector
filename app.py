from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import joblib
import streamlit as st

from src.predict import load_artifacts, predict

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="XAI-CVD | Explainable AI Engine", page_icon=":material/ecg_heart:", layout="wide", initial_sidebar_state="expanded")

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if "assessment_step" not in st.session_state:
    st.session_state.assessment_step = 1
if "patient" not in st.session_state:
    st.session_state.patient = {}
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Light"

dark = st.session_state.theme_mode == "Dark"
palette = {
    "bg": "#071421" if dark else "#edf4f9", "surface": "#0e2233" if dark else "#ffffff",
    "text": "#e8f3f8" if dark else "#10283d", "muted": "#a0b8c7" if dark else "#60788a",
    "border": "#294255" if dark else "#d8e5ec", "navy": "#061a2e", "midnight": "#03111f",
    "teal": "#22d3ee", "blue": "#3b82f6", "purple": "#8b5cf6", "coral": "#ff5a5f",
    "low": "#22c55e", "moderate": "#f59e0b", "high": "#ef4444",
    "riskbg": "#102d34" if dark else "#e8f8f3", "banner": "#152a37" if dark else "#f0f8fc",
}
st.markdown(f"""
<style>
:root {{ color-scheme: {'dark' if dark else 'light'}; --text-color:{palette['text']}; --background-color:{palette['bg']}; --secondary-background-color:{palette['surface']}; --primary-color:{palette['teal']}; }}
.stApp {{ background:{palette['bg']} !important; color:{palette['text']} !important; font-family:Inter,Manrope,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; --text-color:{palette['text']}; --background-color:{palette['bg']}; --secondary-background-color:{palette['surface']}; --primary-color:{palette['teal']}; }}
[data-testid="stAppViewContainer"], [data-testid="stMain"] {{background:{palette['bg']};color:{palette['text']};}}
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3, [data-testid="stMarkdownContainer"] h4, label, [data-testid="stWidgetLabel"] {{color:{palette['text']} !important;}}
[data-testid="stCaptionContainer"], [data-testid="stWidgetHelp"] {{color:{palette['muted']} !important;}}
[data-testid="stHeader"] {{background:transparent;}}
[data-testid="stSidebar"] {{background:linear-gradient(165deg,#03111f 0%,#061a2e 62%,#0a263b 100%) !important;border-right:1px solid #15364b;box-shadow:8px 0 32px #03111f18;}}
[data-testid="stSidebar"] * {{color:#dceaf2;}}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{color:#8faab9 !important;}}
[data-testid="stSidebar"] [data-testid="stRadio"] label {{padding:.58rem .72rem;border-radius:8px;border-left:2px solid transparent;transition:background .18s ease,border-color .18s ease;}}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{background:#ffffff0d;}}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {{background:#22d3ee18;border-left-color:#22d3ee;box-shadow:inset 0 0 18px #22d3ee0c,0 0 20px #22d3ee0a;}}
[data-testid="stSidebar"] [data-testid="stRadio"] label p {{color:#bfd0da !important;font-size:.91rem;}}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p {{color:#eaffff !important;font-weight:650;}}
.block-container {{max-width:1400px;padding-top:.8rem;padding-bottom:3.5rem;}}
.brand {{display:flex;align-items:center;gap:10px;font-size:1.02rem;font-weight:680;letter-spacing:.02em;color:{palette['text']};margin:0 0 .35rem;}}
.brand-mark {{display:inline-grid;place-items:center;background:linear-gradient(145deg,#22d3ee,#3b82f6);color:#03111f;width:35px;height:35px;border-radius:10px;font-size:.74rem;font-weight:800;letter-spacing:.03em;box-shadow:0 0 20px #22d3ee40;}}
.eyebrow {{color:{palette['teal']};font-size:.73rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;margin-bottom:.65rem;}}
.topbar {{display:flex;align-items:center;justify-content:space-between;padding:.1rem .15rem .45rem;}}
.system-status {{display:inline-flex;align-items:center;gap:7px;color:{palette['muted']};font-size:.78rem;letter-spacing:.04em;}}
.status-dot {{width:8px;height:8px;border-radius:99px;background:#22c55e;box-shadow:0 0 10px #22c55eaa;display:inline-block;}}
.hero {{position:relative;isolation:isolate;overflow:hidden;background:radial-gradient(ellipse at 78% 20%,#0d3b59 0%,transparent 36%),radial-gradient(ellipse at 30% 110%,#102d49 0%,transparent 52%),linear-gradient(124deg,#03111f 0%,#061a2e 62%,#092238 100%);color:white;padding:clamp(1.4rem,3vw,2.5rem);border-radius:18px;margin:.4rem 0 .9rem;border:1px solid #1d4055;box-shadow:0 20px 55px #03111f2b;}}
.hero:before {{content:"";position:absolute;inset:0;z-index:-1;opacity:.16;background-image:linear-gradient(#60a5fa20 1px,transparent 1px),linear-gradient(90deg,#60a5fa20 1px,transparent 1px);background-size:34px 34px;mask-image:linear-gradient(90deg,transparent,black);}}
.hero h1 {{font-size:clamp(2.35rem,4.7vw,4.5rem);line-height:1.04;letter-spacing:-.05em;max-width:760px;margin:0 0 1rem;color:#f8fbfd !important;}}
.hero p {{max-width:670px;color:#c7d9e4 !important;font-size:clamp(.98rem,1.35vw,1.08rem);line-height:1.7;margin:0 0 1.15rem;}}
.hero .tag {{display:inline-block;color:#a5f3fc;background:#22d3ee15;border:1px solid #22d3ee50;border-radius:99px;padding:.38rem .7rem;font-size:.68rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:1.15rem;}}
.st-key-hero-wrap {{position:relative;background:radial-gradient(ellipse at 80% 20%,#0d3b59 0%,transparent 35%),radial-gradient(ellipse at 25% 115%,#102d49 0%,transparent 55%),linear-gradient(124deg,#03111f 0%,#061a2e 63%,#092238 100%);border:1px solid #1d4055;border-radius:19px;padding:clamp(1.15rem,2.8vw,2.4rem);margin:.2rem 0 .85rem;overflow:hidden;box-shadow:0 21px 58px #03111f2b;isolation:isolate;}}
.st-key-hero-wrap:before {{content:"";position:absolute;inset:0;z-index:-1;opacity:.17;background-image:linear-gradient(#60a5fa20 1px,transparent 1px),linear-gradient(90deg,#60a5fa20 1px,transparent 1px);background-size:34px 34px;mask-image:linear-gradient(90deg,transparent,black);pointer-events:none;}}
.hero-copy h1 {{font-size:clamp(2.25rem,4.1vw,3.7rem);line-height:1.035;letter-spacing:-.05em;max-width:730px;margin:.3rem 0 1rem;color:#f8fbfd !important;}}
.hero-copy p {{max-width:680px;color:#c7d9e4 !important;font-size:clamp(.97rem,1.25vw,1.08rem);line-height:1.68;margin:0 0 .9rem;}}
.hero-copy .tag {{display:inline-block;color:#a5f3fc !important;background:#22d3ee15;border:1px solid #22d3ee50;border-radius:99px;padding:.38rem .7rem;font-size:.68rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.65rem;}}
.st-key-hero-wrap [data-testid="stButton"] button {{min-height:2.65rem;padding:0 1rem;}}
.st-key-hero-wrap [data-testid="stButton"]:first-child button {{box-shadow:0 0 22px #22d3ee35;}}
.capability-row {{padding-top:.45rem;}}
.hero-art {{position:relative;min-height:300px;display:grid;place-items:center;}}
.heart-svg {{width:min(100%,420px);filter:drop-shadow(0 0 20px #22d3ee60);animation:heartFloat 6s ease-in-out infinite;}}
.ecg-path {{stroke-dasharray:500;stroke-dashoffset:500;animation:ecgTrace 5s linear infinite;}}
.pulse-ring {{transform-origin:260px 185px;animation:pulseGlow 3.2s ease-in-out infinite;}}
.why-glass {{position:absolute;bottom:0;right:0;width:min(270px,82%);padding:.9rem 1rem;border:1px solid #9cecff42;border-radius:13px;background:#081d2bc9;backdrop-filter:blur(14px);box-shadow:0 12px 35px #020b1490;color:#edfaff;}}
.why-glass h3 {{font-size:.98rem;color:white;margin:0 0 .35rem;}}
.why-glass p {{font-size:.79rem;line-height:1.45;color:#bcd1dc;margin:0 0 .5rem;}}
.why-mini {{font-size:.7rem;line-height:1.75;color:#a5f3fc;}}
.capability {{display:inline-block;border:1px solid #a5f3fc30;border-radius:99px;padding:.3rem .58rem;color:#c8f8fb;font-size:.69rem;margin:.18rem .2rem .1rem 0;background:#22d3ee0b;}}
.disclaimer {{padding:.72rem 1rem;border:1px solid {palette['border']};border-left:3px solid #f59e0b;background:{palette['banner']};border-radius:8px;color:{palette['text']};font-size:.82rem;line-height:1.5;margin:.3rem 0 1rem;}}
.metric-box,.panel {{height:100%;background:linear-gradient(145deg,{palette['surface']},{palette['surface']}d9);border:1px solid {palette['border']};border-radius:13px;padding:1.05rem 1.05rem;box-shadow:0 8px 25px #03111f0b;transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease;}}
.metric-box:hover,.panel:hover {{transform:translateY(-3px);border-color:#22d3ee70;box-shadow:0 13px 30px #03111f16,0 0 24px #22d3ee0d;}}
.metric-label {{font-size:.69rem;text-transform:uppercase;letter-spacing:.1em;color:{palette['muted']};}}
.metric-value {{font-size:1.22rem;font-weight:680;margin-top:.4rem;color:{palette['text']};}}
.section-kicker {{font-size:.68rem;text-transform:uppercase;letter-spacing:.14em;color:{palette['blue']};font-weight:700;margin:0 0 .4rem;}}
.section-title {{font-size:clamp(1.5rem,2.5vw,2rem);font-weight:680;letter-spacing:-.035em;margin:0 0 .35rem;color:{palette['text']};}}
.subtle {{color:{palette['muted']};font-size:.89rem;line-height:1.58;}}
.hybrid-panel {{background:radial-gradient(ellipse at 80% 5%,#1e3a8a55 0%,transparent 37%),linear-gradient(125deg,#03111f,#071f34 70%,#092940);border:1px solid #21455c;border-radius:18px;padding:clamp(1.2rem,2.5vw,2rem);color:#e9f8fc;box-shadow:0 18px 50px #03111f20;}}
.st-key-hybrid-panel {{background:radial-gradient(ellipse at 80% 5%,#1e3a8a55 0%,transparent 37%),linear-gradient(125deg,#03111f,#071f34 70%,#092940);border:1px solid #21455c;border-radius:18px;padding:clamp(1rem,2.1vw,1.8rem);color:#e9f8fc;box-shadow:0 18px 50px #03111f20;}}
.st-key-hybrid-panel [data-testid="stMarkdownContainer"] p {{color:#acc5d3 !important;}}
.st-key-hybrid-panel [data-testid="stMarkdownContainer"] h3 {{color:#f4fcff !important;}}
.hybrid-panel h2,.hybrid-panel h3 {{color:#f4fcff !important;}}
.hybrid-panel p {{color:#acc5d3 !important;}}
.arch-node {{background:#0d2639bd;border:1px solid #2b5266;border-radius:11px;padding:.78rem .86rem;min-height:82px;box-shadow:inset 0 1px #ffffff08;}}
.arch-node strong {{color:#e9fbff;font-size:.83rem;}}
.arch-node small {{display:block;color:#95b6c8;font-size:.72rem;margin-top:.27rem;}}
.arch-arrow {{text-align:center;color:#22d3ee;font-size:1.2rem;line-height:1;padding:.28rem;}}
.timeline-step {{background:{palette['surface']};border:1px solid {palette['border']};border-radius:12px;padding:.75rem .65rem;height:100%;position:relative;box-shadow:0 7px 20px #03111f0b;}}
.timeline-num {{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#22d3ee18;color:#0891b2;border:1px solid #22d3ee78;font-size:.71rem;font-weight:750;margin:0 auto .5rem;box-shadow:0 0 16px #22d3ee22;}}
.timeline-title {{font-size:.78rem;font-weight:680;text-align:center;color:{palette['text']};}}
.timeline-copy {{font-size:.66rem;text-align:center;color:{palette['muted']};margin-top:.2rem;line-height:1.35;}}
.timeline-line {{height:2px;background:linear-gradient(90deg,#3b82f6,#22d3ee,#8b5cf6);opacity:.68;margin:-1px 1.3rem 1rem;}}
.stepbar {{display:flex;align-items:center;gap:0;margin:1.1rem 0 1.4rem;}}
.step-item {{display:flex;align-items:center;gap:.5rem;color:{palette['muted']};font-size:.8rem;white-space:nowrap;}}
.step-dot {{width:27px;height:27px;border-radius:50%;border:1px solid {palette['border']};display:grid;place-items:center;background:{palette['surface']};}}
.step-item.active {{color:{palette['teal']};font-weight:650;}}
.step-item.active .step-dot,.step-item.done .step-dot {{background:{palette['teal']};border-color:{palette['teal']};color:#071e32;}}
.step-line {{height:1px;background:{palette['border']};flex:1;margin:0 .7rem;min-width:10px;}}
.live-risk {{display:flex;flex-direction:column;gap:.28rem;margin:1rem 0 .4rem;padding:1rem;border:1px solid #22d3ee45;border-radius:12px;background:linear-gradient(135deg,#22d3ee0d,#3b82f60a);}}
.live-risk small {{font-size:.66rem;text-transform:uppercase;letter-spacing:.11em;color:{palette['muted']};}}
.live-risk strong {{font-size:1.28rem;color:{palette['text']};}}
.live-risk span {{font-size:.76rem;color:{palette['muted']};}}
.result-hero {{border:1px solid #22d3ee45;border-radius:18px;padding:1.1rem;background:radial-gradient(ellipse at 15% 35%,#22d3ee13,transparent 40%),linear-gradient(130deg,{palette['surface']},#0a2030);box-shadow:0 16px 38px #03111f16;}}
.result-hero [data-testid="stMarkdownContainer"] p {{color:#bfd2de;}}
.st-key-report-panel {{border:1px solid {palette['border']};border-radius:15px;padding:1rem;background:{palette['surface']};}}
.ring {{width:min(260px,65vw);aspect-ratio:1;border-radius:50%;display:grid;place-items:center;margin:1rem auto;background:conic-gradient({palette['teal']} var(--risk),{palette['border']} 0);position:relative;animation:ringReveal 1.05s cubic-bezier(.2,.7,.2,1) both;filter:drop-shadow(0 0 19px #22d3ee28);}}
.ring:before {{content:"";position:absolute;inset:13px;background:{palette['surface']};border-radius:50%;}}
.ring-content {{position:relative;text-align:center;}}
.ring-value {{font-size:3.1rem;font-weight:650;letter-spacing:-.05em;line-height:1.05;color:{palette['text']};}}
.ring-label {{font-size:.78rem;color:{palette['muted']};margin-top:.25rem;}}
.insight {{height:100%;background:{palette['surface']};border:1px solid {palette['border']};border-radius:9px;padding:1rem;}}
.insight h4 {{font-size:.92rem;margin:0 0 .45rem;color:{palette['text']};}}
.insight p {{font-size:.84rem;line-height:1.5;color:{palette['muted']};margin:0;}}
div.stButton > button {{border-radius:8px;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease;}}
div.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {{background:linear-gradient(110deg,#22d3ee,#38bdf8) !important;color:#03111f !important;border:1px solid #67e8f9 !important;font-weight:700 !important;}}
div.stButton > button[kind="primary"] p, [data-testid="stBaseButton-primary"] p {{color:#03111f !important;}}
div.stButton > button:hover {{transform:translateY(-2px);box-shadow:0 7px 20px #071e3225;border-color:#22d3ee88;}}
:focus-visible {{outline:3px solid {palette['blue']} !important;outline-offset:2px !important;}}
@keyframes heartFloat {{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-7px)}}}}
@keyframes pulseGlow {{0%,100%{{opacity:.42;transform:scale(.97)}}50%{{opacity:.9;transform:scale(1.04)}}}}
@keyframes ecgTrace {{0%{{stroke-dashoffset:500}}58%,100%{{stroke-dashoffset:0}}}}
@keyframes ringReveal {{from{{transform:rotate(-90deg) scale(.94);opacity:.55}}to{{transform:rotate(0) scale(1);opacity:1}}}}
@media(max-width:980px) {{.hero-art{{min-height:260px}}.why-glass{{right:0;bottom:0}}}}
@media(max-width:700px) {{.block-container{{padding:1rem .85rem 2rem}}.step-item{{font-size:0}}.step-dot{{width:29px;height:29px;font-size:.8rem}}.step-line{{margin:0 .35rem}}.hero h1{{font-size:2.2rem}}.hero-art{{min-height:230px}}.timeline-line{{display:none}}}}
@media(prefers-reduced-motion:reduce) {{*,*::before,*::after{{animation-duration:.01ms !important;animation-iteration-count:1 !important;scroll-behavior:auto !important;transition-duration:.01ms !important}}}}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-mark">XAI</span> XAI-CVD</div>', unsafe_allow_html=True)
    st.caption("Cardiovascular Intelligence")
    st.space("small")
    nav_items = [("⌂", "Overview", "Dashboard"), ("♡", "Risk Assessment", "Assessment"),
                 ("⌘", "Hybrid AI", "Hybrid AI"), ("▥", "Model Analytics", "Model analytics"),
                 ("✦", "Explainability", "Explainability"), ("▤", "Reports", "Reports"), ("ⓘ", "About", "About")]
    nav_labels = [f"{icon}  {label}" for icon, label, _ in nav_items]
    page_by_label = {f"{icon}  {label}": page_name for icon, label, page_name in nav_items}
    current_label = next((label for label, page_name in page_by_label.items() if page_name == st.session_state.page), nav_labels[0])
    chosen = st.radio("Navigate", nav_labels, index=nav_labels.index(current_label), label_visibility="collapsed")
    st.session_state.page = page_by_label[chosen]
    st.space("medium")
    st.toggle("Theme · Dark mode", key="dark_toggle", value=dark, on_change=lambda: st.session_state.update(theme_mode="Dark" if st.session_state.dark_toggle else "Light"))
    st.space("large")
    st.markdown('<div style="border:1px solid #234659;background:#0d2639;border-radius:11px;padding:.85rem .9rem"><div style="color:#a5f3fc;font-size:.67rem;letter-spacing:.11em;font-weight:700">RESEARCH PROTOTYPE</div><div style="font-size:.77rem;color:#cfdee6;margin-top:.4rem;line-height:1.45">Educational use only.<br>This is not a medical diagnosis.</div></div>', unsafe_allow_html=True)

top_left, top_right = st.columns([1.4, 1], vertical_alignment="center")
with top_left:
    st.markdown('<div class="brand"><span class="brand-mark">XAI</span> XAI-CVD <span style="font-weight:400;color:'+palette['muted']+';font-size:.83rem">/ Cardiovascular Intelligence</span></div>', unsafe_allow_html=True)
with top_right:
    with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center"):
        st.markdown('<span class="system-status"><span class="status-dot"></span> APPLICATION ONLINE</span>', unsafe_allow_html=True)
        with st.popover("⚙", help="About this research prototype"):
            st.caption("XAI-CVD is an academic research prototype. Model outputs are not medical diagnoses.")
st.markdown('<div class="disclaimer"><b>Educational and research prototype only.</b> This assessment is not a medical diagnosis and should not replace advice from a qualified healthcare professional.</div>', unsafe_allow_html=True)


def set_page(name: str) -> None:
    st.session_state.page = name
    st.rerun()


def get_artifacts():
    try:
        return load_artifacts()
    except Exception as exc:
        st.error(f"Model is not ready: {exc}")
        st.info("Add the supplied dataset at `data/raw/framingham.csv`, install `requirements.txt`, then train with `python -m src.train --data data/raw/framingham.csv`.")
        return None, None


def landing_page():
    with st.container(key="hero-wrap"):
        copy, visual = st.columns([1.15, .85], vertical_alignment="center", gap="large")
        with copy:
            st.markdown('''<div class="hero-copy"><span class="tag">Explainable AI in healthcare</span><h1>Understand Cardiovascular Risk.<br>Don't Just Predict It.</h1><p>An Explainable Hybrid AI Engine combining machine learning, deep learning and patient-specific XAI to make cardiovascular risk assessment transparent and understandable.</p></div>''', unsafe_allow_html=True)
            with st.container(horizontal=True):
                if st.button("Start risk assessment →", type="primary", key="hero_start"):
                    st.session_state.assessment_step = 1
                    set_page("Assessment")
                if st.button("Explore hybrid AI", key="hero_how"):
                    set_page("Hybrid AI")
            st.markdown('''<div class="capability-row"><span class="capability">✓ Hybrid ML + DL</span><span class="capability">✓ Explainable AI</span><span class="capability">✓ 10-year CHD risk</span><span class="capability">✓ Decision support</span></div>''', unsafe_allow_html=True)
        with visual:
            st.markdown('''<div class="hero-art"><svg class="heart-svg" viewBox="0 0 520 390" role="img" aria-label="Abstract cardiovascular neural network illustration">
              <defs><radialGradient id="heartGlow"><stop offset="0" stop-color="#22D3EE" stop-opacity=".42"/><stop offset="1" stop-color="#3B82F6" stop-opacity=".03"/></radialGradient><linearGradient id="heartStroke" x1="0" x2="1"><stop stop-color="#22D3EE"/><stop offset="1" stop-color="#8B5CF6"/></linearGradient></defs>
              <circle class="pulse-ring" cx="260" cy="185" r="145" fill="url(#heartGlow)" stroke="#22D3EE" stroke-opacity=".2" stroke-width="1"/>
              <path d="M260 301 C220 267 136 211 142 151 C148 94 218 86 258 135 C294 82 373 91 382 148 C392 207 311 270 260 301Z" fill="#0B2A40" stroke="url(#heartStroke)" stroke-width="3"/>
              <path d="M258 133 C251 108 265 77 282 61 M279 82 C305 73 328 82 340 98 M255 97 C239 74 211 69 195 77" fill="none" stroke="#22D3EE" stroke-width="7" stroke-linecap="round"/>
              <path d="M260 150 L260 177 L239 190 L278 190 L264 207 L264 231" fill="none" stroke="#60A5FA" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
              <path class="ecg-path" d="M18 206 H129 L155 206 L174 179 L193 240 L216 196 L231 206 H290 L312 206 L329 185 L346 229 L362 202 L380 206 H500" fill="none" stroke="#22D3EE" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
              <g fill="#67E8F9"><circle cx="112" cy="119" r="3"/><circle cx="405" cy="129" r="3"/><circle cx="416" cy="267" r="2.5"/><circle cx="102" cy="277" r="2.5"/><circle cx="364" cy="64" r="2"/></g>
              <g stroke="#22D3EE" stroke-opacity=".32" stroke-width="1"><path d="M112 119L175 146L142 151M405 129L382 148L354 116M102 277L170 243L198 267M416 267L355 235L340 260M364 64L328 91L305 82"/></g>
            </svg><div class="why-glass"><h3>Why explainable AI?</h3><p>We don't only predict cardiovascular risk. We explain the factors influencing each prediction.</p><div class="why-mini">◉ Patient-specific explanations<br>◉ Key contributing factors<br>◉ Model transparency<br>◉ Risk stratification<br>◉ Decision support</div></div></div>''', unsafe_allow_html=True)
    cols = st.columns(4)
    cards = [("Models compared", "5", "LR · RF · XGBoost · MLP · Hybrid"), ("Dataset specification", "≈11,000", "Expected records · CSV not loaded"), ("Explainability", "SHAP", "Hybrid local + global"), ("Prediction horizon", "10 years", "Coronary heart disease")]
    for col, (label, value, note) in zip(cols, cards):
        with col:
            st.markdown(f'<div class="metric-box"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="subtle">{note}</div></div>', unsafe_allow_html=True)
    st.space("large")
    st.markdown('<div class="section-kicker">The core intelligence</div><div class="section-title">Hybrid AI Engine</div><p class="subtle">Machine learning and deep learning branches come together in a validation-calibrated assessment.</p>', unsafe_allow_html=True)
    with st.container(key="hybrid-panel"):
        st.markdown("### A clearer view of the model")
        st.markdown("Patient profile → fit preprocessing → **tree-based ML + tabular MLP** → validation-calibrated hybrid probability → SHAP explanation and decision support")
        st.markdown('<div class="arch-arrow">↓</div>', unsafe_allow_html=True)
        ml, dl = st.columns(2)
        with ml: st.markdown('<div class="arch-node"><strong>◈ Machine learning</strong><small>Logistic Regression · Random Forest · XGBoost</small></div>', unsafe_allow_html=True)
        with dl: st.markdown('<div class="arch-node"><strong>✧ Deep learning</strong><small>Tabular MLP · BatchNorm · ReLU · Dropout</small></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            with st.popover("Machine learning details"): st.write("All three traditional classifiers are compared. Random Forest or XGBoost supplies the tree probability based on training-only cross-validation.")
        with c2:
            with st.popover("Deep learning details"): st.write("The tabular MLP uses weighted binary cross-entropy, Adam, a stratified validation split, and early stopping.")
        with c3:
            with st.popover("Hybrid engine details"): st.write("The final probability is alpha × tree probability + (1 − alpha) × MLP probability. Alpha is calibrated on training validation data.")
        st.markdown('<div class="arch-arrow">↓</div><div class="arch-node"><strong>◉ HYBRID AI ENGINE</strong><small>One probability · consensus view · model-agnostic SHAP · general decision support</small></div>', unsafe_allow_html=True)
    st.space("large")
    st.markdown('<div class="section-kicker">A transparent workflow</div><div class="section-title">How the assessment works</div><p class="subtle">From patient profile to understandable output.</p>', unsafe_allow_html=True)
    timeline = [("01", "Patient data", "15 clinical attributes", "Only features in the dataset are collected."), ("02", "Preprocessing", "Clean · encode · scale", "Fitted imputation and transformations are reused at prediction time."), ("03", "Hybrid AI", "ML + deep learning", "A selected tree model is combined with the tabular MLP."), ("04", "Risk estimate", "10-year CHD probability", "The model returns a probability for the dataset's target."), ("05", "SHAP", "Why this prediction?", "Contributions describe the final hybrid model behavior."), ("06", "Risk category", "Low · moderate · high", "Configurable model-based bands, not clinically validated."), ("07", "Decision support", "General insights", "Educational discussion points with professional follow-up.")]
    for offset in (0, 4):
        group = timeline[offset:offset+4]
        cols = st.columns(len(group))
        for col, (number, title, short, detail) in zip(cols, group):
            with col:
                st.markdown(f'<div class="timeline-step"><div class="timeline-num">{number}</div><div class="timeline-title">{title}</div><div class="timeline-copy">{short}</div></div>', unsafe_allow_html=True)
                with st.popover("More details"): st.caption(detail)
        st.markdown('<div class="timeline-line"></div>', unsafe_allow_html=True)


def init_patient():
    defaults = {"gender": 0, "age": 50, "education": 2, "currentSmoker": 0, "cigsPerDay": 0,
                "BPMeds": 0, "prevalentStroke": 0, "prevalentHyp": 0, "diabetes": 0,
                "totChol": 200.0, "sysBP": 120.0, "diaBP": 80.0, "BMI": 25.0,
                "heartRate": 70.0, "glucose": 100.0}
    for key, value in defaults.items():
        st.session_state.patient.setdefault(key, value)


def render_steps():
    names = ["Patient profile", "Lifestyle", "Medical history", "Measurements", "Assessment"]
    pieces = []
    for i, name in enumerate(names, 1):
        cls = "active" if i == st.session_state.assessment_step else "done" if i < st.session_state.assessment_step else ""
        pieces.append(f'<div class="step-item {cls}"><span class="step-dot">{i if i >= st.session_state.assessment_step else "✓"}</span><span>STEP 0{i} · {name}</span></div>')
    st.markdown('<div class="stepbar">' + '<div class="step-line"></div>'.join(pieces) + '</div>', unsafe_allow_html=True)


def set_step(step: int):
    st.session_state.assessment_step = step
    st.session_state.pop("generated_report", None)
    st.session_state.pop("generated_report_patient", None)
    st.rerun()


def assessment_page():
    init_patient()
    step = st.session_state.assessment_step
    st.markdown('<div class="section-kicker">Private, session-only inputs · 15 dataset predictors</div><div class="section-title">Cardiovascular risk assessment</div><p class="subtle">Complete each short step. Units and broad input bounds help catch entry errors; these ranges are not diagnostic thresholds.</p>', unsafe_allow_html=True)
    render_steps()
    p = st.session_state.patient
    left, right = st.columns([1.45, .8], gap="large", vertical_alignment="top")
    with left:
      with st.container(border=True):
        if step == 1:
            st.markdown("### Patient profile")
            st.caption("Demographic profile")
            c1, c2, c3 = st.columns(3)
            p["gender"] = c1.selectbox("Gender (dataset coding)", [0, 1], index=int(p["gender"]), format_func=lambda x: "Female · 0" if x == 0 else "Male · 1", key="gender")
            p["age"] = c2.number_input("Age · years", min_value=18, max_value=120, value=int(p["age"]), help="Enter a value from 18 to 120 years.", key="age")
            p["education"] = c3.selectbox("Education · dataset code", [1, 2, 3, 4], index=int(p["education"])-1, help="Dataset levels 1–4.", key="education")
        elif step == 2:
            st.markdown("### Lifestyle")
            c1, c2 = st.columns(2)
            p["currentSmoker"] = c1.selectbox("Current smoker", [0, 1], index=int(p["currentSmoker"]), format_func=lambda x: "No" if x == 0 else "Yes", key="currentSmoker")
            p["cigsPerDay"] = c2.number_input("Cigarettes per day", 0, 100, int(p["cigsPerDay"]), help="Allowed input range: 0–100; this is not a clinical target.", key="cigsPerDay")
        elif step == 3:
            st.markdown("### Medical history")
            st.caption("Select the response encoded in the source dataset.")
            labels = [("BPMeds", "On blood pressure medication"), ("prevalentStroke", "Previous stroke"), ("prevalentHyp", "Hypertension"), ("diabetes", "Diabetes")]
            cols = st.columns(2)
            for i, (key, label) in enumerate(labels):
                p[key] = cols[i % 2].selectbox(label, [0, 1], index=int(p[key]), format_func=lambda x: "No · 0" if x == 0 else "Yes · 1", key=key)
        elif step == 4:
            st.markdown("### Clinical measurements")
            fields = [("totChol", "Total cholesterol", 50.0, 700.0, "mg/dL", 200.0), ("sysBP", "Systolic blood pressure", 50.0, 300.0, "mmHg", 120.0), ("diaBP", "Diastolic blood pressure", 30.0, 200.0, "mmHg", 80.0), ("BMI", "Body mass index", 10.0, 100.0, "kg/m²", 25.0), ("heartRate", "Resting heart rate", 25.0, 250.0, "bpm", 70.0), ("glucose", "Fasting glucose", 20.0, 1000.0, "mg/dL", 100.0)]
            cols = st.columns(2)
            for i, (key, label, lo, hi, unit, default) in enumerate(fields):
                p[key] = cols[i % 2].number_input(f"{label} · {unit}", min_value=lo, max_value=hi, value=float(p[key] or default), help=f"Allowed entry range {lo:g}–{hi:g} {unit}; not a diagnostic range.", key=key)
        else:
            st.markdown("### Review and assess")
            st.write("The prediction uses the values below. Change an earlier step if something needs correction.")
            summary = {"Gender": "Female" if p["gender"] == 0 else "Male", "Age": f"{p['age']} years", "Education": p["education"], "Current smoker": "Yes" if p["currentSmoker"] else "No", "Cigarettes per day": p["cigsPerDay"], "BP medication": "Yes" if p["BPMeds"] else "No", "Previous stroke": "Yes" if p["prevalentStroke"] else "No", "Hypertension": "Yes" if p["prevalentHyp"] else "No", "Diabetes": "Yes" if p["diabetes"] else "No", "Total cholesterol": f"{p['totChol']:g} mg/dL", "Systolic BP": f"{p['sysBP']:g} mmHg", "Diastolic BP": f"{p['diaBP']:g} mmHg", "BMI": f"{p['BMI']:g} kg/m²", "Resting heart rate": f"{p['heartRate']:g} bpm", "Fasting glucose": f"{p['glucose']:g} mg/dL"}
            st.dataframe(pd.DataFrame([summary]).T.rename(columns={0:"Entered value"}), width="stretch")
            st.caption("Values are held in this app session's memory and are not written to disk.")
        st.space("small")
        with st.container(horizontal=True, horizontal_alignment="distribute"):
            if step > 1 and st.button("← Back", key=f"back_{step}"):
                set_step(step - 1)
            if step < 5:
                if st.button("Continue →", type="primary", key=f"next_{step}"):
                    set_step(step + 1)
            elif st.button("Assess cardiovascular risk →", type="primary", key="assess_final"):
                model, metadata = get_artifacts()
                if model is not None:
                    try:
                        with st.status("Analyzing patient profile…", expanded=True) as status:
                            st.write("Validating the entered values")
                            st.write("Generating the risk assessment")
                            result = predict(dict(p), model, metadata)
                            st.write("Preparing the SHAP explanation")
                            status.update(label="Assessment prepared", state="complete", expanded=False)
                        st.session_state.result = result
                        st.session_state.model_metadata = metadata
                        st.session_state.pop("generated_report", None)
                        st.session_state.pop("generated_report_patient", None)
                        st.session_state.page = "Assessment"
                        st.session_state.show_results = True
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Assessment could not be completed: {exc}")
    with right:
        st.markdown('<div class="section-kicker">Live review</div><div class="section-title" style="font-size:1.2rem">Current form values</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.caption(f"Step {step} of 5 · Values are kept in this session")
            fields = [
                ("Profile", f"{'Female' if p['gender'] == 0 else 'Male'} · {p['age']} years · education {p['education']}"),
                ("Lifestyle", f"{'Current smoker' if p['currentSmoker'] else 'Non-smoker'} · {p['cigsPerDay']} cigarettes/day"),
                ("Medical history", " · ".join(name for key, name in [("BPMeds", "BP medication"), ("prevalentStroke", "previous stroke"), ("prevalentHyp", "hypertension"), ("diabetes", "diabetes")] if p[key]) or "No listed history selected"),
                ("Measurements", f"Cholesterol {p['totChol']:g} · BP {p['sysBP']:g}/{p['diaBP']:g} · BMI {p['BMI']:g}"),
                ("Additional", f"Heart rate {p['heartRate']:g} · glucose {p['glucose']:g}"),
            ]
            for label, value in fields:
                st.markdown(f"**{label}**  \n{value}")
            if st.session_state.get("show_results") and st.session_state.get("result"):
                current = st.session_state.result
                band_color = {"LOW": palette["low"], "MODERATE": palette["moderate"], "HIGH": palette["high"]}[current["risk_category"]]
                st.markdown(f'<div class="live-risk"><small>Current model estimate</small><strong>{current["probability"]:.0%}</strong><span style="color:{band_color}">{current["risk_category"]} · model-based band</span></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="live-risk"><small>Assessment status</small><strong>Not assessed</strong><span>Complete the five steps to prepare a result.</span></div>', unsafe_allow_html=True)
            st.caption("Prediction is not a diagnosis. Review results with a qualified healthcare professional.")
    if st.session_state.get("show_results") and st.session_state.get("result"):
        render_results()


def render_results():
    result = st.session_state.result
    metadata = st.session_state.model_metadata
    patient = st.session_state.patient
    category = result["risk_category"]
    risk_color = {"LOW": palette["low"], "MODERATE": palette["moderate"], "HIGH": palette["high"]}[category]
    st.space("large")
    st.markdown('<div class="section-kicker">Hybrid risk score</div><div class="section-title">Estimated 10-year CHD risk</div>', unsafe_allow_html=True)
    with st.container(key="result-hero"):
        left, right = st.columns([.9, 1.2], vertical_alignment="center")
        with left:
            st.markdown(f'<div class="ring" style="--risk:{result["probability"]*100:.1f}%;"><div class="ring-content"><div class="ring-value">{result["probability"]:.0%}</div><div class="ring-label">hybrid model probability</div></div></div>', unsafe_allow_html=True)
        with right:
            st.markdown(f'<div class="panel" style="background:{palette["riskbg"]};"><div class="section-kicker">Model-based category</div><div style="font-size:2rem;font-weight:680;color:{risk_color}">{category} RISK</div><p class="subtle">{result["binary_label"]} · Hybrid ML + MLP · α = {result["alpha"]:.2f}</p><p class="subtle">Configurable academic risk bands; not clinically validated.</p></div>', unsafe_allow_html=True)
            st.caption(f"ML branch: {result['tree_component']} · Deep learning branch: MLP · Binary threshold: {result['model_threshold']:.0%}")

    st.markdown("### Model consensus")
    outputs = result["model_outputs"]
    for start in range(0, len(outputs), 3):
        cards = st.columns(min(3, len(outputs) - start))
        for col, (name, probability) in zip(cards, list(outputs.items())[start:start+3]):
            with col:
              with st.container(border=True):
                st.caption(name)
                st.metric("Probability", f"{probability:.1%}")
                st.caption(("Higher" if probability >= result["model_threshold"] else "Lower") + " predicted risk")
                st.progress(float(np.clip(probability, 0, 1)), text="Model probability")
    if result["model_consensus"]:
        st.success(f"Model consensus: {result['model_consensus_count']}/{result['model_consensus_total']} selected ML, MLP, and hybrid outputs indicate {('higher' if result['prediction'] else 'lower')} predicted risk.")
    else:
        st.warning("Model disagreement detected. Interpret the final ensemble output cautiously.")

    st.markdown("### Hybrid model explanation")
    st.caption("Factors contributing to the final hybrid prediction. SHAP values describe model contributions; they do not prove causation.")
    mode = st.radio("Explanation view", ["Simple explanation", "Technical explanation"], horizontal=True, key="hybrid_explanation_view")
    all_factors = result["shap_values"]
    feature_labels = {"sysBP":"Systolic blood pressure", "diaBP":"Diastolic blood pressure", "totChol":"Total cholesterol", "heartRate":"Resting heart rate", "glucose":"Fasting glucose", "BMI":"BMI", "age":"Age", "currentSmoker":"Current smoker", "cigsPerDay":"Cigarettes per day", "gender":"Gender", "education":"Education", "BPMeds":"BP medication", "prevalentStroke":"Previous stroke", "prevalentHyp":"Hypertension", "diabetes":"Diabetes"}
    units = {"sysBP":"mmHg", "diaBP":"mmHg", "totChol":"mg/dL", "heartRate":"bpm", "glucose":"mg/dL", "BMI":"kg/m²", "age":"years", "cigsPerDay":"per day"}
    def display_value(key):
        value = patient[key]
        if key in ["gender"]: return "Male" if value == 1 else "Female"
        if key in ["currentSmoker", "BPMeds", "prevalentStroke", "prevalentHyp", "diabetes"]: return "Yes" if value else "No"
        if key == "education": return f"Level {int(value)}"
        suffix = units.get(key, "")
        return f"{value:g} {suffix}".strip()
    increasing = [f for f in all_factors if f["contribution"] > 0]
    decreasing = [f for f in all_factors if f["contribution"] < 0]
    inc, dec = st.columns(2)
    with inc:
        st.markdown("#### ↑ Contributed toward higher model output")
        for f in increasing[:5]: st.write(f"↑ **{feature_labels[f['feature']]}** · {display_value(f['feature'])} · contributed to the model's prediction")
    with dec:
        st.markdown("#### ↓ Contributed toward lower model output")
        for f in decreasing[:5]: st.write(f"↓ **{feature_labels[f['feature']]}** · {display_value(f['feature'])} · contributed to the model's prediction")
        if not decreasing: st.caption("No leading features reduced the model output for this assessment.")
    if mode == "Simple explanation":
        for i, f in enumerate(all_factors[:4], 1):
            direction = "increased" if f["contribution"] > 0 else "decreased" if f["contribution"] < 0 else "had little effect on"
            st.write(f"{i}. {feature_labels[f['feature']]} ({display_value(f['feature'])}) {direction} the model's predicted probability.")
        vals = [f["contribution"] for f in all_factors]
        names = [feature_labels[f["feature"]] for f in all_factors]
        fig, ax = plt.subplots(figsize=(9, 5.2)); fig.patch.set_facecolor(palette["surface"]); ax.set_facecolor(palette["surface"])
        ax.barh(names[::-1], vals[::-1], color=[palette["high"] if v > 0 else palette["teal"] for v in vals[::-1]])
        ax.axvline(0, color=palette["muted"], linewidth=.8); ax.set_xlabel("SHAP contribution to hybrid probability", color=palette["muted"]); ax.tick_params(colors=palette["muted"])
        fig.tight_layout(); st.pyplot(fig, width="stretch"); plt.close(fig)
    else:
        technical = pd.DataFrame([{"Feature": feature_labels[f["feature"]], "Patient value": display_value(f["feature"]), "SHAP value": f"{f['contribution']:+.6f}", "Direction": f["direction"].title()} for f in all_factors])
        st.dataframe(technical, width="stretch", hide_index=True)
        try:
            import shap
            order = result["feature_order"]
            explanation = shap.Explanation(values=np.array([next(f["contribution"] for f in all_factors if f["feature"] == key) for key in order]),
                base_values=result["shap_base_value"], data=np.array([float(patient[key]) for key in order]), feature_names=[feature_labels[k] for k in order])
            fig = plt.figure(figsize=(9, 6)); shap.plots.waterfall(explanation, max_display=12, show=False); st.pyplot(fig, width="stretch"); plt.close(fig)
        except Exception as exc:
            st.warning(f"Hybrid SHAP waterfall is unavailable: {exc}")

    with st.expander("Patient assessment summary"):
        st.dataframe(pd.DataFrame([{
            "Age": display_value("age"), "Gender": display_value("gender"), "Smoking": display_value("currentSmoker"),
            "BP medication": display_value("BPMeds"), "Previous stroke": display_value("prevalentStroke"),
            "Hypertension": display_value("prevalentHyp"), "Diabetes": display_value("diabetes"),
            "Total cholesterol": display_value("totChol"), "Systolic BP": display_value("sysBP"),
            "Diastolic BP": display_value("diaBP"), "BMI": display_value("BMI"),
            "Heart rate": display_value("heartRate"), "Glucose": display_value("glucose"),
            "Hybrid probability": f"{result['probability']:.1%}", "Risk category": category,
        }]).T.rename(columns={0:"Current assessment value"}), width="stretch")

    st.markdown("### Intelligent decision support")
    insights = result["decision_support"]
    insight_cols = st.columns(min(3, len(insights)))
    for i, insight in enumerate(insights):
        with insight_cols[i % len(insight_cols)]:
            with st.container(border=True): st.caption(insight)
    st.caption("These general educational insights should be reviewed with a qualified healthcare professional.")

    with st.container(key="report-panel"):
        st.markdown("### Generate clinical AI report")
        if st.button("Generate report", type="primary", key="generate_patient_report"):
            try:
                from src.report import build_report
                report = build_report(patient, result, metadata)
                st.session_state.generated_report = report
                st.session_state.generated_report_patient = dict(patient)
                st.toast("Report generated for this assessment.", icon=":material/check_circle:")
            except Exception as exc:
                st.error(f"Report generation failed: {exc}")
        if st.session_state.get("generated_report") and st.session_state.get("generated_report_patient") == patient:
            st.success("Report generated successfully")
            st.download_button("Download PDF report", st.session_state.generated_report,
                               file_name="xai-cvd-assessment.pdf", mime="application/pdf", key="download_patient_report")
            with st.expander("Preview report contents"):
                st.write("This PDF contains the current patient summary, hybrid prediction, model comparison, model consensus, hybrid SHAP values and chart, decision support, limitations, and disclaimer.")


def hybrid_page():
    model, metadata = get_artifacts()
    st.markdown('<div class="section-kicker">Machine learning · deep learning · explanation</div><div class="section-title">Hybrid AI architecture</div>', unsafe_allow_html=True)
    if model is None:
        st.info("The architecture is ready; train the model bundle to display actual model metrics and alpha calibration.")
        stages = [("Patient data", "The system accepts only the 15 tabular predictors in the existing CHD dataset."),
                  ("Preprocessing", "Imputation, encoding, scaling, and resampling are fitted on training partitions only."),
                  ("Machine learning", "Logistic Regression, Random Forest, and XGBoost are compared; one tree model forms the ML branch."),
                  ("Deep learning", "A tabular MLP uses BatchNorm, ReLU, dropout, weighted loss, Adam, and early stopping."),
                  ("Hybrid engine", "A validation-calibrated weight combines the ML branch probability and MLP probability."),
                  ("Hybrid XAI", "SHAP PermutationExplainer is intended to explain the final hybrid prediction function."),
                  ("Decision support + report", "General educational information and a current-assessment PDF are generated after training.")]
        for row in range(0, len(stages), 2):
            cols=st.columns(2)
            for col,(title,detail) in zip(cols,stages[row:row+2]):
                with col:
                    with st.popover(title): st.write(detail)
        return
    st.write(f"The final probability combines the selected tree model ({model['tree_model_name']}) and a tabular MLP. The ensemble weight was selected on an internal validation split; it is not chosen arbitrarily.")
    st.latex(r"P_{hybrid} = \alpha P_{tree} + (1-\alpha)P_{MLP}")
    st.metric("Validation-calibrated tree weight · α", f"{model['alpha']:.2f}")
    st.caption(f"Calibration score: {metadata['alpha_calibration_score']:.3f} composite · MLP early stopping epoch: {metadata['mlp_best_epoch']}")
    architecture = [
        ("Patient data", "Fifteen tabular predictors from the existing CHD dataset; no imaging or wearable data."),
        ("Preprocessing", "Training-fitted imputation, one-hot encoding, scaling, and training-only resampling."),
        ("Machine learning", f"Logistic regression, Random Forest, and XGBoost are evaluated. {model['tree_model_name']} forms the selected tree branch."),
        ("Deep learning", "A batch-normalized dense MLP with ReLU, dropout, weighted binary cross-entropy, Adam, and validation-based early stopping."),
        ("Hybrid engine", f"Combines tree probability and MLP probability with validation-calibrated alpha {model['alpha']:.2f}."),
        ("Hybrid XAI", "SHAP PermutationExplainer is applied to the final hybrid probability function."),
        ("Decision support and report", "General education insights and an on-demand patient-specific PDF report."),
    ]
    for row in range(0, len(architecture), 2):
        cols=st.columns(2)
        for col, (title, detail) in zip(cols, architecture[row:row+2]):
            with col:
                with st.popover(title): st.write(detail)
    st.markdown("### Hybrid AI performance")
    if metadata.get("comparison",{}).get("hybrid_best_by_composite"):
        st.success("Best-performing model by the reported holdout composite: Hybrid AI.")
    else:
        st.info(f"Best-performing model by the reported holdout composite: {metadata.get('best_model_by_composite')}. Hybrid AI is not reported as the best model.")
    records=[{"Model": name, "ROC-AUC": m["roc_auc"], "F1": m["f1"], "Recall": m["recall"], "Accuracy": m["accuracy"]} for name,m in metadata["metrics"].items()]
    st.dataframe(pd.DataFrame(records).set_index("Model").style.format("{:.3f}"), width="stretch")


def explainability_page():
    model, metadata = get_artifacts()
    st.markdown('<div class="section-kicker">Hybrid model explanation</div><div class="section-title">Understanding the model</div>', unsafe_allow_html=True)
    if model is None: return
    st.caption("Global importance and impact distribution explain the hybrid model across a training sample. Importance does not imply causation.")
    try:
        xai=joblib.load(ROOT/"models"/"shap_config.joblib")
        import shap
        feature_names=xai["feature_names"]
        sv=np.asarray(xai["values"]); xv=np.asarray(xai["feature_values"])
        view=shap.Explanation(values=sv, data=xv, feature_names=feature_names)
        st.markdown("### Global SHAP bar plot")
        fig=plt.figure(figsize=(9,5)); shap.plots.bar(view, max_display=15, show=False); st.pyplot(fig,width="stretch"); plt.close(fig)
        st.markdown("### SHAP beeswarm")
        fig=plt.figure(figsize=(9,6)); shap.plots.beeswarm(view,max_display=15,show=False); st.pyplot(fig,width="stretch"); plt.close(fig)
        st.caption("Global SHAP values were calculated for sampled training records using the final hybrid_predict function.")
    except Exception as exc:
        st.warning(f"Global SHAP plots are not available: {exc}")
    if st.session_state.get("result"):
        st.markdown("### Current patient waterfall")
        result=st.session_state.result
        patient=st.session_state.patient
        try:
            import shap
            ordered=result["feature_order"]
            names={"sysBP":"Systolic blood pressure","diaBP":"Diastolic blood pressure","totChol":"Total cholesterol","heartRate":"Resting heart rate","glucose":"Fasting glucose","BMI":"BMI","age":"Age","currentSmoker":"Current smoker","cigsPerDay":"Cigarettes per day","gender":"Gender","education":"Education","BPMeds":"BP medication","prevalentStroke":"Previous stroke","prevalentHyp":"Hypertension","diabetes":"Diabetes"}
            explanation=shap.Explanation(values=np.array([next(f["contribution"] for f in result["shap_values"] if f["feature"]==name) for name in ordered]),base_values=result["shap_base_value"],data=np.array([float(patient[key]) for key in ordered]),feature_names=[names[k] for k in ordered])
            fig=plt.figure(figsize=(9,6)); shap.plots.waterfall(explanation,max_display=14,show=False); st.pyplot(fig,width="stretch"); plt.close(fig)
        except Exception as exc: st.warning(f"Patient-specific hybrid waterfall is unavailable: {exc}")
    else:
        st.info("Complete an assessment to create a patient-specific hybrid explanation.")


def reports_page():
    st.markdown('<div class="section-kicker">Session-only generated documents</div><div class="section-title">Assessment reports</div>', unsafe_allow_html=True)
    report=st.session_state.get("generated_report")
    if not report:
        st.info("No report has been generated in this session. Complete an assessment, then choose Generate report.")
        if st.button("Go to risk assessment"): set_page("Assessment")
        return
    st.success("A report is available for the current assessment session.")
    st.download_button("Download PDF report", report, file_name="xai-cvd-assessment.pdf", mime="application/pdf", key="reports_download")
    with st.expander("Report preview", expanded=True):
        try:
            from streamlit_pdf_viewer import pdf_viewer
            pdf_viewer(input=report, width=900)
        except Exception:
            st.caption("Inline PDF preview package is unavailable. Download the generated PDF to review the complete report.")


def analytics_page(global_only=False):
    model, metadata = get_artifacts()
    if model is None: return
    st.markdown('<div class="section-kicker">Evaluation on the held-out dataset</div><div class="section-title">'+("Understanding the model" if global_only else "Model analytics")+'</div>', unsafe_allow_html=True)
    if not global_only:
        st.markdown(f"The deployed output is **Hybrid AI**. The table compares held-out performance; the top model by the recorded composite is **{metadata.get('best_model_by_composite', 'not available')}**. The hybrid branch and blend weight were chosen using training-only validation.")
        records=[]
        for name, m in metadata["metrics"].items():
            marker = " · Best on holdout" if name == metadata.get("best_model_by_composite") else " · Deployed output" if name == "Hybrid AI" else ""
            records.append({"Model": name + marker, **{k.upper().replace("_","-"):m[k] for k in ["accuracy","precision","recall","f1","roc_auc"]}})
        st.dataframe(pd.DataFrame(records).set_index("Model").style.format("{:.3f}"), width="stretch")
        tabs=st.tabs(list(metadata["metrics"].keys()))
        for tab,(name,m) in zip(tabs,metadata["metrics"].items()):
            with tab:
                c1,c2=st.columns(2)
                with c1:
                    st.markdown("**Confusion matrix**")
                    st.dataframe(pd.DataFrame(m["confusion_matrix"],index=["Actual 0","Actual 1"],columns=["Predicted 0","Predicted 1"]),width="stretch")
                with c2:
                    fig,ax=plt.subplots(figsize=(5,3.4)); ax.plot(m["roc_curve"]["fpr"],m["roc_curve"]["tpr"],label=f"ROC-AUC {m['roc_auc']:.3f}",color=palette["teal"]); ax.plot([0,1],[0,1],"--",color=palette["muted"]); ax.set(xlabel="False positive rate",ylabel="True positive rate",title=f"{name} ROC curve"); ax.legend(); fig.tight_layout(); st.pyplot(fig,width="stretch"); plt.close(fig)
        st.caption("Accuracy alone is insufficient for evaluating an imbalanced screening task. Scores are research evaluation results, not a clinical performance claim.")
    st.markdown("### Global SHAP importance")
    st.caption("Features with greatest mean absolute SHAP contribution across sampled training records. Importance does not imply causation.")
    global_data=metadata.get("global_shap",[])
    if global_data:
        top=global_data[:20]
        fig,ax=plt.subplots(figsize=(9,max(4,.35*len(top)))); ax.barh([x["feature"].replace("numeric__","").replace("categorical__","") for x in top][::-1],[x["importance"] for x in top][::-1],color=palette["teal"]); ax.set_xlabel("Mean absolute SHAP value"); fig.tight_layout(); st.pyplot(fig,width="stretch"); plt.close(fig)
        st.dataframe(pd.DataFrame(top).rename(columns={"feature":"Feature","importance":"Mean |SHAP|"}),width="stretch")
    else: st.warning("Global feature importance is missing from the saved model metadata.")
    report_file=ROOT/"reports/dataset_report.json"
    if report_file.exists():
        with st.expander("Dataset audit and class distribution"):
            report=json.loads(report_file.read_text(encoding="utf-8")); dist=report["class_distribution"]
            st.write(f"{report['rows_after_cleaning']:,} rows after cleaning from {report['rows_before_cleaning']:,}; {report['duplicate_rows_removed']:,} duplicates removed.")
            st.bar_chart(pd.Series({"No CHD in 10 years (0)":dist.get("0",dist.get(0,0)),"CHD in 10 years (1)":dist.get("1",dist.get(1,0))}),width="stretch")
            st.json(report)


def about_page():
    st.markdown('<div class="section-kicker">Scope and interpretation</div><div class="section-title">About XAI-CVD</div>',unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("**Prediction ≠ diagnosis.** This is an academic decision-support prototype for the supplied 10-year CHD dataset task. Its outputs are not validated for clinical decisions.")
        st.markdown("**SHAP ≠ causation.** Local and global feature contributions show how the selected model uses its input features; they do not prove a biological or medical cause.")
        st.markdown("**Risk bands are model-based.** The low, moderate, and high labels use configurable probability cutoffs and are not clinically validated.")
        st.markdown("**Privacy.** Patient inputs remain in the active browser session and are not written to files or logged by this app. Avoid identifiable information.")
    st.markdown("### How it works")
    st.write("Patient data → input validation → fitted preprocessing → selected ML model → probability → SHAP explanation → model-based category → general decision-support insights")
    with st.expander("Model and data pipeline"):
        st.write("Logistic Regression, Random Forest, and XGBoost are compared with a tabular MLP. A selected tree model and MLP form a weighted hybrid; alpha is calibrated on a training-only validation split. SHAP PermutationExplainer explains the final hybrid function. Imputation, encoding, scaling, and resampling are fitted within training-only pipelines. Training runs separately from the web app.")


page=st.session_state.page
if page=="Dashboard": landing_page()
elif page=="Assessment": assessment_page()
elif page=="Hybrid AI": hybrid_page()
elif page=="Explainability": explainability_page()
elif page=="Model analytics": analytics_page()
elif page=="Reports": reports_page()
else: about_page()

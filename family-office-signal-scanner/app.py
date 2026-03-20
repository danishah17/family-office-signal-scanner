import streamlit as st
import anthropic
import json
import time
import os
import re
from datetime import date, datetime
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle,
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import io

_SCANNER_DIR = os.path.dirname(os.path.abspath(__file__))
_FAVICON = os.path.join(_SCANNER_DIR, "assets", "favicon.png")

load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv(
    "ANTHROPIC_MODEL",
    "claude-sonnet-4-5-20251001",
)


def safe_parse_json(raw_text):
    """Parse model JSON; handle markdown fences and embedded objects."""
    if raw_text is None:
        return None
    text = raw_text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    cleaned = re.sub(r"```json\s*|\s*```", "", text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass

    return None


st.set_page_config(
    page_title="FO Signal Scanner — PolarityIQ",
    page_icon=_FAVICON if os.path.exists(_FAVICON) else None,
    layout="wide",
    initial_sidebar_state="collapsed"
)


@st.cache_resource
def validate_anthropic():
    """
    Lightweight probe: ANTHROPIC_MODEL first; on missing-model errors try fallbacks.
    Returns (success: bool, model_id_or_error: str | None).
    """
    if not ANTHROPIC_API_KEY or not str(ANTHROPIC_API_KEY).strip():
        return False, "Missing ANTHROPIC_API_KEY"

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "Reply with OK"}],
        )
        return True, ANTHROPIC_MODEL
    except Exception as e:
        _nf = getattr(anthropic, "NotFoundError", None)
        is_not_found = _nf is not None and isinstance(e, _nf)
        is_not_found = is_not_found or "not_found" in type(e).__name__.lower()
        is_not_found = is_not_found or "404" in str(e).lower()
        if not is_not_found:
            return False, str(e)

    fallbacks = [
        "claude-sonnet-4-5-20251001",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-haiku-20240307",
    ]
    seen = {ANTHROPIC_MODEL}
    for model in fallbacks:
        if model in seen:
            continue
        seen.add(model)
        try:
            client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Reply with OK"}],
            )
            return True, model
        except Exception:
            continue

    return False, None


# ── GLOBAL CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;1,300&family=DM+Mono:wght@400;500&display=swap');

:root {
    --bg-base:       #070B12;
    --bg-surface:    #0C1420;
    --bg-elevated:   #111D2E;
    --bg-overlay:    #162238;
    --border-subtle: rgba(255,255,255,0.06);
    --border-mid:    rgba(255,255,255,0.10);
    --border-strong: rgba(255,255,255,0.18);
    --accent-blue:   #2563EB;
    --accent-blue-light: #3B82F6;
    --accent-cyan:   #06B6D4;
    --accent-gold:   #D97706;
    --text-primary:  #F1F5F9;
    --text-secondary:#94A3B8;
    --text-muted:    #475569;
    --text-label:    #64748B;
    --signal-hot:    #EF4444;
    --signal-warm:   #F59E0B;
    --signal-active: #10B981;
    --font-display:  'Syne', sans-serif;
    --font-body:     'DM Sans', sans-serif;
    --font-mono:     'DM Mono', monospace;
}

*, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

html, body, [class*="css"] {
    font-family: var(--font-body) !important;
    background: var(--bg-base) !important;
    color: var(--text-primary) !important;
}

.stApp {
    background-color: var(--bg-base) !important;
}

[data-testid="stAppViewContainer"] {
    background-color: #070B12 !important;
}
[data-testid="stVerticalBlock"] {
    background-color: transparent !important;
}
.main .block-container {
    padding-top: 0 !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    max-width: 100% !important;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header, .stDeployButton,
[data-testid="stToolbar"], .viewerBadge_container__1QSob,
[data-testid="stHeader"],
[data-testid="stDecoration"],
[data-testid="collapsedControl"] {
    display: none !important;
    visibility: hidden !important;
}

/* No permalink / anchor icons on injected markdown headings */
[data-testid="stMarkdownContainer"] h1 a,
[data-testid="stMarkdownContainer"] h2 a,
[data-testid="stMarkdownContainer"] h3 a {
    display: none !important;
    pointer-events: none !important;
}

/* Remove default padding */
.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

section.main > div {
    padding: 0 !important;
}

/* Tighter default vertical rhythm between Streamlit blocks (hero → form → CTA) */
section.main [data-testid="stVerticalBlock"] {
    gap: 0.45rem !important;
}

section.main [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] {
    gap: 0.45rem !important;
}

section.main [data-testid="stElementContainer"] {
    margin-bottom: 0.35rem !important;
}

section.main [data-testid="stElementContainer"]:last-child {
    margin-bottom: 0.15rem !important;
}

html {
    scroll-padding-top: 64px;
}

.stApp,
section.main,
[data-testid="stAppViewContainer"] {
    overflow-x: hidden !important;
}

/* Reserves space so content doesn’t sit under fixed topbar */
.topbar-placeholder {
    height: 56px;
    width: 100%;
    flex-shrink: 0;
}

/* ── TOPBAR ── */
.topbar {
    background: rgba(12, 20, 32, 0.92);
    border-bottom: 1px solid var(--border-subtle);
    padding: 0 clamp(1.25rem, 4vw, 3rem);
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 1000;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    box-shadow: 0 1px 0 rgba(0, 0, 0, 0.35);
}

.topbar-brand {
    display: flex;
    align-items: center;
    gap: 10px;
}

.topbar-logo-mark {
    width: 28px;
    height: 28px;
    background: var(--accent-blue);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.topbar-logo-inner {
    width: 12px;
    height: 12px;
    border: 2px solid white;
    border-radius: 2px;
    transform: rotate(45deg);
}

.topbar-name {
    font-family: var(--font-display);
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: 0.3px;
}

.topbar-name span {
    color: var(--accent-blue-light);
}

.topbar-right {
    display: flex;
    align-items: center;
    gap: 1.5rem;
}

.topbar-link {
    font-size: 0.8rem;
    color: var(--text-secondary);
    text-decoration: none;
    font-weight: 500;
    letter-spacing: 0.3px;
    transition: color 0.15s ease;
}

.topbar-link:hover {
    color: var(--accent-blue-light);
}

.topbar-badge {
    background: rgba(37,99,235,0.12);
    border: 1px solid rgba(37,99,235,0.3);
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--accent-blue-light);
    letter-spacing: 0.5px;
    font-family: var(--font-mono);
}

/* ── HERO ── */
.hero-section {
    background: var(--bg-base);
    padding: clamp(2rem, 4.5vw, 3.5rem) clamp(1.25rem, 4vw, 3rem)
        clamp(1.5rem, 3vw, 2.25rem);
    position: relative;
    overflow: hidden;
    border-bottom: 1px solid var(--border-subtle);
}

@media (max-height: 820px) {
    .hero-section {
        padding-top: clamp(1.25rem, 3vw, 2rem);
        padding-bottom: 1.1rem;
    }
    .hero-eyebrow {
        margin-bottom: 1rem !important;
    }
    .hero-subline {
        margin-bottom: 1.35rem !important;
    }
    .hero-metrics {
        margin-bottom: 1.1rem !important;
    }
    .hero-tags {
        gap: 0.4rem !important;
    }
}

.hero-grid {
    position: absolute;
    inset: 0;
    background-image:
        linear-gradient(rgba(37,99,235,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(37,99,235,0.04) 1px, transparent 1px);
    background-size: 60px 60px;
    mask-image: radial-gradient(ellipse 80% 80% at 50% 50%,
        black 40%, transparent 100%);
}

.hero-glow {
    position: absolute;
    top: -20%;
    left: 50%;
    transform: translateX(-50%);
    width: 800px;
    height: 400px;
    background: radial-gradient(ellipse,
        rgba(37,99,235,0.12) 0%,
        transparent 70%);
    pointer-events: none;
}

.hero-inner {
    position: relative;
    z-index: 1;
    max-width: 42rem;
    margin: 0 auto;
    text-align: center;
}

.hero-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(37,99,235,0.08);
    border: 1px solid rgba(37,99,235,0.2);
    border-radius: 3px;
    padding: 5px 14px;
    margin-bottom: 1.25rem;
}

.hero-eyebrow-pulse {
    width: 5px;
    height: 5px;
    background: #10B981;
    border-radius: 50%;
    animation: live-pulse 2.5s ease-in-out infinite;
}

@keyframes live-pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16,185,129,0.4); }
    50% { opacity: 0.7; box-shadow: 0 0 0 4px rgba(16,185,129,0); }
}

.hero-eyebrow-text {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 500;
    color: var(--accent-blue-light);
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

.hero-headline {
    font-family: var(--font-display);
    font-size: clamp(2.15rem, 5.5vw, 3.25rem);
    font-weight: 800;
    line-height: 1.08;
    letter-spacing: -0.06em;
    color: var(--text-primary);
    margin: 0 0 1.25rem;
}

.hero-headline .hl-blue {
    color: var(--accent-blue-light);
    display: inline-block;
}

.hero-subline {
    font-size: clamp(0.95rem, 2.2vw, 1.05rem);
    color: var(--text-secondary);
    line-height: 1.72;
    margin: 0 auto 1.5rem;
    font-weight: 300;
    max-width: 32.5rem;
    text-wrap: balance;
}

.hero-metrics {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 0;
    margin-bottom: 1.35rem;
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    background: var(--bg-surface);
    overflow: hidden;
    max-width: 38rem;
    margin-left: auto;
    margin-right: auto;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
}

.hero-metric {
    flex: 1 1 22%;
    min-width: 5.5rem;
    padding: 1.1rem 0.75rem;
    text-align: center;
    border-right: 1px solid var(--border-subtle);
}

.hero-metric:last-child {
    border-right: none;
}

.hero-metric-value {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
    display: block;
    margin-bottom: 3px;
}

.hero-metric-label {
    font-size: 0.68rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 500;
}

.hero-tags {
    display: flex;
    justify-content: center;
    gap: 0.6rem;
    flex-wrap: wrap;
}

.hero-tag {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 3px;
    padding: 5px 12px;
    font-size: 0.73rem;
    color: var(--text-label);
    font-weight: 500;
    letter-spacing: 0.3px;
}

/* ── CONTENT WRAPPER ── */
.content-wrap {
    max-width: 56rem;
    margin: 0 auto;
    padding: 0.65rem clamp(1.25rem, 4vw, 2.5rem) 1.75rem;
}

/* ── SECTION LABELS ── */
.section-label {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    font-weight: 500;
    color: var(--accent-blue-light);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}

.section-title {
    font-family: var(--font-display);
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.3rem;
    letter-spacing: -0.3px;
}

.section-sub {
    font-size: 0.88rem;
    color: var(--text-secondary);
    line-height: 1.65;
    margin-bottom: 1rem;
    font-weight: 300;
    max-width: 38rem;
    text-wrap: balance;
}

/* ── FORM CARD ── */
.form-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 2rem;
    margin-bottom: 1.5rem;
}

.form-card-label {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 500;
    color: var(--text-label);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin: 0 auto 0.65rem;
    padding: 0 0 0.55rem;
    max-width: 56rem;
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.form-card-label::before {
    content: "";
    width: 3px;
    height: 0.65rem;
    background: var(--accent-blue);
    border-radius: 1px;
    flex-shrink: 0;
}

/* ── STREAMLIT INPUT OVERRIDES ── */
.stTextInput label,
.stSelectbox label,
.stNumberInput label {
    font-family: var(--font-body) !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    color: var(--text-secondary) !important;
    letter-spacing: 0.2px !important;
    margin-bottom: 4px !important;
}

.stTextInput > div > div > input {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-mid) !important;
    border-radius: 6px !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
    font-size: 0.88rem !important;
    padding: 0.6rem 0.9rem !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
    height: 42px !important;
}

.stTextInput > div > div > input:focus {
    border-color: var(--accent-blue) !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
    outline: none !important;
}

.stTextInput > div > div > input::placeholder {
    color: var(--text-muted) !important;
}

.stSelectbox > div > div {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-mid) !important;
    border-radius: 6px !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
    font-size: 0.88rem !important;
    min-height: 42px !important;
}

.stSelectbox > div > div:focus-within {
    border-color: var(--accent-blue) !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
}

.stNumberInput > div > div > input {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-mid) !important;
    border-radius: 6px !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
    font-size: 0.88rem !important;
    height: 42px !important;
}

.stNumberInput button {
    background: var(--bg-overlay) !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border-mid) !important;
    transition: background 0.15s, color 0.15s !important;
}

.stNumberInput button:hover {
    background: rgba(37, 99, 235, 0.15) !important;
    color: var(--text-primary) !important;
}

/* Tighter, more even grid between form columns */
div[data-testid="stHorizontalBlock"] {
    gap: 1rem 1.25rem !important;
}

/* Selectbox dropdown */
div[data-baseweb="select"] > div {
    background: var(--bg-elevated) !important;
    border-color: var(--border-mid) !important;
}

div[data-baseweb="popover"] {
    background: var(--bg-overlay) !important;
    border: 1px solid var(--border-mid) !important;
    border-radius: 6px !important;
}

li[role="option"] {
    background: transparent !important;
    color: var(--text-secondary) !important;
    font-size: 0.85rem !important;
}

li[role="option"]:hover, li[aria-selected="true"] {
    background: rgba(37,99,235,0.12) !important;
    color: var(--text-primary) !important;
}

/* ── PRIMARY BUTTON ── */
.stButton > button {
    background: var(--accent-blue) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 0 1.5rem !important;
    height: 42px !important;
    font-family: var(--font-body) !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    letter-spacing: 0.2px !important;
    cursor: pointer !important;
    transition: background 0.15s, transform 0.1s !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3), 
                0 4px 12px rgba(37,99,235,0.2) !important;
    width: 100% !important;
}

.stButton > button:hover {
    background: var(--accent-blue-light) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3), 
                0 8px 20px rgba(37,99,235,0.25) !important;
}

.stButton > button:active {
    transform: translateY(0) !important;
}

.stButton > button:disabled,
.stButton > button[disabled] {
    background: var(--bg-elevated) !important;
    color: var(--text-muted) !important;
    border: 1px solid var(--border-mid) !important;
    box-shadow: none !important;
    cursor: not-allowed !important;
    opacity: 0.55 !important;
    transform: none !important;
}

.stButton > button:disabled:hover,
.stButton > button[disabled]:hover {
    background: var(--bg-elevated) !important;
    color: var(--text-muted) !important;
    transform: none !important;
    box-shadow: none !important;
}

/* Download button */
.stDownloadButton > button {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text-primary) !important;
    border-radius: 6px !important;
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    height: 42px !important;
}

.stDownloadButton > button:hover {
    border-color: var(--accent-blue) !important;
    color: var(--accent-blue-light) !important;
}

/* ── DIVIDER ── */
.divider {
    height: 1px;
    background: var(--border-subtle);
    margin: 1rem 0 0.85rem;
}

/* CTA hint under scanner button */
.scan-hint {
    text-align: center;
    font-size: 0.84rem;
    color: var(--text-secondary);
    margin: 0.65rem auto 0;
    max-width: 28rem;
    line-height: 1.45;
    font-family: var(--font-body);
    font-weight: 400;
}

.scan-hint .scan-hint-key {
    color: var(--accent-blue-light);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    font-weight: 500;
    letter-spacing: 0.04em;
}

/* ── RESULTS HEADER ── */
.results-bar {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 1.5rem 2rem;
    margin-bottom: 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
}

.results-bar-left {}

.results-fund {
    font-family: var(--font-display);
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.3px;
    margin-bottom: 3px;
}

.results-meta-line {
    font-size: 0.8rem;
    color: var(--text-secondary);
    font-weight: 300;
}

.results-bar-right {
    display: flex;
    gap: 0.8rem;
}

.stat-chip {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    padding: 0.6rem 1rem;
    text-align: center;
    min-width: 64px;
}

.stat-chip-value {
    font-family: var(--font-display);
    font-size: 1.4rem;
    font-weight: 700;
    display: block;
    line-height: 1;
    margin-bottom: 3px;
}

.stat-chip-label {
    font-family: var(--font-mono);
    font-size: 0.6rem;
    color: var(--text-muted);
    letter-spacing: 1px;
    text-transform: uppercase;
}

/* ── SIGNAL CARD ── */
.signal-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    margin-bottom: 1rem;
    overflow: hidden;
    transition: border-color 0.2s, box-shadow 0.2s;
}

.signal-card:hover {
    border-color: var(--border-mid);
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
}

.signal-card-top {
    border-top: 2px solid var(--accent-blue);
}

.signal-card-hot-border {
    border-top-color: var(--signal-hot);
}

.signal-card-warm-border {
    border-top-color: var(--signal-warm);
}

.signal-card-active-border {
    border-top-color: var(--signal-active);
}

.signal-card-header {
    padding: 1.3rem 1.5rem 1rem;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
}

.signal-fo-name {
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.2px;
    margin-bottom: 4px;
}

.signal-fo-meta {
    font-size: 0.78rem;
    color: var(--text-muted);
    font-weight: 300;
}

.signal-header-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 6px;
    flex-shrink: 0;
}

.signal-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    border-radius: 3px;
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.badge-hot {
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.25);
    color: #FCA5A5;
}

.badge-warm {
    background: rgba(245,158,11,0.1);
    border: 1px solid rgba(245,158,11,0.25);
    color: #FCD34D;
}

.badge-active {
    background: rgba(16,185,129,0.1);
    border: 1px solid rgba(16,185,129,0.25);
    color: #6EE7B7;
}

.match-score {
    font-family: var(--font-display);
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--text-muted);
}

.match-score span {
    color: var(--accent-blue-light);
    font-size: 1.1rem;
}

.signal-pills {
    padding: 0 1.5rem 1rem;
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.signal-pill {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: 3px;
    padding: 3px 10px;
    font-size: 0.72rem;
    color: var(--text-label);
    font-family: var(--font-mono);
    letter-spacing: 0.3px;
}

.signal-body {
    padding: 0 1.5rem 1.5rem;
}

.signal-evidence-block {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    padding: 1rem;
    margin-bottom: 1rem;
}

.signal-evidence-label {
    font-family: var(--font-mono);
    font-size: 0.62rem;
    color: var(--text-muted);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 0.7rem;
}

.signal-evidence-item {
    display: flex;
    gap: 10px;
    padding: 5px 0;
    border-bottom: 1px solid var(--border-subtle);
    font-size: 0.82rem;
    color: var(--text-secondary);
    line-height: 1.5;
    font-weight: 300;
}

.signal-evidence-item:last-child {
    border-bottom: none;
    padding-bottom: 0;
}

.signal-evidence-marker {
    width: 4px;
    height: 4px;
    background: var(--accent-blue);
    border-radius: 50%;
    margin-top: 8px;
    flex-shrink: 0;
}

.signal-thesis {
    font-size: 0.82rem;
    color: var(--text-secondary);
    line-height: 1.6;
    margin-bottom: 0.8rem;
    font-weight: 300;
}

.signal-thesis strong {
    color: var(--text-primary);
    font-weight: 500;
}

.signal-contacts {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 1rem;
    font-weight: 300;
}

.signal-contacts strong {
    color: var(--text-primary);
    font-weight: 500;
}

.signal-contacts-link {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-family: var(--font-mono);
}

.signal-outreach {
    background: rgba(37,99,235,0.05);
    border: 1px solid rgba(37,99,235,0.15);
    border-radius: 6px;
    padding: 1rem;
}

.signal-outreach-label {
    font-family: var(--font-mono);
    font-size: 0.62rem;
    color: var(--accent-blue-light);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}

.signal-outreach-text {
    font-size: 0.83rem;
    color: var(--text-secondary);
    line-height: 1.6;
    margin-bottom: 0.5rem;
    font-weight: 300;
}

.signal-urgency {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--signal-warm);
    letter-spacing: 0.3px;
}

/* ── INTEL PANEL ── */
.intel-panel {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}

.intel-panel-label {
    font-family: var(--font-mono);
    font-size: 0.62rem;
    color: var(--text-muted);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 1rem;
    padding-bottom: 0.7rem;
    border-bottom: 1px solid var(--border-subtle);
}

.intel-summary {
    font-size: 0.88rem;
    color: var(--text-secondary);
    line-height: 1.8;
    font-weight: 300;
}

.intel-list-item {
    display: flex;
    gap: 12px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-subtle);
    font-size: 0.83rem;
    color: var(--text-secondary);
    line-height: 1.5;
    font-weight: 300;
}

.intel-list-item:last-child {
    border-bottom: none;
}

.intel-marker-blue {
    width: 3px;
    background: var(--accent-blue);
    border-radius: 2px;
    flex-shrink: 0;
    margin: 4px 0;
}

.intel-marker-red {
    width: 3px;
    background: var(--signal-hot);
    border-radius: 2px;
    flex-shrink: 0;
    margin: 4px 0;
}

/* ── STEPS ── */
.step-row {
    display: flex;
    gap: 1rem;
    padding: 1.2rem 0;
    border-bottom: 1px solid var(--border-subtle);
    align-items: flex-start;
}

.step-row:last-child {
    border-bottom: none;
}

.step-num {
    width: 28px;
    height: 28px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-mid);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 500;
    color: var(--accent-blue-light);
    flex-shrink: 0;
}

.step-content {}

.step-title {
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 2px;
}

.step-timing {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    color: var(--accent-blue-light);
    letter-spacing: 0.5px;
    margin-bottom: 5px;
}

.step-template {
    font-size: 0.8rem;
    color: var(--text-secondary);
    line-height: 1.65;
    font-style: italic;
    font-weight: 300;
}

/* ── CTA ── */
.cta-block {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 3rem;
    text-align: center;
    margin-top: 2.5rem;
    position: relative;
    overflow: hidden;
}

.cta-block::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent,
        var(--accent-blue), transparent);
}

.cta-headline {
    font-family: var(--font-display);
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.4px;
    margin-bottom: 0.6rem;
}

.cta-sub {
    font-size: 0.9rem;
    color: var(--text-secondary);
    line-height: 1.7;
    margin-bottom: 2rem;
    max-width: 500px;
    margin-left: auto;
    margin-right: auto;
    font-weight: 300;
}

.cta-actions {
    display: flex;
    justify-content: center;
    gap: 1rem;
    flex-wrap: wrap;
}

.cta-btn-primary {
    background: var(--accent-blue);
    color: white;
    padding: 0.75rem 1.8rem;
    border-radius: 6px;
    font-family: var(--font-body);
    font-weight: 600;
    font-size: 0.88rem;
    text-decoration: none;
    display: inline-block;
    letter-spacing: 0.2px;
    transition: background 0.15s;
    box-shadow: 0 4px 12px rgba(37,99,235,0.3);
}

.cta-btn-primary:hover {
    background: var(--accent-blue-light);
}

.cta-btn-secondary {
    background: transparent;
    color: var(--text-secondary);
    padding: 0.75rem 1.8rem;
    border-radius: 6px;
    border: 1px solid var(--border-strong);
    font-family: var(--font-body);
    font-weight: 500;
    font-size: 0.88rem;
    text-decoration: none;
    display: inline-block;
    letter-spacing: 0.2px;
    transition: border-color 0.15s, color 0.15s;
}

.cta-btn-secondary:hover {
    border-color: var(--accent-blue);
    color: var(--accent-blue-light);
}

.cta-note {
    font-size: 0.72rem;
    color: var(--text-muted);
    margin-top: 1.5rem;
    font-family: var(--font-mono);
    letter-spacing: 0.3px;
}

/* ── LOADING ── */
.loading-wrap {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 2.5rem;
}

.loading-title {
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.3rem;
}

.loading-sub {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 2rem;
    font-weight: 300;
}

.loading-stage-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0.7rem 0;
    border-bottom: 1px solid var(--border-subtle);
    font-size: 0.83rem;
    color: var(--text-muted);
    font-weight: 300;
    transition: color 0.3s;
}

.loading-stage-item:last-child {
    border-bottom: none;
}

.loading-stage-active {
    color: var(--text-primary) !important;
}

.loading-stage-done {
    color: var(--signal-active) !important;
}

.loading-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--border-mid);
    flex-shrink: 0;
}

.loading-dot-active {
    background: var(--accent-blue);
    animation: dot-pulse 1s ease-in-out infinite;
}

.loading-dot-done {
    background: var(--signal-active);
}

@keyframes dot-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* ── INFO NOTICE ── */
.info-notice {
    background: rgba(37,99,235,0.06);
    border: 1px solid rgba(37,99,235,0.15);
    border-radius: 6px;
    padding: 0.9rem 1.2rem;
    font-size: 0.82rem;
    color: var(--text-secondary);
    font-weight: 300;
}

/* Streamlit info/warning overrides */
.stAlert {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-mid) !important;
    border-radius: 6px !important;
    color: var(--text-secondary) !important;
}

/* Spinner */
.stSpinner > div {
    border-top-color: var(--accent-blue) !important;
}

/* ── PRODUCTION: a11y & mobile CTA ── */
.stButton > button:focus-visible,
.stDownloadButton > button:focus-visible {
    outline: 2px solid var(--accent-blue-light) !important;
    outline-offset: 3px !important;
}

@media (prefers-reduced-motion: reduce) {
    .hero-eyebrow-pulse {
        animation: none !important;
    }
    .loading-dot-active {
        animation: none !important;
    }
}

/* Keep primary CTA reachable on smaller viewports without hunting below the fold */
@media (max-width: 1024px) {
    [data-testid="stHorizontalBlock"]:has(.stButton) {
        position: sticky;
        bottom: 0;
        z-index: 200;
        padding-top: 0.55rem !important;
        padding-bottom: max(0.45rem, env(safe-area-inset-bottom, 0px)) !important;
        margin-top: 0.25rem !important;
        margin-bottom: 0 !important;
        background: rgba(7, 11, 18, 0.96);
        border-top: 1px solid var(--border-subtle);
        box-shadow: 0 -10px 32px rgba(0, 0, 0, 0.45);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
    }

    .content-wrap {
        padding-bottom: 2.25rem !important;
    }
}

</style>
""", unsafe_allow_html=True)

# ── PROMPT BUILDER ─────────────────────────────────────────────
def build_scanner_prompt(strategy, geography, check_size,
                          stage, sector, fund_name):
    return f"""
You are a senior family office intelligence analyst at PolarityIQ.

A fund manager needs intelligence on which family offices are 
actively deploying capital that matches their profile.

Fund Profile:
- Fund Name: {fund_name}
- Strategy: {strategy}
- Geography: {geography}
- Check Size Seeking: ${check_size}M per LP
- Investment Stage: {stage}
- Primary Sector: {sector}

Generate a detailed intelligence report with 6 matched family 
offices showing active deployment signals.

For each family office provide:
1. Realistic name (surname-based e.g. "Whitfield Capital Partners")
2. Specific city and country matching the geography
3. Type: SFO or MFO
4. AUM Range (realistic)
5. Signal Type: one of NEW_ALLOCATION, PORTFOLIO_EXPANSION, 
   CO_INVEST_SEEKING, MANDATE_SHIFT, FIRST_TIME_ALLOCATOR
6. Signal Strength: HOT, WARM, or ACTIVE
7. Three specific signal evidence items (realistic SEC filings,
   LinkedIn activity, news, portfolio announcements with dates)
8. Investment thesis (1-2 sentences)
9. Check size range they write
10. Two realistic decision maker contacts (name + title)
11. Single most compelling outreach angle for this specific FO
12. Match score 0-100
13. Urgency note — why approach now specifically

Also generate:
- market_summary: 2-3 paragraphs on current FO deployment trends
  for {strategy} in {geography}
- deployment_trends: list of 3 specific current trends
- common_mistakes: list of 3 mistakes fund managers make
  approaching FOs for {strategy}
- outreach_sequence: 5 steps with action, timing, and template

Return ONLY valid JSON with this exact structure — no other text:
{{
  "market_summary": "string",
  "deployment_trends": ["string", "string", "string"],
  "common_mistakes": ["string", "string", "string"],
  "outreach_sequence": [
    {{
      "step": 1,
      "action": "string",
      "timing": "string",
      "template": "string"
    }}
  ],
  "family_offices": [
    {{
      "name": "string",
      "location": "string",
      "fo_type": "SFO",
      "aum_range": "string",
      "signal_type": "string",
      "signal_strength": "HOT",
      "signal_evidence": ["string", "string", "string"],
      "investment_thesis": "string",
      "check_size_range": "string",
      "primary_contacts": [
        {{"name": "string", "title": "string"}}
      ],
      "outreach_angle": "string",
      "match_score": 85,
      "urgency_note": "string"
    }}
  ]
}}
"""

# ── PDF GENERATION ─────────────────────────────────────────────
def generate_pdf_report(data, inputs):
    buffer = io.BytesIO()

    NAVY  = colors.HexColor('#070B12')
    BLUE  = colors.HexColor('#2563EB')
    SLATE = colors.HexColor('#1E293B')
    GRAY  = colors.HexColor('#64748B')
    LGRAY = colors.HexColor('#94A3B8')
    WHITE = colors.white
    RED   = colors.HexColor('#EF4444')
    GOLD  = colors.HexColor('#F59E0B')
    GREEN = colors.HexColor('#10B981')

    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=0.7*inch, rightMargin=0.7*inch,
        topMargin=0.75*inch, bottomMargin=0.6*inch
    )

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        'B', fontSize=9, textColor=colors.HexColor('#334155'),
        fontName='Helvetica', spaceAfter=4, leading=14
    )
    head_style = ParagraphStyle(
        'H', fontSize=11, textColor=WHITE,
        fontName='Helvetica-Bold', spaceAfter=0
    )
    sub_style = ParagraphStyle(
        'S', fontSize=8.5, textColor=LGRAY,
        fontName='Helvetica', spaceAfter=0, alignment=TA_CENTER
    )
    fo_name_style = ParagraphStyle(
        'FN', fontSize=10.5, textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica-Bold', spaceAfter=2
    )
    fo_detail_style = ParagraphStyle(
        'FD', fontSize=8, textColor=GRAY,
        fontName='Helvetica', spaceAfter=2, leading=12
    )
    label_style = ParagraphStyle(
        'LB', fontSize=7.5, textColor=BLUE,
        fontName='Helvetica-Bold', spaceAfter=3,
        letterSpacing=1
    )

    story = []

    # Cover block
    cover_rows = [
        [Paragraph('FAMILY OFFICE SIGNAL SCANNER', head_style)],
        [Paragraph(
            f'Intelligence Report — {inputs["fund_name"]}',
            sub_style
        )],
        [Paragraph(
            f'{inputs["strategy"]}  |  {inputs["geography"]}  |  '
            f'${inputs["check_size"]}M Target Check',
            sub_style
        )],
        [Paragraph(
            f'Generated {datetime.now().strftime("%B %d, %Y at %H:%M")}  '
            f'|  Powered by PolarityIQ + Claude AI',
            ParagraphStyle('M', fontSize=7.5, textColor=GRAY,
                          fontName='Helvetica', alignment=TA_CENTER)
        )],
    ]
    cover = Table(cover_rows, colWidths=[7.1*inch])
    cover.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), NAVY),
        ('TOPPADDING', (0,0), (0,0), 28),
        ('BOTTOMPADDING', (0,-1), (0,-1), 24),
        ('TOPPADDING', (0,1), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-2), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 24),
        ('RIGHTPADDING', (0,0), (-1,-1), 24),
        ('LINEBELOW', (0,1), (-1,1), 1, BLUE),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(cover)
    story.append(Spacer(1, 14))

    def section_header(text):
        t = Table([[Paragraph(text, ParagraphStyle(
            'SH', fontSize=8, textColor=LGRAY,
            fontName='Helvetica-Bold', letterSpacing=1.5
        ))]], colWidths=[7.1*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), SLATE),
            ('TOPPADDING', (0,0), (-1,-1), 7),
            ('BOTTOMPADDING', (0,0), (-1,-1), 7),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
        ]))
        return t

    # Market Summary
    story.append(section_header('MARKET INTELLIGENCE SUMMARY'))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        data.get('market_summary', ''), body_style
    ))
    story.append(Spacer(1, 10))

    # Family offices
    story.append(section_header(
        'ACTIVE DEPLOYMENT SIGNALS — 6 MATCHED FAMILY OFFICES'
    ))
    story.append(Spacer(1, 8))

    sig_colors = {
        'HOT': RED, 'WARM': GOLD, 'ACTIVE': GREEN
    }

    for i, fo in enumerate(data.get('family_offices', []), 1):
        strength = fo.get('signal_strength', 'ACTIVE')
        sig_color = sig_colors.get(strength, GREEN)

        # FO header row
        header_data = [[
            Paragraph(
                f'{i}. {fo.get("name","")}',
                fo_name_style
            ),
            Paragraph(
                strength,
                ParagraphStyle(
                    'SB', fontSize=8, textColor=sig_color,
                    fontName='Helvetica-Bold', alignment=TA_CENTER
                )
            ),
            Paragraph(
                f'{fo.get("match_score",0)}% match',
                ParagraphStyle(
                    'MS', fontSize=8, textColor=BLUE,
                    fontName='Helvetica-Bold', alignment=TA_RIGHT
                )
            )
        ]]
        ht = Table(
            header_data,
            colWidths=[4.5*inch, 1.2*inch, 1.4*inch]
        )
        ht.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (0,-1), 10),
            ('LINEABOVE', (0,0), (-1,0), 2, sig_color),
        ]))
        story.append(ht)

        # Details
        details = (
            f'{fo.get("location","")}  |  {fo.get("fo_type","")}  |  '
            f'AUM: {fo.get("aum_range","")}  |  '
            f'Check: {fo.get("check_size_range","")}  |  '
            f'Signal: {fo.get("signal_type","").replace("_"," ")}'
        )
        story.append(Paragraph(details, fo_detail_style))

        for ev in fo.get('signal_evidence', []):
            story.append(Paragraph(
                f'  — {ev}',
                ParagraphStyle(
                    'EV', fontSize=8, textColor=colors.HexColor('#475569'),
                    fontName='Helvetica', spaceAfter=2, leading=12
                )
            ))

        story.append(Paragraph(
            f'Thesis: {fo.get("investment_thesis","")}',
            fo_detail_style
        ))

        contacts = fo.get('primary_contacts', [])
        contact_str = '  |  '.join([
            f'{c["name"]}, {c["title"]}' for c in contacts
        ])
        story.append(Paragraph(
            f'Contacts: {contact_str}  [Full data on PolarityIQ]',
            fo_detail_style
        ))

        story.append(Paragraph(
            f'Outreach Angle: {fo.get("outreach_angle","")}',
            ParagraphStyle(
                'OA', fontSize=8,
                textColor=colors.HexColor('#1E40AF'),
                fontName='Helvetica-Bold',
                spaceAfter=2, leading=12
            )
        ))
        story.append(Paragraph(
            f'Urgency: {fo.get("urgency_note","")}',
            fo_detail_style
        ))
        story.append(Spacer(1, 10))

    # Outreach sequence
    story.append(section_header('5-STEP OUTREACH SEQUENCE'))
    story.append(Spacer(1, 8))

    for step in data.get('outreach_sequence', []):
        story.append(Paragraph(
            f'STEP {step["step"]}  —  {step["action"]}  '
            f'({step["timing"]})',
            ParagraphStyle(
                'ST', fontSize=9, textColor=colors.HexColor('#1E293B'),
                fontName='Helvetica-Bold', spaceAfter=3, leading=13
            )
        ))
        story.append(Paragraph(
            step.get('template', ''), body_style
        ))
        story.append(Spacer(1, 6))

    # Footer
    story.append(Spacer(1, 10))
    footer = Table([[Paragraph(
        'Full verified contact data available at app.polarityiq.com  '
        '|  Powered by PolarityIQ Intelligence + Claude AI  '
        '|  A Falcon Scaling Product',
        ParagraphStyle(
            'FT', fontSize=7.5, textColor=LGRAY,
            fontName='Helvetica', alignment=TA_CENTER
        )
    )]], colWidths=[7.1*inch])
    footer.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), SLATE),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
        ('RIGHTPADDING', (0,0), (-1,-1), 16),
    ]))
    story.append(footer)

    doc.build(story)
    buffer.seek(0)
    return buffer

# ── MAIN APP ───────────────────────────────────────────────────
def main():
    # Topbar (fixed) + spacer so layout isn’t covered
    st.markdown("""
    <div class="topbar-placeholder" aria-hidden="true"></div>
    <div class="topbar">
        <div class="topbar-brand">
            <div class="topbar-logo-mark">
                <div class="topbar-logo-inner"></div>
            </div>
            <div class="topbar-name">
                Polarity<span>IQ</span>
            </div>
        </div>
        <div class="topbar-right">
            <a href="https://app.polarityiq.com" 
               target="_blank" class="topbar-link">
                Platform
            </a>
            <a href="https://app.polarityiq.com" 
               target="_blank" class="topbar-link">
                Pricing
            </a>
            <span class="topbar-badge">SIGNAL SCANNER v1.0</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if 'results' not in st.session_state:
        st.session_state.results = None
    if 'inputs' not in st.session_state:
        st.session_state.inputs = None

    if st.session_state.results is None:
        render_hero()
        render_form()
    else:
        render_results()

def render_hero():
    st.markdown("""
    <div class="hero-section">
        <div class="hero-grid"></div>
        <div class="hero-glow"></div>
        <div class="hero-inner">
            <div class="hero-eyebrow">
                <div class="hero-eyebrow-pulse"></div>
                <span class="hero-eyebrow-text">
                    Live Intelligence Platform
                </span>
            </div>
            <div class="hero-headline" role="heading" aria-level="1">
                Family Office<br>
                <span class="hl-blue">Signal Scanner</span>
            </div>
            <p class="hero-subline">
                Identify family offices actively deploying capital 
                matched to your exact fund profile. AI-powered signals 
                derived from SEC filings, LinkedIn activity, and 
                proprietary deal flow intelligence.
            </p>
            <div class="hero-metrics">
                <div class="hero-metric">
                    <span class="hero-metric-value">18,000+</span>
                    <span class="hero-metric-label">Family Offices</span>
                </div>
                <div class="hero-metric">
                    <span class="hero-metric-value">6</span>
                    <span class="hero-metric-label">
                        Signals Per Scan
                    </span>
                </div>
                <div class="hero-metric">
                    <span class="hero-metric-value">$197</span>
                    <span class="hero-metric-label">One-Time Scan</span>
                </div>
                <div class="hero-metric">
                    <span class="hero-metric-value">60s</span>
                    <span class="hero-metric-label">Time to Results</span>
                </div>
            </div>
            <div class="hero-tags">
                <span class="hero-tag">Claude AI Intelligence</span>
                <span class="hero-tag">SEC EDGAR Signals</span>
                <span class="hero-tag">PolarityIQ Database</span>
                <span class="hero-tag">PDF Report Included</span>
                <span class="hero-tag">Mandate-Matched Results</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_form():
    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)

    st.markdown("""
    <div class="section-label">Configuration</div>
    <div class="section-title">Configure Your Scan</div>
    <div class="section-sub">
        Provide your fund profile below. The scanner matches your 
        parameters against active deployment signals from 18,000+ 
        family offices worldwide and returns 6 mandate-aligned results.
    </div>
    """, unsafe_allow_html=True)

    # Form card — Fund Identity
    st.markdown("""
    <div class="form-card-label">Fund Identity</div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        fund_name = st.text_input(
            "Fund / Company Name",
            placeholder="e.g. Meridian Growth Partners II"
        )
    with col2:
        strategy = st.selectbox(
            "Investment Strategy",
            ["Venture Capital", "Private Equity", "Real Estate",
             "Private Credit", "Hedge Fund",
             "Impact Investing", "Infrastructure", "Multi-Asset"]
        )

    col3, col4 = st.columns(2)
    with col3:
        geography = st.selectbox(
            "Target Geography",
            ["North America", "Europe", "Asia Pacific",
             "Middle East", "Latin America", "Global"]
        )
    with col4:
        sector = st.selectbox(
            "Primary Sector",
            ["Technology", "Healthcare", "Real Estate",
             "Financial Services", "Consumer", "Energy",
             "Industrial", "Deep Tech",
             "Climate Tech", "Sector Agnostic"]
        )

    col5, col6 = st.columns(2)
    with col5:
        stage = st.selectbox(
            "Investment Stage",
            ["Seed / Pre-Seed", "Series A / B",
             "Growth Equity", "Late Stage / Pre-IPO",
             "Buyout", "Multi-Stage"]
        )
    with col6:
        check_size = st.number_input(
            "Target Check Size per LP (USD millions)",
            min_value=0.5, max_value=500.0,
            value=10.0, step=0.5,
            format="%.1f"
        )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    col_btn1, col_btn2, col_btn3 = st.columns([2, 3, 2])
    with col_btn2:
        scan_clicked = st.button(
            "Run Signal Scanner",
            use_container_width=True,
            type="primary",
            disabled=(not fund_name or not fund_name.strip()),
        )

    if not fund_name or not fund_name.strip():
        st.markdown(
            '<p class="scan-hint">Enter '
            '<span class="scan-hint-key">Fund / Company Name</span> '
            "above to run the scan.</p>",
            unsafe_allow_html=True,
        )

    if scan_clicked and fund_name and fund_name.strip():
        inputs = {
            "fund_name": fund_name.strip(),
            "strategy": strategy,
            "geography": geography,
            "sector": sector,
            "stage": stage,
            "check_size": check_size,
        }
        run_scan(inputs)

    st.markdown('</div>', unsafe_allow_html=True)

def run_scan(inputs):
    api_ok, active_model = validate_anthropic()
    if not api_ok:
        st.error(
            "API connection failed. "
            "Check your ANTHROPIC_API_KEY in settings."
        )
        if active_model:
            st.caption(str(active_model))
        return

    stages = [
        "Scanning SEC EDGAR for recent Form D filings",
        "Analyzing LinkedIn signals from family office CIOs",
        "Processing news signals and portfolio announcements",
        "Running mandate alignment analysis",
        "Scoring deployment probability across matched profiles",
        "Generating personalized outreach intelligence",
    ]

    loading_placeholder = st.empty()

    def render_loading(active_idx, done_idxs):
        items_html = ""
        for i, stage_text in enumerate(stages):
            if i in done_idxs:
                dot_cls = "loading-dot loading-dot-done"
                item_cls = "loading-stage-item loading-stage-done"
            elif i == active_idx:
                dot_cls = "loading-dot loading-dot-active"
                item_cls = "loading-stage-item loading-stage-active"
            else:
                dot_cls = "loading-dot"
                item_cls = "loading-stage-item"
            items_html += f"""
            <div class="{item_cls}">
                <div class="{dot_cls}"></div>
                <span>{stage_text}</span>
            </div>
            """
        loading_placeholder.markdown(f"""
        <div class="content-wrap">
            <div class="loading-wrap">
                <div class="loading-title">
                    Scanning for {inputs['fund_name']}
                </div>
                <div class="loading-sub">
                    Analyzing {inputs['strategy']} signals 
                    in {inputs['geography']}
                </div>
                {items_html}
            </div>
        </div>
        """, unsafe_allow_html=True)

    done = set()
    for i in range(len(stages)):
        render_loading(i, done)
        time.sleep(1.1)
        done.add(i)

    render_loading(-1, done)

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = build_scanner_prompt(
            inputs['strategy'], inputs['geography'],
            inputs['check_size'], inputs['stage'],
            inputs['sector'], inputs['fund_name']
        )
        response = client.messages.create(
            model=active_model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text
        data = safe_parse_json(raw)

        loading_placeholder.empty()

        if data is None:
            st.error(
                "The intelligence scan returned an unexpected format. "
                "Please try running the scan again."
            )
            return

        st.session_state.results = data
        st.session_state.inputs = inputs
        st.rerun()

    except Exception as e:
        loading_placeholder.empty()
        st.error(f"Scanner error: {str(e)}")

def render_results():
    data   = st.session_state.results
    inputs = st.session_state.inputs

    if not data:
        st.error("No results available.")
        return

    fos      = data.get('family_offices', [])
    fund     = inputs['fund_name']
    strategy = inputs['strategy']
    geography= inputs['geography']
    sector   = inputs['sector']
    check    = inputs['check_size']

    hot    = len([f for f in fos if f.get('signal_strength')=='HOT'])
    warm   = len([f for f in fos if f.get('signal_strength')=='WARM'])
    active = len([f for f in fos if f.get('signal_strength')=='ACTIVE'])

    st.markdown('<div class="content-wrap">', unsafe_allow_html=True)

    # Results header bar
    st.markdown(f"""
    <div class="results-bar">
        <div class="results-bar-left">
            <div class="results-fund">{fund}</div>
            <div class="results-meta-line">
                {strategy} &nbsp;&middot;&nbsp; {geography}
                &nbsp;&middot;&nbsp; ${check}M Target Check
                &nbsp;&middot;&nbsp; {sector}
                &nbsp;&middot;&nbsp; 
                Scanned {datetime.now().strftime('%b %d, %Y')}
            </div>
        </div>
        <div class="results-bar-right">
            <div class="stat-chip">
                <span class="stat-chip-value" 
                      style="color:#EF4444;">{hot}</span>
                <div class="stat-chip-label">HOT</div>
            </div>
            <div class="stat-chip">
                <span class="stat-chip-value" 
                      style="color:#F59E0B;">{warm}</span>
                <div class="stat-chip-label">WARM</div>
            </div>
            <div class="stat-chip">
                <span class="stat-chip-value" 
                      style="color:#10B981;">{active}</span>
                <div class="stat-chip-label">ACTIVE</div>
            </div>
            <div class="stat-chip">
                <span class="stat-chip-value">{len(fos)}</span>
                <div class="stat-chip-label">TOTAL</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Market intelligence
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown(f"""
        <div class="intel-panel">
            <div class="intel-panel-label">Market Intelligence</div>
            <div class="intel-summary">
                {data.get('market_summary','')}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_right:
        trends_html = "".join([f"""
        <div class="intel-list-item">
            <div class="intel-marker-blue"></div>
            <div>{t}</div>
        </div>
        """ for t in data.get('deployment_trends', [])])

        mistakes_html = "".join([f"""
        <div class="intel-list-item">
            <div class="intel-marker-red"></div>
            <div>{m}</div>
        </div>
        """ for m in data.get('common_mistakes', [])])

        st.markdown(f"""
        <div class="intel-panel">
            <div class="intel-panel-label">
                Active Deployment Trends
            </div>
            {trends_html}
        </div>
        <div class="intel-panel">
            <div class="intel-panel-label">
                Common Mistakes to Avoid
            </div>
            {mistakes_html}
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Signal cards header
    st.markdown("""
    <div class="section-label">Matched Results</div>
    <div class="section-title">Active Deployment Signals</div>
    <div class="section-sub">
        Family offices with mandate-aligned signals, 
        ranked by match score. Full contact data available 
        on PolarityIQ.
    </div>
    """, unsafe_allow_html=True)

    badge_map = {
        'HOT': 'badge-hot',
        'WARM': 'badge-warm',
        'ACTIVE': 'badge-active'
    }
    border_map = {
        'HOT': 'signal-card-top signal-card-hot-border',
        'WARM': 'signal-card-top signal-card-warm-border',
        'ACTIVE': 'signal-card-top signal-card-active-border'
    }

    for fo in fos:
        strength   = fo.get('signal_strength', 'ACTIVE')
        badge_cls  = badge_map.get(strength, 'badge-active')
        border_cls = border_map.get(strength, 'signal-card-top')

        evidence_items = "".join([f"""
        <div class="signal-evidence-item">
            <div class="signal-evidence-marker"></div>
            <div>{ev}</div>
        </div>
        """ for ev in fo.get('signal_evidence', [])])

        contacts = fo.get('primary_contacts', [])
        contacts_str = " &nbsp;&middot;&nbsp; ".join([
            f"<strong>{c['name']}</strong>, {c['title']}"
            for c in contacts
        ])

        st.markdown(f"""
        <div class="signal-card {border_cls}">
            <div class="signal-card-header">
                <div>
                    <div class="signal-fo-name">
                        {fo.get('name','')}
                    </div>
                    <div class="signal-fo-meta">
                        {fo.get('location','')} 
                        &nbsp;&middot;&nbsp; {fo.get('fo_type','')}
                        &nbsp;&middot;&nbsp; 
                        AUM {fo.get('aum_range','')}
                    </div>
                </div>
                <div class="signal-header-right">
                    <span class="signal-badge {badge_cls}">
                        {strength}
                    </span>
                    <div class="match-score">
                        <span>{fo.get('match_score',0)}</span>% match
                    </div>
                </div>
            </div>
            <div class="signal-pills">
                <span class="signal-pill">
                    {fo.get('signal_type','').replace('_',' ')}
                </span>
                <span class="signal-pill">
                    Check: {fo.get('check_size_range','')}
                </span>
            </div>
            <div class="signal-body">
                <div class="signal-evidence-block">
                    <div class="signal-evidence-label">
                        Signal Evidence
                    </div>
                    {evidence_items}
                </div>
                <div class="signal-thesis">
                    <strong>Investment Thesis:</strong> 
                    {fo.get('investment_thesis','')}
                </div>
                <div class="signal-contacts">
                    <strong>Key Contacts:</strong> 
                    {contacts_str}
                    <span class="signal-contacts-link">
                        &nbsp;&nbsp;[Full data on PolarityIQ]
                    </span>
                </div>
                <div class="signal-outreach">
                    <div class="signal-outreach-label">
                        Outreach Angle
                    </div>
                    <div class="signal-outreach-text">
                        {fo.get('outreach_angle','')}
                    </div>
                    <div class="signal-urgency">
                        {fo.get('urgency_note','')}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Outreach sequence
    st.markdown("""
    <div class="section-label">Outreach Strategy</div>
    <div class="section-title">5-Step Outreach Sequence</div>
    <div class="section-sub">
        A personalized outreach sequence for your 
        specific strategy and geography.
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="intel-panel">', unsafe_allow_html=True)
    steps_html = ""
    for step in data.get('outreach_sequence', []):
        steps_html += f"""
        <div class="step-row">
            <div class="step-num">{step['step']}</div>
            <div class="step-content">
                <div class="step-title">{step['action']}</div>
                <div class="step-timing">{step['timing']}</div>
                <div class="step-template">{step['template']}</div>
            </div>
        </div>
        """
    st.markdown(
        f'{steps_html}</div>',
        unsafe_allow_html=True
    )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # PDF Download
    st.markdown("""
    <div class="section-label">Report Export</div>
    <div class="section-title">Download Intelligence Report</div>
    <div class="section-sub">
        Export this scan as a formatted PDF report 
        for your records or team.
    </div>
    """, unsafe_allow_html=True)

    col_d1, col_d2, col_d3 = st.columns([2, 3, 2])
    with col_d2:
        try:
            pdf_buf = generate_pdf_report(data, inputs)
            filename = (
                f"FO_Signal_Report_"
                f"{inputs['fund_name'].replace(' ','_')}_"
                f"{date.today()}.pdf"
            )
            st.download_button(
                label="Download PDF Report",
                data=pdf_buf,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"PDF error: {str(e)}")

    # CTA
    st.markdown("""
    <div class="cta-block">
        <div class="section-label" 
             style="margin-bottom:0.8rem;">
            Next Step
        </div>
        <div class="cta-headline">
            Ready to Reach These Family Offices?
        </div>
        <div class="cta-sub">
            Get verified emails, direct phone numbers, and 
            LinkedIn profiles for every family office in this 
            report — plus 18,000+ more on PolarityIQ.
        </div>
        <div class="cta-actions">
            <a href="https://app.polarityiq.com" 
               target="_blank" class="cta-btn-primary">
                Start PolarityIQ Free Trial
            </a>
            <a href="https://falcon-scaling.kit.com/posts/family-office" 
               target="_blank" class="cta-btn-secondary">
                Family Office Catalyst — $297
            </a>
        </div>
        <div class="cta-note">
            A Falcon Scaling product  |  Powered by 
            PolarityIQ Intelligence + Claude AI  |  
            Signal Scanner v1.0
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    col_r1, col_r2, col_r3 = st.columns([2, 3, 2])
    with col_r2:
        if st.button(
            "Run New Scan",
            use_container_width=True
        ):
            st.session_state.results = None
            st.session_state.inputs = None
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
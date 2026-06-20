import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from io import BytesIO
import html
 
import database
from agent import (
    verify_product,
    trace_journey,
    get_manufacturer_risk_summary,
    chat_about_product,
    load_product_data,
    get_historical_summary
)
from pdf_export import generate_audit_pdf
 
database.init_db()
 
st.set_page_config(
    page_title="◈ NEXUS TRACE AI Supply Chain Intelligence",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)
 
# ─── SESSION STATE ────────────────────────────────────────────────────────────
DEFAULTS = {
    "chat_history": [],
    "active_product_id": None,
    "audit_history": {},
    "current_view": "◈ Analytics Dashboard",
    "sidebar_file_bytes": None,
    "sidebar_file_name": None,
    "last_audited": None,
    "selected_product": None,
    "investigator_search": "",
    "matching_products": [],
}
for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default
 
# ─── CALLBACKS ────────────────────────────────────────────────────────────────
def set_view(view_name):
    st.session_state.current_view = view_name
 
def handle_sidebar_upload():
    uploaded = st.session_state.get("sidebar_uploader")
    if uploaded is not None:
        st.session_state.sidebar_file_bytes = uploaded.getvalue()
        st.session_state.sidebar_file_name = uploaded.name
        st.session_state.current_view = "⬢ Registry Operations"

 
# ─── STATUS BADGE HELPER ──────────────────────────────────────────────────────
def status_badge_html(status, size="normal"):
    status = str(status).upper()
    label_map = {
        "VERIFIED": ("VERIFIED", "verified"),
        "FLAGGED": ("FLAGGED", "flagged"),
        "PENDING": ("PENDING REVIEW", "pending"),
    }
    label, css_class = label_map.get(status, (status, "pending"))
    pad = "3px 10px" if size == "small" else "5px 14px"
    font_size = "0.72rem" if size == "small" else "0.82rem"
    return (
        f'<span class="status-badge status-badge--{css_class}" '
        f'style="padding:{pad};font-size:{font_size};">'
        f'<span class="status-dot"></span>{label}</span>'
    )
 
def ai_glow_card_html(title, body_text):
    safe_body = html.escape(body_text).replace("\n", "<br>")
    return (
        '<div class="ai-glow-card">'
        f'<div class="ai-glow-card__header">{html.escape(title)}</div>'
        f'<div class="ai-glow-card__body">{safe_body}</div>'
        '</div>'
    )
 
def metric_card_html(label, value, delta=None, delta_tone="good", tint=None):
    tint_class = f" metric-card--{tint}" if tint else ""
    delta_html = ""
    if delta:
        tone_class = "good" if delta_tone == "good" else "bad"
        delta_html = (
            f'<div class="metric-card__delta metric-card__delta--{tone_class}">'
            f'↑ {html.escape(str(delta))}</div>'
        )
    return (
        f'<div class="metric-card{tint_class}">'
        f'<div class="metric-card__label">{html.escape(label)}</div>'
        f'<div class="metric-card__value">{html.escape(str(value))}</div>'
        f'{delta_html}'
        '</div>'
    )
st.markdown("""
<div class="hero-heading">
    NEXUS TRACE • AI SUPPLY CHAIN INTELLIGENCE PLATFORM
</div>
""", unsafe_allow_html=True)
 
# ─── FONT / CSS INJECTION ─────────────────────────────────────────────────────
st.html("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900;1500;1800;2000&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800;900;1500;1800;2000&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800;900;1500;1800;2000&display=swap');
 
:root {
    --font-heading: 'Poppins', sans-serif;
    --font-body: 'Inter', system-ui, -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
 
    --bg-base: #0a0e17;
    --bg-elevated: #0f1420;
    --glass-bg: rgba(255, 255, 255, 0.035);
    --glass-bg-hover: rgba(255, 255, 255, 0.06);
    --glass-border: rgba(255, 255, 255, 0.08);
 
    --accent-blue: #3B82F6;
    --accent-cyan: #22D3EE;
    --accent-purple: #8B5CF6;
 
    --status-verified: #00CC96;
    --status-flagged: #EF553B;
    --status-pending: #FFA15A;
}
 
/* ── Base surfaces ───────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at 15% 0%, #101729 0%, var(--bg-base) 45%) !important;
}
[data-testid="stSidebar"] {
    background: var(--bg-elevated) !important;
    border-right: 1px solid var(--glass-border);
}
[data-testid="stHeader"] { background: transparent !important; }
 
/* ── Typography assignment ───────────────────────────────────────────── */
html, body, [class*="css"], .stApp,
div, span, p, label, button, input, textarea, select,
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"], [data-testid="stMetricLabel"],
[data-testid="stChatMessageContent"] {
    font-family: var(--font-body) !important;
    letter-spacing: normal !important;
    word-spacing: normal !important;
}
h1, h2, h3, h4, h5, h6 {
    font-family: var(--font-heading) !important;
    font-weight: 750 !important;
    letter-spacing: -0.01em !important;
}
code, pre, kbd, samp, [data-testid="stMetricValue"] {
    font-family: var(--font-mono) !important;
}
    .sidebar-brand-text {
    display: flex;
    flex-direction: column;
}

.brand-title {
    font-family: var(--font-heading);
    font-size: 1.75rem;
    font-weight: 900;
    letter-spacing: -0.5px;
    line-height: 1;
    color: #F8FAFC;
}

.brand-title {
    font-family: var(--font-heading);
    font-size: 1.66rem;
    font-weight: 950;
    letter-spacing: -0.3px;
    line-height: 1;
    color: #F8FAFC;
}

.brand-subtitle {
    margin-top: 4px;
    font-size: 0.78rem;
    font-weight: 500;
    color: rgba(255,255,255,0.60);
    letter-spacing: 0.3px;
}
        
    .sidebar-section-title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    color:#22D3EE;

    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: 0.3px;

}
 
/* Material icons must stay on their own glyph font no matter what */
.material-icons, .material-icons-rounded, .material-symbols-outlined,
.material-symbols-rounded, .material-symbols-sharp,
[class*="material-icons"], [class*="material-symbols"],
[data-testid="stIconMaterial"], [data-testid="stIconMaterial"] *,
span[data-testid="stIconMaterial"], button [data-testid="stIconMaterial"],
details summary [data-testid="stIconMaterial"] {
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-size: 1.15rem !important;
    line-height: 1 !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 1.15rem !important;
    min-width: 1.15rem !important;
    overflow: hidden !important;
}
button, button *, [role="button"], [role="button"] * {
    font-family: var(--font-body) !important;
    white-space: normal !important;
}
button [data-testid="stIconMaterial"], [role="button"] [data-testid="stIconMaterial"] {
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
}
 
/* ── Glass surfaces: metrics, containers, expanders, dataframes ─────── */
[data-testid="stMetric"] {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 14px;
    padding: 14px 16px 10px 16px;
}
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border) !important;
    border-radius: 14px;
    backdrop-filter: blur(10px);
}
[data-testid="stExpander"] {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border) !important;
    border-radius: 12px;
}
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--glass-border);
}
 
/* ── Buttons ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] button[kind="secondary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
    background: transparent !important;
    border: 1px solid var(--glass-border) !important;
    text-align: left !important;
}
[data-testid="stSidebar"] button[kind="primary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-cyan)) !important;
    border: none !important;
    box-shadow: 0 0 16px rgba(59, 130, 246, 0.45);
    text-align: left !important;
}
button[kind="primary"], [data-testid="stBaseButton-primary"] {
    box-shadow: 0 0 14px rgba(59, 130, 246, 0.35);
}
 
/* ── Status badges (glow = signal) ───────────────────────────────────── */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    border-radius: 999px;
    font-family: var(--font-body);
    font-weight: 600;
    line-height: 1.6;
}
.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}
.status-badge--verified { background: rgba(0, 204, 150, 0.12); color: var(--status-verified); }
.status-badge--verified .status-dot { background: var(--status-verified); box-shadow: 0 0 8px var(--status-verified); }
.status-badge--flagged { background: rgba(239, 85, 59, 0.12); color: var(--status-flagged); }
.status-badge--flagged .status-dot { background: var(--status-flagged); box-shadow: 0 0 8px var(--status-flagged); }
.status-badge--pending { background: rgba(255, 161, 90, 0.12); color: var(--status-pending); }
.status-badge--pending .status-dot { background: var(--status-pending); box-shadow: 0 0 8px var(--status-pending); }
 
/* ── AI glow card ─────────────────────────────────────────────────────── */
.ai-glow-card {
    background: linear-gradient(160deg, rgba(59,130,246,0.06), rgba(139,92,246,0.04));
    border: 1px solid rgba(139, 92, 246, 0.25);
    border-radius: 16px;
    padding: 18px 20px;
    box-shadow: 0 0 28px rgba(139, 92, 246, 0.14), 0 0 50px rgba(59, 130, 246, 0.08);
}
.ai-glow-card__header {
    font-family: var(--font-heading);
    font-weight: 600;
    font-size: 0.95rem;
    margin-bottom: 8px;
    color: #E0E7FF;
}
.ai-glow-card__body {
    font-family: var(--font-body);
    font-size: 0.92rem;
    line-height: 1.6;
    color: rgba(255,255,255,0.85);
}
 
/* ── AI pulse indicator ───────────────────────────────────────────────── */
.ai-pulse-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent-cyan);
    box-shadow: 0 0 6px var(--accent-cyan);
    animation: ai-pulse 2s ease-in-out infinite;
}
        .ledger-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
}
@keyframes ai-pulse {
    0% { box-shadow: 0 0 4px var(--accent-cyan); opacity: 0.7; }
    50% { box-shadow: 0 0 12px var(--accent-cyan); opacity: 1; }
    100% { box-shadow: 0 0 4px var(--accent-cyan); opacity: 0.7; }
}
 
/* ── Hero status banner ───────────────────────────────────────────────── */
.hero-banner {
    position: relative;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 16px;
    padding: 18px 24px;
    margin-bottom: 18px;
    display: flex;
    flex-wrap: wrap;
    gap: 28px;
    overflow: hidden;
}
.hero-banner::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan), var(--accent-purple));
}
.hero-stat { display: flex; flex-direction: column; gap: 2px; }
.hero-stat__label {
    font-family: var(--font-body);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: rgba(255,255,255,0.5);
}
.hero-stat__value {
    font-family: var(--font-mono);
    font-size: 1.3rem;
    font-weight: 700;
    color: #F1F5F9;
    display: flex;
    align-items: center;
    gap: 8px;
}
 
/* ── Sidebar brand card (CHANGE 1) ───────────────────────────────────── */
.sidebar-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 25px 25px;
    border-radius: 18px;
    background: linear-gradient(
        135deg,
        rgba(59,130,246,0.10),
        rgba(34,211,238,0.05)
    );
    border: 1px solid rgba(59,130,246,0.20);
    margin-bottom: 10px;
    box-shadow: 0 0 18px rgba(34,211,238,0.08);
}
.sidebar-brand-icon {
    width: 34px;
    height: 34px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    background: rgba(59,130,246,0.15);
    color: #22D3EE;
    font-size: 1rem;
    flex-shrink: 0;
}
.sidebar-brand-text {
    font-family: var(--font-heading);
    font-weight: 900;
    font-size: 0.95rem;
    line-height: 1.25;
    color: #F1F5F9;
}
    
.hero-heading{
    font-size:0.82rem;
    font-weight:700;
    letter-spacing:0.18em;
    text-transform:uppercase;
    color:rgba(255,255,255,0.45);
    margin-bottom:14px;
}
        
.section-title {
    display: flex;
    align-items: center;
    gap: 10px;

    font-size: 2rem;
    font-weight: 800;
    color: #F8FAFC;

    margin-bottom: 1rem;
}

.section-title .material-symbols-rounded {
    font-size: 1.6rem;
    color: #22D3EE;
}
 
/* ── Tinted metric cards (CHANGE 3) ──────────────────────────────────── */
.metric-card {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 14px;
    padding: 14px 16px 10px 16px;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 4px;
}
    .sidebar-status{
    margin-top:10px;
    margin-bottom:8px;
    font-size: 1rem;
    font-weight: 750;
    color: white;
}

.status-line{
    display:flex;
    align-items:center;
    gap:6px;
    font-size:0.78rem;
    color:rgba(255,255,255,0.55);
    margin-bottom:4px;
}
.metric-card__label {
    font-family: var(--font-body);
    font-size: 0.8rem;
    color: rgba(255,255,255,0.55);
}
.metric-card__value {
    font-family: var(--font-mono);
    font-size: 1.6rem;
    font-weight: 700;
    color: #F1F5F9;
}
.metric-card__delta {
    font-family: var(--font-body);
    font-size: 0.78rem;
    font-weight: 500;
}
.metric-card__delta--good { color: var(--status-verified); }
.metric-card__delta--bad  { color: var(--status-flagged); }

.metric-card--cyan  { background: rgba(34, 211, 238, 0.07); border-color: rgba(34, 211, 238, 0.22); }
.metric-card--green { background: rgba(0, 204, 150, 0.07);  border-color: rgba(0, 204, 150, 0.22); }
.metric-card--red   { background: rgba(239, 85, 59, 0.08);  border-color: rgba(239, 85, 59, 0.20); }

/* ── Quick Ingest file uploader glow ─────────────────────────────────── */
[data-testid="stFileUploader"]{
    border:1px solid rgba(34,211,238,0.15);
    border-radius:14px;
    padding:10px;
    background:rgba(255,255,255,0.02);
}
 
/* ── Sidebar collapse control sizing fix ─────────────────────────────── */
[data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"] {
    min-width: 2.2rem !important;
    width: 2.2rem !important;
    overflow: hidden !important;
}
[data-baseweb="select"] *, [data-testid="stFileUploader"] * {
    letter-spacing: normal !important;
    word-spacing: normal !important;
}
[data-testid="stFileUploader"] button { min-width: 6rem !important; }
[data-testid="stFileUploader"] button [data-testid="stIconMaterial"] { margin-right: 0.25rem !important; }
</style>
""")

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
counts = database.get_product_count()
total_products = sum(counts.values())

if total_products > 0:
    ledger_status = "ledger synced"
else:
    ledger_status = "ledger awaiting ingestion"

    counts = database.get_product_count()
total_products = sum(counts.values())

ledger_status = (
    "ledger synced"
    if total_products > 0
    else "ledger awaiting ingestion"
)

ledger_dot_color = (
    "#22D3EE"
    if total_products > 0
    else "#FF5C5C"
)
with st.sidebar:
    st.html(f"""
<div class="sidebar-brand">
    <div class="sidebar-brand-icon">◈</div>

    <div class="sidebar-brand-text">
        <div class="brand-title">NEXUS TRACE</div>
        <div class="brand-subtitle">AI Supply Chain Intelligence</div>
    </div>
</div>

<div class="sidebar-status">
    <div class="status-line">
        <span class="ai-pulse-dot"></span>
        AI monitor active
    </div>

    <div class="status-line">
        <span class="ledger-dot" style="background:{ledger_dot_color};box-shadow:0 0 8px {ledger_dot_color};"></span>
{ledger_status}
    </div>
</div>
""")


    st.divider()
 
    st.markdown('''
<div class="sidebar-section-title">
    <span class="material-symbols-rounded">apps</span>
    Navigation
</div>
''',
unsafe_allow_html=True
)
    VIEWS = [
        "◈ Analytics Dashboard",
        "▣ Immutable Ledger",
        "◉ AI Analyzer",
        "⬢ Registry Operations"
    ]
    for v in VIEWS:
        is_active = st.session_state.current_view == v
        st.button(
            v,
            key=f"nav_{v}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
            on_click=set_view,
            args=(v,)
        )
 
    st.divider()
    
 
    st.markdown('''
    <div class="sidebar-section-title">
        <span class="material-symbols-rounded">upload_file</span>
        Quick Ingest
    </div>
    ''',
    unsafe_allow_html=True
)
    st.file_uploader(
        "Upload CSV",
        type=["csv"],
        key="sidebar_uploader",
        on_change=handle_sidebar_upload,
        label_visibility="collapsed"
    )

    with open("demo_products.csv", "rb") as file:
     st.download_button(
        label="📥 Download Sample Dataset",
        data=file,
        file_name="demo_products.csv",
        mime="text/csv"
    )
    if st.session_state.sidebar_file_name:
        st.caption(f"Loaded: {st.session_state.sidebar_file_name}")
 
    st.divider()
 
    st.markdown('''
    <div class="sidebar-section-title">
        <span class="material-symbols-rounded">list_alt</span>
        Sample Product IDs
    </div>
    ''',
    unsafe_allow_html=True
)
    try:
        conn = database.get_connection()
        sample_df = pd.read_sql(
            "SELECT product_id, name FROM products ORDER BY RANDOM() LIMIT 8", conn
        )
        conn.close()
        if not sample_df.empty:
            for _, row in sample_df.iterrows():
                name_display = row["name"][:12] if row["name"] != "UNKNOWN" else "—"
                st.caption(f"`{row['product_id']}` — {name_display}")
        else:
            st.caption("No products yet.")
    except Exception:
        st.caption("No products yet.")
 
    st.divider()
 
    st.markdown(
        '''
    <div class="sidebar-section-title">
        <span class="material-symbols-rounded">quiz</span>
        FAQ
    </div>
    ''',
    unsafe_allow_html=True
)
    with st.expander("What does FLAGGED mean?"):
        st.caption("Anomalies detected — missing verifications, suspicious locations, or irregular batch IDs.")
    with st.expander("Is this a real blockchain?"):
        st.caption("Simulated ledger for demo. Logic is scalable to Hyperledger Fabric.")
    with st.expander("What AI model powers this?"):
        st.caption("LLaMA 3.3 70B via Groq API.")
    with st.expander("Can this scale?"):
        st.caption("Yes — swap SQLite for a real blockchain node, agent logic stays identical.")
 
    st.divider()
    st.caption("Built with LLaMA 3.3 70B + Groq")
 
# ══════════════════════════════════════════════════════════════════════════════
# VIEW 1 — ANALYTICS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.current_view == "◈ Analytics Dashboard":
 
    counts = database.get_product_count()
    total = sum(counts.values())
    flagged = counts.get("FLAGGED", 0)
    verified = counts.get("VERIFIED", 0)
    pending = counts.get("PENDING", 0)
    df = database.get_all_products_df()
    product_count = len(df)

    ledger_status = (
        "ledger synced"
        if product_count > 0
        else "ledger awaiting ingestion"
    )

    ledger_dot_color = (
        "#22D3EE"
        if product_count > 0
        else "#FF5C5C"
    )

    node_velocity = df["current_location"].nunique() if not df.empty else 0
    risk_rate = round((flagged / total * 100), 1) if total > 0 else 0
    system_integrity = round((verified / total * 100), 1) if total > 0 else 0
    
 
    st.markdown(
        f"""
        <div class="hero-banner">
            <div class="hero-stat">
                <span class="hero-stat__label">Clearance Rate</span>
                <span class="hero-stat__value">{system_integrity}%</span>
            </div>
            <div class="hero-stat">
                <span class="hero-stat__label">Ledger Status</span>
                <span class="hero-stat__value"><span class="ai-pulse-dot"></span>Synced</span>
            </div>
            <div class="hero-stat">
                <span class="hero-stat__label">AI Monitor</span>
                <span class="hero-stat__value"><span class="ai-pulse-dot"></span>Active</span>
            </div>
            <div class="hero-stat">
                <span class="hero-stat__label">Flagged Assets</span>
                <span class="hero-stat__value">{flagged}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
 
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(metric_card_html("Total Products", f"{total:,}", tint="cyan"), unsafe_allow_html=True)
    with col2:
        st.markdown(metric_card_html("Verified", f"{verified:,}", delta=f"{verified} clean", delta_tone="good", tint="green"), unsafe_allow_html=True)
    with col3:
        st.markdown(metric_card_html("Flagged", f"{flagged:,}", delta=f"{flagged} at risk", delta_tone="bad", tint="red"), unsafe_allow_html=True)
    with col4:
        st.markdown(metric_card_html("Risk Rate", f"{risk_rate}%"), unsafe_allow_html=True)
    with col5:
        st.markdown(metric_card_html("Node Velocity", f"{node_velocity} locations"), unsafe_allow_html=True)
 
    st.divider()
 
    if not df.empty:
        st.markdown("""
<div class="section-title">
    <span class="material-symbols-rounded">monitoring</span>
    Data Visualizations
</div>
""", unsafe_allow_html=True)
        colA, colB = st.columns(2)
        flagged_df = df[df["status"].str.upper() == "FLAGGED"]
 
        with colA:
            if not flagged_df.empty:
                loc_flags = flagged_df["current_location"].value_counts().head(10).reset_index()
                loc_flags.columns = ["location", "count"]
                st.markdown("""
<div class="sidebar-section-title">
    <span class="material-symbols-rounded">warning_amber</span>
    ANOMALY FREQUENCY BY LOCATION
</div>
""", unsafe_allow_html=True)
                fig_loc = px.bar(
                    loc_flags, x="location", y="count",
                    title="",
                    color="count", color_continuous_scale="Reds"
                )
                fig_loc.update_layout(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=10),
    xaxis_tickangle=-45,
    showlegend=False
)
                st.plotly_chart(fig_loc, use_container_width=True)
 
            if not flagged_df.empty:
                mfg_flags = flagged_df["manufacturer"].value_counts().head(10).reset_index()
                mfg_flags.columns = ["manufacturer", "count"]
                st.markdown("""
<div class="sidebar-section-title">
    <span class="material-symbols-rounded">flag</span>
    TOP FLAGGED MANUFACTURERS
</div>
""", unsafe_allow_html=True)
                fig_mfg = px.bar(
                    mfg_flags, x="manufacturer", y="count",
                    title="",
                    color="count", color_continuous_scale="OrRd"
                )
                fig_mfg.update_layout(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=10),
    xaxis_tickangle=-45
)
                st.plotly_chart(fig_mfg, use_container_width=True)
 
        with colB:
            status_counts = df["status"].value_counts().reset_index()
            status_counts.columns = ["status", "count"]
            st.markdown("""
<div class="sidebar-section-title">
    <span class="material-symbols-rounded">health_and_safety</span>
    RISK DISTRIBUTION
</div>
""", unsafe_allow_html=True)
            fig_donut = px.pie(
                status_counts, values="count", names="status",
                title="", hole=0.5,
                color="status",
                color_discrete_map={
                    "VERIFIED": "#00CC96",
                    "FLAGGED": "#EF553B",
                    "PENDING": "#FFA15A",
                    "UNKNOWN": "#636EFA"
                }
            )
            fig_donut.update_layout(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=10)
)
            st.plotly_chart(fig_donut, use_container_width=True)
 
            valid_dates = df[df["manufacture_date"] != "UNKNOWN"]
            if not valid_dates.empty:
                date_counts = valid_dates.groupby("manufacture_date").size().reset_index(name="count")
                st.markdown("""
<div class="sidebar-section-title">
    <span class="material-symbols-rounded">timeline</span>
    MANUFACTURING TIMELINE
</div>
""", unsafe_allow_html=True)
                fig_time = px.line(
                    date_counts.sort_values("manufacture_date"),
                    x="manufacture_date", y="count",
                    title="",
                    markers=True,
                    color_discrete_sequence=["#636EFA"]
                )
                fig_time.update_layout(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=10)
)
                st.plotly_chart(fig_time, use_container_width=True)
            else:
                st.info("No valid date data for timeline.")
 
        st.subheader("Risk Heatmap: Manufacturer vs Location")
        if not flagged_df.empty:
            valid_heatmap = flagged_df[
                (flagged_df["manufacturer"] != "UNKNOWN") &
                (flagged_df["current_location"] != "UNKNOWN")
            ]
            if not valid_heatmap.empty:
                heatmap_df = pd.crosstab(
                    valid_heatmap["manufacturer"],
                    valid_heatmap["current_location"]
                )
                st.dataframe(
                    heatmap_df.style.background_gradient(cmap="Reds"),
                    use_container_width=True
                )
            else:
                st.info("Not enough location data for heatmap.")
    else:
        st.warning("Database is empty. Add products to see analytics.")
 
# ══════════════════════════════════════════════════════════════════════════════
# VIEW 2 — IMMUTABLE LEDGER
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.current_view == "▣ Immutable Ledger":
    st.markdown("""
<div class="section-title">
    <span class="material-symbols-rounded">receipt_long</span>
    Immutable Ledger
</div>
                
""", unsafe_allow_html=True
)
    df = database.get_all_products_df()
    
 
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.multiselect(
                "Filter by Status",
                options=df["status"].unique().tolist(),
                default=df["status"].unique().tolist()
            )
        with col2:
            mfg_filter = st.multiselect(
                "Filter by Manufacturer",
                options=sorted(df["manufacturer"].unique().tolist()),
                default=[]
            )
        with col3:
            loc_filter = st.multiselect(
                "Filter by Location",
                options=sorted(df["current_location"].unique().tolist()),
                default=[]
            )
 
        filtered_df = df[df["status"].isin(status_filter)]
        if mfg_filter:
            filtered_df = filtered_df[filtered_df["manufacturer"].isin(mfg_filter)]
        if loc_filter:
            filtered_df = filtered_df[filtered_df["current_location"].isin(loc_filter)]
 
        st.caption(f"Showing {len(filtered_df):,} of {len(df):,} records")
 
        def color_status(val):
            val = str(val).upper()
            if val == "VERIFIED":
                return "color: #00CC96; font-weight: bold"
            if val == "FLAGGED":
                return "color: #EF553B; font-weight: bold"
            if val == "PENDING":
                return "color: #FFA15A; font-weight: bold"
            return ""
 
        st.dataframe(
            filtered_df.style.map(color_status, subset=["status"]),
            use_container_width=True,
            height=450
        )
 
        st.divider()
        st.subheader("Manufacturer Risk Intelligence")
        with st.expander("Run Pattern Detection"):
            if st.button("Scan for Manufacturer Patterns", key="scan_patterns"):
                with st.spinner("Analyzing..."):
                    risk_summary, patterns = get_manufacturer_risk_summary()
                if not patterns:
                    st.success("No systemic manufacturer risk patterns detected.")
                else:
                    st.error(f"{len(patterns)} manufacturer(s) flagged")
                    for mfr, info in patterns.items():
                        st.markdown(f"**`{mfr}`** — {info['flagged_count']}/{info['total_products']} flagged ({info['flag_rate']}%)")
                        st.caption(f"Affected: {', '.join(info['flagged_product_ids'])}")
                    if risk_summary:
                        st.warning(risk_summary)
    else:
        st.warning("Ledger is empty.")
 
# ══════════════════════════════════════════════════════════════════════════════
# VIEW 3 — AI FORENSIC INVESTIGATOR
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.current_view == "◉ AI Analyzer":
    st.markdown("""
<div class="section-title">
    <span class="material-symbols-rounded">smart_toy</span>
    AI Analyzer
</div>
""", unsafe_allow_html=True)
    df = database.get_all_products_df()
 
    if df.empty:
        st.warning("Ledger is empty. Add products first.")
    else:
        search_input = st.text_input(
            "Search Product ID",
            key="investigator_search",
            placeholder="e.g. PRD-9272, 9272, Component-9272"
        )
 
        run_audit = st.button(
            "Run Forensic Audit",
            type="primary",
            use_container_width=True,
            key="run_audit"
        )
 
        if search_input or st.session_state.matching_products:
            if search_input:
                search_terms = [
                    term.strip().lower().replace("-", "").replace(" ", "")
                    for term in search_input.split(",")
                    if term.strip()
                ]
 
                matching_products = []
                df_copy = df.copy()
                df_copy["_search_key"] = (
                    df_copy["product_id"]
                    .astype(str)
                    .str.lower()
                    .str.replace("-", "", regex=False)
                    .str.replace(" ", "", regex=False)
                )
 
                for term in search_terms:
                    result = df_copy[
                        df_copy["_search_key"].str.contains(term, na=False, regex=False)
                    ]
                    for _, row in result.iterrows():
                        pid = row["product_id"]
                        if pid not in [p["product_id"] for p in matching_products]:
                            matching_products.append(row.to_dict())
 
                st.session_state.matching_products = matching_products
 
            matching_products = st.session_state.matching_products
 
            if matching_products:
                st.subheader("Matching Products")
                cols = st.columns(3)
 
                for idx, product in enumerate(matching_products):
                    with cols[idx % 3]:
                        with st.container(border=True):
                            pid = product["product_id"]
                            history = get_historical_summary(pid)
                            status = str(product["status"]).upper()
 
                            st.markdown(f"### {pid}")
                            st.markdown(status_badge_html(status), unsafe_allow_html=True)
 
                            record_hash = product.get("record_hash", "")
                            if record_hash:
                                with st.container(border=True):
                                    st.markdown("### Integrity Verification")
                                    st.markdown("**Algorithm:** SHA-256")
                                    st.markdown(status_badge_html(status, size="small"), unsafe_allow_html=True)
                                    st.code(record_hash, language=None)
                                    st.caption("Fingerprint successfully stored in ledger")
 
                            st.caption(f"Manufacturer: {product['manufacturer']}")
                            st.caption(f"Location: {product['current_location']}")
                            st.metric("Events", history["total_events"])
 
                            if st.button("Open Investigation", key=f"open_{pid}"):
                                st.session_state.selected_product = pid
 
                if st.session_state.selected_product is not None:
                    actual_pid = st.session_state.selected_product
                    product_info = load_product_data(actual_pid)
                    selected_row = df[df["product_id"] == actual_pid]
 
                    if not selected_row.empty:
                        match = selected_row
                        status = str(selected_row.iloc[0]["status"]).upper()
 
                        if product_info:
                            fields = [
                                (k, v) for k, v in product_info.items()
                                if k not in ["extra_data", "added_timestamp"]
                            ]
                            info_cols = st.columns(3)
                            for i, (k, v) in enumerate(fields[:9]):
                                info_cols[i % 3].metric(
                                    k.replace("_", " ").title(),
                                    str(v)[:30] if v else "—"
                                )
 
                        historical = get_historical_summary(actual_pid)
                        if historical:
                            st.subheader("Historical Ledger Activity")
 
                            if historical["total_events"] > 15:
                                st.error("HIGH HISTORY COMPLEXITY")
                            elif historical["total_events"] > 8:
                                st.warning("MEDIUM HISTORY COMPLEXITY")
                            else:
                                st.success("LOW HISTORY COMPLEXITY")
 
                            col_a, col_b, col_c = st.columns(3)
                            col_a.metric("Total Events", historical["total_events"])
                            col_b.metric("Manufacturers", len(historical["manufacturers"]))
                            col_c.metric("Locations", len(historical["locations"]))
 
                            st.markdown(
                                f"**Manufacturers Seen:** {', '.join(historical['manufacturers'])}\n\n"
                                f"**Locations Visited:** {', '.join(historical['locations'])}"
                            )
 
                            status_text = " | ".join(
                                f"{k}: {v}" for k, v in historical["status_counts"].items()
                            )
                            st.info(f"Status Breakdown → {status_text}")
 
                        st.markdown(
                            f'<div style="margin:6px 0 14px 0;">{status_badge_html(status)} '
                            f'<span style="color:rgba(255,255,255,0.6);font-size:0.85rem;">— {actual_pid}</span></div>',
                            unsafe_allow_html=True
                        )
 
                        if run_audit:
                            if actual_pid not in st.session_state.audit_history:
                                with st.spinner("Running forensic analysis..."):
                                    report = verify_product(actual_pid)
                                    journey = trace_journey(actual_pid)
                                    st.session_state.audit_history[actual_pid] = {
                                        "report": report,
                                        "journey": journey
                                    }
                            st.session_state.active_product_id = actual_pid
                            if st.session_state.last_audited != actual_pid:
                                st.session_state.chat_history = []
                                st.session_state.last_audited = actual_pid
 
                        if actual_pid in st.session_state.audit_history:
                            cached = st.session_state.audit_history[actual_pid]
                            report = cached["report"]
                            journey = cached["journey"]
 
                            st.subheader("AI Forensic Audit Report")
                            st.markdown(
                                ai_glow_card_html("Forensic Summary", report),
                                unsafe_allow_html=True
                            )
 
                            st.subheader("Chain of Custody")
                            if journey:
                                j_cols = st.columns(len(journey))
                                for step, col in zip(journey, j_cols):
                                    with col:
                                        step_status = "VERIFIED" if step["verified"] else "FLAGGED"
                                        st.markdown(f"**{step['stage']}**")
                                        st.markdown(
                                            status_badge_html(step_status, size="small"),
                                            unsafe_allow_html=True
                                        )
                                        st.caption(step["location"])
                                        st.caption(step["date"])
 
                            st.divider()
                            st.subheader("Export Audit Report")
                            product_data = load_product_data(actual_pid)
                            with st.spinner("Generating PDF..."):
                                pdf_bytes = generate_audit_pdf(product_data, journey, report)
 
                            filename = f"audit_{actual_pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                            st.download_button(
                                label=f"Download {actual_pid} Audit Report (PDF)",
                                data=pdf_bytes,
                                file_name=filename,
                                mime="application/pdf",
                                type="primary",
                                key=f"dl_{actual_pid}"
                            )
 
                            st.divider()
                            st.subheader("Ask the Agent")
                            st.caption(f"Chatting about: **{actual_pid}**")
 
                            for msg in st.session_state.chat_history:
                                with st.chat_message(msg["role"]):
                                    st.write(msg["content"])
 
                            user_input = st.chat_input(
                                placeholder=f"Ask about {actual_pid} — e.g. 'Why is it flagged?' or 'What should I do next?'"
                            )
                            if user_input:
                                with st.chat_message("user"):
                                    st.write(user_input)
                                with st.spinner("Thinking..."):
                                    updated_history, reply = chat_about_product(
                                        actual_pid,
                                        st.session_state.chat_history,
                                        user_input
                                    )
                                    st.session_state.chat_history = updated_history
                                with st.chat_message("assistant"):
                                    st.write(reply)
 
                            if st.session_state.chat_history:
                                if st.button("Clear Chat", type="secondary", key=f"clear_chat_{actual_pid}"):
                                    st.session_state.chat_history = []
                                    st.rerun()
                        else:
                            st.info("Click 'Run Forensic Audit' to analyze this product.")
                    else:
                        st.error(f"Product '{actual_pid}' not found in ledger.")
            else:
                st.error(f"No product matching '{search_input}' found in ledger.")
 
# ══════════════════════════════════════════════════════════════════════════════
# VIEW 4 — REGISTER PRODUCT
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.current_view == "⬢ Registry Operations":
    st.markdown("""
<div class="section-title">
    <span class="material-symbols-rounded">inventory</span>
    Registry Operations
</div>
""", unsafe_allow_html=True)
    st.subheader("Add New Product")
 
    with st.form("add_product_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            p_id = st.text_input("Product ID (e.g., PRD-999)")
            name = st.text_input("Product Name")
            mfg = st.text_input("Manufacturer")
            batch = st.text_input("Batch ID")
        with col2:
            mfg_date = st.date_input("Manufacture Date")
            loc = st.text_input("Current Location")
            status = st.selectbox("Status", ["VERIFIED", "FLAGGED", "PENDING"])
 
        save_clicked = st.form_submit_button("Save to Ledger", type="primary")
 
    if save_clicked:
        if not p_id or not name:
            st.error("Product ID and Name are required.")
        else:
            success, message = database.add_product({
                "product_id": p_id,
                "name": name,
                "manufacturer": mfg,
                "batch_id": batch,
                "manufacture_date": str(mfg_date),
                "current_location": loc,
                "status": status
            })
            st.cache_data.clear()
            if success:
                st.success(f"{name} ({p_id}) added to ledger.")
                st.rerun()
            else:
                st.error(message)
 
    st.divider()
 
    st.subheader("Bulk Ingestion (ERP Sync)")
    st.write("Upload any CSV — the semantic mapper normalizes column names automatically.")
 
    uploaded_file = None
    if st.session_state.sidebar_file_bytes is not None:
        uploaded_file = BytesIO(st.session_state.sidebar_file_bytes)
        uploaded_file.name = st.session_state.sidebar_file_name
        st.success("File loaded from Quick Ingest sidebar.")
    else:
        uploaded_file = st.file_uploader("Upload CSV Manifest", type=["csv"], key="main_uploader")
 
    if uploaded_file is not None:
        try:
            uploaded_file.seek(0)
            bulk_df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"Could not read file: {e}. Please re-upload.")
            st.session_state.sidebar_file_bytes = None
            st.session_state.sidebar_file_name = None
            st.stop()
 
        st.write(f"**{len(bulk_df):,} rows detected. Review mappings:**")
        st.dataframe(bulk_df.head(3), use_container_width=True)
 
        st.write("### Column Mapping Suggestions")
        user_confirmed_map = {}
        for col in bulk_df.columns:
            best_match, score = database.get_best_match(col, database.SYNONYM_MAP)
            options = ["Ignore"] + database.CORE_FIELDS
            default_index = options.index(best_match) if best_match in options else 0
            confidence = f"{score}%" if score > 0 else "No match"
            selection = st.selectbox(
                f"**'{col}'** → AI suggests: `{best_match or 'Ignore'}` (Confidence: {confidence})",
                options,
                index=default_index,
                key=f"map_{col}"
            )
            if selection != "Ignore":
                user_confirmed_map[col] = selection
 
        if st.button("Confirm mappings and Upload", type="primary", key="commit_ingest"):
            with st.spinner(f"Ingesting {len(bulk_df):,} products..."):
                inserted, skipped = database.bulk_insert_products(
                    bulk_df,
                    manual_mapping=user_confirmed_map
                )
                st.cache_data.clear()
                st.session_state.sidebar_file_bytes = None
                st.session_state.sidebar_file_name = None
 
            if skipped > 0:
                st.warning(f"{inserted:,} products ingested, {skipped:,} skipped (duplicate product_id).")
            else:
                st.success(f"{inserted:,} products ingested.")
            st.rerun()
 
    st.divider()
 
    st.subheader("System Administration")
    with st.expander("Danger Zone — Admin Only"):
        st.warning("Factory reset will permanently destroy the ledger. Cannot be reversed.")
        confirm = st.text_input("Type 'DELETE' to confirm:")
        if st.button("Factory Reset Database", type="primary", use_container_width=True, key="factory_reset"):
            if confirm == "DELETE":
                database.clear_database()
                st.cache_data.clear()
                st.success("Ledger destroyed. Fresh genesis block created.")
                st.rerun()
            else:
                st.error("Type 'DELETE' exactly to confirm.")
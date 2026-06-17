import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from io import BytesIO

import database
from agent import (
    verify_product,
    trace_journey,
    get_manufacturer_risk_summary,
    chat_about_product,
    load_product_data
)
from pdf_export import generate_audit_pdf

database.init_db()

st.set_page_config(
    page_title="Supply Chain Verification Agent",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── SESSION STATE ────────────────────────────────────────────────────────────
DEFAULTS = {
    "chat_history": [],
    "active_product_id": None,
    "audit_history": {},
    "current_view": "📊 Analytics Dashboard",
    "font_choice": "Poppins",
    "sidebar_file_bytes": None,
    "sidebar_file_name": None,
    "last_audited": None,
}
for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ─── CALLBACKS ────────────────────────────────────────────────────────────────
def set_view(view_name):
    st.session_state.current_view = view_name

def set_font():
    st.session_state.font_choice = st.session_state.font_selector

def handle_sidebar_upload():
    uploaded = st.session_state.get("sidebar_uploader")
    if uploaded is not None:
        st.session_state.sidebar_file_bytes = uploaded.getvalue()
        st.session_state.sidebar_file_name = uploaded.name
        st.session_state.current_view = "➕ Add New Product"

# ─── FONT / CSS INJECTION ─────────────────────────────────────────────────────
FONTS = {
    "Poppins": "https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap",
    "Inter": "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap",
    "JetBrains Mono": "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&display=swap",
}

selected_font = st.session_state.font_choice

st.html(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS[selected_font]}" rel="stylesheet">
<link href="{FONTS['JetBrains Mono']}" rel="stylesheet">
<style>
:root {{
    --app-font: '{selected_font}', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}

html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
    font-family: var(--app-font) !important;
}}

[data-testid="stAppViewContainer"],
[data-testid="stSidebar"],
[data-testid="stMarkdownContainer"],
[data-testid="stText"],
[data-testid="stCaptionContainer"],
[data-testid="stMetric"],
[data-testid="stWidgetLabel"],
[data-testid="stForm"],
[data-testid="stDataFrame"],
[data-testid="stAlert"],
label,
input,
textarea,
select {{
    font-family: var(--app-font) !important;
    letter-spacing: normal !important;
    word-spacing: normal !important;
}}

[data-testid="stMarkdownContainer"] *,
[data-testid="stCaptionContainer"] *,
[data-testid="stMetric"] *,
[data-testid="stWidgetLabel"] *,
[data-testid="stAlert"] * {{
    font-family: var(--app-font) !important;
    letter-spacing: normal !important;
    word-spacing: normal !important;
}}

/* Keep Streamlit's internal Material icon ligatures from rendering as words. */
.material-icons,
.material-icons-rounded,
.material-symbols-outlined,
.material-symbols-rounded,
.material-symbols-sharp,
[class*="material-icons"],
[class*="material-symbols"],
[data-testid="stIconMaterial"],
[data-testid="stIconMaterial"] *,
span[data-testid="stIconMaterial"],
button [data-testid="stIconMaterial"],
details summary [data-testid="stIconMaterial"] {{
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
}}

button,
button *,
[role="button"],
[role="button"] * {{
    font-family: '{selected_font}', sans-serif !important;
    white-space: normal !important;
}}

button [data-testid="stIconMaterial"],
[role="button"] [data-testid="stIconMaterial"] {{
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
}}

h1, h2, h3, h4, h5, h6,
p, label, input, textarea, select,
div[data-testid="stMarkdownContainer"],
div[data-testid="stText"],
div[data-testid="stCaptionContainer"] {{
    font-family: var(--app-font) !important;
    line-height: 1.4 !important;
}}

code, pre, kbd, samp {{
    font-family: 'JetBrains Mono', monospace !important;
}}

/* Keep sidebar expanders in app font, not monospace */
[data-testid="stSidebar"] details summary,
[data-testid="stSidebar"] summary,
[data-testid="stSidebar"] .streamlit-expanderHeader {{
    font-family: var(--app-font) !important;
    display: flex !important;
    align-items: center !important;
    gap: 0.4rem !important;
}}

/* Keep collapse control compact if Streamlit changes icon rendering. */
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] {{
    min-width: 2.2rem !important;
    width: 2.2rem !important;
    overflow: hidden !important;
}}

/* Avoid weird spacing/overlap in selectbox and uploader text. */
[data-baseweb="select"] *,
[data-testid="stFileUploader"] * {{
    letter-spacing: normal !important;
    word-spacing: normal !important;
}}

[data-testid="stFileUploader"] button {{
    min-width: 6rem !important;
}}

[data-testid="stFileUploader"] button [data-testid="stIconMaterial"] {{
    margin-right: 0.25rem !important;
}}
</style>
""")

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔗 Supply Chain Agent")
    st.caption("AI-powered ledger verification")
    st.divider()

    st.markdown("**🎨 Font Style**")
    st.selectbox(
        "Choose Font",
        list(FONTS.keys()),
        index=list(FONTS.keys()).index(st.session_state.font_choice),
        key="font_selector",
        on_change=set_font,
        label_visibility="collapsed"
    )

    st.divider()

    st.markdown("**🧭 Navigation**")
    VIEWS = [
        "📊 Analytics Dashboard",
        "📇 Immutable Ledger",
        "🤖 AI Forensic Investigator",
        "➕ Add New Product"
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

    st.markdown("**📂 Quick Ingest**")
    st.file_uploader(
        "Upload CSV",
        type=["csv"],
        key="sidebar_uploader",
        on_change=handle_sidebar_upload,
        label_visibility="collapsed"
    )
    if st.session_state.sidebar_file_name:
        st.caption(f"Loaded: {st.session_state.sidebar_file_name}")

    st.divider()

    st.markdown("**🗂 Sample Product IDs**")
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

    st.markdown("**❓ FAQ**")
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
if st.session_state.current_view == "📊 Analytics Dashboard":

    counts = database.get_product_count()
    total = sum(counts.values())
    flagged = counts.get("FLAGGED", 0)
    verified = counts.get("VERIFIED", 0)
    pending = counts.get("PENDING", 0)
    df = database.get_all_products_df()
    node_velocity = df["current_location"].nunique() if not df.empty else 0
    risk_rate = round((flagged / total * 100), 1) if total > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("🗃 Total Products", f"{total:,}")
    col2.metric("✅ Verified", f"{verified:,}", delta=f"{verified} clean")
    col3.metric("🚨 Flagged", f"{flagged:,}", delta=f"{flagged} at risk", delta_color="inverse")
    col4.metric("⚡ Risk Rate", f"{risk_rate}%")
    col5.metric("📍 Node Velocity", f"{node_velocity} locations")

    st.divider()

    if not df.empty:
        st.subheader("Data Visualizations")
        colA, colB = st.columns(2)
        flagged_df = df[df["status"].str.upper() == "FLAGGED"]

        with colA:
            if not flagged_df.empty:
                loc_flags = flagged_df["current_location"].value_counts().head(10).reset_index()
                loc_flags.columns = ["location", "count"]
                fig_loc = px.bar(
                    loc_flags, x="location", y="count",
                    title="📍 Anomaly Frequency by Location",
                    color="count", color_continuous_scale="Reds"
                )
                fig_loc.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    xaxis_tickangle=-45,
                    showlegend=False
                )
                st.plotly_chart(fig_loc, use_container_width=True)

            if not flagged_df.empty:
                mfg_flags = flagged_df["manufacturer"].value_counts().head(10).reset_index()
                mfg_flags.columns = ["manufacturer", "count"]
                fig_mfg = px.bar(
                    mfg_flags, x="manufacturer", y="count",
                    title="🏭 Top Flagged Manufacturers",
                    color="count", color_continuous_scale="OrRd"
                )
                fig_mfg.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    xaxis_tickangle=-45
                )
                st.plotly_chart(fig_mfg, use_container_width=True)

        with colB:
            status_counts = df["status"].value_counts().reset_index()
            status_counts.columns = ["status", "count"]
            fig_donut = px.pie(
                status_counts, values="count", names="status",
                title="🎯 Risk Distribution", hole=0.5,
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
                paper_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_donut, use_container_width=True)

            valid_dates = df[df["manufacture_date"] != "UNKNOWN"]
            if not valid_dates.empty:
                date_counts = valid_dates.groupby("manufacture_date").size().reset_index(name="count")
                fig_time = px.line(
                    date_counts.sort_values("manufacture_date"),
                    x="manufacture_date", y="count",
                    title="📅 Manufacturing Timeline",
                    markers=True,
                    color_discrete_sequence=["#636EFA"]
                )
                fig_time.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig_time, use_container_width=True)
            else:
                st.info("No valid date data for timeline.")

        st.subheader("🔥 Risk Heatmap: Manufacturer vs Location")
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
elif st.session_state.current_view == "📇 Immutable Ledger":
    st.subheader("📇 Immutable Ledger")
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
        st.subheader("🏭 Manufacturer Risk Intelligence")
        with st.expander("Run Pattern Detection"):
            if st.button("🔍 Scan for Manufacturer Patterns", key="scan_patterns"):
                with st.spinner("Analyzing..."):
                    risk_summary, patterns = get_manufacturer_risk_summary()
                if not patterns:
                    st.success("✅ No systemic manufacturer risk patterns detected.")
                else:
                    st.error(f"🚨 {len(patterns)} manufacturer(s) flagged")
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
elif st.session_state.current_view == "🤖 AI Forensic Investigator":
    st.subheader("🤖 AI Forensic Investigator")
    df = database.get_all_products_df()

    if df.empty:
        st.warning("Ledger is empty. Add products first.")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            search_input = st.text_input(
                "Search Product ID",
                placeholder="e.g. PRD001, 9539, Component-9272"
            )
        with col2:
            st.write("")
            run_audit = st.button("🔍 Run Forensic Audit", type="primary", use_container_width=True, key="run_audit")

        if search_input:
            search_clean = search_input.strip().lower().replace("-", "").replace(" ", "")
            df_copy = df.copy()
            df_copy["_search_key"] = (
                df_copy["product_id"]
                .astype(str)
                .str.lower()
                .str.replace("-", "", regex=False)
                .str.replace(" ", "", regex=False)
            )
            match = df_copy[df_copy["_search_key"].str.contains(search_clean, na=False, regex=False)]

            if not match.empty:
                actual_pid = match.iloc[0]["product_id"]
                status = str(match.iloc[0]["status"]).upper()

                st.subheader("📋 Ledger Record")
                product_info = load_product_data(actual_pid)
                if product_info:
                    fields = [(k, v) for k, v in product_info.items() if k not in ["extra_data", "added_timestamp"]]
                    info_cols = st.columns(3)
                    for i, (k, v) in enumerate(fields[:9]):
                        info_cols[i % 3].metric(
                            k.replace("_", " ").title(),
                            str(v)[:30] if v else "—"
                        )

                if status == "VERIFIED":
                    st.success(f"✅ {actual_pid} — VERIFIED")
                elif status == "PENDING":
                    st.warning(f"⏳ {actual_pid} — PENDING REVIEW")
                else:
                    st.error(f"🚨 {actual_pid} — FLAGGED FOR INVESTIGATION")

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

                    st.subheader("🧠 AI Forensic Audit Report")
                    st.info(report)

                    st.subheader("⛓️ Chain of Custody")
                    if journey:
                        cols = st.columns(len(journey))
                        for step, col in zip(journey, cols):
                            with col:
                                if step["verified"]:
                                    st.success(f"✅ **{step['stage']}**")
                                else:
                                    st.error(f"🚨 **{step['stage']}**")
                                st.caption(step["location"])
                                st.caption(step["date"])

                    st.divider()
                    st.subheader("📄 Export Audit Report")
                    product_data = match.iloc[0].to_dict()
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_audit_pdf(product_data, journey, report)

                    filename = f"audit_{actual_pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    st.download_button(
                        label=f"⬇️ Download {actual_pid} Audit Report (PDF)",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                        type="primary",
                        key=f"dl_{actual_pid}"
                    )

                    st.divider()
                    st.subheader("💬 Ask the Agent")
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
                        if st.button("🗑️ Clear Chat", type="secondary", key=f"clear_chat_{actual_pid}"):
                            st.session_state.chat_history = []
                            st.rerun()
                else:
                    st.info("👆 Click 'Run Forensic Audit' to analyze this product.")
            else:
                st.error(f"❌ No product matching '{search_input}' found in ledger.")

# ══════════════════════════════════════════════════════════════════════════════
# VIEW 4 — ADD NEW PRODUCT
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.current_view == "➕ Add New Product":
    st.subheader("➕ Register New Product")

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

        save_clicked = st.form_submit_button("💾 Save to Ledger", type="primary")

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
                st.success(f"✅ {name} ({p_id}) added to ledger!")
                st.rerun()
            else:
                st.error(message)

    st.divider()

    st.subheader("📦 Bulk Ingestion (ERP Sync)")
    st.write("Upload any CSV — the semantic mapper normalizes column names automatically.")

    uploaded_file = None
    if st.session_state.sidebar_file_bytes is not None:
        uploaded_file = BytesIO(st.session_state.sidebar_file_bytes)
        uploaded_file.name = st.session_state.sidebar_file_name
        st.success("✅ File loaded from Quick Ingest sidebar!")
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

        st.write("### 🤖 Column Mapping Suggestions")
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

        if st.button("✅ Commit Mappings & Ingest", type="primary", key="commit_ingest"):
            with st.spinner(f"Ingesting {len(bulk_df):,} products..."):
                inserted, skipped = database.bulk_insert_products(
                    bulk_df,
                    manual_mapping=user_confirmed_map
                )
                st.cache_data.clear()
                st.session_state.sidebar_file_bytes = None
                st.session_state.sidebar_file_name = None

            if skipped > 0:
                st.warning(f"✅ {inserted:,} products ingested, {skipped:,} skipped due to duplicate product_id.")
            else:
                st.success(f"✅ {inserted:,} products ingested!")
            st.rerun()

    st.divider()

    st.subheader("⚙️ System Administration")
    with st.expander("⚠️ Danger Zone (Admin Only)"):
        st.warning("Factory reset will permanently destroy the ledger. Cannot be reversed.")
        confirm = st.text_input("Type 'DELETE' to confirm:")
        if st.button("🗑️ Factory Reset Database", type="primary", use_container_width=True, key="factory_reset"):
            if confirm == "DELETE":
                database.clear_database()
                st.cache_data.clear()
                st.success("Ledger destroyed. Fresh genesis block created.")
                st.rerun()
            else:
                st.error("Type 'DELETE' exactly to confirm.")

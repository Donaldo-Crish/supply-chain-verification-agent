import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

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

st.set_page_config(page_title="Supply Chain Verifier", page_icon="📦", layout="wide")

# ─── SESSION STATE ────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "active_product_id" not in st.session_state:
    st.session_state.active_product_id = None
if "last_verified_id" not in st.session_state:
    st.session_state.last_verified_id = None

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📋 How It Works")
    st.markdown("""
    This AI agent simulates a **blockchain-based supply chain verifier**.

    1. Enter a Product ID
    2. The agent queries the ledger
    3. AI analyzes the record with **forensic reasoning**
    4. Download the audit report as PDF
    5. Ask follow-up questions in the chat
    """)
    st.divider()

    st.markdown("### ✔ Available Product IDs")
    try:
        conn = database.get_connection()
        sample_df = pd.read_sql(
            "SELECT product_id, name FROM products ORDER BY RANDOM() LIMIT 10", conn
        )
        conn.close()
        if not sample_df.empty:
            for _, row in sample_df.iterrows():
                name_display = row['name'][:15] if row['name'] != 'UNKNOWN' else '—'
                st.text(f"{row['product_id']} | {name_display}")
        else:
            st.text("Database empty.")
    except:
        st.text("Could not load IDs.")

    st.divider()

    st.subheader("❓ FAQ")
    with st.expander("What does FLAGGED mean?"):
        st.write("The product has anomalies in its supply chain — missing verifications, suspicious locations, or irregular batch IDs.")
    with st.expander("Is this a real blockchain?"):
        st.write("This is a simulated ledger. The AI reasoning is real and scalable to Hyperledger Fabric.")
    with st.expander("What AI model powers this?"):
        st.write("LLaMA 3.3 70B via Groq API — one of the fastest open source models available.")
    with st.expander("Can this scale to real products?"):
        st.write("Yes — swap SQLite for a real blockchain node and the agent logic stays identical.")
    with st.expander("How do I use the dashboard charts?"):
        st.markdown("""
        - 🔍 **Box Zoom:** Drag a box to zoom in
        - ✥ **Pan:** Drag to slide around
        - 🏠 **Reset:** Double-click to reset view
        """)

# ─── HEADER ───────────────────────────────────────────────────────────────────
st.title("SUPPLY CHAIN VERIFICATION AGENT")
st.caption("AI-powered product authentication using immutable ledger tracking — Built with LLaMA 3.3 + Groq")
st.divider()

tab_chat, tab_dashboard, tab_add = st.tabs([
    "🔎 Verification & Chat",
    "📊 Analytics Dashboard",
    "➕ Add New Product"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — VERIFICATION & CHAT
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.subheader("🔎 Verify Products (Bulk Lookup)")

    with st.form("verify_form"):
        product_input = st.text_input(
            "Enter Product IDs (comma-separated)",
            placeholder="e.g. PRD001, PRD-9743, Component-9272"
        )
        submitted = st.form_submit_button("Verify Products", type="primary")

    # Load df once per tab render — cached so it's fast
    df = database.get_all_products_df()

    if submitted and product_input:
        pids = [p.strip() for p in product_input.split(",") if p.strip()]

        for pid in pids:
            st.markdown(f"### 🔍 Searching for: `{pid}`")

            # Partial match — handles dashes, case differences, partial IDs
            match = df[df["product_id"].str.contains(pid, case=False, na=False)]

            if not match.empty:
                actual_pid = match.iloc[0]["product_id"]
                status = match.iloc[0]["status"]

                with st.spinner(f"Analyzing {actual_pid}..."):
                    report = verify_product(actual_pid)
                    journey = trace_journey(actual_pid)

                # Update chat context to latest verified product
                if st.session_state.last_verified_id != actual_pid:
                    st.session_state.chat_history = []
                st.session_state.active_product_id = actual_pid
                st.session_state.last_verified_id = actual_pid

                if status.upper() == "VERIFIED":
                    st.success(f"✅ Product {actual_pid} — VERIFIED")
                else:
                    st.error(f"🚨 Product {actual_pid} — FLAGGED FOR INVESTIGATION")

                st.subheader("🧠 AI Forensic Audit Report")
                st.info(report)

                st.subheader("⛓️ Chain of Custody")
                if journey:
                    cols = st.columns(len(journey))
                    for i, (step, col) in enumerate(zip(journey, cols)):
                        with col:
                            if step["verified"]:
                                st.success(f"✅ **{step['stage']}**")
                            else:
                                st.error(f"🚨 **{step['stage']}**")
                            st.caption(step["location"])
                            st.caption(step["date"])
                else:
                    st.info("No tracking history found for this product.")

                # PDF Export
                st.subheader("📄 Export Audit Report")
                product_data = match.iloc[0].to_dict()
                with st.spinner(f"Generating PDF for {actual_pid}..."):
                    pdf_bytes = generate_audit_pdf(product_data, journey, report)

                filename = f"audit_{actual_pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                st.download_button(
                    label=f"⬇️ Download {actual_pid} Report (PDF)",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    type="primary",
                    key=f"dl_{actual_pid}_{datetime.now().strftime('%H%M%S')}"
                )
            else:
                st.error(f"❌ Product containing '{pid}' not found in the ledger.")

            st.divider()

    # ─── CHAT ─────────────────────────────────────────────────────────────────
    st.subheader("💬 Ask the Agent")
    active_pid = st.session_state.active_product_id

    if not active_pid:
        st.info("Verify a product above first — then ask follow-up questions here.")
    else:
        product_info = load_product_data(active_pid)
        if product_info:
            name = product_info.get('name', 'Unknown product')
            st.caption(f"Chatting about: **{active_pid}** — {name}")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        user_input = st.chat_input(
            placeholder=f"Ask about {active_pid} — e.g. 'Why is it flagged?' or 'What should I do next?'"
        )
        if user_input:
            with st.chat_message("user"):
                st.write(user_input)
            with st.spinner("Agent is thinking..."):
                updated_history, reply = chat_about_product(
                    active_pid, st.session_state.chat_history, user_input
                )
                st.session_state.chat_history = updated_history
            with st.chat_message("assistant"):
                st.write(reply)

        if st.session_state.chat_history:
            if st.button("🗑️ Clear Chat", type="secondary"):
                st.session_state.chat_history = []
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ANALYTICS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_dashboard:
    st.header("Supply Chain Risk Analytics")

    # Fast count query — no full df load for metrics
    counts = database.get_product_count()
    total = sum(counts.values())
    verified = counts.get('VERIFIED', 0)
    flagged = counts.get('FLAGGED', 0)
    pending = counts.get('PENDING', 0)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Products", f"{total:,}")
    col2.metric("Verified", f"{verified:,}", delta=f"{verified} clean")
    col3.metric("Flagged", f"{flagged:,}", delta=f"{flagged} suspicious", delta_color="inverse")
    col4.metric("Pending", f"{pending:,}")
    st.divider()

    # Manufacturer Risk Intelligence
    st.subheader("🏭 Manufacturer Risk Intelligence")
    with st.expander("Run Pattern Detection", expanded=False):
        if st.button("🔍 Scan for Manufacturer Patterns", type="secondary"):
            with st.spinner("Analyzing cross-product patterns..."):
                risk_summary, patterns = get_manufacturer_risk_summary()

            if not patterns:
                st.success("✅ No manufacturer-level risk patterns detected.")
            else:
                st.error(f"🚨 {len(patterns)} manufacturer(s) flagged with systemic risk patterns")
                for mfr, info in patterns.items():
                    with st.container():
                        st.markdown(f"**Manufacturer: `{mfr}`**")
                        mcol1, mcol2, mcol3 = st.columns(3)
                        mcol1.metric("Flagged Products", info["flagged_count"])
                        mcol2.metric("Total Products", info["total_products"])
                        mcol3.metric("Flag Rate", f"{info['flag_rate']}%")
                        st.caption(f"Affected IDs: {', '.join(info['flagged_product_ids'])}")
                        st.divider()
                if risk_summary:
                    st.subheader("🧠 AI Risk Intelligence Summary")
                    st.warning(risk_summary)

    st.divider()

    # Charts — load full df here only (cached)
    df = database.get_all_products_df()

    if not df.empty:
        st.subheader("Data Visualizations")
        colA, colB = st.columns(2)

        with colA:
            # Pie chart
            status_counts = df['status'].value_counts().reset_index()
            status_counts.columns = ['status', 'count']
            fig_pie = px.pie(
                status_counts, values='count', names='status',
                title="Product Status Distribution",
                color='status',
                color_discrete_map={
                    'VERIFIED': '#00CC96',
                    'FLAGGED': '#EF553B',
                    'PENDING': '#FFA15A',
                    'UNKNOWN': '#636EFA'
                }
            )
            st.plotly_chart(fig_pie, use_container_width=True)

            # Flagged by manufacturer
            flagged_df = df[df['status'].str.upper() == 'FLAGGED']
            if not flagged_df.empty:
                mfg_flags = flagged_df['manufacturer'].value_counts().head(10).reset_index()
                mfg_flags.columns = ['manufacturer', 'count']
                fig_mfg = px.bar(
                    mfg_flags, x='manufacturer', y='count',
                    title="Top 10 Flagged by Manufacturer",
                    color_discrete_sequence=['#EF553B']
                )
                fig_mfg.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_mfg, use_container_width=True)

        with colB:
            # Flagged by location
            if not flagged_df.empty:
                loc_flags = flagged_df['current_location'].value_counts().head(10).reset_index()
                loc_flags.columns = ['location', 'count']
                fig_loc = px.bar(
                    loc_flags, x='location', y='count',
                    title="Top 10 Flagged by Location",
                    color_discrete_sequence=['#FFA15A']
                )
                fig_loc.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_loc, use_container_width=True)

            # Manufacturing timeline — filter out UNKNOWN dates
            valid_dates = df[df['manufacture_date'] != 'UNKNOWN']
            if not valid_dates.empty:
                date_counts = valid_dates.groupby('manufacture_date').size().reset_index(name='count')
                date_counts = date_counts.sort_values('manufacture_date')
                fig_time = px.line(
                    date_counts, x='manufacture_date', y='count',
                    title="Manufacturing Timeline",
                    markers=True
                )
                st.plotly_chart(fig_time, use_container_width=True)
            else:
                st.info("No valid date data available for timeline.")

        # Risk heatmap
        st.subheader("Risk Heatmap: Manufacturer vs Location")
        if not flagged_df.empty:
            valid_heatmap = flagged_df[
                (flagged_df['manufacturer'] != 'UNKNOWN') &
                (flagged_df['current_location'] != 'UNKNOWN')
            ]
            if not valid_heatmap.empty:
                heatmap_df = pd.crosstab(
                    valid_heatmap['manufacturer'],
                    valid_heatmap['current_location']
                )
                st.dataframe(
                    heatmap_df.style.background_gradient(cmap='Reds'),
                    use_container_width=True
                )
            else:
                st.info("Not enough location data to generate heatmap. Upload a CSV with location data to see this.")
    else:
        st.warning("Database is empty. Add products or upload a CSV to get started.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ADD NEW PRODUCT
# ══════════════════════════════════════════════════════════════════════════════
with tab_add:
    st.header("Register New Product")

    with st.form("add_product_form", clear_on_submit=True):
        p_id    = st.text_input("Product ID (e.g., PRD-999)")
        name    = st.text_input("Product Name")
        mfg     = st.text_input("Manufacturer")
        batch   = st.text_input("Batch ID")
        mfg_date = st.date_input("Manufacture Date")
        loc     = st.text_input("Current Location")
        status  = st.selectbox("Status", ["VERIFIED", "FLAGGED", "PENDING"])

        if st.form_submit_button("Save to Ledger"):
            if not p_id or not name:
                st.error("Product ID and Name are required.")
            else:
                new_product = {
                    "product_id": p_id, "name": name, "manufacturer": mfg,
                    "batch_id": batch, "manufacture_date": str(mfg_date),
                    "current_location": loc, "status": status
                }
                database.add_product(new_product)
                st.cache_data.clear()  # clear cache so new product shows immediately
                st.success(f"✅ Added {name} ({p_id}) to the ledger!")
                st.rerun()

    st.divider()

    # ─── BULK UPLOAD ──────────────────────────────────────────────────────────
    st.subheader("Bulk Ingestion (ERP Sync)")
    st.write("Upload any CSV manifest. The semantic mapper will suggest column mappings — you can correct them before committing.")

    uploaded_file = st.file_uploader("Upload CSV Manifest", type=["csv"])

    if uploaded_file is not None:
        bulk_df = pd.read_csv(uploaded_file)
        st.write(f"**{len(bulk_df)} rows detected. Review mappings below:**")
        st.dataframe(bulk_df.head(3), use_container_width=True)

        st.write("### 🤖 Review Mapping Suggestions")
        user_confirmed_map = {}

        for col in bulk_df.columns:
            best_match, score = database.get_best_match(col, database.SYNONYM_MAP)
            options = ["Ignore"] + database.CORE_FIELDS
            default_index = options.index(best_match) if best_match in options else 0
            confidence = f"{score}%" if score > 0 else "No match"

            selection = st.selectbox(
                f"Column **'{col}'** → AI suggests: `{best_match or 'Ignore'}` (Confidence: {confidence})",
                options,
                index=default_index,
                key=f"map_{col}"
            )
            if selection != "Ignore":
                user_confirmed_map[col] = selection

        if st.button("✅ Commit Mappings & Ingest", type="primary"):
            with st.spinner(f"Ingesting {len(bulk_df)} products..."):
                database.bulk_insert_products(bulk_df, manual_mapping=user_confirmed_map)
                st.cache_data.clear()  # force dashboard to reload with new data
            st.success(f"✅ Successfully ingested {len(bulk_df)} products!")
            st.rerun()

    st.divider()

    # ─── DANGER ZONE ──────────────────────────────────────────────────────────
    st.subheader("System Administration")
    with st.expander("⚠️ Danger Zone (Admin Only)"):
        st.warning("Executing a factory reset will permanently destroy the current ledger. This action cannot be reversed.")
        confirm = st.text_input("Type 'DELETE' to confirm factory reset:")
        if st.button("🗑️ Factory Reset Database", type="primary", use_container_width=True):
            if confirm == "DELETE":
                database.clear_database()
                st.cache_data.clear()
                st.success("Ledger destroyed. A blank genesis block has been created.")
                st.rerun()
            else:
                st.error("You must type 'DELETE' exactly to authorize the reset.")
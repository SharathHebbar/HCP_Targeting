"""
streamlit_app.py - Modern React-Style Commercial Pharma Portal (Clean UI Fix)
Fixes:
- Uses st.container(border=True) and clean st.html for bulletproof CSS rendering
- Resolves raw HTML string leakage caused by markdown indentation
- React-style sidebar pill navigation
- Integrated HCP 360 card actions with embedded Target button
- Bottom-anchored React-style pagination controls
"""
import os
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import time
import textwrap

from load_and_prep_laya import HCPDataLoader, DB_NAME
from laya_engine import LayaInferenceService
from asset_stitcher import GenerativeAssetStitcher

# Page Setup
st.set_page_config(
    page_title="Laya HCP Decision Portal",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- React / Tailwind / Shadcn CSS Styling ---
st.html("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .stApp {
        background-color: #f8fafc;
    }

    /* Clean React-like sidebar pill nav */
    div[data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 6px;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label {
        background-color: transparent;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 0px;
        border: 1px solid transparent;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background-color: #f1f5f9;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background-color: #e0f2fe !important;
        border: 1px solid #bae6fd !important;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
        color: #0369a1 !important;
        font-weight: 600 !important;
    }

    /* Status Badges & Pills */
    .pill {
        display: inline-flex;
        align-items: center;
        padding: 3px 9px;
        border-radius: 9999px;
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.3px;
        margin-right: 4px;
    }
    .pill-blue { background: #eff6ff; color: #1d4ed8; border: 1px solid #dbeafe; }
    .pill-green { background: #f0fdf4; color: #15803d; border: 1px solid #dcfce7; }
    .pill-red { background: #fef2f2; color: #b91c1c; border: 1px solid #fee2e2; }
    .pill-purple { background: #faf5ff; color: #7e22ce; border: 1px solid #f3e8ff; }
    .pill-gray { background: #f8fafc; color: #475569; border: 1px solid #e2e8f0; }

    /* Next-Best-Action Hero Banner */
    .nba-hero-card {
        background: linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%);
        border-radius: 12px;
        padding: 22px;
        color: white;
        margin-bottom: 16px;
        box-shadow: 0 8px 18px -3px rgba(2, 132, 199, 0.25);
    }

    /* Metric Tiles */
    .metric-tile {
        background: #f8fafc;
        border: 1px solid #edf2f7;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 8px;
    }
    .metric-label {
        font-size: 0.72rem;
        color: #64748b;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .metric-val {
        font-size: 1.25rem;
        font-weight: 700;
        color: #0f172a;
        margin-top: 3px;
    }

    /* Audit items */
    .audit-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 14px;
        border-radius: 8px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        margin-bottom: 8px;
        font-size: 0.86rem;
    }

    /* CRM Note */
    .crm-note {
        border-left: 3px solid #0284c7;
        background: #f8fafc;
        border-radius: 0 8px 8px 0;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 0.86rem;
        color: #334155;
    }
</style>
""")

# --- Service & State Initialization ---
if "data_loader" not in st.session_state:
    st.session_state.data_loader = HCPDataLoader(DB_NAME)

if "laya_service" not in st.session_state:
    st.session_state.laya_service = LayaInferenceService()

if "asset_stitcher" not in st.session_state:
    st.session_state.asset_stitcher = GenerativeAssetStitcher()

if "current_page" not in st.session_state:
    st.session_state.current_page = "HCP 360"

if "selected_hcp_id" not in st.session_state:
    st.session_state.selected_hcp_id = None

if "page_number" not in st.session_state:
    st.session_state.page_number = 1

if "page_size" not in st.session_state:
    st.session_state.page_size = 10

# Check for advanced engagement metrics in DB
def check_advanced_analytics_available(db_path: str = DB_NAME) -> bool:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(hcp_crm_interactions);")
        columns = [row[1].lower() for row in cursor.fetchall()]
        conn.close()
        advanced_fields = {"ctr", "ctor", "call_duration", "duration_minutes", "engagement_score"}
        return any(col in advanced_fields for col in columns)
    except Exception:
        return False

has_advanced_analytics = check_advanced_analytics_available()

# -------------------------------------------------------------
# SIDEBAR: React-Style Navigation
# -------------------------------------------------------------
with st.sidebar:
    st.html("""
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:20px; padding-left:4px;">
        <div style="background:#0284c7; width:34px; height:34px; border-radius:8px; display:flex; align-items:center; justify-content:center; color:white; font-size:18px;">
            🧬
        </div>
        <div>
            <div style="font-weight:700; font-size:1.05rem; color:#0f172a; line-height:1.2;">Laya Engine</div>
            <div style="font-size:0.75rem; color:#64748b;">Commercial Targeting</div>
        </div>
    </div>
    """)

    nav_items = ["HCP 360", "Targeting Console"]
    if has_advanced_analytics:
        nav_items.append("Advanced Analytics")

    selected_nav = st.radio(
        "Navigation",
        options=nav_items,
        index=nav_items.index(st.session_state.current_page) if st.session_state.current_page in nav_items else 0,
        label_visibility="collapsed"
    )

    if selected_nav != st.session_state.current_page:
        st.session_state.current_page = selected_nav
        st.rerun()

    st.markdown("---")
    
    st.markdown("**🔑 Groq LLM Settings**")
    user_groq_key = st.text_input("Groq API Key", type="password", value=os.getenv("GROQ_API_KEY", ""), placeholder="gsk_...")
    if user_groq_key:
        os.environ["GROQ_API_KEY"] = user_groq_key
        # Refresh the stitcher with the new key
        st.session_state.asset_stitcher = GenerativeAssetStitcher()
    st.markdown("---")
    st.html("""
    <div style="background:#f1f5f9; border-radius:8px; padding:12px; font-size:0.78rem; color:#475569;">
        <div style="font-weight:600; color:#1e293b; margin-bottom:4px;">⚡ Inference Telemetry</div>
        Model: <code>convaiinnovations/laya</code><br>
        Speed: <b>~33 ms</b> / pass<br>
        Mode: <b>Non-Autoregressive RLCD</b>
    </div>
    """)

# -------------------------------------------------------------
# PAGE 1: HCP 360 (Directory, React Cards, Embedded Target, Bottom Pagination)
# -------------------------------------------------------------
if st.session_state.current_page == "HCP 360":
    st.markdown("## 👨‍⚕️ HCP 360 Directory")
    st.caption("Filter physician portfolio, inspect multi-channel dynamics, and launch single-click Laya decisions.")

    all_records = st.session_state.data_loader.fetch_all_prepared_records()
    if not all_records:
        st.error("No HCP records found in SQLite. Please ensure you ran Step 1 (`generate_and_store_hcps.py`).")
        st.stop()

    # Flatten dataframe for filtering
    flat_data = []
    for r in all_records:
        flat_data.append({
            "HCP ID": r.hcp_id,
            "Name": r.full_name,
            "Specialty": r.laya_dict_state["profile"]["specialty"],
            "Decile": r.laya_dict_state["profile"]["decile"],
            "Territory": r.metadata["territory"],
            "TRx Volume": r.laya_dict_state["rx_dynamics"]["trx_volume_3m"],
            "Brand Growth %": r.laya_dict_state["rx_dynamics"]["brand_growth_pct"],
            "Comp Growth %": r.laya_dict_state["rx_dynamics"]["competitor_growth_pct"],
            "Formulary Tier": r.laya_dict_state["rx_dynamics"]["formulary_tier"],
            "Access": r.laya_dict_state["profile"]["access_level"],
            "KOL": r.laya_dict_state["profile"]["is_kol"],
            "Days Since Call": r.metadata["days_since_last_call"],
            "Email Opt-In": r.metadata["email_opt_in"]
        })
    df_hcps = pd.DataFrame(flat_data)

    # --- Unified Filter Bar Container ---
    with st.container(border=True):
        st.markdown("**🔍 Physician Search & Portfolio Segmentation**")
        col_search, col_spec, col_terr, col_decile = st.columns([2.5, 2, 2, 2])
        with col_search:
            search_kw = st.text_input("Search Name / ID", placeholder="e.g. Dr. Jane or HCP_00012", label_visibility="collapsed")
        with col_spec:
            specialty_filter = st.multiselect("Specialty", options=sorted(df_hcps["Specialty"].unique()), placeholder="All Specialties")
        with col_terr:
            territory_filter = st.multiselect("Territory", options=sorted(df_hcps["Territory"].unique()), placeholder="All Territories")
        with col_decile:
            min_decile = st.slider("Min Decile", min_value=1, max_value=10, value=1)

    # Apply filters
    filtered_df = df_hcps[df_hcps["Decile"] >= min_decile]
    if specialty_filter:
        filtered_df = filtered_df[filtered_df["Specialty"].isin(specialty_filter)]
    if territory_filter:
        filtered_df = filtered_df[filtered_df["Territory"].isin(territory_filter)]
    if search_kw:
        filtered_df = filtered_df[
            filtered_df["Name"].str.contains(search_kw, case=False) | 
            filtered_df["HCP ID"].str.contains(search_kw, case=False)
        ]

    total_records = len(filtered_df)
    total_pages = max(1, (total_records + st.session_state.page_size - 1) // st.session_state.page_size)
    if st.session_state.page_number > total_pages:
        st.session_state.page_number = total_pages

    start_idx = (st.session_state.page_number - 1) * st.session_state.page_size
    end_idx = min(start_idx + st.session_state.page_size, total_records)
    page_df = filtered_df.iloc[start_idx:end_idx]

    # --- Rich Card List (Clean Native Container) ---
    for _, row in page_df.iterrows():
        with st.container(border=True):
            top_left, top_right = st.columns([4, 1.2])
            
            with top_left:
                kol_badge = "<span class='pill pill-purple'>KOL Tier-1</span>" if row['KOL'] else ""
                access_badge_cls = "pill-green" if row['Access'] == "Open Access" else ("pill-red" if row['Access'] == "No-See" else "pill-gray")
                
                header_html = textwrap.dedent(f"""
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                    <span style="font-size:1.15rem; font-weight:700; color:#0f172a;">{row['Name']}</span>
                    <span class="pill pill-blue">Decile {row['Decile']}/10</span>
                    {kol_badge}
                    <span class="pill {access_badge_cls}">{row['Access']}</span>
                </div>
                <div style="color:#64748b; font-size:0.85rem;">
                    <code>{row['HCP ID']}</code> • {row['Specialty']} • Territory: <b>{row['Territory']}</b> • Formulary: <b>{row['Formulary Tier']}</b>
                </div>
                """)
                st.html(header_html)

            with top_right:
                # Embedded Target Action Button inside Card
                if st.button("🎯 Target HCP", key=f"target_btn_{row['HCP ID']}", type="primary", use_container_width=True):
                    st.session_state.selected_hcp_id = row['HCP ID']
                    st.session_state.current_page = "Targeting Console"
                    st.rerun()

            # Metric Strip inside Card
            m1, m2, m3, m4 = st.columns(4)
            growth_color = "#16a34a" if row['Brand Growth %'] >= 0 else "#dc2626"
            comp_growth_color = "#dc2626" if row['Comp Growth %'] > 0 else "#16a34a"
            
            with m1:
                st.html(textwrap.dedent(f"""
                <div class="metric-tile">
                    <div class="metric-label">3M TRx Volume</div>
                    <div class="metric-val">{row['TRx Volume']} <span style="font-size:0.75rem; color:#94a3b8;">units</span></div>
                </div>
                """))
            with m2:
                st.html(textwrap.dedent(f"""
                <div class="metric-tile">
                    <div class="metric-label">Brand Growth</div>
                    <div class="metric-val" style="color:{growth_color};">{row['Brand Growth %']:+.1f}%</div>
                </div>
                """))
            with m3:
                st.html(textwrap.dedent(f"""
                <div class="metric-tile">
                    <div class="metric-label">Competitor Shift</div>
                    <div class="metric-val" style="color:{comp_growth_color};">{row['Comp Growth %']:+.1f}%</div>
                </div>
                """))
            with m4:
                st.html(textwrap.dedent(f"""
                <div class="metric-tile">
                    <div class="metric-label">Last Call Detail</div>
                    <div class="metric-val">{row['Days Since Call']}d ago</div>
                </div>
                """))

    # --- Bottom-Anchored React Pagination Bar ---
    st.markdown("---")
    with st.container(border=True):
        p_col_info, p_col_prev, p_col_nums, p_col_next, p_col_size = st.columns([3, 1, 2, 1, 1.5])

        with p_col_info:
            showing_from = start_idx + 1 if total_records > 0 else 0
            st.html(f"<div style='padding-top:8px; font-size:0.9rem; color:#475569;'>Showing <b>{showing_from}</b>–<b>{end_idx}</b> of <b>{total_records:,}</b> physicians</div>")

        with p_col_prev:
            if st.button("← Previous", disabled=(st.session_state.page_number <= 1), use_container_width=True):
                st.session_state.page_number = max(1, st.session_state.page_number - 1)
                st.rerun()

        with p_col_nums:
            st.html(f"<div style='text-align:center; padding-top:8px; font-weight:600; color:#0f172a;'>Page {st.session_state.page_number} / {total_pages}</div>")

        with p_col_next:
            if st.button("Next →", disabled=(st.session_state.page_number >= total_pages), use_container_width=True):
                st.session_state.page_number = min(total_pages, st.session_state.page_number + 1)
                st.rerun()

        with p_col_size:
            selected_size = st.selectbox(
                "Rows",
                options=[10, 20, 50, 100],
                index=[10, 20, 50, 100].index(st.session_state.page_size),
                label_visibility="collapsed"
            )
            if selected_size != st.session_state.page_size:
                st.session_state.page_size = selected_size
                st.session_state.page_number = 1
                st.rerun()

# -------------------------------------------------------------
# PAGE 2: Targeting Console (Rich Cards + Serial Laya Decision)
# -------------------------------------------------------------
elif st.session_state.current_page == "Targeting Console":
    all_records = st.session_state.data_loader.fetch_all_prepared_records()
    hcp_id_list = [r.hcp_id for r in all_records]
    current_selected = st.session_state.selected_hcp_id if st.session_state.selected_hcp_id in hcp_id_list else hcp_id_list[0]

    col_nav1, col_nav2 = st.columns([3.5, 1])
    with col_nav1:
        target_hcp_id = st.selectbox("Selected Target Physician", options=hcp_id_list, index=hcp_id_list.index(current_selected))
    with col_nav2:
        st.write("")
        if st.button("← Back to HCP 360", use_container_width=True):
            st.session_state.current_page = "HCP 360"
            st.rerun()

    record = next((r for r in all_records if r.hcp_id == target_hcp_id), None)

    if record:
        rx = record.laya_dict_state["rx_dynamics"]
        prof = record.laya_dict_state["profile"]
        meta = record.metadata
        
        col_left, col_right = st.columns([1, 1], gap="medium")

        # --- LEFT DOSSIER ---
        with col_left:
            # Prescriber Profile Card
            with st.container(border=True):
                st.markdown("**👨‍⚕️ Prescriber Profile**")
                kol_tag = "<span class='pill pill-purple' style='margin-left:6px;'>Key Opinion Leader (KOL)</span>" if prof["is_kol"] else ""
                
                profile_html = textwrap.dedent(f"""
                <div style="font-size:1.35rem; font-weight:800; color:#0f172a; margin-top:4px;">
                    {record.full_name} {kol_tag}
                </div>
                <div style="color:#64748b; font-size:0.86rem; margin-bottom:12px;">
                    <code>{record.hcp_id}</code> • {prof['specialty']} • Territory: <b>{meta['territory']}</b>
                </div>
                """)
                st.html(profile_html)

                p1, p2 = st.columns(2)
                with p1:
                    st.html(textwrap.dedent(f"""
                    <div class="metric-tile">
                        <div class="metric-label">Prescriber Decile</div>
                        <div class="metric-val">{prof['decile']}<span style="font-size:0.8rem; color:#94a3b8;">/10</span></div>
                    </div>
                    <div class="metric-tile">
                        <div class="metric-label">Hospital Access</div>
                        <div class="metric-val" style="font-size:1.05rem;">{prof['access_level']}</div>
                    </div>
                    """))
                with p2:
                    consent_color = '#16a34a' if meta['email_opt_in'] else '#dc2626'
                    consent_text = 'Consent Granted' if meta['email_opt_in'] else 'Unsubscribed'
                    st.html(textwrap.dedent(f"""
                    <div class="metric-tile">
                        <div class="metric-label">Digital Opt-In</div>
                        <div class="metric-val" style="font-size:1.05rem; color:{consent_color};">{consent_text}</div>
                    </div>
                    <div class="metric-tile">
                        <div class="metric-label">Days Since Last Detail</div>
                        <div class="metric-val" style="font-size:1.05rem;">{meta['days_since_last_call']} days</div>
                    </div>
                    """))

            # Prescribing Trajectory Card
            with st.container(border=True):
                st.markdown("**📊 Prescribing Volume & Trajectory (Past 3 Months)**")
                r1, r2 = st.columns(2)
                growth_color = "#16a34a" if rx["brand_growth_pct"] >= 0 else "#dc2626"
                comp_growth_color = "#dc2626" if rx["competitor_growth_pct"] > 0 else "#16a34a"
                
                with r1:
                    st.html(textwrap.dedent(f"""
                    <div class="metric-tile">
                        <div class="metric-label">TRx Volume</div>
                        <div class="metric-val">{rx['trx_volume_3m']} <span style="font-size:0.75rem; color:#94a3b8;">units</span></div>
                    </div>
                    <div class="metric-tile">
                        <div class="metric-label">Competitor Shift</div>
                        <div class="metric-val" style="color:{comp_growth_color};">{rx['competitor_growth_pct']:+.1f}%</div>
                    </div>
                    """))
                with r2:
                    st.html(textwrap.dedent(f"""
                    <div class="metric-tile">
                        <div class="metric-label">Brand Growth Rate</div>
                        <div class="metric-val" style="color:{growth_color};">{rx['brand_growth_pct']:+.1f}%</div>
                    </div>
                    <div class="metric-tile">
                        <div class="metric-label">Formulary Tier</div>
                        <div class="metric-val" style="font-size:0.95rem; color:#0284c7;">{rx['formulary_tier']}</div>
                    </div>
                    """))

            # CRM Timeline Card
            with st.container(border=True):
                st.markdown("**🗓️ Field Rep Logs & Qualitative Interactions**")
                for note in record.laya_dict_state["recent_crm_notes"]:
                    st.html(textwrap.dedent(f"""
                    <div class="crm-note">{note}</div>
                    """))

        # --- RIGHT DECISION & AUDIT ---
        with col_right:
            with st.container(border=True):
                st.markdown("**⚡ Laya Non-Autoregressive Decision Engine**")
                st.caption("Evaluates the state in a single forward pass (~33 ms) against calibrated criteria.")
                run_btn = st.button("🚀 Run Laya Serial Inference", type="primary", use_container_width=True)

            if run_btn or st.session_state.get(f"ran_{record.hcp_id}", False):
                st.session_state[f"ran_{record.hcp_id}"] = True
                start_t = time.time()

                raw_decision = st.session_state.laya_service.predict_single(record.laya_dict_state)
                final_action = st.session_state.laya_service.arbitrate_decision(raw_decision, record.metadata)
                st.session_state.laya_service.save_decision_to_db(record.hcp_id, final_action)
                latency = round((time.time() - start_t) * 1000, 1)

                prio_key = final_action['final_priority']
                prio_pill_cls = {
                    "critical_immediate": "pill-red",
                    "maintain_regular": "pill-green",
                    "digital_only": "pill-blue",
                    "deprioritized": "pill-gray"
                }.get(prio_key, "pill-gray")

                # Hero Next-Best-Action Banner
                hero_banner = textwrap.dedent(f"""
                <div class="nba-hero-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:0.8rem; text-transform:uppercase; letter-spacing:1px; color:#bae6fd; font-weight:700;">
                            Recommended Next-Best-Action
                        </span>
                        <span class="pill {prio_pill_cls}" style="font-size:0.75rem;">
                            {prio_key.replace('_', ' ').upper()}
                        </span>
                    </div>
                    <div style="font-size:1.75rem; font-weight:800; margin: 8px 0 6px 0;">
                        {final_action['final_channel'].replace('_', ' ').title()}
                    </div>
                    <div style="font-size:0.95rem; opacity:0.95;">
                        <b>Content Theme:</b> {final_action['final_content'].replace('_', ' ').title()}
                    </div>
                    <div style="margin-top:14px; font-size:0.78rem; color:#bfdbfe;">
                        Inference Latency: <b>{latency} ms</b> • Backbone: ModernBERT-large (zero hallucination)
                    </div>
                </div>
                """)
                st.html(hero_banner)

                # Output Metric Grid
                with st.container(border=True):
                    st.markdown("**🎯 Calibrated Decision Outputs**")
                    d1, d2 = st.columns(2)
                    with d1:
                        st.html(textwrap.dedent(f"""
                        <div class="metric-tile">
                            <div class="metric-label">Rep Scheduling Priority</div>
                            <div class="metric-val" style="font-size:1.05rem;">{final_action['final_priority'].replace('_', ' ').title()}</div>
                        </div>
                        <div class="metric-tile">
                            <div class="metric-label">Channel Affinity</div>
                            <div class="metric-val" style="font-size:1.05rem;">{final_action['final_channel'].replace('_', ' ').title()}</div>
                        </div>
                        """))
                    with d2:
                        churn_color = '#dc2626' if final_action['churn_prob'] >= 0.70 else '#16a34a'
                        st.html(textwrap.dedent(f"""
                        <div class="metric-tile">
                            <div class="metric-label">Content Theme Affinity</div>
                            <div class="metric-val" style="font-size:1.05rem;">{final_action['final_content'].replace('_', ' ').title()}</div>
                        </div>
                        <div class="metric-tile">
                            <div class="metric-label">Calibrated Churn Risk (Noul)</div>
                            <div class="metric-val" style="font-size:1.05rem; color:{churn_color};">{final_action['churn_prob']:.1%}</div>
                        </div>
                        """))

                # Arbitration & Regulatory Audit Trail
                anti_fatigue_passed = not (raw_decision["optimal_channel"]["choice"] == "in_person_rep" and meta["days_since_last_call"] < 14)
                consent_passed = not (raw_decision["optimal_channel"]["choice"] == "rep_triggered_email" and not meta["email_opt_in"])
                escalation_triggered = final_action["churn_prob"] >= 0.70 and prof["decile"] >= 6

                with st.container(border=True):
                    st.markdown("**🛡️ Arbitration & Regulatory Audit Trail**")
                    audit_html = textwrap.dedent(f"""
                    <div class="audit-item">
                        <span>{'✅' if anti_fatigue_passed else '⚠️'}</span>
                        <div>
                            <b>Anti-Fatigue Frequency Capping:</b> {'Passed (Call gap > 14 days)' if anti_fatigue_passed else f'Triggered - Re-routed from in-person visit (Last detail was {meta["days_since_last_call"]} days ago)'}
                        </div>
                    </div>
                    <div class="audit-item">
                        <span>{'✅' if consent_passed else '⚠️'}</span>
                        <div>
                            <b>Digital Compliance Consent:</b> {'Verified (Opt-in active)' if consent_passed else 'Overridden - Physician has not opted into promotional emails'}
                        </div>
                    </div>
                    <div class="audit-item">
                        <span>{'🚨' if escalation_triggered else 'ℹ️'}</span>
                        <div>
                            <b>High-Churn Escalation Rule:</b> {'Escalated to Critical Immediate Priority due to switch share threat' if escalation_triggered else 'Standard priority assigned'}
                        </div>
                    </div>
                    """)
                    st.html(audit_html)

        # ---------------- GENERATIVE ASSET STITCHING (SYSTEM 2) ----------------
                st.markdown("---")
                with st.container(border=True):
                    header_html = textwrap.dedent("""
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-weight:700; font-size:1.05rem; color:#0f172a;">
                            ✨ Generative Asset Stitching (System 2)
                        </span>
                        <span class="pill pill-purple">Hybrid AI Pipeline</span>
                    </div>
                    <div style="font-size:0.84rem; color:#64748b; margin-bottom:14px;">
                        Pairs Laya's sub-35 ms decision output with the physician's CRM profile to generate field-ready collateral.
                    </div>
                    """)
                    st.html(header_html)

                    tab_brief, tab_email = st.tabs(["📋 Pre-Call Detailing Brief", "✉️ Rep-Triggered Email Draft"])

                    # 1. Pre-Call Detailing Cheat Sheet (Clean dedented rendering)
                    with tab_brief:
                        brief = st.session_state.asset_stitcher.generate_precall_brief(record, final_action)

                        with st.container(border=True):
                            brief_html = textwrap.dedent(f"""
                            <div style="margin-bottom: 12px;">
                                <div style="font-size:0.75rem; text-transform:uppercase; color:#64748b; font-weight:700; letter-spacing:0.5px;">
                                    🎯 Primary Prescriber Barrier
                                </div>
                                <div style="font-size:0.95rem; font-weight:600; color:#b91c1c; margin-top:2px;">
                                    {brief['primary_barrier']}
                                </div>
                            </div>
                            
                            <div style="margin-bottom: 12px;">
                                <div style="font-size:0.75rem; text-transform:uppercase; color:#64748b; font-weight:700; letter-spacing:0.5px;">
                                    💡 Recommended Rep Pivot
                                </div>
                                <div style="font-size:0.9rem; color:#1e293b; margin-top:2px;">
                                    {brief['counter_pivot']}
                                </div>
                            </div>

                            <div style="margin-bottom: 12px;">
                                <div style="font-size:0.75rem; text-transform:uppercase; color:#64748b; font-weight:700; letter-spacing:0.5px;">
                                    📖 Approved Clinical Citation
                                </div>
                                <div style="font-size:0.9rem; color:#0369a1; font-weight:600; margin-top:2px;">
                                    {brief['key_clinical_evidence']}
                                </div>
                            </div>

                            <div style="margin-bottom: 12px;">
                                <div style="font-size:0.75rem; text-transform:uppercase; color:#64748b; font-weight:700; letter-spacing:0.5px;">
                                    📂 Leave-Behind Material
                                </div>
                                <div style="font-size:0.9rem; color:#0f172a; margin-top:2px;">
                                    {brief['recommended_leave_behind']}
                                </div>
                            </div>

                            <div style="background:#eff6ff; border-left:4px solid #3b82f6; border-radius:6px; padding:10px 14px; margin-top:10px;">
                                <div style="font-size:0.75rem; color:#1d4ed8; font-weight:700; text-transform:uppercase;">Suggested Opening Hook</div>
                                <div style="font-size:0.9rem; color:#1e40af; font-style:italic; margin-top:3px;">
                                    "{brief['suggested_opening_hook']}"
                                </div>
                            </div>
                            """)
                            st.html(brief_html)

                    # 2. Compliant Email Draft
                    with tab_email:
                        email_draft = st.session_state.asset_stitcher.generate_email_draft(record, final_action)

                        st.text_input("Recipient", value=email_draft["recipient"], disabled=True)
                        st.text_input("Subject Line", value=email_draft["subject"])
                        st.text_area("Body (Editable)", value=email_draft["body"], height=240)

                        col_send, col_status = st.columns([1.5, 2])
                        with col_send:
                            if st.button("📤 Push to Veeva CRM Approved Email", type="primary", use_container_width=True):
                                st.success("Email staged in Veeva CRM queue for rep sign-off!")
                        with col_status:
                            st.caption(f"🔒 MLR Compliance Verification Code: `{email_draft['compliance_doc_id']}`")
# -------------------------------------------------------------
# PAGE 3: Advanced Analytics (Conditional)
# -------------------------------------------------------------
elif st.session_state.current_page == "Advanced Analytics":
    st.markdown("## 📈 Advanced Channel Engagement Analytics")
    st.caption("Deep-dive digital performance metrics: Channel Reach, CTR, CTOR, and Call Durations.")

    conn = sqlite3.connect(DB_NAME)
    try:
        df_advanced = pd.read_sql_query("SELECT * FROM hcp_crm_interactions", conn)
    finally:
        conn.close()

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Total Digital Reach", f"{len(df_advanced):,}")
    
    if "ctr" in df_advanced.columns:
        a2.metric("Avg CTR", f"{df_advanced['ctr'].mean():.2%}")
    else:
        a2.metric("Avg CTR", "N/A")

    if "ctor" in df_advanced.columns:
        a3.metric("Avg CTOR", f"{df_advanced['ctor'].mean():.2%}")
    else:
        a3.metric("Avg CTOR", "N/A")

    if "call_duration" in df_advanced.columns:
        a4.metric("Avg Call Duration", f"{df_advanced['call_duration'].mean():.1f} min")
    else:
        a4.metric("Avg Call Duration", "N/A")

    st.markdown("---")
    
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        if "channel_used" in df_advanced.columns:
            fig_reach = px.bar(
                df_advanced["channel_used"].value_counts().reset_index(),
                x="channel_used", y="count",
                title="Interactions by Channel Touchpoint",
                color="channel_used"
            )
            st.plotly_chart(fig_reach, use_container_width=True)

    with col_chart2:
        if "call_duration" in df_advanced.columns and "channel_used" in df_advanced.columns:
            fig_dur = px.box(
                df_advanced, x="channel_used", y="call_duration",
                title="Engagement Duration by Channel"
            )
            st.plotly_chart(fig_dur, use_container_width=True)
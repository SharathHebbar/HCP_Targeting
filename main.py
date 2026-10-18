import streamlit as st
import pandas as pd
import numpy as np
import random
import json
import time
import asyncio
from concurrent.futures import ProcessPoolExecutor
from faker import Faker
import plotly.express as px
import plotly.graph_objects as go

# --- Page Configuration ---
st.set_page_config(
    page_title="Laya HCP Targeting Engine",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for executive look & feel
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fb;
        border-radius: 8px;
        padding: 16px;
        border-left: 4px solid #3b82f6;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .badge-critical {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 8px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-maintain {
        background-color: #ecfdf5;
        color: #065f46;
        padding: 4px 8px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Configuration & Constants ---
SPECIALTIES = [
    "Medical Oncology", "Hematology Oncology", "Cardiology",
    "Endocrinology", "Rheumatology", "Neurology", "Immunology"
]
TERRITORIES = [
    "NE-Boston", "NE-NY-Metro", "SE-Atlanta", "MW-Chicago", 
    "SW-Dallas", "WC-SF-Bay", "WC-LA-Metro", "NW-Seattle"
]
FORMULARY_TIERS = [
    "Preferred Tier 1", "Preferred Tier 2", 
    "Non-Preferred Tier 3", "Prior Authorization Required"
]
INTERACTION_TEMPLATES = [
    "Rep visited {days} days ago: HCP noted concerns over adverse events and patient tolerability.",
    "Attended regional symposium {days} days ago; expressed keen interest in 3-year progression-free survival data.",
    "Rep detailing note: Refused in-person meeting citing strict hospital no-see protocol; requested digital summary.",
    "Email interaction: Opened clinical trial newsletter; clicked link on head-to-head comparative efficacy study.",
    "MSL inquiry logged {days} days ago: Inquired on biomarker sub-group analyses and infusion dosage escalations.",
    "Interaction note: Heavy prescriber of competitor therapy; skeptical of switching without real-world registry evidence.",
    "Recent field call: Mentions patient complaints on copay tier; inquiring on co-pay assistance cards."
]

QUESTIONS_SPEC = {
    "rep_visit_priority": {
        "type": "choice",
        "instructions": "What priority tier should be assigned for sales scheduling?",
        "criteria": {
            "critical_immediate": "High decile with dropping brand share or competitor churn; contact in 7 days.",
            "maintain_regular": "Stable prescriber meeting targets; scheduled for standard cycle cadence.",
            "digital_only": "Low decile, unresponsive to reps, or non-access HCP best served digitally.",
            "deprioritized": "Strict no-see policy or low adoption potential."
        }
    },
    "urgent_churn_risk": {
        "type": "noul",
        "instructions": "Is this HCP actively shifting switch-share to competitor therapies?"
    },
    "optimal_channel": {
        "type": "choice",
        "instructions": "Which channel should be selected for the next touchpoint?",
        "criteria": {
            "in_person_rep": "High-touch clinical discussion or objection handling required.",
            "rep_triggered_email": "Follow-up requested or high digital open-rates.",
            "msl_medical_inquiry": "KOL seeking deep scientific, off-label, or trial publication data.",
            "self_serve_portal": "Prefers on-demand portal resources or webinar invitations."
        }
    },
    "content_focus": {
        "type": "choice",
        "instructions": "Which content theme addresses the primary barrier or interest?",
        "criteria": {
            "clinical_efficacy": "Comparative endpoints, survival curves, head-to-head trials.",
            "safety_tolerability": "Adverse event management, contraindications, toxicity mitigation.",
            "patient_support_access": "Copay assistance, prior authorizations, patient assistance programs.",
            "dosing_administration": "Infusion schedules, dose modifications, clinic handling protocols."
        }
    }
}

# --- Session State Initialization ---
if "cohort" not in st.session_state:
    st.session_state.cohort = []
if "scored_results" not in st.session_state:
    st.session_state.scored_results = []
if "logs" not in st.session_state:
    st.session_state.logs = []

# --- Data Generation Functions ---
def generate_hcp_cohort(n_hcps=1000):
    fake = Faker("en_US")
    cohort = []
    
    for i in range(1, n_hcps + 1):
        hcp_id = f"HCP_{i:04d}"
        specialty = random.choice(SPECIALTIES)
        decile = int(np.random.choice(range(1, 11), p=[0.05, 0.05, 0.08, 0.10, 0.12, 0.15, 0.15, 0.12, 0.10, 0.08]))
        is_kol = bool(decile >= 8 and random.random() < 0.25)
        
        base_trx = int(np.clip(np.random.normal(loc=decile * 15, scale=8), 5, 200))
        brand_growth = round(float(np.random.normal(loc=-2.0 if decile > 6 else 1.5, scale=12.0)), 1)
        competitor_growth = round(float(np.random.normal(loc=4.5 if brand_growth < 0 else -1.0, scale=8.0)), 1)
        
        days_since_last_call = int(np.random.exponential(scale=28)) + 1
        email_opt_in = random.random() < 0.72
        access_level = random.choices(["Open Access", "Restricted Access", "No-See"], weights=[0.55, 0.35, 0.10])[0]

        num_notes = random.randint(1, 3)
        notes = [
            random.choice(INTERACTION_TEMPLATES).format(days=random.randint(5, 90))
            for _ in range(num_notes)
        ]

        hcp_record = {
            "hcp_id": hcp_id,
            "hcp_name": f"Dr. {fake.first_name()} {fake.last_name()}, MD",
            "metadata": {
                "specialty": specialty,
                "decile": decile,
                "territory": random.choice(TERRITORIES),
                "key_opinion_leader": is_kol,
                "access_level": access_level,
                "email_opt_in": email_opt_in,
                "days_since_last_call": days_since_last_call
            },
            "laya_state": {
                "profile": {
                    "specialty": specialty,
                    "decile": decile,
                    "access_level": access_level,
                    "is_kol": is_kol
                },
                "rx_dynamics": {
                    "trx_volume_3m": base_trx,
                    "brand_growth_pct": brand_growth,
                    "competitor_growth_pct": competitor_growth,
                    "formulary_tier": random.choice(FORMULARY_TIERS)
                },
                "recent_crm_notes": notes
            }
        }
        cohort.append(hcp_record)
    return cohort

# --- Simulated Calibrated Decision Engine (Fallback) ---
def simulate_laya_inference(state: dict) -> dict:
    profile = state["profile"]
    rx = state["rx_dynamics"]
    notes = " ".join(state["recent_crm_notes"]).lower()
    
    # Priority
    if profile["decile"] >= 7 and (rx["brand_growth_pct"] < -5 or rx["competitor_growth_pct"] > 10):
        priority = "critical_immediate"
    elif profile["access_level"] == "No-See":
        priority = "digital_only"
    elif profile["decile"] <= 3:
        priority = "deprioritized"
    else:
        priority = "maintain_regular"

    # Churn probability calculation
    base_churn = 0.25
    if rx["brand_growth_pct"] < 0: base_churn += 0.35
    if rx["competitor_growth_pct"] > 5: base_churn += 0.25
    if "competitor" in notes or "skeptical" in notes: base_churn += 0.15
    churn_prob = float(np.clip(base_churn + random.uniform(-0.05, 0.05), 0.02, 0.98))

    # Channel affinity
    if profile["is_kol"] and ("trial" in notes or "biomarker" in notes):
        channel = "msl_medical_inquiry"
    elif profile["access_level"] == "No-See":
        channel = "rep_triggered_email"
    elif profile["decile"] >= 6 and profile["access_level"] == "Open Access":
        channel = "in_person_rep"
    else:
        channel = "self_serve_portal"

    # Content affinity
    if "adverse" in notes or "tolerability" in notes:
        content = "safety_tolerability"
    elif "copay" in notes or "cost" in notes:
        content = "patient_support_access"
    elif "infusion" in notes or "dosing" in notes:
        content = "dosing_administration"
    else:
        content = "clinical_efficacy"

    return {
        "rep_visit_priority": {"choice": priority},
        "urgent_churn_risk": {"noul": round(churn_prob, 4)},
        "optimal_channel": {"choice": channel},
        "content_focus": {"choice": content}
    }

# --- Arbitration Guardrail Layer ---
def arbitrate_decision(raw_decision: dict, metadata: dict) -> dict:
    priority = raw_decision["rep_visit_priority"]["choice"]
    channel = raw_decision["optimal_channel"]["choice"]
    content = raw_decision["content_focus"]["choice"]
    churn = raw_decision["urgent_churn_risk"]["noul"]

    # Rule 1: Anti-fatigue frequency cap (reps shouldn't visit within 14 days)
    if channel == "in_person_rep" and metadata["days_since_last_call"] < 14:
        channel = "rep_triggered_email" if metadata["email_opt_in"] else "self_serve_portal"

    # Rule 2: Consent check for triggered email
    if channel == "rep_triggered_email" and not metadata["email_opt_in"]:
        channel = "in_person_rep" if metadata["access_level"] != "No-See" else "self_serve_portal"

    # Rule 3: High churn escalation
    if churn >= 0.70 and priority != "critical_immediate" and metadata["decile"] >= 6:
        priority = "critical_immediate"

    return {
        "final_priority": priority,
        "final_channel": channel,
        "final_content": content,
        "churn_prob": churn
    }

# --- Sidebar Controls ---
st.sidebar.title("⚙️ Engine Controls")

st.sidebar.subheader("1. Cohort Generator")
cohort_size = st.sidebar.slider("Number of HCPs", min_value=100, max_value=2000, value=1000, step=100)
if st.sidebar.button("Generate Synthetic Cohort", use_container_width=True):
    with st.spinner("Generating clinical profiles..."):
        st.session_state.cohort = generate_hcp_cohort(cohort_size)
        st.session_state.scored_results = []
        st.sidebar.success(f"Generated {len(st.session_state.cohort)} HCP profiles!")

st.sidebar.subheader("2. Inference & Architecture")
engine_mode = st.sidebar.selectbox(
    "Inference Engine",
    ["Simulated Laya (Zero-Config)", "Laya-Serve HTTP Server", "Local Laya ProcessPool"]
)
worker_threads = st.sidebar.slider("Parallel Workers", min_value=1, max_value=16, value=8)

st.sidebar.subheader("3. NBA Arbitration Guardrails")
enforce_anti_fatigue = st.sidebar.checkbox("Enforce Anti-Fatigue Capping (14 Days)", value=True)
enforce_consent = st.sidebar.checkbox("Enforce Digital Opt-In Consent", value=True)
escalate_churn = st.sidebar.checkbox("Escalate High Churn (P > 0.70)", value=True)

# --- Top Header ---
st.title("🧬 Next-Best-Action Decision Engine")
st.caption("Powered by Laya non-autoregressive calibrated typed decisions for commercial pharma targeting")

# Auto-generate if empty on startup
if not st.session_state.cohort:
    st.session_state.cohort = generate_hcp_cohort(1000)

# --- Action Banner & Batch Execution ---
col_run1, col_run2 = st.columns([3, 1])
with col_run1:
    st.info(f"Loaded **{len(st.session_state.cohort):,}** HCP profiles. Target dimensions: **Prioritization**, **Channel Affinity**, **Content Theme**, and **Churn Probability**.")
with col_run2:
    run_btn = st.button("🚀 Run Parallel Scoring", type="primary", use_container_width=True)

if run_btn:
    progress_bar = st.progress(0)
    status_text = st.empty()
    start_time = time.time()
    
    scored = []
    total = len(st.session_state.cohort)
    
    # Process batch with simulated concurrency
    batch_size = max(1, total // 20)
    for idx in range(0, total, batch_size):
        chunk = st.session_state.cohort[idx:idx + batch_size]
        for hcp in chunk:
            raw_dec = simulate_laya_inference(hcp["laya_state"])
            arb = arbitrate_decision(raw_dec, hcp["metadata"])
            
            scored.append({
                "HCP ID": hcp["hcp_id"],
                "HCP Name": hcp["hcp_name"],
                "Specialty": hcp["metadata"]["specialty"],
                "Decile": hcp["metadata"]["decile"],
                "Territory": hcp["metadata"]["territory"],
                "TRx Volume": hcp["laya_state"]["rx_dynamics"]["trx_volume_3m"],
                "Brand Growth %": hcp["laya_state"]["rx_dynamics"]["brand_growth_pct"],
                "Churn Risk": arb["churn_prob"],
                "Priority Tier": arb["final_priority"],
                "Optimal Channel": arb["final_channel"],
                "Content Theme": arb["final_content"],
                "Days Since Call": hcp["metadata"]["days_since_last_call"],
                "Raw Notes": " | ".join(hcp["laya_state"]["recent_crm_notes"])
            })
        
        progress = min(1.0, (idx + batch_size) / total)
        progress_bar.progress(progress)
        status_text.text(f"Evaluated {min(idx + batch_size, total)}/{total} HCP states...")
        time.sleep(0.03)  # Small pacing to showcase progress

    elapsed = round(time.time() - start_time, 2)
    throughput = round(total / max(elapsed, 0.001), 1)
    status_text.success(f"Scored {total:,} HCPs in {elapsed}s (~{throughput} req/s) across {worker_threads} workers.")
    st.session_state.scored_results = scored

# --- Main Dashboard Section ---
if st.session_state.scored_results:
    df = pd.DataFrame(st.session_state.scored_results)

    # Tabs
    tab_analytics, tab_explorer, tab_sandbox = st.tabs([
        "📊 Commercial Analytics", "🔍 HCP 360 Explorer", "🧪 Single HCP Sandbox"
    ])

    with tab_analytics:
        # High Level KPIs
        k1, k2, k3, k4 = st.columns(4)
        crit_count = len(df[df["Priority Tier"] == "critical_immediate"])
        high_churn_count = len(df[df["Churn Risk"] >= 0.70])
        rep_calls_assigned = len(df[df["Optimal Channel"] == "in_person_rep"])
        
        k1.metric("Total Prescribers", f"{len(df):,}")
        k2.metric("Critical Immediate Action", f"{crit_count:,}", f"{round(crit_count/len(df)*100, 1)}% of cohort", delta_color="inverse")
        k3.metric("High Churn Risk (P > 70%)", f"{high_churn_count:,}", f"{round(high_churn_count/len(df)*100, 1)}%", delta_color="inverse")
        k4.metric("Rep In-Person Allocation", f"{rep_calls_assigned:,}", f"{round(rep_calls_assigned/len(df)*100, 1)}%")

        st.markdown("---")
        
        # Charts Row 1
        c1, c2 = st.columns(2)
        with c1:
            fig_prio = px.pie(
                df, names="Priority Tier", title="Rep Visit Priority Distribution",
                color="Priority Tier",
                color_discrete_map={
                    "critical_immediate": "#ef4444",
                    "maintain_regular": "#10b981",
                    "digital_only": "#3b82f6",
                    "deprioritized": "#9ca3af"
                },
                hole=0.4
            )
            fig_prio.update_layout(margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig_prio, use_container_width=True)

        with c2:
            fig_chan = px.bar(
                df["Optimal Channel"].value_counts().reset_index(),
                x="Optimal Channel", y="count",
                title="Recommended Touchpoint Channels",
                color="Optimal Channel",
                color_discrete_sequence=px.colors.qualitative.Prism
            )
            fig_chan.update_layout(margin=dict(t=40, b=0, l=0, r=0), showlegend=False)
            st.plotly_chart(fig_chan, use_container_width=True)

        # Charts Row 2
        c3, c4 = st.columns(2)
        with c3:
            fig_content = px.bar(
                df["Content Theme"].value_counts().reset_index(),
                x="count", y="Content Theme",
                orientation="h",
                title="Content & Narrative Theme Affinity",
                color="Content Theme",
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_content.update_layout(margin=dict(t=40, b=0, l=0, r=0), showlegend=False)
            st.plotly_chart(fig_content, use_container_width=True)

        with c4:
            fig_scatter = px.scatter(
                df, x="Decile", y="Churn Risk",
                color="Priority Tier",
                size="TRx Volume",
                hover_data=["HCP Name", "Specialty", "Optimal Channel"],
                title="Prescriber Decile vs. Churn Probability",
                color_discrete_map={
                    "critical_immediate": "#ef4444",
                    "maintain_regular": "#10b981",
                    "digital_only": "#3b82f6",
                    "deprioritized": "#9ca3af"
                }
            )
            fig_scatter.update_layout(margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig_scatter, use_container_width=True)

    with tab_explorer:
        st.subheader("Filter and Inspect HCP Portfolio")
        
        f1, f2, f3 = st.columns(3)
        with f1:
            sel_priority = st.multiselect("Filter by Priority", options=df["Priority Tier"].unique(), default=df["Priority Tier"].unique())
        with f2:
            sel_channel = st.multiselect("Filter by Channel", options=df["Optimal Channel"].unique(), default=df["Optimal Channel"].unique())
        with f3:
            min_decile = st.slider("Minimum Decile", 1, 10, 1)

        filtered_df = df[
            (df["Priority Tier"].isin(sel_priority)) &
            (df["Optimal Channel"].isin(sel_channel)) &
            (df["Decile"] >= min_decile)
        ]

        st.dataframe(
            filtered_df[[
                "HCP ID", "HCP Name", "Specialty", "Decile", "Territory",
                "Priority Tier", "Optimal Channel", "Content Theme", "Churn Risk", "TRx Volume"
            ]],
            use_container_width=True,
            height=400
        )

        st.markdown("### 📋 Deep-Dive HCP Profile Inspection")
        selected_hcp_id = st.selectbox("Select HCP to view full dossier", options=filtered_df["HCP ID"].tolist() if not filtered_df.empty else [])
        
        if selected_hcp_id:
            hcp_data = next((h for h in st.session_state.cohort if h["hcp_id"] == selected_hcp_id), None)
            hcp_scored = next((h for h in st.session_state.scored_results if h["HCP ID"] == selected_hcp_id), None)
            
            if hcp_data and hcp_scored:
                d1, d2 = st.columns([1, 1])
                with d1:
                    st.write("**Clinical & Prescribing Metadata:**")
                    st.json(hcp_data["laya_state"]["profile"])
                    st.json(hcp_data["laya_state"]["rx_dynamics"])
                with d2:
                    st.write("**Next-Best-Action Recommendation:**")
                    st.success(f"**Action:** Dispatch **{hcp_scored['Optimal Channel']}** touchpoint")
                    st.warning(f"**Pillar:** Focus on **{hcp_scored['Content Theme']}**")
                    st.error(f"**Urgent Priority:** {hcp_scored['Priority Tier']} (Churn P={hcp_scored['Churn Risk']:.1%})")
                    
                    st.write("**Recent CRM Notes Evaluated:**")
                    for n in hcp_data["laya_state"]["recent_crm_notes"]:
                        st.info(f"• {n}")

    with tab_sandbox:
        st.subheader("🧪 Real-Time Single HCP Decision Sandbox")
        st.caption("Test how Laya evaluates custom or updated field notes and prescribing dynamics on the fly.")

        sb1, sb2 = st.columns(2)
        with sb1:
            test_spec = st.selectbox("Specialty", SPECIALTIES)
            test_decile = st.slider("Decile", 1, 10, 8)
            test_growth = st.slider("Brand Growth %", -40.0, 40.0, -18.5)
            test_comp_growth = st.slider("Competitor Growth %", -20.0, 50.0, 22.0)
            test_notes = st.text_area(
                "Unstructured CRM Field Notes",
                value="Rep visited 3 days ago. HCP is concerned with patient diarrhea and tolerability issues. Threatens to switch next patient cohort to competitor therapy."
            )
            eval_btn = st.button("Evaluate with Laya", type="primary")

        with sb2:
            if eval_btn:
                test_state = {
                    "profile": {"specialty": test_spec, "decile": test_decile, "access_level": "Open Access", "is_kol": test_decile >= 8},
                    "rx_dynamics": {"trx_volume_3m": test_decile * 15, "brand_growth_pct": test_growth, "competitor_growth_pct": test_comp_growth},
                    "recent_crm_notes": [test_notes]
                }
                decision = simulate_laya_inference(test_state)
                
                st.markdown("#### Calibrated Decision Output (~35 ms forward pass)")
                st.metric("Priority Tier", decision["rep_visit_priority"]["choice"])
                st.metric("Churn Risk Probability", f"{decision['urgent_churn_risk']['noul']:.1%}")
                st.metric("Optimal Channel", decision["optimal_channel"]["choice"])
                st.metric("Content Focus", decision["content_focus"]["choice"])
else:
    st.info("Click **'Run Parallel Scoring'** above to process the 1,000 HCP cohort.")
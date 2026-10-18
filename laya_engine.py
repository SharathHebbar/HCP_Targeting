"""
laya_engine.py
Handles Laya System 1 non-autoregressive decision inference and arbitration.
"""

import json
import sqlite3
from typing import Dict, Any, Optional

# Attempt to import laya SDK; fall back gracefully to calibrated heuristic simulation
try:
    import laya
    LAYA_AVAILABLE = True
except ImportError:
    LAYA_AVAILABLE = False

DB_NAME = "hcp_targeting.db"

# Official Laya decision questions spec for commercial targeting
QUESTIONS_SPEC = {
    "rep_visit_priority": {
        "type": "choice",
        "instructions": "What priority tier should be assigned for field sales representative scheduling?",
        "criteria": {
            "critical_immediate": "High decile with dropping brand share or competitive threat; contact within 7 days.",
            "maintain_regular": "Stable prescriber meeting targets; scheduled for standard cycle cadences.",
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
            "in_person_rep": "High-touch clinical discussion, objection handling, or detailing required.",
            "rep_triggered_email": "Follow-up requested or high digital open-rates paired with rep relationship.",
            "msl_medical_inquiry": "KOL seeking deep scientific, off-label, or trial publication data.",
            "self_serve_portal": "Prefers on-demand portal resources or webinar invitations."
        }
    },
    "content_focus": {
        "type": "choice",
        "instructions": "Which content theme addresses the HCP's primary barrier or interest?",
        "criteria": {
            "clinical_efficacy": "Comparative endpoints, progression-free survival, head-to-head trials.",
            "safety_tolerability": "Adverse event management, drug interactions, contraindications.",
            "patient_support_access": "Copay assistance, prior authorization guidelines, adherence programs.",
            "dosing_administration": "Infusion schedules, dose escalation, monitoring protocols."
        }
    }
}

class LayaInferenceService:
    def __init__(self, model_name: str = "convaiinnovations/laya"):
        self.model_name = model_name
        self.agent = None
        
        if LAYA_AVAILABLE:
            try:
                self.agent = laya.load(model_name)
            except Exception as e:
                print(f"[Warning] Could not load live Laya model: {e}. Defaulting to calibrated engine fallback.")
                self.agent = None

    def predict_single(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes serial inference for one HCP state.
        Uses live Laya if available; otherwise uses deterministic calibrated fallback.
        """
        if self.agent is not None:
            result = self.agent.predict(state, QUESTIONS_SPEC)
            return result["answers"]
        
        # Calibrated fallback logic matching Laya's non-autoregressive criteria
        profile = state.get("profile", {})
        rx = state.get("rx_dynamics", {})
        notes = " ".join(state.get("recent_crm_notes", [])).lower()

        # 1. Priority Decision
        if profile.get("decile", 1) >= 7 and (rx.get("brand_growth_pct", 0) < -5 or rx.get("competitor_growth_pct", 0) > 8):
            priority = "critical_immediate"
        elif profile.get("access_level") == "No-See":
            priority = "digital_only"
        elif profile.get("decile", 1) <= 3:
            priority = "deprioritized"
        else:
            priority = "maintain_regular"

        # 2. Calibrated Churn Probability
        base_churn = 0.20
        if rx.get("brand_growth_pct", 0) < 0:
            base_churn += 0.35
        if rx.get("competitor_growth_pct", 0) > 5:
            base_churn += 0.25
        if "competitor" in notes or "skeptical" in notes:
            base_churn += 0.15
        churn_prob = max(0.02, min(0.96, base_churn))

        # 3. Channel Affinity
        if profile.get("is_kol") and ("trial" in notes or "biomarker" in notes):
            channel = "msl_medical_inquiry"
        elif profile.get("access_level") == "No-See":
            channel = "rep_triggered_email"
        elif profile.get("decile", 1) >= 6 and profile.get("access_level") == "Open Access":
            channel = "in_person_rep"
        else:
            channel = "self_serve_portal"

        # 4. Content Focus
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

    def arbitrate_decision(self, raw_answers: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies commercial business guardrails over raw Laya decisions.
        """
        priority = raw_answers["rep_visit_priority"]["choice"]
        channel = raw_answers["optimal_channel"]["choice"]
        content = raw_answers["content_focus"]["choice"]
        churn = raw_answers["urgent_churn_risk"]["noul"]

        # Guardrail 1: 14-day anti-fatigue frequency capping
        days_since_call = metadata.get("days_since_last_call", 999)
        if channel == "in_person_rep" and days_since_call < 14:
            channel = "rep_triggered_email" if metadata.get("email_opt_in") else "self_serve_portal"

        # Guardrail 2: Digital consent compliance
        if channel == "rep_triggered_email" and not metadata.get("email_opt_in"):
            channel = "in_person_rep" if metadata.get("access_level") != "No-See" else "self_serve_portal"

        # Guardrail 3: High churn priority escalation
        if churn >= 0.70 and priority != "critical_immediate":
            priority = "critical_immediate"

        return {
            "final_priority": priority,
            "final_channel": channel,
            "final_content": content,
            "churn_prob": churn,
            "raw_priority": raw_answers["rep_visit_priority"]["choice"],
            "raw_channel": raw_answers["optimal_channel"]["choice"]
        }

    def save_decision_to_db(self, hcp_id: str, decision: Dict[str, Any], db_path: str = DB_NAME):
        """Saves or updates the decision in the database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS hcp_decisions (
            hcp_id TEXT PRIMARY KEY,
            priority_tier TEXT NOT NULL,
            optimal_channel TEXT NOT NULL,
            content_theme TEXT NOT NULL,
            churn_risk REAL NOT NULL,
            scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hcp_id) REFERENCES hcps(hcp_id)
        );
        """)

        cursor.execute("""
        INSERT OR REPLACE INTO hcp_decisions 
        (hcp_id, priority_tier, optimal_channel, content_theme, churn_risk, scored_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'));
        """, (
            hcp_id,
            decision["final_priority"],
            decision["final_channel"],
            decision["final_content"],
            decision["churn_prob"]
        ))
        
        conn.commit()
        conn.close()
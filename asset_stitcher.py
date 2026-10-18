"""
asset_stitcher.py - LLM-Based Generative Asset Stitcher via Groq API
Combines Laya's System 1 calibrated decisions with Groq's low-latency inference
to synthesize personalized Pre-Call Detailing Briefs and Compliant Email Drafts.
"""

import os
import json
from typing import Dict, Any, Optional

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# MLR-Approved Clinical Proof Points & Leave-Behind Material Library
APPROVED_CLINICAL_ASSETS = {
    "safety_tolerability": {
        "trial_citation": "ELEVATE-301 Phase III Safety Subgroup Analysis",
        "clinical_data_point": "34% reduction in Grade >=3 GI adverse events with standard step-up hydration protocol.",
        "leave_behind": "Patient Tolerability & Titration Pocket Guide (Ref: MLR-SAF-2026-v2)",
        "compliance_ref": "MLR-SAF-2026-v2"
    },
    "clinical_efficacy": {
        "trial_citation": "ASCEND-Core Phase III Trial (36-Month PFS & OS)",
        "clinical_data_point": "4.2-month median PFS improvement over standard-of-care comparator (HR 0.68, p=0.002).",
        "leave_behind": "36-Month Kaplan-Meier Progression-Free Survival Reprint (Ref: MLR-EFF-2026-v4)",
        "compliance_ref": "MLR-EFF-2026-v4"
    },
    "patient_support_access": {
        "trial_citation": "Real-World Evidence Registry: Out-of-Pocket Burden & Persistence",
        "clinical_data_point": "92% of eligible commercially insured patients access therapy with $0 copay via the Co-Pay Card.",
        "leave_behind": "Comprehensive Patient Co-Pay & Foundation Assistance Tear-Sheet (Ref: MLR-ACC-2026-v1)",
        "compliance_ref": "MLR-ACC-2026-v1"
    },
    "dosing_administration": {
        "trial_citation": "Clinical Pharmacokinetics & Infusion Optimization Study",
        "clinical_data_point": "Flexible 60-minute bi-weekly infusion with no pre-medication requirements for secondary lines.",
        "leave_behind": "Nursing Infusion & Dose Modification Protocol Guide (Ref: MLR-DOS-2026-v3)",
        "compliance_ref": "MLR-DOS-2026-v3"
    }
}


class GenerativeAssetStitcher:
    def __init__(self, model_name: str = "openai/gpt-oss-20b"):
        self.model_name = model_name
        self.api_key = os.getenv("GROQ_API_KEY")
        self.client = None
        
        if GROQ_AVAILABLE and self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Failed to initialize Groq client: {e}")
                self.client = None

    def _call_groq_json(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        """Executes a structured JSON call against the Groq API."""
        if not self.client:
            return None
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"[Groq API Error] {e}")
            return None

    def generate_precall_brief(self, hcp_record: Any, laya_decision: Dict[str, Any]) -> Dict[str, str]:
        """
        Synthesizes Laya's decisions + CRM history into a field-rep pre-call brief via Groq LLM.
        """
        content_key = laya_decision.get("final_content", "clinical_efficacy")
        asset_info = APPROVED_CLINICAL_ASSETS.get(content_key, APPROVED_CLINICAL_ASSETS["clinical_efficacy"])
        
        prof = hcp_record.laya_dict_state["profile"]
        rx = hcp_record.laya_dict_state["rx_dynamics"]
        notes = hcp_record.laya_dict_state["recent_crm_notes"]
        notes_str = "\n".join([f"- {n}" for n in notes]) if notes else "No notes logged."

        system_prompt = (
            "You are an elite Life Sciences Commercial Intelligence Copilot for pharmaceutical field reps. "
            "Your job is to generate a concise, tactical Pre-Call Detailing Brief for a sales rep before entering a clinic. "
            "You must strictly ground your clinical evidence and leave-behinds in the provided approved MLR assets. "
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "primary_barrier": "1 sentence summarizing the HCP\'s clinical friction or objection",\n'
            '  "counter_pivot": "1-2 sentences on how the rep should counter or reframe the discussion",\n'
            '  "key_clinical_evidence": "The exact trial citation and clinical data point provided in the context",\n'
            '  "recommended_leave_behind": "The exact leave-behind document name provided in the context",\n'
            '  "suggested_opening_hook": "Natural, conversational opening statement the rep can say to the doctor"\n'
            "}"
        )

        user_prompt = f"""
Physician Dossier:
- Name: {hcp_record.full_name}
- Specialty: {prof['specialty']} | Decile: {prof['decile']}/10 | Access: {prof['access_level']}
- Territory: {hcp_record.metadata['territory']}
- Prescribing Trend: 3M TRx: {rx['trx_volume_3m']} units | Brand Growth: {rx['brand_growth_pct']:+.1f}% | Competitor Shift: {rx['competitor_growth_pct']:+.1f}%
- Formulary: {rx['formulary_tier']}

Laya System 1 Decisions:
- Recommended Channel: {laya_decision.get('final_channel')}
- Core Content Theme: {content_key}
- Calibrated Churn Risk: {laya_decision.get('churn_prob', 0):.1%}
- Priority Tier: {laya_decision.get('final_priority')}

Recent CRM Logs / Field Notes:
{notes_str}

Mandatory Approved Regulatory Assets:
- Citation: {asset_info['trial_citation']}
- Data Point: {asset_info['clinical_data_point']}
- Leave-Behind: {asset_info['leave_behind']}
"""

        result = self._call_groq_json(system_prompt, user_prompt)
        
        # If Groq returns valid structured JSON, use it; otherwise fall back smoothly
        if result and "primary_barrier" in result and "suggested_opening_hook" in result:
            return result

        # Rule-based fallback if API key is unset or unreachable
        return {
            "primary_barrier": f"Prescriber expresses reservation regarding {content_key.replace('_', ' ')} based on recent notes.",
            "counter_pivot": f"Acknowledge practitioner concerns and pivot to {asset_info['trial_citation']}.",
            "key_clinical_evidence": f"{asset_info['trial_citation']} — {asset_info['clinical_data_point']}",
            "recommended_leave_behind": asset_info["leave_behind"],
            "suggested_opening_hook": f"Dr. {hcp_record.full_name.split()[-2]}, I know managing patient outcomes in {prof['specialty']} is top of mind—I wanted to briefly share new findings from {asset_info['trial_citation'].split()[0]}."
        }

    def generate_email_draft(self, hcp_record: Any, laya_decision: Dict[str, Any]) -> Dict[str, str]:
        """
        Generates an MLR-compliant Rep-Triggered Email draft via Groq LLM.
        """
        content_key = laya_decision.get("final_content", "clinical_efficacy")
        asset_info = APPROVED_CLINICAL_ASSETS.get(content_key, APPROVED_CLINICAL_ASSETS["clinical_efficacy"])
        physician_last = hcp_record.full_name.split()[-2]

        prof = hcp_record.laya_dict_state["profile"]
        notes = hcp_record.laya_dict_state["recent_crm_notes"]
        notes_str = "\n".join([f"- {n}" for n in notes]) if notes else "No previous field calls."

        system_prompt = (
            "You are a compliant Life Sciences Medical Communications Assistant writing a personalized "
            "Rep-Triggered Email from a pharmaceutical sales representative to a healthcare provider. "
            "Requirements:\n"
            "1. Tone: Professional, peer-to-peer, concise, non-promotional, and evidence-grounded.\n"
            "2. Reference the doctor's specialty and context from their recent interactions.\n"
            "3. Embed the exact trial citation and clinical data point from the mandatory asset library.\n"
            "4. Mention the attached leave-behind material.\n"
            "5. Include a closing compliance footer with the provided MLR code.\n"
            "Respond ONLY with a valid JSON object matching:\n"
            "{\n"
            '  "subject": "Clear, informative email subject line",\n'
            '  "body": "Complete email body including salutation, body paragraphs, sign-off, and disclaimer"\n'
            "}"
        )

        user_prompt = f"""
Physician: {hcp_record.full_name} (Dr. {physician_last})
Specialty: {prof['specialty']}
Territory: {hcp_record.metadata['territory']}
Context from recent CRM interactions:
{notes_str}

Laya Targeting Pillar: {content_key.replace('_', ' ').title()}

Mandatory Clinical Asset to Include:
- Trial Citation: {asset_info['trial_citation']}
- Data Point: {asset_info['clinical_data_point']}
- Attached Document: {asset_info['leave_behind']}
- MLR Code: {asset_info['compliance_ref']}
"""

        result = self._call_groq_json(system_prompt, user_prompt)
        
        if result and "subject" in result and "body" in result:
            return {
                "subject": result["subject"],
                "recipient": f"{hcp_record.full_name} <verified-hcp@hospital-network.org>",
                "body": result["body"],
                "compliance_doc_id": asset_info["compliance_ref"]
            }

        # Deterministic fallback if API is unavailable
        fallback_body = f"""Dear Dr. {physician_last},

Thank you for your continued dedication to patient care in {prof['specialty']}.

Following up on our recent conversation, I wanted to provide the latest published evidence concerning {content_key.replace('_', ' ')}:

• {asset_info['trial_citation']}:
  {asset_info['clinical_data_point']}

I have attached our digital {asset_info['leave_behind']} for your clinical practice. Please let me know if you would like me to coordinate a brief discussion with our Medical Science Liaison team to review the subgroup data.

Warm regards,

Field Sales Representative
Territory: {hcp_record.metadata['territory']}
[Compliance Ref: {asset_info['compliance_ref']}]"""

        return {
            "subject": f"Clinical Follow-Up: Evidence on {content_key.replace('_', ' ').title()} for your practice",
            "recipient": f"{hcp_record.full_name} <verified-hcp@hospital-network.org>",
            "body": fallback_body,
            "compliance_doc_id": asset_info["compliance_ref"]
        }
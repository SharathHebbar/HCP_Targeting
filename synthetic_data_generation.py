import sqlite3
import json
import random
from datetime import datetime, timedelta
import numpy as np
from faker import Faker

# --- Configuration & Seeds ---
DB_NAME = "hcp_targeting.db"
NUM_HCPS = 1000

fake = Faker("en_US")
np.random.seed(42)
random.seed(42)

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
    "Rep visited: HCP raised concerns regarding patient tolerability and gastrointestinal adverse events.",
    "Attended regional symposium: Expressed keen interest in 3-year progression-free survival (PFS) trial data.",
    "Rep detailing note: Refused in-person meeting citing strict hospital no-see protocol; requested digital summary.",
    "Email interaction: Opened clinical trial newsletter; clicked link on head-to-head comparative efficacy study.",
    "MSL scientific inquiry: Requested technical clarification on biomarker subgroup analysis and dosing titration schedules.",
    "Interaction note: High prescriber of competitor therapy; skeptical of switching without real-world registry evidence.",
    "Field call: Mentions patient complaints on high copay tier; inquiring on co-pay assistance cards and foundation support.",
    "Webinar attendee: Logged into live CME session on next-generation combination therapies."
]

def init_db(conn: sqlite3.Connection):
    cursor = conn.cursor()
    
    # 1. Base HCP Demographics & Access
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hcps (
        hcp_id TEXT PRIMARY KEY,
        npi TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        specialty TEXT NOT NULL,
        decile INTEGER NOT NULL,
        territory TEXT NOT NULL,
        is_kol BOOLEAN NOT NULL,
        access_level TEXT NOT NULL,
        email_opt_in BOOLEAN NOT NULL,
        days_since_last_call INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Prescribing Dynamics & Formulary Tier
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hcp_prescribing_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hcp_id TEXT NOT NULL,
        trx_volume_3m INTEGER NOT NULL,
        brand_growth_pct REAL NOT NULL,
        competitor_growth_pct REAL NOT NULL,
        formulary_tier TEXT NOT NULL,
        metric_date DATE NOT NULL,
        FOREIGN KEY (hcp_id) REFERENCES hcps(hcp_id)
    );
    """)

    # 3. CRM Interactions enriched with Omni-Channel telemetry
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hcp_crm_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hcp_id TEXT NOT NULL,
        interaction_date DATE NOT NULL,
        channel_used TEXT NOT NULL,
        call_duration REAL,
        emails_sent INTEGER DEFAULT 0,
        emails_opened INTEGER DEFAULT 0,
        emails_clicked INTEGER DEFAULT 0,
        ctr REAL DEFAULT 0.0,
        ctor REAL DEFAULT 0.0,
        interaction_note TEXT NOT NULL,
        FOREIGN KEY (hcp_id) REFERENCES hcps(hcp_id)
    );
    """)

    # 4. Laya State View (Unchanged schema: guarantees zero breakages in Laya)
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS v_hcp_laya_state AS
    SELECT 
        h.hcp_id,
        h.full_name,
        h.decile,
        h.territory,
        json_object(
            'profile', json_object(
                'specialty', h.specialty,
                'decile', h.decile,
                'access_level', h.access_level,
                'is_kol', CASE WHEN h.is_kol = 1 THEN json('true') ELSE json('false') END
            ),
            'rx_dynamics', json_object(
                'trx_volume_3m', m.trx_volume_3m,
                'brand_growth_pct', m.brand_growth_pct,
                'competitor_growth_pct', m.competitor_growth_pct,
                'formulary_tier', m.formulary_tier
            ),
            'recent_crm_notes', (
                SELECT json_group_array(interaction_note)
                FROM hcp_crm_interactions
                WHERE hcp_id = h.hcp_id
            )
        ) AS laya_state_json
    FROM hcps h
    JOIN hcp_prescribing_metrics m ON h.hcp_id = m.hcp_id;
    """)

    conn.commit()

def generate_and_insert_data(conn: sqlite3.Connection, num_records: int):
    cursor = conn.cursor()
    today = datetime.now().date()
    
    hcp_rows = []
    metrics_rows = []
    crm_rows = []

    for i in range(1, num_records + 1):
        hcp_id = f"HCP_{i:05d}"
        npi = f"{random.randint(1000000000, 9999999999)}"
        full_name = f"Dr. {fake.first_name()} {fake.last_name()}, MD"
        specialty = random.choice(SPECIALTIES)
        
        decile = int(np.random.choice(range(1, 11), p=[0.05, 0.05, 0.08, 0.10, 0.12, 0.15, 0.15, 0.12, 0.10, 0.08]))
        is_kol = 1 if (decile >= 8 and random.random() < 0.25) else 0
        access_level = random.choices(["Open Access", "Restricted Access", "No-See"], weights=[0.55, 0.35, 0.10])[0]
        email_opt_in = 1 if random.random() < 0.72 else 0
        days_since_last_call = int(np.random.exponential(scale=28)) + 1
        territory = random.choice(TERRITORIES)

        hcp_rows.append((
            hcp_id, npi, full_name, specialty, decile, territory, 
            is_kol, access_level, email_opt_in, days_since_last_call
        ))

        base_trx = int(np.clip(np.random.normal(loc=decile * 15, scale=8), 5, 220))
        brand_growth = round(float(np.random.normal(loc=-2.0 if decile > 6 else 1.5, scale=11.0)), 2)
        competitor_growth = round(float(np.random.normal(loc=4.5 if brand_growth < 0 else -1.0, scale=7.5)), 2)
        formulary = random.choice(FORMULARY_TIERS)

        metrics_rows.append((
            hcp_id, base_trx, brand_growth, competitor_growth, formulary, today.isoformat()
        ))

        # Generate 1 to 3 CRM touchpoints per HCP with realistic metrics
        num_notes = random.randint(1, 3)
        for _ in range(num_notes):
            days_ago = random.randint(3, 90)
            interaction_date = today - timedelta(days=days_ago)
            channel = random.choice(["Field Detail", "Medical Inquiry", "Email Campaign", "CME Symposium"])
            note = random.choice(INTERACTION_TEMPLATES)
            
            # Channel-specific metric simulation
            call_duration = None
            emails_sent = 0
            emails_opened = 0
            emails_clicked = 0
            ctr = 0.0
            ctor = 0.0

            if channel in ["Field Detail", "Medical Inquiry"]:
                # Rep/MSL calls last between 4 and 45 minutes
                mean_dur = 25.0 if channel == "Medical Inquiry" else 12.0
                call_duration = round(float(np.clip(np.random.normal(loc=mean_dur, scale=6.0), 3.0, 50.0)), 1)
            elif channel == "Email Campaign":
                emails_sent = random.randint(2, 8)
                emails_opened = int(np.random.binomial(n=emails_sent, p=0.45 if email_opt_in else 0.15))
                emails_clicked = int(np.random.binomial(n=emails_opened, p=0.30)) if emails_opened > 0 else 0
                
                ctr = round(emails_clicked / emails_sent, 4) if emails_sent > 0 else 0.0
                ctor = round(emails_clicked / emails_opened, 4) if emails_opened > 0 else 0.0

            crm_rows.append((
                hcp_id, 
                interaction_date.isoformat(), 
                channel, 
                call_duration, 
                emails_sent, 
                emails_opened, 
                emails_clicked, 
                ctr, 
                ctor, 
                f"[{interaction_date}] {note}"
            ))

    cursor.executemany("""
    INSERT INTO hcps (hcp_id, npi, full_name, specialty, decile, territory, is_kol, access_level, email_opt_in, days_since_last_call)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, hcp_rows)

    cursor.executemany("""
    INSERT INTO hcp_prescribing_metrics (hcp_id, trx_volume_3m, brand_growth_pct, competitor_growth_pct, formulary_tier, metric_date)
    VALUES (?, ?, ?, ?, ?, ?);
    """, metrics_rows)

    cursor.executemany("""
    INSERT INTO hcp_crm_interactions (
        hcp_id, interaction_date, channel_used, call_duration, 
        emails_sent, emails_opened, emails_clicked, ctr, ctor, interaction_note
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, crm_rows)

    conn.commit()
    print(f"✅ Successfully inserted {num_records} HCPs with omni-channel engagement metrics into '{DB_NAME}'.")

if __name__ == "__main__":
    # Clean reset for new schema
    import os
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"Removed previous '{DB_NAME}' for clean schema migration.")

    conn = sqlite3.connect(DB_NAME)
    init_db(conn)
    generate_and_insert_data(conn, NUM_HCPS)
    conn.close()
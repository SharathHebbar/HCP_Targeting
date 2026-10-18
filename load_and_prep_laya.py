import sqlite3
import json
from typing import List, Dict, Any, Generator, Optional
from pydantic import BaseModel, Field

DB_NAME = "hcp_targeting.db"

# --- 1. Pydantic Models for State Validation ---

class ProfileState(BaseModel):
    specialty: str
    decile: int = Field(ge=1, le=10)
    access_level: str
    is_kol: bool

class RxDynamicsState(BaseModel):
    trx_volume_3m: int
    brand_growth_pct: float
    competitor_growth_pct: float
    formulary_tier: str

class LayaHCPState(BaseModel):
    profile: ProfileState
    rx_dynamics: RxDynamicsState
    recent_crm_notes: List[str]

    def to_serialized_text(self) -> str:
        """
        Converts the structured state into dense, semantic context.
        This format maximizes ModernBERT/mmBERT cross-attention across fields.
        """
        kol_str = "Yes (Tier 1 KOL)" if self.profile.is_kol else "No"
        crm_summary = " ".join(self.recent_crm_notes) if self.recent_crm_notes else "No recent CRM interactions logged."
        
        return (
            f"HCP PROFILE: Specialty: {self.profile.specialty} | Prescriber Decile: {self.profile.decile}/10 | "
            f"KOL Status: {kol_str} | Hospital Access: {self.profile.access_level}. "
            f"RX DYNAMICS (Last 3 Months): Total TRx Volume: {self.rx_dynamics.trx_volume_3m} units | "
            f"Brand Growth: {self.rx_dynamics.brand_growth_pct:+.1f}% | "
            f"Competitor Growth: {self.rx_dynamics.competitor_growth_pct:+.1f}% | "
            f"Formulary Status: {self.rx_dynamics.formulary_tier}. "
            f"RECENT FIELD REP & CRM INTERACTIONS: {crm_summary}"
        )


class PreparedHCPRecord(BaseModel):
    hcp_id: str
    full_name: str
    metadata: Dict[str, Any]
    laya_dict_state: Dict[str, Any]
    laya_text_state: str


# --- 2. Database Reader & Transformer ---

class HCPDataLoader:
    def __init__(self, db_path: str = DB_NAME):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_all_prepared_records(self, limit: Optional[int] = None) -> List[PreparedHCPRecord]:
        """
        Reads from SQLite, validates against Pydantic, and returns 
        Laya-compatible payloads.
        """
        records = []
        conn = self._get_connection()
        cursor = conn.cursor()

        # Query using the view created in Step 1, joining base flags needed for arbitration
        query = """
        SELECT 
            v.hcp_id,
            v.full_name,
            v.laya_state_json,
            h.territory,
            h.email_opt_in,
            h.days_since_last_call
        FROM v_hcp_laya_state v
        JOIN hcps h ON v.hcp_id = h.hcp_id
        """
        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            # 1. Parse raw JSON from SQLite
            raw_json = json.loads(row["laya_state_json"])
            
            # 2. Strict validation via Pydantic
            validated_state = LayaHCPState(**raw_json)

            # 3. Format into dual Laya representations (Dict & Serialized Text)
            prepared = PreparedHCPRecord(
                hcp_id=row["hcp_id"],
                full_name=row["full_name"],
                metadata={
                    "territory": row["territory"],
                    "email_opt_in": bool(row["email_opt_in"]),
                    "days_since_last_call": row["days_since_last_call"]
                },
                laya_dict_state=validated_state.model_dump(),
                laya_text_state=validated_state.to_serialized_text()
            )
            records.append(prepared)

        conn.close()
        return records

    def batch_streamer(self, batch_size: int = 50) -> Generator[List[PreparedHCPRecord], None, None]:
        """
        Memory-efficient generator for streaming batches directly to 
        parallel workers or the Laya inference server.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
        SELECT 
            v.hcp_id,
            v.full_name,
            v.laya_state_json,
            h.territory,
            h.email_opt_in,
            h.days_since_last_call
        FROM v_hcp_laya_state v
        JOIN hcps h ON v.hcp_id = h.hcp_id
        """
        cursor.execute(query)

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            
            batch = []
            for row in rows:
                raw_json = json.loads(row["laya_state_json"])
                validated_state = LayaHCPState(**raw_json)
                batch.append(PreparedHCPRecord(
                    hcp_id=row["hcp_id"],
                    full_name=row["full_name"],
                    metadata={
                        "territory": row["territory"],
                        "email_opt_in": bool(row["email_opt_in"]),
                        "days_since_last_call": row["days_since_last_call"]
                    },
                    laya_dict_state=validated_state.model_dump(),
                    laya_text_state=validated_state.to_serialized_text()
                ))
            yield batch

        conn.close()


# --- 3. Verification & Example Inspection ---

if __name__ == "__main__":
    loader = HCPDataLoader(DB_NAME)
    
    print("Loading and preparing sample records from SQLite...")
    sample_records = loader.fetch_all_prepared_records(limit=2)
    
    if not sample_records:
        print("No records found. Please ensure Step 1 (generate_and_store_hcps.py) was run.")
    else:
        sample = sample_records[0]
        print(f"\n==========================================")
        print(f"HCP: {sample.full_name} ({sample.hcp_id})")
        print(f"==========================================")
        
        print("\n[Format A: Laya Typed Dict State (for direct JSON prediction)]:")
        print(json.dumps(sample.laya_dict_state, indent=2))
        
        print("\n[Format B: Laya Serialized Text State (for single-encoder cross-attention)]:")
        print(sample.laya_text_state)
        
        print("\n[Metadata for downstream arbitration]:")
        print(sample.metadata)

        # Test batch streaming
        total_batches = 0
        total_count = 0
        for batch in loader.batch_streamer(batch_size=100):
            total_batches += 1
            total_count += len(batch)
            
        print(f"\nStreamer check: verified {total_count} records across {total_batches} batches (100 records/batch).")
import json
import csv
from io import StringIO
from datetime import datetime, timedelta, UTC
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# --- 1. DATABASE CONFIGURATION ---
import os
# If running on Render cloud, default to safe runtime memory database parameters
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./risk_engine.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- 2. DATABASE MODEL ---
class RiskAssessmentLog(Base):
    __tablename__ = "risk_assessment_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    national_id = Column(String, index=True)
    phone_number = Column(String)
    requested_amount = Column(Float)
    computed_score = Column(Integer)
    decision = Column(String)
    decision_reason = Column(String)
    risk_flags = Column(String)
    metrics_summary = Column(String)
    crb_status = Column(String)  
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- 3. FASTAPI SCHEMAS ---
app = FastAPI(title="Kenya Risk Engine API", version="1.5.0")


class ApplicantProfile(BaseModel):
    user_id: str = Field(..., examples=["KE_USER_9941"])
    national_id: str = Field(..., description="Kenyan National ID", examples=["32145678"])
    phone_number: str = Field(..., description="Format: +254...", examples=["+254712345678"])
    requested_amount: float = Field(..., description="Loan size requested in KES", examples=[7500.00])
    base_credit_score: int = Field(default=600, description="Starting score value out of 900", examples=[600])
    is_crb_listed: bool = Field(default=False, description="True if applicant has active CRB listings", examples=[False])


class MpesaRecord(BaseModel):
    transaction_id: str = Field(..., examples=["RQA12MXZ45"])
    date: str = Field(..., description="Format: YYYY-MM-DD", examples=["2026-09-02"])
    type: str = Field(..., description="e.g., Fuliza, Paybill Tala, Paybill Branch, Till, P2P", examples=["Paybill Tala"])
    amount: float = Field(..., description="Amount in KES", examples=[1200.00])


class RiskAssessmentRequest(BaseModel):
    applicant_profile: ApplicantProfile
    historical_records: List[MpesaRecord]


# --- 4. ENGINE CORE BUSINESS LOGIC ---
def evaluate_credit_risk(profile: ApplicantProfile, records: List[MpesaRecord]) -> dict:
    current_month = datetime.now(UTC).strftime("%Y-%m")

    fuliza_count = 0
    total_fuliza_value = 0.0
    betting_count = 0
    total_inflows = 0.0
    
    # NEW: Unique competitor lender tracking set
    detected_lenders = set()

    for record in records:
        record_type_lower = record.type.lower()
        
        # Parse standard monthly behaviors
        if record.date.startswith(current_month) and "fuliza" in record_type_lower:
            fuliza_count += 1
            total_fuliza_value += record.amount
        if "sportpesa" in record_type_lower or "betika" in record_type_lower:
            betting_count += 1
        if "inflow" in record_type_lower or "received" in record_type_lower:
            total_inflows += record.amount
            
        # NEW: Check for competitor micro-loan repayment keywords
        if record.date.startswith(current_month):
            if "tala" in record_type_lower:
                detected_lenders.add("TALA")
            elif "branch" in record_type_lower:
                detected_lenders.add("BRANCH")
            elif "zenka" in record_type_lower:
                detected_lenders.add("ZENKA")
            elif "mshwari" in record_type_lower or "m-shwari" in record_type_lower:
                detected_lenders.add("MSHWARI")

    score = profile.base_credit_score
    flags = []

    # Apply processing deductions
    if fuliza_count > 5:
        score -= 50
        flags.append("HIGH_FREQUENCY_FULIZA_LOOP")

    if betting_count > 3:
        score -= 30
        flags.append("EXCESSIVE_GAMBLING_VELOCITY")

    if profile.is_crb_listed:
        score -= 250  
        flags.append("ACTIVE_CRB_BLACKLIST_DEFAULT")

    # NEW: Multi-lender loan stacking penalty rule
    lender_count = len(detected_lenders)
    if lender_count >= 2:
        score -= 40
        flags.append(f"CONCURRENT_LOAN_STACKING_DETECTED_{lender_count}_LENDERS")

    final_score = max(300, min(900, score))

    # Assessment routing
    if profile.is_crb_listed:
        decision = "DECLINED"
        reason = "Hard block triggered due to active adverse listing matching Credit Reference Bureau registries."
    elif final_score < 500:
        decision = "DECLINED"
        reason = "Credit score fell below acceptable risk thresholds."
    elif profile.requested_amount > (total_inflows * 0.5):
        decision = "DECLINED"
        reason = "Requested amount exceeds safe debt-to-income limits based on observed monthly inflows."
    else:
        decision = "APPROVED"
        reason = "Applicant meets minimum credit safety parameters."

    return {
        "assessment_month": current_month,
        "metrics": {
            "fuliza_uses_this_month": fuliza_count,
            "total_fuliza_exposure_kes": total_fuliza_value,
            "betting_transactions_detected": betting_count,
            "estimated_monthly_inflow_kes": total_inflows,
            "concurrent_lenders_count": lender_count  # NEW
        },
        "risk_flags": flags,
        "computed_score": final_score,
        "decision": decision,
        "decision_reason": reason,
    }


# --- 5. API ENDPOINTS ---

@app.post("/api/v1/assess-risk")
def calculate_user_risk(payload: RiskAssessmentRequest, db: Session = Depends(get_db)):
    nat_id = payload.applicant_profile.national_id

    time_threshold = datetime.now(UTC) - timedelta(hours=24)
    recent_declines = (
        db.query(RiskAssessmentLog)
        .filter(
            RiskAssessmentLog.national_id == nat_id,
            RiskAssessmentLog.decision == "DECLINED",
            RiskAssessmentLog.created_at >= time_threshold,
        )
        .count()
    )

    if recent_declines >= 3:
        raise HTTPException(
            status_code=429,
            detail="Application blocked. Maximum decline limit reached within 24 hours. Try again tomorrow.",
        )

    results = evaluate_credit_risk(payload.applicant_profile, payload.historical_records)

    db_log = RiskAssessmentLog(
        user_id=payload.applicant_profile.user_id,
        national_id=nat_id,
        phone_number=payload.applicant_profile.phone_number,
        requested_amount=payload.applicant_profile.requested_amount,
        computed_score=results["computed_score"],
        decision=results["decision"],
        decision_reason=results["decision_reason"],
        risk_flags=",".join(results["risk_flags"]),
        metrics_summary=json.dumps(results["metrics"]),
        crb_status="LISTED" if payload.applicant_profile.is_crb_listed else "CLEAN",
    )

    db.add(db_log)
    db.commit()
    db.refresh(db_log)

    return {
        "user_id": payload.applicant_profile.user_id,
        "status": "success",
        "log_id_saved": db_log.id,
        "result": results,
    }


@app.get("/api/v1/audit-logs/export-csv")
def export_audit_logs_csv(db: Session = Depends(get_db)):
    logs = db.query(RiskAssessmentLog).order_by(RiskAssessmentLog.id.desc()).all()

    stream = StringIO()
    writer = csv.writer(stream, delimiter=",")
    writer.writerow([
        "Log ID", "User ID", "National ID", "Phone Number", "Requested Amt (KES)",
        "CRB Status", "Computed Score", "Decision", "Reason", "Risk Flags", "Timestamp (UTC)"
    ])

    for log in logs:
        writer.writerow([
            log.id, log.user_id, log.national_id, log.phone_number, log.requested_amount,
            log.crb_status, log.computed_score, log.decision, log.decision_reason, log.risk_flags,
            log.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])

    stream.seek(0)
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=kenya_risk_audit_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
    return response


@app.get("/api/v1/audit-logs")
def get_all_logs(limit: int = 10, db: Session = Depends(get_db)):
    logs = db.query(RiskAssessmentLog).limit(limit).all()
    return {"total_retrieved": len(logs), "audit_trail": logs}


@app.get("/")
def read_root():
    return {"message": "Welcome to Kenya Risk Engine API - Multi-Lender Ready"}

import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Kenya Risk Engine", layout="wide")
st.title("🎯 Kenya Risk Engine - Management Center")
st.markdown("---")

tab1, tab2 = st.tabs(["⚡ Live Assessment Simulator", "📊 Historical Audit Spreadsheet"])

with tab1:
    l_panel, r_panel = st.columns(2)
    with l_panel:
        st.header("👤 1. Applicant Profile")
        u_id = st.text_input("User Reference ID", value="KE_USER_9941")
        nat_id = st.text_input("National Identification ID", value="32145678")
        phone = st.text_input("Phone Number", value="+254712345678")
        score = st.slider("Initial Credit Rating Score", 300, 900, 600)
        amount = st.number_input("Requested Loan Principal (KES)", 100, 50000, 7500)
        crb = st.checkbox("⚠️ Active CRB Blacklist Registry Listing (Defaults Present)")

        st.header("📊 2. Historical Transaction History Sim")
        fuliza = st.number_input("Fuliza Cycles This Month", 0, 20, 2)
        betting = st.number_input("Betting Outflows Detected", 0, 20, 1)
        inflows = st.number_input("Estimated Cash Inflows (KES)", 0, 100000, 20000)

        st.markdown("##### 📱 Competitor Micro-Loan Repayments:")
        c1, c2, c3, c4 = st.columns(4)
        has_tala = c1.checkbox("Tala")
        has_branch = c2.checkbox("Branch")
        has_zenka = c3.checkbox("Zenka")
        has_mshwari = c4.checkbox("M-Shwari")

        records = []
        cur_date = datetime.now().strftime("%Y-%m-%d")
        for i in range(fuliza): records.append({"transaction_id": f"FLZ{i}", "date": cur_date, "type": "Fuliza", "amount": 1000.0})
        for i in range(betting): records.append({"transaction_id": f"BET{i}", "date": cur_date, "type": "SportPesa", "amount": 500.0})
        if inflows > 0: records.append({"transaction_id": "INF1", "date": cur_date, "type": "Inflow", "amount": float(inflows)})
        if has_tala: records.append({"transaction_id": "TL1", "date": cur_date, "type": "Tala", "amount": 1500.0})
        if has_branch: records.append({"transaction_id": "BR1", "date": cur_date, "type": "Branch", "amount": 2000.0})
        if has_zenka: records.append({"transaction_id": "ZK1", "date": cur_date, "type": "Zenka", "amount": 1200.0})
        if has_mshwari: records.append({"transaction_id": "MS1", "date": cur_date, "type": "M-Shwari", "amount": 3000.0})

    with r_panel:
        st.header("⚡ Live Core API Assessment Engine")
        if st.button("Execute Risk Assessment Pipeline", type="primary", use_container_width=True):
            payload = {
                "applicant_profile": {"user_id": u_id, "national_id": nat_id, "phone_number": phone, "requested_amount": float(amount), "base_credit_score": int(score), "is_crb_listed": bool(crb)},
                "historical_records": records
            }
            try:
                res = requests.post("https://onrender.com", json=payload, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    asm = data["result"]
                    if asm["decision"] == "APPROVED": st.success(f"🎉 DECISION: {asm['decision']}")
                    else: st.error(f"❌ DECISION: {asm['decision']}")
                    st.metric("Computed Credit Safety Score", f"{asm['computed_score']} / 900")
                    st.info(f"💡 **Reason:** {asm['decision_reason']}")
                    if asm["risk_flags"]:
                        st.warning("⚠️ **Active Flags:**")
                        for f in asm["risk_flags"]: st.markdown(f"- `{f}`")
                elif res.status_code == 429: st.error("🚨 429: Throttled.")
                else: st.error(f"❌ Error: {res.text}")
            except Exception as e: st.error("🔌 Network Error: Backend server offline or cold starting.")

with tab2:
    st.header("📂 Portfolio Underwriting History & Audit Trail")
    if st.button("🔄 Refresh Audit Logs from Database", use_container_width=True):
        try:
            res = requests.get("https://onrender.com", params={"limit": 100}, timeout=30)
            if res.status_code == 200:
                raw_logs = res.json().get("audit_trail", [])
                if raw_logs:
                    df = pd.DataFrame(raw_logs)[[
                        "id", "user_id", "national_id", "phone_number", "requested_amount", "crb_status", "computed_score", "decision", "decision_reason", "risk_flags", "created_at"
                    ]]
                    df.columns = ["Log ID", "User ID", "National ID", "Phone", "Amount (KES)", "CRB Status", "Score", "Decision", "Reason", "Flags", "Timestamp"]
                    
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Total Decisions", len(df))
                    k2.metric("Approvals", len(df[df["Decision"] == "APPROVED"]))
                    k3.metric("Declines", len(df[df["Decision"] == "DECLINED"]))
                    
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button("💾 Download Audit Trail Report (CSV)", data=df.to_csv(index=False).encode('utf-8'), file_name="kenya_risk_ledger.csv", mime="text/csv", use_container_width=True)
                else: st.info("Database table is empty.")
            else: st.error(f"❌ Backend Error: {res.text}")
        except Exception as e: st.error("🔌 Linkage Breakdown: Backend API offline.")

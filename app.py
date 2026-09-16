import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Kenya Risk Engine - Dashboard", page_icon="🎯", layout="wide")

st.title("🎯 Kenya Risk Engine - Management Center")
st.markdown("---")

tab1, tab2 = st.tabs(["⚡ Live Assessment Simulator", "📊 Historical Audit Spreadsheet"])

# --- TAB 1: CORE SIMULATOR ---
with tab1:
    left_panel, right_panel = st.columns(2)

    with left_panel:
        st.header("👤 1. Applicant Profile")
        
        col1, col2 = st.columns(2)
        with col1:
            user_id = st.text_input("User Reference ID", value="KE_USER_9941")
            national_id = st.text_input("National Identification ID", value="32145678")
        with col2:
            phone_number = st.text_input("Phone Number", value="+254712345678")
            base_credit_score = st.slider("Initial Credit Rating Score", min_value=300, max_value=900, value=600)
            
        requested_amount = st.number_input("Requested Loan Principal (KES)", min_value=100, max_value=50000, value=7500)
        is_crb_listed = st.checkbox("⚠️ Active CRB Blacklist Registry Listing (Defaults Present)")

        st.header("📊 2. Historical Transaction History Sim")
        st.markdown("Simulate behavioral events observed inside the applicant's M-Pesa logs:")
        
        col3, col4, col5 = st.columns(3)
        with col3:
            fuliza_count = st.number_input("Fuliza Cycles This Month", min_value=0, max_value=20, value=2)
        with col4:
            betting_count = st.number_input("Betting Outflows Detected", min_value=0, max_value=20, value=1)
        with col5:
            monthly_inflows = st.number_input("Estimated Cash Inflows (KES)", min_value=0, max_value=100000, value=20000)

        # NEW: Multi-Lender Loan Stacking Simulation Boxes
        st.markdown("##### 📱 Competitor Micro-Loan Repayments Found This Month:")
        c1, c2, c3, c4 = st.columns(4)
        has_tala = c1.checkbox("Tala Loan")
        has_branch = c2.checkbox("Branch Loan")
        has_zenka = c3.checkbox("Zenka Loan")
        has_mshwari = c4.checkbox("M-Shwari Loan")

        records = []
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        for i in range(fuliza_count):
            records.append({"transaction_id": f"FLZ{i}", "date": current_date, "type": "Fuliza Drawdown", "amount": 1000.0})
        for i in range(betting_count):
            records.append({"transaction_id": f"BET{i}", "date": current_date, "type": "Paybill (SportPesa)", "amount": 500.0})
        if monthly_inflows > 0:
            records.append({"transaction_id": "INF1", "date": current_date, "type": "Inflow Received (Till)", "amount": float(monthly_inflows)})
            
        # NEW: Append simulated lender logs based on checkboxes
        if has_tala:
            records.append({"transaction_id": "TL1", "date": current_date, "type": "Paybill to Tala", "amount": 1500.0})
        if has_branch:
            records.append({"transaction_id": "BR1", "date": current_date, "type": "Paybill to Branch", "amount": 2000.0})
        if has_zenka:
            records.append({"transaction_id": "ZK1", "date": current_date, "type": "Paybill to Zenka", "amount": 1200.0})
        if has_mshwari:
            records.append({"transaction_id": "MS1", "date": current_date, "type": "M-Shwari Loan Repay", "amount": 3000.0})

    with right_panel:
        st.header("⚡ Live Core API Assessment Engine")
        st.write("")
        
        if st.button("Execute Risk Assessment Pipeline", type="primary", use_container_width=True):
            payload = {
                "applicant_profile": {
                    "user_id": user_id,
                    "national_id": national_id,
                    "phone_number": phone_number,
                    "requested_amount": float(requested_amount),
                    "base_credit_score": int(base_credit_score),
                    "is_crb_listed": bool(is_crb_listed)
                },
                "historical_records": records
            }
            
            try:
                api_endpoint = "https://onrender.com"
                response = requests.post(api_endpoint, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    assessment = data["result"]
                    
                    if assessment["decision"] == "APPROVED":
                        st.success(f"🎉 DECISION: {assessment['decision']}")
                    else:
                        st.error(f"❌ DECISION: {assessment['decision']}")
                    
                    st.metric(label="Computed Credit Safety Score", value=f"{assessment['computed_score']} / 900")
                    st.info(f"💡 **Reason:** {assessment['decision_reason']}")
                    
                    if assessment["risk_flags"]:
                        st.warning("⚠️ **Active Portfolio Risk Flags Raised:**")
                        for flag in assessment["risk_flags"]:
                            st.markdown(f"- `{flag}`")
                    else:
                        st.success("✅ Clean Profile: No risk warnings flagged inside current loop window.")
                        
                    with st.expander("View Raw JSON Network Telemetry"):
                        st.json(data)
                        
                elif response.status_code == 429:
                    st.error("🚨 429 Too Many Requests: This national identity key is hard-blocked due to request submission throttling restrictions.")
                else:
                    st.error(f"Error communicating with backend cluster logic code: {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("🔌 Network Connection Error: Backend server offline.")


# --- TAB 2: AUDIT LOGS SPREADSHEET SCRIPT ---
with tab2:
    st.header("📂 Portfolio Underwriting History & Audit Trail")
    st.markdown("Pull live system underwriting logs directly from the backend database registries.")
    
    if st.button("🔄 Refresh Audit Logs from Database", use_container_width=True):
        try:
            audit_endpoint = "https://onrender.com"
            response = requests.get(audit_endpoint)
            
            if response.status_code == 200:
                raw_logs = response.json().get("audit_trail", [])
                
                if raw_logs:
                    df = pd.DataFrame(raw_logs)
                    df_display = df[[
                        "id", "user_id", "national_id", "phone_number", 
                        "requested_amount", "crb_status", "computed_score", 
                        "decision", "decision_reason", "risk_flags", "created_at"
                    ]].copy()
                    
                    df_display.columns = [
                        "Log ID", "User ID", "National ID", "Phone Number", 
                        "Requested Amount (KES)", "CRB Status", "Risk Score", 
                        "Decision", "Reason Details", "Risk Flags Triggered", "Timestamp (UTC)"
                    ]
                    
                    total_apps = len(df_display)
                    approveds = len(df_display[df_display["Decision"] == "APPROVED"])
                    denieds = len(df_display[df_display["Decision"] == "DECLINED"])
                    
                    kpi1, kpi2, kpi3 = st.columns(3)
                    kpi1.metric("Total Decisions Tracked", total_apps)
                    kpi2.metric("Total Approvals", approveds, delta=f"{int((approveds/total_apps)*100)}%" if total_apps > 0 else "0%")
                    kpi3.metric("Total Declines", denieds, delta=f"{int((denieds/total_apps)*100)}%" if total_apps > 0 else "0%", delta_color="inverse")
                    
                    st.markdown("---")
                    st.subheader("📋 Live Audit Ledger View")
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                    
                    st.markdown("### 📥 Compliance Export Options")
                    csv_data = df_display.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="💾 Download Audit Trail Report (CSV Spreadsheet format)",
                        data=csv_data,
                        file_name=f"kenya_risk_ledger.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.info("The underlying logging schema table is currently empty.")
            else:
                st.error(f"Backend returned communication errors: {response.text}")
        except requests.exceptions.ConnectionError:
            st.error("🔌 Linkage Breakdown: Backend API offline.")


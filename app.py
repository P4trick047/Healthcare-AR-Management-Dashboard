import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import requests
import numpy as np  # For mock scoring

# --------------------------- CONFIG ---------------------------
st.set_page_config(page_title="Custom AR Management Tool", layout="wide")
st.title("🏥 Healthcare AR Management Dashboard")
st.markdown("Inspired by Thoughtful.ai: AI-Prioritized Collections & Denial Recovery")

# API Config (toggle for real NikoHealth integration)
API_KEY = st.secrets.get("NIKO_API_KEY", None)
USE_REAL_API = API_KEY is not None
API_BASE = "https://api.nikohealth.com"

# --------------------------- DATA FETCH (Mock + Real) ---------------------------
@st.cache_data(ttl=600, show_spinner="Loading AR data...")
def fetch_ar_data(start_date, end_date):
    if USE_REAL_API:
        # === REAL NIKOHEALTH INTEGRATION ===
        headers = {"Authorization": f"Bearer {API_KEY}"}
        params = {"start_date": start_date.strftime("%Y-%m-%d"), "end_date": end_date.strftime("%Y-%m-%d"), "limit": 1000}
        try:
            # Pull payments + adjustments for AR (customize endpoints as needed)
            response = requests.get(f"{API_BASE}/v2/payments", headers=headers, params=params, timeout=20)
            if response.status_code == 200:
                data = response.json().get("data", [])
                df = pd.DataFrame(data)
                df["aging_days"] = (pd.to_datetime("today") - pd.to_datetime(df["due_date"])).dt.days
                df["denial_risk"] = np.where(df["status"] == "denied", 1.0, np.random.uniform(0.1, 0.8))  # Placeholder; use real ML
                return df
            else:
                st.error(f"API Error: {response.status_code}")
                return pd.DataFrame()
        except Exception as e:
            st.error(f"Connection issue: {e}")
            return pd.DataFrame()
    else:
        # === MOCK DATA (Healthcare AR Sample) ===
        st.info("🧪 Demo Mode: Using sample healthcare data. Add NIKO_API_KEY to go live.")
        end_date_mock = datetime.now()
        start_date_mock = end_date_mock - timedelta(days=90)
        dates = pd.date_range(start=start_date_mock, end=end_date_mock, freq="D")
        mock_data = []
        payers = ["Medicare", "Blue Cross", "Aetna", "UnitedHealthcare"]
        reasons = ["CO-45: Charge exceeds fee", "PR-96: Non-covered", "CO-97: Duplicate", "CO-16: Missing info"]
        for i, date in enumerate(dates):
            mock_data.append({
                "invoice_id": f"INV-{i+1000}",
                "patient_id": f"PT-{np.random.randint(1000, 2000)}",
                "payer_name": np.random.choice(payers),
                "amount_due": np.random.uniform(100, 2000),
                "amount_paid": np.random.uniform(0, 1) * np.random.uniform(100, 2000),  # Partial payments
                "status": np.random.choice(["open", "partial", "denied", "paid"], p=[0.4, 0.2, 0.3, 0.1]),
                "due_date": date,
                "last_followup": date - timedelta(days=np.random.randint(0, 30)),
                "denial_reason": np.random.choice(reasons) if np.random.rand() > 0.7 else None,
                "notes": "Follow-up pending" if np.random.rand() > 0.6 else ""
            })
        df = pd.DataFrame(mock_data)
        df["aging_days"] = (pd.to_datetime("today") - pd.to_datetime(df["due_date"])).dt.days
        df["outstanding"] = df["amount_due"] - df["amount_paid"]
        df["priority_score"] = calculate_priority(df)  # AI-like scoring
        return df

def calculate_priority(df):
    """Mock AI Prioritization: Score 0-1 based on aging, risk, payer"""
    # Inspired by Thoughtful.ai: High aging + denial risk = high priority
    payer_risk = {"Medicare": 0.2, "Blue Cross": 0.4, "Aetna": 0.6, "UnitedHealthcare": 0.5}
    df["payer_risk"] = df["payer_name"].map(payer_risk).fillna(0.3)
    risk = np.where(df["status"] == "denied", 1.0, 0.5)  # Boost denials
    score = (df["aging_days"] / 90) * 0.4 + df["payer_risk"] * 0.3 + risk * 0.3
    return np.clip(score, 0, 1)

# --------------------------- UI: Filters & Load ---------------------------
st.sidebar.header("Filters")
col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=90))
end_date = col2.date_input("End Date", datetime.now())
min_priority = st.sidebar.slider("Min Priority Score", 0.0, 1.0, 0.3)

df = fetch_ar_data(start_date, end_date)
if df.empty:
    st.warning("No data in range. Adjust filters.")
    st.stop()

df = df[df["priority_score"] >= min_priority].copy()
df = df[df["outstanding"] > 0]  # Focus on open AR

# --------------------------- KEY METRICS (Thoughtful.ai-Style) ---------------------------
col1, col2, col3, col4 = st.columns(4)
total_ar = df["outstanding"].sum()
total_accounts = len(df)
avg_dso = df["aging_days"].mean()  # Days Sales Outstanding proxy
recovery_potential = (df["outstanding"] * 0.8).sum()  # Assume 80% recoverable

with col1:
    st.metric("Total AR", f"${total_ar:,.0f}")
with col2:
    st.metric("Open Accounts", f"{total_accounts:,}")
with col3:
    st.metric("Avg DSO (Days)", f"{avg_dso:.1f}")
with col4:
    st.metric("Recovery Potential", f"${recovery_potential:,.0f}")

st.markdown("---")

# --------------------------- PRIORITIZED ACCOUNTS TABLE ---------------------------
st.subheader("🔥 High-Priority Accounts (AI-Scored)")
priority_df = df.sort_values("priority_score", ascending=False).head(10).copy()
priority_df["priority_score"] = (priority_df["priority_score"] * 100).round(0).astype(int)
priority_df["aging_bucket"] = pd.cut(priority_df["aging_days"], bins=[0, 30, 60, 90, np.inf], labels=["0-30", "31-60", "61-90", "90+"])
priority_df["next_action"] = np.where(priority_df["aging_days"] > 60, "Escalate to Collector", "Auto-Followup Email")

display_cols = ["invoice_id", "patient_id", "payer_name", "outstanding", "aging_days", "priority_score", "next_action", "denial_reason"]
st.dataframe(priority_df[display_cols], use_container_width=True, hide_index=True)

# --------------------------- CHARTS: Trends & Insights ---------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("AR Aging Breakdown")
    aging_pivot = df.groupby("aging_bucket")["outstanding"].sum().reset_index()
    aging_chart = alt.Chart(aging_pivot).mark_bar(color="#FF6B6B").encode(
        x="aging_bucket:N",
        y="outstanding:Q"
    ).properties(height=250)
    st.altair_chart(aging_chart, use_container_width=True)

with col2:
    st.subheader("Priority Distribution")
    prio_bins = pd.cut(df["priority_score"], bins=3, labels=["Low", "Med", "High"])
    prio_count = df.groupby(prio_bins).size().reset_index(name="count")
    prio_chart = alt.Chart(prio_count).mark_bar(color="#4ECDC4").encode(
        x="prio_bins:N",
        y="count:Q"
    ).properties(height=250)
    st.altair_chart(prio_chart, use_container_width=True)

# Predictive Alerts (Mock Thoughtful.ai Intelligence)
st.subheader("🚨 Predictive Alerts")
high_risk = df[(df["priority_score"] > 0.7) & (df["aging_days"] > 45)]
if not high_risk.empty:
    for _, row in high_risk.head(5).iterrows():
        with st.expander(f"Alert: {row['payer_name']} - {row['invoice_id']} (Risk: {row['priority_score']:.2f})"):
            st.write(f"**Outstanding**: ${row['outstanding']:.0f} | **Aging**: {row['aging_days']} days")
            st.write(f"**Recommended**: Send portal check + email. Denial Risk: {row.get('denial_reason', 'Low')}")
            if st.button("Log Follow-up", key=f"log_{row['invoice_id']}"):
                st.success("Follow-up logged!")
else:
    st.success("No high-risk alerts today.")

# --------------------------- EXPORT & NOTES ---------------------------
st.subheader("Actions")
col1, col2 = st.columns(2)
with col1:
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Export AR CSV", csv, "ar_report.csv", "text/csv")
with col2:
    st.text_area("Add Global Notes", key="global_notes", height=100)

if not USE_REAL_API:
    st.sidebar.info("""
    **Go Live with NikoHealth**:
    1. Get API key from support@nikohealth.com
    2. Add to `.streamlit/secrets.toml`: `NIKO_API_KEY = "your_key"`
    3. Customize `fetch_ar_data` for endpoints like `/v2/payments` & `/v1/tasks`
    """)

# Footer Metrics (Thoughtful.ai Claims Simulation)
st.markdown("---")
st.caption(f"Simulated Impact: ~40% faster collections | 10x follow-ups | Track real metrics as data grows.")

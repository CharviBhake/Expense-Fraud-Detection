

import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px

CONN_PARAMS = dict(
    host="localhost",
    port=5432,
    dbname="expense_fraud",
    user="admin",
    password="admin123",
)

st.set_page_config(page_title="Expense Fraud Review Dashboard", layout="wide")

@st.cache_data(ttl=300)
def load_all_data():
    conn = psycopg2.connect(**CONN_PARAMS)

    expenses = pd.read_sql("""
        SELECT e.*, emp.name AS employee_name, emp.department, v.vendor_name
        FROM expenses e
        JOIN employees emp ON e.employee_id = emp.employee_id
        JOIN vendors v ON e.vendor_id = v.vendor_id
    """, conn, parse_dates=["submission_date", "expense_date"])

    rule_flags = pd.read_sql("""
        SELECT expense_id, STRING_AGG(rule_name, ', ') AS rules_triggered, COUNT(*) AS rule_count
        FROM rule_based_flags GROUP BY expense_id
    """, conn)

    ml_scores = pd.read_sql("SELECT expense_id, ml_anomaly_score, ml_anomaly_flag FROM ml_anomaly_scores", conn)
    explanations = pd.read_sql("SELECT expense_id, top_reasons FROM expense_explanations", conn)
    conn.close()

    df = expenses.merge(rule_flags, on="expense_id", how="left")
    df = df.merge(ml_scores, on="expense_id", how="left")
    df = df.merge(explanations, on="expense_id", how="left")

    df["rule_count"] = df["rule_count"].fillna(0).astype(int)
    df["ml_anomaly_flag"] = df["ml_anomaly_flag"].fillna(0).astype(int)
    df["is_flagged"] = (df["rule_count"] > 0) | (df["ml_anomaly_flag"] == 1)
    df["risk_signals"] = df["rule_count"] + df["ml_anomaly_flag"]
    return df


df = load_all_data()
flagged = df[df["is_flagged"]]

st.title("Corporate Expense Fraud Review Dashboard")
st.caption("Rule-based checks + ML anomaly detection + SHAP-based explanations, on synthetic expense data.")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview", "Flagged Expenses", "Vendor Concentration", "Submission Patterns", "Employee Risk Ranking"
])

with tab1:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Expenses", f"{len(df):,}")
    col2.metric("Flagged Expenses", f"{len(flagged):,}", f"{len(flagged)/len(df)*100:.1f}% of total")
    col3.metric("Flagged Value", f"₹{flagged['amount'].sum():,.0f}")
    col4.metric("High-Confidence (2+ signals)", f"{(df['risk_signals'] >= 2).sum():,}")

    st.subheader("Flag Rate by Department")
    dept_summary = df.groupby("department").agg(
        total=("expense_id", "count"),
        flagged=("is_flagged", "sum"),
    ).reset_index()
    dept_summary["flag_rate_pct"] = (dept_summary["flagged"] / dept_summary["total"] * 100).round(1)
    fig = px.bar(dept_summary.sort_values("flag_rate_pct", ascending=False),
                 x="department", y="flag_rate_pct", title="Flag Rate % by Department",
                 labels={"flag_rate_pct": "Flag Rate (%)"})
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Flags by Detection Method")
    method_counts = pd.DataFrame({
        "Method": ["Rules Only", "ML Only", "Both"],
        "Count": [
            ((df["rule_count"] > 0) & (df["ml_anomaly_flag"] == 0)).sum(),
            ((df["rule_count"] == 0) & (df["ml_anomaly_flag"] == 1)).sum(),
            ((df["rule_count"] > 0) & (df["ml_anomaly_flag"] == 1)).sum(),
        ]
    })
    fig2 = px.pie(method_counts, names="Method", values="Count", title="How flagged expenses were caught")
    st.plotly_chart(fig2, use_container_width=True)

with tab2:
    st.subheader("Flagged Expenses — Sortable & Filterable")

    col1, col2, col3 = st.columns(3)
    dept_filter = col1.multiselect("Department", options=sorted(df["department"].unique()))
    min_signals = col2.slider("Minimum risk signals", 1, int(df["risk_signals"].max()), 1)
    sort_by = col3.selectbox("Sort by", ["risk_signals", "amount", "submission_date"], index=0)

    view = flagged.copy()
    if dept_filter:
        view = view[view["department"].isin(dept_filter)]
    view = view[view["risk_signals"] >= min_signals]
    view = view.sort_values(sort_by, ascending=False)

    display_cols = ["expense_id", "employee_name", "department", "vendor_name", "category",
                     "amount", "expense_date", "rules_triggered", "ml_anomaly_flag",
                     "risk_signals", "top_reasons"]
    st.dataframe(view[display_cols], use_container_width=True, height=500)
    st.caption(f"Showing {len(view)} of {len(flagged)} flagged expenses")

with tab3:
    st.subheader("Vendor Dependency by Employee")
    st.caption("Employees whose spend with a single vendor makes up a large share of their total spend.")

    vendor_spend = df.groupby(["employee_name", "vendor_name"])["amount"].sum().reset_index()
    emp_total = df.groupby("employee_name")["amount"].sum().reset_index().rename(columns={"amount": "total"})
    vendor_spend = vendor_spend.merge(emp_total, on="employee_name")
    vendor_spend["pct_of_employee_spend"] = (vendor_spend["amount"] / vendor_spend["total"] * 100).round(1)
    top_concentration = vendor_spend[vendor_spend["pct_of_employee_spend"] > 15].sort_values(
        "pct_of_employee_spend", ascending=False
    ).head(20)

    fig3 = px.bar(top_concentration, x="pct_of_employee_spend", y="employee_name", color="vendor_name",
                  orientation="h", title="Top Employee-Vendor Concentration (>15% of employee spend)")
    st.plotly_chart(fig3, use_container_width=True)

with tab4:
    st.subheader("Submission Timing Patterns")

    df["is_weekend"] = df["expense_date"].dt.dayofweek.isin([5, 6])
    weekly = df.groupby([df["expense_date"].dt.to_period("W").astype(str), "is_weekend"]).size().reset_index(name="count")
    weekly.columns = ["week", "is_weekend", "count"]
    fig4 = px.line(weekly, x="week", y="count", color="is_weekend", title="Expense Submissions Over Time (Weekday vs Weekend)")
    st.plotly_chart(fig4, use_container_width=True)

    st.subheader("Weekend Submission Rate by Employee (Top 15)")
    emp_weekend = df.groupby("employee_name").agg(
        total=("expense_id", "count"),
        weekend_count=("is_weekend", "sum"),
    ).reset_index()
    emp_weekend["weekend_rate_pct"] = (emp_weekend["weekend_count"] / emp_weekend["total"] * 100).round(1)
    emp_weekend = emp_weekend[emp_weekend["total"] >= 5].sort_values("weekend_rate_pct", ascending=False).head(15)
    fig5 = px.bar(emp_weekend, x="weekend_rate_pct", y="employee_name", orientation="h",
                  title="Weekend Submission Rate % (Top 15 employees)")
    st.plotly_chart(fig5, use_container_width=True)

with tab5:
    st.subheader("Expenses Requiring Review, by Employee")
    st.caption("Ranked by flagged expense count and value. This identifies expenses that need review -- not a determination of wrongdoing.")

    emp_risk = df.groupby(["employee_name", "department"]).agg(
        total_expenses=("expense_id", "count"),
        flagged_expenses=("is_flagged", "sum"),
        flagged_value=("amount", lambda x: x[df.loc[x.index, "is_flagged"]].sum()),
    ).reset_index()
    emp_risk = emp_risk[emp_risk["flagged_expenses"] > 0].sort_values("flagged_expenses", ascending=False).head(20)
    fig6 = px.bar(emp_risk, x="flagged_expenses", y="employee_name", color="department",
                  orientation="h", title="Employees by Flagged Expense Count (Top 20)")
    st.plotly_chart(fig6, use_container_width=True)

    st.dataframe(emp_risk, use_container_width=True)

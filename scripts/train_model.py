

import psycopg2
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from psycopg2.extras import execute_values

CONN_PARAMS = dict(
    host="localhost",
    port=5432,
    dbname="expense_fraud",
    user="admin",
    password="admin123",
)


def load_data(conn):
    query = """
        SELECT expense_id, employee_id, vendor_id, amount, category,submission_date, expense_date, receipt_attached, is_fraud_injected
        FROM expenses
    """
    df = pd.read_sql(query, conn, parse_dates=["submission_date", "expense_date"])
    return df

def engineer_features(df):
   
    df=df.copy()
    emp_cat_avg=df.groupby(["employee_id", "category"])["amount"].transform("mean")
    emp_cat_std=df.groupby(["employee_id", "category"])["amount"].transform("std").fillna(1)
    df["amount_zscore_own_avg"]=(df["amount"] - emp_cat_avg) / emp_cat_std.replace(0, 1)

    df["submission_delay_days"]=(
        df["submission_date"]-df["expense_date"]
    ).dt.total_seconds() /86400

    vendor_freq=df.groupby(["employee_id", "vendor_id"])["expense_id"].transform("count")
    emp_total=df.groupby("employee_id")["expense_id"].transform("count")
    df["vendor_freq_share"]=vendor_freq /emp_total

    df["is_weekend"]=df["expense_date"].dt.dayofweek.isin([5, 6]).astype(int)
    df["receipt_missing"]=(~df["receipt_attached"]).astype(int)

    cat_dummies=pd.get_dummies(df["category"], prefix="cat")

    feature_cols=[
        "amount", "amount_zscore_own_avg", "submission_delay_days",
        "vendor_freq_share", "is_weekend", "receipt_missing",
    ]
    X=pd.concat([df[feature_cols], cat_dummies], axis=1).fillna(0)
    return X, df


def main():
    conn = psycopg2.connect(**CONN_PARAMS)

    print("Loading expenses...")
    df = load_data(conn)
    print(f"Loaded {len(df)} expenses.")

    print("Engineering features...")
    X, df = engineer_features(df)
    print(f"Feature matrix shape: {X.shape}")

    print("Training Isolation Forest...")
    model=IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
    predictions=model.fit_predict(X)  
    scores=-model.score_samples(X)    
    df["ml_anomaly_flag"]=(predictions == -1).astype(int)
    df["ml_anomaly_score"]=scores
    cur=conn.cursor()
    cur.execute("DROP TABLE IF EXISTS ml_anomaly_scores")
    cur.execute("""
        CREATE TABLE ml_anomaly_scores (
            expense_id INT REFERENCES expenses(expense_id),
            ml_anomaly_score NUMERIC,
            ml_anomaly_flag INT
        )
    """)
    records=list(df[["expense_id", "ml_anomaly_score", "ml_anomaly_flag"]].itertuples(index=False, name=None))
    execute_values(cur, "INSERT INTO ml_anomaly_scores (expense_id, ml_anomaly_score, ml_anomaly_flag) VALUES %s", records)
    conn.commit()
    print(f"\nWrote {len(records)} rows to ml_anomaly_scores.")

    rule_flags=pd.read_sql("SELECT DISTINCT expense_id FROM rule_based_flags", conn)
    rule_flagged_ids=set(rule_flags["expense_id"])
    ml_flagged_ids=set(df[df["ml_anomaly_flag"] == 1]["expense_id"])

    both=rule_flagged_ids & ml_flagged_ids
    rule_only=rule_flagged_ids - ml_flagged_ids
    ml_only=ml_flagged_ids - rule_flagged_ids
    combined=rule_flagged_ids|ml_flagged_ids

    print(f"\nRule-flagged: {len(rule_flagged_ids)}")
    print(f"ML-flagged: {len(ml_flagged_ids)}")
    print(f"Flagged by both: {len(both)}")
    print(f"Rule-only (ML missed): {len(rule_only)}")
    print(f"ML-only (rules missed): {len(ml_only)}")
    print(f"Combined unique coverage: {len(combined)}")

    df["is_fraud"]=(df["is_fraud_injected"] != "none").astype(int)
    fraud_ids=set(df[df["is_fraud"]==1]["expense_id"])

    def precision_recall(flagged_ids, name):
        if len(flagged_ids) == 0:
            print(f"{name}: no flags to evaluate")
            return
        tp=len(flagged_ids & fraud_ids)
        precision=tp /len(flagged_ids)
        recall=tp /len(fraud_ids)
        print(f"{name:25s} | flagged: {len(flagged_ids):5d} | precision: {precision:.3f} | recall: {recall:.3f}")

    print("\n--- Precision / Recall vs. ground truth ---")
    precision_recall(rule_flagged_ids, "Rules only")
    precision_recall(ml_flagged_ids, "ML only")
    precision_recall(combined, "Combined (rules + ML)")

    print("\n--- Which fraud patterns does each method catch? ---")
    df["rule_flagged"]=df["expense_id"].isin(rule_flagged_ids)
    df["ml_flagged"]=df["expense_id"].isin(ml_flagged_ids)
    pattern_breakdown=df[df["is_fraud"] == 1].groupby("is_fraud_injected").agg(
        total=("expense_id", "count"),
        caught_by_rules=("rule_flagged", "sum"),
        caught_by_ml=("ml_flagged", "sum"),
    )
    pattern_breakdown["caught_by_either"] = df[df["is_fraud"] == 1].groupby("is_fraud_injected").apply(
        lambda g: (g["rule_flagged"] | g["ml_flagged"]).sum()
    )
    print(pattern_breakdown)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()


import psycopg2
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from psycopg2.extras import execute_values
import shap

CONN_PARAMS =dict(
    host="localhost",
    port=5432,
    dbname="expense_fraud",
    user="admin",
    password="admin123",
)

READABLE_FEATURES={
    "amount": "unusually high amount",
    "amount_zscore_own_avg": "amount far above employee's own category average",
    "submission_delay_days": "unusual delay between spend and submission",
    "vendor_freq_share": "high concentration of spend with a single vendor",
    "is_weekend": "submitted on a weekend",
    "receipt_missing": "missing receipt",
}

def load_data(conn):
    query = """
        SELECT expense_id, employee_id, vendor_id, amount, category,
     submission_date, expense_date, receipt_attached
        FROM expenses
    """
    return pd.read_sql(query, conn, parse_dates=["submission_date", "expense_date"])

def engineer_features(df):
    df = df.copy()
    emp_cat_avg=df.groupby(["employee_id", "category"])["amount"].transform("mean")
    emp_cat_std= df.groupby(["employee_id", "category"])["amount"].transform("std").fillna(1)
    df["amount_zscore_own_avg"]= (df["amount"] - emp_cat_avg)/emp_cat_std.replace(0,1)
    df["submission_delay_days"]= (df["submission_date"] - df["expense_date"]).dt.total_seconds() /86400
    vendor_freq= df.groupby(["employee_id", "vendor_id"])["expense_id"].transform("count")
    emp_total= df.groupby("employee_id")["expense_id"].transform("count")
    df["vendor_freq_share"] = vendor_freq / emp_total
    df["is_weekend"]= df["expense_date"].dt.dayofweek.isin([5,6]).astype(int)
    df["receipt_missing"]= (~df["receipt_attached"]).astype(int)
    cat_dummies= pd.get_dummies(df["category"], prefix="cat")

    feature_cols=[
        "amount", "amount_zscore_own_avg", "submission_delay_days",
        "vendor_freq_share", "is_weekend", "receipt_missing",
    ]
    X=pd.concat([df[feature_cols], cat_dummies], axis=1).fillna(0)
    return X, df


def top_reasons(shap_row, feature_names, n=3):
    pairs=[(f, v) for f, v in zip(feature_names, shap_row) if not f.startswith("cat_")]
    pairs.sort(key=lambda x: x[1])
    top=pairs[:n]
    return [READABLE_FEATURES.get(f, f) for f, v in top]


def main():
    conn=psycopg2.connect(**CONN_PARAMS)
    print("Loading data + engineering features...")
    df=load_data(conn)
    X, df = engineer_features(df)

    print("Training Isolation Forest...")
    model=IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
    predictions = model.fit_predict(X)
    df["ml_anomaly_flag"] = (predictions==-1).astype(int)

    flagged_idx = df[df["ml_anomaly_flag"]==1].index
    print(f"Explaining {len(flagged_idx)} flagged expenses...")

    print("Computing SHAP values (this can take a minute)...")
    explainer=shap.TreeExplainer(model)
    shap_values=explainer.shap_values(X.loc[flagged_idx])

    explanations=[]
    for i,idx in enumerate(flagged_idx):
        reasons= top_reasons(shap_values[i], X.columns.tolist())
        reason_str = "; ".join(reasons)
        explanations.append((int(df.loc[idx, "expense_id"]), reason_str))

    cur=conn.cursor()
    cur.execute("DROP TABLE IF EXISTS expense_explanations")
    cur.execute("""
        CREATE TABLE expense_explanations (
            expense_id INT REFERENCES expenses(expense_id),
            top_reasons TEXT
        )
    """)
    execute_values(cur, "INSERT INTO expense_explanations (expense_id, top_reasons) VALUES %s", explanations)
    conn.commit()
    print(f"\nWrote {len(explanations)} explanations to expense_explanations.")

    print("\nSample explanations:")
    for eid,reason in explanations[:10]:
        print(f" Expense {eid}: {reason}")

    print("\nGlobal feature importance (mean |SHAP value| across flagged expenses):")
    mean_abs_shap=np.abs(shap_values).mean(axis=0)
    importance=sorted(zip(X.columns.tolist(), mean_abs_shap), key=lambda x: -x[1])
    for feat,val in importance[:8]:
        label=READABLE_FEATURES.get(feat, feat)
        print(f" {label:55s} {val:.4f}")

    cur.close()
    conn.close()



if __name__ == "__main__":
    main()

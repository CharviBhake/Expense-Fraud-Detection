import psycopg2
import pandas as pd
from psycopg2.extras import execute_values

CONN_PARAMS = dict(
    host="localhost",
    port=5432,
    dbname="expense_fraud",
    user="admin",
    password="admin123",
)

def load_table(cur, df, table, columns):
    sub=df[columns].astype(object)
    records=sub.where(pd.notnull(sub), None).values.tolist()
    cols_str= ", ".join(columns)
    query=f"INSERT INTO {table} ({cols_str}) VALUES %s ON CONFLICT DO NOTHING"
    execute_values(cur, query, records)

def main():
    emp_df=pd.read_csv("data/employees.csv")
    vendor_df=pd.read_csv("data/vendors.csv")
    exp_df=pd.read_csv("data/expenses.csv")
    emp_df["manager_id"]=emp_df["manager_id"].astype("Int64")
    exp_df["approved_by"]=exp_df["approved_by"].astype("Int64")

    conn=psycopg2.connect(**CONN_PARAMS)
    cur=conn.cursor()
    load_table(cur,emp_df, "employees",["employee_id", "name", "department", "role", "manager_id", "join_date"])
    load_table(cur, vendor_df, "vendors",["vendor_id", "vendor_name", "category"])
    load_table(cur,exp_df, "expenses",
               ["expense_id","employee_id", "vendor_id","amount", "category",
                "submission_date", "expense_date","approved_by","approval_status",
                "receipt_attached","description", "is_fraud_injected"])

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM expenses")
    print(f"Loaded. expenses row count in DB: {cur.fetchone()[0]}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
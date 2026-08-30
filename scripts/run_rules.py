"""
Runs all 7 rule-based fraud detection queries against the database and
writes a consolidated `rule_based_flags` table: one row per (expense_id, rule)
that tripped. An expense can appear multiple times if it trips multiple rules --
that's a useful signal in itself (multi-rule hits are higher risk).

Usage:
    python3 scripts/run_rules.py

Requires: schema.sql + load_data.py already run.
"""

import psycopg2
import pandas as pd
from pathlib import Path

CONN_PARAMS = dict(
    host="localhost",
    port=5432,
    dbname="expense_fraud",
    user="admin",
    password="admin123",
)

SQL_DIR = Path(__file__).parent.parent / "sql"

# Each rule query returns a different shape (some flag single expense_ids,
# some flag pairs, some flag employee-level groups). We normalize all of them
# down to (expense_id, rule_name) rows for the summary table.
RULES = [
    {
        "name": "duplicate",
        "file": "01_duplicate_expenses.sql",
        # this query returns pairs -- both expense_id_1 and expense_id_2 get flagged
        "id_columns": ["expense_id_1", "expense_id_2"],
    },
    {
        "name": "round_number",
        "file": "02_round_number_bias.sql",
        "id_columns": ["expense_id"],
    },
    {
        "name": "threshold_skirting",
        "file": "03_threshold_skirting.sql",
        "id_columns": ["expense_id"],
    },
    {
        "name": "missing_receipt_high_amount",
        "file": "06_missing_receipt_high_amount.sql",
        "id_columns": ["expense_id"],
    },
]

# Rules 4, 5, 7 flag at the employee or group level, not a single expense_id
# column directly -- handled separately below since they need a join back to
# expenses to get individual expense_ids.
EMPLOYEE_LEVEL_RULES = ["04_weekend_submission_spikes.sql", "05_vendor_concentration.sql"]
GROUP_LEVEL_RULES = ["07_split_transactions.sql"]


def run_query_file(cur, filename):
    sql = (SQL_DIR / filename).read_text()
    cur.execute(sql)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


def main():
    conn = psycopg2.connect(**CONN_PARAMS)
    cur = conn.cursor()

    all_flags = []  # list of (expense_id, rule_name)

    # --- Simple expense_id-level rules ---
    for rule in RULES:
        df = run_query_file(cur, rule["file"])
        for col in rule["id_columns"]:
            for eid in df[col].dropna().unique():
                all_flags.append((int(eid), rule["name"]))
        print(f"{rule['name']}: {len(df)} rows returned")

    # --- Rule 4: weekend spikes (employee-level -> expand to their weekend expenses) ---
    df4 = run_query_file(cur, "04_weekend_submission_spikes.sql")
    if len(df4) > 0:
        flagged_employees = tuple(int(e) for e in df4["employee_id"].unique())
        cur.execute(
            """SELECT expense_id FROM expenses
               WHERE employee_id IN %s AND EXTRACT(DOW FROM expense_date) IN (0, 6)""",
            (flagged_employees,),
        )
        for (eid,) in cur.fetchall():
            all_flags.append((eid, "weekend_spike"))
    print(f"weekend_spike: {len(df4)} employees flagged")

    # --- Rule 5: vendor concentration (employee+vendor level -> expand to those expenses) ---
    df5 = run_query_file(cur, "05_vendor_concentration.sql")
    for _, row in df5.iterrows():
        cur.execute(
            """SELECT expense_id FROM expenses WHERE employee_id = %s AND vendor_id = %s""",
            (int(row["employee_id"]), int(row["vendor_id"])),
        )
        for (eid,) in cur.fetchall():
            all_flags.append((eid, "vendor_concentration"))
    print(f"vendor_concentration: {len(df5)} employee-vendor pairs flagged")

    # --- Rule 7: split transactions (group level -> expand expense_ids array) ---
    df7 = run_query_file(cur, "07_split_transactions.sql")
    for _, row in df7.iterrows():
        ids = row["expense_ids"]
        # psycopg2 returns Postgres arrays as native Python lists already
        for eid in ids:
            all_flags.append((int(eid), "split_transaction"))
    print(f"split_transaction: {len(df7)} groups flagged")

    # --- Consolidate + write to DB ---
    flags_df = pd.DataFrame(all_flags, columns=["expense_id", "rule_name"]).drop_duplicates()

    cur.execute("DROP TABLE IF EXISTS rule_based_flags")
    cur.execute("""
        CREATE TABLE rule_based_flags (
            expense_id INT REFERENCES expenses(expense_id),
            rule_name VARCHAR(50)
        )
    """)
    records = list(flags_df.itertuples(index=False, name=None))
    from psycopg2.extras import execute_values
    execute_values(cur, "INSERT INTO rule_based_flags (expense_id, rule_name) VALUES %s", records)
    conn.commit()

    print(f"\nTotal (expense_id, rule) flag rows: {len(flags_df)}")
    print(f"Unique expenses flagged by at least one rule: {flags_df['expense_id'].nunique()}")
    print("\nFlags per rule:")
    print(flags_df["rule_name"].value_counts())

    # multi-rule hits -- these are your highest-confidence flags
    multi = flags_df.groupby("expense_id").size()
    multi_hits = multi[multi > 1]
    print(f"\nExpenses flagged by 2+ rules (highest risk): {len(multi_hits)}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

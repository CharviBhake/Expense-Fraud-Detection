-- Rule 5: Vendor Concentration Risk
-- Flags employee-vendor pairs where one vendor accounts for an unusually
-- large share of that employee's total spend -- a common kickback/collusion signature.
-- Threshold set at 20% (not a higher number like 40%) because each employee spreads
-- spend across ~15-20 vendors here, so even a genuinely concentrated kickback
-- relationship dilutes to a moderate share of total spend, not a dominant one.

WITH employee_vendor_spend AS (
    SELECT
        employee_id,
        vendor_id,
        SUM(amount) AS vendor_total,
        COUNT(*) AS vendor_txn_count
    FROM expenses
    GROUP BY employee_id, vendor_id
),
employee_total_spend AS (
    SELECT
        employee_id,
        SUM(amount) AS total_spend
    FROM expenses
    GROUP BY employee_id
)
SELECT
    evs.employee_id,
    evs.vendor_id,
    v.vendor_name,
    evs.vendor_total,
    evs.vendor_txn_count,
    ets.total_spend,
    ROUND((evs.vendor_total / ets.total_spend) * 100, 1) AS pct_of_employee_spend
FROM employee_vendor_spend evs
JOIN employee_total_spend ets ON evs.employee_id = ets.employee_id
JOIN vendors v ON evs.vendor_id = v.vendor_id
WHERE ets.total_spend > 0
  AND (evs.vendor_total / ets.total_spend) > 0.20   -- one vendor = 20%+ of an employee's total spend
  AND evs.vendor_txn_count >= 3
ORDER BY pct_of_employee_spend DESC;

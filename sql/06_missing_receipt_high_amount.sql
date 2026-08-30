-- Rule 6: Missing Receipt on High-Value Expense
-- Flags expenses with no receipt attached where the amount is well above
-- that employee's typical spend in the same category -- unverifiable + unusual.

WITH employee_category_avg AS (
    SELECT
        employee_id,
        category,
        AVG(amount) AS avg_amount
    FROM expenses
    WHERE receipt_attached = TRUE   -- baseline off verified spend only
    GROUP BY employee_id, category
)
SELECT
    e.expense_id,
    e.employee_id,
    e.category,
    e.amount,
    eca.avg_amount AS employee_category_avg,
    ROUND((e.amount / NULLIF(eca.avg_amount, 0))::numeric, 2) AS times_above_own_avg,
    e.receipt_attached,
    e.submission_date
FROM expenses e
JOIN employee_category_avg eca
    ON e.employee_id = eca.employee_id AND e.category = eca.category
WHERE e.receipt_attached = FALSE
  AND e.amount > eca.avg_amount * 1.5
ORDER BY times_above_own_avg DESC;

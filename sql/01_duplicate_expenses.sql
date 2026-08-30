-- Rule 1: Duplicate / Ghost Expenses
-- Same employee, same amount, same vendor, submitted within a short window.
-- Classic double-claiming pattern.

SELECT
    e1.expense_id AS expense_id_1,
    e2.expense_id AS expense_id_2,
    e1.employee_id,
    e1.vendor_id,
    e1.amount,
    e1.submission_date AS submitted_1,
    e2.submission_date AS submitted_2,
    ABS(EXTRACT(EPOCH FROM (e2.submission_date - e1.submission_date)) / 86400) AS days_apart
FROM expenses e1
JOIN expenses e2
    ON e1.employee_id = e2.employee_id
    AND e1.vendor_id = e2.vendor_id
    AND e1.amount = e2.amount
    AND e1.expense_id < e2.expense_id
WHERE ABS(EXTRACT(EPOCH FROM (e2.submission_date - e1.submission_date)) / 86400) <= 10
ORDER BY e1.employee_id, e1.amount;

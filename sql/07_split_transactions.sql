-- Rule 7: Split Transactions
-- One large spend broken into 2-3 smaller claims, same employee, same category,
-- submitted close together, each individually under the approval threshold --
-- a classic "structuring" pattern to dodge sign-off.

WITH thresholds(category, threshold) AS (
    VALUES
        ('Travel', 15000),
        ('Meals & Entertainment', 5000),
        ('Software & Subscriptions', 20000),
        ('Office Supplies', 3000),
        ('Client Gifts', 8000),
        ('Accommodation', 12000),
        ('Ground Transport', 3000),
        ('Conference & Training', 25000),
        ('Miscellaneous', 5000)
),
candidate_groups AS (
    SELECT
        e.employee_id,
        e.category,
        e.expense_date,
        COUNT(*) AS txn_count,
        SUM(e.amount) AS combined_amount,
        ARRAY_AGG(e.expense_id ORDER BY e.expense_id) AS expense_ids
    FROM expenses e
    GROUP BY e.employee_id, e.category, e.expense_date
    HAVING COUNT(*) >= 2
)
SELECT
    cg.employee_id,
    cg.category,
    cg.expense_date,
    cg.txn_count,
    cg.combined_amount,
    t.threshold,
    cg.expense_ids
FROM candidate_groups cg
JOIN thresholds t ON cg.category = t.category
WHERE cg.combined_amount > t.threshold * 0.75   -- combined total looks like it was meant to clear the threshold
ORDER BY cg.combined_amount DESC;

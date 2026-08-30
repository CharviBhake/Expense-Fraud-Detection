-- Rule 3: Threshold-Skirting
-- Expenses submitted just under the category's approval threshold,
-- deliberately avoiding the extra sign-off step.

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
)
SELECT
    e.expense_id,
    e.employee_id,
    e.category,
    e.amount,
    t.threshold,
    ROUND((e.amount / t.threshold) * 100, 1) AS pct_of_threshold
FROM expenses e
JOIN thresholds t ON e.category = t.category
WHERE e.amount >= t.threshold * 0.95
  AND e.amount < t.threshold
ORDER BY pct_of_threshold DESC;

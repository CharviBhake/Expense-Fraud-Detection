-- Rule 4: Weekend / Off-Hours Submission Spikes
-- Flags employees whose weekend submission rate is a statistical outlier
-- relative to their peers (z-score > 1.0), rather than a fixed multiplier --
-- weekends are naturally ~28% of all days, so a flat "2x average" threshold
-- is too aggressive against that already-high baseline. Lower scrutiny days
-- are a common fraud window, but expect this rule alone to have limited
-- precision/recall -- it's one signal among several, not a standalone catch.
-- (This is also a good talking point: rule-based checks like this are exactly
-- why the ML layer in Day 3 earns its place -- it can combine this weak signal
-- with others the rules check separately.)

WITH employee_rates AS (
    SELECT
        employee_id,
        COUNT(*) AS total_expenses,
        SUM(CASE WHEN EXTRACT(DOW FROM expense_date) IN (0, 6) THEN 1 ELSE 0 END) AS weekend_count,
        AVG(CASE WHEN EXTRACT(DOW FROM expense_date) IN (0, 6) THEN 1 ELSE 0 END) AS weekend_rate
    FROM expenses
    GROUP BY employee_id
    HAVING COUNT(*) >= 5   -- ignore employees with too few expenses to be meaningful
),
stats AS (
    SELECT
        AVG(weekend_rate) AS mean_rate,
        STDDEV(weekend_rate) AS std_rate
    FROM employee_rates
)
SELECT
    er.employee_id,
    er.total_expenses,
    er.weekend_count,
    ROUND(er.weekend_rate::numeric, 3) AS weekend_rate,
    ROUND(s.mean_rate::numeric, 3) AS company_mean_rate,
    ROUND(((er.weekend_rate - s.mean_rate) / s.std_rate)::numeric, 2) AS z_score
FROM employee_rates er
CROSS JOIN stats s
WHERE (er.weekend_rate - s.mean_rate) / s.std_rate > 1.0   -- 1+ std dev above peers
ORDER BY z_score DESC;

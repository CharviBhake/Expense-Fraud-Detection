-- Rule 2: Round-Number Bias
-- Fabricated expense amounts cluster on suspiciously round numbers.
-- Real spend (taxi fares, meals, hotel bills) is rarely exactly round.

SELECT
    expense_id,
    employee_id,
    category,
    amount,
    submission_date
FROM expenses
WHERE amount IN (2000, 5000, 10000, 15000, 20000, 25000, 30000)
   OR (amount::numeric % 1000 = 0 AND amount >= 2000)
ORDER BY amount DESC;

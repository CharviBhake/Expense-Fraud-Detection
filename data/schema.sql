-- Corporate Expense Fraud Detection — Schema
-- Run this first, then load_data.py to populate from the CSVs.

DROP TABLE IF EXISTS expenses;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS vendors;

CREATE TABLE employees (
    employee_id   INT PRIMARY KEY,
    name          VARCHAR(100),
    department    VARCHAR(50),
    role          VARCHAR(50),
    manager_id    INT,
    join_date     DATE
);

CREATE TABLE vendors (
    vendor_id     INT PRIMARY KEY,
    vendor_name   VARCHAR(100),
    category      VARCHAR(50)
);

CREATE TABLE expenses (
    expense_id         INT PRIMARY KEY,
    employee_id        INT REFERENCES employees(employee_id),
    vendor_id           INT REFERENCES vendors(vendor_id),
    amount              NUMERIC(10,2),
    category            VARCHAR(50),
    submission_date     TIMESTAMP,
    expense_date        DATE,
    approved_by         INT,
    approval_status     VARCHAR(20),
    receipt_attached    BOOLEAN,
    description          TEXT,
    is_fraud_injected   VARCHAR(30)  -- GROUND TRUTH — drop/hide this column during your "blind" analysis,
                                     -- only use it at the end to score precision/recall
);

CREATE INDEX idx_expenses_employee ON expenses(employee_id);
CREATE INDEX idx_expenses_vendor ON expenses(vendor_id);
CREATE INDEX idx_expenses_date ON expenses(expense_date);

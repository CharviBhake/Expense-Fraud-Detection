# Data Dictionary — Corporate Expense Fraud Detection

## employees.csv
| Column | Type | Notes |
|---|---|---|
| employee_id | int | PK |
| name | text | synthetic |
| department | text | 9 departments (Sales, Engineering, Finance, etc.) |
| role | text | 7-level hierarchy: Analyst → VP |
| manager_id | int | nullable for top roles (Director/VP) |
| join_date | date | |

## vendors.csv
| Column | Type | Notes |
|---|---|---|
| vendor_id | int | PK |
| vendor_name | text | e.g. "Uber for Business", "AWS" |
| category | text | maps to one of 9 expense categories |

## expenses.csv
| Column | Type | Notes |
|---|---|---|
| expense_id | int | PK |
| employee_id | int | FK |
| vendor_id | int | FK |
| amount | numeric | INR |
| category | text | Travel, Meals & Entertainment, Software & Subscriptions, Office Supplies, Client Gifts, Accommodation, Ground Transport, Conference & Training, Miscellaneous |
| submission_date | timestamp | when the claim was filed |
| expense_date | date | when the spend actually happened |
| approved_by | int | manager_id, or self if no manager |
| approval_status | text | Approved / Pending / Rejected |
| receipt_attached | bool | |
| description | text | synthetic free text |
| **is_fraud_injected** | text | **GROUND TRUTH — hide this during analysis.** `none` if normal, otherwise the injected pattern name (see below). Use it only at the end to compute precision/recall. |

## Injected fraud patterns (~4.6% of ~9,100 rows)

| Pattern tag | Description | Why it's realistic |
|---|---|---|
| `duplicate` | Same employee, same amount + vendor, submitted twice a few days apart | Classic double-claiming |
| `round_number` | Suspiciously round amounts (₹5,000 / ₹10,000 / ₹20,000 etc.) | Fabricated numbers cluster on round values; real spend rarely does |
| `threshold_skirting` | Amount just under the category's approval threshold (96–99.9% of threshold) | Dodges the extra sign-off step |
| `weekend_spike` | Concentrated in a handful of repeat-offender employees, dated on weekends | Lower scrutiny days |
| `vendor_concentration` | Two employees repeatedly using one obscure vendor at inflated amounts | Kickback/collusion signature |
| `missing_receipt_high_amount` | No receipt attached + amount ~2x category average | High-value unverifiable claims |
| `split_transaction` | One spend broken into 2–3 smaller claims, each just under the approval threshold | Structuring to avoid approval |

## Approval thresholds by category (INR)
Travel 15,000 · Meals & Entertainment 5,000 · Software & Subscriptions 20,000 ·
Office Supplies 3,000 · Client Gifts 8,000 · Accommodation 12,000 ·
Ground Transport 3,000 · Conference & Training 25,000 · Miscellaneous 5,000

## Recommended workflow
1. Load into Postgres via `schema.sql` + `load_data.py`
2. Drop/ignore `is_fraud_injected` — do your rule-based + ML analysis blind
3. At the end, join back to `is_fraud_injected` to compute precision/recall per method
4. Report combined (rules + ML) recall honestly — this is your key finding

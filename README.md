# Corporate Expense Fraud and Anomaly Detection

A fraud detection pipeline for corporate expense claims. It generates a synthetic expense dataset with seven known fraud patterns hidden in it, stores it in PostgreSQL, flags suspicious claims with SQL rules and an Isolation Forest model, explains each model flag with SHAP, and shows the results in a Streamlit dashboard.

All data is synthetic. The results show that the method works on known patterns under controlled conditions. They do not show how it would perform on a real company's expense data (see [Limitations](#limitations)).

## Why this project

Real expense fraud data is confidential and rarely labelled, so detection methods are hard to compare. Here the fraud is injected, so the true labels are known. A hidden ground-truth column (`is_fraud_injected`) is used only at evaluation time and is never an input to the rules or the model. That makes it possible to report real precision and recall for each method.

## Results

| Method | Expenses flagged | Precision | Recall |
|---|---|---|---|
| SQL rules only | 1,164 | 33.4% | 92.0% |
| Isolation Forest only | 456 | 27.0% | 29.1% |
| Rules + Isolation Forest | 1,418 | 28.5% | 95.5% |

Of 9,108 expenses, 423 (4.6%) are injected fraud. 138 expenses were flagged by two or more rules, which gives a smaller, higher-confidence list.

Detection by fraud pattern:

| Pattern | Injected | Caught by rules | Caught by model | Caught by either |
|---|---|---|---|---|
| duplicate | 90 | 90 | 0 | 90 |
| round_number | 45 | 45 | 17 | 45 |
| threshold_skirting | 45 | 45 | 10 | 45 |
| split_transaction | 108 | 108 | 0 | 108 |
| vendor_concentration | 45 | 45 | 31 | 45 |
| missing_receipt_high_amount | 45 | 36 | 43 | 43 |
| weekend_spike | 45 | 20 | 22 | 28 |

What the numbers show:

- The rules do most of the work, since the fraud patterns are known patterns.
- The model catches fraud that the rules handle less well, such as missing receipts (43 of 45 versus 36 for the rules). Combining the two raises recall from 92.0% to 95.5%.
- The model scores zero on duplicates and split transactions. It scores one expense at a time, and those patterns only exist across several rows. This is why both layers are kept.
- Weekend spikes are weak for both methods. Weekends are about 28% of days anyway, so the injected signal is diluted.
- Precision is low on purpose. A screening step that over-flags is acceptable when a missed fraud costs more than a reviewer checking a clean claim.

## How it works

```
generate_data.py  ->  PostgreSQL  ->  run_rules.py      ->  rule_based_flags
 (synthetic data)    (Docker)         train_model.py    ->  ml_anomaly_scores
                                      explain_model.py  ->  expense_explanations
                                                |
                                       Streamlit dashboard
```

**Data.** 45 employees, 25 vendors and 9,108 expense claims (January 2024 to June 2025, in INR). Normal amounts are drawn from per-category distributions, and each category has an approval threshold. Seven fraud patterns are injected:

| Pattern | What it represents |
|---|---|
| duplicate | Same employee, vendor and amount claimed twice within days |
| round_number | Suspiciously round amounts such as 5,000 or 20,000 |
| threshold_skirting | Amount just under the category's approval threshold |
| split_transaction | One large spend split into claims that each stay under the threshold |
| vendor_concentration | Two employees repeatedly using one vendor at inflated amounts |
| missing_receipt_high_amount | No receipt and an amount far above normal |
| weekend_spike | Claims dated on weekends, concentrated in a few employees |

**Rule-based detection.** Seven SQL queries in `sql/`, one per pattern, each run by `run_rules.py`. Flags are stored in `rule_based_flags` with the rule name, and an expense can trip more than one rule.

**ML detection.** An Isolation Forest (200 trees, contamination 0.05) trained without labels on 15 columns: amount, distance from the employee's own category average, submission delay, the employee's share of spend with the vendor, weekend flag, missing-receipt flag, and a one-hot encoding of the nine categories. Contamination is the fraction of data the model is told to treat as anomalous. It sets where the cutoff falls and does not change the scores.

**Explainability.** SHAP's `TreeExplainer` finds which features pushed each flagged expense toward anomalous. The top three behavioural features become a plain-language reason (for example: "missing receipt; unusually high amount"), stored in `expense_explanations`.

**Dashboard.** Five tabs: overview, flagged expenses (sortable and filterable, with the reason beside each row), vendor concentration, submission patterns, and employee risk ranking. The ranking shows expenses needing review, not a judgement about any person.

<!-- Add screenshots after you take them, then remove this comment:
![Overview](docs/screenshots/overview.png)
![Flagged expenses](docs/screenshots/flagged.png)
-->

## Tech stack

Python, pandas, NumPy, Faker, PostgreSQL 16, Docker Compose, psycopg2, scikit-learn, SHAP, Streamlit, Plotly, openpyxl.

## Project structure

```
.
├── dashboard/
│   └── app.py                    # Streamlit dashboard
├── data/                         # generated CSVs (git-ignored) and data_dictionary.md
├── scripts/
│   ├── generate_data.py          # synthetic data + fraud injection
│   ├── load_data.py              # CSVs -> PostgreSQL
│   ├── run_rules.py              # runs the SQL rules, writes rule_based_flags
│   ├── train_model.py            # Isolation Forest, evaluation vs ground truth
│   ├── explain_model.py          # SHAP explanations
│   └── export_for_powerbi.py     # optional Excel export for BI tools
├── sql/                          # 7 rule queries (01 to 07)
├── docker-compose.yml
├── schema.sql
└── requirements.txt
```

## Getting started

Requirements: Python 3.9 or newer, and Docker. Run all commands from the project root.

```bash
# 1. Python environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Start PostgreSQL in Docker
docker-compose up -d

# 3. Generate the dataset (writes data/*.csv)
python3 scripts/generate_data.py

# 4. Create the tables
docker exec -i $(docker ps -qf "name=db") psql -U admin -d expense_fraud < schema.sql

# 5. Load the data
python3 scripts/load_data.py

# 6. Run detection
python3 scripts/run_rules.py
python3 scripts/train_model.py
python3 scripts/explain_model.py

# 7. Open the dashboard
streamlit run dashboard/app.py
```

`train_model.py` prints the precision and recall table and the per-pattern breakdown shown above.

Optional: `python3 scripts/export_for_powerbi.py` writes `powerbi_export.xlsx` with the joined results and summary sheets.

The database credentials (`admin` / `admin123`) are for local development only.

### Re-running from scratch

The dashboard reads saved results, so after changing the data you need to re-run steps 5 and 6. To reset the database completely:

```bash
docker-compose down -v
docker-compose up -d
```

then repeat steps 4 to 6.

### Troubleshooting

- **`role "admin" does not exist`**: another PostgreSQL is already using port 5432 on your machine (for example a Homebrew install), so Python is connecting to that one and not to the container. Stop the local one (`brew services stop postgresql@16`) or change the port mapping in `docker-compose.yml` and in the scripts.
- **Docker commands hang or fail on macOS**: check that Docker Desktop is running and not paused.

## Limitations

- The data is synthetic. Real expense data is noisier, has unknown fraud rates, and contains legitimate unusual spending that the generator does not model.
- The rules and the injected patterns were designed together, so the rule recall is optimistic.
- The weekend and vendor-concentration thresholds were adjusted after looking at results on this same dataset. No separate held-out dataset was used.
- Contamination (0.05) was set close to the true injected rate, which would not be known in practice.
- Results come from one dataset and one random seed. There was no cross-validation, repeated runs or hyperparameter search.
- The model scores each expense on its own, so it cannot see relational patterns such as duplicates and splits.
- The system is a batch pipeline, so the dashboard shows results only as of the last run.

## Possible next steps

- Test on real or anonymised expense data and re-tune the thresholds from reviewer outcomes.
- Add near-duplicate matching and graph analysis of employee, approver and vendor links to catch relational patterns.
- Add rolling time-window features, and run with several contamination values and random seeds.
- Collect reviewer decisions on flagged expenses and use them to train a supervised model alongside the unsupervised one.
- Build a Power BI report on top of the Excel export.

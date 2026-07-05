# Loan Default Risk & EMI Payment Behavior Analysis (SQL)

A SQL portfolio project analyzing loan default risk using a synthetic lending
dataset with realistic, correlated patterns (not random noise) — designed to
mimic how a bank or NBFC risk team would investigate default drivers.

## Why this project
Lending institutions (banks, NBFCs, fintechs) lose significant revenue to loan
defaults. This project simulates that real-world analytics problem: identifying
which customers, loan types, and early warning signals predict default —
using only SQL (CTEs, window functions, self-joins) for the analysis.

## Dataset
Generated with `generate_data.py` (Python + SQLite), producing:
- **800 customers** — age, income, employment type, city, credit score
- **1,158 loans** — across 5 categories (Home, Auto, Personal, Education, Business)
- **~37,000 EMI payment records** — monthly payment status (On-Time / Late / Missed)

Realistic correlations are deliberately built into the generator so findings
are meaningful:
- Higher loan-to-income ratio → higher default probability
- Lower credit score → higher default probability
- Missed EMIs early in a loan → strong predictor of eventual default
- Riskier categories (Personal, Business) vs. safer ones (Home, Education)

## Schema
```
customers(customer_id, age, monthly_income, employment_type, city, credit_score)
loans(loan_id, customer_id, loan_category, loan_amount, interest_rate,
      tenure_months, disbursed_date, emi_amount, loan_status)
emi_payments(emi_id, loan_id, month_number, due_date, emi_amount,
             payment_status, paid_date, days_late)
```

## Analysis — 10 Queries (`analysis_queries.sql`)
1. Default rate by loan category (window function: RANK)
2. High-risk customers via rolling 6-month missed-EMI window (window function: SUM OVER ROWS)
3. Loan-to-income ratio bucketing vs. default rate (CTE)
4. Early-warning signal: does an early missed EMI predict default? (CTE)
5. Composite customer risk scoring with risk quartiles (window function: NTILE)
6. Month-over-month default trend with 3-month rolling average (window function: AVG OVER)
7. City-wise default risk ranking (window function: DENSE_RANK)
8. Repeat-defaulter detection across a customer's multiple loans (self-join)
9. Employment type vs. payment lateness (window function: percent of total)
10. Credit score bands vs. cumulative default count (window function: cumulative SUM)

## Key Finding
Loans that miss an EMI within the **first 3 months** default at a **30.7% rate**,
more than double the overall portfolio default rate of ~14% — suggesting early
payment behavior is one of the strongest predictors of eventual default.

## How to run
```bash
python3 generate_data.py      # creates loan_default.db
sqlite3 loan_default.db < analysis_queries.sql
```

## Tools used
Python (synthetic data generation), SQLite, SQL (CTEs, window functions, self-joins)

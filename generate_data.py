"""
Synthetic Loan Default & EMI Payment Behavior Dataset Generator
-----------------------------------------------------------------
Generates a realistic, internally-consistent SQLite database simulating
a lending institution's customer, loan, and EMI payment data.

Realistic correlations baked in:
- Lower income + higher loan amount -> higher default probability
- Longer tenure -> slightly higher default probability
- Missed EMIs early in the loan -> strong predictor of eventual default
- Younger age group -> marginally higher risk
- Certain loan categories (personal, auto) riskier than home/education loans

Author: Generated for Anil's Data Analyst portfolio
"""

import sqlite3
import random
from datetime import datetime, timedelta

random.seed(42)

DB_PATH = "loan_default.db"

NUM_CUSTOMERS = 800
LOAN_CATEGORIES = ["Home", "Auto", "Personal", "Education", "Business"]
CITIES = ["Bengaluru", "Mumbai", "Delhi", "Pune", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad"]
EMPLOYMENT_TYPES = ["Salaried", "Self-Employed", "Business Owner"]

# Base risk multiplier by loan category (higher = riskier)
CATEGORY_RISK = {
    "Home": 0.5,
    "Auto": 0.9,
    "Personal": 1.3,
    "Education": 0.6,
    "Business": 1.1,
}

CATEGORY_AMOUNT_RANGE = {
    "Home": (1500000, 6000000),
    "Auto": (300000, 1200000),
    "Personal": (50000, 800000),
    "Education": (100000, 2000000),
    "Business": (200000, 3000000),
}

CATEGORY_TENURE_MONTHS = {
    "Home": [120, 180, 240],
    "Auto": [36, 48, 60],
    "Personal": [12, 24, 36],
    "Education": [36, 60, 84],
    "Business": [24, 36, 60],
}


def random_date(start_year=2021, end_year=2025):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))


def generate_customers(n):
    customers = []
    for cid in range(1, n + 1):
        age = random.randint(22, 60)
        income = max(15000, int(random.gauss(55000, 25000)))
        employment = random.choices(EMPLOYMENT_TYPES, weights=[0.6, 0.25, 0.15])[0]
        city = random.choice(CITIES)
        credit_score = max(300, min(900, int(random.gauss(680, 90))))
        customers.append({
            "customer_id": cid,
            "age": age,
            "monthly_income": income,
            "employment_type": employment,
            "city": city,
            "credit_score": credit_score,
        })
    return customers


def compute_default_probability(customer, category, loan_amount, tenure_months):
    """Combine multiple realistic risk factors into a default probability."""
    base = 0.06  # base default rate

    # Income vs loan amount ratio - higher amount relative to income = riskier
    income_annual = customer["monthly_income"] * 12
    loan_to_income = loan_amount / max(income_annual, 1)
    if loan_to_income > 8:
        base += 0.18
    elif loan_to_income > 5:
        base += 0.10
    elif loan_to_income > 3:
        base += 0.05

    # Credit score effect
    if customer["credit_score"] < 600:
        base += 0.15
    elif customer["credit_score"] < 700:
        base += 0.06
    elif customer["credit_score"] > 800:
        base -= 0.05

    # Category risk multiplier
    base *= CATEGORY_RISK[category]

    # Tenure effect - longer tenure slightly riskier
    if tenure_months >= 60:
        base += 0.03

    # Age effect - younger borrowers marginally riskier
    if customer["age"] < 28:
        base += 0.04

    # Employment stability
    if customer["employment_type"] == "Business Owner":
        base += 0.03
    elif customer["employment_type"] == "Salaried":
        base -= 0.02

    return max(0.01, min(0.85, base))


def generate_loans_and_emis(customers):
    loans = []
    emis = []
    loan_id_counter = 1
    emi_id_counter = 1

    for customer in customers:
        num_loans = random.choices([1, 2, 3], weights=[0.65, 0.25, 0.10])[0]
        for _ in range(num_loans):
            category = random.choice(LOAN_CATEGORIES)
            amt_min, amt_max = CATEGORY_AMOUNT_RANGE[category]
            loan_amount = random.randint(amt_min, amt_max)
            tenure_months = random.choice(CATEGORY_TENURE_MONTHS[category])
            interest_rate = round(random.uniform(7.5, 18.5), 2)
            disbursed_date = random_date(2021, 2024)

            default_prob = compute_default_probability(customer, category, loan_amount, tenure_months)
            will_default = random.random() < default_prob

            # Determine loan status and how many EMIs were actually paid before default/completion
            months_elapsed = min(tenure_months, (datetime(2026, 6, 1) - disbursed_date).days // 30)
            months_elapsed = max(1, months_elapsed)

            if will_default and months_elapsed >= 3:
                # Default happens somewhere after month 3, weighted toward earlier months
                default_month = min(months_elapsed, max(3, int(random.triangular(3, months_elapsed, months_elapsed * 0.4))))
                loan_status = "Defaulted"
                emis_paid = default_month
            elif months_elapsed >= tenure_months:
                loan_status = "Closed"
                emis_paid = tenure_months
            else:
                loan_status = "Active"
                emis_paid = months_elapsed

            emi_amount = round((loan_amount * (1 + interest_rate / 100 * (tenure_months / 12))) / tenure_months, 2)

            loans.append({
                "loan_id": loan_id_counter,
                "customer_id": customer["customer_id"],
                "loan_category": category,
                "loan_amount": loan_amount,
                "interest_rate": interest_rate,
                "tenure_months": tenure_months,
                "disbursed_date": disbursed_date.strftime("%Y-%m-%d"),
                "emi_amount": emi_amount,
                "loan_status": loan_status,
            })

            # Generate EMI payment records for months actually elapsed
            missed_streak = 0
            for month_num in range(1, emis_paid + 1):
                due_date = disbursed_date + timedelta(days=30 * month_num)

                # Missed payment probability rises if loan will default, and compounds with streak
                miss_base_prob = default_prob * 0.5 if will_default else 0.03
                miss_prob = miss_base_prob + (missed_streak * 0.08)
                missed = random.random() < miss_prob

                if missed:
                    missed_streak += 1
                    payment_status = "Missed"
                    paid_date = None
                    days_late = None
                else:
                    missed_streak = max(0, missed_streak - 1)
                    # Some payments are late but not fully missed
                    late = random.random() < 0.15
                    if late:
                        days_late = random.randint(1, 20)
                        payment_status = "Late"
                        paid_date = (due_date + timedelta(days=days_late)).strftime("%Y-%m-%d")
                    else:
                        days_late = 0
                        payment_status = "On-Time"
                        paid_date = due_date.strftime("%Y-%m-%d")

                emis.append({
                    "emi_id": emi_id_counter,
                    "loan_id": loan_id_counter,
                    "month_number": month_num,
                    "due_date": due_date.strftime("%Y-%m-%d"),
                    "emi_amount": emi_amount,
                    "payment_status": payment_status,
                    "paid_date": paid_date,
                    "days_late": days_late,
                })
                emi_id_counter += 1

            loan_id_counter += 1

    return loans, emis


def build_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
    DROP TABLE IF EXISTS emi_payments;
    DROP TABLE IF EXISTS loans;
    DROP TABLE IF EXISTS customers;

    CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        age INTEGER NOT NULL,
        monthly_income INTEGER NOT NULL,
        employment_type TEXT NOT NULL,
        city TEXT NOT NULL,
        credit_score INTEGER NOT NULL
    );

    CREATE TABLE loans (
        loan_id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        loan_category TEXT NOT NULL,
        loan_amount INTEGER NOT NULL,
        interest_rate REAL NOT NULL,
        tenure_months INTEGER NOT NULL,
        disbursed_date TEXT NOT NULL,
        emi_amount REAL NOT NULL,
        loan_status TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    );

    CREATE TABLE emi_payments (
        emi_id INTEGER PRIMARY KEY,
        loan_id INTEGER NOT NULL,
        month_number INTEGER NOT NULL,
        due_date TEXT NOT NULL,
        emi_amount REAL NOT NULL,
        payment_status TEXT NOT NULL,
        paid_date TEXT,
        days_late INTEGER,
        FOREIGN KEY (loan_id) REFERENCES loans(loan_id)
    );
    """)

    customers = generate_customers(NUM_CUSTOMERS)
    loans, emis = generate_loans_and_emis(customers)

    cur.executemany(
        "INSERT INTO customers VALUES (:customer_id, :age, :monthly_income, :employment_type, :city, :credit_score)",
        customers,
    )
    cur.executemany(
        """INSERT INTO loans VALUES (:loan_id, :customer_id, :loan_category, :loan_amount, :interest_rate,
           :tenure_months, :disbursed_date, :emi_amount, :loan_status)""",
        loans,
    )
    cur.executemany(
        """INSERT INTO emi_payments VALUES (:emi_id, :loan_id, :month_number, :due_date, :emi_amount,
           :payment_status, :paid_date, :days_late)""",
        emis,
    )

    conn.commit()

    # Print summary stats
    cur.execute("SELECT COUNT(*) FROM customers")
    print(f"Customers: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM loans")
    print(f"Loans: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM emi_payments")
    print(f"EMI records: {cur.fetchone()[0]}")
    cur.execute("SELECT loan_status, COUNT(*) FROM loans GROUP BY loan_status")
    print("Loan status breakdown:", cur.fetchall())
    cur.execute("SELECT loan_category, COUNT(*), SUM(CASE WHEN loan_status='Defaulted' THEN 1 ELSE 0 END) FROM loans GROUP BY loan_category")
    print("Category-wise (total, defaults):", cur.fetchall())

    conn.close()


if __name__ == "__main__":
    build_database()
    print(f"\nDatabase created at: {DB_PATH}")

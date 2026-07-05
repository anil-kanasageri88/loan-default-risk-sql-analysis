"""
Synthetic Loan Default & EMI Payment Behavior Dataset Generator (MySQL version)
--------------------------------------------------------------------------------
Generates a realistic, internally-consistent MySQL database simulating
a lending institution's customer, loan, and EMI payment data.

Realistic correlations baked in:
- Lower income + higher loan amount -> higher default probability
- Longer tenure -> slightly higher default probability
- Missed EMIs early in the loan -> strong predictor of eventual default
- Younger age group -> marginally higher risk
- Certain loan categories (personal, auto) riskier than home/education loans

Author: Generated for Anil's Data Analyst portfolio

SETUP BEFORE RUNNING:
1. Install the MySQL connector:  pip install mysql-connector-python
2. Fill in your MySQL credentials in the CONFIG section below
3. Run:  python3 generate_data_mysql.py
"""

import mysql.connector
import random
from datetime import datetime, timedelta

random.seed(42)

# ============================================================================
# CONFIG - fill in your own MySQL credentials here
# ============================================================================
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",          # <-- change if your username is different
    "password": "YOUR_PASSWORD_HERE",  # <-- put your actual MySQL password here
    "port": 3306,
}
DATABASE_NAME = "loan_default_db"
# ============================================================================

NUM_CUSTOMERS = 800
LOAN_CATEGORIES = ["Home", "Auto", "Personal", "Education", "Business"]
CITIES = ["Bengaluru", "Mumbai", "Delhi", "Pune", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad"]
EMPLOYMENT_TYPES = ["Salaried", "Self-Employed", "Business Owner"]

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
    base = 0.06

    income_annual = customer["monthly_income"] * 12
    loan_to_income = loan_amount / max(income_annual, 1)
    if loan_to_income > 8:
        base += 0.18
    elif loan_to_income > 5:
        base += 0.10
    elif loan_to_income > 3:
        base += 0.05

    if customer["credit_score"] < 600:
        base += 0.15
    elif customer["credit_score"] < 700:
        base += 0.06
    elif customer["credit_score"] > 800:
        base -= 0.05

    base *= CATEGORY_RISK[category]

    if tenure_months >= 60:
        base += 0.03

    if customer["age"] < 28:
        base += 0.04

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

            months_elapsed = min(tenure_months, (datetime(2026, 6, 1) - disbursed_date).days // 30)
            months_elapsed = max(1, months_elapsed)

            if will_default and months_elapsed >= 3:
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

            missed_streak = 0
            for month_num in range(1, emis_paid + 1):
                due_date = disbursed_date + timedelta(days=30 * month_num)

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
    # Step 1: connect to MySQL server (no specific database yet)
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cur = conn.cursor()

    # Step 2: create the database if it doesn't exist, then use it
    cur.execute(f"DROP DATABASE IF EXISTS {DATABASE_NAME}")
    cur.execute(f"CREATE DATABASE {DATABASE_NAME}")
    cur.execute(f"USE {DATABASE_NAME}")

    # Step 3: create tables
    cur.execute("""
        CREATE TABLE customers (
            customer_id INT PRIMARY KEY,
            age INT NOT NULL,
            monthly_income INT NOT NULL,
            employment_type VARCHAR(50) NOT NULL,
            city VARCHAR(50) NOT NULL,
            credit_score INT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE loans (
            loan_id INT PRIMARY KEY,
            customer_id INT NOT NULL,
            loan_category VARCHAR(50) NOT NULL,
            loan_amount INT NOT NULL,
            interest_rate DECIMAL(5,2) NOT NULL,
            tenure_months INT NOT NULL,
            disbursed_date DATE NOT NULL,
            emi_amount DECIMAL(12,2) NOT NULL,
            loan_status VARCHAR(20) NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
    """)

    cur.execute("""
        CREATE TABLE emi_payments (
            emi_id INT PRIMARY KEY,
            loan_id INT NOT NULL,
            month_number INT NOT NULL,
            due_date DATE NOT NULL,
            emi_amount DECIMAL(12,2) NOT NULL,
            payment_status VARCHAR(20) NOT NULL,
            paid_date DATE,
            days_late INT,
            FOREIGN KEY (loan_id) REFERENCES loans(loan_id)
        )
    """)

    # Step 4: generate the synthetic data
    customers = generate_customers(NUM_CUSTOMERS)
    loans, emis = generate_loans_and_emis(customers)

    # Step 5: insert data in batches (fast, using executemany)
    cur.executemany(
        "INSERT INTO customers VALUES (%(customer_id)s, %(age)s, %(monthly_income)s, %(employment_type)s, %(city)s, %(credit_score)s)",
        customers,
    )
    cur.executemany(
        """INSERT INTO loans VALUES (%(loan_id)s, %(customer_id)s, %(loan_category)s, %(loan_amount)s, %(interest_rate)s,
           %(tenure_months)s, %(disbursed_date)s, %(emi_amount)s, %(loan_status)s)""",
        loans,
    )
    cur.executemany(
        """INSERT INTO emi_payments VALUES (%(emi_id)s, %(loan_id)s, %(month_number)s, %(due_date)s, %(emi_amount)s,
           %(payment_status)s, %(paid_date)s, %(days_late)s)""",
        emis,
    )

    conn.commit()

    # Step 6: print summary stats to confirm success
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

    cur.close()
    conn.close()


if __name__ == "__main__":
    build_database()
    print(f"\nDatabase '{DATABASE_NAME}' created successfully in MySQL!")
    print("Open MySQL Workbench, refresh your schemas list, and you'll see it there.")

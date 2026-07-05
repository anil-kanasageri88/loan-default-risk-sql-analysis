-- ============================================================================
-- LOAN DEFAULT RISK & EMI PAYMENT BEHAVIOR ANALYSIS
-- Advanced SQL Portfolio Project
-- Database: SQLite (loan_default.db)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- SCHEMA (for reference — already created by generate_data.py)
-- ----------------------------------------------------------------------------
-- customers(customer_id, age, monthly_income, employment_type, city, credit_score)
-- loans(loan_id, customer_id, loan_category, loan_amount, interest_rate,
--       tenure_months, disbursed_date, emi_amount, loan_status)
-- emi_payments(emi_id, loan_id, month_number, due_date, emi_amount,
--              payment_status, paid_date, days_late)
-- ----------------------------------------------------------------------------


-- ============================================================================
-- Q1. Default rate by loan category, ranked highest to lowest
-- Technique: Aggregation + Window Function (RANK)
-- ============================================================================
SELECT
    loan_category,
    COUNT(*) AS total_loans,
    SUM(CASE WHEN loan_status = 'Defaulted' THEN 1 ELSE 0 END) AS defaulted_loans,
    ROUND(100.0 * SUM(CASE WHEN loan_status = 'Defaulted' THEN 1 ELSE 0 END) / COUNT(*), 2) AS default_rate_pct,
    RANK() OVER (ORDER BY 100.0 * SUM(CASE WHEN loan_status = 'Defaulted' THEN 1 ELSE 0 END) / COUNT(*) DESC) AS risk_rank
FROM loans
GROUP BY loan_category
ORDER BY risk_rank;


-- ============================================================================
-- Q2. High-risk customer flagging using a multi-step CTE
-- Flags customers who missed 2+ EMIs within any rolling 6-month window
-- Technique: CTE chaining + Window Function (SUM ... OVER with ROWS frame)
-- ============================================================================
WITH missed_flags AS (
    SELECT
        l.customer_id,
        l.loan_id,
        e.month_number,
        CASE WHEN e.payment_status = 'Missed' THEN 1 ELSE 0 END AS is_missed
    FROM emi_payments e
    JOIN loans l ON l.loan_id = e.loan_id
),
rolling_missed AS (
    SELECT
        customer_id,
        loan_id,
        month_number,
        is_missed,
        SUM(is_missed) OVER (
            PARTITION BY loan_id
            ORDER BY month_number
            ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
        ) AS missed_in_last_6_months
    FROM missed_flags
)
SELECT DISTINCT
    customer_id,
    loan_id,
    MAX(missed_in_last_6_months) AS worst_6mo_missed_count
FROM rolling_missed
GROUP BY customer_id, loan_id
HAVING worst_6mo_missed_count >= 2
ORDER BY worst_6mo_missed_count DESC;


-- ============================================================================
-- Q3. Loan-to-income ratio vs default outcome
-- Technique: CTE + CASE bucketing + aggregation
-- ============================================================================
WITH loan_income AS (
    SELECT
        l.loan_id,
        l.loan_status,
        l.loan_amount,
        c.monthly_income * 12 AS annual_income,
        ROUND(l.loan_amount * 1.0 / (c.monthly_income * 12), 2) AS loan_to_income_ratio
    FROM loans l
    JOIN customers c ON c.customer_id = l.customer_id
),
bucketed AS (
    SELECT
        *,
        CASE
            WHEN loan_to_income_ratio < 2 THEN '<2x'
            WHEN loan_to_income_ratio < 5 THEN '2x-5x'
            WHEN loan_to_income_ratio < 8 THEN '5x-8x'
            ELSE '8x+'
        END AS ratio_bucket
    FROM loan_income
)
SELECT
    ratio_bucket,
    COUNT(*) AS total_loans,
    SUM(CASE WHEN loan_status = 'Defaulted' THEN 1 ELSE 0 END) AS defaults,
    ROUND(100.0 * SUM(CASE WHEN loan_status = 'Defaulted' THEN 1 ELSE 0 END) / COUNT(*), 2) AS default_rate_pct
FROM bucketed
GROUP BY ratio_bucket
ORDER BY
    CASE ratio_bucket
        WHEN '<2x' THEN 1 WHEN '2x-5x' THEN 2 WHEN '5x-8x' THEN 3 ELSE 4
    END;


-- ============================================================================
-- Q4. Early-warning signal: does a customer's FIRST missed EMI predict
-- eventual default? Self-join comparing first missed month to loan outcome.
-- Technique: Self-join (via correlated subquery) + CTE
-- ============================================================================
WITH first_miss AS (
    SELECT
        loan_id,
        MIN(month_number) AS first_missed_month
    FROM emi_payments
    WHERE payment_status = 'Missed'
    GROUP BY loan_id
)
SELECT
    CASE
        WHEN fm.first_missed_month IS NULL THEN 'Never Missed'
        WHEN fm.first_missed_month <= 3 THEN 'Missed within first 3 months'
        WHEN fm.first_missed_month <= 6 THEN 'Missed within 4-6 months'
        ELSE 'Missed after 6 months'
    END AS early_warning_category,
    COUNT(l.loan_id) AS total_loans,
    SUM(CASE WHEN l.loan_status = 'Defaulted' THEN 1 ELSE 0 END) AS defaults,
    ROUND(100.0 * SUM(CASE WHEN l.loan_status = 'Defaulted' THEN 1 ELSE 0 END) / COUNT(l.loan_id), 2) AS default_rate_pct
FROM loans l
LEFT JOIN first_miss fm ON fm.loan_id = l.loan_id
GROUP BY early_warning_category
ORDER BY default_rate_pct DESC;


-- ============================================================================
-- Q5. Customer risk scoring: combine credit score, income, and payment
-- history into a single composite risk score per customer.
-- Technique: Multi-step CTE + window function (NTILE for risk tiers)
-- ============================================================================
WITH customer_payment_stats AS (
    SELECT
        l.customer_id,
        COUNT(DISTINCT l.loan_id) AS num_loans,
        SUM(CASE WHEN e.payment_status = 'Missed' THEN 1 ELSE 0 END) AS total_missed_emis,
        COUNT(e.emi_id) AS total_emis
    FROM loans l
    JOIN emi_payments e ON e.loan_id = l.loan_id
    GROUP BY l.customer_id
),
customer_risk AS (
    SELECT
        c.customer_id,
        c.credit_score,
        c.monthly_income,
        cps.num_loans,
        ROUND(100.0 * cps.total_missed_emis / NULLIF(cps.total_emis, 0), 2) AS missed_emi_pct,
        -- simple composite score: lower credit score and higher missed % = higher risk
        ROUND(
            (900 - c.credit_score) * 0.5 +
            COALESCE(100.0 * cps.total_missed_emis / NULLIF(cps.total_emis, 0), 0) * 3
        , 2) AS composite_risk_score
    FROM customers c
    JOIN customer_payment_stats cps ON cps.customer_id = c.customer_id
)
SELECT
    customer_id,
    credit_score,
    monthly_income,
    missed_emi_pct,
    composite_risk_score,
    NTILE(4) OVER (ORDER BY composite_risk_score DESC) AS risk_quartile  -- 1 = highest risk
FROM customer_risk
ORDER BY composite_risk_score DESC
LIMIT 50;


-- ============================================================================
-- Q6. Month-over-month default trend (loans disbursed by month vs eventual
-- default rate) — useful for spotting whether risk is rising over time.
-- Technique: Window function (moving average)
-- ============================================================================
WITH monthly_stats AS (
    SELECT
        strftime('%Y-%m', disbursed_date) AS disbursed_month,
        COUNT(*) AS loans_disbursed,
        SUM(CASE WHEN loan_status = 'Defaulted' THEN 1 ELSE 0 END) AS defaults
    FROM loans
    GROUP BY disbursed_month
)
SELECT
    disbursed_month,
    loans_disbursed,
    defaults,
    ROUND(100.0 * defaults / loans_disbursed, 2) AS default_rate_pct,
    ROUND(AVG(100.0 * defaults / loans_disbursed) OVER (
        ORDER BY disbursed_month
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2) AS rolling_3mo_avg_default_rate
FROM monthly_stats
ORDER BY disbursed_month;


-- ============================================================================
-- Q7. City-wise risk ranking with dense rank, filtering only cities with
-- meaningful loan volume (avoids small-sample noise)
-- Technique: CTE + DENSE_RANK
-- ============================================================================
WITH city_stats AS (
    SELECT
        c.city,
        COUNT(l.loan_id) AS total_loans,
        SUM(CASE WHEN l.loan_status = 'Defaulted' THEN 1 ELSE 0 END) AS defaults,
        ROUND(100.0 * SUM(CASE WHEN l.loan_status = 'Defaulted' THEN 1 ELSE 0 END) / COUNT(l.loan_id), 2) AS default_rate_pct
    FROM customers c
    JOIN loans l ON l.customer_id = c.customer_id
    GROUP BY c.city
    HAVING COUNT(l.loan_id) >= 30
)
SELECT
    city,
    total_loans,
    defaults,
    default_rate_pct,
    DENSE_RANK() OVER (ORDER BY default_rate_pct DESC) AS risk_rank
FROM city_stats
ORDER BY risk_rank;


-- ============================================================================
-- Q8. Repeat-defaulter detection: customers who defaulted on one loan —
-- did they also default (or currently struggle) on another loan?
-- Technique: Self-join on loans table via customer_id
-- ============================================================================
SELECT
    l1.customer_id,
    l1.loan_id AS defaulted_loan_id,
    l1.loan_category AS defaulted_category,
    l2.loan_id AS other_loan_id,
    l2.loan_category AS other_loan_category,
    l2.loan_status AS other_loan_status
FROM loans l1
JOIN loans l2
    ON l1.customer_id = l2.customer_id
    AND l1.loan_id != l2.loan_id
WHERE l1.loan_status = 'Defaulted'
ORDER BY l1.customer_id;


-- ============================================================================
-- Q9. Employment type vs. average days late on payments
-- Technique: Aggregation + window function (percent of total)
-- ============================================================================
WITH emp_lateness AS (
    SELECT
        c.employment_type,
        COUNT(e.emi_id) AS total_emis,
        ROUND(AVG(CASE WHEN e.payment_status = 'Late' THEN e.days_late END), 2) AS avg_days_late,
        SUM(CASE WHEN e.payment_status = 'Missed' THEN 1 ELSE 0 END) AS missed_count
    FROM customers c
    JOIN loans l ON l.customer_id = c.customer_id
    JOIN emi_payments e ON e.loan_id = l.loan_id
    GROUP BY c.employment_type
)
SELECT
    employment_type,
    total_emis,
    avg_days_late,
    missed_count,
    ROUND(100.0 * missed_count / SUM(missed_count) OVER (), 2) AS pct_of_all_missed_emis
FROM emp_lateness
ORDER BY missed_count DESC;


-- ============================================================================
-- Q10. Credit score band vs default rate, with running cumulative default
-- count as credit score decreases — shows the "risk cliff" visually.
-- Technique: CTE + window function (cumulative SUM)
-- ============================================================================
WITH score_bands AS (
    SELECT
        l.loan_id,
        l.loan_status,
        CASE
            WHEN c.credit_score >= 800 THEN '800+'
            WHEN c.credit_score >= 750 THEN '750-799'
            WHEN c.credit_score >= 700 THEN '700-749'
            WHEN c.credit_score >= 650 THEN '650-699'
            WHEN c.credit_score >= 600 THEN '600-649'
            ELSE 'Below 600'
        END AS score_band,
        CASE
            WHEN c.credit_score >= 800 THEN 1
            WHEN c.credit_score >= 750 THEN 2
            WHEN c.credit_score >= 700 THEN 3
            WHEN c.credit_score >= 650 THEN 4
            WHEN c.credit_score >= 600 THEN 5
            ELSE 6
        END AS band_order
    FROM loans l
    JOIN customers c ON c.customer_id = l.customer_id
),
band_summary AS (
    SELECT
        score_band,
        band_order,
        COUNT(*) AS total_loans,
        SUM(CASE WHEN loan_status = 'Defaulted' THEN 1 ELSE 0 END) AS defaults
    FROM score_bands
    GROUP BY score_band, band_order
)
SELECT
    score_band,
    total_loans,
    defaults,
    ROUND(100.0 * defaults / total_loans, 2) AS default_rate_pct,
    SUM(defaults) OVER (ORDER BY band_order) AS cumulative_defaults_as_score_drops
FROM band_summary
ORDER BY band_order;

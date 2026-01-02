-- ============================================
-- Object Type: TABLE
-- Object Name: gold.dim_customer
-- Source File: sample_financial_schema.sql
-- Separated On: 2025-12-08 18:51:52
-- Dialect: tsql
-- ============================================

/* Gold: Customer dimension table */ SELECT * INTO gold.dim_customer FROM (SELECT c.customer_id AS customer_id, c.full_name AS full_name, c.email_normalized AS email, c.signup_date AS signup_date, c.country_code AS country_code, t.transaction_count AS transaction_count, t.total_amount AS lifetime_value, DATEDIFF(DAY, CAST(c.signup_date AS DATETIME2), CAST(t.last_transaction_date AS DATETIME2)) AS customer_tenure_days, CASE WHEN t.total_amount > 10000 THEN 'Premium' WHEN t.total_amount > 1000 THEN 'Standard' ELSE 'Basic' END AS customer_tier FROM staging.customers_clean AS c LEFT JOIN staging.customer_transactions AS t ON c.customer_id = t.customer_id) AS temp

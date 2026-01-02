-- ============================================
-- Object Type: TABLE
-- Object Name: gold.fact_transactions
-- Source File: sample_financial_schema.sql
-- Separated On: 2025-12-08 18:51:52
-- Dialect: tsql
-- ============================================

/* Gold: Transaction fact table */ SELECT * INTO gold.fact_transactions FROM (SELECT t.transaction_id AS transaction_id, t.customer_id AS customer_id, t.transaction_date AS transaction_date, t.amount AS amount, t.currency AS currency, c.customer_tier AS customer_tier, c.country_code AS country_code, YEAR(t.transaction_date) AS transaction_year, MONTH(t.transaction_date) AS transaction_month, DAY(t.transaction_date) AS transaction_day FROM raw.transactions AS t INNER JOIN gold.dim_customer AS c ON t.customer_id = c.customer_id WHERE t.status = 'COMPLETED') AS temp

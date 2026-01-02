-- ============================================
-- Object Type: TABLE
-- Object Name: staging.customer_transactions
-- Source File: sample_financial_schema.sql
-- Separated On: 2025-12-08 18:51:52
-- Dialect: tsql
-- ============================================

/* Staging: Aggregated transaction metrics */ SELECT * INTO staging.customer_transactions FROM (SELECT customer_id AS customer_id, COUNT(*) AS transaction_count, SUM(amount) AS total_amount, AVG(amount) AS avg_amount, MAX(transaction_date) AS last_transaction_date, MIN(transaction_date) AS first_transaction_date FROM raw.transactions WHERE status = 'COMPLETED' GROUP BY customer_id) AS temp

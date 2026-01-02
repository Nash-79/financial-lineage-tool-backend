-- ============================================
-- Object Type: VIEW
-- Object Name: analytics.customer_ltv_analysis
-- Source File: sample_financial_schema.sql
-- Separated On: 2025-12-08 18:51:52
-- Dialect: tsql
-- ============================================

/* Analytics: Customer lifetime value analysis */ CREATE VIEW analytics.customer_ltv_analysis AS SELECT customer_id, full_name, customer_tier, lifetime_value, transaction_count, lifetime_value / NULLIF(transaction_count, 0) AS avg_transaction_value, customer_tenure_days, lifetime_value / NULLIF(customer_tenure_days, 0) AS daily_value FROM gold.dim_customer WHERE transaction_count > 0

-- ============================================
-- Object Type: TABLE
-- Object Name: staging.customers_clean
-- Source File: sample_financial_schema.sql
-- Separated On: 2025-12-08 18:51:52
-- Dialect: tsql
-- ============================================

/* Staging: Cleansed customer data */ SELECT * INTO staging.customers_clean FROM (SELECT customer_id AS customer_id, CONCAT(first_name, ' ', last_name) AS full_name, LOWER(email) AS email_normalized, signup_date AS signup_date, UPPER(country) AS country_code FROM raw.customers WHERE NOT email IS NULL) AS temp

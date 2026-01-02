-- ============================================
-- Object Type: TABLE
-- Object Name: 
-- Source File: sample_financial_schema.sql
-- Separated On: 2025-12-08 18:51:52
-- Dialect: tsql
-- ============================================

/* Sample Financial Data Warehouse Schema */ /* This demonstrates table relationships and data lineage */ /* Source: Raw customer data */ CREATE TABLE raw.customers (customer_id INTEGER PRIMARY KEY, first_name VARCHAR(50), last_name VARCHAR(50), email VARCHAR(100), signup_date DATE, country VARCHAR(50))

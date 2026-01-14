-- Sample Financial Data Warehouse Schema
-- This demonstrates table relationships and data lineage

-- Source: Raw customer data
CREATE TABLE raw.customers (
    customer_id INT PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(100),
    signup_date DATE,
    country VARCHAR(50)
);

-- Source: Raw transaction data
CREATE TABLE raw.transactions (
    transaction_id INT PRIMARY KEY,
    customer_id INT,
    transaction_date TIMESTAMP,
    amount DECIMAL(18,2),
    currency VARCHAR(3),
    status VARCHAR(20),
    FOREIGN KEY (customer_id) REFERENCES raw.customers(customer_id)
);

-- Staging: Cleansed customer data
CREATE TABLE staging.customers_clean AS
SELECT
    customer_id,
    CONCAT(first_name, ' ', last_name) as full_name,
    LOWER(email) as email_normalized,
    signup_date,
    UPPER(country) as country_code
FROM raw.customers
WHERE email IS NOT NULL;

-- Staging: Aggregated transaction metrics
CREATE TABLE staging.customer_transactions AS
SELECT
    customer_id,
    COUNT(*) as transaction_count,
    SUM(amount) as total_amount,
    AVG(amount) as avg_amount,
    MAX(transaction_date) as last_transaction_date,
    MIN(transaction_date) as first_transaction_date
FROM raw.transactions
WHERE status = 'COMPLETED'
GROUP BY customer_id;

-- Gold: Customer dimension table
CREATE TABLE gold.dim_customer AS
SELECT
    c.customer_id,
    c.full_name,
    c.email_normalized as email,
    c.signup_date,
    c.country_code,
    t.transaction_count,
    t.total_amount as lifetime_value,
    DATEDIFF(day, c.signup_date, t.last_transaction_date) as customer_tenure_days,
    CASE
        WHEN t.total_amount > 10000 THEN 'Premium'
        WHEN t.total_amount > 1000 THEN 'Standard'
        ELSE 'Basic'
    END as customer_tier
FROM staging.customers_clean c
LEFT JOIN staging.customer_transactions t
    ON c.customer_id = t.customer_id;

-- Gold: Transaction fact table
CREATE TABLE gold.fact_transactions AS
SELECT
    t.transaction_id,
    t.customer_id,
    t.transaction_date,
    t.amount,
    t.currency,
    c.customer_tier,
    c.country_code,
    YEAR(t.transaction_date) as transaction_year,
    MONTH(t.transaction_date) as transaction_month,
    DAY(t.transaction_date) as transaction_day
FROM raw.transactions t
INNER JOIN gold.dim_customer c
    ON t.customer_id = c.customer_id
WHERE t.status = 'COMPLETED';

-- Analytics: Customer lifetime value analysis
CREATE VIEW analytics.customer_ltv_analysis AS
SELECT
    customer_id,
    full_name,
    customer_tier,
    lifetime_value,
    transaction_count,
    lifetime_value / NULLIF(transaction_count, 0) as avg_transaction_value,
    customer_tenure_days,
    lifetime_value / NULLIF(customer_tenure_days, 0) as daily_value
FROM gold.dim_customer
WHERE transaction_count > 0;

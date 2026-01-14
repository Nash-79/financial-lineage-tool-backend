-- Source: demo_data/postgres_investments_embeddings2.sql
-- Type: SQL_STATEMENT
-- Chunk: 6
----------------------------------------
/* Raw FX rates */ CREATE TABLE raw_market.fx_rates (as_of_date DATE, ccy TEXT, usd_rate DECIMAL(18, 8) /* 1 unit of ccy * usd_rate = USD */, PRIMARY KEY (as_of_date, ccy))
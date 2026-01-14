-- Source: demo_data/postgres_investments_embeddings.sql
-- Type: SQL_STATEMENT
-- Chunk: 8
----------------------------------------
/* Optional sample data for tests */ INSERT INTO raw_market.trade_feed_venue_a (venue_trade_id, trade_ts, account_code, isin, side, quantity, price, currency) VALUES ('A-1', '2025-01-01T10:00:00Z', 'ACC-001', 'US0378331005', 'BUY', 100, 180.00, 'USD'), ('A-2', '2025-01-01T11:00:00Z', 'ACC-002', 'US0378331005', 'SELL', 50, 182.50, 'USD')
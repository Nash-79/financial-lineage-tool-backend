-- Source: demo_data/postgres_investments_embeddings2.sql
-- Type: SQL_STATEMENT
-- Chunk: 17
----------------------------------------
/* Example load from v_all_trades into position_intraday */ INSERT INTO stg_investments.position_intraday (trade_ts, trade_date, account_code, instrument_isin, quantity, price_ccy, currency, source_system) SELECT trade_ts, CAST(trade_ts AS DATE) AS trade_date, account_code, instrument_isin, quantity, price_ccy, currency, source_system FROM stg_investments.v_all_trades
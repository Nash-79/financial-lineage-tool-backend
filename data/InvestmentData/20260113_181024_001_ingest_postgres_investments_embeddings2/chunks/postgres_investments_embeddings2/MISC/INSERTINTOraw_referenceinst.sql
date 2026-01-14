-- Source: demo_data/postgres_investments_embeddings2.sql
-- Type: SQL_STATEMENT
-- Chunk: 11
----------------------------------------
INSERT INTO raw_reference.instrument_ref_json (as_of_date, payload) VALUES ('2025-01-01', CAST('{
      "isin": "US0378331005",
      "ticker": "AAPL",
      "asset_class": "EQUITY",
      "region": "US",
      "sector": "Information Technology",
      "currency": "USD"
    }' AS JSONB))
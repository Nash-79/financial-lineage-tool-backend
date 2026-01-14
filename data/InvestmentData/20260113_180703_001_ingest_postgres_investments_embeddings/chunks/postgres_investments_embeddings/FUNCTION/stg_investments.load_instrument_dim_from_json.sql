-- Source: demo_data/postgres_investments_embeddings.sql
-- Type: SQL_STATEMENT
-- Chunk: 14
----------------------------------------
CREATE OR REPLACE FUNCTION stg_investments.load_instrument_dim_from_json() RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO stg_investments.instrument_dim (isin, ticker, asset_class, region, sector, currency, as_of_date)
    SELECT
        payload->>'isin'         AS isin,
        payload->>'ticker'       AS ticker,
        payload->>'asset_class'  AS asset_class,
        payload->>'region'       AS region,
        payload->>'sector'       AS sector,
        payload->>'currency'     AS currency,
        as_of_date
    FROM raw_reference.instrument_ref_json
    ON CONFLICT (isin) DO UPDATE
    SET
        ticker     = EXCLUDED.ticker,
        asset_class= EXCLUDED.asset_class,
        region     = EXCLUDED.region,
        sector     = EXCLUDED.sector,
        currency   = EXCLUDED.currency,
        as_of_date = EXCLUDED.as_of_date;
END;
$$
-- Source: demo_data/postgres_investments_embeddings.sql
-- Type: SQL_STATEMENT
-- Chunk: 18
----------------------------------------
/* FX conversion helper */ CREATE OR REPLACE FUNCTION stg_investments.to_usd(p_ccy TEXT, p_trade_dt DATE, p_amount DECIMAL(30, 10)) RETURNS DECIMAL(30, 10) LANGUAGE plpgsql AS $$
DECLARE
    v_rate NUMERIC(18,8);
BEGIN
    SELECT usd_rate INTO v_rate
    FROM raw_market.fx_rates
    WHERE as_of_date = p_trade_dt
      AND ccy = p_ccy;

    IF NOT FOUND OR v_rate IS NULL THEN
        RETURN NULL;
    END IF;

    RETURN p_amount * v_rate;
END;
$$
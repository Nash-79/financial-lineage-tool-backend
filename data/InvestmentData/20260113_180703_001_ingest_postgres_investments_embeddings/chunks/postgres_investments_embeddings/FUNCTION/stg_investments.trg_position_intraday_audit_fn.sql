-- Source: demo_data/postgres_investments_embeddings.sql
-- Type: SQL_STATEMENT
-- Chunk: 20
----------------------------------------
CREATE OR REPLACE FUNCTION stg_investments.trg_position_intraday_audit_fn() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_notional_ccy NUMERIC(30,10);
    v_notional_usd NUMERIC(30,10);
BEGIN
    v_notional_ccy := NEW.quantity * NEW.price_ccy;
    v_notional_usd := stg_investments.to_usd(NEW.currency, NEW.trade_date, v_notional_ccy);

    INSERT INTO stg_investments.position_intraday_audit (
        position_id, trade_ts, account_code, instrument_isin,
        quantity, price_ccy, notional_ccy, notional_usd,
        currency
    )
    VALUES (
        NEW.position_id, NEW.trade_ts, NEW.account_code, NEW.instrument_isin,
        NEW.quantity, NEW.price_ccy, v_notional_ccy, v_notional_usd,
        NEW.currency
    );

    RETURN NEW;
END;
$$
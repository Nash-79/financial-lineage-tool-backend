-- postgres_investments_example.sql
-- Investment landing + transformation zone (PostgreSQL)

-- =========================
-- 1. Schemas
-- =========================
CREATE SCHEMA raw_market;
CREATE SCHEMA raw_reference;
CREATE SCHEMA stg_investments;
CREATE SCHEMA export;

-- =========================
-- 2. Raw landing tables
-- =========================

-- Raw trade feeds (heterogeneous)
CREATE TABLE raw_market.trade_feed_venue_a (
    trade_id        BIGSERIAL PRIMARY KEY,
    venue_trade_id  TEXT,
    trade_ts        TIMESTAMPTZ,
    account_code    TEXT,
    isin            TEXT,
    side            TEXT,            -- 'BUY'/'SELL'
    quantity        NUMERIC(20,4),
    price           NUMERIC(18,6),
    currency        TEXT,            -- e.g. 'USD','EUR'
    source_system   TEXT DEFAULT 'VENUE_A'
);

CREATE TABLE raw_market.trade_feed_venue_b (
    id              BIGSERIAL PRIMARY KEY,
    exec_time       TIMESTAMPTZ,
    portfolio       TEXT,
    ticker          TEXT,
    direction       TEXT,            -- 'B'/'S'
    qty             NUMERIC(20,4),
    gross_amount    NUMERIC(18,6),   -- quantity * price
    ccy             TEXT,
    source_system   TEXT DEFAULT 'VENUE_B'
);

-- Raw FX rates
CREATE TABLE raw_market.fx_rates (
    as_of_date  DATE,
    ccy         TEXT,
    usd_rate    NUMERIC(18,8),  -- 1 unit of ccy * usd_rate = USD
    PRIMARY KEY (as_of_date, ccy)
);

-- Raw instrument reference as JSON
CREATE TABLE raw_reference.instrument_ref_json (
    id            BIGSERIAL PRIMARY KEY,
    as_of_date    DATE,
    payload       JSONB  -- contains ISIN, ticker, asset_class, region, etc.
);

-- Optional sample data for tests
INSERT INTO raw_market.trade_feed_venue_a
    (venue_trade_id, trade_ts, account_code, isin, side, quantity, price, currency)
VALUES
    ('A-1', '2025-01-01T10:00:00Z', 'ACC-001', 'US0378331005', 'BUY',  100, 180.00, 'USD'),
    ('A-2', '2025-01-01T11:00:00Z', 'ACC-002', 'US0378331005', 'SELL',  50, 182.50, 'USD');

INSERT INTO raw_market.trade_feed_venue_b
    (exec_time, portfolio, ticker, direction, qty, gross_amount, ccy)
VALUES
    ('2025-01-01T09:30:00Z', 'ACC-001', 'AAPL', 'B', 200, 36000.00, 'USD');

INSERT INTO raw_market.fx_rates (as_of_date, ccy, usd_rate)
VALUES
    ('2025-01-01', 'USD', 1.0),
    ('2025-01-01', 'EUR', 1.1);

INSERT INTO raw_reference.instrument_ref_json (as_of_date, payload)
VALUES (
    '2025-01-01',
    '{
      "isin": "US0378331005",
      "ticker": "AAPL",
      "asset_class": "EQUITY",
      "region": "US",
      "sector": "Information Technology",
      "currency": "USD"
    }'::jsonb
);

-- =========================
-- 3. Helper functions and staging tables
-- =========================

-- Normalize heterogeneous trades into signed quantity and price
CREATE OR REPLACE FUNCTION stg_investments.normalize_trade(
    p_side         TEXT,
    p_quantity     NUMERIC(20,4),
    p_price        NUMERIC(18,6),
    p_gross_amount NUMERIC(18,6)
)
RETURNS TABLE (
    norm_qty   NUMERIC(20,4),
    norm_price NUMERIC(18,6)
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_price IS NOT NULL THEN
        -- Use explicit price
        norm_price := p_price;
    ELSIF p_gross_amount IS NOT NULL AND p_quantity IS NOT NULL AND p_quantity <> 0 THEN
        norm_price := p_gross_amount / p_quantity;
    ELSE
        norm_price := NULL;
    END IF;

    -- Apply sign based on side
    IF p_side IN ('SELL','S') THEN
        norm_qty := -1 * p_quantity;
    ELSE
        norm_qty := p_quantity;
    END IF;

    RETURN NEXT;
END;
$$;

-- Structured instrument dimension staging from JSON
CREATE TABLE stg_investments.instrument_dim (
    instrument_key   SERIAL PRIMARY KEY,
    isin             TEXT UNIQUE,
    ticker           TEXT,
    asset_class      TEXT,
    region           TEXT,
    sector           TEXT,
    currency         TEXT,
    as_of_date       DATE
);

CREATE OR REPLACE FUNCTION stg_investments.load_instrument_dim_from_json()
RETURNS VOID
LANGUAGE plpgsql
AS $$
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
$$;

-- Intraday position staging table
CREATE TABLE stg_investments.position_intraday (
    position_id     BIGSERIAL PRIMARY KEY,
    trade_ts        TIMESTAMPTZ,
    trade_date      DATE,
    account_code    TEXT,
    instrument_isin TEXT,
    quantity        NUMERIC(20,4),
    price_ccy       NUMERIC(18,6),
    currency        TEXT,
    source_system   TEXT
);

-- View to unify all raw trades using normalize_trade
CREATE OR REPLACE VIEW stg_investments.v_all_trades AS
SELECT
    tf.trade_ts,
    tf.account_code,
    tf.isin            AS instrument_isin,
    (nt.norm_qty)      AS quantity,
    (nt.norm_price)    AS price_ccy,
    tf.currency,
    tf.source_system
FROM raw_market.trade_feed_venue_a tf
CROSS JOIN LATERAL stg_investments.normalize_trade(
    tf.side, tf.quantity, tf.price, NULL
) AS nt

UNION ALL

SELECT
    tf.exec_time      AS trade_ts,
    tf.portfolio      AS account_code,
    NULL              AS instrument_isin,  -- will be resolved via ticker in later step
    (nt.norm_qty)     AS quantity,
    (nt.norm_price)   AS price_ccy,
    tf.ccy            AS currency,
    tf.source_system
FROM raw_market.trade_feed_venue_b tf
CROSS JOIN LATERAL stg_investments.normalize_trade(
    tf.direction, tf.qty, NULL, tf.gross_amount
) AS nt;

-- Example load from v_all_trades into position_intraday
INSERT INTO stg_investments.position_intraday (
    trade_ts, trade_date, account_code,
    instrument_isin, quantity, price_ccy, currency, source_system
)
SELECT
    trade_ts,
    trade_ts::date AS trade_date,
    account_code,
    instrument_isin,
    quantity,
    price_ccy,
    currency,
    source_system
FROM stg_investments.v_all_trades;

-- FX conversion helper
CREATE OR REPLACE FUNCTION stg_investments.to_usd(
    p_ccy      TEXT,
    p_trade_dt DATE,
    p_amount   NUMERIC(30,10)
)
RETURNS NUMERIC(30,10)
LANGUAGE plpgsql
AS $$
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
$$;

-- =========================
-- 4. Triggered audit with additional transformations
-- =========================

CREATE TABLE stg_investments.position_intraday_audit (
    audit_id        BIGSERIAL PRIMARY KEY,
    position_id     BIGINT,
    trade_ts        TIMESTAMPTZ,
    account_code    TEXT,
    instrument_isin TEXT,
    quantity        NUMERIC(20,4),
    price_ccy       NUMERIC(18,6),
    notional_ccy    NUMERIC(30,10),
    notional_usd    NUMERIC(30,10),
    currency        TEXT,
    audit_ts        TIMESTAMPTZ DEFAULT now()
);

CREATE OR REPLACE FUNCTION stg_investments.trg_position_intraday_audit_fn()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
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
$$;

CREATE TRIGGER trg_position_intraday_audit
AFTER INSERT ON stg_investments.position_intraday
FOR EACH ROW
EXECUTE FUNCTION stg_investments.trg_position_intraday_audit_fn();

-- =========================
-- 5. Export layer for Python / SQL Server
-- =========================

CREATE OR REPLACE VIEW export.daily_positions AS
SELECT
    p.trade_date            AS valuation_date,
    p.account_code,
    COALESCE(p.instrument_isin, i.isin) AS instrument_isin,
    i.ticker,
    i.asset_class,
    i.region,
    i.sector,
    SUM(p.quantity)                      AS position_qty,
    AVG(p.price_ccy)                     AS avg_price_ccy,
    p.currency,
    SUM(p.quantity * p.price_ccy)        AS notional_ccy,
    SUM(stg_investments.to_usd(p.currency, p.trade_date, p.quantity * p.price_ccy)) AS notional_usd
FROM stg_investments.position_intraday p
LEFT JOIN stg_investments.instrument_dim i
    ON p.instrument_isin = i.isin
GROUP BY
    p.trade_date,
    p.account_code,
    COALESCE(p.instrument_isin, i.isin),
    i.ticker,
    i.asset_class,
    i.region,
    i.sector,
    p.currency;
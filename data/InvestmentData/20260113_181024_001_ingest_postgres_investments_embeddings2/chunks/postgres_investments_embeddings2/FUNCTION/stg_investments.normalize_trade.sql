-- Source: demo_data/postgres_investments_embeddings2.sql
-- Type: SQL_STATEMENT
-- Chunk: 12
----------------------------------------
/* ========================= */ /* 3. Helper functions and staging tables */ /* ========================= */ /* Normalize heterogeneous trades into signed quantity and price */ CREATE OR REPLACE FUNCTION stg_investments.normalize_trade(p_side TEXT, p_quantity DECIMAL(20, 4), p_price DECIMAL(18, 6), p_gross_amount DECIMAL(18, 6)) RETURNS TABLE (norm_qty DECIMAL(20, 4), norm_price DECIMAL(18, 6)) LANGUAGE plpgsql AS $$
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
$$
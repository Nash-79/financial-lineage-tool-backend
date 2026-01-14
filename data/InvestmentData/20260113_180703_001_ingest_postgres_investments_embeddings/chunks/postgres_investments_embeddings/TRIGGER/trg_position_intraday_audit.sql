-- Source: demo_data/postgres_investments_embeddings.sql
-- Type: SQL_STATEMENT
-- Chunk: 21
----------------------------------------
CREATE TRIGGER trg_position_intraday_audit
AFTER INSERT ON stg_investments.position_intraday
FOR EACH ROW
EXECUTE FUNCTION stg_investments.trg_position_intraday_audit_fn()
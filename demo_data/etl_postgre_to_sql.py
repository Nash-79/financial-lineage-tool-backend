# etl_postgres_to_sqlserver.py
# Reads Postgres export.daily_positions + JSON risk rules,
# writes to SQL Server core.Stg_PositionImport

import json
from datetime import date

import psycopg2
import pyodbc

POSTGRES_DSN = "dbname=invest_landing user=etl password=secret host=localhost port=5432"
MSSQL_DSN = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=InvestCore;"
    "UID=etl;"
    "PWD=secret"
)

def load_risk_buckets(config_path: str) -> list[dict]:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def classify_risk(row: dict, rules: list[dict]) -> str:
    """
    Simple rule engine: return first matching bucket based on
    asset_class, region, and notional_usd range.
    """
    for rule in rules:
        if rule.get("asset_class") and rule["asset_class"] != row["asset_class"]:
            continue
        if rule.get("region") and rule["region"] != row["region"]:
            continue
        min_notional = rule.get("min_notional_usd") or 0
        max_notional = rule.get("max_notional_usd") or 1e18
        if not (min_notional <= row["notional_usd"] <= max_notional):
            continue
        return rule["bucket"]
    return "UNCLASSIFIED"

def main(valuation_date: date, risk_config_path: str = "risk_buckets.json") -> None:
    risk_rules = load_risk_buckets(risk_config_path)

    # Connect to Postgres
    pg_conn = psycopg2.connect(POSTGRES_DSN)
    pg_cur = pg_conn.cursor()

    # Connect to SQL Server
    mssql_conn = pyodbc.connect(MSSQL_DSN)
    mssql_cur = mssql_conn.cursor()

    # Fetch canonical positions from Postgres
    pg_cur.execute(
        """
        SELECT
            valuation_date,
            account_code,
            instrument_isin,
            ticker,
            asset_class,
            region,
            sector,
            position_qty,
            avg_price_ccy,
            currency,
            notional_ccy,
            notional_usd
        FROM export.daily_positions
        WHERE valuation_date = %s
        """,
        (valuation_date,),
    )

    rows = pg_cur.fetchall()
    columns = [desc[0] for desc in pg_cur.description]

    insert_sql = """
        INSERT INTO core.Stg_PositionImport (
            ValuationDate, AccountCode, InstrumentIsin, Ticker,
            AssetClass, Region, Sector,
            PositionQty, AvgPriceCcy, Currency,
            NotionalCcy, NotionalUsd,
            RiskBucket, SourceSystem
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    for row in rows:
        data = dict(zip(columns, row))
        bucket = classify_risk(
            {
                "asset_class": data["asset_class"],
                "region": data["region"],
                "notional_usd": float(data["notional_usd"] or 0),
            },
            risk_rules,
        )

        params = (
            data["valuation_date"],
            data["account_code"],
            data["instrument_isin"],
            data["ticker"],
            data["asset_class"],
            data["region"],
            data["sector"],
            data["position_qty"],
            data["avg_price_ccy"],
            data["currency"],
            data["notional_ccy"],
            data["notional_usd"],
            bucket,
            "POSTGRES_LANDING",
        )
        mssql_cur.execute(insert_sql, params)

    mssql_conn.commit()

    pg_cur.close()
    pg_conn.close()
    mssql_cur.close()
    mssql_conn.close()

if __name__ == "__main__":
    main(date(2025, 1, 1))
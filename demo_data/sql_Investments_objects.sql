-- sqlserver_investments_example.sql
-- Core investment warehouse (SQL Server / T-SQL)

-- =========================
-- 1. Schema & staging
-- =========================
CREATE SCHEMA core;
GO

CREATE TABLE core.Stg_PositionImport (
    ImportId          INT IDENTITY(1,1) PRIMARY KEY,
    ValuationDate     DATE,
    AccountCode       NVARCHAR(50),
    InstrumentIsin    NVARCHAR(20),
    Ticker            NVARCHAR(50),
    AssetClass        NVARCHAR(50),
    Region            NVARCHAR(50),
    Sector            NVARCHAR(100),
    PositionQty       DECIMAL(20,4),
    AvgPriceCcy       DECIMAL(18,6),
    Currency          NVARCHAR(10),
    NotionalCcy       DECIMAL(30,10),
    NotionalUsd       DECIMAL(30,10),
    RiskBucket        NVARCHAR(50),
    SourceSystem      NVARCHAR(50)      -- e.g. 'POSTGRES_LANDING'
);
GO

-- =========================
-- 2. Dimensions
-- =========================
CREATE TABLE core.DimAccount (
    AccountKey     INT IDENTITY(1,1) PRIMARY KEY,
    AccountCode    NVARCHAR(50) UNIQUE,
    AccountName    NVARCHAR(200),
    SourceSystem   NVARCHAR(50)
);

CREATE TABLE core.DimInstrument (
    InstrumentKey   INT IDENTITY(1,1) PRIMARY KEY,
    InstrumentIsin  NVARCHAR(20) UNIQUE,
    Ticker          NVARCHAR(50),
    AssetClass      NVARCHAR(50),
    Region          NVARCHAR(50),
    Sector          NVARCHAR(100),
    Currency        NVARCHAR(10)
);
GO

-- =========================
-- 3. Fact tables & history
-- =========================
CREATE TABLE core.FactPosition (
    PositionKey     INT IDENTITY(1,1) PRIMARY KEY,
    ValuationDate   DATE NOT NULL,
    AccountKey      INT NOT NULL REFERENCES core.DimAccount(AccountKey),
    InstrumentKey   INT NOT NULL REFERENCES core.DimInstrument(InstrumentKey),
    PositionQty     DECIMAL(20,4) NOT NULL,
    NotionalUsd     DECIMAL(30,10) NOT NULL,
    RiskBucket      NVARCHAR(50),
    SourceSystem    NVARCHAR(50)
);

CREATE TABLE core.FactDailyPnL (
    PnLKey          INT IDENTITY(1,1) PRIMARY KEY,
    ValuationDate   DATE NOT NULL,
    AccountKey      INT NOT NULL,
    InstrumentKey   INT NOT NULL,
    StartNotionalUsd DECIMAL(30,10),
    EndNotionalUsd   DECIMAL(30,10),
    PnLUsd           DECIMAL(30,10)
);

CREATE TABLE core.PositionHistory (
    HistoryId       INT IDENTITY(1,1) PRIMARY KEY,
    PositionKey     INT,
    ValuationDate   DATE,
    AccountKey      INT,
    InstrumentKey   INT,
    PositionQty     DECIMAL(20,4),
    NotionalUsd     DECIMAL(30,10),
    RiskBucket      NVARCHAR(50),
    SnapshotTs      DATETIME2 DEFAULT SYSDATETIME()
);
GO

-- =========================
-- 4. Helper function: PnL
-- =========================
CREATE OR ALTER FUNCTION core.fn_CalcPnL (
    @StartNotionalUsd DECIMAL(30,10),
    @EndNotionalUsd   DECIMAL(30,10)
)
RETURNS DECIMAL(30,10)
AS
BEGIN
    RETURN ISNULL(@EndNotionalUsd, 0) - ISNULL(@StartNotionalUsd, 0);
END;
GO

-- =========================
-- 5. Upsert dimensions from staging
-- =========================
CREATE OR ALTER PROCEDURE core.usp_UpsertDimAccount
AS
BEGIN
    SET NOCOUNT ON;

    MERGE core.DimAccount AS tgt
    USING (
        SELECT DISTINCT AccountCode, SourceSystem
        FROM core.Stg_PositionImport
    ) AS src
        ON tgt.AccountCode = src.AccountCode
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (AccountCode, AccountName, SourceSystem)
        VALUES (src.AccountCode, src.AccountCode, src.SourceSystem);
END;
GO

CREATE OR ALTER PROCEDURE core.usp_UpsertDimInstrument
AS
BEGIN
    SET NOCOUNT ON;

    MERGE core.DimInstrument AS tgt
    USING (
        SELECT DISTINCT InstrumentIsin, Ticker, AssetClass, Region, Sector, Currency
        FROM core.Stg_PositionImport
    ) AS src
        ON tgt.InstrumentIsin = src.InstrumentIsin
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (InstrumentIsin, Ticker, AssetClass, Region, Sector, Currency)
        VALUES (src.InstrumentIsin, src.Ticker, src.AssetClass, src.Region, src.Sector, src.Currency);
END;
GO

-- =========================
-- 6. Load FactPosition and FactDailyPnL
-- =========================
CREATE OR ALTER PROCEDURE core.usp_LoadFactPosition
    @ValuationDate DATE
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO core.FactPosition (
        ValuationDate, AccountKey, InstrumentKey,
        PositionQty, NotionalUsd, RiskBucket, SourceSystem
    )
    SELECT
        s.ValuationDate,
        a.AccountKey,
        i.InstrumentKey,
        s.PositionQty,
        s.NotionalUsd,
        s.RiskBucket,
        s.SourceSystem
    FROM core.Stg_PositionImport s
    JOIN core.DimAccount   a ON a.AccountCode     = s.AccountCode
    JOIN core.DimInstrument i ON i.InstrumentIsin = s.InstrumentIsin
    WHERE s.ValuationDate = @ValuationDate;
END;
GO

CREATE OR ALTER PROCEDURE core.usp_LoadFactDailyPnL
    @ValuationDate DATE
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @PrevDate DATE;
    SET @PrevDate = DATEADD(DAY, -1, @ValuationDate);

    INSERT INTO core.FactDailyPnL (
        ValuationDate, AccountKey, InstrumentKey,
        StartNotionalUsd, EndNotionalUsd, PnLUsd
    )
    SELECT
        @ValuationDate,
        f_today.AccountKey,
        f_today.InstrumentKey,
        f_prev.NotionalUsd      AS StartNotionalUsd,
        f_today.NotionalUsd     AS EndNotionalUsd,
        core.fn_CalcPnL(f_prev.NotionalUsd, f_today.NotionalUsd) AS PnLUsd
    FROM core.FactPosition f_today
    LEFT JOIN core.FactPosition f_prev
        ON f_prev.ValuationDate = @PrevDate
       AND f_prev.AccountKey    = f_today.AccountKey
       AND f_prev.InstrumentKey = f_today.InstrumentKey
    WHERE f_today.ValuationDate = @ValuationDate;
END;
GO

-- =========================
-- 7. Trigger: Position history
-- =========================
CREATE OR ALTER TRIGGER core.trg_FactPosition_InsertHistory
ON core.FactPosition
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO core.PositionHistory (
        PositionKey, ValuationDate, AccountKey, InstrumentKey,
        PositionQty, NotionalUsd, RiskBucket
    )
    SELECT
        i.PositionKey,
        i.ValuationDate,
        i.AccountKey,
        i.InstrumentKey,
        i.PositionQty,
        i.NotionalUsd,
        i.RiskBucket
    FROM inserted i;
END;
GO

-- =========================
-- 8. Orchestration
-- =========================
CREATE OR ALTER PROCEDURE core.usp_RunPositionLoad
    @ValuationDate DATE
AS
BEGIN
    SET NOCOUNT ON;

    EXEC core.usp_UpsertDimAccount;
    EXEC core.usp_UpsertDimInstrument;
    EXEC core.usp_LoadFactPosition @ValuationDate = @ValuationDate;
    EXEC core.usp_LoadFactDailyPnL @ValuationDate = @ValuationDate;
END;
GO

-- Example run after Python has loaded Stg_PositionImport:
-- EXEC core.usp_RunPositionLoad @ValuationDate = '2025-01-01';
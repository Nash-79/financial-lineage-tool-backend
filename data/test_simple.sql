-- Simple test query for ingestion
-- This creates a view that joins customer and order data

CREATE VIEW customer_orders AS
SELECT
    c.CustomerID,
    c.FirstName,
    c.LastName,
    o.SalesOrderID,
    o.OrderDate,
    o.TotalDue
FROM SalesLT.Customer c
INNER JOIN SalesLT.SalesOrderHeader o
    ON c.CustomerID = o.CustomerID
WHERE o.OrderDate >= '2020-01-01';

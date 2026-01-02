-- ============================================
-- Object Type: PROCEDURE
-- Object Name: [SalesLT].[MultipleResultsColors]
-- Source File: AdventureWorksLT-All.sql
-- Separated On: 2025-12-08 18:51:51
-- Dialect: tsql
-- ============================================

er]  WITH CHECK ADD  CONSTRAINT [FK_SalesOrderHeader_Customer_CustomerID] FOREIGN KEY([CustomerID])
REFERENCES [SalesLT].[Customer] ([CustomerID])
G

-- ============================================
-- Object Type: PROCEDURE
-- Object Name: [SalesLT].[Product_Search]
-- Source File: AdventureWorksLT-All.sql
-- Separated On: 2025-12-08 18:51:51
-- Dialect: tsql
-- ============================================

R TABLE [SalesLT].[SalesOrderHeader]  WITH CHECK ADD  CONSTRAINT [CK_SalesOrderHeader_SubTotal] CHECK  (([SubTotal]>=(0.00)))
G

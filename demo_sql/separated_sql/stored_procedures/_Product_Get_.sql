-- ============================================
-- Object Type: PROCEDURE
-- Object Name: [SalesLT].[Product_Get]
-- Source File: AdventureWorksLT-All.sql
-- Separated On: 2025-12-08 18:51:51
-- Dialect: tsql
-- ============================================

CHECK ADD  CONSTRAINT [CK_SalesOrderDetail_OrderQty] CHECK  (([OrderQty]>(0)))
G

-- ============================================
-- Object Type: PROCEDURE
-- Object Name: [SalesLT].[SalesOrderDetail_GetAll]
-- Source File: AdventureWorksLT-All.sql
-- Separated On: 2025-12-08 18:51:51
-- Dialect: tsql
-- ============================================

Count(*) FROM SalesLT.Product
    WHERE (@Name IS NULL OR Name LIKE @Name + '%') 
    AND   (@ProductNumber IS NULL OR ProductNumber LIKE @ProductNumber + '%')
    AND   (@BeginningCost IS NULL OR StandardCost >= @BeginningCost)
	AND   (@EndingCost IS NULL OR StandardCost <= @EndingCost)
END
G

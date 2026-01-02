-- ============================================
-- Object Type: TABLE
-- Object Name: [SalesLT].[Product]
-- Source File: AdventureWorksLT-All.sql
-- Separated On: 2025-12-08 18:51:51
-- Dialect: tsql
-- ============================================

ALL

		SELECT C.[ParentProductCategoryID], C.[ProductCategoryID], C.[Name]
		FROM SalesLT.ProductCategory AS C
		INNER JOIN CategoryCTE AS BC ON BC.ProductCategoryID = C.ParentProductCategoryID
	)

	INSERT INTO @retCategoryInformation
	SELECT PC.[Name] AS [ParentProductCategoryName], CCTE.[Name] as [ProductCategoryName], CCTE.[ProductCategoryID]  
	FROM CategoryCTE AS CCTE
	JOIN SalesLT.ProductCategory AS PC 
	ON PC.[ProductCategoryID] = CCTE.[ParentProductCategoryID];

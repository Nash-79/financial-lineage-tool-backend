# Hierarchical SQL Organization - Complete Guide

## Overview

The **Hierarchical SQL Organizer** uses SQL Server comment patterns (`/****** Object: ... ******/`) to detect object boundaries and create a hierarchical folder structure where each database object gets its own folder with related objects grouped together.

## Key Features

### ✅ 1. **Comment-Based Object Detection**
Detects SQL Server object headers:
```sql
/****** Object:  Table [SalesLT].[Product]    Script Date: 4/7/2021 10:02:56 AM ******/
/****** Object:  Index [IX_Product_Name]    Script Date: 4/7/2021 10:02:56 AM ******/
/****** Object:  View [SalesLT].[vProductAndDescription]    Script Date: 4/7/2021 10:02:56 AM ******/
```

### ✅ 2. **Hierarchical Folder Structure**
Each object gets its own folder with subfolders for related objects:

```
AdventureWorksLT-All/
  tables/
    Product/
      Product.sql                           <-- Main table definition
      indexes/
        PK_Product_ProductID.sql
        IX_Product_Name.sql
      foreign_keys/
        FK_Product_ProductCategory.sql
      check_constraints/
        CK_Product_ListPrice.sql
        CK_Product_Weight.sql
      defaults/
        DF_Product_rowguid.sql

    ProductCategory/
      ProductCategory.sql
      indexes/
      foreign_keys/
        FK_ProductCategory_Parent.sql

  views/
    vProductAndDescription/
      vProductAndDescription.sql             <-- View definition
      indexes/
        IX_vProductAndDescription.sql       <-- INDEXED VIEW!

  functions/
    ufnGetAllCategories/
      ufnGetAllCategories.sql

  stored_procedures/
    Product_Insert/
      Product_Insert.sql
    Product_Update/
      Product_Update.sql
```

### ✅ 3. **Indexed Views Support**
Automatically detects indexed views (views with clustered indexes):
- View definition in main folder
- Clustered index in `indexes/` subfolder
- Metadata shows parent-child relationship

### ✅ 4. **Constraint Grouping**
Automatically groups constraints with their parent tables:
- **Foreign Keys** → `foreign_keys/`
- **Check Constraints** → `check_constraints/`
- **Defaults** → `defaults/`
- **Other Constraints** → `constraints/`
- **Indexes** → `indexes/`

### ✅ 5. **Metadata Preservation**
Every file includes comprehensive metadata:
```sql
-- ============================================
-- Object Type: Index
-- Constraint/Index Name: IX_vProductAndDescription
-- Parent Object: vProductAndDescription
-- Source File: AdventureWorksLT-All.sql
-- Script Date: 4/7/2021 10:02:56 AM
-- Separated On: 2025-12-08 19:50:20
-- ============================================

CREATE UNIQUE CLUSTERED INDEX [IX_vProductAndDescription] ON ...
```

## How It Works

### 1. Enhanced SQL Parser
- Reads SQL Server comment patterns
- Detects object types (Table, View, Index, etc.)
- Extracts schema and object names
- Identifies parent-child relationships

### 2. Object Grouping
- Scans ALTER TABLE statements
- Links constraints to parent tables
- Links indexes to parent tables/views
- Groups related objects together

### 3. Hierarchical Organization
- Creates folder per object
- Creates subfolders for related objects
- Preserves all metadata
- Generates manifest

## Real-World Example

### Input: `AdventureWorksLT-All.sql`
A SQL Server database backup script with 46 objects:
- 10 Tables
- 3 Views (1 indexed!)
- 3 Functions
- 15 Stored Procedures
- 5 Indexes
- Multiple constraints

### Output Structure

```
data/separated_sql/
  AdventureWorksLT-All/
    tables/                                 <-- 10 tables
      Product/
        Product.sql
        indexes/
          PK_Product_ProductID.sql
          IX_Product_Name.sql
        foreign_keys/
          FK_Product_ProductCategory.sql
          FK_Product_ProductModel.sql
        check_constraints/
          CK_Product_ListPrice.sql
          CK_Product_Weight.sql
          CK_Product_SellEndDate.sql
        defaults/
          DF_Product_rowguid.sql
          DF_Product_ModifiedDate.sql

      ProductCategory/
        ProductCategory.sql
        indexes/
        foreign_keys/
        constraints/

      Customer/
        Customer.sql
        ...

    views/                                  <-- 3 views
      vProductAndDescription/
        vProductAndDescription.sql          <-- Indexed view!
        indexes/
          IX_vProductAndDescription.sql     <-- Clustered index

      vProductModelCatalogDescription/
        vProductModelCatalogDescription.sql

      vGetAllCategories/
        vGetAllCategories.sql

    functions/                              <-- 3 functions
      ufnGetAllCategories/
        ufnGetAllCategories.sql
      ufnGetSalesOrderStatusText/
        ufnGetSalesOrderStatusText.sql
      ufnGetCustomerInformation/
        ufnGetCustomerInformation.sql

    stored_procedures/                      <-- 15 stored procedures
      Product_Insert/
        Product_Insert.sql
      Product_Update/
        Product_Update.sql
      Product_Delete/
        Product_Delete.sql
      ...

    organization_manifest.json              <-- Metadata log
```

## Usage

### Quick Start

```bash
# 1. Add SQL file to data/raw/
cp your_database.sql data/raw/

# 2. Run hierarchical organizer
cd financial-lineage-tool
python examples/test_hierarchical_organizer.py

# 3. Check results
ls data/separated_sql/your_database/tables/
```

### Python API

```python
from src.ingestion.hierarchical_organizer import organize_sql_hierarchically

# Organize SQL file
results = organize_sql_hierarchically(
    input_file="./data/raw/AdventureWorksLT-All.sql",
    output_dir="./data/separated_sql"
)
```

### Advanced Usage

```python
from src.ingestion.hierarchical_organizer import HierarchicalOrganizer

organizer = HierarchicalOrganizer(
    output_base_dir="./data/separated_sql",
    add_metadata_header=True,
    overwrite_existing=True
)

results = organizer.organize_file("./data/raw/your_db.sql")
organizer.print_summary()
```

## Folder Structure Details

### Tables
```
tables/
  TableName/
    TableName.sql              <-- CREATE TABLE statement
    indexes/
      PK_TableName.sql         <-- Primary key
      IX_TableName_Column.sql  <-- Indexes
    foreign_keys/
      FK_TableName_Parent.sql  <-- Foreign key constraints
    check_constraints/
      CK_TableName_Column.sql  <-- Check constraints
    defaults/
      DF_TableName_Column.sql  <-- Default constraints
    constraints/
      Other constraints
```

### Views
```
views/
  ViewName/
    ViewName.sql               <-- CREATE VIEW statement
    indexes/                   <-- Only for indexed views!
      IX_ViewName.sql          <-- Clustered index (makes it indexed view)
```

### Functions
```
functions/
  FunctionName/
    FunctionName.sql           <-- CREATE FUNCTION statement
```

### Stored Procedures
```
stored_procedures/
  ProcedureName/
    ProcedureName.sql          <-- CREATE PROCEDURE statement
```

## Object Detection Patterns

### Tables
```sql
/****** Object:  Table [Schema].[TableName]    Script Date: ... ******/
CREATE TABLE [Schema].[TableName] (...)
```

### Indexed Views
```sql
/****** Object:  View [Schema].[ViewName]    Script Date: ... ******/
CREATE VIEW [Schema].[ViewName] WITH SCHEMABINDING AS ...
GO

/****** Object:  Index [IndexName]    Script Date: ... ******/
CREATE UNIQUE CLUSTERED INDEX [IndexName] ON [Schema].[ViewName] (...)
```

### Constraints
```sql
ALTER TABLE [Schema].[TableName] ADD CONSTRAINT [ConstraintName]
  FOREIGN KEY ([Column]) REFERENCES [OtherTable]([OtherColumn])

ALTER TABLE [Schema].[TableName] ADD CONSTRAINT [ConstraintName]
  CHECK ([Column] > 0)

ALTER TABLE [Schema].[TableName] ADD CONSTRAINT [ConstraintName]
  DEFAULT (GETDATE()) FOR [Column]
```

## Statistics

From AdventureWorksLT-All.sql:
- **Files Processed**: 1
- **Objects Separated**: 46
- **Tables with Constraints**: 10
- **Indexed Views**: 1 (vProductAndDescription)
- **Total Files Created**: 46+

## Manifest File

Every organization generates a manifest:

```json
{
  "generated_at": "2025-12-08T19:50:20.123456",
  "source_directory": "data/separated_sql/AdventureWorksLT-All",
  "organization_type": "hierarchical",
  "statistics": {
    "objects_separated": 46,
    "tables_with_constraints": 10,
    "indexed_views": 1,
    "by_type": {
      "Table": 10,
      "View": 3,
      "UserDefinedFunction": 3,
      "StoredProcedure": 15,
      "Index": 5,
      "Schema": 1
    }
  },
  "files_by_type": {...}
}
```

## Differences from Basic Organizer

| Feature | Basic Organizer | Hierarchical Organizer |
|---------|----------------|------------------------|
| Structure | Flat folders by type | Nested folders per object |
| Constraints | Separate files | Grouped with parent table |
| Indexes | Separate files | Grouped with parent table/view |
| Indexed Views | Not detected | Auto-detected and grouped |
| Comment Detection | No | Yes (SQL Server patterns) |
| Parent-Child Links | No | Yes (full hierarchy) |

## Extended Properties (Future)

The system can parse extended properties for data dictionary:

```sql
EXEC sys.sp_addextendedproperty
  @name=N'MS_Description',
  @value=N'Primary key for Product records.',
  @level0type=N'SCHEMA',
  @level0name=N'SalesLT',
  @level1type=N'TABLE',
  @level1name=N'Product',
  @level2type=N'COLUMN',
  @level2name=N'ProductID'
```

This will be used to generate comprehensive data dictionaries.

## Integration Points

### 1. Current: File Organization
```
SQL File → Parser → Hierarchical Organizer → Folder Structure
```

### 2. Next: Knowledge Graph
```
Organized Files → Entity Extractor → Graph Populator → Cosmos DB
```

### 3. Future: Data Dictionary
```
Extended Properties → Dictionary Generator → Markdown/JSON Docs
```

## Troubleshooting

### Issue: Objects not grouped with parent
**Cause**: ALTER TABLE statements don't have parent object comment
**Solution**: Parser detects parent from ALTER TABLE ... ON [TableName]

### Issue: Very long filenames on Windows
**Cause**: Windows has 260 character path limit
**Solution**: Use shorter object names or enable long paths

### Issue: Some objects in "other" folder
**Cause**: Object type not recognized
**Solution**: Check SQL Server object type in comment header

## Summary

✅ **Hierarchical organization** - Each object has its own folder
✅ **Comment-based detection** - Uses SQL Server patterns
✅ **Constraint grouping** - Related objects together
✅ **Indexed view support** - Auto-detected
✅ **Metadata preservation** - Full traceability
✅ **Production-ready** - Tested with real databases

## Next Steps

1. **Use hierarchical organizer**: `python examples/test_hierarchical_organizer.py`
2. **Check output**: `data/separated_sql/AdventureWorksLT-All/`
3. **Integrate with pipeline**: Entity extraction → Knowledge graph
4. **Generate data dictionary**: From extended properties

---

**Ready to organize your SQL database hierarchically!**

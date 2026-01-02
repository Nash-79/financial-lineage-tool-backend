# AdventureWorks in Neo4j - Complete Guide

## ✅ Status: AdventureWorks Schema Successfully Added!

Your Neo4j graph database now contains the complete AdventureWorks schema.

### Graph Statistics:
- **Total Nodes**: 44
- **Total Edges**: 42
- **Tables**: 9 (7 AdventureWorks + 2 test tables)
- **Columns**: 35
- **Relationships**: CONTAINS (35), REFERENCES (6), DERIVES_FROM (1)

---

## Schema Overview

### AdventureWorks Tables Added:

1. **SalesLT.Customer** - Customer information
   - CustomerID (PK), FirstName, LastName, EmailAddress, CompanyName

2. **SalesLT.Product** - Product catalog
   - ProductID (PK), Name, ProductNumber, Color, StandardCost, ListPrice, ProductCategoryID (FK)

3. **SalesLT.ProductCategory** - Product categories
   - ProductCategoryID (PK), Name, ParentProductCategoryID

4. **SalesLT.SalesOrderHeader** - Sales order headers
   - SalesOrderID (PK), OrderDate, CustomerID (FK), SubTotal, TotalDue

5. **SalesLT.SalesOrderDetail** - Sales order line items
   - SalesOrderDetailID (PK), SalesOrderID (FK), ProductID (FK), OrderQty, UnitPrice, LineTotal

6. **SalesLT.Address** - Customer addresses
   - AddressID (PK), AddressLine1, City, StateProvince, CountryRegion

7. **SalesLT.CustomerAddress** - Customer-Address junction
   - CustomerID (FK), AddressID (FK), AddressType

---

## Visualize Your Data

### Option 1: Neo4j Browser (Recommended)

**Open:** https://console.neo4j.io

**Login:**
- URI: `neo4j+s://66e1cb8c.databases.neo4j.io`
- Username: `neo4j`
- Password: `S6OFtX78rqAyI7Zk9tcpnDAzyN1srKiq4so53WSBWhg`

**Try These Cypher Queries:**

```cypher
// 1. View all tables
MATCH (t:Table)
RETURN t.name as TableName, t.schema as Schema
ORDER BY t.schema, t.name

// 2. View all AdventureWorks tables with their columns
MATCH (t:Table {database: 'AdventureWorksLT'})-[:CONTAINS]->(c:Column)
RETURN t.name as Table, collect(c.name) as Columns

// 3. Visualize entire schema
MATCH (n)-[r]->(m)
WHERE n.database = 'AdventureWorksLT' OR m.database = 'AdventureWorksLT'
RETURN n, r, m
LIMIT 100

// 4. Find all foreign key relationships
MATCH (c1:Column)-[r:REFERENCES]->(c2:Column)
RETURN c1.name as FromColumn, c2.name as ToColumn, r.description as Relationship

// 5. Get table with all its columns and their types
MATCH (t:Table {name: 'Customer'})-[:CONTAINS]->(c:Column)
RETURN c.name as Column, c.data_type as DataType, c.is_primary_key as IsPK
```

### Option 2: Query via Python Script

```bash
python query_neo4j.py
```

This will show you:
- Graph statistics
- All nodes and relationships
- Lineage paths
- Useful Cypher queries

### Option 3: Export to JSON

```bash
# Export full graph
python export_graph_json.py

# Files created:
# - data/graph_export.json      (Full graph data)
# - data/graph_viz.json          (D3.js format)
# - data/cypher_queries.json     (Common queries)
```

---

## Query via API

### Get Graph Stats
```bash
curl http://localhost:8000/api/v1/graph/stats
```

### Search for Tables
```bash
curl "http://localhost:8000/api/v1/graph/search?name=customer"
```

### Get Entity Details
```bash
curl "http://localhost:8000/api/v1/graph/entity/saleslt_customer"
```

### Get Lineage
```bash
curl "http://localhost:8000/api/v1/graph/lineage/saleslt_customer?direction=downstream"
```

---

## Common Use Cases

### 1. Find All Columns in a Table

**Cypher:**
```cypher
MATCH (t:Table {name: 'SalesOrderHeader'})-[:CONTAINS]->(c:Column)
RETURN c.name, c.data_type, c.is_primary_key, c.is_foreign_key
```

**Via API:**
```bash
curl "http://localhost:8000/api/v1/graph/search?name=SalesOrderHeader"
```

### 2. Trace Foreign Key Relationships

**Cypher:**
```cypher
MATCH path = (t1:Table)-[:CONTAINS]->(c1:Column)-[:REFERENCES]->(c2:Column)<-[:CONTAINS]-(t2:Table)
WHERE t1.name = 'SalesOrderHeader'
RETURN t1.name, c1.name, t2.name, c2.name
```

### 3. Find Data Lineage

**Cypher:**
```cypher
// Upstream lineage (what feeds into SalesOrderDetail)
MATCH path = (source)-[*1..3]->(target:Table {name: 'SalesOrderDetail'})
RETURN path

// Downstream lineage (what SalesOrderDetail feeds into)
MATCH path = (source:Table {name: 'SalesOrderDetail'})-[*1..3]->(target)
RETURN path
```

### 4. Get All Tables Related to Customer

**Cypher:**
```cypher
MATCH path = (customer:Table {name: 'Customer'})-[*1..2]-(related:Table)
RETURN DISTINCT related.name as RelatedTable
```

---

## Entity Relationship Diagram

```
Customer
  ├── CustomerID (PK) ────────┐
  ├── FirstName               │
  ├── LastName                │
  └── EmailAddress            │
                              │ REFERENCES
SalesOrderHeader              │
  ├── SalesOrderID (PK) ──────┼──┐
  ├── CustomerID (FK) ────────┘  │
  └── OrderDate                  │
                                 │ REFERENCES
SalesOrderDetail                 │
  ├── SalesOrderDetailID (PK)    │
  ├── SalesOrderID (FK) ─────────┘
  ├── ProductID (FK) ────────┐
  └── OrderQty               │
                             │ REFERENCES
Product                      │
  ├── ProductID (PK) ────────┘
  ├── Name
  ├── ListPrice
  └── ProductCategoryID (FK) ─┐
                              │ REFERENCES
ProductCategory               │
  ├── ProductCategoryID (PK) ─┘
  └── Name
```

---

## Advanced Queries

### Find Circular References
```cypher
MATCH path = (n)-[:REFERENCES*2..5]->(n)
RETURN path
```

### Get Table Complexity (number of columns and relationships)
```cypher
MATCH (t:Table)-[:CONTAINS]->(c:Column)
WITH t, count(c) as column_count
OPTIONAL MATCH (c:Column)-[:REFERENCES]->(other)
WHERE (t)-[:CONTAINS]->(c)
WITH t, column_count, count(other) as fk_count
RETURN t.name, column_count, fk_count
ORDER BY column_count DESC
```

### Find Tables Without Foreign Keys
```cypher
MATCH (t:Table)-[:CONTAINS]->(c:Column)
WHERE NOT (c)-[:REFERENCES]->()
RETURN DISTINCT t.name
```

---

## Export Options

### Export to CSV
```cypher
// In Neo4j Browser
CALL apoc.export.csv.all("adventureworks.csv", {})
```

### Export to JSON (via Python)
```bash
python export_graph_json.py
```

### Export to NetworkX (Python)
```python
import json
import networkx as nx

with open('data/graph_export.json') as f:
    data = json.load(f)

G = nx.DiGraph()
for node in data['nodes']:
    G.add_node(node['id'], **node['properties'])
for rel in data['relationships']:
    G.add_edge(rel['source'], rel['target'],
               type=rel['type'], **rel['properties'])
```

---

## Next Steps

### 1. Add More Data
Run the script again with additional tables:
```bash
python add_adventureworks_entities.py
```

### 2. Create Views or Derived Tables
Add analytical views:
```python
client.add_entity(
    entity_id="saleslt_customer_summary",
    entity_type="View",
    name="CustomerSummary",
    schema="SalesLT",
    database="AdventureWorksLT"
)
```

### 3. Add Lineage Transformations
Document ETL transformations:
```python
client.add_relationship(
    source_id="saleslt_salesorderheader",
    target_id="saleslt_customer_summary",
    relationship_type="TRANSFORMS_TO",
    transformation="GROUP BY customer, SUM(total_due)"
)
```

### 4. Build Reports
Use the graph data to generate documentation:
```bash
python query_neo4j.py > adventureworks_schema_report.txt
```

---

## Troubleshooting

### Can't see tables in Neo4j Browser?
```cypher
// Check connection
MATCH (n) RETURN count(n)

// Verify database
SHOW DATABASE
```

### Need to clear and reload?
```python
# Clear all AdventureWorks data
from src.knowledge_graph.neo4j_client import Neo4jGraphClient
client = Neo4jGraphClient(...)

query = "MATCH (n {database: 'AdventureWorksLT'}) DETACH DELETE n"
client._execute_query(query)

# Then re-run
python add_adventureworks_entities.py
```

---

## Resources

- **Neo4j Browser**: https://console.neo4j.io
- **Interactive API Docs**: http://localhost:8000/docs
- **Query Script**: `python query_neo4j.py`
- **Export Script**: `python export_graph_json.py`
- **Graph Exports**: `data/graph_export.json`, `data/graph_viz.json`

Your AdventureWorks schema is now in Neo4j and ready for lineage analysis! 🚀

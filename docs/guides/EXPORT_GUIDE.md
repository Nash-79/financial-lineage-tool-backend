# JSON Export Guide

This guide explains how to export graph data and embeddings to JSON format for analysis, visualization, or integration with other systems.

## Available Export Scripts

### 1. Graph Export (`export_graph_json.py`)

Exports Neo4j graph data to JSON format.

**Run:**
```bash
python export_graph_json.py
```

**Outputs:**

#### `data/graph_export.json` - Full Graph Data
Complete graph structure with all nodes and relationships.

```json
{
  "metadata": {
    "export_timestamp": "2025-12-06T17:00:59.049423",
    "database": "neo4j",
    "statistics": {
      "nodes": 3,
      "edges": 2,
      "node_types": {"Table": 2, "Column": 1},
      "relationship_types": {"CONTAINS": 1, "DERIVES_FROM": 1}
    }
  },
  "nodes": [
    {
      "id": "test_table_customers",
      "labels": ["Table"],
      "properties": {
        "schema": "public",
        "database": "production",
        "name": "customers"
      }
    }
  ],
  "relationships": [
    {
      "source": "test_table_customers",
      "target": "test_column_customer_id",
      "type": "CONTAINS",
      "properties": {"position": 1}
    }
  ]
}
```

#### `data/graph_viz.json` - Visualization Format
D3.js-compatible format for graph visualization.

```json
{
  "nodes": [
    {
      "id": "test_table_customers",
      "name": "customers",
      "group": "Table",
      "properties": {...}
    }
  ],
  "links": [
    {
      "source": 0,
      "target": 2,
      "type": "CONTAINS",
      "properties": {...}
    }
  ]
}
```

#### `data/cypher_queries.json` - Common Cypher Queries
Reusable Cypher queries for Neo4j.

```json
{
  "get_all_tables": {
    "description": "Get all table nodes",
    "cypher": "MATCH (n:Table) RETURN n"
  },
  "get_upstream_lineage": {
    "description": "Get upstream lineage for an entity",
    "cypher": "MATCH path = (source)-[:DERIVES_FROM|TRANSFORMS_TO*1..5]->(target {id: $entity_id}) RETURN path",
    "parameters": {"entity_id": "entity_identifier"}
  }
}
```

---

### 2. Embeddings Export (`export_embeddings_json.py`)

Generates and exports embeddings using Ollama.

**Run:**
```bash
python export_embeddings_json.py
```

**Outputs:**

#### `data/sample_embeddings.json` - Sample Text Embeddings
Embeddings for sample text descriptions.

```json
{
  "metadata": {
    "total_items": 4,
    "successful": 4,
    "failed": 0,
    "model": "nomic-embed-text",
    "embedding_dimension": 768
  },
  "embeddings": [
    {
      "id": 0,
      "text": "Customer table containing customer information",
      "embedding": [0.123, -0.456, 0.789, ...],
      "embedding_dimension": 768,
      "model": "nomic-embed-text"
    }
  ]
}
```

#### `data/sql_embeddings.json` - SQL Statement Embeddings
Embeddings for SQL CREATE/SELECT statements.

```json
{
  "metadata": {
    "source_file": "data/sample_financial_schema.sql",
    "total_statements": 7,
    "successful": 7,
    "model": "nomic-embed-text"
  },
  "embeddings": [
    {
      "id": 0,
      "sql": "CREATE TABLE raw.customers (...)",
      "embedding": [...],
      "embedding_dimension": 768
    }
  ]
}
```

#### `data/entity_embeddings.json` - Neo4j Entity Embeddings
Embeddings for all entities in the Neo4j graph.

```json
{
  "metadata": {
    "total_entities": 3,
    "successful": 3,
    "model": "nomic-embed-text"
  },
  "embeddings": [
    {
      "entity_id": "test_table_customers",
      "entity_name": "customers",
      "entity_type": "Table",
      "text_representation": "Table: customers (schema=public, database=production)",
      "embedding": [...],
      "properties": {...}
    }
  ]
}
```

---

## Use Cases

### 1. **Graph Visualization**
Use `graph_viz.json` with D3.js, Cytoscape, or similar libraries:

```javascript
// D3.js Force-Directed Graph
d3.json("data/graph_viz.json").then(data => {
  const simulation = d3.forceSimulation(data.nodes)
    .force("link", d3.forceLink(data.links).id(d => d.id))
    .force("charge", d3.forceManyBody())
    .force("center", d3.forceCenter(width / 2, height / 2));
});
```

### 2. **Semantic Search**
Use embeddings for similarity search:

```python
import json
import numpy as np

# Load embeddings
with open('data/entity_embeddings.json') as f:
    data = json.load(f)

embeddings = [item['embedding'] for item in data['embeddings']]

# Compute similarity
from sklearn.metrics.pairwise import cosine_similarity
similarities = cosine_similarity(embeddings)
```

### 3. **Export to Other Databases**
Use JSON exports to migrate to other graph databases:

```python
# Example: Load into NetworkX
import networkx as nx
import json

with open('data/graph_export.json') as f:
    data = json.load(f)

G = nx.DiGraph()
for node in data['nodes']:
    G.add_node(node['id'], **node['properties'])

for rel in data['relationships']:
    G.add_edge(rel['source'], rel['target'],
               type=rel['type'], **rel['properties'])
```

### 4. **Data Analysis**
Analyze graph structure with pandas:

```python
import pandas as pd
import json

# Load graph
with open('data/graph_export.json') as f:
    data = json.load(f)

# Convert to DataFrame
nodes_df = pd.DataFrame(data['nodes'])
relationships_df = pd.DataFrame(data['relationships'])

# Analyze
print(nodes_df['labels'].value_counts())
print(relationships_df['type'].value_counts())
```

---

## API Endpoints

You can also export via API (if you add these endpoints to `main_local.py`):

```bash
# Export graph
curl http://localhost:8000/api/v1/export/graph > graph.json

# Export embeddings for text
curl -X POST http://localhost:8000/api/v1/export/embeddings \
  -H "Content-Type: application/json" \
  -d '{"texts": ["sample text"]}' > embeddings.json
```

---

## Customization

### Export Specific Entities

Modify `export_graph_json.py` to filter:

```python
# Only export tables
nodes_query = """
MATCH (n:Table)
RETURN n.id as id, labels(n) as labels, properties(n) as properties
"""
```

### Custom Embedding Models

Change the model in `.env`:

```bash
EMBEDDING_MODEL=llama2  # or any other Ollama model
```

### Batch Processing

For large graphs, export in batches:

```python
# Paginated export
offset = 0
batch_size = 1000

while True:
    query = f"""
    MATCH (n)
    RETURN n
    SKIP {offset} LIMIT {batch_size}
    """
    results = client._execute_query(query)
    if not results:
        break
    # Process batch
    offset += batch_size
```

---

## File Sizes

| File | Typical Size | Content |
|------|-------------|---------|
| `graph_export.json` | 1-100 KB | Nodes & relationships |
| `graph_viz.json` | 1-50 KB | Visualization format |
| `entity_embeddings.json` | 50-500 KB | 768-dim vectors per entity |
| `sql_embeddings.json` | 100 KB - 1 MB | SQL statement vectors |

**Note:** Embedding files can be large (768 floats per item ≈ 3KB)

---

## Next Steps

1. **Visualize**: Load `graph_viz.json` in a D3.js web app
2. **Analyze**: Use pandas/numpy to analyze embeddings
3. **Search**: Build semantic search with embedding similarity
4. **Integrate**: Import into other tools (Tableau, PowerBI, Gephi)

For questions or issues, see the main README.

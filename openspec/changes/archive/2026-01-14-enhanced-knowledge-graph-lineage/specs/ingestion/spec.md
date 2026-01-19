## ADDED Requirements

### Requirement: Deep SQL Parsing
The ingestion system SHALL support parsing of complex SQL constructs including MERGE statements and Procedure bodies.

#### Scenario: Parsing MERGE Statements
Given a SQL file with a `MERGE INTO target USING source ...` statement
When the file is ingested
Then the lineage graph should show a valid edge from `source` to `target`
And the relationship type should be `MERGE` or `WRITES_TO`

#### Scenario: Parsing Procedure Dependencies
Given a SQL Procedure that selects from Table A and inserts into Table B
When the procedure is ingested
Then the lineage graph should show `Procdure -> READS -> Table A` and `Procedure -> WRITES -> Table B`

### Requirement: Python-SQL Linking (LLM-Assisted)
The ingestion system SHALL use an LLM to identify SQL execution patterns in Python scripts and link them to database tables.

#### Scenario: ETL Script Linkage
Given a Python script `etl.py` that executes `INSERT INTO target_table`
When the script is ingested and analyzed by the LLM
Then the lineage graph should show `etl.py -> EXECUTES -> target_table`
And the edge should include metadata indicating it was LLM-inferred

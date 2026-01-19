## ADDED Requirements

### Requirement: Knowledge Inference Enrichment
The system SHALL enrich graph nodes with LLM-inferred summaries and logic descriptions.

#### Scenario: Function Summarization
Given a specific SQL function node
When knowledge inference runs
Then the node should have properties `summary` and `logic_description` popualted by the LLM

### Requirement: Vectorized Knowledge Search
The system SHALL support semantic search over inferred knowledge summaries using Qdrant.

#### Scenario: Searching by Business Logic
Given a function `fn_calculate_risk` exists with an inferred description
When a user searches for "risk calculation logic"
Then the system should return `fn_calculate_risk` as a high-ranking result
And the result should be found via vector similarity in Qdrant

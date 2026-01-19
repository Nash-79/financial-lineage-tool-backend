# Spec Delta: Parsed Objects API

## MODIFIED Requirements

### Requirement: Parsed Objects Endpoint Returns Hierarchical Structure

The `GET /api/v1/database/parsed-objects` endpoint SHALL return objects grouped by database and object type.

#### Scenario: Fetching Parsed Objects
Given SQL files have been ingested into Neo4j
When I call `GET /api/v1/database/parsed-objects`
Then the response MUST have a `databases` array at the top level
And each database object MUST contain `name`, `source_file`, `run_id`, and `object_types`
And each `object_types` entry MUST contain `type`, `count`, and `objects` array
And each object MUST include `id`, `name`, `object_type`, `file_path`, `run_id`

#### Scenario: Empty Parsed Objects
Given no SQL files have been ingested
When I call `GET /api/v1/database/parsed-objects`
Then the response MUST be `{ "databases": [] }`
And the response status MUST be 200

#### Scenario: Project Scoping
Given objects exist for multiple projects
When I call `GET /api/v1/database/parsed-objects?project_id=proj1`
Then only objects with `project_id=proj1` SHALL be returned

### Requirement: Object Dependencies Returns Simple String Arrays
The `GET /api/v1/database/objects/{db}/{name}/dependencies` endpoint SHALL return dependency names as string arrays.

#### Scenario: Object With Dependencies
Given an object has upstream and downstream dependencies
When I call `GET /api/v1/database/objects/{db}/{name}/dependencies`
Then the response MUST contain `upstream` as an array of object name strings
And the response MUST contain `downstream` as an array of object name strings
And the response SHALL NOT include `object_name` or `database` fields

#### Scenario: Object Without Dependencies
Given an object has no dependencies
When I call `GET /api/v1/database/objects/{db}/{name}/dependencies`
Then the response MUST be `{ "upstream": [], "downstream": [] }`

#### Scenario: Project Scoping for Dependencies
Given dependencies exist for multiple projects
When I call `GET /api/v1/database/objects/{db}/{name}/dependencies?project_id=proj1`
Then only dependencies within `project_id=proj1` scope SHALL be returned

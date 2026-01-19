# Tasks: Parsed Objects API

## 1. Response Models
- [x] 1.1 Define `ParsedObject` model with all required fields (`id`, `name`, `object_type`, `file_path`, `definition`, `columns`, `run_id`, `created_at`)
- [x] 1.2 Define `ColumnInfo` model for table/view columns
- [x] 1.3 Define `ObjectTypeGroup` model with `type`, `count`, `objects`
- [x] 1.4 Define `ParsedDatabase` model with `name`, `source_file`, `run_id`, `object_types`
- [x] 1.5 Define `ParsedObjectsResponse` wrapper with `databases` array
- [x] 1.6 Define `SimpleDependencyResponse` with `upstream: List[str]`, `downstream: List[str]`

## 2. Parsed Objects Endpoint
- [x] 2.1 Add `project_id` query parameter support
- [x] 2.2 Update Neo4j query to fetch `id`, `definition`, `file_path`, `run_id`, `created_at`, `columns`
- [x] 2.3 Implement label-to-type mapping (`Table`→`TABLE`, `Function`→`FUNCTION`, etc.)
- [x] 2.4 Implement grouping logic: records → databases → object_types → objects
- [x] 2.5 Return `{ databases: [...] }` response format
- [x] 2.6 Handle empty results gracefully (return empty `databases` array)

## 3. Dependencies Endpoint
- [x] 3.1 Add `project_id` query parameter support
- [x] 3.2 Simplify response to `{ upstream: string[], downstream: string[] }`
- [x] 3.3 Remove `object_name` and `database` from response (not needed by frontend)
- [x] 3.4 Return only object names, not full metadata objects

## 4. Testing & Validation
- [x] 4.1 Verify frontend `useParsedObjects` hook works with new response
- [x] 4.2 Verify `useObjectDependencies` hook works with simplified response
- [x] 4.3 Test empty state handling (no objects returns `{ databases: [] }`)
- [x] 4.4 Test project scoping with `project_id` parameter

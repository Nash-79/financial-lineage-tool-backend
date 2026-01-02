# code-organization Specification

## Purpose
TBD - created by archiving change cleanup-and-organize-backend. Update Purpose after archive.
## Requirements
### Requirement: Modular API Structure
The API SHALL be organized into focused router modules with clear separation of concerns.

#### Scenario: Router isolation
- **WHEN** developer works on chat endpoints
- **THEN** they only need to modify src/api/routers/chat.py
- **AND** changes don't affect other endpoint groups
- **AND** file is under 500 lines

#### Scenario: Router registration
- **WHEN** application starts
- **THEN** main.py includes all routers
- **AND** each router has distinct prefix and tags
- **AND** Swagger UI groups endpoints by router tags

#### Scenario: Router dependencies
- **WHEN** router needs shared state
- **THEN** it accesses via dependency injection
- **AND** router doesn't directly access global state
- **AND** dependencies are explicit in function signatures

### Requirement: Service Layer Separation
The system SHALL organize business logic into service layer separate from API layer.

#### Scenario: Service encapsulation
- **WHEN** business logic is needed
- **THEN** it resides in src/services/ modules
- **AND** API routers call service methods
- **AND** services don't import from routers

#### Scenario: LLM service organization
- **WHEN** LLM functionality is needed
- **THEN** it's accessed via src/services/llm/llamaindex_service.py
- **AND** service has no FastAPI dependencies
- **AND** service can be tested independently

#### Scenario: Graph service organization
- **WHEN** graph operations are needed
- **THEN** they're accessed via src/services/graph/ modules
- **AND** Neo4j client is encapsulated in service
- **AND** service exposes domain operations not DB operations

### Requirement: Utility Module Organization
The system SHALL organize shared utilities into focused modules.

#### Scenario: Exception hierarchy
- **WHEN** error occurs
- **THEN** custom exception from src/utils/exceptions.py is raised
- **AND** exception class indicates error category
- **AND** exception message is descriptive

#### Scenario: Constants management
- **WHEN** code needs configuration constant
- **THEN** it's imported from src/utils/constants.py
- **AND** constant has descriptive name
- **AND** constant is documented with comment

#### Scenario: Type aliases
- **WHEN** complex type is used repeatedly
- **THEN** it's defined in src/utils/types.py
- **AND** type alias has descriptive name
- **AND** type is imported consistently

### Requirement: No Deprecated Code
The codebase SHALL NOT contain unused or deprecated code.

#### Scenario: Azure code removal
- **WHEN** codebase is scanned
- **THEN** no Azure-specific code exists
- **AND** no Cosmos DB client exists
- **AND** only local/Docker infrastructure remains

#### Scenario: Duplicate elimination
- **WHEN** similar functionality exists
- **THEN** only one implementation is kept
- **AND** best implementation is chosen
- **AND** unused alternatives are deleted

#### Scenario: Dead code detection
- **WHEN** file is not imported anywhere
- **THEN** it's marked for deletion
- **AND** deletion is documented in change notes
- **AND** git history preserves code if needed later

### Requirement: Directory Structure Clarity
The project SHALL have clear, hierarchical directory structure.

#### Scenario: API layer organization
- **WHEN** looking for API code
- **THEN** all API code is in src/api/
- **AND** routers are in src/api/routers/
- **AND** models are in src/api/models/
- **AND** middleware is in src/api/middleware/

#### Scenario: Service layer organization
- **WHEN** looking for business logic
- **THEN** services are in src/services/
- **AND** each service has own subdirectory
- **AND** service modules are focused on single responsibility

#### Scenario: Utility organization
- **WHEN** looking for shared utilities
- **THEN** utilities are in src/utils/
- **AND** each utility file has focused purpose
- **AND** utilities have no circular dependencies

### Requirement: Script Consolidation
Startup and utility scripts SHALL be organized in scripts directory.

#### Scenario: Windows scripts location
- **WHEN** looking for Windows scripts
- **THEN** all .bat files are in scripts/windows/
- **AND** scripts have descriptive names
- **AND** scripts include usage help

#### Scenario: Unix scripts location
- **WHEN** looking for Unix scripts
- **THEN** all .sh files are in scripts/unix/
- **AND** scripts are executable
- **AND** scripts have shebang line

#### Scenario: Script documentation
- **WHEN** running script with --help
- **THEN** usage information is displayed
- **AND** all options are documented
- **AND** examples are provided

### Requirement: Root Directory Cleanliness
The project root SHALL contain only essential configuration and documentation files.

#### Scenario: Essential files only
- **WHEN** listing root directory
- **THEN** only README, LICENSE, .gitignore, requirements, Docker files exist
- **AND** no temporary markdown files exist
- **AND** no data or log files exist

#### Scenario: Temporary file cleanup
- **WHEN** development generates temporary files
- **THEN** they're gitignored
- **AND** they're in dedicated directories (data/, logs/)
- **AND** they don't clutter root

### Requirement: File Size Limits
Source files SHALL adhere to maximum line count for maintainability.

#### Scenario: File size enforcement
- **WHEN** source file is created or modified
- **THEN** it's kept under 500 lines
- **AND** larger files are split into modules
- **AND** splitting maintains logical cohesion

#### Scenario: main.py size limit
- **WHEN** main.py is edited
- **THEN** it remains under 200 lines
- **AND** only contains app factory and lifespan
- **AND** logic is extracted to routers/middleware

### Requirement: Backward Compatibility
Import paths SHALL maintain backward compatibility during transition.

#### Scenario: Deprecated import support
- **WHEN** old import path is used
- **THEN** it still works via compatibility shim
- **AND** deprecation warning is logged
- **AND** new import path is suggested

#### Scenario: Compatibility period
- **WHEN** backward-compatible import exists
- **THEN** it's maintained for one release cycle
- **AND** deprecation is documented
- **AND** removal is planned for next major version


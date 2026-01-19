# Code Cleanup Specification

## ADDED Requirements

### Requirement: Remove Singleton Pattern
The system SHALL eliminate old singleton code after migration to dependency injection.

**Priority**: High

#### Scenario: Remove get_duckdb_client function
**Given** all code has migrated to ServiceContainer  
**When** code cleanup phase executes  
**Then** `get_duckdb_client()` function is deleted  
**And** global `_duckdb_client` variable is removed  
**And** no code references the old singleton pattern

#### Scenario: Update all imports
**Given** singleton pattern is removed  
**When** import statements are updated  
**Then** all files import from `dependency_injection` module  
**And** no files import `get_duckdb_client`  
**And** linter shows zero import errors

---

### Requirement: Remove Duplicate Implementations
The system SHALL eliminate parallel implementations of same functionality.

**Priority**: High

#### Scenario: Remove old repository implementations
**Given** optimized repositories are in production  
**When** cleanup executes  
**Then** old `ModelConfigRepository` is deleted  
**And** only `OptimizedModelConfigRepository` remains  
**And** all services use the optimized version

#### Scenario: Consolidate service implementations
**Given** multiple service implementations exist  
**When** cleanup executes  
**Then** only the latest implementation is kept  
**And** deprecated services are removed  
**And** no duplicate code exists

---

### Requirement: Standardize Error Handling
The system SHALL provide consistent error handling across all services.

**Priority**: Medium

#### Scenario: Replace generic exceptions
**Given** code uses generic `Exception` types  
**When** error handling is standardized  
**Then** all database errors use `DatabaseException` hierarchy  
**And** all exceptions include proper context  
**And** error messages are consistent and actionable

#### Scenario: Consistent logging patterns
**Given** services log errors differently  
**When** logging is standardized  
**Then** all services use structured logging  
**And** log levels are appropriate (ERROR, WARNING, INFO)  
**And** sensitive data is not logged

---

### Requirement: Code Quality Standards
The codebase SHALL maintain high code quality and consistency.

**Priority**: Medium

#### Scenario: Linter compliance
**Given** code cleanup is complete  
**When** linters are run (Ruff, Black, mypy)  
**Then** zero linter warnings are reported  
**And** code formatting is consistent  
**And** type hints are complete

#### Scenario: Remove dead code
**Given** unused code exists in codebase  
**When** dead code analysis runs  
**Then** all unused imports are removed  
**And** all unused functions are deleted  
**And** code coverage tools show no dead code

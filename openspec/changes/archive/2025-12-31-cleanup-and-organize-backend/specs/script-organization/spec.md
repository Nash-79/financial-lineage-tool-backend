# Script Organization Spec

## ADDED Requirements

### Requirement: Consolidated Startup Scripts
Startup scripts SHALL be consolidated and organized in root directory

#### Scenario: Starting the application
- **WHEN** developer wants to start the system
- **THEN** start-docker.{bat,sh} is the primary method
- **AND** script is in project root for easy access
- **AND** script has clear comments and error handling
- **AND** both Windows (.bat) and Unix (.sh) versions exist

#### Scenario: Managing running services
- **WHEN** developer needs to manage services
- **THEN** stop-docker.{bat,sh} stops all services
- **AND** logs-docker.{bat,sh} shows service logs
- **AND** check-docker.{bat,sh} validates environment
- **AND** all scripts follow same naming convention

#### Scenario: Deprecated startup methods
- **WHEN** deprecated startup scripts exist
- **THEN** they're moved to scripts/legacy/ directory
- **AND** README in scripts/legacy/ explains deprecation
- **AND** scripts display deprecation warning when run
- **AND** recommended alternative is shown

### Requirement: Legacy Script Organization
Deprecated scripts SHALL be moved to scripts/legacy/ directory

#### Scenario: Moving deprecated script
- **WHEN** start-local.bat is deprecated
- **THEN** it's moved to scripts/legacy/start-local.bat
- **AND** deprecation notice is added at top of script
- **AND** script guides user to start-docker.bat
- **AND** original functionality is preserved

#### Scenario: Legacy directory documentation
- **WHEN** viewing scripts/legacy/
- **THEN** README.md explains why scripts are deprecated
- **AND** migration guide to Docker setup exists
- **AND** last supported version is documented
- **AND** removal timeline is stated

#### Scenario: Running legacy script
- **WHEN** deprecated script is executed
- **THEN** clear warning is displayed
- **AND** recommended modern alternative is shown
- **AND** confirmation is required to continue
- **AND** user has chance to cancel

### Requirement: Docker Compose Consolidation
Docker Compose files SHALL be consolidated and clearly named

#### Scenario: Starting local development
- **WHEN** developer runs start-docker script
- **THEN** docker-compose.yml is used (primary config)
- **AND** file contains core service definitions
- **AND** file is self-documenting with comments
- **AND** unused compose files are removed

#### Scenario: Production deployment
- **WHEN** deploying to production
- **THEN** docker-compose.prod.yml overlays docker-compose.yml
- **AND** production-specific overrides are documented
- **AND** usage command is documented in README
- **AND** resource limits are appropriate

#### Scenario: Special configurations
- **WHEN** Neo4j-specific setup is needed
- **THEN** docker-compose.neo4j.yml contains Neo4j service
- **AND** file is optional and well-documented
- **AND** usage is explained in documentation
- **AND** conflicts with main compose are avoided

### Requirement: Organized Utility Scripts
Utility scripts SHALL be organized in scripts/ directory

#### Scenario: Database utility scripts
- **WHEN** looking for database scripts
- **THEN** they're in scripts/ directory
- **AND** script names indicate purpose (add_adventureworks_entities.py)
- **AND** each script has --help documentation
- **AND** scripts are executable

#### Scenario: Testing scripts
- **WHEN** looking for test scripts
- **THEN** they're in scripts/test/ subdirectory
- **AND** script names start with test_
- **AND** scripts can run independently
- **AND** dependencies are documented

#### Scenario: Deployment scripts
- **WHEN** looking for deployment scripts
- **THEN** they're in scripts/deploy/ subdirectory
- **AND** scripts handle environment-specific config
- **AND** error handling is robust
- **AND** rollback procedures are documented

### Requirement: Script Error Handling
Shell scripts SHALL include error handling and help text

#### Scenario: Running script with --help
- **WHEN** script is run with --help flag
- **THEN** usage information is displayed
- **AND** all parameters are documented
- **AND** examples are provided
- **AND** script exits without performing action

#### Scenario: Script encounters error
- **WHEN** script dependency is missing
- **THEN** clear error message is displayed
- **AND** installation instructions are provided
- **AND** script exits with non-zero code
- **AND** partial changes are cleaned up if needed

#### Scenario: Prerequisites check
- **WHEN** script starts
- **THEN** all prerequisites are verified
- **AND** missing tools are reported clearly
- **AND** script fails fast if prerequisites missing
- **AND** helpful error messages guide user

### Requirement: Cross-Platform Parity
Windows and Unix scripts SHALL be feature-equivalent

#### Scenario: Cross-platform startup
- **WHEN** comparing start-docker.bat and start-docker.sh
- **THEN** both perform identical checks
- **AND** both show same output messages
- **AND** both handle errors similarly
- **AND** both support same options/flags

#### Scenario: Platform-specific differences
- **WHEN** platform-specific code is needed
- **THEN** differences are clearly commented
- **AND** equivalent functionality exists on both platforms
- **AND** platform limitations are documented
- **AND** workarounds are provided if needed

#### Scenario: Script maintenance
- **WHEN** script is updated
- **THEN** both .bat and .sh versions are updated
- **AND** changes are consistent across platforms
- **AND** testing is done on both platforms
- **AND** platform-specific issues are resolved

### Requirement: Environment Validation
Scripts SHALL validate environment before executing

#### Scenario: Docker validation
- **WHEN** start-docker script runs
- **THEN** Docker installation is verified
- **AND** Docker daemon running status is checked
- **AND** required Docker version is validated
- **AND** clear errors guide user if checks fail

#### Scenario: Service availability
- **WHEN** script depends on service
- **THEN** service availability is checked
- **AND** warning shown if optional service unavailable
- **AND** error thrown if required service unavailable
- **AND** service URLs are displayed when available

#### Scenario: File and directory validation
- **WHEN** script requires files
- **THEN** file existence is verified
- **AND** file permissions are checked
- **AND** directory structure is validated
- **AND** missing items are created or reported

### Requirement: Consistent Script Naming
Script naming SHALL follow consistent conventions

#### Scenario: Action scripts
- **WHEN** script performs action
- **THEN** name starts with verb (start-, stop-, check-)
- **AND** technology/context is included (docker, local)
- **AND** extension indicates platform (.bat, .sh)
- **AND** name is hyphen-separated lowercase

#### Scenario: Utility scripts
- **WHEN** script is utility function
- **THEN** name describes function clearly
- **AND** context is included (test_qdrant.py)
- **AND** Python scripts use snake_case
- **AND** shell scripts use kebab-case

#### Scenario: Avoiding naming conflicts
- **WHEN** creating new script
- **THEN** name doesn't conflict with existing scripts
- **AND** similar scripts have distinguishable names
- **AND** purpose is clear from name alone
- **AND** documentation references use exact name

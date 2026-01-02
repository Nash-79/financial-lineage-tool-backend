# Contributing to Financial Lineage Tool

Thank you for your interest in contributing to the Financial Lineage Tool! This document provides guidelines and standards for contributing to the backend codebase.

## Table of Contents
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Docker Desktop 20.10+
- Ollama (for LLM features)
- Git
- A code editor with Python support (VS Code recommended)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/financial-lineage-tool-backend.git
   cd financial-lineage-tool-backend
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/financial-lineage-tool-backend.git
   ```

## Development Setup

### Local Development

1. **Create virtual environment**:
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # Unix/Linux/macOS
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements-local.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start services**:
   ```bash
   # Windows
   start-docker.bat

   # Unix/Linux/macOS
   ./start-docker.sh
   ```

5. **Run the application**:
   ```bash
   uvicorn src.api.main_local:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker Development

```bash
# Build and start all services
docker compose up --build

# Run in detached mode
docker compose up -d

# View logs
docker compose logs -f api
```

## Code Standards

### Python Style Guide

We follow **PEP 8** with some modifications. All code must pass our linting tools.

#### Formatting

- **Black**: Automatic code formatting
  ```bash
  python -m black src/
  ```

- **Line Length**: 88 characters (Black default)
- **Imports**: Organized using `isort`
- **Quotes**: Double quotes for strings (Black enforced)

#### Linting

- **Ruff**: Fast Python linter
  ```bash
  python -m ruff check src/ --fix
  ```

- **Type Checking**: MyPy for static type analysis
  ```bash
  python -m mypy src/
  ```

### Code Structure Standards

#### 1. Type Hints

All functions must have type hints:

```python
from __future__ import annotations

def process_data(input_data: str, limit: int = 10) -> list[dict[str, Any]]:
    """Process input data and return results."""
    ...
```

#### 2. Docstrings

Use **Google-style docstrings** for all functions and classes:

```python
def query_lineage(entity_id: str, max_depth: int = 5) -> dict[str, Any]:
    """Query lineage for a given entity.

    Args:
        entity_id: Unique identifier for the entity.
        max_depth: Maximum depth for lineage traversal.

    Returns:
        Dictionary containing lineage data with upstream and downstream paths.

    Raises:
        EntityNotFoundError: If the entity doesn't exist.
        GraphDatabaseError: If the graph database is unavailable.
    """
    ...
```

#### 3. Imports Organization

```python
# Standard library imports
import asyncio
from typing import Any, Optional

# Third-party imports
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Local imports
from src.services import OllamaClient
from src.utils.exceptions import LineageToolError
```

#### 4. Module Structure

```python
"""Module description.

More detailed explanation of what this module does.
"""

from __future__ import annotations

# Imports here

# Constants
DEFAULT_TIMEOUT = 30

# Type aliases
JSON = dict[str, Any]

# Classes and functions
class MyClass:
    """Class docstring."""
    ...

# __all__ for public API
__all__ = ["MyClass", "my_function"]
```

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `OllamaClient`, `LineageResponse`)
- **Functions/Methods**: `snake_case` (e.g., `get_lineage`, `process_query`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_TIMEOUT`, `MAX_RETRIES`)
- **Private**: Prefix with `_` (e.g., `_internal_method`)
- **Type Aliases**: `PascalCase` (e.g., `JSON`, `Vector`)

### Error Handling

Use custom exceptions from `src/utils/exceptions.py`:

```python
from src.utils.exceptions import GraphDatabaseError, ValidationError

def connect_to_graph(uri: str) -> GraphClient:
    """Connect to graph database."""
    if not uri:
        raise ValidationError("URI cannot be empty")

    try:
        client = GraphClient(uri)
        client.verify_connection()
        return client
    except ConnectionError as e:
        raise GraphDatabaseError(f"Failed to connect to {uri}") from e
```

### Async/Await

- Use `async`/`await` for I/O operations
- Use `asyncio.gather()` for concurrent operations
- Always use `async with` for async context managers

```python
async def fetch_multiple_entities(entity_ids: list[str]) -> list[Entity]:
    """Fetch multiple entities concurrently."""
    tasks = [fetch_entity(entity_id) for entity_id in entity_ids]
    return await asyncio.gather(*tasks)
```

## Project Structure

```
src/
├── api/                    # API Layer
│   ├── main_local.py      # FastAPI application
│   ├── config.py          # Configuration
│   ├── middleware/        # HTTP middleware
│   ├── models/            # Pydantic models
│   └── routers/           # API endpoints
├── services/              # Services Layer
│   ├── ollama_service.py  # Ollama client
│   ├── qdrant_service.py  # Qdrant client
│   └── agent_service.py   # Agent orchestration
├── llm/                   # LLM integration
├── ingestion/             # Code processing
├── knowledge_graph/       # Graph operations
└── utils/                 # Utilities
```

### Where to Add New Code

- **New API endpoint**: Create/update router in `src/api/routers/`
- **New model**: Add to appropriate file in `src/api/models/`
- **New service**: Add to `src/services/`
- **New utility**: Add to `src/utils/`
- **New exception**: Add to `src/utils/exceptions.py`

## Making Changes

### Branch Strategy

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Branch naming**:
   - Feature: `feature/description`
   - Bug fix: `fix/description`
   - Documentation: `docs/description`
   - Refactoring: `refactor/description`

### Commit Messages

Follow the **Conventional Commits** specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples**:
```
feat(api): add endpoint for batch entity creation

fix(services): handle connection timeout in Ollama client

docs(readme): update installation instructions

refactor(routers): extract common validation logic
```

### Development Workflow

1. **Pull latest changes**:
   ```bash
   git checkout main
   git pull upstream main
   ```

2. **Create feature branch**:
   ```bash
   git checkout -b feature/my-feature
   ```

3. **Make changes**:
   - Write code
   - Add tests
   - Update documentation

4. **Format and lint**:
   ```bash
   python -m black src/
   python -m ruff check src/ --fix
   ```

5. **Run tests**:
   ```bash
   python -m pytest tests/
   ```

6. **Commit changes**:
   ```bash
   git add .
   git commit -m "feat(api): add new endpoint"
   ```

7. **Push to your fork**:
   ```bash
   git push origin feature/my-feature
   ```

8. **Create Pull Request** on GitHub

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Run specific test file
python -m pytest tests/test_api_endpoints.py

# Run specific test
python -m pytest tests/test_api_endpoints.py::test_health_check
```

### Writing Tests

```python
import pytest
from fastapi.testclient import TestClient
from src.api.main_local import app

client = TestClient(app)

def test_health_check():
    """Test health check endpoint returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["healthy", "degraded"]

@pytest.mark.asyncio
async def test_async_operation():
    """Test async operation."""
    result = await my_async_function()
    assert result is not None
```

### Test Coverage

- Aim for **80%+ test coverage**
- All new features must include tests
- Bug fixes should include regression tests

## Documentation

### Code Documentation

- All public functions/classes must have docstrings
- Include type hints for all parameters and return values
- Use Google-style docstrings

### API Documentation

- API changes automatically update OpenAPI docs
- Add examples to docstrings for complex endpoints
- Update [API_REFERENCE.md](API_REFERENCE.md) for major changes

### Architecture Documentation

- Update [ARCHITECTURE.md](ARCHITECTURE.md) for architectural changes
- Include diagrams for new components
- Document design decisions and trade-offs

## Pull Request Process

### Before Creating a PR

1. **Ensure all tests pass**
2. **Format and lint your code**
3. **Update documentation**
4. **Rebase on latest main**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Changes Made
- List of changes
- Use bullet points
- Be specific

## Testing
- Describe testing performed
- Include test results

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-reviewed code
- [ ] Added/updated tests
- [ ] Updated documentation
- [ ] No new warnings
- [ ] Tests pass locally
```

### Review Process

1. **Automated Checks**: All CI checks must pass
2. **Code Review**: At least one maintainer review required
3. **Testing**: Reviewers may test your changes
4. **Approval**: Maintainer approval required to merge

### After PR is Merged

1. **Delete your branch**:
   ```bash
   git branch -d feature/my-feature
   ```

2. **Update your fork**:
   ```bash
   git checkout main
   git pull upstream main
   git push origin main
   ```

## Questions or Issues?

- **Bug Reports**: Open an issue with reproduction steps
- **Feature Requests**: Open an issue with use case description
- **Questions**: Start a discussion or open an issue

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to the Financial Lineage Tool! 🎉

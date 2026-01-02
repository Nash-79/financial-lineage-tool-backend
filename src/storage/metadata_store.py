"""
Metadata storage layer for projects, repositories, and links.

Provides CRUD operations with DuckDB SQL dialect features.
Uses DuckDB's native capabilities like QUALIFY, LIST aggregation, and JSON operators.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from .duckdb_client import get_duckdb_client

logger = logging.getLogger(__name__)


class ProjectStore:
    """
    CRUD operations for projects table.

    Uses DuckDB SQL dialect throughout for consistency.
    """

    async def create(
        self,
        name: str,
        description: Optional[str] = None,
        id: Optional[str] = None
    ) -> dict:
        """
        Create a new project.

        Args:
            name: Project name
            description: Optional project description
            id: Optional project ID (generated if not provided)

        Returns:
            Created project dict
        """
        client = get_duckdb_client()
        project_id = id or str(uuid.uuid4())

        await client.execute_write(
            """
            INSERT INTO projects (id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, current_timestamp, current_timestamp)
            """,
            (project_id, name, description)
        )

        logger.info(f"Created project: {project_id}")
        return self.get(project_id)

    def get(self, project_id: str) -> Optional[dict]:
        """
        Get project by ID with repository and link counts.

        Args:
            project_id: Project ID

        Returns:
            Project dict or None if not found
        """
        client = get_duckdb_client()

        # Use DuckDB's native aggregation for counts
        result = client.fetchone(
            """
            SELECT
                p.id,
                p.name,
                p.description,
                p.created_at,
                p.updated_at,
                COUNT(DISTINCT r.id) AS repository_count,
                COUNT(DISTINCT l.id) AS link_count
            FROM projects p
            LEFT JOIN repositories r ON p.id = r.project_id
            LEFT JOIN links l ON p.id = l.project_id
            WHERE p.id = ?
            GROUP BY p.id, p.name, p.description, p.created_at, p.updated_at
            """,
            (project_id,)
        )

        if not result:
            return None

        return {
            "id": result[0],
            "name": result[1],
            "description": result[2],
            "created_at": result[3].isoformat() if result[3] else None,
            "updated_at": result[4].isoformat() if result[4] else None,
            "repository_count": result[5],
            "link_count": result[6],
        }

    def list(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """
        List all projects with repository and link counts.

        Uses DuckDB's efficient aggregation for computing counts.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of project dicts
        """
        client = get_duckdb_client()

        results = client.fetchall(
            """
            SELECT
                p.id,
                p.name,
                p.description,
                p.created_at,
                p.updated_at,
                COUNT(DISTINCT r.id) AS repository_count,
                COUNT(DISTINCT l.id) AS link_count
            FROM projects p
            LEFT JOIN repositories r ON p.id = r.project_id
            LEFT JOIN links l ON p.id = l.project_id
            GROUP BY p.id, p.name, p.description, p.created_at, p.updated_at
            ORDER BY p.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )

        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None,
                "repository_count": row[5],
                "link_count": row[6],
            }
            for row in results
        ]

    async def update(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[dict]:
        """
        Update project by ID.

        Args:
            project_id: Project ID
            name: New name (optional)
            description: New description (optional)

        Returns:
            Updated project dict or None if not found
        """
        client = get_duckdb_client()

        # Build dynamic update
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if not updates:
            return self.get(project_id)

        updates.append("updated_at = current_timestamp")
        params.append(project_id)

        await client.execute_write(
            f"UPDATE projects SET {', '.join(updates)} WHERE id = ?",
            tuple(params)
        )

        logger.info(f"Updated project: {project_id}")
        return self.get(project_id)

    async def delete(self, project_id: str) -> bool:
        """
        Delete project by ID.

        CASCADE delete removes associated repositories and links.

        Args:
            project_id: Project ID

        Returns:
            True if deleted, False if not found
        """
        client = get_duckdb_client()

        # Check if exists
        if not self.get(project_id):
            return False

        await client.execute_write(
            "DELETE FROM projects WHERE id = ?",
            (project_id,)
        )

        logger.info(f"Deleted project: {project_id}")
        return True

    def count(self) -> int:
        """Get total project count."""
        client = get_duckdb_client()
        result = client.fetchone("SELECT COUNT(*) FROM projects")
        return result[0] if result else 0

    def exists(self, project_id: str) -> bool:
        """Check if project exists."""
        client = get_duckdb_client()
        result = client.fetchone(
            "SELECT 1 FROM projects WHERE id = ?",
            (project_id,)
        )
        return result is not None


class RepositoryStore:
    """
    CRUD operations for repositories table.

    Repositories are scoped to projects and track file/node counts.
    """

    async def create(
        self,
        project_id: str,
        name: str,
        source: str,
        source_ref: Optional[str] = None,
        id: Optional[str] = None
    ) -> dict:
        """
        Create a new repository.

        Args:
            project_id: Parent project ID
            name: Repository name
            source: Source type ('github', 'upload', 'manual')
            source_ref: Source reference (e.g., 'owner/repo' for GitHub)
            id: Optional repository ID (generated if not provided)

        Returns:
            Created repository dict
        """
        client = get_duckdb_client()
        repo_id = id or str(uuid.uuid4())

        await client.execute_write(
            """
            INSERT INTO repositories (id, project_id, name, source, source_ref, created_at)
            VALUES (?, ?, ?, ?, ?, current_timestamp)
            """,
            (repo_id, project_id, name, source, source_ref)
        )

        logger.info(f"Created repository: {repo_id} in project: {project_id}")
        return self.get(repo_id)

    def get(self, repo_id: str) -> Optional[dict]:
        """
        Get repository by ID.

        Args:
            repo_id: Repository ID

        Returns:
            Repository dict or None if not found
        """
        client = get_duckdb_client()

        result = client.fetchone(
            """
            SELECT id, project_id, name, source, source_ref,
                   file_count, node_count, last_synced, created_at
            FROM repositories
            WHERE id = ?
            """,
            (repo_id,)
        )

        if not result:
            return None

        return {
            "id": result[0],
            "project_id": result[1],
            "name": result[2],
            "source": result[3],
            "source_ref": result[4],
            "file_count": result[5],
            "node_count": result[6],
            "last_synced": result[7].isoformat() if result[7] else None,
            "created_at": result[8].isoformat() if result[8] else None,
        }

    def list_by_project(self, project_id: str) -> list[dict]:
        """
        List all repositories for a project.

        Args:
            project_id: Project ID

        Returns:
            List of repository dicts
        """
        client = get_duckdb_client()

        results = client.fetchall(
            """
            SELECT id, project_id, name, source, source_ref,
                   file_count, node_count, last_synced, created_at
            FROM repositories
            WHERE project_id = ?
            ORDER BY created_at DESC
            """,
            (project_id,)
        )

        return [
            {
                "id": row[0],
                "project_id": row[1],
                "name": row[2],
                "source": row[3],
                "source_ref": row[4],
                "file_count": row[5],
                "node_count": row[6],
                "last_synced": row[7].isoformat() if row[7] else None,
                "created_at": row[8].isoformat() if row[8] else None,
            }
            for row in results
        ]

    async def update_counts(
        self,
        repo_id: str,
        file_count: Optional[int] = None,
        node_count: Optional[int] = None
    ) -> Optional[dict]:
        """
        Update repository file and node counts.

        Args:
            repo_id: Repository ID
            file_count: New file count
            node_count: New node count

        Returns:
            Updated repository dict or None if not found
        """
        client = get_duckdb_client()

        updates = []
        params = []

        if file_count is not None:
            updates.append("file_count = ?")
            params.append(file_count)

        if node_count is not None:
            updates.append("node_count = ?")
            params.append(node_count)

        if not updates:
            return self.get(repo_id)

        updates.append("last_synced = current_timestamp")
        params.append(repo_id)

        await client.execute_write(
            f"UPDATE repositories SET {', '.join(updates)} WHERE id = ?",
            tuple(params)
        )

        return self.get(repo_id)

    async def delete(self, repo_id: str) -> bool:
        """
        Delete repository by ID.

        CASCADE delete removes associated links.

        Args:
            repo_id: Repository ID

        Returns:
            True if deleted, False if not found
        """
        client = get_duckdb_client()

        if not self.get(repo_id):
            return False

        await client.execute_write(
            "DELETE FROM repositories WHERE id = ?",
            (repo_id,)
        )

        logger.info(f"Deleted repository: {repo_id}")
        return True

    def exists(self, repo_id: str) -> bool:
        """Check if repository exists."""
        client = get_duckdb_client()
        result = client.fetchone(
            "SELECT 1 FROM repositories WHERE id = ?",
            (repo_id,)
        )
        return result is not None

    async def update_last_synced(self, repo_id: str) -> Optional[dict]:
        """
        Update repository last_synced timestamp to current time.

        Args:
            repo_id: Repository ID

        Returns:
            Updated repository dict or None if not found
        """
        client = get_duckdb_client()

        if not self.get(repo_id):
            return None

        await client.execute_write(
            "UPDATE repositories SET last_synced = current_timestamp WHERE id = ?",
            (repo_id,)
        )

        logger.info(f"Updated last_synced for repository: {repo_id}")
        return self.get(repo_id)


class LinkStore:
    """
    CRUD operations for links table.

    Links represent relationships between repositories within a project.
    Can be manual (user-created) or auto-detected (by code analysis).
    """

    async def create(
        self,
        project_id: str,
        source_repo_id: str,
        target_repo_id: str,
        link_type: str,
        description: Optional[str] = None,
        confidence: Optional[float] = None,
        evidence: Optional[list[dict]] = None,
        id: Optional[str] = None
    ) -> dict:
        """
        Create a new link between repositories.

        Args:
            project_id: Parent project ID
            source_repo_id: Source repository ID
            target_repo_id: Target repository ID
            link_type: Link type ('manual', 'auto-detected')
            description: Optional description
            confidence: Confidence score (0.0-1.0) for auto-detected links
            evidence: Evidence array for auto-detected links
            id: Optional link ID (generated if not provided)

        Returns:
            Created link dict
        """
        client = get_duckdb_client()
        link_id = id or str(uuid.uuid4())

        # Serialize evidence to JSON string
        evidence_json = json.dumps(evidence) if evidence else None

        await client.execute_write(
            """
            INSERT INTO links (id, project_id, source_repo_id, target_repo_id,
                               link_type, description, confidence, evidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            (link_id, project_id, source_repo_id, target_repo_id,
             link_type, description, confidence, evidence_json)
        )

        logger.info(f"Created link: {link_id} from {source_repo_id} to {target_repo_id}")
        return self.get(link_id)

    def get(self, link_id: str) -> Optional[dict]:
        """
        Get link by ID.

        Args:
            link_id: Link ID

        Returns:
            Link dict or None if not found
        """
        client = get_duckdb_client()

        result = client.fetchone(
            """
            SELECT id, project_id, source_repo_id, target_repo_id,
                   link_type, description, confidence, evidence, created_at
            FROM links
            WHERE id = ?
            """,
            (link_id,)
        )

        if not result:
            return None

        # Parse evidence JSON
        evidence = None
        if result[7]:
            try:
                evidence = json.loads(result[7]) if isinstance(result[7], str) else result[7]
            except (json.JSONDecodeError, TypeError):
                evidence = None

        return {
            "id": result[0],
            "project_id": result[1],
            "source_repo_id": result[2],
            "target_repo_id": result[3],
            "link_type": result[4],
            "description": result[5],
            "confidence": result[6],
            "evidence": evidence,
            "created_at": result[8].isoformat() if result[8] else None,
        }

    def list_by_project(self, project_id: str) -> list[dict]:
        """
        List all links for a project.

        Args:
            project_id: Project ID

        Returns:
            List of link dicts
        """
        client = get_duckdb_client()

        results = client.fetchall(
            """
            SELECT id, project_id, source_repo_id, target_repo_id,
                   link_type, description, confidence, evidence, created_at
            FROM links
            WHERE project_id = ?
            ORDER BY created_at DESC
            """,
            (project_id,)
        )

        links = []
        for row in results:
            evidence = None
            if row[7]:
                try:
                    evidence = json.loads(row[7]) if isinstance(row[7], str) else row[7]
                except (json.JSONDecodeError, TypeError):
                    evidence = None

            links.append({
                "id": row[0],
                "project_id": row[1],
                "source_repo_id": row[2],
                "target_repo_id": row[3],
                "link_type": row[4],
                "description": row[5],
                "confidence": row[6],
                "evidence": evidence,
                "created_at": row[8].isoformat() if row[8] else None,
            })

        return links

    async def delete(self, link_id: str) -> bool:
        """
        Delete link by ID.

        Args:
            link_id: Link ID

        Returns:
            True if deleted, False if not found
        """
        client = get_duckdb_client()

        if not self.get(link_id):
            return False

        await client.execute_write(
            "DELETE FROM links WHERE id = ?",
            (link_id,)
        )

        logger.info(f"Deleted link: {link_id}")
        return True


async def ensure_default_project() -> dict:
    """
    Ensure default project exists for backward compatibility.

    Creates a "Default Project" if the projects table is empty.
    This allows endpoints to work without explicit project_id.

    Returns:
        Default project dict
    """
    project_store = ProjectStore()

    if project_store.count() == 0:
        logger.info("Creating default project for backward compatibility")
        return await project_store.create(
            id="default",
            name="Default Project",
            description="Auto-created for backward compatibility. "
                       "Endpoints without project_id use this project."
        )

    return project_store.get("default") or project_store.list(limit=1)[0]

"""
Projects router for project, repository, and link management.

Provides 9 endpoints for managing the multi-project architecture:
- Project CRUD (5 endpoints)
- Repository management (2 endpoints)
- Link management (3 endpoints)
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.storage.metadata_store import ProjectStore, RepositoryStore, LinkStore
from ..models.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    ProjectDetailResponse,
    RepositoryCreate,
    RepositoryResponse,
    LinkCreate,
    LinkResponse,
    LinkDetectRequest,
    LinkDetectResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# Store instances
project_store = ProjectStore()
repository_store = RepositoryStore()
link_store = LinkStore()


# ==================== Project Endpoints ====================


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
):
    """
    List all projects with repository and link counts.

    Returns paginated list of projects ordered by creation date (newest first).
    """
    projects = project_store.list(limit=limit, offset=offset)
    total = project_store.count()

    return ProjectListResponse(
        projects=[ProjectResponse(**p) for p in projects],
        total=total,
    )


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(project: ProjectCreate):
    """
    Create a new project.

    Projects are containers for repositories and their relationships (links).
    """
    try:
        created = await project_store.create(
            name=project.name,
            description=project.description,
            id=project.id,
        )
        logger.info(f"Created project: {created['id']}")
        return ProjectResponse(**created)
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: str):
    """
    Get project details including all repositories and links.

    Returns complete project information with nested repositories and links.
    """
    project = project_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    repositories = repository_store.list_by_project(project_id)
    links = link_store.list_by_project(project_id)

    return ProjectDetailResponse(
        id=project["id"],
        name=project["name"],
        description=project["description"],
        created_at=project["created_at"],
        updated_at=project["updated_at"],
        repositories=[RepositoryResponse(**r) for r in repositories],
        links=[LinkResponse(**l) for l in links],
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, project: ProjectUpdate):
    """
    Update project details.

    Only provided fields are updated; others remain unchanged.
    """
    existing = project_store.get(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    try:
        updated = await project_store.update(
            project_id=project_id,
            name=project.name,
            description=project.description,
        )
        logger.info(f"Updated project: {project_id}")
        return ProjectResponse(**updated)
    except Exception as e:
        logger.error(f"Failed to update project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    delete_data: bool = Query(
        False,
        description="If true, also delete lineage nodes from Neo4j"
    ),
):
    """
    Delete a project and all its repositories and links.

    CASCADE delete removes all associated repositories and links from DuckDB.
    If delete_data=true, also removes lineage nodes from Neo4j.
    """
    existing = project_store.get(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    try:
        # TODO: If delete_data=True, delete lineage nodes from Neo4j
        # This would query Neo4j for nodes with project_id property and delete them
        if delete_data:
            logger.info(f"delete_data=True: Would delete Neo4j nodes for project {project_id}")
            # Placeholder for Neo4j cleanup

        await project_store.delete(project_id)
        logger.info(f"Deleted project: {project_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to delete project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")


# ==================== Repository Endpoints ====================


@router.post("/{project_id}/repositories", response_model=RepositoryResponse, status_code=201)
async def add_repository(project_id: str, repository: RepositoryCreate):
    """
    Add a repository to a project.

    Repositories track file sources (GitHub, upload, manual) and their metadata.
    """
    # Verify project exists
    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    try:
        created = await repository_store.create(
            project_id=project_id,
            name=repository.name,
            source=repository.source,
            source_ref=repository.source_ref,
            id=repository.id,
        )
        logger.info(f"Added repository {created['id']} to project {project_id}")
        return RepositoryResponse(**created)
    except Exception as e:
        logger.error(f"Failed to add repository: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add repository: {str(e)}")


@router.delete("/{project_id}/repositories/{repo_id}", status_code=204)
async def remove_repository(project_id: str, repo_id: str):
    """
    Remove a repository from a project.

    CASCADE delete removes all links involving this repository.
    Does NOT delete lineage nodes from Neo4j (use delete_data param on project delete).
    """
    # Verify project exists
    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    # Verify repository exists and belongs to project
    repo = repository_store.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository not found: {repo_id}")
    if repo["project_id"] != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"Repository {repo_id} does not belong to project {project_id}"
        )

    try:
        await repository_store.delete(repo_id)
        logger.info(f"Removed repository {repo_id} from project {project_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to remove repository: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove repository: {str(e)}")


# ==================== Link Endpoints ====================


@router.post("/{project_id}/links", response_model=LinkResponse, status_code=201)
async def create_link(project_id: str, link: LinkCreate):
    """
    Create a manual link between two repositories.

    Links represent relationships between repositories (e.g., data dependencies).
    Manual links have link_type='manual' and no confidence score.
    """
    # Verify project exists
    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    # Verify source repository exists and belongs to project
    source_repo = repository_store.get(link.source_repo_id)
    if not source_repo:
        raise HTTPException(status_code=404, detail=f"Source repository not found: {link.source_repo_id}")
    if source_repo["project_id"] != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"Source repository {link.source_repo_id} does not belong to project {project_id}"
        )

    # Verify target repository exists and belongs to project
    target_repo = repository_store.get(link.target_repo_id)
    if not target_repo:
        raise HTTPException(status_code=404, detail=f"Target repository not found: {link.target_repo_id}")
    if target_repo["project_id"] != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"Target repository {link.target_repo_id} does not belong to project {project_id}"
        )

    # Prevent self-links
    if link.source_repo_id == link.target_repo_id:
        raise HTTPException(status_code=400, detail="Cannot create link from repository to itself")

    try:
        created = await link_store.create(
            project_id=project_id,
            source_repo_id=link.source_repo_id,
            target_repo_id=link.target_repo_id,
            link_type="manual",
            description=link.description,
        )
        logger.info(f"Created link {created['id']} in project {project_id}")
        return LinkResponse(**created)
    except Exception as e:
        logger.error(f"Failed to create link: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create link: {str(e)}")


@router.post("/{project_id}/links/detect", response_model=LinkDetectResponse)
async def detect_links(project_id: str, request: LinkDetectRequest):
    """
    Auto-detect links between repositories by analyzing code.

    Analyzes files in all repositories for cross-references:
    - Table references in SQL
    - Import statements
    - File includes

    Detected links have link_type='auto-detected', confidence score, and evidence.
    """
    # Verify project exists
    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    repositories = repository_store.list_by_project(project_id)
    if len(repositories) < 2:
        return LinkDetectResponse(
            detected_links=[],
            total_detected=0,
            analyzed_files=0,
        )

    # TODO: Implement actual code analysis for link detection
    # This would:
    # 1. Get all files from each repository
    # 2. Parse SQL for table references
    # 3. Look for references to tables/objects in other repositories
    # 4. Create links with confidence scores and evidence

    logger.info(f"Link detection requested for project {project_id} (not yet implemented)")

    # Placeholder response
    return LinkDetectResponse(
        detected_links=[],
        total_detected=0,
        analyzed_files=0,
    )


@router.delete("/{project_id}/links/{link_id}", status_code=204)
async def delete_link(project_id: str, link_id: str):
    """
    Delete a link between repositories.
    """
    # Verify project exists
    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    # Verify link exists and belongs to project
    link = link_store.get(link_id)
    if not link:
        raise HTTPException(status_code=404, detail=f"Link not found: {link_id}")
    if link["project_id"] != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"Link {link_id} does not belong to project {project_id}"
        )

    try:
        await link_store.delete(link_id)
        logger.info(f"Deleted link {link_id} from project {project_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to delete link: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete link: {str(e)}")

"""
Projects router for project, repository, and link management.

Provides endpoints for managing the multi-project architecture:
- Project CRUD (5 endpoints)
- Repository management (2 endpoints)
- Project link management (3 endpoints)
- Repository link management (3 endpoints)
"""

import logging

from fastapi import APIRouter, HTTPException, Query, UploadFile, File

from src.storage.metadata_store import (
    ProjectStore,
    RepositoryStore,
    LinkStore,
    ProjectLinkStore,
)
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
    ProjectLinkCreate,
    ProjectLinkResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# Store instances
project_store = ProjectStore()
repository_store = RepositoryStore()
link_store = LinkStore()
project_link_store = ProjectLinkStore()


def get_app_state():
    """Get application state from FastAPI app."""
    from ..main_local import state

    return state


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
        state = get_app_state()
        if state.graph:
            try:
                state.graph.upsert_project_node(
                    project_id=created["id"],
                    name=created.get("name"),
                    description=created.get("description"),
                )
            except Exception as exc:
                logger.warning("Failed to upsert project node in Neo4j: %s", exc)
        logger.info(f"Created project: {created['id']}")
        return ProjectResponse(**created)
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create project: {str(e)}"
        )


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
    project_links = project_link_store.list_by_project(project_id)

    return ProjectDetailResponse(
        id=project["id"],
        name=project["name"],
        description=project["description"],
        created_at=project["created_at"],
        updated_at=project["updated_at"],
        repositories=[RepositoryResponse(**r) for r in repositories],
        links=[LinkResponse(**l) for l in links],
        project_links=[ProjectLinkResponse(**l) for l in project_links],
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
        state = get_app_state()
        if state.graph:
            try:
                state.graph.upsert_project_node(
                    project_id=project_id,
                    name=updated.get("name"),
                    description=updated.get("description"),
                )
            except Exception as exc:
                logger.warning("Failed to update project node in Neo4j: %s", exc)
        logger.info(f"Updated project: {project_id}")
        return ProjectResponse(**updated)
    except Exception as e:
        logger.error(f"Failed to update project: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update project: {str(e)}"
        )


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    delete_data: bool = Query(
        False, description="If true, also delete lineage nodes from Neo4j"
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
            logger.info(
                f"delete_data=True: Would delete Neo4j nodes for project {project_id}"
            )
            # Placeholder for Neo4j cleanup

        await project_store.delete(project_id)
        logger.info(f"Deleted project: {project_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to delete project: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete project: {str(e)}"
        )


# ==================== Repository Endpoints ====================


@router.post(
    "/{project_id}/repositories", response_model=RepositoryResponse, status_code=201
)
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
        raise HTTPException(
            status_code=500, detail=f"Failed to add repository: {str(e)}"
        )


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
            detail=f"Repository {repo_id} does not belong to project {project_id}",
        )

    try:
        await repository_store.delete(repo_id)
        logger.info(f"Removed repository {repo_id} from project {project_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to remove repository: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to remove repository: {str(e)}"
        )


# ==================== Project Link Endpoints ====================


@router.post(
    "/{project_id}/project-links", response_model=ProjectLinkResponse, status_code=201
)
async def create_project_link(project_id: str, link: ProjectLinkCreate):
    """
    Create a manual link between two projects.
    """
    source_project = project_store.get(project_id)
    if not source_project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    target_project = project_store.get(link.target_project_id)
    if not target_project:
        raise HTTPException(
            status_code=404,
            detail=f"Target project not found: {link.target_project_id}",
        )

    if project_id == link.target_project_id:
        raise HTTPException(status_code=400, detail="Cannot link a project to itself")

    created = await project_link_store.create(
        source_project_id=project_id,
        target_project_id=link.target_project_id,
        link_type="manual",
        description=link.description,
    )

    state = get_app_state()
    if state.graph:
        try:
            state.graph.upsert_project_node(
                project_id=source_project["id"],
                name=source_project.get("name"),
                description=source_project.get("description"),
            )
            state.graph.upsert_project_node(
                project_id=target_project["id"],
                name=target_project.get("name"),
                description=target_project.get("description"),
            )
            state.graph.link_projects(
                source_project_id=source_project["id"],
                target_project_id=target_project["id"],
                link_type="manual",
                description=link.description,
            )
        except Exception as exc:
            logger.warning("Failed to create project link in Neo4j: %s", exc)

    logger.info(
        "Created project link %s from %s to %s",
        created["id"],
        project_id,
        link.target_project_id,
    )
    return ProjectLinkResponse(**created)


@router.get("/{project_id}/project-links", response_model=list[ProjectLinkResponse])
async def list_project_links(project_id: str):
    """List project links involving a project."""
    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    links = project_link_store.list_by_project(project_id)
    return [ProjectLinkResponse(**link) for link in links]


@router.delete("/{project_id}/project-links/{link_id}", status_code=204)
async def delete_project_link(project_id: str, link_id: str):
    """Delete a project-to-project link."""
    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    link = project_link_store.get(link_id)
    if not link:
        raise HTTPException(
            status_code=404, detail=f"Project link not found: {link_id}"
        )

    if project_id not in {link["source_project_id"], link["target_project_id"]}:
        raise HTTPException(
            status_code=400,
            detail=f"Project link {link_id} does not involve project {project_id}",
        )

    await project_link_store.delete(link_id)
    state = get_app_state()
    if state.graph:
        try:
            state.graph.unlink_projects(
                source_project_id=link["source_project_id"],
                target_project_id=link["target_project_id"],
            )
        except Exception as exc:
            logger.warning("Failed to remove project link in Neo4j: %s", exc)
    logger.info("Deleted project link %s for project %s", link_id, project_id)
    return None


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
        raise HTTPException(
            status_code=404,
            detail=f"Source repository not found: {link.source_repo_id}",
        )
    if source_repo["project_id"] != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"Source repository {link.source_repo_id} does not belong to project {project_id}",
        )

    # Verify target repository exists and belongs to project
    target_repo = repository_store.get(link.target_repo_id)
    if not target_repo:
        raise HTTPException(
            status_code=404,
            detail=f"Target repository not found: {link.target_repo_id}",
        )
    if target_repo["project_id"] != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"Target repository {link.target_repo_id} does not belong to project {project_id}",
        )

    # Prevent self-links
    if link.source_repo_id == link.target_repo_id:
        raise HTTPException(
            status_code=400, detail="Cannot create link from repository to itself"
        )

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

    logger.info(
        f"Link detection requested for project {project_id} (not yet implemented)"
    )

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
            detail=f"Link {link_id} does not belong to project {project_id}",
        )

    try:
        await link_store.delete(link_id)
        logger.info(f"Deleted link {link_id} from project {project_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to delete link: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete link: {str(e)}")


# ==================== Context Endpoints ====================


@router.get("/{project_id}/context")
async def get_project_context(project_id: str):
    """
    Get project context.

    Returns the stored context including description, source/target entities,
    related projects, and domain hints. Returns empty default structure if
    no context has been set.
    """
    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    context = project_store.get_context(project_id)
    return context


@router.put("/{project_id}/context")
async def update_project_context(project_id: str, context: dict):
    """
    Update project context.

    Accepts a JSON object with the following fields:
    - description: string (required) - Project description
    - format: "text" | "markdown" - Description format
    - source_entities: string[] - Starting points for lineage
    - target_entities: string[] - End targets for lineage
    - related_projects: string[] - IDs of related projects
    - domain_hints: string[] - Domain-specific terms

    Self-referential related_projects are rejected (400).
    """
    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    # Validate context schema
    errors = project_store.validate_context_schema(context)
    if errors:
        raise HTTPException(
            status_code=400, detail=f"Invalid context schema: {'; '.join(errors)}"
        )

    try:
        updated = await project_store.update_context(project_id, context)
        return updated
    except ValueError as e:
        # Circular reference error
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update context: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update context: {str(e)}"
        )


@router.post("/{project_id}/context/upload")
async def upload_context_file(project_id: str, file: UploadFile = File(...)):
    """
    Upload a markdown file as project context.

    Accepts a .md file up to 50KB. If the file contains YAML frontmatter,
    structured fields are extracted:
    - format, source_entities, target_entities, related_projects, domain_hints

    The markdown body becomes the description.
    """
    import yaml
    from pathlib import Path

    if not project_store.exists(project_id):
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    # Validate file extension
    if not file.filename.lower().endswith(".md"):
        raise HTTPException(
            status_code=400, detail="Only .md files are supported for context upload"
        )

    # Read content
    try:
        content_bytes = await file.read()

        # Validate size (50KB limit)
        if len(content_bytes) > 50 * 1024:
            raise HTTPException(
                status_code=413,  # Payload Too Large
                detail="File size exceeds 50KB limit",
            )

        content_str = content_bytes.decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(status_code=400, detail="Failed to read file content")

    # Parse frontmatter if present
    context_data = {"description": content_str, "format": "markdown"}

    # Frontmatter parsing logic
    if content_str.startswith("---"):
        try:
            parts = content_str.split("---", 2)
            if len(parts) >= 3:
                # Part 0 is empty (before first ---)
                # Part 1 is frontmatter
                # Part 2 is body
                frontmatter = yaml.safe_load(parts[1])
                body = parts[2].strip()

                if isinstance(frontmatter, dict):
                    # Map frontmatter fields to context fields
                    # We allow direct mapping for keys that match context schema
                    for key in [
                        "source_entities",
                        "target_entities",
                        "related_projects",
                        "domain_hints",
                    ]:
                        if key in frontmatter:
                            context_data[key] = frontmatter[key]

                    # Update description to be just the body
                    context_data["description"] = body
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse frontmatter for project {project_id}: {e}")
            # Continue with full content as description if parsing fails
            pass

    # Save to disk
    try:
        # Save original file
        file_path = f"data/contexts/{project_id}.md"
        # Ensure directory exists (it should, but safety first)
        Path("data/contexts").mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content_str)

        # Update metadata store
        await project_store.update_context(project_id, context_data, file_path)

        return {
            "status": "success",
            "file_path": file_path,
            "context_extracted": context_data,
        }

    except Exception as e:
        logger.error(f"Failed to save context file: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process context file: {str(e)}"
        )

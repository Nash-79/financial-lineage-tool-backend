"""Pydantic models for project management."""

from typing import Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Request model for creating a project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Project description"
    )
    id: Optional[str] = Field(
        None, description="Optional custom project ID (generated if not provided)"
    )


class ProjectUpdate(BaseModel):
    """Request model for updating a project."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="Project name"
    )
    description: Optional[str] = Field(
        None, max_length=1000, description="Project description"
    )


class ProjectResponse(BaseModel):
    """Response model for a project."""

    id: str = Field(..., description="Project ID")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    created_at: Optional[str] = Field(None, description="Creation timestamp (ISO 8601)")
    updated_at: Optional[str] = Field(
        None, description="Last update timestamp (ISO 8601)"
    )
    repository_count: int = Field(0, description="Number of repositories in project")
    link_count: int = Field(0, description="Number of links between repositories")


class ProjectListResponse(BaseModel):
    """Response model for project list."""

    projects: list[ProjectResponse] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects")


class RepositoryCreate(BaseModel):
    """Request model for adding a repository to a project."""

    name: str = Field(..., min_length=1, max_length=255, description="Repository name")
    source: str = Field(
        ...,
        pattern="^(github|upload|manual)$",
        description="Repository source type: 'github', 'upload', or 'manual'",
    )
    source_ref: Optional[str] = Field(
        None,
        max_length=500,
        description="Source reference (e.g., 'owner/repo' for GitHub, file path for upload)",
    )
    id: Optional[str] = Field(None, description="Optional custom repository ID")


class RepositoryResponse(BaseModel):
    """Response model for a repository."""

    id: str = Field(..., description="Repository ID")
    project_id: str = Field(..., description="Parent project ID")
    name: str = Field(..., description="Repository name")
    source: str = Field(..., description="Source type: 'github', 'upload', or 'manual'")
    source_ref: Optional[str] = Field(None, description="Source reference")
    file_count: int = Field(0, description="Number of files in repository")
    node_count: int = Field(
        0, description="Number of lineage nodes from this repository"
    )
    last_synced: Optional[str] = Field(
        None, description="Last sync timestamp (ISO 8601)"
    )
    created_at: Optional[str] = Field(None, description="Creation timestamp (ISO 8601)")


class LinkCreate(BaseModel):
    """Request model for creating a link between repositories."""

    source_repo_id: str = Field(..., description="Source repository ID")
    target_repo_id: str = Field(..., description="Target repository ID")
    description: Optional[str] = Field(
        None, max_length=1000, description="Link description"
    )


class LinkDetectRequest(BaseModel):
    """Request model for auto-detecting links."""

    analyze_code: bool = Field(True, description="Analyze code for references")
    confidence_threshold: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for detected links",
    )


class LinkEvidence(BaseModel):
    """Evidence for an auto-detected link."""

    source_file: str = Field(..., description="Source file path")
    target_file: str = Field(..., description="Target file path")
    reference_type: str = Field(
        ..., description="Type of reference (e.g., 'table_reference', 'import')"
    )
    reference: str = Field(..., description="The actual reference text")


class LinkResponse(BaseModel):
    """Response model for a link."""

    id: str = Field(..., description="Link ID")
    project_id: str = Field(..., description="Parent project ID")
    source_repo_id: str = Field(..., description="Source repository ID")
    target_repo_id: str = Field(..., description="Target repository ID")
    link_type: str = Field(..., description="Link type: 'manual' or 'auto-detected'")
    description: Optional[str] = Field(None, description="Link description")
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Confidence score (for auto-detected)"
    )
    evidence: Optional[list[LinkEvidence]] = Field(
        None, description="Evidence array (for auto-detected)"
    )
    created_at: Optional[str] = Field(None, description="Creation timestamp (ISO 8601)")


class ProjectLinkCreate(BaseModel):
    """Request model for creating a link between projects."""

    target_project_id: str = Field(..., description="Target project ID")
    description: Optional[str] = Field(
        None, max_length=1000, description="Link description"
    )


class ProjectLinkResponse(BaseModel):
    """Response model for a project link."""

    id: str = Field(..., description="Project link ID")
    source_project_id: str = Field(..., description="Source project ID")
    target_project_id: str = Field(..., description="Target project ID")
    link_type: str = Field(..., description="Link type: 'manual' or 'auto-detected'")
    description: Optional[str] = Field(None, description="Link description")
    created_at: Optional[str] = Field(None, description="Creation timestamp (ISO 8601)")


class ProjectDetailResponse(BaseModel):
    """Response model for project details including repositories and links."""

    id: str = Field(..., description="Project ID")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    created_at: Optional[str] = Field(None, description="Creation timestamp (ISO 8601)")
    updated_at: Optional[str] = Field(
        None, description="Last update timestamp (ISO 8601)"
    )
    repositories: list[RepositoryResponse] = Field(
        ..., description="List of repositories"
    )
    links: list[LinkResponse] = Field(
        ..., description="List of links between repositories"
    )
    project_links: list[ProjectLinkResponse] = Field(
        default_factory=list,
        description="List of links between projects",
    )


class LinkDetectResponse(BaseModel):
    """Response model for link detection results."""

    detected_links: list[LinkResponse] = Field(
        ..., description="List of detected links"
    )
    total_detected: int = Field(..., description="Total number of links detected")
    analyzed_files: int = Field(..., description="Number of files analyzed")

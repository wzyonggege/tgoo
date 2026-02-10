"""Project endpoints."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import generate_api_key, get_current_active_user
from app.models import Project, Staff
from app.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.api.common_responses import LIST_RESPONSES

logger = get_logger("endpoints.projects")
router = APIRouter()


@router.get(
    "",
    response_model=ProjectListResponse,
    responses=LIST_RESPONSES
)
async def list_projects(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectListResponse:
    """
    List projects.

    Retrieve a list of projects. This endpoint is typically used by system administrators
    to manage multiple tenant projects.
    """
    logger.info(f"User {current_user.username} listing projects")

    # Query projects (non-deleted)
    projects = db.query(Project).filter(
        Project.deleted_at.is_(None)
    ).all()

    project_responses = [ProjectResponse.model_validate(project) for project in projects]

    return ProjectListResponse(data=project_responses)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectResponse:
    """
    Create project.

    Create a new project (tenant). This automatically generates an API key for the project
    and publishes a project creation event for AI Service synchronization.
    """
    logger.info(f"User {current_user.username} creating project: {project_data.name}")

    # Generate API key
    api_key = generate_api_key()

    # Create project
    project = Project(
        name=project_data.name,
        api_key=api_key,
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    logger.info(f"Created project {project.id} with name: {project.name}")

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectResponse:
    """Get project details."""
    logger.info(f"User {current_user.username} getting project: {project_id}")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.deleted_at.is_(None)
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectResponse:
    """
    Update project.

    Update project information. This publishes a project update event
    for AI Service synchronization.
    """
    logger.info(f"User {current_user.username} updating project: {project_id}")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.deleted_at.is_(None)
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Update fields
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    project.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(project)

    logger.info(f"Updated project {project.id}")

    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> None:
    """
    Delete project (soft delete).

    Soft delete a project. This publishes a project deletion event
    for AI Service synchronization and cleanup.
    """
    logger.info(f"User {current_user.username} deleting project: {project_id}")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.deleted_at.is_(None)
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Soft delete
    project.deleted_at = datetime.utcnow()
    project.updated_at = datetime.utcnow()

    db.commit()

    logger.info(f"Deleted project {project.id}")

    return None


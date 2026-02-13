"""Setup endpoints for installation/bootstrapping status."""

from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import generate_api_key, get_password_hash
from app.models import (
    Project,
    Staff,
    StaffRole,
    SystemSetup,
    VisitorAssignmentRule,
)
from app.schemas import (
    BatchCreateStaffRequest,
    BatchCreateStaffResponse,
    ConfigureLLMRequest,
    ConfigureLLMResponse,
    CreateAdminRequest,
    CreateAdminResponse,
    SetupCheckResult,
    SetupStatusResponse,
    SkipLLMConfigResponse,
    StaffCreatedItem,
    VerifySetupResponse,
)
from app.services.wukongim_client import wukongim_client
from app.utils.const import CHANNEL_TYPE_PROJECT_STAFF
from app.utils.encoding import build_project_staff_channel_id

logger = get_logger("endpoints.setup")
router = APIRouter()


def _get_or_create_setup_state(db: Session) -> SystemSetup:
    """Return existing setup singleton row or initialize a new one."""
    setup_state = (
        db.query(SystemSetup)
        .order_by(SystemSetup.created_at.asc())
        .first()
    )
    if setup_state:
        return setup_state

    # For the slimmed-down architecture we default to skipping in-app LLM config.
    setup_state = SystemSetup(
        skip_llm_config=True,
    )
    db.add(setup_state)
    db.commit()
    db.refresh(setup_state)
    logger.info("Initialized SystemSetup record with skip_llm_config=True")
    return setup_state


def _get_primary_project(db: Session) -> Project | None:
    """Return the first non-deleted project if it exists."""
    return (
        db.query(Project)
        .filter(Project.deleted_at.is_(None))
        .order_by(Project.created_at.asc())
        .first()
    )


def _ensure_assignment_rule(db: Session, project_id):
    """Ensure the project has a basic visitor assignment rule."""
    existing_rule = (
        db.query(VisitorAssignmentRule)
        .filter(VisitorAssignmentRule.project_id == project_id)
        .first()
    )
    if existing_rule:
        return existing_rule

    rule = VisitorAssignmentRule(
        project_id=project_id,
        llm_assignment_enabled=False,
        service_weekdays=[1, 2, 3, 4, 5, 6, 7],
        service_start_time="00:00",
        service_end_time="23:59",
    )
    db.add(rule)
    return rule


async def _add_staff_to_project_channel(project_id, staff_id):
    """Subscribe staff to the shared project channel in WuKongIM."""
    channel_id = build_project_staff_channel_id(project_id)
    staff_uid = f"{staff_id}-staff"
    await wukongim_client.add_channel_subscribers(
        channel_id=channel_id,
        channel_type=CHANNEL_TYPE_PROJECT_STAFF,
        subscribers=[staff_uid],
    )


def _calculate_setup_flags(db: Session, setup_state: SystemSetup):
    """Return setup flags shared across endpoints."""
    admin_count = (
        db.query(func.count(Staff.id))
        .filter(
            Staff.role == StaffRole.ADMIN.value,
            Staff.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )
    has_admin = admin_count > 0

    user_staff_count = (
        db.query(func.count(Staff.id))
        .filter(
            Staff.role == StaffRole.USER.value,
            Staff.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )
    has_user_staff = user_staff_count > 0

    env_llm_ready = bool(settings.AI_PROVIDER_MODE)
    has_llm_config = bool(
        setup_state.llm_configured
        or setup_state.skip_llm_config
        or env_llm_ready
    )

    effective_is_installed = bool(
        setup_state.is_installed
        or (
            has_admin
            and has_user_staff
            and has_llm_config
        )
    )

    return has_admin, has_user_staff, has_llm_config, effective_is_installed


def _maybe_mark_installed(
    db: Session,
    setup_state: SystemSetup,
    has_admin: bool,
    has_user_staff: bool,
    has_llm_config: bool,
) -> None:
    """Set installation flags when all prerequisites are satisfied."""
    if has_admin and has_user_staff and has_llm_config:
        setup_state.is_installed = True
        if not setup_state.setup_completed_at:
            setup_state.setup_completed_at = datetime.utcnow()
        db.add(setup_state)


@router.get(
    "/status",
    response_model=SetupStatusResponse,
    summary="Get installation status (public)",
)
async def get_setup_status(
    db: Session = Depends(get_db),
) -> SetupStatusResponse:
    """
    Return the current installation status.

    This endpoint intentionally skips authentication so that the UI can determine whether
    it should show the setup wizard prior to login.
    """
    setup_state = _get_or_create_setup_state(db)
    has_admin, has_user_staff, has_llm_config, effective_is_installed = _calculate_setup_flags(
        db, setup_state
    )

    logger.debug(
        "Setup status check",
        extra={
            "has_admin": has_admin,
            "has_user_staff": has_user_staff,
            "has_llm_config": has_llm_config,
            "effective_is_installed": effective_is_installed,
        },
    )

    return SetupStatusResponse(
        is_installed=effective_is_installed,
        has_admin=has_admin,
        has_user_staff=has_user_staff,
        has_llm_config=has_llm_config,
        skip_llm_config=setup_state.skip_llm_config,
        setup_completed_at=setup_state.setup_completed_at,
    )


@router.post(
    "/admin",
    response_model=CreateAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_account(
    payload: CreateAdminRequest,
    db: Session = Depends(get_db),
) -> CreateAdminResponse:
    """Create the initial admin account and default project."""
    setup_state = _get_or_create_setup_state(db)

    existing_admin = (
        db.query(Staff)
        .filter(
            Staff.role == StaffRole.ADMIN.value,
            Staff.deleted_at.is_(None),
        )
        .first()
    )
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account already exists",
        )

    username = payload.username.strip().lower()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty",
        )

    duplicate = (
        db.query(Staff)
        .filter(
            Staff.username == username,
            Staff.deleted_at.is_(None),
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    project = _get_primary_project(db)
    project_name = payload.project_name.strip() or "Default Project"
    if project is None:
        project = Project(
            name=project_name,
            api_key=generate_api_key(),
        )
        db.add(project)
        db.flush()
    else:
        project.name = project_name

    _ensure_assignment_rule(db, project.id)

    admin_staff = Staff(
        project_id=project.id,
        username=username,
        password_hash=get_password_hash(payload.password),
        role=StaffRole.ADMIN.value,
        status="online",
        nickname=payload.nickname or "Administrator",
        name=payload.nickname or "Administrator",
        is_active=True,
        service_paused=False,
    )
    db.add(admin_staff)
    db.flush()

    try:
        await _add_staff_to_project_channel(project.id, admin_staff.id)
    except Exception as exc:  # pragma: no cover - external dependency
        logger.error("Failed to add admin to project channel: %s", exc)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize IM channel",
        )

    setup_state.admin_created = True
    if payload.skip_llm_config:
        setup_state.skip_llm_config = True
        setup_state.llm_configured = True
    db.add(setup_state)
    db.commit()
    db.refresh(project)
    db.refresh(admin_staff)
    db.refresh(setup_state)

    has_admin, has_user_staff, has_llm_config, _ = _calculate_setup_flags(db, setup_state)
    _maybe_mark_installed(db, setup_state, has_admin, has_user_staff, has_llm_config)
    db.commit()
    db.refresh(setup_state)

    return CreateAdminResponse(
        id=admin_staff.id,
        username=admin_staff.username,
        nickname=admin_staff.nickname,
        project_id=project.id,
        project_name=project.name,
        created_at=admin_staff.created_at,
    )


@router.post(
    "/staff",
    response_model=BatchCreateStaffResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_staff_batch(
    payload: BatchCreateStaffRequest,
    db: Session = Depends(get_db),
) -> BatchCreateStaffResponse:
    """Batch create human staff members during setup."""
    project = _get_primary_project(db)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project not initialized. Create admin first.",
        )

    created_staff: List[Staff] = []
    skipped: List[str] = []

    for item in payload.staff_list:
        username = item.username.strip()
        if not username:
            skipped.append(item.username)
            continue

        duplicate = (
            db.query(Staff)
            .filter(
                Staff.username == username,
                Staff.deleted_at.is_(None),
            )
            .first()
        )
        if duplicate:
            skipped.append(username)
            continue

        staff = Staff(
            project_id=project.id,
            username=username,
            password_hash=get_password_hash(item.password),
            role=StaffRole.USER.value,
            status="online",
            name=item.name,
            nickname=item.nickname,
            description=item.description,
            is_active=True,
            service_paused=False,
        )
        db.add(staff)
        db.flush()

        try:
            await _add_staff_to_project_channel(project.id, staff.id)
        except Exception as exc:  # pragma: no cover - external dependency
            logger.error("Failed to add staff to project channel: %s", exc)
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize IM channel",
            )

        created_staff.append(staff)

    db.commit()

    for staff in created_staff:
        db.refresh(staff)

    setup_state = _get_or_create_setup_state(db)
    has_admin, has_user_staff, has_llm_config, _ = _calculate_setup_flags(db, setup_state)
    _maybe_mark_installed(db, setup_state, has_admin, has_user_staff, has_llm_config)
    db.commit()
    db.refresh(setup_state)

    created_items = [
        StaffCreatedItem(
            id=staff.id,
            username=staff.username,
            name=staff.name,
            nickname=staff.nickname,
            created_at=staff.created_at,
        )
        for staff in created_staff
    ]

    return BatchCreateStaffResponse(
        created_count=len(created_staff),
        staff_list=created_items,
        skipped_usernames=skipped,
    )


@router.post(
    "/llm-config",
    response_model=ConfigureLLMResponse,
    status_code=status.HTTP_200_OK,
)
async def configure_llm_provider(
    payload: ConfigureLLMRequest,
    db: Session = Depends(get_db),
) -> ConfigureLLMResponse:
    """Store LLM configuration metadata (FastGPT handles execution)."""
    project = _get_primary_project(db)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project not initialized",
        )

    setup_state = _get_or_create_setup_state(db)
    provider_id = uuid4()

    config = setup_state.config or {}
    config["llm_provider"] = {
        "id": str(provider_id),
        "provider": payload.provider,
        "name": payload.name,
        "api_base_url": payload.api_base_url,
        "default_model": payload.default_model,
        "available_models": payload.available_models,
        "is_active": payload.is_active,
        "config": payload.config or {},
    }
    setup_state.config = config
    setup_state.llm_configured = True
    setup_state.skip_llm_config = False
    db.add(setup_state)

    has_admin, has_user_staff, has_llm_config, _ = _calculate_setup_flags(db, setup_state)
    _maybe_mark_installed(db, setup_state, has_admin, has_user_staff, has_llm_config)
    db.commit()
    db.refresh(setup_state)

    return ConfigureLLMResponse(
        id=provider_id,
        provider=payload.provider,
        name=payload.name,
        default_model=payload.default_model,
        is_active=payload.is_active,
        project_id=project.id,
        created_at=datetime.utcnow(),
    )


@router.post(
    "/skip-llm",
    response_model=SkipLLMConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def skip_llm_configuration(
    db: Session = Depends(get_db),
) -> SkipLLMConfigResponse:
    """Mark the LLM step as skipped (FastGPT is configured externally)."""
    setup_state = _get_or_create_setup_state(db)
    setup_state.skip_llm_config = True
    setup_state.llm_configured = True
    db.add(setup_state)

    has_admin, has_user_staff, has_llm_config, _ = _calculate_setup_flags(db, setup_state)
    _maybe_mark_installed(db, setup_state, has_admin, has_user_staff, has_llm_config)
    db.commit()
    db.refresh(setup_state)

    return SkipLLMConfigResponse(
        message="LLM configuration skipped",
        is_installed=setup_state.is_installed,
        setup_completed_at=setup_state.setup_completed_at or datetime.utcnow(),
    )


@router.get(
    "/verify",
    response_model=VerifySetupResponse,
    summary="Verify installation completeness",
)
async def verify_installation(
    db: Session = Depends(get_db),
) -> VerifySetupResponse:
    """Run basic checks to verify installation."""
    setup_state = _get_or_create_setup_state(db)
    has_admin, has_user_staff, has_llm_config, _ = _calculate_setup_flags(db, setup_state)

    checks = {
        "database": SetupCheckResult(passed=True, message="Database connection OK"),
        "admin": SetupCheckResult(
            passed=has_admin,
            message="Admin account configured" if has_admin else "No admin account present",
        ),
        "staff": SetupCheckResult(
            passed=has_user_staff,
            message="Human staff configured" if has_user_staff else "No human staff members",
        ),
        "llm": SetupCheckResult(
            passed=has_llm_config,
            message="LLM provider ready" if has_llm_config else "LLM provider not configured",
        ),
    }

    errors: List[str] = []
    if not has_admin:
        errors.append("Admin account is required.")
    if not has_user_staff:
        errors.append("At least one human staff member is required.")
    if not has_llm_config:
        errors.append("LLM configuration must be completed or skipped explicitly.")

    warnings: List[str] = []
    is_valid = len(errors) == 0

    _maybe_mark_installed(db, setup_state, has_admin, has_user_staff, has_llm_config)
    db.commit()
    db.refresh(setup_state)

    return VerifySetupResponse(
        is_valid=is_valid,
        checks=checks,
        errors=errors,
        warnings=warnings,
    )

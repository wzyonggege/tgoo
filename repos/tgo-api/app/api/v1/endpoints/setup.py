"""Setup endpoints for installation/bootstrapping status."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models import Staff, StaffRole, SystemSetup
from app.schemas import SetupStatusResponse

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

    # LLM configuration now relies on environment-based FastGPT settings.
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

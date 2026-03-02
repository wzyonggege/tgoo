"""Quick reply endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import require_permission
from app.models import QuickReply, Staff
from app.schemas import (
    QuickReplyCreate,
    QuickReplyListParams,
    QuickReplyListResponse,
    QuickReplyResponse,
    QuickReplyUpdate,
)

logger = get_logger("endpoints.quick_replies")
router = APIRouter()


@router.get("", response_model=QuickReplyListResponse)
async def list_quick_replies(
    params: QuickReplyListParams = Depends(),
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("quick_replies:list")),
) -> QuickReplyListResponse:
    """List quick replies in current project."""
    query = db.query(QuickReply).filter(
        QuickReply.project_id == current_user.project_id,
        QuickReply.deleted_at.is_(None),
    )

    if params.active_only:
        query = query.filter(QuickReply.is_active.is_(True))
    if params.category:
        query = query.filter(QuickReply.category == params.category)
    if params.q:
        q = f"%{params.q}%"
        query = query.filter(
            or_(
                QuickReply.shortcut.ilike(q),
                QuickReply.title.ilike(q),
                QuickReply.content.ilike(q),
            )
        )

    total = query.count()
    items = (
        query.order_by(
            QuickReply.sort_order.asc(),
            QuickReply.usage_count.desc(),
            QuickReply.last_used_at.desc().nullslast(),
            QuickReply.updated_at.desc(),
        )
        .offset(params.offset)
        .limit(params.limit)
        .all()
    )

    return QuickReplyListResponse(
        data=[QuickReplyResponse.model_validate(item) for item in items],
        pagination={
            "total": total,
            "limit": params.limit,
            "offset": params.offset,
            "has_next": params.offset + params.limit < total,
            "has_prev": params.offset > 0,
        },
    )


@router.post("", response_model=QuickReplyResponse, status_code=status.HTTP_201_CREATED)
async def create_quick_reply(
    payload: QuickReplyCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("quick_replies:create")),
) -> QuickReplyResponse:
    """Create a quick reply."""
    exists = (
        db.query(QuickReply)
        .filter(
            QuickReply.project_id == current_user.project_id,
            QuickReply.shortcut == payload.shortcut,
            QuickReply.deleted_at.is_(None),
        )
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shortcut already exists",
        )

    quick_reply = QuickReply(
        project_id=current_user.project_id,
        title=payload.title,
        shortcut=payload.shortcut,
        content=payload.content,
        category=payload.category,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(quick_reply)
    db.commit()
    db.refresh(quick_reply)
    logger.info("Created quick reply %s", quick_reply.id)
    return QuickReplyResponse.model_validate(quick_reply)


@router.patch("/{quick_reply_id}", response_model=QuickReplyResponse)
async def update_quick_reply(
    quick_reply_id: UUID,
    payload: QuickReplyUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("quick_replies:update")),
) -> QuickReplyResponse:
    """Update a quick reply."""
    quick_reply = (
        db.query(QuickReply)
        .filter(
            QuickReply.id == quick_reply_id,
            QuickReply.project_id == current_user.project_id,
            QuickReply.deleted_at.is_(None),
        )
        .first()
    )
    if not quick_reply:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quick reply not found")

    update_data = payload.model_dump(exclude_unset=True)

    new_shortcut = update_data.get("shortcut")
    if new_shortcut and new_shortcut != quick_reply.shortcut:
        conflict = (
            db.query(QuickReply)
            .filter(
                QuickReply.project_id == current_user.project_id,
                QuickReply.shortcut == new_shortcut,
                QuickReply.id != quick_reply.id,
                QuickReply.deleted_at.is_(None),
            )
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shortcut already exists",
            )

    for field, value in update_data.items():
        setattr(quick_reply, field, value)

    quick_reply.updated_by = current_user.id
    quick_reply.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(quick_reply)
    return QuickReplyResponse.model_validate(quick_reply)


@router.delete("/{quick_reply_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quick_reply(
    quick_reply_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("quick_replies:delete")),
) -> None:
    """Soft delete a quick reply."""
    quick_reply = (
        db.query(QuickReply)
        .filter(
            QuickReply.id == quick_reply_id,
            QuickReply.project_id == current_user.project_id,
            QuickReply.deleted_at.is_(None),
        )
        .first()
    )
    if not quick_reply:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quick reply not found")

    now = datetime.utcnow()
    quick_reply.deleted_at = now
    quick_reply.updated_at = now
    quick_reply.updated_by = current_user.id
    db.commit()
    return None


@router.post("/{quick_reply_id}/use", status_code=status.HTTP_204_NO_CONTENT)
async def mark_quick_reply_used(
    quick_reply_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("quick_replies:read")),
) -> None:
    """Increment usage stats when quick reply is used in chat."""
    quick_reply = (
        db.query(QuickReply)
        .filter(
            QuickReply.id == quick_reply_id,
            QuickReply.project_id == current_user.project_id,
            QuickReply.deleted_at.is_(None),
        )
        .first()
    )
    if not quick_reply:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quick reply not found")

    now = datetime.utcnow()
    quick_reply.usage_count = quick_reply.usage_count + 1
    quick_reply.last_used_at = now
    quick_reply.updated_at = now
    quick_reply.updated_by = current_user.id
    db.commit()
    return None

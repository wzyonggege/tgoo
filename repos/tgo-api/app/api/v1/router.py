"""Main API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai_config,
    channels,
    chat,
    conversations,
    docs,
    email,
    platforms,
    projects,
    search,
    setup,
    sessions,
    staff,
    system,
    tags,
    visitors,
    visitor_assignment_rules,
    visitor_waiting_queue,
    wukongim,
    wukongim_webhook,
    utils,
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    projects.router,
    prefix="/projects",
    tags=["Projects"]
)

# Onboarding endpoints (JWT auth, project_id from current_user)
api_router.include_router(
    staff.router,
    prefix="/staff",
    tags=["Staff"]
)

api_router.include_router(
    visitors.router,
    prefix="/visitors",
    tags=["Visitors"]
)

api_router.include_router(
    visitor_assignment_rules.router,
    prefix="/visitor-assignment-rules",
    tags=["Visitor Assignment Rules"]
)

api_router.include_router(
    visitor_waiting_queue.router,
    prefix="/visitor-waiting-queue",
    tags=["Visitor Waiting Queue"]
)

api_router.include_router(
    tags.router,
    prefix="/tags",
    tags=["Tags"]
)

api_router.include_router(
    platforms.router,
    prefix="/platforms",
    tags=["Platforms"]
)

api_router.include_router(
    setup.router,
    prefix="/setup",
    tags=["Setup"],
)

# WuKongIM Public Endpoints
api_router.include_router(
    wukongim.router,
    prefix="/wukongim",
    tags=["WuKongIM"]
)


api_router.include_router(
    wukongim_webhook.router
)

# Email endpoints
api_router.include_router(
    email.router,
    prefix="/email",
    tags=["Email"]
)

api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"],
)

api_router.include_router(
    ai_config.router,
    prefix="/ai",
    tags=["AI Config"],
)

api_router.include_router(
    channels.router,
    prefix="/channels",
    tags=["Channels"],
)

api_router.include_router(
    conversations.router,
    prefix="/conversations",
    tags=["Conversations"],
)

api_router.include_router(
    sessions.router,
    prefix="/sessions",
    tags=["Sessions"],
)

api_router.include_router(
    search.router,
    prefix="/search",
    tags=["Search"],
)

# System information endpoints
api_router.include_router(
    system.router,
    prefix="/system",
    tags=["System"],
)

# Unified documentation endpoints
api_router.include_router(
    docs.router,
    tags=["Documentation"],
)

# Utility endpoints
api_router.include_router(
    utils.router,
    prefix="/utils",
    tags=["Utils"],
)

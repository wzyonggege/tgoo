# TGO-Tech API Service

Core Business Logic Microservice for the TGO-Tech customer service platform.

## Features

- **User Management**: Staff authentication and authorization
- **Visitor Management**: External user tracking and interactions
- **Assignment System**: Visitor-to-staff assignment operations
- **Tagging System**: Categorization and labeling for visitors and content
- **Platform Integration**: Multi-platform communication support
- **Multi-tenant Architecture**: Project-scoped isolation and access control
- **Dual Service Architecture**: Separate main API (authenticated) and internal services (no auth)

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Configuration**: Pydantic Settings
- **Authentication**: JWT tokens and API keys
- **Migrations**: Alembic
- **Development**: Docker Compose

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry
- Docker and Docker Compose

### Development Setup

1. **Clone and setup the project:**
   ```bash
   git clone <repository-url>
   cd tgo-api
   poetry install
   ```

2. **Start development environment:**
   ```bash
   make dev
   ```

   This command will:
   - Start PostgreSQL database in Docker
   - Run database migrations
   - Start the FastAPI development server

3. **Access the API:**
   - **Main API** (requires authentication):
     - API Documentation: http://localhost:8000/v1/docs
     - ReDoc Documentation: http://localhost:8000/v1/redoc
     - Health Check: http://localhost:8000/health
   - **Internal Services** (no authentication):
     - API Documentation: http://localhost:8001/internal/docs
     - Health Check: http://localhost:8001/health

4. **Start both services** (Main + Internal):
   ```bash
   ./scripts/start_services.sh
   ```

   Or start them separately:
   ```bash
   # Terminal 1 - Main API
   poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

   # Terminal 2 - Internal Services
   poetry run uvicorn app.internal:internal_app --host 127.0.0.1 --port 8001 --reload
   ```

### Available Commands

```bash
# Start development environment
make dev

# Run database migrations
make migrate

# Create new migration
make migration

# Run tests
make test

# Format code
make format

# Lint code
make lint

# Clean up
make clean
```

## Project Structure

```
app/
├── __init__.py
├── main.py                 # Main FastAPI application (port 8000, requires auth)
├── internal.py             # Internal services application (port 8001, no auth)
├── api/                    # API routes and endpoints
│   ├── v1/                 # Main API v1 (authenticated)
│   │   ├── router.py       # Main API router
│   │   └── endpoints/      # Individual endpoint modules
│   └── internal/           # Internal services (no authentication)
│       ├── router.py       # Internal services router
│       └── endpoints/      # Internal endpoint modules
├── core/                   # Core application components
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── database.py        # Database connection and session
│   ├── logging.py         # Logging configuration
│   └── security.py        # Authentication and security
├── models/                 # SQLAlchemy ORM models
│   ├── __init__.py
│   └── ...
├── schemas/                # Pydantic models for validation
│   ├── __init__.py
│   └── ...
└── services/              # Business logic services
    ├── __init__.py
    └── ...
```

## Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/tgo_api

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Configuration
PROJECT_NAME=TGO-Tech API Service
PROJECT_DESCRIPTION=Core Business Logic Microservice
PROJECT_VERSION=0.1.0
API_V1_STR=/v1

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"]

# Internal Services
INTERNAL_SERVICE_HOST=127.0.0.1
INTERNAL_SERVICE_PORT=8001
INTERNAL_CORS_ORIGINS=["http://localhost:*", "http://127.0.0.1:*"]

# Logging
LOG_LEVEL=INFO
```

## API Documentation

The API follows the OpenAPI 3.0 specification. Key features:

- **Dual Service Architecture**:
  - Main API (port 8000): Requires JWT authentication
  - Internal Services (port 8001): No authentication required
- **Dual Authentication**: JWT tokens and API keys (main API only)
- **Multi-tenant Support**: Project-scoped access control

内部服务的架构说明已迁移到主仓库 README 和 `specs/` 中的 OpenAPI 定义，可直接参考那里提供的最新结构。
- **Comprehensive Error Handling**: Structured error responses
- **Type Safety**: Full Pydantic validation for requests/responses

### Authentication

#### JWT Authentication (Service-to-service)
```bash
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### API Key Authentication (Project-scoped)
```bash
X-API-Key: ak_live_1234567890abcdef
```

## Database Schema

The application uses PostgreSQL with the following main entities:

- **api_projects**: Multi-tenant project isolation
- **api_platforms**: Communication platform configurations
- **api_staff**: Human users and AI agents
- **api_visitors**: External users/customers
- **api_visitor_assignments**: Visitor-to-staff assignments
- **api_tags**: Categorization system
- **api_visitor_tags**: Many-to-many visitor-tag relationships

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

Proprietary - TGO-Tech

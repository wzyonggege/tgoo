# =========================
# Builder stage
# =========================
FROM python:3.11-slim AS builder

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# No apt deps in builder: Python wheels cover current runtime dependencies.

# Install Python deps into local venv (without Poetry)
COPY requirements.runtime.txt ./
RUN set -eux; \
    python -m venv /app/.venv; \
    /app/.venv/bin/pip install --upgrade pip setuptools wheel; \
    install_requirements() { \
        /app/.venv/bin/pip install --prefer-binary --retries 3 --timeout 60 -r requirements.runtime.txt && return 0; \
        /app/.venv/bin/pip install --prefer-binary --retries 3 --timeout 60 -i https://pypi.org/simple -r requirements.runtime.txt && return 0; \
        /app/.venv/bin/pip install --prefer-binary --retries 3 --timeout 60 -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -r requirements.runtime.txt && return 0; \
        /app/.venv/bin/pip install --prefer-binary --retries 3 --timeout 60 -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com -r requirements.runtime.txt; \
    }; \
    install_requirements

# Copy application source (for things like Alembic env, etc.)
COPY . .

# =========================
# Runtime stage
# =========================
FROM python:3.11-slim AS runtime

# Build-time metadata (injected via Docker build args)
ARG APP_VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_TIME=unknown

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${APP_VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    BUILD_TIME=${BUILD_TIME}

WORKDIR /app

# No apt deps in runtime: avoid external apt mirror dependency.

# Copy virtualenv from builder (keep same path to preserve shebang)
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY . .

# Create logs directory (as before)
RUN mkdir -p logs

# Install CLI commands (resetadmin, etc.)
RUN chmod +x /app/scripts/resetadmin \
    && ln -s /app/scripts/resetadmin /usr/local/bin/resetadmin

# Expose ports (main + internal)
EXPOSE 8000
EXPOSE 8001

# Health check (both services)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5); urllib.request.urlopen('http://localhost:8001/health', timeout=5)"

# Run the application via uvicorn directly (no Poetry at runtime)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 & uvicorn app.internal:internal_app --host 0.0.0.0 --port 8001 & wait"]

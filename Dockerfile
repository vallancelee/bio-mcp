# Bio-MCP Dockerfile
# Multi-stage build to compile dependencies and create lean runtime image

# Build stage - includes build tools for compiling SpaCy/thinc
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies for native compilation
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock alembic.ini ./
COPY src/ src/
COPY migrations/ migrations/

# Install dependencies with build tools available
RUN uv sync --frozen

# Runtime stage - lean image without build tools
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv in runtime stage
RUN pip install uv

# Copy the entire uv environment from builder stage
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/pyproject.toml /app/uv.lock /app/alembic.ini ./
COPY --from=builder /app/src /app/src
COPY --from=builder /app/migrations /app/migrations

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Set environment variables
ENV PYTHONPATH=/app
ENV BIO_MCP_LOG_LEVEL=INFO

# Expose no ports (MCP uses stdio)
# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD uv run python -m bio_mcp.health || exit 1

# Run the MCP server
CMD ["uv", "run", "python", "-m", "bio_mcp.main"]
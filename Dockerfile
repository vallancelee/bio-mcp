# Bio-MCP Dockerfile
# Phase 1A: Simple single-stage build

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/

# Install dependencies
RUN uv sync --frozen

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
  CMD echo '{"jsonrpc": "2.0", "method": "ping", "id": 1}' | timeout 5s uv run python -m src.bio_mcp.main || exit 1

# Run the MCP server
CMD ["uv", "run", "python", "-m", "src.bio_mcp.main"]
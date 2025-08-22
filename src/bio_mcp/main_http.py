"""HTTP server entrypoint for Bio-MCP."""

import uvicorn

from bio_mcp.config.logging_config import auto_configure_logging, get_logger
from bio_mcp.http.app import create_app

# Configure logging
auto_configure_logging()
logger = get_logger(__name__)

# Create the FastAPI application
app = create_app()


def main():
    """Main entrypoint for HTTP server."""
    logger.info("Starting Bio-MCP HTTP server...")

    uvicorn.run(
        "bio_mcp.main_http:app",
        host="0.0.0.0",
        port=8080,
        log_config=None,  # Use our own logging configuration
        access_log=False,  # We'll handle access logging ourselves
        limit_concurrency=200,  # Reasonable default for T0
    )


if __name__ == "__main__":
    main()

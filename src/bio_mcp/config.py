"""
Configuration management for Bio-MCP server.
Phase 1A: Basic environment variable loading.
"""

import os
from dataclasses import dataclass

from . import __build__, __commit__, __version__


@dataclass
class Config:
    """Basic configuration for Bio-MCP server."""
    
    # Version information
    version: str = __version__
    build: str | None = __build__
    commit: str | None = __commit__
    
    # Server configuration
    server_name: str = "bio-mcp"
    log_level: str = "INFO"
    
    # API Keys (optional for Phase 1A)
    pubmed_api_key: str | None = None
    openai_api_key: str | None = None
    
    # Database (defaults to in-memory for Phase 1A)
    database_url: str = "sqlite:///:memory:"
    
    # Weaviate (defaults to local for Phase 1A)
    weaviate_url: str = "http://localhost:8080"
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            # Version info can be overridden by build process
            version=os.getenv("BIO_MCP_VERSION", __version__),
            build=os.getenv("BIO_MCP_BUILD", __build__),
            commit=os.getenv("BIO_MCP_COMMIT", __commit__),
            # Server config
            server_name=os.getenv("BIO_MCP_SERVER_NAME", "bio-mcp"),
            log_level=os.getenv("BIO_MCP_LOG_LEVEL", "INFO"),
            pubmed_api_key=os.getenv("PUBMED_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///:memory:"),
            weaviate_url=os.getenv("WEAVIATE_URL", "http://localhost:8080"),
        )
    
    def validate(self) -> None:
        """Basic validation - will be enhanced in Phase 1B."""
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            raise ValueError(f"Invalid log level: {self.log_level}")


# Global config instance
config = Config.from_env()
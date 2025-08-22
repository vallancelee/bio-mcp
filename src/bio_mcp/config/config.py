"""
Configuration management for Bio-MCP server.
Phase 1A: Basic environment variable loading.
"""

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from bio_mcp import __build__, __commit__, __version__

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv

    # Look for .env file in project root
    project_root = Path(__file__).parent.parent.parent
    env_file = project_root / ".env"

    if env_file.exists():
        load_dotenv(env_file)
        print(f"✓ Loaded configuration from {env_file}")
    else:
        print(f"i No .env file found at {env_file} (using environment variables)")

except ImportError:
    print("i python-dotenv not available (using environment variables only)")
    pass


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

    # Model configuration
    uuid_namespace: uuid.UUID = None  # Set in __post_init__
    document_schema_version: int = 1
    chunker_version: str = "v1.2.0"

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
            pubmed_api_key=os.getenv("BIO_MCP_PUBMED_API_KEY"),
            openai_api_key=os.getenv("BIO_MCP_OPENAI_API_KEY"),
            database_url=os.getenv("BIO_MCP_DATABASE_URL", "sqlite:///:memory:"),
            weaviate_url=os.getenv("BIO_MCP_WEAVIATE_URL", "http://localhost:8080"),
            # Model configuration will be set in __post_init__
        )

    def __post_init__(self):
        """Set fields that can't be set as dataclass defaults."""
        if self.uuid_namespace is None:
            default_uuid = "1b2c3d4e-0000-0000-0000-000000000000"
            self.uuid_namespace = uuid.UUID(
                os.getenv("BIO_MCP_UUID_NAMESPACE", default_uuid)
            )
        if (
            not hasattr(self, "document_schema_version")
            or self.document_schema_version == 1
        ):
            self.document_schema_version = int(
                os.getenv("BIO_MCP_DOCUMENT_SCHEMA_VERSION", "1")
            )
        if not hasattr(self, "chunker_version") or self.chunker_version == "v1.2.0":
            self.chunker_version = os.getenv("BIO_MCP_CHUNKER_VERSION", "v1.2.0")

    def validate(self) -> None:
        """Basic validation - will be enhanced in Phase 1B."""
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            raise ValueError(f"Invalid log level: {self.log_level}")


# Global config instance
config = Config.from_env()

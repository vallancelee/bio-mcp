"""
Configuration management for Bio-MCP server.
Phase 1A: Basic environment variable loading.
"""

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

# Import will be done lazily to avoid circular imports
from typing import TYPE_CHECKING

from bio_mcp import __build__, __commit__, __version__

if TYPE_CHECKING:
    from bio_mcp.orchestrator.config import OrchestratorConfig

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

    # OpenAI Embedding Configuration
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int | None = 1536

    # Legacy - kept for backward compatibility during migration
    biobert_model_name: str = "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
    biobert_max_tokens: int = 512

    # Collection Configuration
    weaviate_collection_v2: str = "DocumentChunk_v2"

    # Model configuration
    uuid_namespace: uuid.UUID = None  # Set in __post_init__
    document_schema_version: int = 1
    chunker_version: str = "v1.2.0"

    # Chunking configuration
    chunker_target_tokens: int = 325
    chunker_max_tokens: int = 450
    chunker_min_tokens: int = 120
    chunker_overlap_tokens: int = 50

    # Search boosting configuration
    boost_results_section: str = "0.15"
    boost_conclusions_section: str = "0.12"
    boost_methods_section: str = "0.05"
    boost_background_section: str = "0.02"
    quality_boost_factor: str = "0.1"
    recency_recent_years: str = "2"
    recency_moderate_years: str = "5"
    recency_old_years: str = "10"

    # Orchestrator configuration (lazy loaded)
    orchestrator: "OrchestratorConfig" = None

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
            openai_api_key=os.getenv("OPENAI_API_KEY")
            or os.getenv("BIO_MCP_OPENAI_API_KEY"),
            database_url=os.getenv("BIO_MCP_DATABASE_URL", "sqlite:///:memory:"),
            weaviate_url=os.getenv("BIO_MCP_WEAVIATE_URL", "http://localhost:8080"),
            # OpenAI Embedding Configuration
            openai_embedding_model=os.getenv(
                "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
            ),
            openai_embedding_dimensions=int(
                os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "1536")
            )
            if os.getenv("OPENAI_EMBEDDING_DIMENSIONS")
            else None,
            # Legacy BioBERT Configuration (backward compatibility)
            biobert_model_name=os.getenv(
                "BIO_MCP_EMBED_MODEL",
                "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb",
            ),
            biobert_max_tokens=int(os.getenv("BIO_MCP_EMBED_MAX_TOKENS", "512")),
            # Collection Configuration
            weaviate_collection_v2=os.getenv(
                "BIO_MCP_WEAVIATE_COLLECTION_V2", "DocumentChunk_v2"
            ),
            # Chunking configuration
            chunker_target_tokens=int(
                os.getenv("BIO_MCP_CHUNKER_TARGET_TOKENS", "325")
            ),
            chunker_max_tokens=int(os.getenv("BIO_MCP_CHUNKER_MAX_TOKENS", "450")),
            chunker_min_tokens=int(os.getenv("BIO_MCP_CHUNKER_MIN_TOKENS", "120")),
            chunker_overlap_tokens=int(
                os.getenv("BIO_MCP_CHUNKER_OVERLAP_TOKENS", "50")
            ),
            # Search boosting configuration
            boost_results_section=os.getenv("BIO_MCP_BOOST_RESULTS_SECTION", "0.15"),
            boost_conclusions_section=os.getenv(
                "BIO_MCP_BOOST_CONCLUSIONS_SECTION", "0.12"
            ),
            boost_methods_section=os.getenv("BIO_MCP_BOOST_METHODS_SECTION", "0.05"),
            boost_background_section=os.getenv(
                "BIO_MCP_BOOST_BACKGROUND_SECTION", "0.02"
            ),
            quality_boost_factor=os.getenv("BIO_MCP_QUALITY_BOOST_FACTOR", "0.1"),
            recency_recent_years=os.getenv("BIO_MCP_RECENCY_RECENT_YEARS", "2"),
            recency_moderate_years=os.getenv("BIO_MCP_RECENCY_MODERATE_YEARS", "5"),
            recency_old_years=os.getenv("BIO_MCP_RECENCY_OLD_YEARS", "10"),
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

        # Initialize orchestrator config lazily to avoid circular imports
        if self.orchestrator is None:
            from bio_mcp.orchestrator.config import OrchestratorConfig

            self.orchestrator = OrchestratorConfig.from_main_config(self)

    def validate(self) -> None:
        """Basic validation - will be enhanced in Phase 1B."""
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            raise ValueError(f"Invalid log level: {self.log_level}")


# Global config instance
config = Config.from_env()

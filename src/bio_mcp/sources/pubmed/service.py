"""
PubMed service implementation.
"""

from typing import Any

from bio_mcp.config.logging_config import get_logger
from bio_mcp.shared.services.base_service import BaseSourceService
from bio_mcp.shared.utils.checkpoints import CheckpointManager
from bio_mcp.sources.pubmed.client import PubMedClient
from bio_mcp.sources.pubmed.config import PubMedConfig
from bio_mcp.sources.pubmed.models import PubMedDocument
from bio_mcp.sources.pubmed.sync_strategy import PubMedSyncStrategy

logger = get_logger(__name__)


class PubMedService(BaseSourceService[PubMedDocument]):
    """Service for PubMed operations with multi-source architecture."""

    def __init__(
        self,
        config: PubMedConfig | None = None,
        checkpoint_manager: CheckpointManager | None = None,
    ):
        super().__init__("pubmed")
        self.config = config or PubMedConfig.from_env()
        self.checkpoint_manager = checkpoint_manager
        self.client: PubMedClient | None = None
        self.sync_strategy: PubMedSyncStrategy | None = None

    async def initialize(self) -> None:
        """Initialize PubMed service with client and sync strategy."""
        if self._initialized:
            return

        logger.info("Initializing PubMed service")

        # Initialize PubMed client
        self.client = PubMedClient(self.config)
        await self.client.initialize()

        # Initialize sync strategy if checkpoint manager available
        if self.checkpoint_manager:
            self.sync_strategy = PubMedSyncStrategy(
                self.checkpoint_manager, self.client
            )

        self._initialized = True
        logger.info("PubMed service initialized successfully")

    async def search(self, query: str, **kwargs) -> list[str]:
        """Search PubMed documents."""
        await self.ensure_initialized()

        if not self.client:
            raise RuntimeError("PubMed client not initialized")

        return await self.client.search(query, **kwargs)

    async def get_document(self, pmid: str) -> PubMedDocument:
        """Get a single PubMed document by PMID."""
        await self.ensure_initialized()

        if not self.client:
            raise RuntimeError("PubMed client not initialized")

        return await self.client.get_document(pmid)

    async def sync_documents(
        self, query: str, query_key: str, limit: int
    ) -> dict[str, Any]:
        """Sync PubMed documents using incremental EDAT strategy."""
        await self.ensure_initialized()

        if not self.sync_strategy:
            raise RuntimeError(
                "Sync strategy not initialized - checkpoint manager required"
            )

        return await self.sync_strategy.sync_incremental(query, query_key, limit)

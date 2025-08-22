"""
Base service class for data source services.
"""

from abc import ABC, abstractmethod
from typing import Any

from bio_mcp.shared.models.base_models import BaseClient, BaseDocument, BaseSyncStrategy


class BaseSourceService[T: BaseDocument](ABC):
    """Abstract base class for all data source services."""

    def __init__(self, source_name: str):
        self.source_name = source_name
        self.client: BaseClient[T] | None = None
        self.sync_strategy: BaseSyncStrategy | None = None
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service and its dependencies."""
        pass

    @abstractmethod
    async def search(self, query: str, **kwargs) -> list[str]:
        """Search documents in this source."""
        pass

    @abstractmethod
    async def get_document(self, doc_id: str) -> T:
        """Get a single document by ID."""
        pass

    @abstractmethod
    async def sync_documents(
        self, query: str, query_key: str, limit: int
    ) -> dict[str, Any]:
        """Sync documents from external source."""
        pass

    async def ensure_initialized(self) -> None:
        """Ensure service is initialized before use."""
        if not self._initialized:
            await self.initialize()
            self._initialized = True

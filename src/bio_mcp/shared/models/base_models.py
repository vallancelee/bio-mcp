"""
Abstract base classes for multi-source biomedical data.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar


@dataclass
class BaseDocument(ABC):
    """Abstract base for all document types across data sources."""
    id: str                          # Universal ID format: {source}:{source_id}
    source_id: str                   # Original ID from source (PMID, NCT ID, etc.)
    source: str                      # Source identifier ("pubmed", "clinicaltrials")
    title: str
    abstract: str | None = None
    content: str | None = None       # Full searchable content
    authors: list[str] = field(default_factory=list)
    publication_date: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)  # Source-specific fields
    quality_score: int = 0           # Normalized 0-100 score
    last_updated: datetime | None = None    # For sync watermarks
    
    @abstractmethod
    def get_search_content(self) -> str:
        """Return text content for embedding and search."""
        pass
    
    @abstractmethod
    def get_display_title(self) -> str:
        """Return formatted title for display."""
        pass


T = TypeVar('T', bound=BaseDocument)


class BaseClient(ABC, Generic[T]):
    """Abstract base for all external API clients."""
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> list[str]:
        """Return list of document IDs matching query."""
        pass
        
    @abstractmethod
    async def get_document(self, doc_id: str) -> T:
        """Fetch single document by source ID."""
        pass
        
    @abstractmethod
    async def get_documents(self, doc_ids: list[str]) -> list[T]:
        """Fetch multiple documents efficiently."""
        pass
    
    @abstractmethod
    async def get_updates_since(self, timestamp: datetime, limit: int = 100) -> list[T]:
        """Get documents updated since timestamp (for incremental sync)."""
        pass


class BaseSyncStrategy(ABC):
    """Abstract base for source-specific sync strategies."""
    
    @abstractmethod
    async def get_sync_watermark(self, query_key: str) -> datetime | None:
        """Get last sync timestamp for a query."""
        pass
    
    @abstractmethod
    async def set_sync_watermark(self, query_key: str, timestamp: datetime) -> None:
        """Update sync watermark for a query."""
        pass
    
    @abstractmethod
    async def sync_incremental(self, query: str, query_key: str, limit: int) -> dict:
        """Perform incremental sync based on watermark."""
        pass


class BaseService(ABC, Generic[T]):
    """Abstract base for all data source services."""
    
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
    async def sync_documents(self, query: str, query_key: str, limit: int) -> dict[str, Any]:
        """Sync documents from external source."""
        pass
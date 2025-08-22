"""
Unit tests for base models and abstract classes.
"""

from datetime import datetime

import pytest

from bio_mcp.shared.models.base_models import (
    BaseClient,
    BaseDocument,
    BaseService,
    BaseSyncStrategy,
)


class ConcreteDocument(BaseDocument):
    """Concrete implementation of BaseDocument for testing."""

    def get_search_content(self) -> str:
        parts = [self.title]
        if self.abstract:
            parts.append(self.abstract)
        return " ".join(parts)

    def get_display_title(self) -> str:
        return f"{self.title} ({self.source})"


class ConcreteClient(BaseClient):
    """Concrete implementation of BaseClient for testing."""

    async def search(self, query: str, **kwargs) -> list[str]:
        return ["doc1", "doc2", "doc3"]

    async def get_document(self, doc_id: str) -> ConcreteDocument:
        return ConcreteDocument(
            id=f"test:{doc_id}",
            source_id=doc_id,
            source="test",
            title=f"Document {doc_id}",
        )

    async def get_documents(self, doc_ids: list[str]) -> list[ConcreteDocument]:
        return [await self.get_document(doc_id) for doc_id in doc_ids]

    async def get_updates_since(
        self, timestamp: datetime, limit: int = 100
    ) -> list[ConcreteDocument]:
        return [
            ConcreteDocument(
                id="test:updated1",
                source_id="updated1",
                source="test",
                title="Updated Document 1",
                last_updated=timestamp,
            )
        ]


class ConcreteSyncStrategy(BaseSyncStrategy):
    """Concrete implementation of BaseSyncStrategy for testing."""

    def __init__(self):
        self.watermarks = {}

    async def get_sync_watermark(self, query_key: str) -> datetime | None:
        return self.watermarks.get(query_key)

    async def set_sync_watermark(self, query_key: str, timestamp: datetime) -> None:
        self.watermarks[query_key] = timestamp

    async def sync_incremental(self, query: str, query_key: str, limit: int) -> dict:
        return {
            "status": "success",
            "documents_synced": 5,
            "query": query,
            "query_key": query_key,
        }


class ConcreteService(BaseService):
    """Concrete implementation of BaseService for testing."""

    async def initialize(self) -> None:
        self.client = ConcreteClient()
        self.sync_strategy = ConcreteSyncStrategy()
        self._initialized = True

    async def search(self, query: str, **kwargs) -> list[str]:
        if not self._initialized:
            await self.initialize()
        return await self.client.search(query, **kwargs)

    async def get_document(self, doc_id: str) -> ConcreteDocument:
        if not self._initialized:
            await self.initialize()
        return await self.client.get_document(doc_id)

    async def sync_documents(self, query: str, query_key: str, limit: int) -> dict:
        if not self._initialized:
            await self.initialize()
        return await self.sync_strategy.sync_incremental(query, query_key, limit)


class TestBaseDocument:
    """Test BaseDocument abstract class."""

    def test_concrete_document_creation(self):
        """Test creating a concrete document."""
        doc = ConcreteDocument(
            id="test:123", source_id="123", source="test", title="Test Document"
        )

        assert doc.id == "test:123"
        assert doc.source_id == "123"
        assert doc.source == "test"
        assert doc.title == "Test Document"
        assert doc.abstract is None
        assert doc.content is None
        assert doc.authors == []
        assert doc.publication_date is None
        assert doc.metadata == {}
        assert doc.quality_score == 0
        assert doc.last_updated is None

    def test_concrete_document_with_all_fields(self):
        """Test creating a document with all fields."""
        pub_date = datetime(2023, 6, 15)
        updated_date = datetime(2023, 7, 1)

        doc = ConcreteDocument(
            id="test:456",
            source_id="456",
            source="test",
            title="Comprehensive Test Document",
            abstract="This is the abstract",
            content="Full content here",
            authors=["Author A", "Author B"],
            publication_date=pub_date,
            metadata={"category": "research", "priority": "high"},
            quality_score=85,
            last_updated=updated_date,
        )

        assert doc.id == "test:456"
        assert doc.source_id == "456"
        assert doc.source == "test"
        assert doc.title == "Comprehensive Test Document"
        assert doc.abstract == "This is the abstract"
        assert doc.content == "Full content here"
        assert doc.authors == ["Author A", "Author B"]
        assert doc.publication_date == pub_date
        assert doc.metadata == {"category": "research", "priority": "high"}
        assert doc.quality_score == 85
        assert doc.last_updated == updated_date

    def test_get_search_content(self):
        """Test get_search_content method."""
        # Title only
        doc = ConcreteDocument(
            id="test:1", source_id="1", source="test", title="Test Title"
        )
        assert doc.get_search_content() == "Test Title"

        # Title and abstract
        doc = ConcreteDocument(
            id="test:2",
            source_id="2",
            source="test",
            title="Test Title",
            abstract="Test abstract content",
        )
        assert doc.get_search_content() == "Test Title Test abstract content"

    def test_get_display_title(self):
        """Test get_display_title method."""
        doc = ConcreteDocument(
            id="test:1", source_id="1", source="test", title="Display Title Test"
        )
        assert doc.get_display_title() == "Display Title Test (test)"

    def test_cannot_instantiate_abstract_base(self):
        """Test that BaseDocument cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseDocument(id="test:1", source_id="1", source="test", title="Test")


class TestBaseClient:
    """Test BaseClient abstract class."""

    @pytest.mark.asyncio
    async def test_concrete_client_search(self):
        """Test concrete client search functionality."""
        client = ConcreteClient()
        results = await client.search("test query")
        assert results == ["doc1", "doc2", "doc3"]

    @pytest.mark.asyncio
    async def test_concrete_client_get_document(self):
        """Test concrete client get_document functionality."""
        client = ConcreteClient()
        doc = await client.get_document("123")

        assert isinstance(doc, ConcreteDocument)
        assert doc.id == "test:123"
        assert doc.source_id == "123"
        assert doc.source == "test"
        assert doc.title == "Document 123"

    @pytest.mark.asyncio
    async def test_concrete_client_get_documents(self):
        """Test concrete client get_documents functionality."""
        client = ConcreteClient()
        docs = await client.get_documents(["123", "456"])

        assert len(docs) == 2
        assert all(isinstance(doc, ConcreteDocument) for doc in docs)
        assert docs[0].source_id == "123"
        assert docs[1].source_id == "456"

    @pytest.mark.asyncio
    async def test_concrete_client_get_updates_since(self):
        """Test concrete client get_updates_since functionality."""
        client = ConcreteClient()
        timestamp = datetime(2023, 6, 1)

        docs = await client.get_updates_since(timestamp, limit=50)

        assert len(docs) == 1
        assert isinstance(docs[0], ConcreteDocument)
        assert docs[0].source_id == "updated1"
        assert docs[0].last_updated == timestamp

    def test_cannot_instantiate_abstract_base_client(self):
        """Test that BaseClient cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseClient()


class TestBaseSyncStrategy:
    """Test BaseSyncStrategy abstract class."""

    @pytest.mark.asyncio
    async def test_concrete_sync_strategy_watermark_operations(self):
        """Test concrete sync strategy watermark operations."""
        strategy = ConcreteSyncStrategy()
        query_key = "test_query"
        timestamp = datetime(2023, 6, 15)

        # Initially no watermark
        watermark = await strategy.get_sync_watermark(query_key)
        assert watermark is None

        # Set watermark
        await strategy.set_sync_watermark(query_key, timestamp)

        # Retrieve watermark
        watermark = await strategy.get_sync_watermark(query_key)
        assert watermark == timestamp

    @pytest.mark.asyncio
    async def test_concrete_sync_strategy_sync_incremental(self):
        """Test concrete sync strategy incremental sync."""
        strategy = ConcreteSyncStrategy()

        result = await strategy.sync_incremental("test query", "query_key", 10)

        assert result["status"] == "success"
        assert result["documents_synced"] == 5
        assert result["query"] == "test query"
        assert result["query_key"] == "query_key"

    def test_cannot_instantiate_abstract_base_sync_strategy(self):
        """Test that BaseSyncStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseSyncStrategy()


class TestBaseService:
    """Test BaseService abstract class."""

    def test_service_initialization_state(self):
        """Test service initialization state."""
        service = ConcreteService("test_source")

        assert service.source_name == "test_source"
        assert service.client is None
        assert service.sync_strategy is None
        assert service._initialized is False

    @pytest.mark.asyncio
    async def test_service_initialize(self):
        """Test service initialization."""
        service = ConcreteService("test_source")

        await service.initialize()

        assert service._initialized is True
        assert service.client is not None
        assert service.sync_strategy is not None
        assert isinstance(service.client, ConcreteClient)
        assert isinstance(service.sync_strategy, ConcreteSyncStrategy)

    @pytest.mark.asyncio
    async def test_service_search(self):
        """Test service search functionality."""
        service = ConcreteService("test_source")

        # Should auto-initialize if not initialized
        results = await service.search("test query")

        assert service._initialized is True
        assert results == ["doc1", "doc2", "doc3"]

    @pytest.mark.asyncio
    async def test_service_get_document(self):
        """Test service get_document functionality."""
        service = ConcreteService("test_source")

        # Should auto-initialize if not initialized
        doc = await service.get_document("789")

        assert service._initialized is True
        assert isinstance(doc, ConcreteDocument)
        assert doc.source_id == "789"

    @pytest.mark.asyncio
    async def test_service_sync_documents(self):
        """Test service sync_documents functionality."""
        service = ConcreteService("test_source")

        # Should auto-initialize if not initialized
        result = await service.sync_documents("sync query", "sync_key", 25)

        assert service._initialized is True
        assert result["status"] == "success"
        assert result["query"] == "sync query"
        assert result["query_key"] == "sync_key"

    @pytest.mark.asyncio
    async def test_service_multiple_initialization_calls(self):
        """Test that multiple initialization calls don't cause issues."""
        service = ConcreteService("test_source")

        # First initialization
        await service.initialize()
        assert service._initialized is True
        assert service.client is not None
        assert service.sync_strategy is not None

        # Second initialization (should remain initialized)
        await service.initialize()

        # Service should remain initialized with valid client and strategy
        assert service._initialized is True
        assert service.client is not None
        assert service.sync_strategy is not None

    def test_cannot_instantiate_abstract_base_service(self):
        """Test that BaseService cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseService("test_source")


# Mark as unit tests
pytestmark = pytest.mark.unit

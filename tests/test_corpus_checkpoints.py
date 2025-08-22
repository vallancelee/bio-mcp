"""
Tests for corpus checkpoint functionality (Phase 4B.3).
Tests checkpoint creation, retrieval, listing, and deletion for reproducible research.

Run with: pytest tests/test_corpus_checkpoints.py -v -s
"""

from unittest.mock import AsyncMock, patch

import pytest

from bio_mcp.mcp.corpus_tools import (
    CorpusCheckpointManager,
    corpus_checkpoint_create_tool,
    corpus_checkpoint_delete_tool,
    corpus_checkpoint_get_tool,
    corpus_checkpoint_list_tool,
)
from bio_mcp.services.services import CorpusCheckpointService
from bio_mcp.shared.models.database_models import CorpusCheckpoint


class TestCorpusCheckpointDatabase:
    """Test corpus checkpoint database operations."""

    @pytest.mark.asyncio
    async def test_corpus_checkpoint_creation(self):
        """Test creating a new corpus checkpoint."""
        with patch("src.bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db = AsyncMock()
            mock_db_class.return_value = mock_db

            # Mock checkpoint creation
            mock_checkpoint = CorpusCheckpoint(
                checkpoint_id="cardiac_research_v1",
                name="Cardiac Research Corpus v1.0",
                description="Comprehensive cardiac research corpus with 500 papers",
                document_count="500",
                last_sync_edat="2024/08/15",
                primary_queries=["heart disease", "cardiac treatment"],
                total_documents="500",
                total_vectors="500",
                version="1.0",
            )
            mock_db.create_corpus_checkpoint.return_value = mock_checkpoint

            service = CorpusCheckpointService()
            service.manager = mock_db

            # Test checkpoint creation
            result = await service.create_checkpoint(
                checkpoint_id="cardiac_research_v1",
                name="Cardiac Research Corpus v1.0",
                description="Comprehensive cardiac research corpus with 500 papers",
                primary_queries=["heart disease", "cardiac treatment"],
            )

            assert result.checkpoint_id == "cardiac_research_v1"
            assert result.name == "Cardiac Research Corpus v1.0"
            assert result.total_documents == "500"
            assert result.primary_queries == ["heart disease", "cardiac treatment"]

    @pytest.mark.asyncio
    async def test_corpus_checkpoint_retrieval(self):
        """Test retrieving an existing corpus checkpoint."""
        with patch("src.bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db = AsyncMock()
            mock_db_class.return_value = mock_db

            # Mock existing checkpoint
            mock_checkpoint = CorpusCheckpoint(
                checkpoint_id="diabetes_research_v2",
                name="Diabetes Research Corpus v2.0",
                description="Extended diabetes research with recent studies",
                document_count="750",
                last_sync_edat="2024/08/18",
                primary_queries=["diabetes treatment", "insulin therapy"],
                total_documents="750",
                total_vectors="750",
                version="2.0",
                parent_checkpoint_id="diabetes_research_v1",
            )
            mock_db.get_corpus_checkpoint.return_value = mock_checkpoint

            service = CorpusCheckpointService()
            service.manager = mock_db

            # Test checkpoint retrieval
            result = await service.get_checkpoint("diabetes_research_v2")

            assert result is not None
            assert result.checkpoint_id == "diabetes_research_v2"
            assert result.name == "Diabetes Research Corpus v2.0"
            assert result.total_documents == "750"
            assert result.parent_checkpoint_id == "diabetes_research_v1"

    @pytest.mark.asyncio
    async def test_corpus_checkpoint_listing(self):
        """Test listing corpus checkpoints with pagination."""
        with patch("src.bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db = AsyncMock()
            mock_db_class.return_value = mock_db

            # Mock list of checkpoints
            mock_checkpoints = [
                CorpusCheckpoint(
                    checkpoint_id="checkpoint_1",
                    name="Research Checkpoint 1",
                    description="First checkpoint",
                    total_documents="100",
                ),
                CorpusCheckpoint(
                    checkpoint_id="checkpoint_2",
                    name="Research Checkpoint 2",
                    description="Second checkpoint",
                    total_documents="200",
                ),
                CorpusCheckpoint(
                    checkpoint_id="checkpoint_3",
                    name="Research Checkpoint 3",
                    description="Third checkpoint",
                    total_documents="300",
                ),
            ]
            mock_db.list_corpus_checkpoints.return_value = mock_checkpoints

            service = CorpusCheckpointService()
            service.manager = mock_db

            # Test checkpoint listing
            result = await service.list_checkpoints(limit=10, offset=0)

            assert len(result) == 3
            assert result[0].checkpoint_id == "checkpoint_1"
            assert result[1].checkpoint_id == "checkpoint_2"
            assert result[2].checkpoint_id == "checkpoint_3"


class TestCorpusCheckpointManager:
    """Test corpus checkpoint manager operations."""

    @pytest.mark.asyncio
    async def test_checkpoint_manager_create_success(self):
        """Test successful checkpoint creation via manager."""
        with patch(
            "src.bio_mcp.services.services.CorpusCheckpointService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service

            # Mock successful checkpoint creation
            mock_checkpoint = CorpusCheckpoint(
                checkpoint_id="oncology_research",
                name="Oncology Research Corpus",
                description="Cancer research papers and clinical trials",
                document_count="1200",
                last_sync_edat="2024/08/19",
                primary_queries=["cancer treatment", "oncology", "chemotherapy"],
                total_documents="1200",
                total_vectors="1200",
                version="1.0",
            )
            mock_service.create_checkpoint.return_value = mock_checkpoint

            manager = CorpusCheckpointManager()
            manager.checkpoint_service = mock_service
            manager.initialized = True

            # Test checkpoint creation
            result = await manager.create_checkpoint(
                checkpoint_id="oncology_research",
                name="Oncology Research Corpus",
                description="Cancer research papers and clinical trials",
                primary_queries=["cancer treatment", "oncology", "chemotherapy"],
            )

            assert result.success is True
            assert result.operation == "create"
            assert result.checkpoint_id == "oncology_research"
            assert result.checkpoint_data["name"] == "Oncology Research Corpus"
            assert result.checkpoint_data["total_documents"] == "1200"

    @pytest.mark.asyncio
    async def test_checkpoint_manager_get_not_found(self):
        """Test checkpoint retrieval when checkpoint doesn't exist."""
        with patch(
            "src.bio_mcp.services.services.CorpusCheckpointService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service

            # Mock checkpoint not found
            mock_service.get_checkpoint.return_value = None

            manager = CorpusCheckpointManager()
            manager.checkpoint_service = mock_service
            manager.initialized = True

            # Test checkpoint retrieval
            result = await manager.get_checkpoint("nonexistent_checkpoint")

            assert result.success is True
            assert result.operation == "get"
            assert result.checkpoint_id == "nonexistent_checkpoint"
            assert result.checkpoint_data is None

    @pytest.mark.asyncio
    async def test_checkpoint_manager_delete_success(self):
        """Test successful checkpoint deletion."""
        with patch(
            "src.bio_mcp.services.services.CorpusCheckpointService"
        ) as mock_service_class:
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service

            # Mock successful deletion
            mock_service.delete_checkpoint.return_value = True

            manager = CorpusCheckpointManager()
            manager.checkpoint_service = mock_service
            manager.initialized = True

            # Test checkpoint deletion
            result = await manager.delete_checkpoint("old_checkpoint")

            assert result.success is True
            assert result.operation == "delete"
            assert result.checkpoint_id == "old_checkpoint"


class TestCorpusCheckpointMCPTools:
    """Test the MCP tools for corpus checkpoints."""

    @pytest.mark.asyncio
    async def test_checkpoint_create_tool_success(self):
        """Test successful checkpoint creation via MCP tool."""
        with patch(
            "src.bio_mcp.mcp.corpus_tools.get_checkpoint_manager"
        ) as mock_get_manager:
            # Mock the manager and its create method
            mock_manager = AsyncMock(spec=CorpusCheckpointManager)
            mock_get_manager.return_value = mock_manager

            # Mock successful creation result
            from src.bio_mcp.mcp.corpus_tools import CheckpointResult

            mock_result = CheckpointResult(
                checkpoint_id="immunology_corpus",
                operation="create",
                success=True,
                execution_time_ms=850.0,
                checkpoint_data={
                    "checkpoint_id": "immunology_corpus",
                    "name": "Immunology Research Corpus",
                    "description": "Comprehensive immunology research papers",
                    "total_documents": "800",
                    "total_vectors": "800",
                    "version": "1.0",
                    "primary_queries": ["immunology", "immune system", "vaccines"],
                },
            )
            mock_manager.create_checkpoint.return_value = mock_result

            # Test checkpoint creation tool
            result = await corpus_checkpoint_create_tool(
                "corpus.checkpoint.create",
                {
                    "checkpoint_id": "immunology_corpus",
                    "name": "Immunology Research Corpus",
                    "description": "Comprehensive immunology research papers",
                    "primary_queries": ["immunology", "immune system", "vaccines"],
                },
            )

            assert len(result) == 1
            response_text = result[0].text

            # Verify creation success indicators
            assert "✅ Corpus checkpoint created successfully" in response_text
            assert "immunology_corpus" in response_text
            assert "Immunology Research Corpus" in response_text
            assert "Total Documents:** 800" in response_text
            assert "850.0ms" in response_text

            # Verify manager was called with correct parameters
            mock_manager.create_checkpoint.assert_called_once_with(
                checkpoint_id="immunology_corpus",
                name="Immunology Research Corpus",
                description="Comprehensive immunology research papers",
                primary_queries=["immunology", "immune system", "vaccines"],
                parent_checkpoint_id=None,
            )

    @pytest.mark.asyncio
    async def test_checkpoint_create_tool_missing_params(self):
        """Test checkpoint creation tool with missing required parameters."""
        # Test missing checkpoint_id
        result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create", {"name": "Test Corpus"}
        )

        assert len(result) == 1
        response_text = result[0].text
        assert "❌ Error: 'checkpoint_id' parameter is required" in response_text

        # Test missing name
        result = await corpus_checkpoint_create_tool(
            "corpus.checkpoint.create", {"checkpoint_id": "test_checkpoint"}
        )

        assert len(result) == 1
        response_text = result[0].text
        assert "❌ Error: 'name' parameter is required" in response_text

    @pytest.mark.asyncio
    async def test_checkpoint_get_tool_success(self):
        """Test successful checkpoint retrieval via MCP tool."""
        with patch(
            "src.bio_mcp.mcp.corpus_tools.get_checkpoint_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock(spec=CorpusCheckpointManager)
            mock_get_manager.return_value = mock_manager

            # Mock successful retrieval result
            from src.bio_mcp.mcp.corpus_tools import CheckpointResult

            mock_result = CheckpointResult(
                checkpoint_id="neuroscience_corpus",
                operation="get",
                success=True,
                execution_time_ms=425.0,
                checkpoint_data={
                    "checkpoint_id": "neuroscience_corpus",
                    "name": "Neuroscience Research Corpus",
                    "description": "Brain and neural research papers",
                    "total_documents": "650",
                    "total_vectors": "650",
                    "version": "1.0",
                    "created_at": "2024-08-19T10:30:00+00:00",
                    "primary_queries": [
                        "neuroscience",
                        "brain research",
                        "neural networks",
                    ],
                },
            )
            mock_manager.get_checkpoint.return_value = mock_result

            # Test checkpoint retrieval tool
            result = await corpus_checkpoint_get_tool(
                "corpus.checkpoint.get", {"checkpoint_id": "neuroscience_corpus"}
            )

            assert len(result) == 1
            response_text = result[0].text

            # Verify retrieval success indicators
            assert "📋 Corpus Checkpoint Details" in response_text
            assert "neuroscience_corpus" in response_text
            assert "Neuroscience Research Corpus" in response_text
            assert "Total Documents: 650" in response_text
            assert "425.0ms" in response_text

    @pytest.mark.asyncio
    async def test_checkpoint_list_tool_success(self):
        """Test successful checkpoint listing via MCP tool."""
        with patch(
            "src.bio_mcp.mcp.corpus_tools.get_checkpoint_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock(spec=CorpusCheckpointManager)
            mock_get_manager.return_value = mock_manager

            # Mock successful list result
            from src.bio_mcp.mcp.corpus_tools import CheckpointListResult

            mock_result = CheckpointListResult(
                total_found=2,
                checkpoints=[
                    {
                        "checkpoint_id": "checkpoint_1",
                        "name": "First Checkpoint",
                        "description": "Initial research corpus",
                        "total_documents": "300",
                        "version": "1.0",
                        "created_at": "2024-08-15T09:00:00+00:00",
                    },
                    {
                        "checkpoint_id": "checkpoint_2",
                        "name": "Second Checkpoint",
                        "description": "Extended research corpus",
                        "total_documents": "500",
                        "version": "1.1",
                        "created_at": "2024-08-18T14:30:00+00:00",
                    },
                ],
                execution_time_ms=320.0,
                limit=20,
                offset=0,
            )
            mock_manager.list_checkpoints.return_value = mock_result

            # Test checkpoint listing tool
            result = await corpus_checkpoint_list_tool(
                "corpus.checkpoint.list", {"limit": 20, "offset": 0}
            )

            assert len(result) == 1
            response_text = result[0].text

            # Verify list success indicators
            assert "📋 **Corpus Checkpoints**" in response_text
            assert "Found:** 2 checkpoints" in response_text
            assert "First Checkpoint" in response_text
            assert "Second Checkpoint" in response_text
            assert "320.0ms" in response_text

    @pytest.mark.asyncio
    async def test_checkpoint_delete_tool_success(self):
        """Test successful checkpoint deletion via MCP tool."""
        with patch(
            "src.bio_mcp.mcp.corpus_tools.get_checkpoint_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock(spec=CorpusCheckpointManager)
            mock_get_manager.return_value = mock_manager

            # Mock successful deletion result
            from src.bio_mcp.mcp.corpus_tools import CheckpointResult

            mock_result = CheckpointResult(
                checkpoint_id="old_checkpoint",
                operation="delete",
                success=True,
                execution_time_ms=180.0,
            )
            mock_manager.delete_checkpoint.return_value = mock_result

            # Test checkpoint deletion tool
            result = await corpus_checkpoint_delete_tool(
                "corpus.checkpoint.delete", {"checkpoint_id": "old_checkpoint"}
            )

            assert len(result) == 1
            response_text = result[0].text

            # Verify deletion success indicators
            assert "🗑️ Checkpoint deleted: old_checkpoint" in response_text
            assert "permanently removed" in response_text
            assert "180.0ms" in response_text


class TestCheckpointLineage:
    """Test checkpoint lineage and versioning functionality."""

    @pytest.mark.asyncio
    async def test_checkpoint_lineage_tracking(self):
        """Test that checkpoint lineage is tracked correctly."""
        with patch("src.bio_mcp.services.services.DatabaseManager") as mock_db_class:
            mock_db = AsyncMock()
            mock_db_class.return_value = mock_db

            # Mock lineage chain: v1 -> v2 -> v3
            checkpoints = {
                "research_v3": CorpusCheckpoint(
                    checkpoint_id="research_v3",
                    name="Research v3.0",
                    version="3.0",
                    parent_checkpoint_id="research_v2",
                    total_documents="1000",
                ),
                "research_v2": CorpusCheckpoint(
                    checkpoint_id="research_v2",
                    name="Research v2.0",
                    version="2.0",
                    parent_checkpoint_id="research_v1",
                    total_documents="500",
                ),
                "research_v1": CorpusCheckpoint(
                    checkpoint_id="research_v1",
                    name="Research v1.0",
                    version="1.0",
                    parent_checkpoint_id=None,
                    total_documents="200",
                ),
            }

            def mock_get_checkpoint(checkpoint_id):
                return checkpoints.get(checkpoint_id)

            mock_db.get_corpus_checkpoint.side_effect = mock_get_checkpoint

            service = CorpusCheckpointService()
            service.manager = mock_db

            # Test lineage retrieval
            lineage = await service.get_checkpoint_lineage("research_v3")

            assert len(lineage) == 3
            assert lineage[0]["checkpoint_id"] == "research_v3"
            assert lineage[1]["checkpoint_id"] == "research_v2"
            assert lineage[2]["checkpoint_id"] == "research_v1"
            assert lineage[0]["total_documents"] == "1000"
            assert lineage[1]["total_documents"] == "500"
            assert lineage[2]["total_documents"] == "200"


class TestCheckpointEdgeCases:
    """Test edge cases and error handling for checkpoints."""

    @pytest.mark.asyncio
    async def test_checkpoint_creation_duplicate_id(self):
        """Test checkpoint creation with duplicate ID."""
        with patch(
            "src.bio_mcp.mcp.corpus_tools.get_checkpoint_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock(spec=CorpusCheckpointManager)
            mock_get_manager.return_value = mock_manager

            # Mock duplicate ID error
            from src.bio_mcp.mcp.corpus_tools import CheckpointResult

            mock_result = CheckpointResult(
                checkpoint_id="duplicate_id",
                operation="create",
                success=False,
                execution_time_ms=50.0,
                error_message="Checkpoint 'duplicate_id' already exists",
            )
            mock_manager.create_checkpoint.return_value = mock_result

            # Test duplicate checkpoint creation
            result = await corpus_checkpoint_create_tool(
                "corpus.checkpoint.create",
                {"checkpoint_id": "duplicate_id", "name": "Duplicate Checkpoint"},
            )

            assert len(result) == 1
            response_text = result[0].text

            # Verify error handling
            assert "❌ Checkpoint create failed" in response_text
            assert "duplicate_id" in response_text
            assert "already exists" in response_text

    @pytest.mark.asyncio
    async def test_checkpoint_list_empty_database(self):
        """Test checkpoint listing when database is empty."""
        with patch(
            "src.bio_mcp.mcp.corpus_tools.get_checkpoint_manager"
        ) as mock_get_manager:
            mock_manager = AsyncMock(spec=CorpusCheckpointManager)
            mock_get_manager.return_value = mock_manager

            # Mock empty list result
            from src.bio_mcp.mcp.corpus_tools import CheckpointListResult

            mock_result = CheckpointListResult(
                total_found=0,
                checkpoints=[],
                execution_time_ms=120.0,
                limit=20,
                offset=0,
            )
            mock_manager.list_checkpoints.return_value = mock_result

            # Test empty checkpoint listing
            result = await corpus_checkpoint_list_tool("corpus.checkpoint.list", {})

            assert len(result) == 1
            response_text = result[0].text

            # Verify empty state handling
            assert "📋 No corpus checkpoints found" in response_text
            assert "corpus.checkpoint.create" in response_text
            assert "120.0ms" in response_text


# Pytest configuration for corpus checkpoint tests
pytestmark = pytest.mark.unit

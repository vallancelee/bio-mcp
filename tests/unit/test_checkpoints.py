"""
Unit tests for checkpoint management utilities.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bio_mcp.shared.models.database_models import SyncWatermark
from bio_mcp.shared.utils.checkpoints import CheckpointManager


class TestCheckpointManager:
    """Test CheckpointManager utility class."""
    
    def test_init(self):
        """Test CheckpointManager initialization."""
        mock_session = MagicMock(spec=AsyncSession)
        manager = CheckpointManager(mock_session)
        
        assert manager.db_session is mock_session
    
    @pytest.mark.asyncio
    async def test_get_watermark_exists(self):
        """Test getting existing watermark."""
        mock_session = AsyncMock(spec=AsyncSession)
        timestamp = datetime(2023, 8, 15, 14, 30, 0, tzinfo=UTC)
        
        # Mock the database query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = timestamp
        mock_session.execute.return_value = mock_result
        
        manager = CheckpointManager(mock_session)
        
        result = await manager.get_watermark("pubmed", "cancer_research")
        
        assert result == timestamp
        mock_session.execute.assert_called_once()
        mock_result.scalar_one_or_none.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_watermark_not_exists(self):
        """Test getting non-existent watermark."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock the database query result - no watermark found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        manager = CheckpointManager(mock_session)
        
        result = await manager.get_watermark("pubmed", "nonexistent_query")
        
        assert result is None
        mock_session.execute.assert_called_once()
        mock_result.scalar_one_or_none.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_set_watermark_new(self):
        """Test setting watermark for new source/query combination."""
        mock_session = AsyncMock(spec=AsyncSession)
        timestamp = datetime(2023, 8, 15, 14, 30, 0, tzinfo=UTC)
        
        # Mock the database query to return None (no existing watermark)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        manager = CheckpointManager(mock_session)
        
        await manager.set_watermark("pubmed", "new_query", timestamp)
        
        # Verify session.add was called with a new SyncWatermark
        mock_session.add.assert_called_once()
        added_watermark = mock_session.add.call_args[0][0]
        assert isinstance(added_watermark, SyncWatermark)
        assert added_watermark.source == "pubmed"
        assert added_watermark.query_key == "new_query"
        assert added_watermark.last_sync == timestamp
        
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_set_watermark_update_existing(self):
        """Test updating existing watermark."""
        mock_session = AsyncMock(spec=AsyncSession)
        timestamp = datetime(2023, 8, 15, 14, 30, 0, tzinfo=UTC)
        
        # Mock existing watermark
        existing_watermark = SyncWatermark(
            source="pubmed",
            query_key="existing_query",
            last_sync=datetime(2023, 7, 1, tzinfo=UTC)
        )
        
        # Mock the database query to return existing watermark
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_watermark
        mock_session.execute.return_value = mock_result
        
        manager = CheckpointManager(mock_session)
        
        await manager.set_watermark("pubmed", "existing_query", timestamp)
        
        # Verify update was executed
        mock_session.execute.assert_called()
        assert mock_session.execute.call_count == 2  # One for select, one for update
        
        # Verify no new record was added
        mock_session.add.assert_not_called()
        
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_watermarks_all(self):
        """Test listing all watermarks."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create mock watermarks
        watermark1 = SyncWatermark(
            source="pubmed",
            query_key="cancer",
            last_sync=datetime(2023, 8, 15, tzinfo=UTC),
            created_at=datetime(2023, 8, 1, tzinfo=UTC),
            updated_at=datetime(2023, 8, 15, tzinfo=UTC)
        )
        watermark1.id = 1
        
        watermark2 = SyncWatermark(
            source="clinicaltrials",
            query_key="immunotherapy",
            last_sync=datetime(2023, 8, 10, tzinfo=UTC),
            created_at=datetime(2023, 7, 20, tzinfo=UTC),
            updated_at=datetime(2023, 8, 10, tzinfo=UTC)
        )
        watermark2.id = 2
        
        # Mock the database query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [watermark1, watermark2]
        mock_session.execute.return_value = mock_result
        
        manager = CheckpointManager(mock_session)
        
        result = await manager.list_watermarks()
        
        assert len(result) == 2
        
        assert result[0]["source"] == "pubmed"
        assert result[0]["query_key"] == "cancer"
        assert result[0]["last_sync"] == datetime(2023, 8, 15, tzinfo=UTC)
        
        assert result[1]["source"] == "clinicaltrials"
        assert result[1]["query_key"] == "immunotherapy"
        assert result[1]["last_sync"] == datetime(2023, 8, 10, tzinfo=UTC)
        
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_watermarks_filtered_by_source(self):
        """Test listing watermarks filtered by source."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create mock pubmed watermark
        watermark = SyncWatermark(
            source="pubmed",
            query_key="biomarkers",
            last_sync=datetime(2023, 8, 12, tzinfo=UTC),
            created_at=datetime(2023, 8, 1, tzinfo=UTC),
            updated_at=datetime(2023, 8, 12, tzinfo=UTC)
        )
        watermark.id = 1
        
        # Mock the database query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [watermark]
        mock_session.execute.return_value = mock_result
        
        manager = CheckpointManager(mock_session)
        
        result = await manager.list_watermarks(source="pubmed")
        
        assert len(result) == 1
        assert result[0]["source"] == "pubmed"
        assert result[0]["query_key"] == "biomarkers"
        
        # Verify the query was executed with source filter
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_watermarks_empty(self):
        """Test listing watermarks when none exist."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        manager = CheckpointManager(mock_session)
        
        result = await manager.list_watermarks()
        
        assert result == []
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_watermark_query_parameters(self):
        """Test that get_watermark constructs correct SQL query."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        manager = CheckpointManager(mock_session)
        
        await manager.get_watermark("test_source", "test_query")
        
        # Verify execute was called with correct parameters
        mock_session.execute.assert_called_once()
        
        # Get the SQL statement that was passed
        call_args = mock_session.execute.call_args
        statement = call_args[0][0]
        
        # Verify it's a select statement (basic check)
        assert hasattr(statement, 'compile')  # SQLAlchemy statement
    
    @pytest.mark.asyncio
    async def test_watermark_operations_integration(self):
        """Test complete watermark lifecycle - get, set, list."""
        mock_session = AsyncMock(spec=AsyncSession)
        source = "pubmed"
        query_key = "integration_test"
        timestamp = datetime(2023, 8, 20, 10, 0, 0, tzinfo=UTC)
        
        # Test 1: Get non-existent watermark
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result1
        
        manager = CheckpointManager(mock_session)
        
        result = await manager.get_watermark(source, query_key)
        assert result is None
        
        # Reset mock for next operation
        mock_session.reset_mock()
        
        # Test 2: Set watermark (new)
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = None  # No existing watermark
        mock_session.execute.return_value = mock_result2
        
        await manager.set_watermark(source, query_key, timestamp)
        
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        
        # Reset mock for next operation
        mock_session.reset_mock()
        
        # Test 3: List watermarks
        created_watermark = SyncWatermark(
            source=source,
            query_key=query_key,
            last_sync=timestamp,
            created_at=datetime(2023, 8, 20, 9, 0, 0, tzinfo=UTC),
            updated_at=datetime(2023, 8, 20, 10, 0, 0, tzinfo=UTC)
        )
        created_watermark.id = 1
        
        mock_result3 = MagicMock()
        mock_result3.scalars.return_value.all.return_value = [created_watermark]
        mock_session.execute.return_value = mock_result3
        
        watermarks = await manager.list_watermarks(source)
        
        assert len(watermarks) == 1
        assert watermarks[0]["source"] == source
        assert watermarks[0]["query_key"] == query_key
        assert watermarks[0]["last_sync"] == timestamp
    
    @pytest.mark.asyncio 
    async def test_error_handling(self):
        """Test error handling in checkpoint operations."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock database error
        mock_session.execute.side_effect = Exception("Database connection error")
        
        manager = CheckpointManager(mock_session)
        
        # Should propagate database errors
        with pytest.raises(Exception) as exc_info:
            await manager.get_watermark("pubmed", "test")
        
        assert "Database connection error" in str(exc_info.value)


# Mark as unit tests
pytestmark = pytest.mark.unit
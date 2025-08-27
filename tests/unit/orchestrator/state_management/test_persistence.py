"""Test state persistence functionality."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state_management.persistence import (
    BioMCPCheckpointSaver,
    OrchestrationCheckpoint,
    StateManager,
)


class TestOrchestrationCheckpoint:
    """Test OrchestrationCheckpoint dataclass."""

    def test_checkpoint_creation(self):
        """Test creating an OrchestrationCheckpoint."""
        checkpoint = OrchestrationCheckpoint(
            checkpoint_id="test_123",
            query="test query",
            frame={"intent": "search"},
            state={"query": "test"},
            created_at=datetime.now(UTC),
            execution_path=["frame", "router"],
        )

        assert checkpoint.checkpoint_id == "test_123"
        assert checkpoint.query == "test query"
        assert checkpoint.frame["intent"] == "search"
        assert checkpoint.error_count == 0
        assert checkpoint.retry_count == 0
        assert not checkpoint.partial_results
        assert checkpoint.execution_path == ["frame", "router"]


class TestBioMCPCheckpointSaver:
    """Test BioMCPCheckpointSaver implementation."""

    @pytest.mark.asyncio
    async def test_init_with_memory_db(self):
        """Test initialization with in-memory database."""
        config = OrchestratorConfig()
        saver = BioMCPCheckpointSaver(config, ":memory:")

        assert saver.db_path == ":memory:"
        assert saver.config == config
        assert saver.conn is not None

        # Check that bio-mcp tables are created
        cursor = saver.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orchestration_checkpoints'"
        )
        assert cursor.fetchone() is not None

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='query_metrics'"
        )
        assert cursor.fetchone() is not None

    @pytest.mark.asyncio
    async def test_init_with_file_db(self):
        """Test initialization with file database."""
        config = OrchestratorConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            saver = BioMCPCheckpointSaver(config, str(db_path))

            assert saver.db_path == str(db_path)
            assert db_path.exists()

    @pytest.mark.asyncio
    async def test_save_orchestration_checkpoint(self):
        """Test saving bio-mcp checkpoint data."""
        config = OrchestratorConfig()
        saver = BioMCPCheckpointSaver(config, ":memory:")

        checkpoint_data = OrchestrationCheckpoint(
            checkpoint_id="test_checkpoint_123",
            query="diabetes research",
            frame={"entities": {"topic": "diabetes"}, "intent": "search"},
            state={"query": "diabetes research", "node_path": ["frame", "router"]},
            created_at=datetime.now(UTC),
            execution_path=["frame", "router"],
            error_count=0,
            retry_count=0,
        )

        # This should save the bio-mcp specific data
        checkpoint_id = await saver.asave_checkpoint(
            checkpoint=None,  # Base checkpoint handled by LangGraph
            metadata=None,
            bio_mcp_data=checkpoint_data,
        )

        # Should return the checkpoint ID
        assert checkpoint_id == "test_checkpoint_123"

        # Verify data was saved in database
        cursor = saver.conn.cursor()
        cursor.execute(
            "SELECT * FROM orchestration_checkpoints WHERE checkpoint_id = ?",
            (checkpoint_data.checkpoint_id,),
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "test_checkpoint_123"  # checkpoint_id
        assert row[1] == "diabetes research"  # query

    @pytest.mark.asyncio
    async def test_get_orchestration_checkpoint(self):
        """Test retrieving bio-mcp checkpoint data."""
        config = OrchestratorConfig()
        saver = BioMCPCheckpointSaver(config, ":memory:")

        # First save a checkpoint
        checkpoint_data = OrchestrationCheckpoint(
            checkpoint_id="retrieve_test_123",
            query="cancer trials",
            frame={"entities": {"indication": "cancer"}},
            state={"results": []},
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            error_count=1,
            retry_count=2,
            partial_results=True,
            execution_path=["frame", "enhanced_pubmed", "enhanced_trials"],
        )

        await saver.asave_checkpoint(None, None, checkpoint_data)

        # Now retrieve it
        retrieved = await saver.aget_checkpoint("retrieve_test_123")

        assert retrieved is not None
        assert retrieved.checkpoint_id == "retrieve_test_123"
        assert retrieved.query == "cancer trials"
        assert retrieved.frame["entities"]["indication"] == "cancer"
        assert retrieved.error_count == 1
        assert retrieved.retry_count == 2
        assert retrieved.partial_results is True
        assert retrieved.execution_path == [
            "frame",
            "enhanced_pubmed",
            "enhanced_trials",
        ]

    @pytest.mark.asyncio
    async def test_get_nonexistent_checkpoint(self):
        """Test retrieving non-existent checkpoint returns None."""
        config = OrchestratorConfig()
        saver = BioMCPCheckpointSaver(config, ":memory:")

        result = await saver.aget_checkpoint("nonexistent_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_query_metrics(self):
        """Test saving query performance metrics."""
        config = OrchestratorConfig()
        saver = BioMCPCheckpointSaver(config, ":memory:")

        metrics = {
            "query_hash": hash("test query"),
            "intent": "search",
            "total_latency_ms": 2500.0,
            "tool_latencies": {"pubmed_search": 1200, "trials_search": 1300},
            "cache_hit_rate": 0.75,
            "result_count": 25,
            "success": True,
        }

        await saver.save_query_metrics("test_checkpoint", metrics)

        # Verify metrics were saved
        cursor = saver.conn.cursor()
        cursor.execute(
            "SELECT * FROM query_metrics WHERE checkpoint_id = ?", ("test_checkpoint",)
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[1] == "test_checkpoint"  # checkpoint_id
        assert row[3] == "search"  # intent
        assert row[4] == 2500.0  # total_latency_ms
        assert row[6] == 0.75  # cache_hit_rate
        assert row[7] == 25  # result_count
        assert row[8] == 1  # success (True as 1)

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints(self):
        """Test cleaning up old checkpoints."""
        config = OrchestratorConfig()
        saver = BioMCPCheckpointSaver(config, ":memory:")

        # Create old and recent checkpoints
        old_checkpoint = OrchestrationCheckpoint(
            checkpoint_id="old_checkpoint",
            query="old query",
            frame={},
            state={},
            created_at=datetime(2020, 1, 1, tzinfo=UTC),  # Very old
        )

        recent_checkpoint = OrchestrationCheckpoint(
            checkpoint_id="recent_checkpoint",
            query="recent query",
            frame={},
            state={},
            created_at=datetime.now(UTC),
        )

        await saver.asave_checkpoint(None, None, old_checkpoint)
        await saver.asave_checkpoint(None, None, recent_checkpoint)

        # Cleanup old checkpoints (older than 1 day)
        await saver.cleanup_old_checkpoints(days=1)

        # Old checkpoint should be gone
        old_retrieved = await saver.aget_checkpoint("old_checkpoint")
        assert old_retrieved is None

        # Recent checkpoint should still exist
        recent_retrieved = await saver.aget_checkpoint("recent_checkpoint")
        assert recent_retrieved is not None


class TestStateManager:
    """Test StateManager implementation."""

    @pytest.mark.asyncio
    async def test_init_state_manager(self):
        """Test StateManager initialization."""
        config = OrchestratorConfig()
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")

        manager = StateManager(config, checkpointer)

        assert manager.config == config
        assert manager.checkpointer == checkpointer

    @pytest.mark.asyncio
    async def test_create_checkpoint(self):
        """Test creating a checkpoint from state."""
        config = OrchestratorConfig()
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        manager = StateManager(config, checkpointer)

        state = {
            "query": "test checkpoint creation",
            "frame": {"intent": "search", "entities": {"topic": "test"}},
            "node_path": ["frame_parser", "router"],
            "errors": [],
            "results": {"count": 5},
        }

        checkpoint = await manager.create_checkpoint(state)

        assert checkpoint.checkpoint_id.startswith("ckpt_")
        assert checkpoint.query == "test checkpoint creation"
        assert checkpoint.frame["intent"] == "search"
        assert checkpoint.execution_path == ["frame_parser", "router"]

        # Verify checkpoint was saved
        retrieved = await checkpointer.aget_checkpoint(checkpoint.checkpoint_id)
        assert retrieved is not None
        assert retrieved.query == "test checkpoint creation"

    @pytest.mark.asyncio
    async def test_update_checkpoint(self):
        """Test updating an existing checkpoint."""
        config = OrchestratorConfig()
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        manager = StateManager(config, checkpointer)

        # Create initial checkpoint
        initial_state = {
            "query": "update test",
            "frame": {},
            "node_path": ["frame"],
            "errors": [],
        }

        checkpoint = await manager.create_checkpoint(initial_state)

        # Update with new state
        updated_state = {
            "query": "update test",
            "frame": {},
            "node_path": ["frame", "router", "pubmed_search"],
            "errors": [{"error": "minor issue"}],
            "pubmed_results": {"count": 10},
        }

        await manager.update_checkpoint(checkpoint.checkpoint_id, updated_state)

        # Verify update
        retrieved = await checkpointer.aget_checkpoint(checkpoint.checkpoint_id)
        assert retrieved is not None
        assert retrieved.execution_path == ["frame", "router", "pubmed_search"]
        assert retrieved.error_count == 1
        assert retrieved.state["pubmed_results"]["count"] == 10

    @pytest.mark.asyncio
    async def test_finalize_checkpoint(self):
        """Test finalizing a checkpoint with metrics."""
        config = OrchestratorConfig()
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        manager = StateManager(config, checkpointer)

        # Create checkpoint
        state = {
            "query": "finalization test",
            "frame": {"intent": "search"},
            "latencies": {"pubmed_search": 1000, "trials_search": 1500},
            "cache_hits": {"pubmed_search": True, "trials_search": False},
            "pubmed_results": {"results": [1, 2, 3]},
            "errors": [],
        }

        checkpoint = await manager.create_checkpoint(state)

        # Finalize checkpoint
        await manager.finalize_checkpoint(checkpoint.checkpoint_id, state)

        # Verify completion
        retrieved = await checkpointer.aget_checkpoint(checkpoint.checkpoint_id)
        assert retrieved is not None
        assert retrieved.completed_at is not None
        assert retrieved.partial_results is False  # No errors

        # Verify metrics were saved
        cursor = checkpointer.conn.cursor()
        cursor.execute(
            "SELECT * FROM query_metrics WHERE checkpoint_id = ?",
            (checkpoint.checkpoint_id,),
        )
        metrics_row = cursor.fetchone()
        assert metrics_row is not None
        assert metrics_row[3] == "search"  # intent
        assert metrics_row[4] == 2500.0  # total latency (1000 + 1500)

    @pytest.mark.asyncio
    async def test_checkpoint_id_generation(self):
        """Test checkpoint ID generation is unique."""
        config = OrchestratorConfig()
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        manager = StateManager(config, checkpointer)

        state1 = {"query": "first query", "frame": {}, "node_path": []}
        state2 = {"query": "second query", "frame": {}, "node_path": []}

        checkpoint1 = await manager.create_checkpoint(state1)
        checkpoint2 = await manager.create_checkpoint(state2)

        assert checkpoint1.checkpoint_id != checkpoint2.checkpoint_id
        assert checkpoint1.checkpoint_id.startswith("ckpt_")
        assert checkpoint2.checkpoint_id.startswith("ckpt_")

    @pytest.mark.asyncio
    async def test_extract_metrics(self):
        """Test metrics extraction from state."""
        config = OrchestratorConfig()
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        manager = StateManager(config, checkpointer)

        state = {
            "query": "metrics test",
            "frame": {"intent": "research"},
            "latencies": {"node1": 100, "node2": 200, "node3": 300},
            "cache_hits": {"node1": True, "node2": False, "node3": True},
            "pubmed_results": {"results": [1, 2, 3, 4, 5]},
            "ctgov_results": {"results": [1, 2]},
            "errors": [],
        }

        metrics = manager._extract_metrics(state)

        assert metrics["intent"] == "research"
        assert metrics["total_latency_ms"] == 600  # 100 + 200 + 300
        assert metrics["cache_hit_rate"] == 2 / 3  # 2 hits out of 3
        assert metrics["result_count"] == 7  # 5 PubMed + 2 trials
        assert metrics["success"] is True  # No errors

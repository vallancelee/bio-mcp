"""State persistence functionality for bio-mcp orchestrator."""
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver

from bio_mcp.orchestrator.config import OrchestratorConfig


@dataclass
class OrchestrationCheckpoint:
    """Bio-MCP orchestration checkpoint data."""
    checkpoint_id: str
    query: str
    frame: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict) 
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None
    execution_path: list[str] = field(default_factory=list)
    error_count: int = 0
    retry_count: int = 0
    partial_results: bool = False


class BioMCPCheckpointSaver(BaseCheckpointSaver):
    """Bio-MCP specific checkpoint saver with SQLite persistence."""
    
    def __init__(self, config: OrchestratorConfig, db_path: str = ":memory:"):
        """Initialize the checkpoint saver.
        
        Args:
            config: Orchestrator configuration
            db_path: SQLite database path (defaults to in-memory)
        """
        super().__init__()
        self.config = config
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._initialize_tables()
    
    def _initialize_tables(self) -> None:
        """Initialize bio-mcp specific database tables."""
        cursor = self.conn.cursor()
        
        # Orchestration checkpoints table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestration_checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                frame_data TEXT,
                state_data TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                execution_path TEXT,
                error_count INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                partial_results INTEGER DEFAULT 0
            )
        """)
        
        # Query performance metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checkpoint_id TEXT NOT NULL,
                query_hash INTEGER,
                intent TEXT,
                total_latency_ms REAL,
                tool_latencies TEXT,
                cache_hit_rate REAL,
                result_count INTEGER,
                success INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (checkpoint_id) REFERENCES orchestration_checkpoints (checkpoint_id)
            )
        """)
        
        self.conn.commit()
    
    async def asave_checkpoint(
        self,
        checkpoint: Any,  # Base LangGraph checkpoint (can be None)
        metadata: Any,    # Base metadata (can be None)  
        bio_mcp_data: Optional[OrchestrationCheckpoint] = None
    ) -> str:
        """Save bio-mcp checkpoint data.
        
        Args:
            checkpoint: Base LangGraph checkpoint (ignored for now)
            metadata: Base metadata (ignored for now)
            bio_mcp_data: Bio-MCP specific checkpoint data
            
        Returns:
            Checkpoint ID
        """
        if not bio_mcp_data:
            raise ValueError("bio_mcp_data is required")
            
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO orchestration_checkpoints 
            (checkpoint_id, query, frame_data, state_data, created_at, completed_at,
             execution_path, error_count, retry_count, partial_results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bio_mcp_data.checkpoint_id,
            bio_mcp_data.query,
            json.dumps(bio_mcp_data.frame),
            json.dumps(bio_mcp_data.state),
            bio_mcp_data.created_at.isoformat(),
            bio_mcp_data.completed_at.isoformat() if bio_mcp_data.completed_at else None,
            json.dumps(bio_mcp_data.execution_path),
            bio_mcp_data.error_count,
            bio_mcp_data.retry_count,
            1 if bio_mcp_data.partial_results else 0
        ))
        
        self.conn.commit()
        return bio_mcp_data.checkpoint_id
    
    async def aget_checkpoint(self, checkpoint_id: str) -> Optional[OrchestrationCheckpoint]:
        """Retrieve bio-mcp checkpoint data.
        
        Args:
            checkpoint_id: Checkpoint ID
            
        Returns:
            OrchestrationCheckpoint or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT checkpoint_id, query, frame_data, state_data, created_at, completed_at,
                   execution_path, error_count, retry_count, partial_results
            FROM orchestration_checkpoints 
            WHERE checkpoint_id = ?
        """, (checkpoint_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return OrchestrationCheckpoint(
            checkpoint_id=row[0],
            query=row[1],
            frame=json.loads(row[2]) if row[2] else {},
            state=json.loads(row[3]) if row[3] else {},
            created_at=datetime.fromisoformat(row[4]),
            completed_at=datetime.fromisoformat(row[5]) if row[5] else None,
            execution_path=json.loads(row[6]) if row[6] else [],
            error_count=row[7],
            retry_count=row[8],
            partial_results=bool(row[9])
        )
    
    async def save_query_metrics(self, checkpoint_id: str, metrics: dict[str, Any]) -> None:
        """Save query performance metrics.
        
        Args:
            checkpoint_id: Associated checkpoint ID
            metrics: Performance metrics dictionary
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO query_metrics 
            (checkpoint_id, query_hash, intent, total_latency_ms, tool_latencies,
             cache_hit_rate, result_count, success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            checkpoint_id,
            metrics.get("query_hash"),
            metrics.get("intent"),
            metrics.get("total_latency_ms"),
            json.dumps(metrics.get("tool_latencies", {})),
            metrics.get("cache_hit_rate"),
            metrics.get("result_count"),
            1 if metrics.get("success") else 0
        ))
        
        self.conn.commit()
    
    async def cleanup_old_checkpoints(self, days: int = 7) -> None:
        """Clean up old checkpoints.
        
        Args:
            days: Number of days to keep checkpoints
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)
        cursor = self.conn.cursor()
        
        # Clean up metrics first (foreign key constraint)
        cursor.execute("""
            DELETE FROM query_metrics 
            WHERE checkpoint_id IN (
                SELECT checkpoint_id FROM orchestration_checkpoints 
                WHERE created_at < ?
            )
        """, (cutoff_date.isoformat(),))
        
        # Clean up checkpoints
        cursor.execute("""
            DELETE FROM orchestration_checkpoints 
            WHERE created_at < ?
        """, (cutoff_date.isoformat(),))
        
        self.conn.commit()


class StateManager:
    """Manages orchestrator state and checkpoints."""
    
    def __init__(self, config: OrchestratorConfig, checkpointer: BioMCPCheckpointSaver):
        """Initialize state manager.
        
        Args:
            config: Orchestrator configuration
            checkpointer: Checkpoint saver instance
        """
        self.config = config
        self.checkpointer = checkpointer
    
    async def create_checkpoint(self, state: dict[str, Any]) -> OrchestrationCheckpoint:
        """Create a new checkpoint from current state.
        
        Args:
            state: Current orchestrator state
            
        Returns:
            Created checkpoint
        """
        checkpoint_id = f"ckpt_{uuid.uuid4().hex[:12]}"
        
        checkpoint = OrchestrationCheckpoint(
            checkpoint_id=checkpoint_id,
            query=state.get("query", ""),
            frame=state.get("frame", {}),
            state=dict(state),
            created_at=datetime.now(UTC),
            execution_path=state.get("node_path", []),
            error_count=len(state.get("errors", [])),
            retry_count=0,
            partial_results=len(state.get("errors", [])) > 0
        )
        
        await self.checkpointer.asave_checkpoint(None, None, checkpoint)
        return checkpoint
    
    async def update_checkpoint(self, checkpoint_id: str, state: dict[str, Any]) -> None:
        """Update an existing checkpoint with new state.
        
        Args:
            checkpoint_id: Checkpoint ID to update
            state: Updated state
        """
        # Retrieve existing checkpoint
        existing = await self.checkpointer.aget_checkpoint(checkpoint_id)
        if not existing:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")
        
        # Update with new state
        updated_checkpoint = OrchestrationCheckpoint(
            checkpoint_id=existing.checkpoint_id,
            query=existing.query,
            frame=existing.frame,
            state=dict(state),
            created_at=existing.created_at,
            completed_at=existing.completed_at,
            execution_path=state.get("node_path", existing.execution_path),
            error_count=len(state.get("errors", [])),
            retry_count=existing.retry_count,
            partial_results=len(state.get("errors", [])) > 0
        )
        
        await self.checkpointer.asave_checkpoint(None, None, updated_checkpoint)
    
    async def finalize_checkpoint(self, checkpoint_id: str, final_state: dict[str, Any]) -> None:
        """Finalize a checkpoint with completion data and metrics.
        
        Args:
            checkpoint_id: Checkpoint ID to finalize
            final_state: Final orchestrator state
        """
        # Update checkpoint as completed
        existing = await self.checkpointer.aget_checkpoint(checkpoint_id)
        if not existing:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")
        
        finalized_checkpoint = OrchestrationCheckpoint(
            checkpoint_id=existing.checkpoint_id,
            query=existing.query,
            frame=existing.frame,
            state=dict(final_state),
            created_at=existing.created_at,
            completed_at=datetime.now(UTC),
            execution_path=final_state.get("node_path", existing.execution_path),
            error_count=len(final_state.get("errors", [])),
            retry_count=existing.retry_count,
            partial_results=len(final_state.get("errors", [])) > 0
        )
        
        await self.checkpointer.asave_checkpoint(None, None, finalized_checkpoint)
        
        # Extract and save metrics
        metrics = self._extract_metrics(final_state)
        await self.checkpointer.save_query_metrics(checkpoint_id, metrics)
    
    def _extract_metrics(self, state: dict[str, Any]) -> dict[str, Any]:
        """Extract performance metrics from state.
        
        Args:
            state: Orchestrator state
            
        Returns:
            Metrics dictionary
        """
        frame = state.get("frame", {})
        latencies = state.get("latencies", {})
        cache_hits = state.get("cache_hits", {})
        errors = state.get("errors", [])
        
        # Calculate totals
        total_latency = sum(latencies.values())
        
        # Calculate cache hit rate
        if cache_hits:
            hit_count = sum(1 for hit in cache_hits.values() if hit)
            cache_hit_rate = hit_count / len(cache_hits)
        else:
            cache_hit_rate = 0.0
        
        # Count results
        result_count = 0
        if "pubmed_results" in state and state["pubmed_results"] is not None:
            pubmed_results = state["pubmed_results"].get("results", [])
            result_count += len(pubmed_results)
        if "ctgov_results" in state and state["ctgov_results"] is not None:
            ctgov_results = state["ctgov_results"].get("results", [])
            result_count += len(ctgov_results)
        
        return {
            "query_hash": hash(state.get("query", "")),
            "intent": frame.get("intent", "unknown"),
            "total_latency_ms": total_latency,
            "tool_latencies": latencies,
            "cache_hit_rate": cache_hit_rate,
            "result_count": result_count,
            "success": len(errors) == 0
        }
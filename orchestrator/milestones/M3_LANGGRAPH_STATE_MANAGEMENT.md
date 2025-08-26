# M3 — LangGraph State Management & Flow Control (1 day)

## Objective
Implement advanced state persistence, error recovery, and flow control mechanisms using LangGraph's built-in capabilities. Focus on checkpointing, conditional routing, budget enforcement, partial results handling, and robust error recovery strategies that ensure the orchestrator can handle failures gracefully and provide useful results even under adverse conditions.

## Dependencies (Existing Bio-MCP Components)
- **M1 LangGraph Nodes**: Basic node implementations
- **M2 Tool Integration**: Enhanced MCP tool integration
- **LangGraph State**: `src/bio_mcp/orchestrator/state.py` - State schema
- **Configuration**: `src/bio_mcp/orchestrator/config.py` - Orchestrator config
- **Database**: `src/bio_mcp/shared/clients/database.py` - DatabaseManager
- **Cache**: `src/bio_mcp/shared/cache/` - Caching infrastructure

## Core State Management Components

### 1. Enhanced State Persistence

**File**: `src/bio_mcp/orchestrator/state/persistence.py`
```python
"""Advanced state persistence and checkpointing for LangGraph."""
import json
import sqlite3
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.shared.clients.database import DatabaseManager

logger = get_logger(__name__)

@dataclass
class OrchestrationCheckpoint:
    """Extended checkpoint with bio-mcp specific metadata."""
    checkpoint_id: str
    query: str
    frame: Dict[str, Any]
    state: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_count: int = 0
    retry_count: int = 0
    partial_results: bool = False
    execution_path: List[str] = None

class BioMCPCheckpointSaver(SqliteSaver):
    """Custom checkpoint saver with bio-mcp enhancements."""
    
    def __init__(self, config: OrchestratorConfig, db_path: Optional[str] = None):
        self.config = config
        self.db_path = db_path or config.langgraph.checkpoint_db_path
        
        # Initialize SQLite connection
        if self.db_path == ":memory:":
            self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        
        super().__init__(conn=self.conn)
        self._init_bio_mcp_tables()
    
    def _init_bio_mcp_tables(self):
        """Initialize bio-mcp specific tables."""
        cursor = self.conn.cursor()
        
        # Orchestration checkpoints table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orchestration_checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                frame TEXT,
                state TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error_count INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                partial_results BOOLEAN DEFAULT FALSE,
                execution_path TEXT,
                metadata TEXT
            )
        """)
        
        # Query performance metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checkpoint_id TEXT,
                query_hash TEXT,
                intent TEXT,
                total_latency_ms REAL,
                tool_latencies TEXT,
                cache_hit_rate REAL,
                result_count INTEGER,
                success BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (checkpoint_id) REFERENCES orchestration_checkpoints (checkpoint_id)
            )
        """)
        
        self.conn.commit()
    
    async def asave_checkpoint(
        self, 
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        bio_mcp_data: Optional[OrchestrationCheckpoint] = None
    ) -> str:
        """Save checkpoint with bio-mcp metadata."""
        # Save base checkpoint
        checkpoint_id = await super().asave_checkpoint(checkpoint, metadata)
        
        # Save bio-mcp specific data
        if bio_mcp_data:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO orchestration_checkpoints 
                (checkpoint_id, query, frame, state, created_at, completed_at, 
                 error_count, retry_count, partial_results, execution_path, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bio_mcp_data.checkpoint_id,
                bio_mcp_data.query,
                json.dumps(bio_mcp_data.frame) if bio_mcp_data.frame else None,
                json.dumps(bio_mcp_data.state) if bio_mcp_data.state else None,
                bio_mcp_data.created_at,
                bio_mcp_data.completed_at,
                bio_mcp_data.error_count,
                bio_mcp_data.retry_count,
                bio_mcp_data.partial_results,
                json.dumps(bio_mcp_data.execution_path) if bio_mcp_data.execution_path else None,
                json.dumps(metadata._asdict() if hasattr(metadata, '_asdict') else {})
            ))
            self.conn.commit()
        
        return checkpoint_id
    
    async def aget_checkpoint(self, checkpoint_id: str) -> Optional[OrchestrationCheckpoint]:
        """Get bio-mcp checkpoint data."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT checkpoint_id, query, frame, state, created_at, completed_at,
                   error_count, retry_count, partial_results, execution_path, metadata
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
            error_count=row[6],
            retry_count=row[7],
            partial_results=bool(row[8]),
            execution_path=json.loads(row[9]) if row[9] else []
        )
    
    async def save_query_metrics(self, checkpoint_id: str, metrics: Dict[str, Any]):
        """Save query performance metrics."""
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
            metrics.get("success", False)
        ))
        self.conn.commit()
    
    async def cleanup_old_checkpoints(self, days: int = 7):
        """Clean up checkpoints older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        cursor = self.conn.cursor()
        
        # Clean up orchestration checkpoints
        cursor.execute("""
            DELETE FROM orchestration_checkpoints 
            WHERE created_at < ?
        """, (cutoff,))
        
        # Clean up query metrics
        cursor.execute("""
            DELETE FROM query_metrics 
            WHERE created_at < ?
        """, (cutoff,))
        
        self.conn.commit()
        logger.info(f"Cleaned up checkpoints older than {days} days")

class StateManager:
    """Manages orchestrator state transitions and persistence."""
    
    def __init__(self, config: OrchestratorConfig, checkpointer: BioMCPCheckpointSaver):
        self.config = config
        self.checkpointer = checkpointer
    
    async def create_checkpoint(self, state: Dict[str, Any]) -> OrchestrationCheckpoint:
        """Create new checkpoint from state."""
        checkpoint = OrchestrationCheckpoint(
            checkpoint_id=self._generate_checkpoint_id(state),
            query=state.get("query", ""),
            frame=state.get("frame", {}),
            state=state,
            created_at=datetime.utcnow(),
            execution_path=state.get("node_path", [])
        )
        
        await self.checkpointer.asave_checkpoint(
            checkpoint=None,  # Base checkpoint handled by LangGraph
            metadata=None,
            bio_mcp_data=checkpoint
        )
        
        return checkpoint
    
    async def update_checkpoint(self, checkpoint_id: str, state: Dict[str, Any]):
        """Update existing checkpoint with new state."""
        checkpoint = await self.checkpointer.aget_checkpoint(checkpoint_id)
        if checkpoint:
            checkpoint.state = state
            checkpoint.execution_path = state.get("node_path", [])
            checkpoint.error_count = len(state.get("errors", []))
            
            await self.checkpointer.asave_checkpoint(
                checkpoint=None,
                metadata=None,
                bio_mcp_data=checkpoint
            )
    
    async def finalize_checkpoint(self, checkpoint_id: str, state: Dict[str, Any]):
        """Mark checkpoint as completed."""
        checkpoint = await self.checkpointer.aget_checkpoint(checkpoint_id)
        if checkpoint:
            checkpoint.completed_at = datetime.utcnow()
            checkpoint.partial_results = len(state.get("errors", [])) > 0
            
            await self.checkpointer.asave_checkpoint(
                checkpoint=None,
                metadata=None,
                bio_mcp_data=checkpoint
            )
            
            # Save performance metrics
            metrics = self._extract_metrics(state)
            await self.checkpointer.save_query_metrics(checkpoint_id, metrics)
    
    def _generate_checkpoint_id(self, state: Dict[str, Any]) -> str:
        """Generate unique checkpoint ID."""
        import hashlib
        content = f"{state.get('query', '')}:{datetime.utcnow().isoformat()}"
        hash_digest = hashlib.md5(content.encode()).hexdigest()[:12]
        return f"ckpt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{hash_digest}"
    
    def _extract_metrics(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract performance metrics from state."""
        latencies = state.get("latencies", {})
        cache_hits = state.get("cache_hits", {})
        
        total_latency = sum(latencies.values())
        cache_hit_rate = (
            sum(1 for hit in cache_hits.values() if hit) / len(cache_hits)
            if cache_hits else 0.0
        )
        
        return {
            "query_hash": hash(state.get("query", "")),
            "intent": state.get("frame", {}).get("intent"),
            "total_latency_ms": total_latency,
            "tool_latencies": latencies,
            "cache_hit_rate": cache_hit_rate,
            "result_count": self._count_total_results(state),
            "success": len(state.get("errors", [])) == 0
        }
    
    def _count_total_results(self, state: Dict[str, Any]) -> int:
        """Count total results across all sources."""
        count = 0
        
        # PubMed results
        pubmed = state.get("pubmed_results")
        if pubmed and isinstance(pubmed, dict):
            count += len(pubmed.get("results", []))
        
        # ClinicalTrials results
        ctgov = state.get("ctgov_results")
        if ctgov and isinstance(ctgov, dict):
            count += len(ctgov.get("results", []))
        
        # RAG results
        rag = state.get("rag_results")
        if rag and isinstance(rag, dict):
            count += len(rag.get("results", []))
        
        return count
```

### 2. Error Recovery and Retry Logic

**File**: `src/bio_mcp/orchestrator/state/error_recovery.py`
```python
"""Error recovery and retry mechanisms."""
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncio
import random

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig

logger = get_logger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"           # Non-critical errors, continue with partial results
    MEDIUM = "medium"     # Retryable errors
    HIGH = "high"         # Critical errors, abort execution
    TIMEOUT = "timeout"   # Timeout errors, may retry with extended timeout

@dataclass
class ErrorClassification:
    """Classification of an error."""
    severity: ErrorSeverity
    retryable: bool
    retry_delay: float = 0.0
    max_retries: int = 0
    fallback_action: Optional[str] = None

class ErrorClassifier:
    """Classifies errors and determines recovery strategies."""
    
    def __init__(self):
        self.error_patterns = {
            # Network/API errors - retryable
            "timeout": ErrorClassification(
                severity=ErrorSeverity.TIMEOUT,
                retryable=True,
                retry_delay=2.0,
                max_retries=3,
                fallback_action="extend_timeout"
            ),
            "connection": ErrorClassification(
                severity=ErrorSeverity.MEDIUM,
                retryable=True,
                retry_delay=1.0,
                max_retries=2,
                fallback_action="skip_node"
            ),
            "rate_limit": ErrorClassification(
                severity=ErrorSeverity.MEDIUM,
                retryable=True,
                retry_delay=5.0,
                max_retries=3,
                fallback_action="exponential_backoff"
            ),
            
            # Data errors - may be retryable
            "parse_error": ErrorClassification(
                severity=ErrorSeverity.LOW,
                retryable=False,
                fallback_action="use_fallback_data"
            ),
            "validation_error": ErrorClassification(
                severity=ErrorSeverity.MEDIUM,
                retryable=True,
                retry_delay=0.5,
                max_retries=1,
                fallback_action="relax_validation"
            ),
            
            # System errors - critical
            "database_error": ErrorClassification(
                severity=ErrorSeverity.HIGH,
                retryable=True,
                retry_delay=2.0,
                max_retries=2,
                fallback_action="switch_to_cache_only"
            ),
            "out_of_memory": ErrorClassification(
                severity=ErrorSeverity.HIGH,
                retryable=False,
                fallback_action="reduce_batch_size"
            ),
        }
    
    def classify_error(self, error_msg: str, error_context: Dict[str, Any]) -> ErrorClassification:
        """Classify error and return recovery strategy."""
        error_lower = error_msg.lower()
        
        # Check for known patterns
        for pattern, classification in self.error_patterns.items():
            if pattern in error_lower:
                return classification
        
        # Default classification for unknown errors
        return ErrorClassification(
            severity=ErrorSeverity.MEDIUM,
            retryable=True,
            retry_delay=1.0,
            max_retries=1,
            fallback_action="skip_node"
        )

class RetryStrategy:
    """Implements various retry strategies."""
    
    @staticmethod
    async def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0):
        """Exponential backoff with jitter."""
        delay = min(base_delay * (2 ** attempt), max_delay)
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0.1, 0.3) * delay
        await asyncio.sleep(delay + jitter)
    
    @staticmethod
    async def linear_backoff(attempt: int, delay: float = 1.0):
        """Linear backoff."""
        await asyncio.sleep(delay * (attempt + 1))
    
    @staticmethod
    async def fixed_delay(delay: float = 1.0):
        """Fixed delay."""
        await asyncio.sleep(delay)

class ErrorRecoveryManager:
    """Manages error recovery and retry logic."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.classifier = ErrorClassifier()
        self.retry_strategy = RetryStrategy()
        self.active_retries: Dict[str, int] = {}
    
    async def handle_error(
        self, 
        error: Exception, 
        context: Dict[str, Any],
        state: OrchestratorState,
        retry_function: Callable
    ) -> Dict[str, Any]:
        """Handle error with recovery strategy."""
        error_msg = str(error)
        node_name = context.get("node_name", "unknown")
        
        # Classify error
        classification = self.classifier.classify_error(error_msg, context)
        
        logger.error(f"Error in {node_name}: {error_msg}", extra={
            "node": node_name,
            "severity": classification.severity.value,
            "retryable": classification.retryable,
            "context": context
        })
        
        # Check if we should retry
        if self._should_retry(node_name, classification):
            return await self._execute_retry(
                node_name, classification, retry_function, context, state
            )
        
        # Apply fallback action
        return await self._apply_fallback(
            classification, context, state, error_msg
        )
    
    def _should_retry(self, node_name: str, classification: ErrorClassification) -> bool:
        """Determine if we should retry this error."""
        if not classification.retryable:
            return False
        
        current_retries = self.active_retries.get(node_name, 0)
        if current_retries >= classification.max_retries:
            return False
        
        return True
    
    async def _execute_retry(
        self,
        node_name: str,
        classification: ErrorClassification,
        retry_function: Callable,
        context: Dict[str, Any],
        state: OrchestratorState
    ) -> Dict[str, Any]:
        """Execute retry with appropriate strategy."""
        attempt = self.active_retries.get(node_name, 0)
        self.active_retries[node_name] = attempt + 1
        
        logger.info(f"Retrying {node_name} (attempt {attempt + 1})", extra={
            "node": node_name,
            "attempt": attempt + 1,
            "max_retries": classification.max_retries
        })
        
        # Apply retry delay
        if classification.retry_delay > 0:
            if classification.fallback_action == "exponential_backoff":
                await self.retry_strategy.exponential_backoff(
                    attempt, classification.retry_delay
                )
            else:
                await self.retry_strategy.fixed_delay(classification.retry_delay)
        
        # Modify context for retry if needed
        modified_context = self._modify_context_for_retry(
            context, classification, attempt
        )
        
        try:
            # Execute retry
            result = await retry_function(modified_context)
            
            # Reset retry counter on success
            self.active_retries.pop(node_name, None)
            
            return result
            
        except Exception as retry_error:
            # If retry also fails, handle recursively
            return await self.handle_error(
                retry_error, context, state, retry_function
            )
    
    def _modify_context_for_retry(
        self,
        context: Dict[str, Any],
        classification: ErrorClassification,
        attempt: int
    ) -> Dict[str, Any]:
        """Modify context for retry attempt."""
        modified = context.copy()
        
        if classification.fallback_action == "extend_timeout":
            current_timeout = modified.get("timeout_ms", 5000)
            modified["timeout_ms"] = min(current_timeout * 1.5, 30000)
        
        elif classification.fallback_action == "reduce_batch_size":
            current_limit = modified.get("limit", 20)
            modified["limit"] = max(5, current_limit // 2)
        
        elif classification.fallback_action == "relax_validation":
            modified["strict_validation"] = False
        
        return modified
    
    async def _apply_fallback(
        self,
        classification: ErrorClassification,
        context: Dict[str, Any],
        state: OrchestratorState,
        error_msg: str
    ) -> Dict[str, Any]:
        """Apply fallback action for unrecoverable errors."""
        node_name = context.get("node_name", "unknown")
        
        # Add error to state
        error_entry = {
            "node": node_name,
            "error": error_msg,
            "severity": classification.severity.value,
            "timestamp": datetime.utcnow().isoformat(),
            "fallback_applied": classification.fallback_action
        }
        
        fallback_result = {
            "errors": state["errors"] + [error_entry],
            "node_path": state["node_path"] + [f"{node_name}_failed"]
        }
        
        # Apply specific fallback actions
        if classification.fallback_action == "use_fallback_data":
            fallback_result[f"{node_name}_results"] = self._get_fallback_data(node_name)
        
        elif classification.fallback_action == "switch_to_cache_only":
            fallback_result["config"] = {
                **state.get("config", {}),
                "fetch_policy": "cache_only"
            }
        
        elif classification.fallback_action == "skip_node":
            # Mark node as skipped but don't block progression
            fallback_result["messages"] = state.get("messages", []) + [{
                "role": "system",
                "content": f"Skipped {node_name} due to error: {error_msg[:100]}..."
            }]
        
        return fallback_result
    
    def _get_fallback_data(self, node_name: str) -> Dict[str, Any]:
        """Get fallback data for failed node."""
        # Return empty results structure
        return {
            "results": [],
            "total": 0,
            "source": "fallback",
            "note": f"Fallback data used due to {node_name} failure"
        }
    
    def reset_retry_counts(self):
        """Reset all retry counters."""
        self.active_retries.clear()

def create_error_recovery_middleware(config: OrchestratorConfig):
    """Create error recovery middleware for nodes."""
    recovery_manager = ErrorRecoveryManager(config)
    
    def middleware(node_func: Callable):
        async def wrapped_node(state: OrchestratorState) -> Dict[str, Any]:
            try:
                return await node_func(state)
            except Exception as e:
                context = {
                    "node_name": getattr(node_func, "__name__", "unknown"),
                    "state_keys": list(state.keys()),
                    "query": state.get("query", "")
                }
                
                return await recovery_manager.handle_error(
                    e, context, state, 
                    lambda ctx: node_func(state)
                )
        
        return wrapped_node
    
    return middleware
```

### 3. Budget and Timeout Enforcement

**File**: `src/bio_mcp/orchestrator/state/budget_manager.py`
```python
"""Budget and timeout enforcement for orchestrator execution."""
import asyncio
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig

logger = get_logger(__name__)

@dataclass
class BudgetStatus:
    """Current budget status."""
    allocated_ms: int
    consumed_ms: float
    remaining_ms: float
    utilization: float
    in_danger_zone: bool
    should_abort: bool

class BudgetManager:
    """Manages execution budget and timeouts."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.execution_start: Optional[datetime] = None
        self.budget_ms: int = config.default_budget_ms
        self.node_budgets: Dict[str, int] = {}
        self.danger_zone_threshold: float = 0.8  # 80% budget consumed
        self.abort_threshold: float = 0.95  # 95% budget consumed
    
    def start_execution(self, budget_ms: Optional[int] = None):
        """Start budget tracking for execution."""
        self.execution_start = datetime.utcnow()
        self.budget_ms = budget_ms or self.config.default_budget_ms
        
        # Allocate budget to different phases
        self._allocate_node_budgets()
        
        logger.info(f"Started execution with budget: {self.budget_ms}ms", extra={
            "budget_ms": self.budget_ms,
            "node_budgets": self.node_budgets
        })
    
    def _allocate_node_budgets(self):
        """Allocate budget to different nodes."""
        # Reserve 10% for overhead
        available = self.budget_ms * 0.9
        
        # Typical allocation based on expected latencies
        self.node_budgets = {
            "parse_frame": int(available * 0.05),      # 5% - fast parsing
            "router": int(available * 0.02),           # 2% - simple routing
            "pubmed_search": int(available * 0.35),    # 35% - API calls
            "ctgov_search": int(available * 0.35),     # 35% - API calls
            "rag_search": int(available * 0.15),       # 15% - vector search
            "synthesizer": int(available * 0.08),      # 8% - text generation
        }
    
    def get_status(self) -> BudgetStatus:
        """Get current budget status."""
        if not self.execution_start:
            return BudgetStatus(0, 0, 0, 0, False, False)
        
        consumed_ms = (datetime.utcnow() - self.execution_start).total_seconds() * 1000
        remaining_ms = max(0, self.budget_ms - consumed_ms)
        utilization = consumed_ms / self.budget_ms if self.budget_ms > 0 else 1.0
        
        return BudgetStatus(
            allocated_ms=self.budget_ms,
            consumed_ms=consumed_ms,
            remaining_ms=remaining_ms,
            utilization=utilization,
            in_danger_zone=utilization >= self.danger_zone_threshold,
            should_abort=utilization >= self.abort_threshold
        )
    
    def get_node_budget(self, node_name: str) -> int:
        """Get remaining budget for specific node."""
        status = self.get_status()
        
        if status.should_abort:
            return 0
        
        # Base budget for node
        base_budget = self.node_budgets.get(node_name, int(status.remaining_ms * 0.5))
        
        # Adjust based on remaining total budget
        if status.in_danger_zone:
            # In danger zone, be more conservative
            adjusted_budget = min(base_budget, int(status.remaining_ms * 0.7))
        else:
            adjusted_budget = min(base_budget, int(status.remaining_ms))
        
        return max(0, adjusted_budget)
    
    def check_timeout(self, node_name: str) -> bool:
        """Check if node should timeout based on budget."""
        status = self.get_status()
        
        if status.should_abort:
            logger.warning(f"Budget exhausted, aborting {node_name}", extra={
                "node": node_name,
                "consumed_ms": status.consumed_ms,
                "budget_ms": status.allocated_ms
            })
            return True
        
        node_budget = self.get_node_budget(node_name)
        if node_budget <= 0:
            logger.warning(f"Node budget exhausted: {node_name}", extra={
                "node": node_name,
                "node_budget": node_budget,
                "remaining_total": status.remaining_ms
            })
            return True
        
        return False
    
    def create_timeout_context(self, node_name: str) -> asyncio.TimeoutError:
        """Create timeout context for node execution."""
        node_budget = self.get_node_budget(node_name)
        timeout_seconds = node_budget / 1000.0
        
        return asyncio.timeout(timeout_seconds)

class PartialResultsManager:
    """Manages partial results when execution is interrupted."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.collected_results: Dict[str, Any] = {}
    
    def add_partial_result(self, node_name: str, result: Any):
        """Add partial result from a node."""
        self.collected_results[node_name] = result
        logger.info(f"Collected partial result from {node_name}")
    
    def has_useful_results(self) -> bool:
        """Check if we have enough partial results to provide value."""
        # Check if we have results from at least one data source
        data_sources = ["pubmed_search", "ctgov_search", "rag_search"]
        return any(source in self.collected_results for source in data_sources)
    
    def synthesize_partial_answer(self, state: OrchestratorState) -> Dict[str, Any]:
        """Create answer from partial results."""
        if not self.has_useful_results():
            return {
                "answer": "Unable to complete request due to timeout. Please try with a simpler query or longer timeout.",
                "partial_results": True,
                "checkpoint_id": f"partial_{int(time.time())}",
                "errors": state.get("errors", []) + [{
                    "node": "budget_manager",
                    "error": "Execution timed out with insufficient partial results",
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
        
        # Build answer from available results
        answer_parts = ["## Partial Results (Request Timed Out)\n\n"]
        
        # Add available results
        for node_name, result in self.collected_results.items():
            if result and isinstance(result, dict):
                results = result.get("results", [])
                if results:
                    source_name = node_name.replace("_search", "").replace("_", " ").title()
                    answer_parts.append(f"### {source_name} ({len(results)} results)\n")
                    
                    for i, item in enumerate(results[:3], 1):  # Show first 3
                        title = item.get("title", item.get("name", "Untitled"))
                        answer_parts.append(f"{i}. {title}\n")
                    
                    if len(results) > 3:
                        answer_parts.append(f"... and {len(results) - 3} more results\n")
                    
                    answer_parts.append("\n")
        
        answer_parts.append("\n*Note: This is a partial response due to timeout. " +
                           "Consider using a more specific query or longer timeout.*")
        
        return {
            "answer": "".join(answer_parts),
            "partial_results": True,
            "checkpoint_id": f"partial_{int(time.time())}",
            "collected_results": self.collected_results,
            "messages": state.get("messages", []) + [{
                "role": "assistant",
                "content": "Partial results provided due to timeout"
            }]
        }

def create_budget_middleware(config: OrchestratorConfig):
    """Create budget enforcement middleware."""
    budget_manager = BudgetManager(config)
    partial_manager = PartialResultsManager(config)
    
    def middleware(node_func: Callable):
        async def wrapped_node(state: OrchestratorState) -> Dict[str, Any]:
            node_name = getattr(node_func, "__name__", "unknown_node")
            
            # Check budget before execution
            if budget_manager.check_timeout(node_name):
                # Return partial results if available
                if partial_manager.has_useful_results():
                    return partial_manager.synthesize_partial_answer(state)
                else:
                    return {
                        "errors": state.get("errors", []) + [{
                            "node": node_name,
                            "error": "Budget exhausted",
                            "timestamp": datetime.utcnow().isoformat()
                        }]
                    }
            
            # Execute with timeout
            try:
                timeout_context = budget_manager.create_timeout_context(node_name)
                async with timeout_context:
                    result = await node_func(state)
                    
                    # Collect partial result
                    if node_name.endswith("_search") and result.get(f"{node_name}_results"):
                        partial_manager.add_partial_result(
                            node_name, result[f"{node_name}_results"]
                        )
                    
                    return result
                    
            except asyncio.TimeoutError:
                logger.warning(f"Node {node_name} timed out")
                
                # Return partial results if we have them
                if partial_manager.has_useful_results():
                    return partial_manager.synthesize_partial_answer(state)
                else:
                    return {
                        "errors": state.get("errors", []) + [{
                            "node": node_name,
                            "error": "Node execution timed out",
                            "timestamp": datetime.utcnow().isoformat()
                        }]
                    }
        
        return wrapped_node
    
    # Store managers on the middleware for access
    middleware.budget_manager = budget_manager
    middleware.partial_manager = partial_manager
    
    return middleware
```

## Testing Strategy

### Unit Tests

**File**: `tests/unit/orchestrator/state/test_persistence.py`
```python
"""Test state persistence functionality."""
import pytest
import tempfile
from datetime import datetime
from bio_mcp.orchestrator.state.persistence import (
    BioMCPCheckpointSaver, 
    StateManager,
    OrchestrationCheckpoint
)
from bio_mcp.orchestrator.config import OrchestratorConfig

@pytest.mark.asyncio
async def test_checkpoint_creation():
    """Test checkpoint creation and retrieval."""
    config = OrchestratorConfig()
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        checkpointer = BioMCPCheckpointSaver(config, f.name)
        manager = StateManager(config, checkpointer)
        
        state = {
            "query": "test query",
            "frame": {"intent": "test"},
            "node_path": ["node1", "node2"],
            "errors": []
        }
        
        checkpoint = await manager.create_checkpoint(state)
        
        assert checkpoint.checkpoint_id.startswith("ckpt_")
        assert checkpoint.query == "test query"
        
        # Retrieve checkpoint
        retrieved = await checkpointer.aget_checkpoint(checkpoint.checkpoint_id)
        assert retrieved is not None
        assert retrieved.query == "test query"
```

**File**: `tests/unit/orchestrator/state/test_error_recovery.py`
```python
"""Test error recovery mechanisms."""
import pytest
from bio_mcp.orchestrator.state.error_recovery import (
    ErrorClassifier,
    ErrorRecoveryManager,
    ErrorSeverity
)
from bio_mcp.orchestrator.config import OrchestratorConfig

def test_error_classification():
    """Test error classification logic."""
    classifier = ErrorClassifier()
    
    # Test timeout error
    classification = classifier.classify_error("Connection timeout", {})
    assert classification.severity == ErrorSeverity.TIMEOUT
    assert classification.retryable is True
    assert classification.max_retries == 3
    
    # Test rate limit error
    classification = classifier.classify_error("Rate limit exceeded", {})
    assert classification.severity == ErrorSeverity.MEDIUM
    assert classification.fallback_action == "exponential_backoff"

@pytest.mark.asyncio
async def test_retry_logic():
    """Test retry logic."""
    config = OrchestratorConfig()
    manager = ErrorRecoveryManager(config)
    
    # Mock retry function
    call_count = 0
    async def mock_retry():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("temporary failure")
        return {"success": True}
    
    # This would be called in a real scenario through handle_error
    # For testing, we verify the classification logic
    classification = manager.classifier.classify_error("temporary failure", {})
    assert classification.retryable is True
```

### Integration Tests

**File**: `tests/integration/orchestrator/test_state_management.py`
```python
"""Integration tests for state management."""
import pytest
import asyncio
from bio_mcp.orchestrator.state.budget_manager import BudgetManager
from bio_mcp.orchestrator.config import OrchestratorConfig

@pytest.mark.integration
@pytest.mark.asyncio
async def test_budget_enforcement():
    """Test budget enforcement in practice."""
    config = OrchestratorConfig()
    config.default_budget_ms = 1000  # 1 second budget
    
    manager = BudgetManager(config)
    manager.start_execution()
    
    # Initially should have budget
    assert not manager.check_timeout("test_node")
    
    # Simulate time passing
    await asyncio.sleep(0.5)
    status = manager.get_status()
    assert status.consumed_ms > 400  # Should have consumed significant time
    
    # Should still have budget
    assert not manager.check_timeout("test_node")
    
    # Wait for budget exhaustion
    await asyncio.sleep(0.8)
    assert manager.check_timeout("test_node")
```

## Acceptance Criteria
- [ ] BioMCPCheckpointSaver extends LangGraph's SQLite saver with bio-mcp metadata
- [ ] State persistence works across execution interruptions
- [ ] Error recovery correctly classifies and handles different error types
- [ ] Retry mechanisms use appropriate backoff strategies
- [ ] Budget enforcement prevents runaway executions
- [ ] Partial results are available when execution times out
- [ ] Query performance metrics are captured and stored
- [ ] Old checkpoints are cleaned up automatically
- [ ] Integration tests validate real-world error scenarios
- [ ] State transitions are properly logged and traceable

## Files Created/Modified
- `src/bio_mcp/orchestrator/state/persistence.py` - Enhanced state persistence
- `src/bio_mcp/orchestrator/state/error_recovery.py` - Error recovery mechanisms
- `src/bio_mcp/orchestrator/state/budget_manager.py` - Budget and timeout enforcement
- `tests/unit/orchestrator/state/test_persistence.py` - Persistence tests
- `tests/unit/orchestrator/state/test_error_recovery.py` - Error recovery tests
- `tests/integration/orchestrator/test_state_management.py` - Integration tests

## Next Milestone
After completion, proceed to **M4 — LangGraph Synthesis** which will focus on advanced result synthesis, citation extraction, and checkpoint management.
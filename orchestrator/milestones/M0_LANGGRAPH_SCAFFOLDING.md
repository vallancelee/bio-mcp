# M0 — LangGraph Scaffolding & Setup (COMPLETED ✅)

## Current Status: COMPLETED ✅
All scaffolding components have been successfully implemented and are operational in production.

## Objective
Set up LangGraph infrastructure for the bio-mcp orchestrator, including state schema definition, basic graph structure, and integration with existing bio-mcp components. Replace the original custom DAG executor approach with LangGraph's stateful graph architecture.

**COMPLETED FEATURES:**
- ✅ LangGraph dependencies installed and configured
- ✅ OrchestratorState typed state schema implemented
- ✅ AsyncSqliteSaver checkpointing operational
- ✅ Production graph with real nodes (not placeholders)
- ✅ Configuration integration complete
- ✅ Basic testing infrastructure in place

## Dependencies (Existing Bio-MCP Components)
- **Config System**: `src/bio_mcp/config/config.py` - Pydantic settings management
- **Logging**: `src/bio_mcp/config/logging_config.py` - Structured logging setup
- **Telemetry**: `src/bio_mcp/http/observability/` - OpenTelemetry configuration
- **Database**: `src/bio_mcp/shared/clients/database.py` - DatabaseManager
- **MCP Tools**: Existing pubmed, clinicaltrials, and rag tools

## New Components to Create

### 1. LangGraph Dependencies

**Add to pyproject.toml:**
```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "langgraph>=0.0.60",
    "langsmith>=0.0.60",  # For observability
    "langchain-core>=0.1.0",  # Core LangChain components
]
```

### 2. State Schema Definition

**File**: `src/bio_mcp/orchestrator/state.py`
```python
"""LangGraph state schema for bio-mcp orchestrator."""
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

# Core state for the orchestrator graph
class OrchestratorState(TypedDict):
    """Central state for bio-mcp orchestrator workflow."""
    
    # Input data
    query: str
    config: Dict[str, Any]
    
    # Processing stages
    frame: Optional[Dict[str, Any]]  # Parsed query intent
    routing_decision: Optional[str]  # Which path to take
    
    # Tool execution results
    pubmed_results: Optional[Dict[str, Any]]
    ctgov_results: Optional[Dict[str, Any]]
    rag_results: Optional[Dict[str, Any]]
    
    # Metadata and tracing
    tool_calls_made: List[str]
    cache_hits: Dict[str, bool]
    latencies: Dict[str, float]
    errors: List[Dict[str, Any]]
    node_path: List[str]  # Execution path through graph
    
    # Output
    answer: Optional[str]
    checkpoint_id: Optional[str]
    
    # Messages for tracing and debugging
    messages: Annotated[List[Dict[str, Any]], add_messages]

class FrameModel(BaseModel):
    """Pydantic model for Frame validation."""
    intent: str
    entities: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)
    fetch_policy: str = "cache_then_network"
    time_budget_ms: int = 5000
    parallel_limit: int = Field(default=5, description="Max parallel operations")

class NodeResult(BaseModel):
    """Standard result format for graph nodes."""
    success: bool
    data: Any = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    cache_hit: bool = False
    rows: int = 0
    latency_ms: float = 0
    node_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### 3. Base Graph Structure

**File**: `src/bio_mcp/orchestrator/graph.py`
```python
"""Core LangGraph setup for bio-mcp orchestrator."""
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.graph import CompiledGraph
from typing import Dict, Any, Optional
import sqlite3

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig

logger = get_logger(__name__)

class BioMCPGraph:
    """LangGraph-based orchestrator for bio-mcp."""
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        self._graph = None
        self._compiled_graph = None
        self._checkpointer = None
        
    def build_graph(self) -> StateGraph:
        """Build the orchestrator state graph."""
        if self._graph is not None:
            return self._graph
            
        workflow = StateGraph(OrchestratorState)
        
        # Placeholder nodes - will be implemented in M1
        workflow.add_node("parse_frame", self._parse_frame_placeholder)
        workflow.add_node("route_intent", self._route_intent_placeholder)
        workflow.add_node("synthesize", self._synthesize_placeholder)
        
        # Basic flow structure
        workflow.set_entry_point("parse_frame")
        workflow.add_edge("parse_frame", "route_intent")
        workflow.add_edge("route_intent", "synthesize")  # Simplified for now
        workflow.add_edge("synthesize", END)
        
        self._graph = workflow
        logger.info("Built orchestrator graph with placeholder nodes")
        return workflow
    
    def compile_graph(self) -> CompiledGraph:
        """Compile the graph with checkpointing."""
        if self._compiled_graph is not None:
            return self._compiled_graph
            
        if self._graph is None:
            self.build_graph()
            
        # Set up SQLite checkpointer for state persistence
        self._checkpointer = SqliteSaver.from_conn_string(":memory:")
        
        self._compiled_graph = self._graph.compile(
            checkpointer=self._checkpointer,
            debug=self.config.debug_mode
        )
        
        logger.info("Compiled orchestrator graph with checkpointing")
        return self._compiled_graph
    
    async def invoke(self, query: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the graph for a single query."""
        graph = self.compile_graph()
        
        initial_state = OrchestratorState(
            query=query,
            config=config or {},
            frame=None,
            routing_decision=None,
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=[],
            answer=None,
            checkpoint_id=None,
            messages=[]
        )
        
        try:
            result = await graph.ainvoke(initial_state)
            logger.info(f"Graph execution completed", extra={
                "query": query,
                "tool_calls": len(result.get("tool_calls_made", [])),
                "errors": len(result.get("errors", [])),
                "node_path": result.get("node_path", [])
            })
            return result
            
        except Exception as e:
            logger.error(f"Graph execution failed", extra={
                "query": query,
                "error": str(e)
            })
            raise
    
    async def stream(self, query: str, config: Optional[Dict[str, Any]] = None):
        """Stream graph execution results."""
        graph = self.compile_graph()
        
        initial_state = OrchestratorState(
            query=query,
            config=config or {},
            # ... same as invoke
        )
        
        async for chunk in graph.astream(initial_state):
            yield chunk
    
    # Placeholder node implementations (will be replaced in M1)
    
    def _parse_frame_placeholder(self, state: OrchestratorState) -> Dict[str, Any]:
        """Placeholder frame parser node."""
        logger.info("Parsing frame (placeholder)")
        return {
            "frame": {
                "intent": "recent_pubs_by_topic",
                "entities": {"topic": state["query"]},
                "filters": {},
                "fetch_policy": "cache_then_network",
                "time_budget_ms": 5000
            },
            "node_path": state["node_path"] + ["parse_frame"],
            "messages": state["messages"] + [{
                "role": "system",
                "content": f"Parsed query: {state['query']}"
            }]
        }
    
    def _route_intent_placeholder(self, state: OrchestratorState) -> Dict[str, Any]:
        """Placeholder router node."""
        frame = state["frame"]
        intent = frame["intent"] if frame else "recent_pubs_by_topic"
        
        logger.info(f"Routing intent: {intent}")
        return {
            "routing_decision": intent,
            "node_path": state["node_path"] + ["route_intent"],
            "messages": state["messages"] + [{
                "role": "system", 
                "content": f"Routed to intent: {intent}"
            }]
        }
    
    def _synthesize_placeholder(self, state: OrchestratorState) -> Dict[str, Any]:
        """Placeholder synthesizer node."""
        query = state["query"]
        
        # Generate simple response
        answer = f"Placeholder response for: {query}"
        checkpoint_id = f"ckpt_{hash(query) % 10000}"
        
        logger.info("Synthesizing response (placeholder)")
        return {
            "answer": answer,
            "checkpoint_id": checkpoint_id,
            "node_path": state["node_path"] + ["synthesize"],
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": answer
            }]
        }
```

### 4. Configuration Integration

**File**: `src/bio_mcp/orchestrator/config.py` (Enhanced)
```python
"""LangGraph orchestrator configuration."""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from pathlib import Path

from bio_mcp.config.config import Config

class LangGraphConfig(BaseModel):
    """LangGraph-specific configuration."""
    
    # Graph execution
    debug_mode: bool = Field(default=False, description="Enable graph debugging")
    max_iterations: int = Field(default=50, description="Max graph iterations")
    recursion_limit: int = Field(default=100, description="Recursion depth limit")
    
    # Checkpointing
    checkpoint_db_path: str = Field(default=":memory:", description="SQLite checkpoint DB path")
    checkpoint_ttl: int = Field(default=3600, description="Checkpoint TTL in seconds")
    
    # LangSmith integration
    langsmith_project: Optional[str] = Field(default="bio-mcp-orchestrator")
    langsmith_api_key: Optional[str] = Field(default=None, description="LangSmith API key")
    enable_tracing: bool = Field(default=True, description="Enable LangSmith tracing")

class OrchestratorConfig(BaseModel):
    """Enhanced orchestrator configuration for LangGraph."""
    
    # Timing & Performance
    default_budget_ms: int = Field(default=5000, description="Default time budget")
    max_budget_ms: int = Field(default=30000, description="Maximum allowed budget")
    node_timeout_ms: int = Field(default=2000, description="Default node timeout")
    
    # Concurrency
    max_parallel_nodes: int = Field(default=5, description="Max parallel node execution")
    
    # Rate Limiting
    pubmed_rps: float = Field(default=2.0, description="PubMed requests per second")
    ctgov_rps: float = Field(default=2.0, description="ClinicalTrials.gov requests per second")
    rag_rps: float = Field(default=3.0, description="RAG search requests per second")
    
    # Cache Policy
    default_fetch_policy: str = Field(default="cache_then_network")
    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")
    
    # Features
    enable_streaming: bool = Field(default=True, description="Enable streaming results")
    enable_partial_results: bool = Field(default=True, description="Return partial results on timeout")
    
    # LangGraph settings
    langgraph: LangGraphConfig = Field(default_factory=LangGraphConfig)
    
    @classmethod
    def from_main_config(cls, config: Config) -> "OrchestratorConfig":
        """Create from main bio-mcp configuration."""
        return cls(
            # Map relevant settings from main config
            default_budget_ms=getattr(config, 'default_timeout_ms', 5000),
            enable_streaming=getattr(config, 'enable_streaming', True),
        )
```

### 5. Basic Testing Infrastructure

**File**: `tests/unit/orchestrator/test_langgraph_setup.py`
```python
"""Test LangGraph orchestrator setup."""
import pytest
from bio_mcp.orchestrator.graph import BioMCPGraph
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import OrchestratorState

class TestLangGraphSetup:
    """Test basic LangGraph setup."""
    
    def test_config_creation(self):
        """Test orchestrator config creation."""
        config = OrchestratorConfig()
        assert config.default_budget_ms == 5000
        assert config.langgraph.debug_mode is False
        assert config.max_parallel_nodes == 5
    
    def test_graph_creation(self):
        """Test graph creation."""
        graph_builder = BioMCPGraph()
        graph = graph_builder.build_graph()
        
        # Check graph structure
        assert graph is not None
        assert "parse_frame" in graph.nodes
        assert "route_intent" in graph.nodes
        assert "synthesize" in graph.nodes
    
    def test_graph_compilation(self):
        """Test graph compilation with checkpointing."""
        graph_builder = BioMCPGraph()
        compiled_graph = graph_builder.compile_graph()
        
        assert compiled_graph is not None
        assert graph_builder._checkpointer is not None
    
    @pytest.mark.asyncio
    async def test_basic_execution(self):
        """Test basic graph execution with placeholders."""
        graph_builder = BioMCPGraph()
        result = await graph_builder.invoke("test query about diabetes")
        
        # Check result structure
        assert result["query"] == "test query about diabetes"
        assert result["answer"] is not None
        assert result["checkpoint_id"] is not None
        assert len(result["node_path"]) > 0
        assert "parse_frame" in result["node_path"]
        assert "synthesize" in result["node_path"]
    
    @pytest.mark.asyncio
    async def test_state_updates(self):
        """Test that state updates work correctly."""
        graph_builder = BioMCPGraph()
        result = await graph_builder.invoke("GLP-1 research")
        
        # Check state was properly updated through nodes
        assert result["frame"] is not None
        assert result["frame"]["intent"] == "recent_pubs_by_topic"
        assert result["routing_decision"] is not None
        assert len(result["messages"]) > 0
    
    @pytest.mark.asyncio
    async def test_streaming_execution(self):
        """Test streaming graph execution."""
        graph_builder = BioMCPGraph()
        chunks = []
        
        async for chunk in graph_builder.stream("Alzheimer drug trials"):
            chunks.append(chunk)
        
        # Should receive multiple chunks
        assert len(chunks) > 0
        
        # Last chunk should have final results
        final_chunk = chunks[-1]
        assert any("synthesize" in chunk for chunk in chunks)
```

## Integration Points

### 1. Update Main Config
**File**: `src/bio_mcp/config/config.py`
```python
# Add orchestrator config
from bio_mcp.orchestrator.config import OrchestratorConfig

class Config(BaseSettings):
    # ... existing fields ...
    
    orchestrator: OrchestratorConfig = Field(
        default_factory=OrchestratorConfig,
        description="LangGraph orchestrator configuration"
    )
```

### 2. Environment Variables
```bash
# LangSmith integration (optional)
export LANGSMITH_API_KEY="your-api-key"
export LANGSMITH_PROJECT="bio-mcp-orchestrator"

# LangGraph debugging
export LANGGRAPH_DEBUG=true
```

### 3. FastAPI Integration Point
**File**: `src/bio_mcp/http/app.py` (future integration)
```python
from bio_mcp.orchestrator.graph import BioMCPGraph

# Initialize orchestrator
orchestrator = BioMCPGraph()

@app.post("/orchestrate")
async def orchestrate_query(request: OrchestrationRequest):
    """Execute orchestration via LangGraph."""
    result = await orchestrator.invoke(request.query, request.config)
    return result
```

## Acceptance Criteria ✅ COMPLETED
- [x] LangGraph and dependencies successfully installed
- [x] `OrchestratorState` typed state schema defined (`src/bio_mcp/orchestrator/state.py`)
- [x] Production graph structure with real nodes created (`src/bio_mcp/orchestrator/graph_builder.py`)
- [x] Graph compilation with AsyncSqliteSaver checkpointing works
- [x] Graph execution (invoke) works with production nodes
- [x] Streaming execution (astream) implemented
- [x] Configuration integrated with main bio-mcp config
- [x] Unit tests pass for basic setup (`tests/unit/orchestrator/test_langgraph_setup.py`)
- [x] Integration tests validate end-to-end execution (`tests/integration/orchestrator/test_node_integration.py`)
- [x] Logging and telemetry integration confirmed

## Files Created
- `src/bio_mcp/orchestrator/state.py` - LangGraph state schema
- `src/bio_mcp/orchestrator/graph.py` - Core graph builder and execution
- `src/bio_mcp/orchestrator/config.py` - Enhanced configuration (updated)
- `tests/unit/orchestrator/test_langgraph_setup.py` - Setup validation tests

## Next Milestone
After completion, proceed to **M1 — LangGraph Nodes Implementation** which will replace the placeholder nodes with actual frame parsing, routing, tool execution, and synthesis logic.
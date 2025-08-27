# DESIGN & IMPLEMENTATION PLAN — Bio-MCP Orchestrator with LangGraph

This document adapts the original orchestrator design to use LangGraph's stateful graph architecture for executing MCP tool calls. LangGraph provides built-in state management, parallel execution, checkpointing, and visual debugging capabilities.

---

## 1) Objectives & Success Criteria

**Objectives**

* Interpret user questions → plan minimal tool calls → answer with citations and a `checkpoint_id`
* Support **lazy load**: fetch live from PubMed/CT.gov on cache misses, persist to S3/PG
* Return useful partial results under a strict latency budget
* Leverage LangGraph for stateful workflow orchestration

**Success Criteria**

* P50 end-to-end latency ≤ **2.5s**; P95 ≤ **5s** on common queries
* Answers include **tables/summaries + PMIDs/NCTs** and a `checkpoint_id`
* Deterministic outputs given same inputs + corpus snapshot
* Telemetry: one trace per question; spans per node with `cache_hit`, `rows`, `latency_ms`
* Graph visualization and debugging via LangSmith integration

**Non-Goals (this phase)**

* No multi-agent choreography beyond LangGraph nodes
* No paid data vendors
* No embeddings on the hot path (enqueue write-behind if needed)

---

## 2) LangGraph Architecture

### Core Components Flow

```
User Query
   │
   ▼
[Parse Frame Node] → OrchestratorState.frame
   │
   ▼
[Router Node] → OrchestratorState.routing_decision
   │
   ▼
[PubMed Search Node] → OrchestratorState.pubmed_results (M1: all routes go here)
   │
   ▼
[Synthesizer Node] → OrchestratorState.answer + session_id

Note: ClinicalTrials and RAG nodes are planned but route to PubMed in M1 implementation.
```

### State Management

```python
from typing import Annotated, Any, TypedDict
from langgraph.graph.message import add_messages

class OrchestratorState(TypedDict):
    """Central state for bio-mcp orchestrator workflow."""
    
    # Input data
    query: str
    config: dict[str, Any]
    
    # Processing stages
    frame: dict[str, Any] | None  # Parsed query intent
    routing_decision: str | None  # Which path to take
    
    # Tool execution results
    pubmed_results: dict[str, Any] | None
    ctgov_results: dict[str, Any] | None
    rag_results: dict[str, Any] | None
    
    # Metadata and tracing
    tool_calls_made: list[str]
    cache_hits: dict[str, bool]
    latencies: dict[str, float]
    errors: list[dict[str, Any]]
    node_path: list[str]  # Execution path through graph
    
    # Output
    answer: str | None
    orchestrator_checkpoint_id: str | None  # Renamed to avoid LangGraph reserved field collision
    
    # Messages for tracing and debugging
    messages: Annotated[list[dict[str, Any]], add_messages]
```

### Graph Topology

```python
from langgraph.graph import END, StateGraph
from bio_mcp.orchestrator.nodes.frame_node import create_frame_parser_node
from bio_mcp.orchestrator.nodes.router_node import create_router_node, routing_function
from bio_mcp.orchestrator.nodes.synthesizer_node import create_synthesizer_node
from bio_mcp.orchestrator.nodes.tool_nodes import create_pubmed_search_node

def build_orchestrator_graph(config: OrchestratorConfig) -> StateGraph:
    """Build the complete orchestrator graph with real nodes."""
    
    # Create graph
    workflow = StateGraph(OrchestratorState)
    
    # Create nodes with factory functions (M1 implementation)
    frame_parser = create_frame_parser_node(config)
    router = create_router_node(config)
    pubmed_search = create_pubmed_search_node(config)
    synthesizer = create_synthesizer_node(config)
    
    # Add nodes to graph
    workflow.add_node("parse_frame", frame_parser)
    workflow.add_node("router", router)
    workflow.add_node("pubmed_search", pubmed_search)
    workflow.add_node("synthesizer", synthesizer)
    
    # Entry point
    workflow.set_entry_point("parse_frame")
    
    # Sequential flow
    workflow.add_edge("parse_frame", "router")
    
    # Conditional routing (M1: simplified, all routes go to pubmed)
    workflow.add_conditional_edges(
        "router",
        routing_function,
        {
            "pubmed_search": "pubmed_search",
            # M1 limitation: other intents also route to pubmed_search
            "ctgov_search": "pubmed_search", 
            "rag_search": "pubmed_search",
        }
    )
    
    # Direct to synthesizer (no separate pubmed_get node)
    workflow.add_edge("pubmed_search", "synthesizer")
    
    # End state
    workflow.add_edge("synthesizer", END)
    
    return workflow
```

---

## 3) Data Contracts (LangGraph Adapted)

### 3.1 Frame (Enhanced for LangGraph State)

```python
from pydantic import BaseModel, Field
from typing import Literal, Dict, Any, Optional

FetchPolicy = Literal["cache_only", "cache_then_network", "network_only"]
Intent = Literal["recent_pubs_by_topic", "indication_phase_trials", "trials_with_pubs", "hybrid_search"]

class Frame(BaseModel):
    """Structured query intent for LangGraph processing."""
    intent: Intent
    entities: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)
    fetch_policy: FetchPolicy = "cache_then_network"
    time_budget_ms: int = 5000
    
    # LangGraph-specific fields
    parallel_limit: int = Field(default=5, description="Max parallel tool calls")
    retry_count: int = Field(default=0, description="Current retry count")
    node_path: List[str] = Field(default_factory=list, description="Execution path")
```

### 3.2 Node Configurations

```python
class NodeConfig(BaseModel):
    """Configuration for individual graph nodes."""
    name: str
    timeout_ms: int = 2000
    retry_policy: Dict[str, Any] = Field(default_factory=dict)
    rate_limit: Optional[float] = None
    cache_ttl: int = 3600  # seconds
```

### 3.3 Tool Registry (LangGraph Enhanced)

```json
{
  "nodes": {
    "pubmed_search": {
      "version": "v1",
      "timeout_ms": 2000,
      "rate_limit": 2.0,
      "retry_policy": {"max_attempts": 3, "backoff": "exponential"},
      "tool_mapping": "pubmed.search"
    },
    "pubmed_get": {
      "version": "v1", 
      "timeout_ms": 1500,
      "rate_limit": 3.0,
      "retry_policy": {"max_attempts": 2, "backoff": "linear"},
      "tool_mapping": "pubmed.get"
    },
    "ctgov_search": {
      "version": "v1",
      "timeout_ms": 3000, 
      "rate_limit": 1.5,
      "retry_policy": {"max_attempts": 3, "backoff": "exponential"},
      "tool_mapping": "clinicaltrials.search"
    },
    "rag_search": {
      "version": "v1",
      "timeout_ms": 2500,
      "rate_limit": 2.0,
      "retry_policy": {"max_attempts": 2, "backoff": "linear"}, 
      "tool_mapping": "rag.search"
    }
  }
}
```

---

## 4) LangGraph Execution Semantics

### Parallel Execution

```python
# Multiple nodes can execute in parallel via conditional edges
workflow.add_conditional_edges(
    "route_intent",
    route_by_intent,
    {
        "trials_with_pubs": ["ctgov_search", "pubmed_search"]  # Parallel execution
    }
)
```

### State Updates

```python
def pubmed_search_node(state: OrchestratorState) -> OrchestratorState:
    """Execute PubMed search and update state."""
    frame = state["frame"]
    
    # Execute tool call with rate limiting
    result = execute_pubmed_search(frame["entities"]["topic"])
    
    # Update state
    return {
        "pubmed_results": result,
        "tool_calls_made": state["tool_calls_made"] + ["pubmed_search"],
        "latencies": {**state["latencies"], "pubmed_search": result["latency_ms"]},
        "cache_hits": {**state["cache_hits"], "pubmed_search": result["cache_hit"]},
        "messages": [{"role": "system", "content": f"PubMed search completed: {len(result.get('results', []))} results"}]
    }
```

### Error Handling

```python
def handle_node_error(state: OrchestratorState, error: Exception, node_name: str) -> OrchestratorState:
    """Handle node execution errors."""
    error_info = {
        "node": node_name,
        "error": str(error),
        "timestamp": datetime.utcnow().isoformat(),
        "retry_count": state.get("retry_count", 0)
    }
    
    return {
        "errors": state["errors"] + [error_info],
        "messages": state["messages"] + [{"role": "system", "content": f"Error in {node_name}: {str(error)}"}]
    }
```

### Conditional Routing

```python
def routing_function(state: OrchestratorState) -> str:
    """Conditional routing function for LangGraph edges."""
    routing_decision = state.get("routing_decision", "pubmed_search")
    
    # M1 implementation: all routes go to pubmed_search
    # Future versions will implement proper conditional routing
    return "pubmed_search"  # Simplified for M1
    
# Future implementation (when M2+ nodes are ready):
def route_by_intent_full(state: OrchestratorState) -> str:
    """Full routing logic (not used in M1)."""
    frame = state.get("frame", {})
    intent = frame.get("intent", "recent_pubs_by_topic")
    
    if intent == "recent_pubs_by_topic":
        return "pubmed_search"
    elif intent == "indication_phase_trials":
        return "ctgov_search"
    elif intent == "hybrid_search":
        return "rag_search"
    else:
        return "pubmed_search"  # Fallback
```

---

## 5) Implementation Plan (LangGraph Milestones)

### ✅ M0 — LangGraph Scaffolding (COMPLETED)

* ✅ Install LangGraph dependencies
* ✅ Set up StateGraph with OrchestratorState
* ✅ Basic node structure and graph compilation
* ✅ Integration with bio-mcp config system
* 🔄 LangSmith integration for tracing (config ready, not implemented)

### ✅ M1 — Core Nodes Implementation (COMPLETED)

* ✅ Frame parser node with existing logic (`FrameParserNode`)
* ✅ Router node with intent-based conditional routing (`RouterNode`)
* ✅ PubMed search node (combined search + fetch) (`PubMedSearchNode`)
* ⏳ ClinicalTrials and RAG nodes (routes to PubMed for M1)
* ✅ Synthesizer node for final answer generation (`SynthesizerNode`)

### 🔄 M2 — State Management & Flow Control (PARTIAL)

* ✅ State schema validation with Pydantic (`FrameModel`, `NodeResult`)
* ⏳ Conditional edges and parallel execution (simplified for M1)
* ✅ Error handling and retry logic (basic implementation in nodes)
* ✅ State persistence and checkpointing (AsyncSqliteSaver)

### 🔄 M3 — Tool Integration (PARTIAL)

* ✅ Wrap existing MCP tools as LangGraph nodes (PubMed via client)
* ⏳ Cache-then-network pattern in nodes (basic cache_hits tracking)
* ✅ Rate limiting middleware for nodes (`TokenBucketRateLimiter`)
* ✅ Tool result normalization (structured response format)

### M4 — Advanced Features (1 day)

* Streaming partial results
* Budget/timeout enforcement
* LangSmith observability integration
* Graph visualization

### M5 — Testing & Optimization (2 days)

* Unit tests for individual nodes
* Integration tests for graph execution
* Performance optimization
* E2E testing with real queries

---

## 6) LangGraph Code Skeletons

### 6.1 Main Orchestrator

```python
# orchestrator/langgraph_orchestrator.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Dict, Any

from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.nodes import (
    parse_frame_node,
    route_intent_node, 
    pubmed_search_node,
    ctgov_search_node,
    rag_search_node,
    pubmed_get_node,
    synthesize_node
)
from bio_mcp.orchestrator.routing import route_by_intent

class BioMCPOrchestrator:
    """LangGraph-based orchestrator for bio-mcp."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.graph = self._build_graph()
        
        # Set up checkpointing
        self.checkpointer = SqliteSaver.from_conn_string(":memory:")
        self.app = self.graph.compile(checkpointer=self.checkpointer)
    
    def _build_graph(self) -> StateGraph:
        """Build the orchestrator graph."""
        workflow = StateGraph(OrchestratorState)
        
        # Add nodes
        workflow.add_node("parse_frame", parse_frame_node)
        workflow.add_node("route_intent", route_intent_node)
        workflow.add_node("pubmed_search", pubmed_search_node)
        workflow.add_node("ctgov_search", ctgov_search_node)
        workflow.add_node("rag_search", rag_search_node)
        workflow.add_node("pubmed_get", pubmed_get_node)
        workflow.add_node("synthesize", synthesize_node)
        
        # Set entry point
        workflow.set_entry_point("parse_frame")
        
        # Add edges
        workflow.add_edge("parse_frame", "route_intent")
        
        # Conditional routing
        workflow.add_conditional_edges(
            "route_intent",
            route_by_intent,
            {
                "recent_pubs_by_topic": ["pubmed_search"],
                "indication_phase_trials": ["ctgov_search"],
                "trials_with_pubs": ["ctgov_search", "pubmed_search"],
                "hybrid_search": ["rag_search"]
            }
        )
        
        # Continue to synthesis
        workflow.add_edge("pubmed_search", "pubmed_get")
        workflow.add_edge("pubmed_get", "synthesize")
        workflow.add_edge("ctgov_search", "synthesize") 
        workflow.add_edge("rag_search", "synthesize")
        workflow.add_edge("synthesize", END)
        
        return workflow
    
    async def orchestrate(self, query: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute orchestration for a query."""
        initial_state = OrchestratorState(
            query=query,
            config=config or self.config,
            frame=None,
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            answer=None,
            checkpoint_id=None,
            messages=[]
        )
        
        # Execute graph
        result = await self.app.ainvoke(initial_state)
        
        return {
            "answer": result["answer"],
            "checkpoint_id": result["checkpoint_id"],
            "trace": {
                "tool_calls": result["tool_calls_made"],
                "cache_hits": result["cache_hits"],
                "latencies": result["latencies"],
                "errors": result["errors"]
            }
        }
    
    async def stream_orchestrate(self, query: str, config: Dict[str, Any] = None):
        """Stream orchestration results as they become available."""
        initial_state = OrchestratorState(
            query=query,
            config=config or self.config,
            # ... other fields
        )
        
        async for chunk in self.app.astream(initial_state):
            yield chunk
```

### 6.2 Example Node Implementation

```python
# src/bio_mcp/orchestrator/nodes/tool_nodes.py (M1 Implementation)
from typing import Any
from datetime import UTC, datetime
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.sources.pubmed.client import PubMedClient, PubMedConfig

class PubMedSearchNode(BaseToolNode):
    """Node for executing PubMed searches."""
    
    def __init__(self, config: OrchestratorConfig):
        super().__init__(config, "pubmed_search")
        pubmed_config = PubMedConfig()
        self.client = PubMedClient(pubmed_config)
    
    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Execute PubMed search using query directly (M1 simplification)."""
        search_term = state.get("query")  # Direct query usage
        
        if not search_term:
            # Fallback to frame entities for backward compatibility
            frame = state.get("frame", {})
            entities = frame.get("entities", {})
            search_term = entities.get("topic") or entities.get("indication")
        
        if not search_term:
            return self._error_response(state, "No search term found")
    
        try:
            # Search for PMIDs
            search_result = await self.client.search(
                query=search_term,
                limit=20
            )
            
            # Fetch full documents (combined in M1)
            documents = []
            if search_result.pmids:
                doc_details = await self.client.fetch_documents(search_result.pmids)
                documents = [{
                    "pmid": doc.pmid,
                    "title": doc.title,
                    "authors": doc.authors or [],
                    "year": doc.publication_date.year if doc.publication_date else None,
                    "abstract": doc.abstract
                } for doc in doc_details]
            
            # Calculate latency
            latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            
            # Update state (partial update pattern)
            return {
                "pubmed_results": {
                    "total_count": search_result.total_count,
                    "results": documents,
                    "query": search_term
                },
                "tool_calls_made": state["tool_calls_made"] + ["pubmed_search"],
                "cache_hits": {**state["cache_hits"], "pubmed_search": False},
                "latencies": {**state["latencies"], "pubmed_search": latency_ms},
                "node_path": state["node_path"] + ["pubmed_search"],
                "messages": state["messages"] + [{
                    "role": "system",
                    "content": f"PubMed search completed: {len(documents)} results"
                }]
            }
        
        except Exception as e:
            return self._error_response(state, str(e))
```

---

## 7) Benefits of LangGraph Approach

### Built-in Features

1. **State Persistence**: Automatic state checkpointing and recovery
2. **Parallel Execution**: Native support for concurrent node execution  
3. **Visual Debugging**: Graph visualization and execution tracing
4. **Streaming**: Stream partial results as nodes complete
5. **Error Handling**: Built-in retry policies and error recovery
6. **Observability**: Integration with LangSmith for monitoring
7. **Conditional Logic**: Clean conditional routing between nodes

### Integration with Bio-MCP

1. **MCP Tool Wrapping**: Existing tools become graph nodes
2. **State Schema**: Typed state management with Pydantic
3. **Caching**: Cache-then-network pattern at node level
4. **Rate Limiting**: Per-node rate limiting middleware
5. **Telemetry**: Enhanced tracing with graph context

---

## 8) Testing Strategy

### Unit Tests

```python
# Test individual nodes in isolation
def test_pubmed_search_node():
    state = OrchestratorState(
        frame={"entities": {"topic": "GLP-1"}, "filters": {}}
    )
    result = await pubmed_search_node(state)
    assert "pubmed_results" in result
    assert len(result["tool_calls_made"]) > 0
```

### Integration Tests

```python
# Test graph execution end-to-end
def test_orchestrator_graph():
    orchestrator = BioMCPOrchestrator(config={})
    result = await orchestrator.orchestrate("recent papers on diabetes")
    assert result["answer"] is not None
    assert result["checkpoint_id"] is not None
```

### Graph Validation

```python
# Test graph structure and routing
def test_graph_routing():
    graph = create_orchestrator_graph()
    
    # Test intent routing
    state = OrchestratorState(frame={"intent": "recent_pubs_by_topic"})
    next_nodes = route_by_intent(state)
    assert "pubmed_search" in next_nodes
```

---

## 9) Migration from Original Design

### Component Mapping

| Original | LangGraph | Notes |
|----------|-----------|-------|
| `exec.py` DAG executor | `StateGraph` execution | Built-in parallel execution |
| Context dictionary | `OrchestratorState` | Typed state with persistence |
| Wave-based execution | Conditional edges | More flexible routing |
| Custom checkpointing | LangGraph checkpointer | Built-in fault tolerance |
| Manual error handling | Node error handling | Automatic retry policies |

### Preserved Components

* Frame parsing logic (wrapped as node)
* Tool clients (wrapped as nodes)
* Synthesizer logic (as final node)
* Configuration system
* Telemetry and tracing

---

## 10) Current Implementation Status & Architecture

### Two Parallel Implementations

The codebase currently has two LangGraph implementations:

1. **Production Implementation** (`graph_builder.py`):
   - Uses real node classes: `FrameParserNode`, `RouterNode`, `PubMedSearchNode`, `SynthesizerNode`
   - Factory functions: `create_frame_parser_node()`, etc.
   - Simplified M1 routing: all intents → pubmed_search
   - Used by POC backend via `build_orchestrator_graph(config)`

2. **Legacy Placeholder** (`graph.py`):
   - `BioMCPGraph` class with placeholder nodes
   - Kept for compatibility during development
   - Uses MemorySaver instead of AsyncSqliteSaver

### Current Limitations (M1)

**Routing Limitations:**
- All intents route to `pubmed_search` node
- No parallel execution via conditional edges
- ClinicalTrials and RAG nodes not implemented

**Feature Gaps:**
- No streaming results implementation in nodes
- Basic cache_hits tracking (not full cache-then-network)
- LangSmith integration configured but not active

**State Management:**
- `session_id` field exists but `checkpoint_id` renamed to `orchestrator_checkpoint_id`
- Query normalization fields present but node excluded per requirements
- `node_path` tracking works correctly

### Working Features

**Core Workflow:**
```
parse_frame → router → pubmed_search → synthesizer → END
```

**State Tracking:**
- Execution path in `node_path`
- Latency measurement per node
- Error handling and propagation
- Structured message logging

**Integration Points:**
- POC backend integration via `langgraph_client.py`
- AsyncSqliteSaver checkpointing
- Real PubMedClient integration
- Pydantic model validation

---

## 11) Rollout Plan

### Phase 1: Core Migration (Week 1)
* Set up LangGraph scaffolding
* Implement core nodes (parse, route, synthesize)
* Basic graph execution

### Phase 2: Tool Integration (Week 2)  
* Wrap existing MCP tools as nodes
* Implement cache-then-network pattern
* Add rate limiting middleware

### Phase 3: Advanced Features (Week 3)
* Streaming results
* Enhanced error handling
* LangSmith observability

### Phase 4: Testing & Optimization (Week 4)
* Comprehensive testing
* Performance tuning
* Production deployment

This LangGraph-based approach provides a more robust, maintainable, and observable orchestration system while preserving the core functionality and performance requirements of the original design.
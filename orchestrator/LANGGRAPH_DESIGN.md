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
[Router Node] → conditional edges based on intent
   │
   ├─→ [PubMed Search Node] → OrchestratorState.pubmed_results
   ├─→ [ClinicalTrials Node] → OrchestratorState.ctgov_results  
   └─→ [RAG Search Node] → OrchestratorState.rag_results
   │
   ▼
[Synthesizer Node] → OrchestratorState.answer + checkpoint_id
```

### State Management

```python
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import add_messages

class OrchestratorState(TypedDict):
    """Central state for bio-mcp orchestrator workflow."""
    
    # Input
    query: str
    config: Dict[str, Any]  # Budget, fetch policy, etc.
    
    # Parsed intent
    frame: Optional[Dict[str, Any]]  # Frame from parser
    
    # Tool execution results
    pubmed_results: Optional[Dict[str, Any]]
    ctgov_results: Optional[Dict[str, Any]]
    rag_results: Optional[Dict[str, Any]]
    
    # Execution metadata
    tool_calls_made: List[str]
    cache_hits: Dict[str, bool]
    latencies: Dict[str, float]
    errors: List[Dict[str, Any]]
    
    # Output
    answer: Optional[str]
    checkpoint_id: Optional[str]
    
    # Tracing
    messages: Annotated[List[Dict], add_messages]
```

### Graph Topology

```python
from langgraph.graph import StateGraph, END

def create_orchestrator_graph() -> StateGraph:
    """Create the main orchestrator graph."""
    
    workflow = StateGraph(OrchestratorState)
    
    # Add nodes
    workflow.add_node("parse_frame", parse_frame_node)
    workflow.add_node("route_intent", route_intent_node)
    workflow.add_node("pubmed_search", pubmed_search_node)
    workflow.add_node("ctgov_search", ctgov_search_node)
    workflow.add_node("rag_search", rag_search_node)
    workflow.add_node("pubmed_get", pubmed_get_node)
    workflow.add_node("synthesize", synthesize_node)
    
    # Entry point
    workflow.set_entry_point("parse_frame")
    
    # Sequential flow to router
    workflow.add_edge("parse_frame", "route_intent")
    
    # Conditional routing based on intent
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
    
    # PubMed pipeline
    workflow.add_edge("pubmed_search", "pubmed_get")
    workflow.add_edge("pubmed_get", "synthesize")
    
    # Direct synthesis paths
    workflow.add_edge("ctgov_search", "synthesize")
    workflow.add_edge("rag_search", "synthesize")
    
    # End state
    workflow.add_edge("synthesize", END)
    
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
def route_by_intent(state: OrchestratorState) -> List[str]:
    """Route execution based on parsed intent."""
    frame = state["frame"]
    intent = frame["intent"]
    
    if intent == "recent_pubs_by_topic":
        return ["pubmed_search"]
    elif intent == "indication_phase_trials":
        return ["ctgov_search"]
    elif intent == "trials_with_pubs":
        return ["ctgov_search", "pubmed_search"]  # Parallel
    elif intent == "hybrid_search":
        return ["rag_search"]
    else:
        # Fallback
        return ["pubmed_search"]
```

---

## 5) Implementation Plan (LangGraph Milestones)

### M0 — LangGraph Scaffolding (1 day)

* Install LangGraph dependencies
* Set up StateGraph with OrchestratorState
* Basic node structure and graph compilation
* Integration with bio-mcp config system
* LangSmith integration for tracing

### M1 — Core Nodes Implementation (2 days)

* Frame parser node with existing logic
* Router node with intent-based conditional routing
* Tool execution nodes (PubMed, ClinicalTrials, RAG)
* Synthesizer node for final answer generation

### M2 — State Management & Flow Control (1 day)

* State schema validation with Pydantic
* Conditional edges and parallel execution
* Error handling and retry logic
* State persistence and checkpointing

### M3 — Tool Integration (2 days)

* Wrap existing MCP tools as LangGraph nodes
* Cache-then-network pattern in nodes
* Rate limiting middleware for nodes
* Tool result normalization

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
# orchestrator/nodes/pubmed_node.py
from typing import Dict, Any
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.sources.pubmed.client import PubMedClient
from bio_mcp.orchestrator.middleware import with_rate_limit, with_cache

@with_rate_limit(rate=2.0)  # 2 RPS
@with_cache(ttl=3600)  # 1 hour cache
async def pubmed_search_node(state: OrchestratorState) -> Dict[str, Any]:
    """Execute PubMed search based on frame."""
    frame = state["frame"]
    topic = frame["entities"].get("topic")
    
    if not topic:
        return {
            "errors": state["errors"] + [{"node": "pubmed_search", "error": "No topic found"}]
        }
    
    try:
        # Execute search
        client = PubMedClient()
        result = await client.search(
            term=topic,
            limit=20,
            published_within_days=frame["filters"].get("published_within_days")
        )
        
        # Update state
        return {
            "pubmed_results": result,
            "tool_calls_made": state["tool_calls_made"] + ["pubmed_search"],
            "latencies": {**state["latencies"], "pubmed_search": result.get("latency_ms", 0)},
            "cache_hits": {**state["cache_hits"], "pubmed_search": result.get("cache_hit", False)},
            "messages": state["messages"] + [{
                "role": "system", 
                "content": f"PubMed search for '{topic}': {len(result.get('results', []))} results"
            }]
        }
    
    except Exception as e:
        return {
            "errors": state["errors"] + [{
                "node": "pubmed_search",
                "error": str(e),
                "query": topic
            }]
        }
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

## 10) Rollout Plan

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
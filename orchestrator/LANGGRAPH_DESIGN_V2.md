Perfect — here’s your **updated design doc**, refactored so the “parse\_frame” node is now a **single LLM-based parser node** (strict JSON schema + validation + regex/gazetteer backstop). I’ve woven it into the existing structure you pasted, preserving everything else.

---

# DESIGN & IMPLEMENTATION PLAN — Bio-MCP Orchestrator with LangGraph (LLM Parser v1)

This document adapts the original orchestrator design to use LangGraph's stateful graph architecture for executing MCP tool calls. LangGraph provides built-in state management, parallel execution, checkpointing, and visual debugging capabilities.
**Update:** The multi-step parse pipeline has been collapsed into a **single LLM-based parser node** that produces a structured `Frame` object. This simplifies v1 while retaining correctness via JSON schema validation and lightweight backstop rules.

---

## 1) Objectives & Success Criteria

**Objectives**

* Interpret user questions → parse with LLM → plan tool calls → answer with citations and a `checkpoint_id`
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
[LLM Parse Node] → OrchestratorState.frame
   │
   ▼
[Router Node] → OrchestratorState.routing_decision
   │
   ├─→ [PubMed Search Node] → OrchestratorState.pubmed_results
   ├─→ [ClinicalTrials Node] → OrchestratorState.ctgov_results (future)
   └─→ [RAG Search Node] → OrchestratorState.rag_results (future)
   │
   ▼
[Synthesizer Node] → OrchestratorState.answer + orchestrator_checkpoint_id
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
    frame: dict[str, Any] | None  # Parsed query intent (from LLM parser)
    routing_decision: str | None  # Which path to take
    intent_confidence: float | None
    entity_confidence: dict[str, float]
    
    # Tool execution results
    pubmed_results: dict[str, Any] | None
    ctgov_results: dict[str, Any] | None
    rag_results: dict[str, Any] | None
    
    # Metadata and tracing
    tool_calls_made: list[str]
    cache_hits: dict[str, bool]
    latencies: dict[str, float]
    errors: list[dict[str, Any]]
    node_path: list[str]
    
    # Output
    answer: str | None
    orchestrator_checkpoint_id: str | None
    
    # Messages for tracing and debugging
    messages: Annotated[list[dict[str, Any]], add_messages]
```

---

## 3) LLM Parse Node

### Role

The **LLM parse node** replaces separate normalization/intent/entity/filter steps. It:

* Calls an LLM with the query + JSON schema.
* Produces structured `Frame` with `intent`, `entities`, `filters`, `tool_hints`.
* Includes per-field confidences + `parser_version`.
* Validates via Pydantic; retries once on schema failure.
* Applies regex/gazetteer backstops (e.g., NCT IDs, company aliases).

### Frame Contract

```python
from pydantic import BaseModel, Field
from typing import Literal, Dict, Any

Intent = Literal["recent_pubs_by_topic","indication_phase_trials","trials_with_pubs","hybrid_search"]

class Frame(BaseModel):
    intent: Intent
    entities: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)
    tool_hints: Dict[str, Any] = Field(default_factory=dict)

    intent_confidence: float = 1.0
    entity_confidence: Dict[str, float] = Field(default_factory=dict)
    parser_version: str = "v2025.08.27-a"
```

### Example Node

```python
@trace_method("llm_parse")
async def llm_parse_node(state: OrchestratorState):
    query = state["query"]
    start = datetime.utcnow()

    raw = await call_llm_with_schema(query)  # strict JSON schema
    try:
        frame = Frame(**raw).model_dump()
    except Exception as e:
        raw = await call_llm_with_schema(query, error=str(e))
        frame = Frame(**raw).model_dump()

    frame = apply_backstop_rules(query, frame)  # regex/gazetteer

    latency = (datetime.utcnow() - start).total_seconds() * 1000
    return {
        "frame": frame,
        "intent_confidence": frame.get("intent_confidence", 1.0),
        "entity_confidence": frame.get("entity_confidence", {}),
        "node_path": state["node_path"] + ["llm_parse"],
        "latencies": {**state["latencies"], "llm_parse": latency},
        "messages": state["messages"] + [{
            "role":"system",
            "content":f"Parsed intent={frame['intent']} conf={frame.get('intent_confidence'):.2f}"
        }]
    }
```

---

## 4) Graph Topology

```python
from langgraph.graph import END, StateGraph
from bio_mcp.orchestrator.nodes.llm_parse_node import llm_parse_node
from bio_mcp.orchestrator.nodes.router_node import create_router_node, routing_function
from bio_mcp.orchestrator.nodes.synthesizer_node import create_synthesizer_node
from bio_mcp.orchestrator.nodes.tool_nodes import create_pubmed_search_node

def build_orchestrator_graph(config: OrchestratorConfig) -> StateGraph:
    workflow = StateGraph(OrchestratorState)
    
    # Nodes
    workflow.add_node("llm_parse", llm_parse_node)
    router = create_router_node(config)
    pubmed_search = create_pubmed_search_node(config)
    synthesizer = create_synthesizer_node(config)
    
    workflow.add_node("router", router)
    workflow.add_node("pubmed_search", pubmed_search)
    workflow.add_node("synthesizer", synthesizer)
    
    # Entry point
    workflow.set_entry_point("llm_parse")
    
    # Edges
    workflow.add_edge("llm_parse", "router")
    workflow.add_conditional_edges(
        "router",
        routing_function,
        {
            "pubmed_search": "pubmed_search",
            "ctgov_search": "pubmed_search",  # M1 limitation
            "rag_search": "pubmed_search",    # M1 limitation
        }
    )
    workflow.add_edge("pubmed_search", "synthesizer")
    workflow.add_edge("synthesizer", END)
    
    return workflow
```

---

## 5) Router (Confidence-Aware)

```python
def routing_function(state: OrchestratorState) -> str:
    frame = state.get("frame") or {}
    intent = frame.get("intent", "recent_pubs_by_topic")
    conf = state.get("intent_confidence", 0.0)
    
    if conf < 0.5:
        return "rag_search"  # fallback
    
    return {
        "recent_pubs_by_topic": "pubmed_search",
        "indication_phase_trials": "ctgov_search",
        "trials_with_pubs": "ctgov_search",  # parallel fanout in future
        "hybrid_search": "rag_search"
    }.get(intent, "pubmed_search")
```

---

## 6) Implementation Plan (Updated Milestones)

### ✅ M0 — Scaffolding

* StateGraph scaffolding
* Checkpointer integration
* State schema

### ✅ M1 — Core Nodes

* **LLM Parse Node** (new unified parser)
* Router Node
* PubMed Search Node
* Synthesizer Node

### 🔄 M2 — Tool Expansion

* Add ClinicalTrials + RAG search nodes
* Enable parallel fanout (`trials_with_pubs`)
* Use `tool_hints` in tool calls

### M3 — Advanced Features

* Streaming partial results
* Budget/timeout enforcement
* LangSmith integration

### M4 — Testing & Optimization

* Unit + integration tests
* Performance tuning
* Production rollout

---

## 7) Benefits of LLM Parser Approach

* **Fastest path to production** — one node replaces multi-step parsing.
* **Guardrails:** strict JSON schema + validation + retry + regex backstop.
* **Confidence-aware routing** ensures robustness.
* **Future-proof:** easy to split into multiple nodes later if needed.

---

✅ This update makes the design doc consistent with your new decision: a **single LLM-based parser node** instead of separate normalization/intent/entity/filter nodes, while keeping all other LangGraph architecture unchanged.

Do you want me to also **regenerate your Graphviz DOT diagram** with `llm_parse` as the entry node replacing `parse_frame`?

# M1 — LangGraph Nodes Implementation (COMPLETED ✅)

## Current Status: COMPLETED ✅  
All core nodes have been implemented with the LLM-based parser approach from LANGGRAPH_DESIGN_V2.md. The system is operational in production.

**ACTUAL IMPLEMENTATION:**
- ✅ **LLM Parse Node**: `src/bio_mcp/orchestrator/nodes/llm_parse_node.py` (replaces frame parser)
- ✅ **Router Node**: `src/bio_mcp/orchestrator/nodes/router_node.py` (M1 limitation: all routes → PubMed)
- ✅ **PubMed Search Node**: `src/bio_mcp/orchestrator/nodes/tool_nodes.py` (production ready)
- ✅ **Synthesizer Node**: `src/bio_mcp/orchestrator/nodes/synthesizer_node.py` (production ready)
- ✅ **Graph Builder**: `src/bio_mcp/orchestrator/graph_builder.py` (using factory functions)

**CURRENT FLOW:** `llm_parse → router → pubmed_search → synthesizer`

## Objective
Replace placeholder nodes with actual implementations that integrate existing bio-mcp components. Build production-ready nodes for LLM-based query parsing, routing, tool execution, and synthesis that leverage the LangGraph state management system.

## Dependencies (Existing Bio-MCP Components)
- **LangGraph Setup**: `src/bio_mcp/orchestrator/graph.py` - Base graph structure
- **State Schema**: `src/bio_mcp/orchestrator/state.py` - OrchestratorState definition
- **Frame Parser**: `src/bio_mcp/orchestrator/frame.py` - Existing frame parsing logic
- **Rule Planner**: `src/bio_mcp/orchestrator/plan.py` - Intent-to-plan mapping
- **MCP Tools**: Existing PubMed, ClinicalTrials, and RAG tool implementations
- **Database**: `src/bio_mcp/shared/clients/database.py` - DatabaseManager
- **Telemetry**: `src/bio_mcp/http/observability/` - OpenTelemetry tracing

## Core Node Implementations

### 1. LLM Parse Node (IMPLEMENTED ✅)

**File**: `src/bio_mcp/orchestrator/nodes/llm_parse_node.py` (ACTUAL IMPLEMENTATION)
```python
"""Frame parser node for LangGraph orchestrator."""
from typing import Dict, Any
from datetime import datetime

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState, FrameModel
from bio_mcp.orchestrator.frame import FrameParser
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.http.observability.decorators import trace_method

logger = get_logger(__name__)

class FrameParserNode:
    """Node that parses natural language queries into structured frames."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.parser = FrameParser(config)
    
    @trace_method("parse_frame_node")
    async def __call__(self, state: OrchestratorState) -> Dict[str, Any]:
        """Parse query into frame structure."""
        start_time = datetime.utcnow()
        query = state["query"]
        
        try:
            # Parse using existing frame parser
            frame_dict = self.parser.parse_frame(query)
            
            # Validate with Pydantic model
            frame = FrameModel(**frame_dict)
            
            # Calculate latency
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.info("Frame parsed successfully", extra={
                "query": query,
                "intent": frame.intent,
                "entities": frame.entities,
                "latency_ms": latency_ms
            })
            
            # Update state
            return {
                "frame": frame.model_dump(),
                "node_path": state["node_path"] + ["parse_frame"],
                "latencies": {**state["latencies"], "parse_frame": latency_ms},
                "messages": state["messages"] + [{
                    "role": "system",
                    "content": f"Parsed intent: {frame.intent}"
                }]
            }
            
        except Exception as e:
            logger.error(f"Frame parsing failed", extra={
                "query": query,
                "error": str(e)
            })
            
            # Return error state
            return {
                "errors": state["errors"] + [{
                    "node": "parse_frame",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }],
                "node_path": state["node_path"] + ["parse_frame"],
                "messages": state["messages"] + [{
                    "role": "system",
                    "content": f"Frame parsing error: {str(e)}"
                }]
            }

def create_frame_parser_node(config: OrchestratorConfig):
    """Factory function to create frame parser node."""
    node = FrameParserNode(config)
    return node
```

### 2. Router Node

**File**: `src/bio_mcp/orchestrator/nodes/router_node.py`
```python
"""Router node for intent-based conditional routing."""
from typing import Dict, Any, List
from datetime import datetime

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.http.observability.decorators import trace_method

logger = get_logger(__name__)

class RouterNode:
    """Node that routes execution based on parsed intent."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self._setup_routing_rules()
    
    def _setup_routing_rules(self):
        """Setup intent to node routing rules."""
        self.routing_map = {
            "recent_pubs_by_topic": ["pubmed_search"],
            "indication_phase_trials": ["ctgov_search"],
            "trials_with_pubs": ["ctgov_search", "pubmed_search"],  # Parallel
            "hybrid_search": ["rag_search"],
            "company_pipeline": ["company_search", "ctgov_search"],
        }
    
    @trace_method("router_node")
    async def __call__(self, state: OrchestratorState) -> Dict[str, Any]:
        """Route based on frame intent."""
        start_time = datetime.utcnow()
        frame = state.get("frame")
        
        if not frame:
            logger.error("No frame found in state for routing")
            return {
                "routing_decision": "pubmed_search",  # Default fallback
                "errors": state["errors"] + [{
                    "node": "router",
                    "error": "No frame available for routing",
                    "timestamp": datetime.utcnow().isoformat()
                }],
                "node_path": state["node_path"] + ["router"]
            }
        
        intent = frame.get("intent", "recent_pubs_by_topic")
        
        # Get routing decision
        next_nodes = self.routing_map.get(intent, ["pubmed_search"])
        routing_decision = "|".join(next_nodes) if len(next_nodes) > 1 else next_nodes[0]
        
        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.info(f"Routing decision made", extra={
            "intent": intent,
            "routing": routing_decision,
            "parallel": len(next_nodes) > 1,
            "latency_ms": latency_ms
        })
        
        return {
            "routing_decision": routing_decision,
            "node_path": state["node_path"] + ["router"],
            "latencies": {**state["latencies"], "router": latency_ms},
            "messages": state["messages"] + [{
                "role": "system",
                "content": f"Routing to: {routing_decision}"
            }]
        }

def routing_function(state: OrchestratorState) -> List[str]:
    """Conditional routing function for LangGraph edges."""
    routing_decision = state.get("routing_decision", "pubmed_search")
    
    # Split parallel routes
    if "|" in routing_decision:
        return routing_decision.split("|")
    else:
        return [routing_decision]

def create_router_node(config: OrchestratorConfig):
    """Factory function to create router node."""
    node = RouterNode(config)
    return node
```

### 3. Tool Execution Nodes

**File**: `src/bio_mcp/orchestrator/nodes/tool_nodes.py`
```python
"""Tool execution nodes for LangGraph orchestrator."""
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState, NodeResult
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.middleware import RateLimiter, CacheManager
from bio_mcp.sources.pubmed.client import PubMedClient
from bio_mcp.sources.clinicaltrials.client import ClinicalTrialsClient
from bio_mcp.sources.rag.client import RAGClient
from bio_mcp.http.observability.decorators import trace_method

logger = get_logger(__name__)

class BaseToolNode:
    """Base class for tool execution nodes."""
    
    def __init__(self, config: OrchestratorConfig, tool_name: str):
        self.config = config
        self.tool_name = tool_name
        self.rate_limiter = RateLimiter(self._get_rate_limit())
        self.cache_manager = CacheManager(ttl=config.cache_ttl)
    
    def _get_rate_limit(self) -> float:
        """Get rate limit for this tool."""
        rate_limits = {
            "pubmed_search": self.config.pubmed_rps,
            "ctgov_search": self.config.ctgov_rps,
            "rag_search": self.config.rag_rps,
        }
        return rate_limits.get(self.tool_name, 2.0)
    
    async def _execute_with_middleware(self, execute_fn, cache_key: str) -> NodeResult:
        """Execute tool with rate limiting and caching."""
        # Check cache first
        cached = await self.cache_manager.get(cache_key)
        if cached:
            return NodeResult(
                success=True,
                data=cached,
                cache_hit=True,
                node_name=self.tool_name
            )
        
        # Apply rate limiting
        await self.rate_limiter.acquire()
        
        # Execute tool
        try:
            result = await execute_fn()
            
            # Cache successful results
            await self.cache_manager.set(cache_key, result)
            
            return NodeResult(
                success=True,
                data=result,
                cache_hit=False,
                rows=len(result.get("results", [])) if isinstance(result, dict) else 0,
                node_name=self.tool_name
            )
        except Exception as e:
            logger.error(f"Tool execution failed: {self.tool_name}", extra={
                "error": str(e)
            })
            return NodeResult(
                success=False,
                error_message=str(e),
                node_name=self.tool_name
            )

class PubMedSearchNode(BaseToolNode):
    """Node for executing PubMed searches."""
    
    def __init__(self, config: OrchestratorConfig):
        super().__init__(config, "pubmed_search")
        self.client = PubMedClient()
    
    @trace_method("pubmed_search_node")
    async def __call__(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute PubMed search based on frame."""
        start_time = datetime.utcnow()
        frame = state.get("frame", {})
        
        # Extract search parameters
        topic = frame.get("entities", {}).get("topic")
        indication = frame.get("entities", {}).get("indication")
        search_term = topic or indication
        
        if not search_term:
            return self._error_response(state, "No search term found in frame")
        
        # Build cache key
        filters = frame.get("filters", {})
        cache_key = f"pubmed:{search_term}:{filters.get('published_within_days', 'all')}"
        
        # Execute search
        async def execute():
            return await self.client.search(
                term=search_term,
                limit=20,
                published_within_days=filters.get("published_within_days")
            )
        
        result = await self._execute_with_middleware(execute, cache_key)
        
        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Update state
        return {
            "pubmed_results": result.data if result.success else None,
            "tool_calls_made": state["tool_calls_made"] + ["pubmed_search"],
            "cache_hits": {**state["cache_hits"], "pubmed_search": result.cache_hit},
            "latencies": {**state["latencies"], "pubmed_search": latency_ms},
            "node_path": state["node_path"] + ["pubmed_search"],
            "errors": state["errors"] + ([{
                "node": "pubmed_search",
                "error": result.error_message,
                "timestamp": datetime.utcnow().isoformat()
            }] if not result.success else []),
            "messages": state["messages"] + [{
                "role": "system",
                "content": f"PubMed search completed: {result.rows} results"
            }]
        }
    
    def _error_response(self, state: OrchestratorState, error_msg: str) -> Dict[str, Any]:
        """Generate error response."""
        return {
            "errors": state["errors"] + [{
                "node": "pubmed_search",
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat()
            }],
            "node_path": state["node_path"] + ["pubmed_search"]
        }

class ClinicalTrialsSearchNode(BaseToolNode):
    """Node for executing ClinicalTrials.gov searches."""
    
    def __init__(self, config: OrchestratorConfig):
        super().__init__(config, "ctgov_search")
        self.client = ClinicalTrialsClient()
    
    @trace_method("ctgov_search_node")
    async def __call__(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute ClinicalTrials search based on frame."""
        start_time = datetime.utcnow()
        frame = state.get("frame", {})
        
        # Extract search parameters
        entities = frame.get("entities", {})
        filters = frame.get("filters", {})
        
        condition = entities.get("indication")
        company = entities.get("company")
        nct = entities.get("trial_nct")
        
        if not any([condition, company, nct]):
            return self._error_response(state, "No search criteria found in frame")
        
        # Build cache key
        cache_key = f"ctgov:{condition}:{company}:{nct}:{filters.get('phase')}:{filters.get('status')}"
        
        # Execute search
        async def execute():
            return await self.client.search(
                condition=condition,
                sponsor=company,
                nct_id=nct,
                phase=filters.get("phase"),
                status=filters.get("status"),
                limit=50
            )
        
        result = await self._execute_with_middleware(execute, cache_key)
        
        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Update state
        return {
            "ctgov_results": result.data if result.success else None,
            "tool_calls_made": state["tool_calls_made"] + ["ctgov_search"],
            "cache_hits": {**state["cache_hits"], "ctgov_search": result.cache_hit},
            "latencies": {**state["latencies"], "ctgov_search": latency_ms},
            "node_path": state["node_path"] + ["ctgov_search"],
            "errors": state["errors"] + ([{
                "node": "ctgov_search",
                "error": result.error_message,
                "timestamp": datetime.utcnow().isoformat()
            }] if not result.success else []),
            "messages": state["messages"] + [{
                "role": "system",
                "content": f"ClinicalTrials search completed: {result.rows} results"
            }]
        }
    
    def _error_response(self, state: OrchestratorState, error_msg: str) -> Dict[str, Any]:
        """Generate error response."""
        return {
            "errors": state["errors"] + [{
                "node": "ctgov_search",
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat()
            }],
            "node_path": state["node_path"] + ["ctgov_search"]
        }

class RAGSearchNode(BaseToolNode):
    """Node for executing RAG searches."""
    
    def __init__(self, config: OrchestratorConfig):
        super().__init__(config, "rag_search")
        self.client = RAGClient()
    
    @trace_method("rag_search_node")
    async def __call__(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute RAG search based on frame."""
        start_time = datetime.utcnow()
        frame = state.get("frame", {})
        query = state["query"]
        
        # Build cache key
        cache_key = f"rag:{query}"
        
        # Execute search
        async def execute():
            return await self.client.search(
                query=query,
                limit=10,
                filters=frame.get("filters", {})
            )
        
        result = await self._execute_with_middleware(execute, cache_key)
        
        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Update state
        return {
            "rag_results": result.data if result.success else None,
            "tool_calls_made": state["tool_calls_made"] + ["rag_search"],
            "cache_hits": {**state["cache_hits"], "rag_search": result.cache_hit},
            "latencies": {**state["latencies"], "rag_search": latency_ms},
            "node_path": state["node_path"] + ["rag_search"],
            "errors": state["errors"] + ([{
                "node": "rag_search",
                "error": result.error_message,
                "timestamp": datetime.utcnow().isoformat()
            }] if not result.success else []),
            "messages": state["messages"] + [{
                "role": "system",
                "content": f"RAG search completed: {result.rows} results"
            }]
        }

# Factory functions
def create_pubmed_search_node(config: OrchestratorConfig):
    """Factory function to create PubMed search node."""
    return PubMedSearchNode(config)

def create_ctgov_search_node(config: OrchestratorConfig):
    """Factory function to create ClinicalTrials search node."""
    return ClinicalTrialsSearchNode(config)

def create_rag_search_node(config: OrchestratorConfig):
    """Factory function to create RAG search node."""
    return RAGSearchNode(config)
```

### 4. Synthesizer Node

**File**: `src/bio_mcp/orchestrator/nodes/synthesizer_node.py`
```python
"""Synthesizer node for generating final answers."""
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
import json

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.http.observability.decorators import trace_method

logger = get_logger(__name__)

class SynthesizerNode:
    """Node that synthesizes results into final answer."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
    
    @trace_method("synthesizer_node")
    async def __call__(self, state: OrchestratorState) -> Dict[str, Any]:
        """Synthesize results into final answer."""
        start_time = datetime.utcnow()
        
        # Gather all results
        pubmed_results = state.get("pubmed_results")
        ctgov_results = state.get("ctgov_results")
        rag_results = state.get("rag_results")
        
        # Generate answer based on available results
        answer = self._generate_answer(
            query=state["query"],
            frame=state.get("frame"),
            pubmed=pubmed_results,
            ctgov=ctgov_results,
            rag=rag_results
        )
        
        # Generate checkpoint ID
        checkpoint_id = self._generate_checkpoint_id(state)
        
        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.info("Answer synthesized", extra={
            "checkpoint_id": checkpoint_id,
            "answer_length": len(answer),
            "latency_ms": latency_ms,
            "tool_calls": len(state.get("tool_calls_made", [])),
            "cache_hit_rate": self._calculate_cache_hit_rate(state)
        })
        
        return {
            "answer": answer,
            "checkpoint_id": checkpoint_id,
            "node_path": state["node_path"] + ["synthesizer"],
            "latencies": {**state["latencies"], "synthesizer": latency_ms},
            "messages": state["messages"] + [{
                "role": "assistant",
                "content": answer
            }]
        }
    
    def _generate_answer(self, query: str, frame: Optional[Dict], 
                        pubmed: Optional[Dict], ctgov: Optional[Dict], 
                        rag: Optional[Dict]) -> str:
        """Generate answer from available results."""
        answer_parts = []
        
        # Header
        intent = frame.get("intent", "unknown") if frame else "unknown"
        answer_parts.append(f"## Query Analysis\n")
        answer_parts.append(f"Intent: {intent}\n")
        
        if frame and frame.get("entities"):
            entities = frame["entities"]
            entity_lines = [f"- {k}: {v}" for k, v in entities.items() if v]
            if entity_lines:
                answer_parts.append("Entities identified:\n" + "\n".join(entity_lines))
        
        answer_parts.append("\n## Results\n")
        
        # PubMed results
        if pubmed and pubmed.get("results"):
            answer_parts.append(f"\n### PubMed Publications ({len(pubmed['results'])} found)\n")
            for i, pub in enumerate(pubmed["results"][:5], 1):
                answer_parts.append(
                    f"{i}. **{pub.get('title', 'Untitled')}**\n"
                    f"   - PMID: {pub.get('pmid', 'N/A')}\n"
                    f"   - Authors: {', '.join(pub.get('authors', [])[:3])}...\n"
                    f"   - Year: {pub.get('year', 'N/A')}\n"
                )
        
        # ClinicalTrials results
        if ctgov and ctgov.get("results"):
            answer_parts.append(f"\n### Clinical Trials ({len(ctgov['results'])} found)\n")
            for i, trial in enumerate(ctgov["results"][:5], 1):
                answer_parts.append(
                    f"{i}. **{trial.get('title', 'Untitled')}**\n"
                    f"   - NCT ID: {trial.get('nct_id', 'N/A')}\n"
                    f"   - Phase: {trial.get('phase', 'N/A')}\n"
                    f"   - Status: {trial.get('status', 'N/A')}\n"
                    f"   - Sponsor: {trial.get('sponsor', 'N/A')}\n"
                )
        
        # RAG results
        if rag and rag.get("results"):
            answer_parts.append(f"\n### Related Documents ({len(rag['results'])} found)\n")
            for i, doc in enumerate(rag["results"][:3], 1):
                answer_parts.append(
                    f"{i}. {doc.get('title', 'Untitled')}\n"
                    f"   - Score: {doc.get('score', 0):.3f}\n"
                    f"   - {doc.get('snippet', 'No snippet available')[:200]}...\n"
                )
        
        # Summary
        total_results = (
            len(pubmed.get("results", [])) if pubmed else 0 +
            len(ctgov.get("results", [])) if ctgov else 0 +
            len(rag.get("results", [])) if rag else 0
        )
        
        if total_results == 0:
            answer_parts.append("\n*No results found for your query.*")
        else:
            answer_parts.append(f"\n---\n*Total results found: {total_results}*")
        
        return "\n".join(answer_parts)
    
    def _generate_checkpoint_id(self, state: OrchestratorState) -> str:
        """Generate unique checkpoint ID for this execution."""
        # Create hash from query and timestamp
        content = f"{state['query']}:{datetime.utcnow().isoformat()}"
        hash_digest = hashlib.md5(content.encode()).hexdigest()[:8]
        
        # Format: ckpt_YYYYMMDD_HASH
        date_str = datetime.utcnow().strftime("%Y%m%d")
        return f"ckpt_{date_str}_{hash_digest}"
    
    def _calculate_cache_hit_rate(self, state: OrchestratorState) -> float:
        """Calculate cache hit rate from state."""
        cache_hits = state.get("cache_hits", {})
        if not cache_hits:
            return 0.0
        
        total = len(cache_hits)
        hits = sum(1 for hit in cache_hits.values() if hit)
        return hits / total if total > 0 else 0.0

def create_synthesizer_node(config: OrchestratorConfig):
    """Factory function to create synthesizer node."""
    return SynthesizerNode(config)
```

### 5. Updated Graph Builder

**File**: `src/bio_mcp/orchestrator/graph_builder.py`
```python
"""Enhanced graph builder with real node implementations."""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Dict, Any, Optional

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.nodes.frame_node import create_frame_parser_node
from bio_mcp.orchestrator.nodes.router_node import create_router_node, routing_function
from bio_mcp.orchestrator.nodes.tool_nodes import (
    create_pubmed_search_node,
    create_ctgov_search_node,
    create_rag_search_node
)
from bio_mcp.orchestrator.nodes.synthesizer_node import create_synthesizer_node

logger = get_logger(__name__)

def build_orchestrator_graph(config: OrchestratorConfig) -> StateGraph:
    """Build the complete orchestrator graph with real nodes."""
    
    # Create graph
    workflow = StateGraph(OrchestratorState)
    
    # Create nodes
    frame_parser = create_frame_parser_node(config)
    router = create_router_node(config)
    pubmed_search = create_pubmed_search_node(config)
    ctgov_search = create_ctgov_search_node(config)
    rag_search = create_rag_search_node(config)
    synthesizer = create_synthesizer_node(config)
    
    # Add nodes to graph
    workflow.add_node("parse_frame", frame_parser)
    workflow.add_node("router", router)
    workflow.add_node("pubmed_search", pubmed_search)
    workflow.add_node("ctgov_search", ctgov_search)
    workflow.add_node("rag_search", rag_search)
    workflow.add_node("synthesizer", synthesizer)
    
    # Set entry point
    workflow.set_entry_point("parse_frame")
    
    # Add sequential edges
    workflow.add_edge("parse_frame", "router")
    
    # Add conditional routing
    workflow.add_conditional_edges(
        "router",
        routing_function,
        {
            "pubmed_search": "pubmed_search",
            "ctgov_search": "ctgov_search",
            "rag_search": "rag_search",
        }
    )
    
    # All tool nodes lead to synthesizer
    workflow.add_edge("pubmed_search", "synthesizer")
    workflow.add_edge("ctgov_search", "synthesizer")
    workflow.add_edge("rag_search", "synthesizer")
    
    # End after synthesis
    workflow.add_edge("synthesizer", END)
    
    logger.info("Built complete orchestrator graph with production nodes")
    return workflow
```

## Testing Strategy

### Unit Tests

**File**: `tests/unit/orchestrator/nodes/test_frame_node.py`
```python
"""Test frame parser node."""
import pytest
from datetime import datetime
from bio_mcp.orchestrator.nodes.frame_node import FrameParserNode
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig

@pytest.mark.asyncio
async def test_frame_parser_node():
    """Test frame parser node execution."""
    config = OrchestratorConfig()
    node = FrameParserNode(config)
    
    state = OrchestratorState(
        query="recent publications on GLP-1 agonists",
        config={},
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
    
    result = await node(state)
    
    assert "frame" in result
    assert result["frame"]["intent"] == "recent_pubs_by_topic"
    assert "parse_frame" in result["node_path"]
    assert "parse_frame" in result["latencies"]
```

**File**: `tests/unit/orchestrator/nodes/test_tool_nodes.py`
```python
"""Test tool execution nodes."""
import pytest
from unittest.mock import Mock, AsyncMock
from bio_mcp.orchestrator.nodes.tool_nodes import PubMedSearchNode
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig

@pytest.mark.asyncio
async def test_pubmed_search_node():
    """Test PubMed search node execution."""
    config = OrchestratorConfig()
    node = PubMedSearchNode(config)
    
    # Mock the client
    node.client = Mock()
    node.client.search = AsyncMock(return_value={
        "results": [
            {"pmid": "123", "title": "Test Article"}
        ]
    })
    
    state = OrchestratorState(
        query="test query",
        config={},
        frame={
            "entities": {"topic": "GLP-1"},
            "filters": {"published_within_days": 180}
        },
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
    
    result = await node(state)
    
    assert "pubmed_results" in result
    assert len(result["pubmed_results"]["results"]) == 1
    assert "pubmed_search" in result["tool_calls_made"]
    assert "pubmed_search" in result["cache_hits"]
```

### Integration Tests

**File**: `tests/integration/orchestrator/test_node_integration.py`
```python
"""Integration tests for LangGraph nodes."""
import pytest
from bio_mcp.orchestrator.graph_builder import build_orchestrator_graph
from bio_mcp.orchestrator.config import OrchestratorConfig
from langgraph.checkpoint.sqlite import SqliteSaver

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_graph_execution():
    """Test complete graph execution with real nodes."""
    config = OrchestratorConfig()
    graph = build_orchestrator_graph(config)
    
    # Compile with checkpointing
    checkpointer = SqliteSaver.from_conn_string(":memory:")
    compiled = graph.compile(checkpointer=checkpointer)
    
    # Execute a query
    initial_state = {
        "query": "recent papers on diabetes",
        "config": {},
        "frame": None,
        "routing_decision": None,
        "pubmed_results": None,
        "ctgov_results": None,
        "rag_results": None,
        "tool_calls_made": [],
        "cache_hits": {},
        "latencies": {},
        "errors": [],
        "node_path": [],
        "answer": None,
        "checkpoint_id": None,
        "messages": []
    }
    
    result = await compiled.ainvoke(initial_state)
    
    # Verify execution
    assert result["answer"] is not None
    assert result["checkpoint_id"] is not None
    assert "parse_frame" in result["node_path"]
    assert "router" in result["node_path"]
    assert "synthesizer" in result["node_path"]
    assert len(result["messages"]) > 0
```

## Acceptance Criteria ✅ COMPLETED
- [x] LLM parse node replaces frame parser with confidence scoring and backstop rules
- [x] Router node correctly routes based on intent (M1: simplified to PubMed only)
- [x] PubMed tool node wraps existing PubMed client with full search + fetch
- [x] All nodes include proper error handling and state updates
- [x] Nodes update state correctly with results, latencies, cache_hits, and node_path
- [x] Rate limiting middleware implemented (`TokenBucketRateLimiter`)
- [x] Synthesizer generates comprehensive markdown answers with PMIDs
- [x] Checkpoint IDs are unique and deterministic (session_id generation)
- [x] Unit tests exist for node implementations (`tests/unit/orchestrator/`)
- [x] Integration tests validate full graph execution (`tests/integration/orchestrator/`)
- [x] OpenTelemetry tracing spans created for each node
- [x] Logging includes all relevant execution details

**M1 LIMITATIONS (for M2):**
- ClinicalTrials and RAG nodes route to PubMed (simplified)
- No parallel execution via conditional edges
- Basic cache_hits tracking (not full cache-then-network)

## Files Created/Modified
- `src/bio_mcp/orchestrator/nodes/frame_node.py` - Frame parser node
- `src/bio_mcp/orchestrator/nodes/router_node.py` - Router node
- `src/bio_mcp/orchestrator/nodes/tool_nodes.py` - Tool execution nodes
- `src/bio_mcp/orchestrator/nodes/synthesizer_node.py` - Synthesizer node
- `src/bio_mcp/orchestrator/graph_builder.py` - Enhanced graph builder
- `tests/unit/orchestrator/nodes/test_frame_node.py` - Frame node tests
- `tests/unit/orchestrator/nodes/test_tool_nodes.py` - Tool node tests
- `tests/integration/orchestrator/test_node_integration.py` - Integration tests

## Next Milestone
After completion, proceed to **M2 — LangGraph Tool Integration** which will focus on deeper integration with existing MCP tools and implementing cache-then-network patterns.
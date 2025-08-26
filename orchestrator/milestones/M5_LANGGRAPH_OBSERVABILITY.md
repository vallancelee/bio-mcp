# M5 — LangGraph Observability & Monitoring (1 day)

## Objective
Implement comprehensive monitoring, debugging, and performance tracking for the LangGraph orchestrator using LangSmith integration, enhanced OpenTelemetry tracing, graph visualization, and detailed performance metrics collection. Focus on production-ready observability that enables debugging, optimization, and operational monitoring.

## Dependencies (Existing Bio-MCP Components)
- **M1-M4 LangGraph**: Complete orchestrator implementation
- **OpenTelemetry**: `src/bio_mcp/http/observability/` - Existing tracing infrastructure
- **Logging**: `src/bio_mcp/config/logging_config.py` - Structured logging
- **Database**: `src/bio_mcp/shared/clients/database.py` - Metrics storage
- **Configuration**: `src/bio_mcp/orchestrator/config.py` - Observability settings

## Core Observability Components

### 1. LangSmith Integration

**File**: `src/bio_mcp/orchestrator/observability/langsmith_tracer.py`
```python
"""LangSmith integration for LangGraph observability."""
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
import asyncio

try:
    from langsmith import Client, traceable
    from langsmith.schemas import RunTree, Example
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    # Create mock classes for when LangSmith is not available
    class Client:
        pass
    def traceable(func):
        return func

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import OrchestratorState

logger = get_logger(__name__)

@dataclass
class GraphExecutionTrace:
    """Trace data for graph execution."""
    trace_id: str
    query: str
    intent: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[float]
    node_traces: List[Dict[str, Any]]
    final_state: Dict[str, Any]
    success: bool
    error_message: Optional[str]
    quality_score: Optional[float]

class LangSmithTracer:
    """Integrates LangGraph execution with LangSmith tracing."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.enabled = LANGSMITH_AVAILABLE and config.langgraph.enable_tracing
        self.client = None
        
        if self.enabled:
            self._setup_client()
    
    def _setup_client(self):
        """Setup LangSmith client."""
        try:
            api_key = (
                self.config.langgraph.langsmith_api_key or
                os.getenv("LANGSMITH_API_KEY")
            )
            
            if not api_key:
                logger.warning("LangSmith API key not found, disabling tracing")
                self.enabled = False
                return
            
            self.client = Client(
                api_key=api_key,
                api_url=os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
            )
            
            # Test connection
            self.client.list_runs(limit=1)
            logger.info("LangSmith tracing enabled")
            
        except Exception as e:
            logger.error(f"Failed to setup LangSmith client: {e}")
            self.enabled = False
    
    @traceable(name="bio_mcp_orchestrator")
    async def trace_execution(
        self,
        query: str,
        execution_func,
        **kwargs
    ) -> Dict[str, Any]:
        """Trace complete orchestrator execution."""
        if not self.enabled:
            return await execution_func()
        
        trace_id = f"trace_{int(datetime.utcnow().timestamp() * 1000)}"
        start_time = datetime.utcnow()
        
        trace = GraphExecutionTrace(
            trace_id=trace_id,
            query=query,
            intent=None,
            start_time=start_time,
            end_time=None,
            duration_ms=None,
            node_traces=[],
            final_state={},
            success=False,
            error_message=None,
            quality_score=None
        )
        
        try:
            # Execute with tracing
            result = await execution_func()
            
            # Extract trace information
            self._extract_trace_data(trace, result)
            trace.success = True
            
            # Log to LangSmith
            await self._log_to_langsmith(trace, result)
            
            return result
            
        except Exception as e:
            trace.error_message = str(e)
            trace.success = False
            
            # Log error to LangSmith
            await self._log_to_langsmith(trace, {"error": str(e)})
            
            raise
        finally:
            trace.end_time = datetime.utcnow()
            trace.duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
    
    def _extract_trace_data(self, trace: GraphExecutionTrace, result: Dict[str, Any]):
        """Extract tracing data from execution result."""
        # Extract intent
        frame = result.get("frame", {})
        trace.intent = frame.get("intent")
        
        # Extract node execution path
        node_path = result.get("node_path", [])
        latencies = result.get("latencies", {})
        cache_hits = result.get("cache_hits", {})
        
        for node in node_path:
            node_trace = {
                "node_name": node,
                "latency_ms": latencies.get(node, 0),
                "cache_hit": cache_hits.get(node, False),
                "timestamp": datetime.utcnow().isoformat()
            }
            trace.node_traces.append(node_trace)
        
        # Extract quality score
        quality_metrics = result.get("quality_metrics", {})
        trace.quality_score = quality_metrics.get("overall_score")
        
        # Store final state (sanitized)
        trace.final_state = self._sanitize_state(result)
    
    def _sanitize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize state for logging (remove large data)."""
        sanitized = {}
        
        # Keep important metadata
        for key in ["query", "checkpoint_id", "node_path", "latencies", 
                   "cache_hits", "errors", "tool_calls_made"]:
            if key in state:
                sanitized[key] = state[key]
        
        # Summarize result counts instead of full data
        if "pubmed_results" in state:
            pubmed = state["pubmed_results"]
            sanitized["pubmed_summary"] = {
                "count": len(pubmed.get("results", [])) if isinstance(pubmed, dict) else 0,
                "has_data": bool(pubmed)
            }
        
        if "ctgov_results" in state:
            ctgov = state["ctgov_results"]
            sanitized["ctgov_summary"] = {
                "count": len(ctgov.get("results", [])) if isinstance(ctgov, dict) else 0,
                "has_data": bool(ctgov)
            }
        
        return sanitized
    
    async def _log_to_langsmith(self, trace: GraphExecutionTrace, result: Dict[str, Any]):
        """Log trace to LangSmith."""
        if not self.client:
            return
        
        try:
            # Create run data
            run_data = {
                "name": "bio_mcp_orchestration",
                "run_type": "chain",
                "inputs": {"query": trace.query},
                "outputs": {
                    "answer": result.get("answer", ""),
                    "checkpoint_id": result.get("checkpoint_id"),
                    "quality_score": trace.quality_score
                },
                "start_time": trace.start_time,
                "end_time": trace.end_time,
                "extra": {
                    "intent": trace.intent,
                    "node_traces": trace.node_traces,
                    "success": trace.success,
                    "duration_ms": trace.duration_ms,
                    "tool_calls": result.get("tool_calls_made", []),
                    "cache_hit_rate": self._calculate_cache_hit_rate(result)
                }
            }
            
            if trace.error_message:
                run_data["error"] = trace.error_message
            
            # Submit to LangSmith
            await asyncio.get_event_loop().run_in_executor(
                None, 
                self.client.create_run,
                **run_data
            )
            
        except Exception as e:
            logger.warning(f"Failed to log to LangSmith: {e}")
    
    def _calculate_cache_hit_rate(self, result: Dict[str, Any]) -> float:
        """Calculate cache hit rate."""
        cache_hits = result.get("cache_hits", {})
        if not cache_hits:
            return 0.0
        
        hits = sum(1 for hit in cache_hits.values() if hit)
        return hits / len(cache_hits)
    
    async def create_evaluation_dataset(self, queries: List[str], name: str) -> Optional[str]:
        """Create evaluation dataset in LangSmith."""
        if not self.enabled:
            return None
        
        try:
            examples = []
            for query in queries:
                examples.append(Example(
                    inputs={"query": query},
                    outputs=None  # Will be filled during evaluation
                ))
            
            dataset = await asyncio.get_event_loop().run_in_executor(
                None,
                self.client.create_dataset,
                name,
                examples=examples
            )
            
            return dataset.id
            
        except Exception as e:
            logger.error(f"Failed to create evaluation dataset: {e}")
            return None

# Global tracer instance
_langsmith_tracer = None

def get_langsmith_tracer(config: OrchestratorConfig) -> LangSmithTracer:
    """Get global LangSmith tracer instance."""
    global _langsmith_tracer
    if _langsmith_tracer is None:
        _langsmith_tracer = LangSmithTracer(config)
    return _langsmith_tracer
```

### 2. Enhanced OpenTelemetry Integration

**File**: `src/bio_mcp/orchestrator/observability/otel_tracer.py`
```python
"""Enhanced OpenTelemetry tracing for orchestrator."""
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import asynccontextmanager
import json

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.propagate import extract, inject
from opentelemetry.baggage import set_baggage, get_baggage

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.http.observability.context import get_trace_context

logger = get_logger(__name__)

class OrchestratorTracer:
    """Enhanced tracing for orchestrator execution."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.tracer = trace.get_tracer("bio_mcp.orchestrator")
    
    @asynccontextmanager
    async def trace_orchestration(self, query: str, config: Dict[str, Any]):
        """Trace complete orchestration execution."""
        with self.tracer.start_as_current_span(
            "orchestrator.execute",
            attributes={
                "orchestrator.query": query,
                "orchestrator.config": json.dumps(config, default=str),
                "orchestrator.version": "v1"
            }
        ) as span:
            # Set baggage for downstream spans
            set_baggage("query", query)
            
            try:
                yield span
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    
    @asynccontextmanager
    async def trace_node_execution(self, node_name: str, state: OrchestratorState):
        """Trace individual node execution."""
        with self.tracer.start_as_current_span(
            f"orchestrator.node.{node_name}",
            attributes={
                "node.name": node_name,
                "node.input_keys": list(state.keys()),
                "query": get_baggage("query", ""),
            }
        ) as span:
            start_time = datetime.utcnow()
            
            try:
                yield span
                
                # Calculate execution time
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                span.set_attribute("node.duration_ms", execution_time)
                span.set_status(Status(StatusCode.OK))
                
            except Exception as e:
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                span.set_attribute("node.duration_ms", execution_time)
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
    
    def add_node_result_attributes(self, span: trace.Span, result: Dict[str, Any]):
        """Add result attributes to node span."""
        # Add cache information
        if "cache_hits" in result:
            cache_hits = result["cache_hits"]
            span.set_attribute("node.cache_hits", sum(1 for hit in cache_hits.values() if hit))
            span.set_attribute("node.cache_total", len(cache_hits))
        
        # Add result counts
        for source in ["pubmed_results", "ctgov_results", "rag_results"]:
            if source in result and isinstance(result[source], dict):
                results = result[source].get("results", [])
                span.set_attribute(f"node.{source}_count", len(results))
        
        # Add error information
        if "errors" in result:
            errors = result["errors"]
            span.set_attribute("node.error_count", len(errors))
            if errors:
                latest_error = errors[-1]
                span.set_attribute("node.latest_error", latest_error.get("error", ""))
    
    def add_final_attributes(self, span: trace.Span, result: Dict[str, Any]):
        """Add final execution attributes."""
        # Quality metrics
        quality_metrics = result.get("quality_metrics", {})
        if quality_metrics:
            span.set_attribute("orchestrator.quality_score", 
                             quality_metrics.get("overall_score", 0))
            span.set_attribute("orchestrator.completeness_score",
                             quality_metrics.get("completeness_score", 0))
        
        # Execution summary
        latencies = result.get("latencies", {})
        if latencies:
            span.set_attribute("orchestrator.total_latency_ms", sum(latencies.values()))
            span.set_attribute("orchestrator.node_count", len(latencies))
        
        # Tool calls
        tool_calls = result.get("tool_calls_made", [])
        span.set_attribute("orchestrator.tool_calls_count", len(tool_calls))
        span.set_attribute("orchestrator.tool_calls", json.dumps(tool_calls))
        
        # Final status
        has_answer = bool(result.get("answer"))
        has_errors = len(result.get("errors", [])) > 0
        
        span.set_attribute("orchestrator.has_answer", has_answer)
        span.set_attribute("orchestrator.has_errors", has_errors)
        span.set_attribute("orchestrator.success", has_answer and not has_errors)

class TracingMiddleware:
    """Middleware to add tracing to orchestrator nodes."""
    
    def __init__(self, tracer: OrchestratorTracer):
        self.tracer = tracer
    
    def __call__(self, node_func):
        """Wrap node function with tracing."""
        async def traced_node(state: OrchestratorState) -> Dict[str, Any]:
            node_name = getattr(node_func, "__name__", node_func.__class__.__name__)
            
            async with self.tracer.trace_node_execution(node_name, state) as span:
                result = await node_func(state)
                
                # Add result attributes to span
                self.tracer.add_node_result_attributes(span, result)
                
                return result
        
        return traced_node

def create_tracing_middleware(config: OrchestratorConfig):
    """Create tracing middleware for orchestrator."""
    tracer = OrchestratorTracer(config)
    return TracingMiddleware(tracer)
```

### 3. Performance Metrics Collector

**File**: `src/bio_mcp/orchestrator/observability/metrics_collector.py`
```python
"""Performance metrics collection and analysis."""
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import statistics
import json

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.shared.clients.database import DatabaseManager

logger = get_logger(__name__)

@dataclass
class NodePerformanceMetrics:
    """Performance metrics for a single node."""
    node_name: str
    execution_count: int
    total_duration_ms: float
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p95_duration_ms: float
    cache_hit_rate: float
    error_rate: float
    last_execution: datetime

@dataclass
class OrchestrationMetrics:
    """Overall orchestration performance metrics."""
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_total_duration_ms: float
    avg_quality_score: float
    avg_result_count: int
    cache_hit_rate: float
    most_common_intents: List[Dict[str, Any]]
    node_metrics: List[NodePerformanceMetrics]

class MetricsCollector:
    """Collects and analyzes orchestrator performance metrics."""
    
    def __init__(self, config: OrchestratorConfig, db_manager: Optional[DatabaseManager] = None):
        self.config = config
        self.db_manager = db_manager
        
        # In-memory metrics storage
        self.execution_history = deque(maxlen=1000)  # Last 1000 executions
        self.node_performance = defaultdict(list)     # Node-specific metrics
        self.quality_history = deque(maxlen=1000)
        
        # Real-time metrics
        self.current_execution_count = 0
        self.current_error_count = 0
        self.last_reset_time = datetime.utcnow()
    
    async def record_execution(self, result: Dict[str, Any], execution_time_ms: float):
        """Record execution metrics."""
        timestamp = datetime.utcnow()
        
        # Extract metrics
        execution_data = {
            "timestamp": timestamp,
            "execution_time_ms": execution_time_ms,
            "success": len(result.get("errors", [])) == 0,
            "query": result.get("query", ""),
            "intent": result.get("frame", {}).get("intent", ""),
            "node_path": result.get("node_path", []),
            "latencies": result.get("latencies", {}),
            "cache_hits": result.get("cache_hits", {}),
            "tool_calls": result.get("tool_calls_made", []),
            "result_count": self._count_results(result),
            "quality_score": result.get("quality_metrics", {}).get("overall_score"),
            "checkpoint_id": result.get("checkpoint_id")
        }
        
        # Store in memory
        self.execution_history.append(execution_data)
        
        # Update node performance metrics
        await self._update_node_metrics(execution_data)
        
        # Store quality metrics
        if execution_data["quality_score"] is not None:
            self.quality_history.append({
                "timestamp": timestamp,
                "score": execution_data["quality_score"],
                "intent": execution_data["intent"]
            })
        
        # Update counters
        self.current_execution_count += 1
        if not execution_data["success"]:
            self.current_error_count += 1
        
        # Persist to database if available
        if self.db_manager:
            await self._persist_metrics(execution_data)
        
        # Log key metrics
        logger.info("Execution metrics recorded", extra={
            "execution_time_ms": execution_time_ms,
            "success": execution_data["success"],
            "quality_score": execution_data["quality_score"],
            "result_count": execution_data["result_count"],
            "cache_hit_rate": self._calculate_cache_hit_rate(execution_data["cache_hits"])
        })
    
    async def _update_node_metrics(self, execution_data: Dict[str, Any]):
        """Update node-specific performance metrics."""
        node_path = execution_data["node_path"]
        latencies = execution_data["latencies"]
        cache_hits = execution_data["cache_hits"]
        
        for node in node_path:
            node_data = {
                "timestamp": execution_data["timestamp"],
                "duration_ms": latencies.get(node, 0),
                "cache_hit": cache_hits.get(node, False),
                "success": execution_data["success"]
            }
            
            self.node_performance[node].append(node_data)
            
            # Keep only recent data (last 500 executions per node)
            if len(self.node_performance[node]) > 500:
                self.node_performance[node] = self.node_performance[node][-500:]
    
    def get_current_metrics(self) -> OrchestrationMetrics:
        """Get current performance metrics."""
        if not self.execution_history:
            return self._empty_metrics()
        
        # Calculate overall metrics
        recent_executions = list(self.execution_history)[-100:]  # Last 100
        
        total_executions = len(recent_executions)
        successful = sum(1 for ex in recent_executions if ex["success"])
        failed = total_executions - successful
        
        avg_duration = statistics.mean(ex["execution_time_ms"] for ex in recent_executions)
        
        # Quality metrics
        recent_quality = [ex["quality_score"] for ex in recent_executions 
                         if ex["quality_score"] is not None]
        avg_quality = statistics.mean(recent_quality) if recent_quality else 0.0
        
        # Result count
        avg_results = statistics.mean(ex["result_count"] for ex in recent_executions)
        
        # Cache hit rate
        all_cache_hits = []
        for ex in recent_executions:
            cache_hits = ex["cache_hits"]
            if cache_hits:
                all_cache_hits.extend(cache_hits.values())
        
        cache_hit_rate = sum(all_cache_hits) / len(all_cache_hits) if all_cache_hits else 0.0
        
        # Intent analysis
        intent_counts = defaultdict(int)
        for ex in recent_executions:
            intent = ex.get("intent", "unknown")
            intent_counts[intent] += 1
        
        most_common_intents = [
            {"intent": intent, "count": count, "percentage": count/total_executions*100}
            for intent, count in sorted(intent_counts.items(), key=lambda x: x[1], reverse=True)
        ][:5]
        
        # Node metrics
        node_metrics = []
        for node_name, node_data in self.node_performance.items():
            if not node_data:
                continue
                
            durations = [d["duration_ms"] for d in node_data if d["duration_ms"] > 0]
            cache_hits = [d["cache_hit"] for d in node_data]
            successes = [d["success"] for d in node_data]
            
            if durations:
                node_metrics.append(NodePerformanceMetrics(
                    node_name=node_name,
                    execution_count=len(node_data),
                    total_duration_ms=sum(durations),
                    avg_duration_ms=statistics.mean(durations),
                    min_duration_ms=min(durations),
                    max_duration_ms=max(durations),
                    p95_duration_ms=statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations),
                    cache_hit_rate=sum(cache_hits) / len(cache_hits) if cache_hits else 0.0,
                    error_rate=1.0 - (sum(successes) / len(successes)) if successes else 0.0,
                    last_execution=max(d["timestamp"] for d in node_data)
                ))
        
        return OrchestrationMetrics(
            total_executions=total_executions,
            successful_executions=successful,
            failed_executions=failed,
            avg_total_duration_ms=avg_duration,
            avg_quality_score=avg_quality,
            avg_result_count=int(avg_results),
            cache_hit_rate=cache_hit_rate,
            most_common_intents=most_common_intents,
            node_metrics=sorted(node_metrics, key=lambda x: x.avg_duration_ms, reverse=True)
        )
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate detailed performance report."""
        metrics = self.get_current_metrics()
        
        # Identify performance issues
        issues = []
        
        # High latency nodes
        high_latency_nodes = [
            n for n in metrics.node_metrics 
            if n.avg_duration_ms > 2000  # > 2 seconds
        ]
        
        if high_latency_nodes:
            issues.append({
                "type": "high_latency",
                "description": f"{len(high_latency_nodes)} nodes with high average latency",
                "nodes": [n.node_name for n in high_latency_nodes]
            })
        
        # Low cache hit rates
        low_cache_nodes = [
            n for n in metrics.node_metrics 
            if n.cache_hit_rate < 0.3 and n.execution_count > 10  # < 30% cache hit rate
        ]
        
        if low_cache_nodes:
            issues.append({
                "type": "low_cache_hit",
                "description": f"{len(low_cache_nodes)} nodes with low cache hit rates",
                "nodes": [n.node_name for n in low_cache_nodes]
            })
        
        # High error rates
        high_error_nodes = [
            n for n in metrics.node_metrics 
            if n.error_rate > 0.1  # > 10% error rate
        ]
        
        if high_error_nodes:
            issues.append({
                "type": "high_error_rate",
                "description": f"{len(high_error_nodes)} nodes with high error rates",
                "nodes": [n.node_name for n in high_error_nodes]
            })
        
        # Generate recommendations
        recommendations = []
        
        if metrics.cache_hit_rate < 0.5:
            recommendations.append("Consider increasing cache TTL or improving cache key strategies")
        
        if metrics.avg_total_duration_ms > 5000:
            recommendations.append("Overall execution time is high - consider parallelization or optimization")
        
        if metrics.avg_quality_score < 0.7:
            recommendations.append("Quality scores are low - review data sources and filtering criteria")
        
        return {
            "summary": asdict(metrics),
            "issues": issues,
            "recommendations": recommendations,
            "generated_at": datetime.utcnow().isoformat(),
            "time_period": f"Last {len(self.execution_history)} executions"
        }
    
    async def _persist_metrics(self, execution_data: Dict[str, Any]):
        """Persist metrics to database."""
        try:
            # This would insert into a metrics table
            # Implementation depends on specific database schema
            pass
        except Exception as e:
            logger.warning(f"Failed to persist metrics: {e}")
    
    def _count_results(self, result: Dict[str, Any]) -> int:
        """Count total results across all sources."""
        count = 0
        for source in ["pubmed_results", "ctgov_results", "rag_results"]:
            data = result.get(source)
            if isinstance(data, dict) and "results" in data:
                count += len(data["results"])
        return count
    
    def _calculate_cache_hit_rate(self, cache_hits: Dict[str, bool]) -> float:
        """Calculate cache hit rate."""
        if not cache_hits:
            return 0.0
        return sum(1 for hit in cache_hits.values() if hit) / len(cache_hits)
    
    def _empty_metrics(self) -> OrchestrationMetrics:
        """Return empty metrics structure."""
        return OrchestrationMetrics(
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
            avg_total_duration_ms=0.0,
            avg_quality_score=0.0,
            avg_result_count=0,
            cache_hit_rate=0.0,
            most_common_intents=[],
            node_metrics=[]
        )
    
    async def reset_metrics(self):
        """Reset all metrics."""
        self.execution_history.clear()
        self.node_performance.clear()
        self.quality_history.clear()
        self.current_execution_count = 0
        self.current_error_count = 0
        self.last_reset_time = datetime.utcnow()
        logger.info("Metrics reset")

# Global metrics collector
_metrics_collector = None

def get_metrics_collector(config: OrchestratorConfig, db_manager: Optional[DatabaseManager] = None) -> MetricsCollector:
    """Get global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(config, db_manager)
    return _metrics_collector
```

### 4. Graph Visualization and Debugging

**File**: `src/bio_mcp/orchestrator/observability/graph_visualizer.py`
```python
"""Graph visualization and debugging tools."""
from typing import Dict, Any, List, Optional, Tuple
import json
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState

logger = get_logger(__name__)

class NodeStatus(Enum):
    """Node execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class NodeVisualization:
    """Visualization data for a single node."""
    name: str
    status: NodeStatus
    duration_ms: Optional[float]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    input_size: int
    output_size: int
    cache_hit: bool
    error_message: Optional[str]
    
class GraphVisualizer:
    """Generates visualizations and debug information for graph execution."""
    
    def __init__(self):
        self.execution_logs: List[Dict[str, Any]] = []
    
    def log_execution_step(self, step_data: Dict[str, Any]):
        """Log execution step for visualization."""
        self.execution_logs.append({
            **step_data,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def generate_execution_timeline(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate timeline visualization of execution."""
        node_path = result.get("node_path", [])
        latencies = result.get("latencies", {})
        cache_hits = result.get("cache_hits", {})
        errors = result.get("errors", [])
        
        # Create timeline entries
        timeline = []
        cumulative_time = 0
        
        for node in node_path:
            duration = latencies.get(node, 0)
            cache_hit = cache_hits.get(node, False)
            
            # Find any errors for this node
            node_errors = [e for e in errors if e.get("node") == node]
            error_msg = node_errors[0].get("error") if node_errors else None
            
            status = NodeStatus.FAILED if node_errors else NodeStatus.COMPLETED
            
            timeline.append({
                "node": node,
                "start_time_ms": cumulative_time,
                "end_time_ms": cumulative_time + duration,
                "duration_ms": duration,
                "status": status.value,
                "cache_hit": cache_hit,
                "error": error_msg
            })
            
            cumulative_time += duration
        
        return {
            "timeline": timeline,
            "total_duration_ms": cumulative_time,
            "node_count": len(node_path),
            "error_count": len(errors)
        }
    
    def generate_mermaid_graph(self, result: Dict[str, Any]) -> str:
        """Generate Mermaid diagram of execution flow."""
        node_path = result.get("node_path", [])
        errors = result.get("errors", [])
        cache_hits = result.get("cache_hits", {})
        
        # Build Mermaid syntax
        lines = ["graph TD"]
        
        # Add nodes with status styling
        for i, node in enumerate(node_path):
            node_errors = [e for e in errors if e.get("node") == node]
            cache_hit = cache_hits.get(node, False)
            
            # Determine node styling
            if node_errors:
                style_class = "error"
                symbol = "❌"
            elif cache_hit:
                style_class = "cache"
                symbol = "💾"
            else:
                style_class = "normal"
                symbol = "✅"
            
            node_id = f"node_{i}"
            lines.append(f"    {node_id}[\"{symbol} {node.replace('_', ' ').title()}\"]")
            
            # Add connections
            if i > 0:
                prev_node_id = f"node_{i-1}"
                lines.append(f"    {prev_node_id} --> {node_id}")
        
        # Add styling
        lines.extend([
            "",
            "    classDef error fill:#ffcccc,stroke:#ff0000",
            "    classDef cache fill:#ccffcc,stroke:#00ff00", 
            "    classDef normal fill:#ccccff,stroke:#0000ff"
        ])
        
        # Apply styles
        for i, node in enumerate(node_path):
            node_errors = [e for e in errors if e.get("node") == node]
            cache_hit = cache_hits.get(node, False)
            
            node_id = f"node_{i}"
            if node_errors:
                lines.append(f"    class {node_id} error")
            elif cache_hit:
                lines.append(f"    class {node_id} cache")
            else:
                lines.append(f"    class {node_id} normal")
        
        return "\n".join(lines)
    
    def generate_debug_report(self, state: OrchestratorState, result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive debug report."""
        return {
            "execution_summary": {
                "query": result.get("query", ""),
                "checkpoint_id": result.get("checkpoint_id"),
                "success": len(result.get("errors", [])) == 0,
                "total_duration_ms": sum(result.get("latencies", {}).values()),
                "node_count": len(result.get("node_path", [])),
                "tool_calls": len(result.get("tool_calls_made", []))
            },
            
            "frame_analysis": {
                "intent": result.get("frame", {}).get("intent"),
                "entities": result.get("frame", {}).get("entities", {}),
                "filters": result.get("frame", {}).get("filters", {}),
                "fetch_policy": result.get("frame", {}).get("fetch_policy")
            },
            
            "node_execution": self._analyze_node_execution(result),
            
            "data_flow": self._analyze_data_flow(result),
            
            "error_analysis": self._analyze_errors(result.get("errors", [])),
            
            "performance_analysis": self._analyze_performance(result),
            
            "recommendations": self._generate_recommendations(result),
            
            "timeline": self.generate_execution_timeline(result),
            
            "mermaid_graph": self.generate_mermaid_graph(result)
        }
    
    def _analyze_node_execution(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze node execution details."""
        node_path = result.get("node_path", [])
        latencies = result.get("latencies", {})
        cache_hits = result.get("cache_hits", {})
        
        node_details = []
        for node in node_path:
            node_details.append({
                "name": node,
                "duration_ms": latencies.get(node, 0),
                "cache_hit": cache_hits.get(node, False),
                "percentage_of_total": (latencies.get(node, 0) / sum(latencies.values()) * 100) if sum(latencies.values()) > 0 else 0
            })
        
        return {
            "nodes": node_details,
            "total_nodes": len(node_path),
            "cache_hit_rate": sum(1 for hit in cache_hits.values() if hit) / len(cache_hits) if cache_hits else 0
        }
    
    def _analyze_data_flow(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze data flow through the graph."""
        data_sources = {}
        
        # Analyze PubMed data flow
        pubmed_data = result.get("pubmed_results")
        if pubmed_data:
            data_sources["pubmed"] = {
                "results_count": len(pubmed_data.get("results", [])),
                "has_full_articles": "full_articles" in pubmed_data,
                "search_terms": pubmed_data.get("search_terms", [])
            }
        
        # Analyze ClinicalTrials data flow
        ctgov_data = result.get("ctgov_results")
        if ctgov_data:
            data_sources["clinicaltrials"] = {
                "trials_count": len(ctgov_data.get("trials", [])),
                "filtered_count": ctgov_data.get("filtered_count", 0),
                "total_found": ctgov_data.get("total_found", 0)
            }
        
        # Analyze RAG data flow
        rag_data = result.get("rag_results")
        if rag_data:
            data_sources["rag"] = {
                "results_count": len(rag_data.get("results", [])),
                "avg_relevance": sum(r.get("score", 0) for r in rag_data.get("results", [])) / len(rag_data.get("results", [])) if rag_data.get("results") else 0
            }
        
        return {
            "sources": data_sources,
            "total_results": sum(
                source.get("results_count", source.get("trials_count", 0)) 
                for source in data_sources.values()
            )
        }
    
    def _analyze_errors(self, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze errors that occurred during execution."""
        if not errors:
            return {"error_count": 0, "errors": []}
        
        error_analysis = {
            "error_count": len(errors),
            "errors": [],
            "error_types": {},
            "nodes_with_errors": set()
        }
        
        for error in errors:
            error_analysis["errors"].append({
                "node": error.get("node", "unknown"),
                "error": error.get("error", ""),
                "timestamp": error.get("timestamp", ""),
                "severity": error.get("severity", "unknown")
            })
            
            error_type = self._classify_error_type(error.get("error", ""))
            error_analysis["error_types"][error_type] = error_analysis["error_types"].get(error_type, 0) + 1
            error_analysis["nodes_with_errors"].add(error.get("node", "unknown"))
        
        error_analysis["nodes_with_errors"] = list(error_analysis["nodes_with_errors"])
        
        return error_analysis
    
    def _classify_error_type(self, error_msg: str) -> str:
        """Classify error type based on message."""
        error_msg_lower = error_msg.lower()
        
        if "timeout" in error_msg_lower:
            return "timeout"
        elif "connection" in error_msg_lower:
            return "connection"
        elif "rate limit" in error_msg_lower:
            return "rate_limit"
        elif "parse" in error_msg_lower:
            return "parsing"
        elif "validation" in error_msg_lower:
            return "validation"
        else:
            return "other"
    
    def _analyze_performance(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance characteristics."""
        latencies = result.get("latencies", {})
        
        if not latencies:
            return {"total_duration": 0, "analysis": "No latency data available"}
        
        total_duration = sum(latencies.values())
        slowest_node = max(latencies.items(), key=lambda x: x[1])
        fastest_node = min(latencies.items(), key=lambda x: x[1])
        
        return {
            "total_duration_ms": total_duration,
            "slowest_node": {"name": slowest_node[0], "duration_ms": slowest_node[1]},
            "fastest_node": {"name": fastest_node[0], "duration_ms": fastest_node[1]},
            "parallelization_potential": self._assess_parallelization_potential(result),
            "bottlenecks": [node for node, duration in latencies.items() if duration > total_duration * 0.4]
        }
    
    def _assess_parallelization_potential(self, result: Dict[str, Any]) -> str:
        """Assess potential for parallelization."""
        tool_calls = result.get("tool_calls_made", [])
        
        if "pubmed_search" in tool_calls and "ctgov_search" in tool_calls:
            return "High - Search operations can be parallelized"
        elif len(tool_calls) > 2:
            return "Medium - Some operations can be parallelized"
        else:
            return "Low - Limited parallelization opportunities"
    
    def _generate_recommendations(self, result: Dict[str, Any]) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        latencies = result.get("latencies", {})
        cache_hits = result.get("cache_hits", {})
        errors = result.get("errors", [])
        
        # Performance recommendations
        if latencies:
            total_duration = sum(latencies.values())
            if total_duration > 5000:
                recommendations.append("Consider optimizing slow nodes or implementing parallelization")
            
            slowest_node = max(latencies.items(), key=lambda x: x[1])
            if slowest_node[1] > total_duration * 0.5:
                recommendations.append(f"Node '{slowest_node[0]}' is a bottleneck ({slowest_node[1]:.1f}ms)")
        
        # Cache recommendations
        if cache_hits:
            cache_hit_rate = sum(1 for hit in cache_hits.values() if hit) / len(cache_hits)
            if cache_hit_rate < 0.3:
                recommendations.append("Low cache hit rate - consider adjusting cache strategy")
        
        # Error recommendations
        if errors:
            error_types = {}
            for error in errors:
                error_type = self._classify_error_type(error.get("error", ""))
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            if "timeout" in error_types:
                recommendations.append("Timeout errors detected - consider increasing timeouts or optimizing queries")
            if "rate_limit" in error_types:
                recommendations.append("Rate limiting detected - implement exponential backoff")
        
        # Quality recommendations
        quality_metrics = result.get("quality_metrics", {})
        if quality_metrics:
            overall_score = quality_metrics.get("overall_score", 0)
            if overall_score < 0.6:
                recommendations.append("Low quality score - review data sources and filtering criteria")
        
        return recommendations
```

## Testing Strategy

### Unit Tests

**File**: `tests/unit/orchestrator/observability/test_langsmith_tracer.py`
```python
"""Test LangSmith integration."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from bio_mcp.orchestrator.observability.langsmith_tracer import LangSmithTracer
from bio_mcp.orchestrator.config import OrchestratorConfig

@pytest.mark.asyncio
async def test_langsmith_tracer():
    """Test LangSmith tracing functionality."""
    config = OrchestratorConfig()
    config.langgraph.enable_tracing = True
    
    with patch('bio_mcp.orchestrator.observability.langsmith_tracer.LANGSMITH_AVAILABLE', True):
        tracer = LangSmithTracer(config)
        
        # Mock execution function
        async def mock_execution():
            return {
                "query": "test query",
                "answer": "test answer",
                "checkpoint_id": "ckpt_123",
                "frame": {"intent": "test"},
                "node_path": ["node1", "node2"],
                "latencies": {"node1": 100, "node2": 200},
                "cache_hits": {"node1": True, "node2": False}
            }
        
        # Test tracing (will not actually call LangSmith without proper setup)
        result = await tracer.trace_execution("test query", mock_execution)
        
        assert result["query"] == "test query"
        assert result["answer"] == "test answer"
```

### Integration Tests

**File**: `tests/integration/orchestrator/test_observability_integration.py`
```python
"""Integration tests for observability components."""
import pytest
from bio_mcp.orchestrator.observability.metrics_collector import MetricsCollector
from bio_mcp.orchestrator.observability.graph_visualizer import GraphVisualizer
from bio_mcp.orchestrator.config import OrchestratorConfig

@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_collection():
    """Test metrics collection and analysis."""
    config = OrchestratorConfig()
    collector = MetricsCollector(config)
    
    # Mock execution result
    result = {
        "query": "test query",
        "frame": {"intent": "recent_pubs_by_topic"},
        "node_path": ["parse_frame", "router", "pubmed_search", "synthesizer"],
        "latencies": {"parse_frame": 50, "router": 10, "pubmed_search": 500, "synthesizer": 100},
        "cache_hits": {"pubmed_search": False},
        "errors": [],
        "tool_calls_made": ["pubmed_search"],
        "quality_metrics": {"overall_score": 0.8}
    }
    
    # Record execution
    await collector.record_execution(result, 660)
    
    # Get metrics
    metrics = collector.get_current_metrics()
    
    assert metrics.total_executions == 1
    assert metrics.successful_executions == 1
    assert len(metrics.node_metrics) > 0

@pytest.mark.integration
def test_graph_visualization():
    """Test graph visualization generation."""
    visualizer = GraphVisualizer()
    
    # Mock result
    result = {
        "node_path": ["parse_frame", "router", "pubmed_search"],
        "latencies": {"parse_frame": 50, "router": 10, "pubmed_search": 500},
        "cache_hits": {"parse_frame": False, "router": False, "pubmed_search": True},
        "errors": []
    }
    
    # Generate visualizations
    timeline = visualizer.generate_execution_timeline(result)
    mermaid = visualizer.generate_mermaid_graph(result)
    debug_report = visualizer.generate_debug_report({}, result)
    
    assert timeline["total_duration_ms"] == 560
    assert "graph TD" in mermaid
    assert "execution_summary" in debug_report
```

## Acceptance Criteria
- [ ] LangSmith integration traces complete graph executions
- [ ] OpenTelemetry spans are created for each node with proper attributes
- [ ] Metrics collector captures performance, quality, and error metrics
- [ ] Graph visualizer generates meaningful timeline and flow diagrams
- [ ] Debug reports provide actionable insights for optimization
- [ ] Performance recommendations identify bottlenecks and issues
- [ ] Mermaid diagrams accurately represent execution flow with status
- [ ] Error analysis classifies and provides context for failures
- [ ] Cache hit rate tracking helps optimize caching strategies
- [ ] Integration tests validate real tracing and metrics collection

## Files Created/Modified
- `src/bio_mcp/orchestrator/observability/langsmith_tracer.py` - LangSmith integration
- `src/bio_mcp/orchestrator/observability/otel_tracer.py` - Enhanced OpenTelemetry
- `src/bio_mcp/orchestrator/observability/metrics_collector.py` - Performance metrics
- `src/bio_mcp/orchestrator/observability/graph_visualizer.py` - Graph visualization
- `tests/unit/orchestrator/observability/test_langsmith_tracer.py` - LangSmith tests
- `tests/integration/orchestrator/test_observability_integration.py` - Integration tests

## Next Milestone
After completion, proceed to **M6 — LangGraph Testing** which will focus on comprehensive testing of the complete orchestrator system including unit tests, integration tests, and end-to-end testing scenarios.
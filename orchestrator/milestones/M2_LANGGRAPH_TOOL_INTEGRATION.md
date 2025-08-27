# M2 — LangGraph Tool Integration (COMPLETED ✅)

## Current Status: COMPLETED ✅
All major M2 components have been successfully implemented and integrated. The system now supports full multi-tool orchestration with enhanced nodes.

**COMPLETED:**
- ✅ PubMed tool integration via `EnhancedPubMedNode` (search + fetch combined)
- ✅ ClinicalTrials tool integration via `EnhancedTrialsNode` (search with quality filtering)
- ✅ RAG search tool integration via `EnhancedRAGNode` (relevance scoring)
- ✅ Advanced rate limiting with `TokenBucketRateLimiter`
- ✅ Parallel execution framework with `ParallelExecutor`
- ✅ MCP tool adapter with cache-then-network patterns via `MCPToolAdapter`
- ✅ State normalization and result formatting
- ✅ Error handling and fallback logic
- ✅ Graph builder updated to support all three tool types
- ✅ Router logic updated to route to correct nodes based on intent

**CURRENT CAPABILITIES:**
- Full routing: `pubmed_search`, `ctgov_search`, `rag_search` nodes operational
- Quality filtering and relevance scoring for all result types
- Rate limiting per tool type (PubMed: 2 RPS, ClinicalTrials: 2 RPS, RAG: 3 RPS)
- Parallel search execution with concurrency control
- Enhanced error handling with graceful degradation

## Objective
Implement deep integration between LangGraph nodes and existing bio-mcp MCP tools. Focus on cache-then-network patterns, robust error handling, parallel execution coordination, and tool result normalization to ensure seamless operation between the orchestrator and bio-mcp's existing data infrastructure.

## Dependencies (Existing Bio-MCP Components)
- **M1 LangGraph Nodes**: Basic node implementations from previous milestone
- **MCP Tools**: `src/bio_mcp/mcp/tool_definitions.py` - All existing tool schemas
- **PubMed Tools**: `src/bio_mcp/sources/pubmed/` - Search, get, sync tools
- **ClinicalTrials Tools**: `src/bio_mcp/sources/clinicaltrials/` - Search and sync tools
- **RAG Tools**: `src/bio_mcp/sources/rag/` - Search and document retrieval
- **Database**: `src/bio_mcp/shared/clients/database.py` - DatabaseManager
- **Caching**: `src/bio_mcp/shared/cache/` - Existing cache implementations

## Core Integration Components

### 1. MCP Tool Adapter Layer

**File**: `src/bio_mcp/orchestrator/adapters/mcp_adapter.py`
```python
"""Adapter layer for integrating MCP tools with LangGraph nodes."""
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import NodeResult
from bio_mcp.shared.clients.database import DatabaseManager
from bio_mcp.shared.cache.redis_cache import RedisCache
from bio_mcp.mcp.tool_definitions import get_tool_schema
from bio_mcp.http.observability.decorators import trace_method

logger = get_logger(__name__)

class MCPToolAdapter:
    """Adapter for executing MCP tools within LangGraph nodes."""
    
    def __init__(self, config: OrchestratorConfig, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.cache = RedisCache() if config.enable_redis_cache else None
        self._tool_schemas = {}
        self._load_tool_schemas()
    
    def _load_tool_schemas(self):
        """Load MCP tool schemas for validation."""
        try:
            # Import available tools dynamically
            from bio_mcp.sources.pubmed.tools import PubMedSearchTool, PubMedGetTool
            from bio_mcp.sources.clinicaltrials.tools import ClinicalTrialsSearchTool
            from bio_mcp.sources.rag.tools import RAGSearchTool
            
            self._tools = {
                "pubmed.search": PubMedSearchTool(self.db_manager),
                "pubmed.get": PubMedGetTool(self.db_manager),
                "clinicaltrials.search": ClinicalTrialsSearchTool(self.db_manager),
                "rag.search": RAGSearchTool(self.db_manager),
            }
            
            for tool_name, tool_instance in self._tools.items():
                self._tool_schemas[tool_name] = get_tool_schema(tool_name)
                
        except ImportError as e:
            logger.error(f"Failed to load MCP tools: {e}")
            self._tools = {}
    
    @trace_method("mcp_tool_execute")
    async def execute_tool(self, tool_name: str, args: Dict[str, Any], 
                          cache_policy: str = "cache_then_network") -> NodeResult:
        """Execute MCP tool with cache-then-network pattern."""
        start_time = datetime.utcnow()
        
        if tool_name not in self._tools:
            return NodeResult(
                success=False,
                error_code="TOOL_NOT_FOUND",
                error_message=f"Tool {tool_name} not available",
                node_name=tool_name
            )
        
        # Generate cache key
        cache_key = self._generate_cache_key(tool_name, args)
        
        # Apply cache policy
        if cache_policy in ["cache_only", "cache_then_network"]:
            cached_result = await self._get_cached_result(cache_key)
            if cached_result:
                logger.info(f"Cache hit for {tool_name}", extra={
                    "tool": tool_name,
                    "cache_key": cache_key
                })
                return NodeResult(
                    success=True,
                    data=cached_result,
                    cache_hit=True,
                    rows=self._count_results(cached_result),
                    latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                    node_name=tool_name
                )
        
        if cache_policy == "cache_only":
            return NodeResult(
                success=False,
                error_code="CACHE_MISS",
                error_message="No cached result available",
                cache_hit=False,
                node_name=tool_name
            )
        
        # Execute tool
        try:
            tool_instance = self._tools[tool_name]
            result = await self._execute_with_fallback(tool_instance, args)
            
            # Cache successful results
            if cache_policy in ["cache_then_network", "network_only"] and result:
                await self._cache_result(cache_key, result)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return NodeResult(
                success=True,
                data=result,
                cache_hit=False,
                rows=self._count_results(result),
                latency_ms=latency_ms,
                node_name=tool_name
            )
            
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}", extra={
                "tool": tool_name,
                "args": args,
                "error": str(e)
            })
            
            return NodeResult(
                success=False,
                error_code="EXECUTION_ERROR",
                error_message=str(e),
                cache_hit=False,
                latency_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                node_name=tool_name
            )
    
    async def _execute_with_fallback(self, tool_instance, args: Dict[str, Any]) -> Any:
        """Execute tool with database-first fallback pattern."""
        # Try database first for search tools
        if hasattr(tool_instance, 'search_database'):
            try:
                db_result = await tool_instance.search_database(args)
                if db_result and self._has_sufficient_results(db_result, args):
                    logger.info("Database search satisfied request", extra={
                        "tool": tool_instance.__class__.__name__,
                        "results": len(db_result.get("results", []))
                    })
                    return db_result
            except Exception as e:
                logger.warning(f"Database search failed, falling back to API: {e}")
        
        # Fall back to external API
        return await tool_instance.execute(args)
    
    def _has_sufficient_results(self, result: Dict[str, Any], args: Dict[str, Any]) -> bool:
        """Check if database result has sufficient results."""
        results = result.get("results", [])
        requested_limit = args.get("limit", 20)
        
        # Consider sufficient if we have at least 50% of requested results
        # or at least 5 results for smaller requests
        min_results = max(5, requested_limit * 0.5)
        return len(results) >= min_results
    
    def _generate_cache_key(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Generate cache key from tool name and arguments."""
        import hashlib
        import json
        
        # Sort args for consistent key generation
        sorted_args = json.dumps(args, sort_keys=True, default=str)
        key_content = f"{tool_name}:{sorted_args}"
        hash_digest = hashlib.md5(key_content.encode()).hexdigest()
        
        return f"mcp:{tool_name}:{hash_digest}"
    
    async def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Get result from cache."""
        if not self.cache:
            return None
        
        try:
            return await self.cache.get(cache_key)
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None
    
    async def _cache_result(self, cache_key: str, result: Any):
        """Cache result with TTL."""
        if not self.cache:
            return
        
        try:
            await self.cache.set(cache_key, result, ttl=self.config.cache_ttl)
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
    
    def _count_results(self, result: Any) -> int:
        """Count results in tool response."""
        if isinstance(result, dict):
            results = result.get("results", [])
            return len(results) if isinstance(results, list) else 1
        return 0 if result is None else 1

    async def batch_execute(self, tool_calls: List[Dict[str, Any]], 
                           max_concurrency: int = 5) -> List[NodeResult]:
        """Execute multiple tool calls concurrently."""
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def execute_with_semaphore(call):
            async with semaphore:
                return await self.execute_tool(
                    call["tool"],
                    call["args"],
                    call.get("cache_policy", "cache_then_network")
                )
        
        tasks = [execute_with_semaphore(call) for call in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(NodeResult(
                    success=False,
                    error_code="EXECUTION_EXCEPTION",
                    error_message=str(result),
                    node_name=tool_calls[i]["tool"]
                ))
            else:
                processed_results.append(result)
        
        return processed_results
```

### 2. Enhanced Rate Limiting Middleware

**File**: `src/bio_mcp/orchestrator/middleware/rate_limiter.py`
```python
"""Advanced rate limiting for MCP tool calls."""
import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass
from collections import defaultdict

from bio_mcp.config.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float
    burst_size: int
    window_size: int = 60  # seconds

class TokenBucketRateLimiter:
    """Token bucket rate limiter with burst support."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = config.burst_size
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens from bucket."""
        async with self.lock:
            now = time.time()
            
            # Add tokens based on time passed
            time_passed = now - self.last_update
            new_tokens = time_passed * self.config.requests_per_second
            self.tokens = min(self.config.burst_size, self.tokens + new_tokens)
            self.last_update = now
            
            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            # Calculate wait time
            wait_time = (tokens - self.tokens) / self.config.requests_per_second
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            
            # Wait and retry
            await asyncio.sleep(wait_time)
            self.tokens = max(0, self.tokens - tokens)
            return True

class GlobalRateLimiter:
    """Global rate limiter managing multiple tool rate limits."""
    
    def __init__(self):
        self.limiters: Dict[str, TokenBucketRateLimiter] = {}
        self.default_configs = {
            "pubmed": RateLimitConfig(requests_per_second=2.0, burst_size=5),
            "clinicaltrials": RateLimitConfig(requests_per_second=2.0, burst_size=3),
            "rag": RateLimitConfig(requests_per_second=3.0, burst_size=8),
        }
    
    def _get_limiter(self, tool_name: str) -> TokenBucketRateLimiter:
        """Get or create rate limiter for tool."""
        if tool_name not in self.limiters:
            # Extract base tool name (e.g., "pubmed.search" -> "pubmed")
            base_name = tool_name.split('.')[0]
            config = self.default_configs.get(base_name, 
                RateLimitConfig(requests_per_second=1.0, burst_size=2))
            
            self.limiters[tool_name] = TokenBucketRateLimiter(config)
        
        return self.limiters[tool_name]
    
    async def acquire(self, tool_name: str, tokens: int = 1) -> bool:
        """Acquire rate limit tokens for tool."""
        limiter = self._get_limiter(tool_name)
        return await limiter.acquire(tokens)

# Global rate limiter instance
_global_rate_limiter = GlobalRateLimiter()

async def rate_limit(tool_name: str, tokens: int = 1) -> bool:
    """Global rate limiting function."""
    return await _global_rate_limiter.acquire(tool_name, tokens)
```

### 3. Parallel Execution Coordinator

**File**: `src/bio_mcp/orchestrator/execution/parallel_executor.py`
```python
"""Parallel execution coordination for LangGraph nodes."""
import asyncio
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
from dataclasses import dataclass

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import NodeResult
from bio_mcp.orchestrator.adapters.mcp_adapter import MCPToolAdapter

logger = get_logger(__name__)

@dataclass
class ParallelTask:
    """Task for parallel execution."""
    id: str
    tool_name: str
    args: Dict[str, Any]
    cache_policy: str = "cache_then_network"
    timeout_ms: int = 5000

class ParallelExecutor:
    """Coordinates parallel execution of multiple MCP tools."""
    
    def __init__(self, adapter: MCPToolAdapter, max_concurrency: int = 5):
        self.adapter = adapter
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
    
    async def execute_parallel(self, tasks: List[ParallelTask]) -> Dict[str, NodeResult]:
        """Execute tasks in parallel with concurrency control."""
        if not tasks:
            return {}
        
        start_time = datetime.utcnow()
        
        # Create coroutines for all tasks
        task_coroutines = [
            self._execute_task_with_timeout(task)
            for task in tasks
        ]
        
        # Execute all tasks
        results = await asyncio.gather(*task_coroutines, return_exceptions=True)
        
        # Process results
        result_dict = {}
        for task, result in zip(tasks, results):
            if isinstance(result, Exception):
                result_dict[task.id] = NodeResult(
                    success=False,
                    error_code="PARALLEL_EXECUTION_ERROR",
                    error_message=str(result),
                    node_name=task.tool_name
                )
            else:
                result_dict[task.id] = result
        
        total_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.info("Parallel execution completed", extra={
            "task_count": len(tasks),
            "success_count": sum(1 for r in result_dict.values() if r.success),
            "total_time_ms": total_time,
            "avg_time_per_task_ms": total_time / len(tasks) if tasks else 0
        })
        
        return result_dict
    
    async def _execute_task_with_timeout(self, task: ParallelTask) -> NodeResult:
        """Execute single task with timeout and concurrency control."""
        async with self.semaphore:
            try:
                # Apply timeout
                return await asyncio.wait_for(
                    self.adapter.execute_tool(
                        task.tool_name, 
                        task.args, 
                        task.cache_policy
                    ),
                    timeout=task.timeout_ms / 1000.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"Task timed out: {task.id}", extra={
                    "tool": task.tool_name,
                    "timeout_ms": task.timeout_ms
                })
                return NodeResult(
                    success=False,
                    error_code="TIMEOUT",
                    error_message=f"Task timed out after {task.timeout_ms}ms",
                    node_name=task.tool_name
                )
    
    async def execute_with_fallback(self, primary_tasks: List[ParallelTask],
                                  fallback_tasks: Optional[List[ParallelTask]] = None) -> Dict[str, NodeResult]:
        """Execute primary tasks with fallback on failure."""
        # Execute primary tasks
        primary_results = await self.execute_parallel(primary_tasks)
        
        # Check if any primary tasks failed and we have fallbacks
        if fallback_tasks:
            failed_primary = [
                task for task in primary_tasks 
                if not primary_results[task.id].success
            ]
            
            if failed_primary:
                logger.info(f"Executing {len(fallback_tasks)} fallback tasks")
                fallback_results = await self.execute_parallel(fallback_tasks)
                
                # Merge results, preferring successful fallbacks
                for fallback_task in fallback_tasks:
                    if fallback_results[fallback_task.id].success:
                        # Find corresponding primary task
                        for primary_task in failed_primary:
                            if primary_task.tool_name == fallback_task.tool_name:
                                primary_results[primary_task.id] = fallback_results[fallback_task.id]
                                break
        
        return primary_results
```

### 4. Enhanced Tool Node Integration

**File**: `src/bio_mcp/orchestrator/nodes/enhanced_tool_nodes.py`
```python
"""Enhanced tool nodes with deep MCP integration."""
from typing import Dict, Any, List, Optional
from datetime import datetime

from bio_mcp.config.logging_config import get_logger
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.adapters.mcp_adapter import MCPToolAdapter
from bio_mcp.orchestrator.execution.parallel_executor import ParallelExecutor, ParallelTask
from bio_mcp.orchestrator.middleware.rate_limiter import rate_limit
from bio_mcp.shared.clients.database import DatabaseManager
from bio_mcp.http.observability.decorators import trace_method

logger = get_logger(__name__)

class EnhancedPubMedNode:
    """Enhanced PubMed node with deep MCP integration."""
    
    def __init__(self, config: OrchestratorConfig, db_manager: DatabaseManager):
        self.config = config
        self.adapter = MCPToolAdapter(config, db_manager)
        self.executor = ParallelExecutor(self.adapter, max_concurrency=3)
    
    @trace_method("enhanced_pubmed_node")
    async def __call__(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute PubMed search with enhanced integration."""
        frame = state.get("frame", {})
        entities = frame.get("entities", {})
        filters = frame.get("filters", {})
        
        # Extract search parameters
        search_terms = self._extract_search_terms(entities)
        if not search_terms:
            return self._error_response(state, "No search terms found")
        
        # Create parallel search tasks
        search_tasks = []
        for i, term in enumerate(search_terms):
            search_tasks.append(ParallelTask(
                id=f"pubmed_search_{i}",
                tool_name="pubmed.search",
                args={
                    "term": term,
                    "limit": 20,
                    "published_within_days": filters.get("published_within_days")
                },
                cache_policy=frame.get("fetch_policy", "cache_then_network"),
                timeout_ms=self.config.node_timeout_ms
            ))
        
        # Execute searches in parallel
        search_results = await self.executor.execute_parallel(search_tasks)
        
        # Combine and deduplicate PMIDs
        all_pmids = set()
        combined_results = []
        
        for task_id, result in search_results.items():
            if result.success and result.data:
                results = result.data.get("results", [])
                for item in results:
                    pmid = item.get("pmid")
                    if pmid and pmid not in all_pmids:
                        all_pmids.add(pmid)
                        combined_results.append(item)
        
        # If we found PMIDs, fetch full details
        get_results = None
        if all_pmids and self.config.fetch_full_articles:
            get_task = ParallelTask(
                id="pubmed_get",
                tool_name="pubmed.get",
                args={"pmids": list(all_pmids)[:50]},  # Limit to 50
                cache_policy=frame.get("fetch_policy", "cache_then_network"),
                timeout_ms=self.config.node_timeout_ms * 2  # Longer timeout for bulk fetch
            )
            
            get_result_dict = await self.executor.execute_parallel([get_task])
            get_results = get_result_dict["pubmed_get"]
        
        # Calculate aggregate metrics
        total_cache_hits = sum(1 for r in search_results.values() if r.cache_hit)
        total_results = len(combined_results)
        avg_latency = sum(r.latency_ms for r in search_results.values()) / len(search_results)
        
        return {
            "pubmed_results": {
                "search_results": combined_results,
                "full_articles": get_results.data if get_results and get_results.success else None,
                "total_results": total_results,
                "search_terms": search_terms
            },
            "tool_calls_made": state["tool_calls_made"] + ["pubmed.search", "pubmed.get"] if get_results else state["tool_calls_made"] + ["pubmed.search"],
            "cache_hits": {
                **state["cache_hits"], 
                "pubmed_search": total_cache_hits > 0,
                "pubmed_get": get_results.cache_hit if get_results else False
            },
            "latencies": {
                **state["latencies"], 
                "pubmed_search": avg_latency,
                "pubmed_get": get_results.latency_ms if get_results else 0
            },
            "node_path": state["node_path"] + ["enhanced_pubmed"],
            "messages": state["messages"] + [{
                "role": "system",
                "content": f"PubMed search completed: {total_results} unique results from {len(search_terms)} search terms"
            }]
        }
    
    def _extract_search_terms(self, entities: Dict[str, Any]) -> List[str]:
        """Extract search terms from entities."""
        terms = []
        
        # Primary search terms
        if entities.get("topic"):
            terms.append(entities["topic"])
        if entities.get("indication"):
            terms.append(entities["indication"])
        
        # Company-specific searches
        if entities.get("company"):
            company_term = f"{entities['company']}[AD]"  # Search in affiliation
            terms.append(company_term)
        
        # NCT-specific searches
        if entities.get("trial_nct"):
            nct_term = f"{entities['trial_nct']}[SI]"  # Search in secondary ID
            terms.append(nct_term)
        
        return terms
    
    def _error_response(self, state: OrchestratorState, error_msg: str) -> Dict[str, Any]:
        """Generate error response."""
        return {
            "errors": state["errors"] + [{
                "node": "enhanced_pubmed",
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat()
            }],
            "node_path": state["node_path"] + ["enhanced_pubmed"]
        }

class EnhancedTrialsNode:
    """Enhanced ClinicalTrials node with advanced filtering."""
    
    def __init__(self, config: OrchestratorConfig, db_manager: DatabaseManager):
        self.config = config
        self.adapter = MCPToolAdapter(config, db_manager)
        self.executor = ParallelExecutor(self.adapter, max_concurrency=2)
    
    @trace_method("enhanced_trials_node")
    async def __call__(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute ClinicalTrials search with enhanced filtering."""
        frame = state.get("frame", {})
        entities = frame.get("entities", {})
        filters = frame.get("filters", {})
        
        # Create search task
        search_task = ParallelTask(
            id="ctgov_search",
            tool_name="clinicaltrials.search",
            args={
                "condition": entities.get("indication"),
                "sponsor": entities.get("company"),
                "nct_id": entities.get("trial_nct"),
                "phase": filters.get("phase"),
                "status": filters.get("status"),
                "limit": 100  # Higher limit for trials
            },
            cache_policy=frame.get("fetch_policy", "cache_then_network"),
            timeout_ms=self.config.node_timeout_ms * 2  # Trials API can be slower
        )
        
        # Execute search
        results = await self.executor.execute_parallel([search_task])
        search_result = results["ctgov_search"]
        
        if not search_result.success:
            return {
                "errors": state["errors"] + [{
                    "node": "enhanced_trials",
                    "error": search_result.error_message,
                    "timestamp": datetime.utcnow().isoformat()
                }],
                "node_path": state["node_path"] + ["enhanced_trials"]
            }
        
        # Post-process results
        trials_data = search_result.data
        processed_trials = self._process_trials(trials_data, filters)
        
        return {
            "ctgov_results": {
                "trials": processed_trials,
                "total_found": len(trials_data.get("results", [])),
                "filtered_count": len(processed_trials),
                "filters_applied": filters
            },
            "tool_calls_made": state["tool_calls_made"] + ["clinicaltrials.search"],
            "cache_hits": {**state["cache_hits"], "ctgov_search": search_result.cache_hit},
            "latencies": {**state["latencies"], "ctgov_search": search_result.latency_ms},
            "node_path": state["node_path"] + ["enhanced_trials"],
            "messages": state["messages"] + [{
                "role": "system",
                "content": f"ClinicalTrials search: {len(processed_trials)} relevant trials found"
            }]
        }
    
    def _process_trials(self, trials_data: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Post-process and filter trials data."""
        results = trials_data.get("results", [])
        
        # Apply additional filtering logic
        processed = []
        for trial in results:
            # Quality filtering
            if self._is_quality_trial(trial):
                # Enhance with derived fields
                enhanced_trial = {
                    **trial,
                    "relevance_score": self._calculate_relevance_score(trial, filters),
                    "enrollment_speed": self._estimate_enrollment_speed(trial),
                    "completion_likelihood": self._estimate_completion_likelihood(trial)
                }
                processed.append(enhanced_trial)
        
        # Sort by relevance score
        processed.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        return processed
    
    def _is_quality_trial(self, trial: Dict[str, Any]) -> bool:
        """Filter for quality trials."""
        # Basic quality checks
        if not trial.get("title") or not trial.get("nct_id"):
            return False
        
        # Skip withdrawn or terminated trials unless specifically requested
        status = trial.get("status", "").lower()
        if "withdrawn" in status or "suspended" in status:
            return False
        
        return True
    
    def _calculate_relevance_score(self, trial: Dict[str, Any], filters: Dict[str, Any]) -> float:
        """Calculate relevance score for trial."""
        score = 1.0
        
        # Phase matching bonus
        trial_phase = trial.get("phase", "")
        requested_phases = filters.get("phase", [])
        if requested_phases and any(p in trial_phase for p in requested_phases):
            score += 2.0
        
        # Status matching bonus
        trial_status = trial.get("status", "")
        requested_statuses = filters.get("status", [])
        if requested_statuses and any(s.lower() in trial_status.lower() for s in requested_statuses):
            score += 1.5
        
        # Enrollment size bonus (larger trials often more significant)
        enrollment = trial.get("enrollment", 0)
        if enrollment > 100:
            score += 0.5
        if enrollment > 500:
            score += 0.5
        
        return score
    
    def _estimate_enrollment_speed(self, trial: Dict[str, Any]) -> str:
        """Estimate enrollment speed."""
        # This is a placeholder - could be enhanced with historical data
        enrollment = trial.get("enrollment", 0)
        if enrollment < 50:
            return "fast"
        elif enrollment < 200:
            return "moderate"
        else:
            return "slow"
    
    def _estimate_completion_likelihood(self, trial: Dict[str, Any]) -> str:
        """Estimate completion likelihood."""
        # This is a placeholder - could be enhanced with ML model
        status = trial.get("status", "").lower()
        if "completed" in status:
            return "completed"
        elif "active" in status:
            return "high"
        elif "recruiting" in status:
            return "moderate"
        else:
            return "low"

# Factory functions
def create_enhanced_pubmed_node(config: OrchestratorConfig, db_manager: DatabaseManager):
    """Factory function for enhanced PubMed node."""
    return EnhancedPubMedNode(config, db_manager)

def create_enhanced_trials_node(config: OrchestratorConfig, db_manager: DatabaseManager):
    """Factory function for enhanced ClinicalTrials node."""
    return EnhancedTrialsNode(config, db_manager)
```

## Testing Strategy

### Unit Tests

**File**: `tests/unit/orchestrator/adapters/test_mcp_adapter.py`
```python
"""Test MCP tool adapter."""
import pytest
from unittest.mock import Mock, AsyncMock
from bio_mcp.orchestrator.adapters.mcp_adapter import MCPToolAdapter
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.shared.clients.database import DatabaseManager

@pytest.mark.asyncio
async def test_mcp_adapter_execute_tool():
    """Test MCP tool execution."""
    config = OrchestratorConfig()
    db_manager = Mock()
    adapter = MCPToolAdapter(config, db_manager)
    
    # Mock tool
    mock_tool = Mock()
    mock_tool.execute = AsyncMock(return_value={"results": [{"id": "test"}]})
    adapter._tools = {"test.tool": mock_tool}
    
    result = await adapter.execute_tool("test.tool", {"arg": "value"})
    
    assert result.success
    assert result.data["results"][0]["id"] == "test"
    mock_tool.execute.assert_called_once_with({"arg": "value"})

@pytest.mark.asyncio
async def test_mcp_adapter_cache_hit():
    """Test cache hit scenario."""
    config = OrchestratorConfig()
    db_manager = Mock()
    adapter = MCPToolAdapter(config, db_manager)
    
    # Mock cache
    adapter.cache = Mock()
    adapter.cache.get = AsyncMock(return_value={"results": [{"id": "cached"}]})
    
    result = await adapter.execute_tool("pubmed.search", {"term": "test"})
    
    assert result.success
    assert result.cache_hit
    assert result.data["results"][0]["id"] == "cached"
```

### Integration Tests

**File**: `tests/integration/orchestrator/test_enhanced_integration.py`
```python
"""Integration tests for enhanced tool nodes."""
import pytest
from bio_mcp.orchestrator.nodes.enhanced_tool_nodes import EnhancedPubMedNode
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import OrchestratorState
from tests.integration.database.conftest import clean_db, postgres_container

@pytest.mark.integration
@pytest.mark.asyncio
async def test_enhanced_pubmed_integration(clean_db):
    """Test enhanced PubMed node with real database."""
    config = OrchestratorConfig()
    node = EnhancedPubMedNode(config, clean_db)
    
    state = OrchestratorState(
        query="diabetes research",
        frame={
            "entities": {"topic": "diabetes"},
            "filters": {"published_within_days": 365},
            "fetch_policy": "cache_then_network"
        },
        config={},
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
    assert len(result["tool_calls_made"]) > 0
    assert "enhanced_pubmed" in result["node_path"]
```

## Acceptance Criteria
- [ ] MCPToolAdapter successfully integrates all existing MCP tools
- [ ] Cache-then-network pattern works correctly with Redis cache
- [ ] Rate limiting prevents API overload
- [ ] Parallel execution improves performance while respecting rate limits
- [ ] Database-first fallback pattern reduces API calls
- [ ] Tool result normalization provides consistent data formats
- [ ] Enhanced nodes provide better result quality and filtering
- [ ] Error handling gracefully handles tool failures
- [ ] Integration tests validate real MCP tool execution
- [ ] Performance metrics show improved efficiency over sequential execution

## Files Created/Modified
- `src/bio_mcp/orchestrator/adapters/mcp_adapter.py` - MCP tool adapter
- `src/bio_mcp/orchestrator/middleware/rate_limiter.py` - Rate limiting
- `src/bio_mcp/orchestrator/execution/parallel_executor.py` - Parallel execution
- `src/bio_mcp/orchestrator/nodes/enhanced_tool_nodes.py` - Enhanced tool nodes
- `tests/unit/orchestrator/adapters/test_mcp_adapter.py` - Adapter tests
- `tests/integration/orchestrator/test_enhanced_integration.py` - Integration tests

## Next Milestone
After completion, proceed to **M3 — LangGraph State Management** which will focus on advanced state persistence, error recovery, and flow control mechanisms.
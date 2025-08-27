"""Enhanced tool nodes with deep MCP integration."""

from datetime import UTC, datetime
from typing import Any

from bio_mcp.orchestrator.adapters.mcp_adapter import MCPToolAdapter
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.execution.parallel_executor import ParallelExecutor
from bio_mcp.orchestrator.middleware.rate_limiter import TokenBucketRateLimiter
from bio_mcp.orchestrator.types import NodeResult, OrchestratorState


class EnhancedPubMedNode:
    """Enhanced PubMed node with deep MCP integration."""

    def __init__(self, config: OrchestratorConfig, db_manager: Any):
        """Initialize the enhanced PubMed node."""
        self.config = config
        self.adapter = MCPToolAdapter(config, db_manager)

        # Create rate limiter for PubMed (2 requests per second, capacity 5)
        rate_limiter = TokenBucketRateLimiter(capacity=5, refill_rate=2.0)
        self.executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=3)

    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Execute PubMed search with enhanced integration."""
        frame = state.get("frame", {})
        entities = frame.get("entities", {})
        filters = frame.get("filters", {})

        # Extract search terms
        search_terms = self._extract_search_terms(entities)
        if not search_terms:
            return self._error_response(state, "No search terms found")

        # Create parallel search tasks
        search_tasks = []
        for i, term in enumerate(search_terms):
            task = {
                "func": self._search_pubmed,
                "args": (term, filters),
                "kwargs": {},
                "token_cost": 1,
            }
            search_tasks.append(task)

        # Execute searches in parallel
        search_results = await self.executor.execute_parallel(search_tasks)

        # Combine and deduplicate PMIDs
        all_pmids = set()
        combined_results = []

        for result in search_results:
            if result.success and result.data:
                results = result.data.get("results", [])
                for item in results:
                    pmid = item.get("pmid")
                    if pmid and pmid not in all_pmids:
                        all_pmids.add(pmid)
                        combined_results.append(item)

        # Calculate aggregate metrics
        total_cache_hits = sum(1 for r in search_results if r.cache_hit)
        total_results = len(combined_results)
        avg_latency = (
            sum(r.latency_ms for r in search_results) / len(search_results)
            if search_results
            else 0
        )

        # Update state
        return {
            "pubmed_results": {
                "search_results": combined_results,
                "total_results": total_results,
                "search_terms": search_terms,
            },
            "tool_calls_made": [*state.get("tool_calls_made", []), "pubmed.search"],
            "cache_hits": {
                **state.get("cache_hits", {}),
                "pubmed_search": total_cache_hits > 0,
            },
            "latencies": {
                **state.get("latencies", {}),
                "pubmed_search": avg_latency,
            },
            "node_path": [*state.get("node_path", []), "enhanced_pubmed"],
            "messages": [
                *state.get("messages", []),
                {
                    "role": "system",
                    "content": f"PubMed search completed: {total_results} unique results from {len(search_terms)} search terms",
                },
            ],
        }

    async def _search_pubmed(self, term: str, filters: dict[str, Any]) -> NodeResult:
        """Execute a single PubMed search."""
        args = {
            "term": term,
            "limit": 20,
        }

        # Add filters if present
        if filters.get("published_within_days"):
            args["published_within_days"] = filters["published_within_days"]

        return await self.adapter.execute_tool("pubmed.search", args)

    def _extract_search_terms(self, entities: dict[str, Any]) -> list[str]:
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

    def _error_response(
        self, state: OrchestratorState, error_msg: str
    ) -> dict[str, Any]:
        """Generate error response."""
        return {
            "error": error_msg,
            "errors": [
                *state.get("errors", []),
                {
                    "node": "enhanced_pubmed",
                    "error": error_msg,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            ],
            "node_path": [*state.get("node_path", []), "enhanced_pubmed"],
        }


class EnhancedTrialsNode:
    """Enhanced ClinicalTrials node with advanced filtering."""

    def __init__(self, config: OrchestratorConfig, db_manager: Any):
        """Initialize the enhanced trials node."""
        self.config = config
        self.adapter = MCPToolAdapter(config, db_manager)

        # Create rate limiter for ClinicalTrials (2 requests per second, capacity 3)
        rate_limiter = TokenBucketRateLimiter(capacity=3, refill_rate=2.0)
        self.executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=2)

    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Execute ClinicalTrials search with enhanced filtering."""
        frame = state.get("frame", {})
        entities = frame.get("entities", {})
        filters = frame.get("filters", {})

        # Extract search terms
        search_terms = self._extract_search_terms(entities)
        if not search_terms:
            return self._error_response(state, "No search terms found")

        # Create search task
        search_task = {
            "func": self._search_trials,
            "args": (entities, filters),
            "kwargs": {},
            "token_cost": 2,  # Trials searches are more expensive
        }

        # Execute search
        search_results = await self.executor.execute_parallel([search_task])
        search_result = search_results[0]

        if not search_result.success:
            return self._error_response(state, search_result.error_message)

        # Post-process results
        trials_data = search_result.data
        processed_trials = self._process_trials(trials_data, filters)

        # Update state
        return {
            "ctgov_results": {
                "trials": processed_trials,
                "total_found": len(trials_data.get("results", [])),
                "filtered_count": len(processed_trials),
                "filters_applied": filters,
                "search_terms": search_terms,
            },
            "tool_calls_made": [
                *state.get("tool_calls_made", []),
                "clinicaltrials.search",
            ],
            "cache_hits": {
                **state.get("cache_hits", {}),
                "ctgov_search": search_result.cache_hit,
            },
            "latencies": {
                **state.get("latencies", {}),
                "ctgov_search": search_result.latency_ms,
            },
            "node_path": [*state.get("node_path", []), "enhanced_trials"],
            "messages": [
                *state.get("messages", []),
                {
                    "role": "system",
                    "content": f"ClinicalTrials search: {len(processed_trials)} relevant trials found",
                },
            ],
        }

    async def _search_trials(
        self, entities: dict[str, Any], filters: dict[str, Any]
    ) -> NodeResult:
        """Execute trials search."""
        args = {
            "limit": 100  # Higher limit for trials
        }

        # Add entity-based parameters
        if entities.get("indication"):
            args["condition"] = entities["indication"]
        if entities.get("company"):
            args["sponsor"] = entities["company"]
        if entities.get("trial_nct"):
            args["nct_id"] = entities["trial_nct"]

        # Add filters
        if filters.get("phase"):
            args["phase"] = filters["phase"]
        if filters.get("status"):
            args["status"] = filters["status"]

        return await self.adapter.execute_tool("clinicaltrials.search", args)

    def _extract_search_terms(self, entities: dict[str, Any]) -> list[str]:
        """Extract search terms from entities."""
        terms = []

        # Primary search terms
        if entities.get("indication"):
            terms.append(entities["indication"])
        if entities.get("company"):
            terms.append(entities["company"])
        if entities.get("trial_nct"):
            terms.append(entities["trial_nct"])

        return terms

    def _process_trials(
        self, trials_data: dict[str, Any], filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
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
                    "completion_likelihood": self._estimate_completion_likelihood(
                        trial
                    ),
                }
                processed.append(enhanced_trial)

        # Sort by relevance score
        processed.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        return processed

    def _is_quality_trial(self, trial: dict[str, Any]) -> bool:
        """Filter for quality trials."""
        # Basic quality checks
        if not trial.get("title") or not trial.get("nct_id"):
            return False

        # Skip withdrawn or terminated trials unless specifically requested
        status = trial.get("status", "").lower()
        if "withdrawn" in status or "suspended" in status:
            return False

        return True

    def _calculate_relevance_score(
        self, trial: dict[str, Any], filters: dict[str, Any]
    ) -> float:
        """Calculate relevance score for trial."""
        score = 1.0

        # Phase matching bonus
        trial_phase = trial.get("phase", "").lower()
        filter_phase = filters.get("phase", "").lower()
        if filter_phase and filter_phase in trial_phase:
            score += 0.5

        # Status preference (active trials score higher)
        status = trial.get("status", "").lower()
        if "recruiting" in status or "active" in status:
            score += 0.3

        # Recent trials get bonus
        start_date = trial.get("start_date")
        if start_date and "2020" in str(start_date):  # Recent trials
            score += 0.2

        return score

    def _estimate_enrollment_speed(self, trial: dict[str, Any]) -> str:
        """Estimate enrollment speed."""
        # Simple heuristic based on enrollment vs target
        enrollment = trial.get("enrollment", {})
        if isinstance(enrollment, dict):
            actual = enrollment.get("actual", 0)
            target = enrollment.get("target", 1)
            ratio = actual / target if target > 0 else 0

            if ratio > 0.8:
                return "fast"
            elif ratio > 0.4:
                return "moderate"
            else:
                return "slow"

        return "unknown"

    def _estimate_completion_likelihood(self, trial: dict[str, Any]) -> str:
        """Estimate completion likelihood."""
        # Simple heuristic based on status and phase
        status = trial.get("status", "").lower()
        phase = trial.get("phase", "").lower()

        if "completed" in status:
            return "high"
        elif "recruiting" in status and ("phase 3" in phase or "phase iii" in phase):
            return "high"
        elif "active" in status:
            return "moderate"
        else:
            return "low"

    def _error_response(
        self, state: OrchestratorState, error_msg: str
    ) -> dict[str, Any]:
        """Generate error response."""
        return {
            "error": error_msg,
            "errors": [
                *state.get("errors", []),
                {
                    "node": "enhanced_trials",
                    "error": error_msg,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            ],
            "node_path": [*state.get("node_path", []), "enhanced_trials"],
        }


class EnhancedRAGNode:
    """Enhanced RAG search node with advanced querying."""

    def __init__(self, config: OrchestratorConfig, db_manager: Any):
        """Initialize the enhanced RAG node."""
        self.config = config
        self.adapter = MCPToolAdapter(config, db_manager)

        # Create rate limiter for RAG (3 requests per second, capacity 8)
        rate_limiter = TokenBucketRateLimiter(capacity=8, refill_rate=3.0)
        self.executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=2)

    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Execute RAG search with enhanced querying."""
        query = state.get("normalized_query") or state.get("query", "")
        frame = state.get("frame", {})
        filters = frame.get("filters", {})

        if not query:
            return self._error_response(state, "No query found for RAG search")

        # Create search task
        search_task = {
            "func": self._search_rag,
            "args": (query, filters),
            "kwargs": {},
            "token_cost": 1,
        }

        # Execute search
        search_results = await self.executor.execute_parallel([search_task])
        search_result = search_results[0]

        if not search_result.success:
            return self._error_response(state, search_result.error_message)

        # Post-process results
        rag_data = search_result.data
        processed_results = self._process_rag_results(rag_data, query)

        # Update state
        return {
            "rag_results": {
                "documents": processed_results,
                "total_found": len(rag_data.get("results", [])),
                "filtered_count": len(processed_results),
                "query": query,
            },
            "tool_calls_made": [*state.get("tool_calls_made", []), "rag.search"],
            "cache_hits": {
                **state.get("cache_hits", {}),
                "rag_search": search_result.cache_hit,
            },
            "latencies": {
                **state.get("latencies", {}),
                "rag_search": search_result.latency_ms,
            },
            "node_path": [*state.get("node_path", []), "enhanced_rag"],
            "messages": [
                *state.get("messages", []),
                {
                    "role": "system",
                    "content": f"RAG search: {len(processed_results)} relevant documents found",
                },
            ],
        }

    async def _search_rag(self, query: str, filters: dict[str, Any]) -> NodeResult:
        """Execute RAG search."""
        args = {
            "query": query,
            "limit": 10,
        }

        # Add filters if present
        if filters:
            args["filters"] = filters

        return await self.adapter.execute_tool("rag.search", args)

    def _process_rag_results(
        self, rag_data: dict[str, Any], query: str
    ) -> list[dict[str, Any]]:
        """Post-process RAG search results."""
        results = rag_data.get("results", [])

        # Enhance each result with relevance scoring
        processed = []
        for doc in results:
            enhanced_doc = {
                **doc,
                "query_relevance": self._calculate_query_relevance(doc, query),
                "document_quality": self._assess_document_quality(doc),
            }
            processed.append(enhanced_doc)

        # Sort by relevance and quality
        processed.sort(
            key=lambda x: (
                x.get("query_relevance", 0.0) + x.get("document_quality", 0.0)
            ),
            reverse=True,
        )

        return processed

    def _calculate_query_relevance(self, doc: dict[str, Any], query: str) -> float:
        """Calculate query relevance score."""
        # Use existing score if available, otherwise simple text matching
        if "score" in doc:
            return min(1.0, max(0.0, doc["score"]))

        # Simple keyword matching fallback
        title = doc.get("title", "").lower()
        content = doc.get("snippet", "").lower()
        query_words = query.lower().split()

        matches = 0
        for word in query_words:
            if word in title:
                matches += 2  # Title matches worth more
            elif word in content:
                matches += 1

        # Normalize by query length
        return min(1.0, matches / len(query_words)) if query_words else 0.0

    def _assess_document_quality(self, doc: dict[str, Any]) -> float:
        """Assess document quality."""
        score = 0.5  # Base score

        # Prefer documents with titles
        if doc.get("title"):
            score += 0.2

        # Prefer documents with abstracts/snippets
        snippet = doc.get("snippet", "")
        if snippet and len(snippet) > 100:
            score += 0.2

        # Prefer recent documents if date available
        if doc.get("date"):
            # Simple heuristic - assume recent is better
            score += 0.1

        return min(1.0, score)

    def _error_response(
        self, state: OrchestratorState, error_msg: str
    ) -> dict[str, Any]:
        """Generate error response."""
        return {
            "error": error_msg,
            "errors": [
                *state.get("errors", []),
                {
                    "node": "enhanced_rag",
                    "error": error_msg,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            ],
            "node_path": [*state.get("node_path", []), "enhanced_rag"],
        }


# Factory functions
def create_enhanced_pubmed_search_node(
    config: OrchestratorConfig, db_manager: Any = None
):
    """Factory function for enhanced PubMed node."""
    return EnhancedPubMedNode(config, db_manager)


def create_enhanced_ctgov_search_node(
    config: OrchestratorConfig, db_manager: Any = None
):
    """Factory function for enhanced ClinicalTrials node."""
    return EnhancedTrialsNode(config, db_manager)


def create_enhanced_rag_search_node(config: OrchestratorConfig, db_manager: Any = None):
    """Factory function for enhanced RAG search node."""
    return EnhancedRAGNode(config, db_manager)

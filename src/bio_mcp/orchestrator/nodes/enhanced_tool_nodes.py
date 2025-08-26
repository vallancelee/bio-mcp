"""Enhanced tool nodes with deep MCP integration."""
from datetime import UTC, datetime
from typing import Any

from bio_mcp.orchestrator.adapters.mcp_adapter import MCPToolAdapter
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.execution.parallel_executor import ParallelExecutor
from bio_mcp.orchestrator.middleware.rate_limiter import TokenBucketRateLimiter
from bio_mcp.orchestrator.state import NodeResult, OrchestratorState


class EnhancedPubMedNode:
    """Enhanced PubMed node with deep MCP integration."""
    
    def __init__(self, config: OrchestratorConfig, db_manager: Any):
        """Initialize the enhanced PubMed node.
        
        Args:
            config: Orchestrator configuration
            db_manager: Database manager
        """
        self.config = config
        self.adapter = MCPToolAdapter(config, db_manager)
        
        # Create rate limiter for PubMed (2 requests per second, capacity 5)
        rate_limiter = TokenBucketRateLimiter(capacity=5, refill_rate=2.0)
        self.executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=3)
    
    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Execute PubMed search with enhanced integration.
        
        Args:
            state: Current orchestrator state
            
        Returns:
            Updated state dictionary
        """
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
                "token_cost": 1
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
        
        # TODO: Implement full article fetching when pubmed.get tool is available
        
        # Calculate aggregate metrics
        total_cache_hits = sum(1 for r in search_results if r.cache_hit)
        total_results = len(combined_results)
        avg_latency = sum(r.latency_ms for r in search_results) / len(search_results) if search_results else 0
        
        # Update state
        updated_state = dict(state)
        updated_state.update({
            "pubmed_results": {
                "search_results": combined_results,
                "total_results": total_results,
                "search_terms": search_terms
            },
            "tool_calls_made": state.get("tool_calls_made", []) + ["pubmed.search"],
            "cache_hits": {
                **state.get("cache_hits", {}), 
                "pubmed_search": total_cache_hits > 0
            },
            "latencies": {
                **state.get("latencies", {}), 
                "pubmed_search": avg_latency
            },
            "node_path": state.get("node_path", []) + ["enhanced_pubmed"],
            "messages": state.get("messages", []) + [{
                "role": "system",
                "content": f"PubMed search completed: {total_results} unique results from {len(search_terms)} search terms"
            }]
        })
        
        return updated_state
    
    async def _search_pubmed(self, term: str, filters: dict[str, Any]) -> NodeResult:
        """Execute a single PubMed search.
        
        Args:
            term: Search term
            filters: Search filters
            
        Returns:
            NodeResult with search results
        """
        args = {
            "term": term,
            "limit": 20,
        }
        
        # Add filters if present
        if filters.get("published_within_days"):
            args["published_within_days"] = filters["published_within_days"]
        
        return await self.adapter.execute_tool("pubmed.search", args)
    
    
    def _extract_search_terms(self, entities: dict[str, Any]) -> list[str]:
        """Extract search terms from entities.
        
        Args:
            entities: Extracted entities from frame
            
        Returns:
            List of search terms
        """
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
    
    def _error_response(self, state: OrchestratorState, error_msg: str) -> dict[str, Any]:
        """Generate error response.
        
        Args:
            state: Current state
            error_msg: Error message
            
        Returns:
            Updated state with error
        """
        updated_state = dict(state)
        updated_state.update({
            "error": error_msg,
            "errors": state.get("errors", []) + [{
                "node": "enhanced_pubmed",
                "error": error_msg,
                "timestamp": datetime.now(UTC).isoformat()
            }],
            "node_path": state.get("node_path", []) + ["enhanced_pubmed"]
        })
        return updated_state


class EnhancedTrialsNode:
    """Enhanced ClinicalTrials node with advanced filtering."""
    
    def __init__(self, config: OrchestratorConfig, db_manager: Any):
        """Initialize the enhanced trials node.
        
        Args:
            config: Orchestrator configuration
            db_manager: Database manager
        """
        self.config = config
        self.adapter = MCPToolAdapter(config, db_manager)
        
        # Create rate limiter for ClinicalTrials (2 requests per second, capacity 3)
        rate_limiter = TokenBucketRateLimiter(capacity=3, refill_rate=2.0)
        self.executor = ParallelExecutor(rate_limiter=rate_limiter, max_concurrency=2)
    
    async def __call__(self, state: OrchestratorState) -> dict[str, Any]:
        """Execute ClinicalTrials search with enhanced filtering.
        
        Args:
            state: Current orchestrator state
            
        Returns:
            Updated state dictionary
        """
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
            "token_cost": 2  # Trials searches are more expensive
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
        updated_state = dict(state)
        updated_state.update({
            "trials_results": {
                "trials": processed_trials,
                "total_found": len(trials_data.get("results", [])),
                "filtered_count": len(processed_trials),
                "filters_applied": filters,
                "search_terms": search_terms
            },
            "tool_calls_made": state.get("tool_calls_made", []) + ["clinicaltrials.search"],
            "cache_hits": {
                **state.get("cache_hits", {}), 
                "trials_search": search_result.cache_hit
            },
            "latencies": {
                **state.get("latencies", {}), 
                "trials_search": search_result.latency_ms
            },
            "node_path": state.get("node_path", []) + ["enhanced_trials"],
            "messages": state.get("messages", []) + [{
                "role": "system",
                "content": f"ClinicalTrials search: {len(processed_trials)} relevant trials found"
            }]
        })
        
        return updated_state
    
    async def _search_trials(self, entities: dict[str, Any], filters: dict[str, Any]) -> NodeResult:
        """Execute trials search.
        
        Args:
            entities: Extracted entities
            filters: Search filters
            
        Returns:
            NodeResult with search results
        """
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
        """Extract search terms from entities.
        
        Args:
            entities: Extracted entities from frame
            
        Returns:
            List of search terms
        """
        terms = []
        
        # Primary search terms
        if entities.get("indication"):
            terms.append(entities["indication"])
        if entities.get("company"):
            terms.append(entities["company"])
        if entities.get("trial_nct"):
            terms.append(entities["trial_nct"])
        
        return terms
    
    def _process_trials(self, trials_data: dict[str, Any], filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Post-process and filter trials data.
        
        Args:
            trials_data: Raw trials data from search
            filters: Applied filters
            
        Returns:
            List of processed and filtered trials
        """
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
    
    def _is_quality_trial(self, trial: dict[str, Any]) -> bool:
        """Filter for quality trials.
        
        Args:
            trial: Trial data
            
        Returns:
            True if trial meets quality criteria
        """
        # Basic quality checks
        if not trial.get("title") or not trial.get("nct_id"):
            return False
        
        # Skip withdrawn or terminated trials unless specifically requested
        status = trial.get("status", "").lower()
        if "withdrawn" in status or "suspended" in status:
            return False
        
        return True
    
    def _calculate_relevance_score(self, trial: dict[str, Any], filters: dict[str, Any]) -> float:
        """Calculate relevance score for trial.
        
        Args:
            trial: Trial data
            filters: Applied filters
            
        Returns:
            Relevance score (higher is better)
        """
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
        """Estimate enrollment speed.
        
        Args:
            trial: Trial data
            
        Returns:
            Estimated enrollment speed category
        """
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
        """Estimate completion likelihood.
        
        Args:
            trial: Trial data
            
        Returns:
            Estimated completion likelihood
        """
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
    
    def _error_response(self, state: OrchestratorState, error_msg: str) -> dict[str, Any]:
        """Generate error response.
        
        Args:
            state: Current state
            error_msg: Error message
            
        Returns:
            Updated state with error
        """
        updated_state = dict(state)
        updated_state.update({
            "error": error_msg,
            "errors": state.get("errors", []) + [{
                "node": "enhanced_trials",
                "error": error_msg,
                "timestamp": datetime.now(UTC).isoformat()
            }],
            "node_path": state.get("node_path", []) + ["enhanced_trials"]
        })
        return updated_state
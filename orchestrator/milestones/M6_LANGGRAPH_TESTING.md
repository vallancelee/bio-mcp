# M6 — LangGraph Comprehensive Testing (PARTIAL 🔄)

## Current Status: PARTIAL 🔄
Basic testing exists but comprehensive coverage needs expansion.

**COMPLETED:**
- ✅ Unit tests exist for individual nodes (`tests/unit/orchestrator/`)
- ✅ Integration tests for graph execution (`tests/integration/orchestrator/test_node_integration.py`)
- ✅ LLM parse node integration tests
- ✅ Synthesis and M2/M3 integration tests
- ✅ Basic end-to-end orchestrator flow testing

**PENDING (Next Phase):**
- ⏳ Performance benchmarking and load testing
- ⏳ Failure scenario and error recovery testing
- ⏳ ClinicalTrials and RAG node testing (when implemented)
- ⏳ Streaming results testing
- ⏳ Cache behavior and rate limiting testing

## Objective
Implement comprehensive testing for the complete LangGraph orchestrator system including unit tests for all components, integration tests with real services, end-to-end testing scenarios, performance benchmarks, and failure scenario testing. Focus on ensuring reliability, correctness, and maintainability of the orchestrator.

## Dependencies (Existing Bio-MCP Components)
- **M1-M5 LangGraph**: Complete orchestrator implementation with observability
- **Testing Infrastructure**: `tests/` directory structure and existing test patterns
- **Database Testing**: `tests/integration/database/conftest.py` - Test database setup
- **MCP Tools**: All existing MCP tool implementations
- **Test Containers**: Existing testcontainers setup for integration testing

## Core Testing Components

### 1. Unit Test Suite

**File**: `tests/unit/orchestrator/test_complete_orchestrator.py`
```python
"""Comprehensive unit tests for orchestrator components."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import asyncio

from bio_mcp.orchestrator.graph_builder import build_orchestrator_graph
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.nodes.frame_node import create_frame_parser_node
from bio_mcp.orchestrator.nodes.router_node import create_router_node
from bio_mcp.orchestrator.synthesis.synthesizer import AdvancedSynthesizer
from bio_mcp.shared.clients.database import DatabaseManager

class TestOrchestratorUnits:
    """Unit tests for orchestrator components."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.config = OrchestratorConfig()
        self.config.default_budget_ms = 5000
        self.mock_db = Mock(spec=DatabaseManager)
    
    @pytest.mark.asyncio
    async def test_frame_parser_node_success(self):
        """Test successful frame parsing."""
        frame_node = create_frame_parser_node(self.config)
        
        state = OrchestratorState(
            query="recent publications on diabetes treatment",
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
        
        result = await frame_node(state)
        
        # Verify frame parsing
        assert "frame" in result
        assert result["frame"]["intent"] == "recent_pubs_by_topic"
        assert "diabetes" in result["frame"]["entities"]["topic"].lower()
        assert "parse_frame" in result["node_path"]
        assert "parse_frame" in result["latencies"]
    
    @pytest.mark.asyncio
    async def test_frame_parser_node_error_handling(self):
        """Test frame parser error handling."""
        frame_node = create_frame_parser_node(self.config)
        
        # Test with empty query
        state = OrchestratorState(
            query="",
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
        
        # Mock frame parser to raise exception
        with patch('bio_mcp.orchestrator.frame.FrameParser.parse_frame') as mock_parser:
            mock_parser.side_effect = Exception("Parse error")
            
            result = await frame_node(state)
            
            # Verify error handling
            assert len(result["errors"]) > 0
            assert result["errors"][0]["node"] == "parse_frame"
            assert "Parse error" in result["errors"][0]["error"]
    
    @pytest.mark.asyncio 
    async def test_router_node_intent_routing(self):
        """Test router node intent-based routing."""
        router_node = create_router_node(self.config)
        
        test_cases = [
            {
                "intent": "recent_pubs_by_topic",
                "expected": "pubmed_search"
            },
            {
                "intent": "indication_phase_trials", 
                "expected": "ctgov_search"
            },
            {
                "intent": "trials_with_pubs",
                "expected": "ctgov_search|pubmed_search"
            }
        ]
        
        for test_case in test_cases:
            state = OrchestratorState(
                query="test query",
                config={},
                frame={"intent": test_case["intent"]},
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
            
            result = await router_node(state)
            
            assert result["routing_decision"] == test_case["expected"]
            assert "router" in result["node_path"]
    
    @pytest.mark.asyncio
    async def test_synthesizer_comprehensive_answer(self):
        """Test comprehensive answer synthesis."""
        synthesizer = AdvancedSynthesizer(self.config)
        
        # Mock state with rich results
        state = OrchestratorState(
            query="diabetes research trends",
            config={},
            frame={"intent": "recent_pubs_by_topic", "entities": {"topic": "diabetes"}},
            routing_decision="pubmed_search",
            pubmed_results={
                "results": [
                    {
                        "pmid": "12345678",
                        "title": "Advanced Diabetes Treatment Methods",
                        "authors": ["Smith, J.", "Doe, A."],
                        "journal": "Nature Medicine",
                        "year": 2023
                    },
                    {
                        "pmid": "87654321", 
                        "title": "Diabetes Prevention Strategies",
                        "authors": ["Johnson, B.", "Wilson, C."],
                        "journal": "The Lancet",
                        "year": 2023
                    }
                ]
            },
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=["pubmed_search"],
            cache_hits={"pubmed_search": False},
            latencies={"parse_frame": 50, "router": 10, "pubmed_search": 800, "synthesizer": 0},
            errors=[],
            node_path=["parse_frame", "router", "pubmed_search"],
            answer=None,
            checkpoint_id=None,
            messages=[]
        )
        
        result = await synthesizer.synthesize(state)
        
        # Verify comprehensive answer
        assert "answer" in result
        assert "checkpoint_id" in result
        assert "citations" in result
        assert len(result["citations"]) == 2
        
        # Verify answer content
        answer = result["answer"]
        assert "diabetes" in answer.lower()
        assert "Nature Medicine" in answer
        assert "The Lancet" in answer
        assert "PMID" in answer
        
        # Verify citations
        citations = result["citations"]
        assert any(c["pmid"] == "12345678" for c in citations)
        assert any(c["pmid"] == "87654321" for c in citations)
        
        # Verify quality metrics
        assert "quality_metrics" in result
        quality = result["quality_metrics"]
        assert quality["overall_score"] > 0
    
    @pytest.mark.asyncio
    async def test_synthesizer_partial_results(self):
        """Test synthesis with partial results (some sources failed)."""
        synthesizer = AdvancedSynthesizer(self.config)
        
        # State with errors and partial results
        state = OrchestratorState(
            query="clinical trials for alzheimer",
            config={},
            frame={"intent": "trials_with_pubs"},
            routing_decision="ctgov_search|pubmed_search",
            pubmed_results=None,  # Failed
            ctgov_results={
                "results": [
                    {
                        "nct_id": "NCT12345678",
                        "title": "Phase 3 Alzheimer Drug Trial",
                        "phase": "Phase 3",
                        "status": "Recruiting",
                        "sponsor": "Pharma Corp"
                    }
                ]
            },
            rag_results=None,
            tool_calls_made=["ctgov_search", "pubmed_search"],
            cache_hits={"ctgov_search": False, "pubmed_search": False},
            latencies={"ctgov_search": 1200, "pubmed_search": 0},
            errors=[
                {
                    "node": "pubmed_search",
                    "error": "API timeout",
                    "timestamp": datetime.utcnow().isoformat()
                }
            ],
            node_path=["parse_frame", "router", "ctgov_search", "pubmed_search"],
            answer=None,
            checkpoint_id=None,
            messages=[]
        )
        
        result = await synthesizer.synthesize(state)
        
        # Should still generate answer with available data
        assert "answer" in result
        assert "alzheimer" in result["answer"].lower()
        assert "NCT12345678" in result["answer"]
        
        # Quality score should reflect partial nature
        quality = result["quality_metrics"]
        assert quality["completeness_score"] < 1.0  # Not complete due to missing PubMed
    
    @pytest.mark.asyncio
    async def test_synthesizer_empty_results(self):
        """Test synthesis with no results."""
        synthesizer = AdvancedSynthesizer(self.config)
        
        state = OrchestratorState(
            query="very obscure medical condition xyz123",
            config={},
            frame={"intent": "recent_pubs_by_topic"},
            routing_decision="pubmed_search",
            pubmed_results={"results": []},  # No results
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=["pubmed_search"],
            cache_hits={"pubmed_search": False},
            latencies={"pubmed_search": 500},
            errors=[],
            node_path=["parse_frame", "router", "pubmed_search"],
            answer=None,
            checkpoint_id=None,
            messages=[]
        )
        
        result = await synthesizer.synthesize(state)
        
        # Should generate empty results answer
        assert "answer" in result
        assert "no results" in result["answer"].lower() or "not found" in result["answer"].lower()
        
        # Should have appropriate answer type
        synthesis_metrics = result["synthesis_metrics"]
        assert synthesis_metrics["answer_type"] == "empty"

class TestOrchestratorIntegration:
    """Integration tests combining multiple components."""
    
    def setup_method(self):
        """Setup integration test fixtures."""
        self.config = OrchestratorConfig()
        self.mock_db = Mock(spec=DatabaseManager)
    
    @pytest.mark.asyncio
    async def test_frame_to_router_integration(self):
        """Test integration between frame parser and router."""
        frame_node = create_frame_parser_node(self.config)
        router_node = create_router_node(self.config)
        
        # Start with empty state
        initial_state = OrchestratorState(
            query="recent clinical trials for diabetes phase 3",
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
        
        # Execute frame parsing
        frame_result = await frame_node(initial_state)
        
        # Update state with frame result
        intermediate_state = {**initial_state, **frame_result}
        
        # Execute routing
        router_result = await router_node(intermediate_state)
        
        # Verify integration
        assert "frame" in frame_result
        assert frame_result["frame"]["intent"] == "indication_phase_trials"  # Should detect phase 3 trials
        
        assert router_result["routing_decision"] == "ctgov_search"  # Should route to clinical trials
    
    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """Test error propagation through the system."""
        frame_node = create_frame_parser_node(self.config)
        
        # Mock frame parser to fail
        with patch('bio_mcp.orchestrator.frame.FrameParser.parse_frame') as mock_parser:
            mock_parser.side_effect = ValueError("Invalid query format")
            
            state = OrchestratorState(
                query="malformed query $$##@@",
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
            
            result = await frame_node(state)
            
            # Error should be properly captured and formatted
            assert len(result["errors"]) == 1
            error = result["errors"][0]
            assert error["node"] == "parse_frame"
            assert "Invalid query format" in error["error"]
            assert "timestamp" in error
    
    @pytest.mark.asyncio
    async def test_state_accumulation(self):
        """Test that state properly accumulates across nodes."""
        frame_node = create_frame_parser_node(self.config)
        router_node = create_router_node(self.config)
        
        state = OrchestratorState(
            query="diabetes research",
            config={"test_param": "value"},
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
        
        # Execute frame node
        after_frame = await frame_node(state)
        
        # Update state
        updated_state = {**state, **after_frame}
        
        # Execute router node
        after_router = await router_node(updated_state)
        
        # Final state should accumulate all changes
        final_state = {**updated_state, **after_router}
        
        # Verify accumulation
        assert "parse_frame" in final_state["node_path"]
        assert "router" in final_state["node_path"]
        assert "parse_frame" in final_state["latencies"]
        assert "router" in final_state["latencies"]
        assert final_state["config"]["test_param"] == "value"  # Original config preserved
        assert final_state["frame"] is not None  # Frame added
        assert final_state["routing_decision"] is not None  # Routing decision added
```

### 2. Integration Test Suite

**File**: `tests/integration/orchestrator/test_full_orchestrator_integration.py`
```python
"""Full integration tests with real services."""
import pytest
import asyncio
from datetime import datetime

from bio_mcp.orchestrator.graph_builder import build_orchestrator_graph
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state.persistence import BioMCPCheckpointSaver
from bio_mcp.shared.clients.database import DatabaseManager
from tests.integration.database.conftest import postgres_container, clean_db

class TestFullOrchestratorIntegration:
    """Integration tests with real database and services."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_pubmed_flow(self, clean_db):
        """Test complete flow with real PubMed integration."""
        config = OrchestratorConfig()
        config.default_budget_ms = 10000  # 10 second budget for integration test
        
        # Build graph
        graph = build_orchestrator_graph(config)
        
        # Set up checkpointing
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        # Execute realistic query
        initial_state = {
            "query": "recent publications on GLP-1 receptor agonists for diabetes",
            "config": {"max_results": 5},
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
        
        result = await compiled_graph.ainvoke(initial_state)
        
        # Verify complete execution
        assert result["answer"] is not None
        assert result["checkpoint_id"] is not None
        assert "parse_frame" in result["node_path"]
        assert "router" in result["node_path"]
        assert "synthesizer" in result["node_path"]
        
        # Should have routed to PubMed for publications query
        assert "pubmed_search" in result["node_path"]
        
        # Should have PubMed results
        assert result["pubmed_results"] is not None
        
        # Answer should contain relevant information
        answer = result["answer"].lower()
        assert any(keyword in answer for keyword in ["glp-1", "diabetes", "publications"])
        
        # Should have quality metrics
        assert "quality_metrics" in result
        quality = result["quality_metrics"]
        assert quality["overall_score"] >= 0
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_clinical_trials_flow(self, clean_db):
        """Test flow with clinical trials query."""
        config = OrchestratorConfig()
        config.default_budget_ms = 15000  # Longer budget for trials API
        
        graph = build_orchestrator_graph(config)
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        initial_state = {
            "query": "phase 3 trials for Alzheimer disease currently recruiting",
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
        
        result = await compiled_graph.ainvoke(initial_state)
        
        # Should route to clinical trials
        assert "ctgov_search" in result["node_path"]
        
        # Should have trials results
        if result["ctgov_results"]:  # May be empty due to specific query
            assert isinstance(result["ctgov_results"], dict)
        
        # Answer should mention trials
        answer = result["answer"].lower()
        assert "trials" in answer or "clinical" in answer
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_recovery_integration(self, clean_db):
        """Test error recovery in integration environment."""
        config = OrchestratorConfig()
        
        # Mock one of the services to fail
        from unittest.mock import patch
        
        graph = build_orchestrator_graph(config)
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        # Test with query that should trigger PubMed search
        initial_state = {
            "query": "diabetes research publications",
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
        
        with patch('bio_mcp.sources.pubmed.client.PubMedClient.search') as mock_search:
            # Mock PubMed to fail
            mock_search.side_effect = Exception("PubMed API error")
            
            result = await compiled_graph.ainvoke(initial_state)
            
            # Should still complete execution with error handling
            assert result["answer"] is not None
            assert len(result["errors"]) > 0
            
            # Error should be recorded
            pubmed_errors = [e for e in result["errors"] if "pubmed" in e.get("node", "").lower()]
            assert len(pubmed_errors) > 0
            assert "PubMed API error" in pubmed_errors[0]["error"]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_executions(self, clean_db):
        """Test handling multiple concurrent executions."""
        config = OrchestratorConfig()
        
        graph = build_orchestrator_graph(config)
        checkpointer = BioMCPCheckpointSaver(config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        # Create multiple different queries
        queries = [
            "recent diabetes research",
            "alzheimer clinical trials phase 2",
            "cancer immunotherapy publications"
        ]
        
        # Execute all queries concurrently
        tasks = []
        for query in queries:
            initial_state = {
                "query": query,
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
            tasks.append(compiled_graph.ainvoke(initial_state))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All executions should complete
        assert len(results) == 3
        
        # Check that all results are valid (not exceptions)
        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"Query {i} failed: {result}"
            assert result["answer"] is not None
            assert result["checkpoint_id"] is not None
            
            # Each should have unique checkpoint
            for j, other_result in enumerate(results):
                if i != j and not isinstance(other_result, Exception):
                    assert result["checkpoint_id"] != other_result["checkpoint_id"]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_checkpoint_persistence(self, clean_db):
        """Test checkpoint persistence and retrieval."""
        config = OrchestratorConfig()
        
        # Use file-based checkpoint for persistence testing
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            checkpoint_path = f.name
        
        checkpointer = BioMCPCheckpointSaver(config, checkpoint_path)
        
        # Create orchestration checkpoint
        from bio_mcp.orchestrator.state.persistence import OrchestrationCheckpoint
        
        checkpoint = OrchestrationCheckpoint(
            checkpoint_id="test_checkpoint_123",
            query="test query for persistence",
            frame={"intent": "recent_pubs_by_topic"},
            state={"test": "data"},
            created_at=datetime.utcnow()
        )
        
        # Save checkpoint
        await checkpointer.asave_checkpoint(None, None, checkpoint)
        
        # Retrieve checkpoint
        retrieved = await checkpointer.aget_checkpoint("test_checkpoint_123")
        
        assert retrieved is not None
        assert retrieved.checkpoint_id == "test_checkpoint_123"
        assert retrieved.query == "test query for persistence"
        assert retrieved.frame["intent"] == "recent_pubs_by_topic"
        
        # Cleanup
        import os
        os.unlink(checkpoint_path)
```

### 3. End-to-End Test Suite

**File**: `tests/e2e/orchestrator/test_orchestrator_e2e.py`
```python
"""End-to-end tests simulating real user scenarios."""
import pytest
import asyncio
from datetime import datetime

from bio_mcp.orchestrator.graph_builder import build_orchestrator_graph
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state.persistence import BioMCPCheckpointSaver
from bio_mcp.orchestrator.observability.metrics_collector import get_metrics_collector

class TestOrchestratorE2E:
    """End-to-end user scenario tests."""
    
    def setup_method(self):
        """Setup E2E test environment."""
        self.config = OrchestratorConfig()
        self.config.default_budget_ms = 20000  # Generous budget for E2E
        self.metrics_collector = get_metrics_collector(self.config)
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_researcher_literature_review_scenario(self):
        """Test scenario: Researcher doing literature review."""
        # Scenario: A researcher wants to review recent literature on GLP-1 agonists
        
        graph = build_orchestrator_graph(self.config)
        checkpointer = BioMCPCheckpointSaver(self.config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        # Query typical of researcher
        query = "recent systematic reviews and meta-analyses on GLP-1 receptor agonists for type 2 diabetes published in last 2 years"
        
        initial_state = {
            "query": query,
            "config": {"fetch_policy": "cache_then_network"},
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
        
        start_time = datetime.utcnow()
        result = await compiled_graph.ainvoke(initial_state)
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Verify researcher expectations
        assert result["answer"] is not None
        assert len(result["answer"]) > 500  # Substantial content
        
        # Should identify relevant publications
        answer = result["answer"].lower()
        assert "glp-1" in answer or "glucagon" in answer
        assert "diabetes" in answer
        assert "systematic" in answer or "meta-analysis" in answer
        
        # Should have quality assessment
        quality = result["quality_metrics"]
        assert quality["overall_score"] > 0.5  # Reasonable quality
        
        # Should have proper citations
        citations = result["citations"]
        assert len(citations) > 0
        
        # Performance should be acceptable
        assert execution_time < 20000  # Under 20 seconds
        
        # Record metrics
        await self.metrics_collector.record_execution(result, execution_time)
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_clinician_trial_lookup_scenario(self):
        """Test scenario: Clinician looking for current trials."""
        # Scenario: Clinician wants to find recruiting trials for patients
        
        graph = build_orchestrator_graph(self.config)
        checkpointer = BioMCPCheckpointSaver(self.config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        query = "currently recruiting phase 3 clinical trials for heart failure with reduced ejection fraction"
        
        initial_state = {
            "query": query,
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
        
        result = await compiled_graph.ainvoke(initial_state)
        
        # Should route to clinical trials
        assert "ctgov_search" in result["node_path"]
        
        # Answer should contain trial information
        answer = result["answer"].lower()
        assert "trials" in answer
        assert "phase" in answer
        assert "recruiting" in answer or "enrolling" in answer
        
        # Should have NCT identifiers if trials found
        if result["ctgov_results"] and result["ctgov_results"].get("results"):
            assert "NCT" in result["answer"]
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_pharmaceutical_company_scenario(self):
        """Test scenario: Pharmaceutical company competitive analysis."""
        # Scenario: Company wants to understand competitive landscape
        
        graph = build_orchestrator_graph(self.config)
        checkpointer = BioMCPCheckpointSaver(self.config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        query = "Pfizer diabetes drug development pipeline clinical trials and recent publications"
        
        initial_state = {
            "query": query,
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
        
        result = await compiled_graph.ainvoke(initial_state)
        
        # Should identify company entity
        frame = result["frame"]
        assert frame["entities"].get("company") == "Pfizer"
        
        # Should route to both publications and trials
        assert "trials_with_pubs" in frame["intent"] or "recent_pubs_by_topic" in frame["intent"]
        
        # Answer should mention Pfizer
        assert "pfizer" in result["answer"].lower()
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complex_multi_entity_scenario(self):
        """Test scenario: Complex query with multiple entities."""
        # Scenario: Complex research question with multiple parameters
        
        graph = build_orchestrator_graph(self.config)
        checkpointer = BioMCPCheckpointSaver(self.config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        query = "phase 2 and 3 trials by Novartis for cardiovascular outcomes with publications in high impact journals last 3 years"
        
        initial_state = {
            "query": query,
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
        
        result = await compiled_graph.ainvoke(initial_state)
        
        # Should extract multiple entities and filters
        frame = result["frame"]
        entities = frame["entities"]
        filters = frame["filters"]
        
        assert entities.get("company") == "Novartis"
        assert "2" in filters.get("phase", []) or "3" in filters.get("phase", [])
        
        # Should provide comprehensive answer
        answer = result["answer"]
        assert len(answer) > 300  # Detailed response expected
        
        # Quality should reflect complexity
        quality = result["quality_metrics"]
        # Complex queries may have lower completeness if some data unavailable
        assert quality["overall_score"] >= 0.0
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_user_feedback_scenario(self):
        """Test scenario: User refining search based on feedback."""
        # Scenario: User gets initial results, then refines query
        
        graph = build_orchestrator_graph(self.config)
        checkpointer = BioMCPCheckpointSaver(self.config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        # First query - broad
        initial_query = "diabetes treatment"
        
        first_state = {
            "query": initial_query,
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
        
        first_result = await compiled_graph.ainvoke(first_state)
        
        # Second query - more specific (simulating user refinement)
        refined_query = "diabetes treatment insulin therapy recent clinical trials"
        
        second_state = {
            "query": refined_query,
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
        
        second_result = await compiled_graph.ainvoke(second_state)
        
        # Verify both queries complete successfully
        assert first_result["answer"] is not None
        assert second_result["answer"] is not None
        
        # Second query should be more specific
        first_frame = first_result["frame"]
        second_frame = second_result["frame"]
        
        # Should have different or more specific entities/filters
        assert (
            second_frame["entities"] != first_frame["entities"] or
            second_frame["filters"] != first_frame["filters"] or
            second_frame["intent"] != first_frame["intent"]
        )
        
        # Different checkpoints
        assert first_result["checkpoint_id"] != second_result["checkpoint_id"]
    
    @pytest.mark.e2e
    @pytest.mark.asyncio 
    async def test_performance_under_load_scenario(self):
        """Test scenario: System under moderate concurrent load."""
        # Scenario: Multiple users querying system simultaneously
        
        graph = build_orchestrator_graph(self.config)
        checkpointer = BioMCPCheckpointSaver(self.config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        # Different types of queries
        queries = [
            "recent alzheimer drug developments",
            "phase 3 cancer trials recruiting",
            "diabetes prevention strategies publications",
            "heart failure treatment guidelines",
            "covid-19 vaccine effectiveness studies"
        ]
        
        # Execute 10 concurrent requests (2 of each query type)
        tasks = []
        for i in range(10):
            query = queries[i % len(queries)]
            
            initial_state = {
                "query": f"{query} request {i}",  # Make each unique
                "config": {"request_id": i},
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
            
            tasks.append(compiled_graph.ainvoke(initial_state))
        
        start_time = datetime.utcnow()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Verify performance characteristics
        successful_results = [r for r in results if not isinstance(r, Exception)]
        
        # At least 80% should succeed under load
        success_rate = len(successful_results) / len(results)
        assert success_rate >= 0.8, f"Success rate under load: {success_rate:.1%}"
        
        # Average response time should be reasonable
        avg_response_time = total_time / len(results)
        assert avg_response_time < 30, f"Average response time too high: {avg_response_time:.1f}s"
        
        # All successful results should have answers
        for result in successful_results:
            assert result["answer"] is not None
            assert result["checkpoint_id"] is not None
```

### 4. Performance Benchmark Suite

**File**: `tests/benchmarks/orchestrator/test_orchestrator_performance.py`
```python
"""Performance benchmarks for orchestrator."""
import pytest
import asyncio
import time
import statistics
from datetime import datetime

from bio_mcp.orchestrator.graph_builder import build_orchestrator_graph
from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state.persistence import BioMCPCheckpointSaver

class TestOrchestratorPerformance:
    """Performance benchmarks and regression tests."""
    
    def setup_method(self):
        """Setup benchmark environment."""
        self.config = OrchestratorConfig()
        self.config.default_budget_ms = 10000
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_simple_query_performance(self):
        """Benchmark simple query performance."""
        graph = build_orchestrator_graph(self.config)
        checkpointer = BioMCPCheckpointSaver(self.config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        query = "diabetes publications"
        
        # Warmup execution
        warmup_state = {
            "query": query,
            "config": {},
            "frame": None, "routing_decision": None, "pubmed_results": None,
            "ctgov_results": None, "rag_results": None, "tool_calls_made": [],
            "cache_hits": {}, "latencies": {}, "errors": [], "node_path": [],
            "answer": None, "checkpoint_id": None, "messages": []
        }
        
        await compiled_graph.ainvoke(warmup_state)
        
        # Benchmark executions
        execution_times = []
        num_runs = 10
        
        for i in range(num_runs):
            test_state = {
                "query": f"{query} run {i}",
                "config": {},
                "frame": None, "routing_decision": None, "pubmed_results": None,
                "ctgov_results": None, "rag_results": None, "tool_calls_made": [],
                "cache_hits": {}, "latencies": {}, "errors": [], "node_path": [],
                "answer": None, "checkpoint_id": None, "messages": []
            }
            
            start_time = time.perf_counter()
            result = await compiled_graph.ainvoke(test_state)
            end_time = time.perf_counter()
            
            execution_time_ms = (end_time - start_time) * 1000
            execution_times.append(execution_time_ms)
            
            # Verify successful execution
            assert result["answer"] is not None
        
        # Performance assertions
        avg_time = statistics.mean(execution_times)
        p95_time = statistics.quantiles(execution_times, n=20)[18]  # 95th percentile
        
        print(f"Simple query performance:")
        print(f"  Average: {avg_time:.1f}ms")
        print(f"  P95: {p95_time:.1f}ms")
        print(f"  Min: {min(execution_times):.1f}ms")
        print(f"  Max: {max(execution_times):.1f}ms")
        
        # Performance targets
        assert avg_time < 3000, f"Average execution time too high: {avg_time:.1f}ms"
        assert p95_time < 5000, f"P95 execution time too high: {p95_time:.1f}ms"
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_complex_query_performance(self):
        """Benchmark complex query performance."""
        graph = build_orchestrator_graph(self.config)
        checkpointer = BioMCPCheckpointSaver(self.config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        # Complex query that should trigger multiple tool calls
        query = "phase 3 trials by Pfizer for diabetes with recent publications in high impact journals"
        
        execution_times = []
        num_runs = 5  # Fewer runs for complex queries
        
        for i in range(num_runs):
            test_state = {
                "query": f"{query} run {i}",
                "config": {},
                "frame": None, "routing_decision": None, "pubmed_results": None,
                "ctgov_results": None, "rag_results": None, "tool_calls_made": [],
                "cache_hits": {}, "latencies": {}, "errors": [], "node_path": [],
                "answer": None, "checkpoint_id": None, "messages": []
            }
            
            start_time = time.perf_counter()
            result = await compiled_graph.ainvoke(test_state)
            end_time = time.perf_counter()
            
            execution_time_ms = (end_time - start_time) * 1000
            execution_times.append(execution_time_ms)
            
            assert result["answer"] is not None
        
        avg_time = statistics.mean(execution_times)
        
        print(f"Complex query performance:")
        print(f"  Average: {avg_time:.1f}ms")
        
        # Complex queries can take longer
        assert avg_time < 8000, f"Complex query execution time too high: {avg_time:.1f}ms"
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_concurrent_execution_performance(self):
        """Benchmark concurrent execution performance."""
        graph = build_orchestrator_graph(self.config)
        checkpointer = BioMCPCheckpointSaver(self.config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        # Different queries to avoid cache effects
        queries = [
            "alzheimer research publications",
            "cancer immunotherapy trials",
            "diabetes prevention studies",
            "heart failure treatments",
            "covid vaccine research"
        ]
        
        num_concurrent = 5
        
        # Create concurrent tasks
        tasks = []
        for i in range(num_concurrent):
            query = queries[i % len(queries)]
            
            test_state = {
                "query": f"{query} concurrent {i}",
                "config": {},
                "frame": None, "routing_decision": None, "pubmed_results": None,
                "ctgov_results": None, "rag_results": None, "tool_calls_made": [],
                "cache_hits": {}, "latencies": {}, "errors": [], "node_path": [],
                "answer": None, "checkpoint_id": None, "messages": []
            }
            
            tasks.append(compiled_graph.ainvoke(test_state))
        
        # Execute concurrently
        start_time = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.perf_counter()
        
        total_time = (end_time - start_time) * 1000
        avg_time_per_request = total_time / num_concurrent
        
        # Check results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        success_rate = len(successful_results) / len(results)
        
        print(f"Concurrent execution performance ({num_concurrent} requests):")
        print(f"  Total time: {total_time:.1f}ms")
        print(f"  Average per request: {avg_time_per_request:.1f}ms")
        print(f"  Success rate: {success_rate:.1%}")
        
        # Performance assertions
        assert success_rate >= 0.8, f"Success rate too low under concurrency: {success_rate:.1%}"
        assert avg_time_per_request < 6000, f"Average concurrent execution time too high: {avg_time_per_request:.1f}ms"
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_memory_usage_benchmark(self):
        """Benchmark memory usage during execution."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        graph = build_orchestrator_graph(self.config)
        checkpointer = BioMCPCheckpointSaver(self.config, ":memory:")
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        # Execute multiple queries
        for i in range(20):
            test_state = {
                "query": f"test query {i}",
                "config": {},
                "frame": None, "routing_decision": None, "pubmed_results": None,
                "ctgov_results": None, "rag_results": None, "tool_calls_made": [],
                "cache_hits": {}, "latencies": {}, "errors": [], "node_path": [],
                "answer": None, "checkpoint_id": None, "messages": []
            }
            
            await compiled_graph.ainvoke(test_state)
        
        # Check memory after executions
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - baseline_memory
        
        print(f"Memory usage:")
        print(f"  Baseline: {baseline_memory:.1f} MB")
        print(f"  Final: {final_memory:.1f} MB")
        print(f"  Increase: {memory_increase:.1f} MB")
        
        # Memory increase should be reasonable
        assert memory_increase < 100, f"Memory increase too high: {memory_increase:.1f} MB"
```

## Testing Configuration and Setup

**File**: `tests/conftest.py` (additions to existing conftest)
```python
"""Additional test configuration for orchestrator tests."""
import pytest
import asyncio
from unittest.mock import Mock

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_orchestrator_config():
    """Mock orchestrator configuration for testing."""
    from bio_mcp.orchestrator.config import OrchestratorConfig
    
    config = OrchestratorConfig()
    config.default_budget_ms = 5000
    config.enable_tracing = False  # Disable for tests
    config.enable_redis_cache = False  # Use in-memory for tests
    return config

@pytest.fixture
def mock_database_manager():
    """Mock database manager for testing."""
    from bio_mcp.shared.clients.database import DatabaseManager
    
    mock_db = Mock(spec=DatabaseManager)
    mock_db.get_connection.return_value = Mock()
    return mock_db
```

## Test Runner and CI Integration

**File**: `.github/workflows/orchestrator-tests.yml`
```yaml
name: Orchestrator Tests

on:
  push:
    paths:
      - 'src/bio_mcp/orchestrator/**'
      - 'tests/**'
  pull_request:
    paths:
      - 'src/bio_mcp/orchestrator/**'
      - 'tests/**'

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --dev
      
      - name: Run unit tests
        run: uv run pytest tests/unit/orchestrator/ -v --cov=src/bio_mcp/orchestrator
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: biotest
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --dev
      
      - name: Run integration tests
        run: uv run pytest tests/integration/orchestrator/ -v
        env:
          DATABASE_URL: postgresql://postgres:testpass@localhost:5432/biotest

  e2e-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request' || github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --dev
      
      - name: Run E2E tests
        run: uv run pytest tests/e2e/orchestrator/ -v --tb=short
        timeout-minutes: 30

  performance-tests:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --dev
      
      - name: Run performance benchmarks
        run: uv run pytest tests/benchmarks/orchestrator/ -v --tb=short
```

## Acceptance Criteria
- [ ] Unit tests achieve >95% code coverage for all orchestrator components
- [ ] Integration tests validate real database and MCP tool interactions
- [ ] End-to-end tests cover realistic user scenarios and workflows
- [ ] Performance benchmarks establish baseline metrics and regression detection
- [ ] Error handling tests verify graceful failure and recovery scenarios
- [ ] Concurrent execution tests validate system stability under load
- [ ] Memory usage tests ensure no significant memory leaks
- [ ] CI pipeline runs all test suites automatically on code changes
- [ ] Test fixtures properly mock external dependencies
- [ ] Test documentation provides clear examples of usage patterns

## Files Created/Modified
- `tests/unit/orchestrator/test_complete_orchestrator.py` - Comprehensive unit tests
- `tests/integration/orchestrator/test_full_orchestrator_integration.py` - Integration tests
- `tests/e2e/orchestrator/test_orchestrator_e2e.py` - End-to-end user scenarios
- `tests/benchmarks/orchestrator/test_orchestrator_performance.py` - Performance benchmarks
- `tests/conftest.py` - Additional test configuration
- `.github/workflows/orchestrator-tests.yml` - CI pipeline configuration

## Next Milestone
After completion, proceed to **M7 — LangGraph Optimization** which will focus on performance optimization, production deployment readiness, and final system tuning for optimal performance and reliability.
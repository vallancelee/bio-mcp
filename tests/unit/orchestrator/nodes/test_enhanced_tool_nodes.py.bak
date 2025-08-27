"""Test enhanced tool nodes with deep MCP integration."""

from unittest.mock import AsyncMock, Mock

import pytest

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.nodes.enhanced_tool_nodes import (
    EnhancedPubMedNode,
    EnhancedTrialsNode,
)
from bio_mcp.orchestrator.state import NodeResult, OrchestratorState


class TestEnhancedPubMedNode:
    """Test EnhancedPubMedNode implementation."""

    @pytest.mark.asyncio
    async def test_init_enhanced_pubmed_node(self):
        """Test enhanced PubMed node initialization."""
        config = OrchestratorConfig()
        db_manager = Mock()

        node = EnhancedPubMedNode(config, db_manager)

        assert node.config == config
        assert node.adapter is not None
        assert node.executor is not None

    @pytest.mark.asyncio
    async def test_enhanced_pubmed_search_with_topic(self):
        """Test enhanced PubMed search with topic entity."""
        config = OrchestratorConfig()
        db_manager = Mock()
        node = EnhancedPubMedNode(config, db_manager)

        # Mock the executor
        node.executor.execute_parallel = AsyncMock(
            return_value=[
                NodeResult(
                    success=True,
                    data={
                        "results": [{"pmid": "12345", "title": "Test Article"}],
                        "total": 1,
                    },
                    cache_hit=False,
                    latency_ms=100.0,
                    node_name="pubmed.search",
                )
            ]
        )

        state = OrchestratorState(
            query="search for diabetes",
            config={},
            frame={
                "entities": {"topic": "diabetes"},
                "filters": {"published_within_days": 30},
            },
            routing_decision=None,
            pubmed_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=[],
            messages=[],
        )

        result = await node(state)

        assert "pubmed_results" in result
        assert result["pubmed_results"]["total_results"] == 1
        assert result["pubmed_results"]["search_terms"] == ["diabetes"]
        assert "enhanced_pubmed" in result["node_path"]
        assert "pubmed.search" in result["tool_calls_made"]

    @pytest.mark.asyncio
    async def test_enhanced_pubmed_multiple_search_terms(self):
        """Test enhanced PubMed search with multiple entities."""
        config = OrchestratorConfig()
        db_manager = Mock()
        node = EnhancedPubMedNode(config, db_manager)

        # Mock parallel execution results
        node.executor.execute_parallel = AsyncMock(
            return_value=[
                NodeResult(
                    success=True,
                    data={
                        "results": [{"pmid": "12345", "title": "Diabetes Article"}],
                        "total": 1,
                    },
                    cache_hit=False,
                    latency_ms=100.0,
                    node_name="pubmed.search",
                ),
                NodeResult(
                    success=True,
                    data={
                        "results": [{"pmid": "67890", "title": "Pharma Article"}],
                        "total": 1,
                    },
                    cache_hit=True,
                    latency_ms=50.0,
                    node_name="pubmed.search",
                ),
            ]
        )

        state = OrchestratorState(
            query="search for diabetes from Pfizer",
            config={},
            frame={
                "entities": {"topic": "diabetes", "company": "Pfizer"},
                "filters": {},
            },
            routing_decision=None,
            pubmed_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=[],
            messages=[],
        )

        result = await node(state)

        assert result["pubmed_results"]["total_results"] == 2
        assert set(result["pubmed_results"]["search_terms"]) == {
            "diabetes",
            "Pfizer[AD]",
        }
        assert result["cache_hits"]["pubmed_search"]  # At least one cache hit
        assert result["latencies"]["pubmed_search"] == 75.0  # Average of 100 and 50

    @pytest.mark.asyncio
    async def test_enhanced_pubmed_no_search_terms(self):
        """Test enhanced PubMed node with no extractable search terms."""
        config = OrchestratorConfig()
        db_manager = Mock()
        node = EnhancedPubMedNode(config, db_manager)

        state = OrchestratorState(
            query="generic query",
            config={},
            frame={
                "entities": {},  # No extractable entities
                "filters": {},
            },
            routing_decision=None,
            pubmed_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=[],
            messages=[],
        )

        result = await node(state)

        # Should return error response
        assert "error" in result
        assert "No search terms found" in result["error"]

    @pytest.mark.asyncio
    async def test_enhanced_pubmed_deduplication(self):
        """Test PMID deduplication across multiple search results."""
        config = OrchestratorConfig()
        db_manager = Mock()
        node = EnhancedPubMedNode(config, db_manager)

        # Mock results with duplicate PMIDs
        node.executor.execute_parallel = AsyncMock(
            return_value=[
                NodeResult(
                    success=True,
                    data={
                        "results": [
                            {"pmid": "12345", "title": "Article 1"},
                            {"pmid": "67890", "title": "Article 2"},
                        ],
                        "total": 2,
                    },
                    cache_hit=False,
                    latency_ms=100.0,
                    node_name="pubmed.search",
                ),
                NodeResult(
                    success=True,
                    data={
                        "results": [
                            {
                                "pmid": "12345",
                                "title": "Article 1 Duplicate",
                            },  # Same PMID
                            {"pmid": "11111", "title": "Article 3"},
                        ],
                        "total": 2,
                    },
                    cache_hit=False,
                    latency_ms=100.0,
                    node_name="pubmed.search",
                ),
            ]
        )

        state = OrchestratorState(
            query="search query",
            config={},
            frame={
                "entities": {"topic": "diabetes", "indication": "type 2"},
                "filters": {},
            },
            routing_decision=None,
            pubmed_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=[],
            messages=[],
        )

        result = await node(state)

        # Should deduplicate - only 3 unique PMIDs
        assert result["pubmed_results"]["total_results"] == 3
        pmids = {
            article["pmid"] for article in result["pubmed_results"]["search_results"]
        }
        assert pmids == {"12345", "67890", "11111"}


class TestEnhancedTrialsNode:
    """Test EnhancedTrialsNode implementation."""

    @pytest.mark.asyncio
    async def test_init_enhanced_trials_node(self):
        """Test enhanced trials node initialization."""
        config = OrchestratorConfig()
        db_manager = Mock()

        node = EnhancedTrialsNode(config, db_manager)

        assert node.config == config
        assert node.adapter is not None
        assert node.executor is not None

    @pytest.mark.asyncio
    async def test_enhanced_trials_search_with_condition(self):
        """Test enhanced trials search with condition entity."""
        config = OrchestratorConfig()
        db_manager = Mock()
        node = EnhancedTrialsNode(config, db_manager)

        # Mock the executor
        node.executor.execute_parallel = AsyncMock(
            return_value=[
                NodeResult(
                    success=True,
                    data={
                        "results": [{"nct_id": "NCT12345", "title": "Diabetes Trial"}],
                        "total": 1,
                    },
                    cache_hit=False,
                    latency_ms=150.0,
                    node_name="clinicaltrials.search",
                )
            ]
        )

        state = OrchestratorState(
            query="search for diabetes trials",
            config={},
            frame={
                "entities": {"indication": "diabetes"},
                "filters": {"phase": "Phase III"},
            },
            routing_decision=None,
            trials_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=[],
            messages=[],
        )

        result = await node(state)

        assert "trials_results" in result
        assert result["trials_results"]["filtered_count"] == 1
        assert result["trials_results"]["search_terms"] == ["diabetes"]
        assert "enhanced_trials" in result["node_path"]
        assert "clinicaltrials.search" in result["tool_calls_made"]

    @pytest.mark.asyncio
    async def test_enhanced_trials_company_search(self):
        """Test enhanced trials search with company-specific terms."""
        config = OrchestratorConfig()
        db_manager = Mock()
        node = EnhancedTrialsNode(config, db_manager)

        node.executor.execute_parallel = AsyncMock(
            return_value=[
                NodeResult(
                    success=True,
                    data={
                        "results": [{"nct_id": "NCT67890", "title": "Pfizer Trial"}],
                        "total": 1,
                    },
                    cache_hit=False,
                    latency_ms=120.0,
                    node_name="clinicaltrials.search",
                )
            ]
        )

        state = OrchestratorState(
            query="Pfizer trials",
            config={},
            frame={
                "entities": {"company": "Pfizer"},
                "filters": {"status": "recruiting"},
            },
            routing_decision=None,
            trials_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=[],
            messages=[],
        )

        result = await node(state)

        assert "Pfizer" in result["trials_results"]["search_terms"]
        assert result["latencies"]["trials_search"] == 120.0

    @pytest.mark.asyncio
    async def test_enhanced_trials_no_search_terms(self):
        """Test enhanced trials node with no extractable search terms."""
        config = OrchestratorConfig()
        db_manager = Mock()
        node = EnhancedTrialsNode(config, db_manager)

        state = OrchestratorState(
            query="generic query",
            config={},
            frame={
                "entities": {},  # No extractable entities
                "filters": {},
            },
            routing_decision=None,
            trials_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=[],
            messages=[],
        )

        result = await node(state)

        # Should return error response
        assert "error" in result
        assert "No search terms found" in result["error"]

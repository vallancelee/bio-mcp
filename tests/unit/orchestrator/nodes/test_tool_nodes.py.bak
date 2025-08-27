"""Test tool execution nodes."""

from unittest.mock import AsyncMock, Mock

import pytest

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.nodes.tool_nodes import PubMedSearchNode
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.sources.pubmed.client import PubMedDocument


class TestPubMedSearchNode:
    """Test PubMedSearchNode implementation."""

    @pytest.mark.asyncio
    async def test_pubmed_search_node_success(self):
        """Test successful PubMed search."""
        config = OrchestratorConfig()
        node = PubMedSearchNode(config)

        # Mock the client and its methods
        mock_search_result = Mock()
        mock_search_result.pmids = ["123456", "789012"]
        mock_search_result.total_count = 2

        mock_documents = [
            PubMedDocument(
                pmid="123456",
                title="Test Article 1",
                authors=["Author A", "Author B"],
                abstract="Test abstract 1",
            ),
            PubMedDocument(
                pmid="789012",
                title="Test Article 2",
                authors=["Author C"],
                abstract="Test abstract 2",
            ),
        ]

        node.client = Mock()
        node.client.search = AsyncMock(return_value=mock_search_result)
        node.client.fetch_documents = AsyncMock(return_value=mock_documents)

        state = OrchestratorState(
            query="test query",
            config={},
            normalized_query=None,
            query_entities=None,
            query_enhancement_metadata=None,
            frame={
                "intent": "recent_pubs_by_topic",
                "entities": {"topic": "GLP-1 agonists"},
                "filters": {"published_within_days": 180},
            },
            routing_decision=None,
            intent_confidence=None,
            entity_confidence=None,
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=[],
            answer=None,
            orchestrator_checkpoint_id=None,
            messages=[],
        )

        result = await node(state)

        # Verify results
        assert "pubmed_results" in result
        assert result["pubmed_results"]["total_count"] == 2
        assert len(result["pubmed_results"]["results"]) == 2
        assert result["pubmed_results"]["results"][0]["title"] == "Test Article 1"

        # Verify state updates
        assert "pubmed_search" in result["tool_calls_made"]
        assert "pubmed_search" in result["cache_hits"]
        assert "pubmed_search" in result["latencies"]
        assert "pubmed_search" in result["node_path"]
        assert len(result["messages"]) == 1
        assert "2 results" in result["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_pubmed_search_node_no_topic_error(self):
        """Test error handling when no search term is found."""
        config = OrchestratorConfig()
        node = PubMedSearchNode(config)

        state = OrchestratorState(
            query="",  # Empty query to trigger error
            config={},
            normalized_query=None,
            query_entities=None,
            query_enhancement_metadata=None,
            frame={
                "intent": "recent_pubs_by_topic",
                "entities": {},  # No topic
                "filters": {},
            },
            routing_decision=None,
            intent_confidence=None,
            entity_confidence=None,
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=[],
            answer=None,
            orchestrator_checkpoint_id=None,
            messages=[],
        )

        result = await node(state)

        # Verify error handling
        assert len(result["errors"]) == 1
        assert result["errors"][0]["node"] == "pubmed_search"
        assert "No search term found" in result["errors"][0]["error"]
        assert "pubmed_search" in result["node_path"]

    @pytest.mark.asyncio
    async def test_pubmed_search_node_client_error(self):
        """Test error handling when client fails."""
        config = OrchestratorConfig()
        node = PubMedSearchNode(config)

        # Mock client to raise exception
        node.client = Mock()
        node.client.search = AsyncMock(side_effect=Exception("API Error"))

        state = OrchestratorState(
            query="test query",
            config={},
            normalized_query=None,
            query_entities=None,
            query_enhancement_metadata=None,
            frame={
                "intent": "recent_pubs_by_topic",
                "entities": {"topic": "diabetes"},
                "filters": {},
            },
            routing_decision=None,
            intent_confidence=None,
            entity_confidence=None,
            pubmed_results=None,
            ctgov_results=None,
            rag_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            errors=[],
            node_path=[],
            answer=None,
            orchestrator_checkpoint_id=None,
            messages=[],
        )

        result = await node(state)

        # Verify error handling
        assert result["pubmed_results"] is None
        assert len(result["errors"]) == 1
        assert result["errors"][0]["node"] == "pubmed_search"
        assert "API Error" in result["errors"][0]["error"]

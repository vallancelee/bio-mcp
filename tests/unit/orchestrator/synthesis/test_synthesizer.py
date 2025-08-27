"""Test advanced synthesizer functionality."""


import pytest

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import OrchestratorState
from bio_mcp.orchestrator.synthesis.synthesizer import (
    AdvancedSynthesizer,
    AnswerType,
)


@pytest.mark.asyncio
async def test_comprehensive_synthesis():
    """Test comprehensive answer synthesis."""
    config = OrchestratorConfig()
    synthesizer = AdvancedSynthesizer(config)

    state = OrchestratorState(
        query="diabetes research",
        frame={"intent": "recent_pubs_by_topic", "entities": {"topic": "diabetes"}},
        pubmed_results={
            "results": [
                {
                    "pmid": "123",
                    "title": "Diabetes Study",
                    "authors": ["Smith J"],
                    "journal": "Nature",
                }
            ]
        },
        ctgov_results={
            "results": [
                {"nct_id": "NCT123", "title": "Diabetes Trial", "phase": "Phase 3"}
            ]
        },
        config={},
        routing_decision=None,
        rag_results=None,
        tool_calls_made=["pubmed_search", "ctgov_search"],
        cache_hits={"pubmed_search": True, "ctgov_search": False},
        latencies={"pubmed_search": 200, "ctgov_search": 300},
        errors=[],
        node_path=["parse_frame", "router", "pubmed_search", "ctgov_search"],
        answer=None,
        checkpoint_id=None,
        messages=[],
    )

    result = await synthesizer.synthesize(state)

    assert "answer" in result
    assert "checkpoint_id" in result
    assert "citations" in result
    assert "quality_metrics" in result
    assert "synthesis_metrics" in result
    assert len(result["citations"]) == 2  # One from each source


@pytest.mark.asyncio
async def test_synthesis_with_empty_results():
    """Test synthesis with no results."""
    config = OrchestratorConfig()
    synthesizer = AdvancedSynthesizer(config)

    state = OrchestratorState(
        query="unknown topic",
        frame={"intent": "recent_pubs_by_topic"},
        pubmed_results={"results": []},
        ctgov_results={"results": []},
        config={},
        routing_decision=None,
        rag_results=None,
        tool_calls_made=[],
        cache_hits={},
        latencies={},
        errors=[],
        node_path=[],
        answer=None,
        checkpoint_id=None,
        messages=[],
    )

    result = await synthesizer.synthesize(state)

    assert result["answer"] is not None
    assert result["synthesis_metrics"]["answer_type"] == AnswerType.EMPTY.value


def test_answer_type_classification():
    """Test answer type classification logic."""
    config = OrchestratorConfig()
    synthesizer = AdvancedSynthesizer(config)

    # Empty results
    result_data = {"pubmed": {"results": []}, "clinicaltrials": {"results": []}}
    answer_type = synthesizer._classify_answer_type(result_data)
    assert answer_type == AnswerType.EMPTY

    # Minimal results
    result_data = {"pubmed": {"results": [{"pmid": "123"}]}}
    answer_type = synthesizer._classify_answer_type(result_data)
    assert answer_type == AnswerType.MINIMAL

    # Comprehensive results
    result_data = {
        "pubmed": {"results": [{"pmid": str(i)} for i in range(10)]},
        "clinicaltrials": {"results": [{"nct_id": f"NCT{i}"} for i in range(5)]},
    }
    answer_type = synthesizer._classify_answer_type(result_data)
    assert answer_type == AnswerType.COMPREHENSIVE


def test_checkpoint_id_generation():
    """Test deterministic checkpoint ID generation."""
    config = OrchestratorConfig()
    synthesizer = AdvancedSynthesizer(config)

    state = OrchestratorState(
        query="test query",
        frame={"intent": "recent_pubs_by_topic"},
        pubmed_results=None,
        ctgov_results=None,
        config={},
        routing_decision=None,
        rag_results=None,
        tool_calls_made=[],
        cache_hits={},
        latencies={},
        errors=[],
        node_path=[],
        answer=None,
        checkpoint_id=None,
        messages=[],
    )

    result_data = {"pubmed": {"results": [{"pmid": "123"}]}}

    # Should be deterministic
    checkpoint_id1 = synthesizer._generate_checkpoint_id(state, result_data)
    checkpoint_id2 = synthesizer._generate_checkpoint_id(state, result_data)

    assert checkpoint_id1 == checkpoint_id2
    assert checkpoint_id1.startswith("ckpt_")


def test_result_deduplication():
    """Test result deduplication across sources."""
    config = OrchestratorConfig()
    synthesizer = AdvancedSynthesizer(config)

    result_data = {
        "pubmed": {
            "results": [
                {"pmid": "123", "title": "Study 1"},
                {"pmid": "456", "title": "Study 2"},
            ]
        },
        "clinicaltrials": {
            "results": [
                {"nct_id": "NCT123", "title": "Trial 1"},
                {"nct_id": "NCT456", "title": "Trial 2"},
            ]
        },
    }

    unique_results = synthesizer._deduplicate_results(result_data)

    assert len(unique_results) == 4
    assert all("_source" in result for result in unique_results)


def test_result_id_generation():
    """Test unique ID generation for different result types."""
    config = OrchestratorConfig()
    synthesizer = AdvancedSynthesizer(config)

    # PubMed result with PMID
    pubmed_result = {"pmid": "12345", "title": "Study"}
    result_id = synthesizer._get_result_id(pubmed_result, "pubmed")
    assert result_id == "pmid:12345"

    # ClinicalTrials result with NCT ID
    ct_result = {"nct_id": "NCT12345", "title": "Trial"}
    result_id = synthesizer._get_result_id(ct_result, "clinicaltrials")
    assert result_id == "nct:NCT12345"

    # Result with only title
    title_result = {"title": "Some Document"}
    result_id = synthesizer._get_result_id(title_result, "rag")
    assert result_id.startswith("rag:")


def test_cache_hit_rate_calculation():
    """Test cache hit rate calculation."""
    config = OrchestratorConfig()
    synthesizer = AdvancedSynthesizer(config)

    state = OrchestratorState(
        query="test",
        frame={},
        pubmed_results=None,
        ctgov_results=None,
        config={},
        routing_decision=None,
        rag_results=None,
        tool_calls_made=[],
        cache_hits={"tool1": True, "tool2": False, "tool3": True},
        latencies={},
        errors=[],
        node_path=[],
        answer=None,
        checkpoint_id=None,
        messages=[],
    )

    hit_rate = synthesizer._calculate_cache_hit_rate(state)
    assert hit_rate == 2 / 3  # 2 hits out of 3 tools

    # Test with no cache data
    state["cache_hits"] = {}
    hit_rate = synthesizer._calculate_cache_hit_rate(state)
    assert hit_rate == 0.0

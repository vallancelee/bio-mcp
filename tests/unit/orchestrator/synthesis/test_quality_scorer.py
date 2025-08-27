"""Test quality scoring functionality."""
import pytest
from datetime import datetime
from bio_mcp.orchestrator.synthesis.quality_scorer import QualityScorer, QualityMetrics
from bio_mcp.orchestrator.synthesis.synthesizer import Citation


def test_score_comprehensive_results():
    """Test quality scoring for comprehensive results."""
    scorer = QualityScorer()
    
    result_data = {
        "pubmed": {
            "results": [
                {"pmid": "1", "title": "Study 1", "journal": "Nature"},
                {"pmid": "2", "title": "Study 2", "journal": "Science"},
                {"pmid": "3", "title": "Meta-analysis of treatment", "journal": "NEJM"}
            ]
        },
        "clinicaltrials": {
            "results": [
                {"nct_id": "NCT1", "title": "Trial 1", "start_date": "2023-01-01"},
                {"nct_id": "NCT2", "title": "Trial 2", "start_date": "2022-06-01"}
            ]
        },
        "rag": {
            "results": [
                {"title": "Document 1", "score": 0.9},
                {"title": "Document 2", "score": 0.7}
            ]
        }
    }
    
    citations = [
        Citation(
            id="1", source="pubmed", title="Study 1", authors=["Author A"],
            journal="Nature", year=2023, relevance_score=0.8
        ),
        Citation(
            id="2", source="clinicaltrials", title="Trial 1", authors=["Sponsor A"],
            year=2023, relevance_score=0.7
        )
    ]
    
    quality = scorer.score_results(result_data, citations)
    
    assert isinstance(quality, QualityMetrics)
    assert quality.overall_score > 0
    assert quality.total_sources == 3
    assert quality.has_multiple_perspectives is True
    assert quality.completeness_score > 0.8  # All 3 sources present with results


def test_score_empty_results():
    """Test quality scoring for empty results."""
    scorer = QualityScorer()
    
    result_data = {
        "pubmed": {"results": []},
        "clinicaltrials": {"results": []},
        "rag": {"results": []}
    }
    
    citations = []
    
    quality = scorer.score_results(result_data, citations)
    
    assert quality.overall_score < 0.3  # Low score for empty results
    assert quality.total_sources == 3
    assert quality.has_multiple_perspectives is False
    assert quality.completeness_score == 0.6  # Base source coverage score


def test_completeness_scoring():
    """Test completeness score calculation."""
    scorer = QualityScorer()
    
    # Full coverage with results
    full_data = {
        "pubmed": {"results": [{"pmid": "1"}, {"pmid": "2"}]},
        "clinicaltrials": {"results": [{"nct_id": "NCT1"}]},
        "rag": {"results": [{"title": "Doc1"}]}
    }
    completeness = scorer._score_completeness(full_data)
    assert completeness > 0.8
    
    # Partial coverage
    partial_data = {
        "pubmed": {"results": [{"pmid": "1"}]},
        "clinicaltrials": {"results": []},
        "rag": {"results": []}
    }
    completeness = scorer._score_completeness(partial_data)
    assert completeness < 0.7  # Lower score for partial coverage
    
    # No coverage
    empty_data = {
        "pubmed": {"results": []},
        "clinicaltrials": {"results": []},
        "rag": {"results": []}
    }
    completeness = scorer._score_completeness(empty_data)
    assert completeness == 0.6  # Base source coverage score (3/3 sources present but no results)


def test_recency_scoring():
    """Test recency score calculation."""
    scorer = QualityScorer()
    current_year = datetime.now().year
    
    # All recent citations
    recent_citations = [
        Citation(id="1", source="pubmed", title="Study 1", authors=[], year=current_year),
        Citation(id="2", source="pubmed", title="Study 2", authors=[], year=current_year - 1)
    ]
    recency = scorer._score_recency(recent_citations)
    assert recency > 0.8
    
    # Mixed age citations
    mixed_citations = [
        Citation(id="1", source="pubmed", title="Study 1", authors=[], year=current_year),
        Citation(id="2", source="pubmed", title="Study 2", authors=[], year=current_year - 10)
    ]
    recency = scorer._score_recency(mixed_citations)
    assert 0.3 < recency < 0.8
    
    # No citations
    recency = scorer._score_recency([])
    assert recency == 0.0
    
    # Citations without years
    no_year_citations = [
        Citation(id="1", source="rag", title="Doc 1", authors=[], year=None)
    ]
    recency = scorer._score_recency(no_year_citations)
    assert recency == 0.0


def test_authority_scoring():
    """Test authority score calculation."""
    scorer = QualityScorer()
    
    # High-impact citations
    high_impact_citations = [
        Citation(
            id="1", source="pubmed", title="Important study", authors=["Author A"],
            journal="Nature", relevance_score=0.9
        ),
        Citation(
            id="2", source="pubmed", title="Systematic review", authors=["Author B"],
            journal="JAMA", relevance_score=0.8
        ),
        Citation(
            id="3", source="clinicaltrials", title="Phase 3 trial", authors=["Sponsor"],
            relevance_score=0.7
        )
    ]
    authority = scorer._score_authority(high_impact_citations)
    assert authority > 0.4  # Good authority score
    
    # Low authority citations
    low_authority_citations = [
        Citation(
            id="1", source="rag", title="Document", authors=[],
            journal=None, relevance_score=0.5
        )
    ]
    authority = scorer._score_authority(low_authority_citations)
    assert authority < 0.3


def test_diversity_scoring():
    """Test diversity score calculation."""
    scorer = QualityScorer()
    
    # High diversity - multiple sources and types
    diverse_data = {
        "pubmed": {"results": [{"pmid": "1"}]},
        "clinicaltrials": {"results": [{"nct_id": "NCT1"}]},
        "rag": {"results": [{"title": "Doc1"}]}
    }
    diverse_citations = [
        Citation(id="1", source="pubmed", title="Study", authors=[]),
        Citation(id="2", source="clinicaltrials", title="Trial", authors=[]),
        Citation(id="3", source="rag", title="Document", authors=[])
    ]
    diversity = scorer._score_diversity(diverse_data, diverse_citations)
    assert diversity == 1.0
    
    # Low diversity - single source
    single_source_data = {
        "pubmed": {"results": [{"pmid": "1"}]},
        "clinicaltrials": {"results": []},
        "rag": {"results": []}
    }
    single_citations = [
        Citation(id="1", source="pubmed", title="Study", authors=[])
    ]
    diversity = scorer._score_diversity(single_source_data, single_citations)
    assert diversity < 0.7


def test_relevance_scoring():
    """Test relevance score calculation."""
    scorer = QualityScorer()
    
    # High relevance citations
    high_rel_citations = [
        Citation(id="1", source="pubmed", title="Study", authors=[], relevance_score=0.9),
        Citation(id="2", source="pubmed", title="Study", authors=[], relevance_score=0.8)
    ]
    relevance = scorer._score_relevance(high_rel_citations)
    assert abs(relevance - 0.85) < 0.01  # Handle floating point precision
    
    # No citations
    relevance = scorer._score_relevance([])
    assert relevance == 0.0


def test_count_primary_sources():
    """Test primary source counting."""
    scorer = QualityScorer()
    
    citations = [
        Citation(id="1", source="pubmed", title="Study", authors=[], journal="Nature"),
        Citation(id="2", source="pubmed", title="Study", authors=[], journal="Unknown"),
        Citation(id="3", source="clinicaltrials", title="Trial", authors=[]),
        Citation(id="4", source="rag", title="Document", authors=[])
    ]
    
    count = scorer._count_primary_sources(citations)
    assert count == 2  # Nature journal + clinical trial


def test_count_recent_results():
    """Test recent results counting."""
    scorer = QualityScorer()
    current_year = datetime.now().year
    
    citations = [
        Citation(id="1", source="pubmed", title="Study", authors=[], year=current_year),
        Citation(id="2", source="pubmed", title="Study", authors=[], year=current_year - 1),
        Citation(id="3", source="pubmed", title="Study", authors=[], year=current_year - 5),
        Citation(id="4", source="pubmed", title="Study", authors=[], year=None)
    ]
    
    count = scorer._count_recent_results(citations)
    assert count == 2  # Within last 2 years


def test_count_high_impact():
    """Test high-impact publication counting."""
    scorer = QualityScorer()
    
    citations = [
        Citation(id="1", source="pubmed", title="Study", authors=[], journal="Nature"),
        Citation(id="2", source="pubmed", title="Study", authors=[], journal="Science"),
        Citation(id="3", source="pubmed", title="Study", authors=[], journal="Unknown Journal"),
        Citation(id="4", source="clinicaltrials", title="Trial", authors=[])
    ]
    
    count = scorer._count_high_impact(citations)
    assert count == 2  # Nature + Science


def test_has_systematic_reviews():
    """Test systematic review detection."""
    scorer = QualityScorer()
    
    # With systematic reviews
    with_reviews = [
        Citation(id="1", source="pubmed", title="Systematic review of treatments", authors=[]),
        Citation(id="2", source="pubmed", title="Regular study", authors=[])
    ]
    assert scorer._has_systematic_reviews(with_reviews) is True
    
    # Without systematic reviews
    without_reviews = [
        Citation(id="1", source="pubmed", title="Regular study", authors=[]),
        Citation(id="2", source="pubmed", title="Another study", authors=[])
    ]
    assert scorer._has_systematic_reviews(without_reviews) is False


def test_has_recent_trials():
    """Test recent clinical trials detection."""
    scorer = QualityScorer()
    current_year = datetime.now().year
    
    # With recent trials
    recent_trial_data = {
        "clinicaltrials": {
            "results": [
                {"nct_id": "NCT1", "start_date": f"{current_year - 1}-01-01"},
                {"nct_id": "NCT2", "start_date": "2010-01-01"}
            ]
        }
    }
    assert scorer._has_recent_trials(recent_trial_data) is True
    
    # Without recent trials
    old_trial_data = {
        "clinicaltrials": {
            "results": [
                {"nct_id": "NCT1", "start_date": "2010-01-01"},
                {"nct_id": "NCT2", "start_date": "2005-01-01"}
            ]
        }
    }
    assert scorer._has_recent_trials(old_trial_data) is False
    
    # No trial data
    no_trial_data = {"pubmed": {"results": []}}
    assert scorer._has_recent_trials(no_trial_data) is False


def test_has_multiple_perspectives():
    """Test multiple perspectives detection."""
    scorer = QualityScorer()
    
    # Multiple sources with results
    multi_source_data = {
        "pubmed": {"results": [{"pmid": "1"}]},
        "clinicaltrials": {"results": [{"nct_id": "NCT1"}]}
    }
    assert scorer._has_multiple_perspectives(multi_source_data) is True
    
    # Single source with results
    single_source_data = {
        "pubmed": {"results": [{"pmid": "1"}]},
        "clinicaltrials": {"results": []}
    }
    assert scorer._has_multiple_perspectives(single_source_data) is False


def test_detect_conflicts():
    """Test conflict detection."""
    scorer = QualityScorer()
    
    current_year = datetime.now().year
    
    # Old results
    old_citations = [
        Citation(id="1", source="pubmed", title="Study", authors=[], year=current_year - 15),
        Citation(id="2", source="pubmed", title="Study", authors=[], year=current_year - 12)
    ]
    
    limited_data = {"pubmed": {"results": [{"pmid": "1"}]}}
    
    conflicts = scorer._detect_conflicts(limited_data, old_citations)
    
    assert len(conflicts) > 0
    assert any("outdated" in conflict.lower() for conflict in conflicts)
    assert any("limited" in conflict.lower() for conflict in conflicts)


def test_quality_metrics_dataclass():
    """Test QualityMetrics dataclass structure."""
    metrics = QualityMetrics(
        completeness_score=0.8,
        recency_score=0.7,
        authority_score=0.6,
        diversity_score=0.9,
        relevance_score=0.8,
        overall_score=0.76,
        total_sources=3,
        primary_source_count=2,
        recent_results_count=5,
        high_impact_count=3,
        has_systematic_reviews=True,
        has_recent_trials=False,
        has_multiple_perspectives=True,
        potential_conflicts=["Limited data"]
    )
    
    assert metrics.completeness_score == 0.8
    assert metrics.overall_score == 0.76
    assert metrics.has_systematic_reviews is True
    assert metrics.potential_conflicts == ["Limited data"]
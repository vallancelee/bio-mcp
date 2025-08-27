"""Test template engine functionality."""

import pytest

from bio_mcp.orchestrator.synthesis.template_engine import TemplateEngine


@pytest.mark.asyncio
async def test_render_comprehensive_template():
    """Test rendering comprehensive answer template."""
    engine = TemplateEngine()

    context = {
        "query": "diabetes treatment",
        "timestamp": "2024-01-01T10:00:00",
        "frame": {
            "intent": "recent_pubs_by_topic",
            "entities": {"topic": "diabetes", "condition": "type 2 diabetes"},
        },
        "results": {
            "pubmed": {
                "results": [
                    {
                        "pmid": "123456",
                        "title": "Novel diabetes treatment",
                        "authors": ["Smith, J.", "Doe, A."],
                        "journal": "Nature Medicine",
                        "year": 2023,
                    }
                ]
            },
            "clinicaltrials": {
                "results": [
                    {
                        "nct_id": "NCT123456",
                        "title": "Phase 3 diabetes trial",
                        "phase": "Phase 3",
                        "status": "Recruiting",
                        "sponsor": "Pharma Corp",
                    }
                ]
            },
        },
        "citations": [
            {
                "id": "1",
                "source": "pubmed",
                "title": "Novel diabetes treatment",
                "authors": ["Smith, J.", "Doe, A."],
                "pmid": "123456",
            }
        ],
        "quality": {
            "overall_score": 0.85,
            "completeness_score": 0.9,
            "recency_score": 0.8,
            "authority_score": 0.7,
            "diversity_score": 0.9,
            "has_systematic_reviews": False,
            "has_recent_trials": True,
            "has_multiple_perspectives": True,
            "potential_conflicts": [],
        },
        "metrics": {
            "total_results": 2,
            "source_count": 2,
            "execution_time": 1500.0,
            "cache_hit_rate": 0.5,
        },
    }

    result = await engine.render("answer_comprehensive", context)

    assert isinstance(result, str)
    assert "diabetes treatment" in result
    assert "Biomedical Research Results" in result
    assert "Quality Assessment" in result
    assert "Results Summary" in result
    assert "References" in result
    assert "0.85/1.00" in result  # Overall quality score
    assert "PMIDs/NCTs" not in result or "PubMed" in result


@pytest.mark.asyncio
async def test_render_partial_template():
    """Test rendering partial answer template."""
    engine = TemplateEngine()

    context = {
        "query": "rare disease research",
        "results": {
            "pubmed": {"results": [{"pmid": "789", "title": "Rare disease study"}]}
        },
        "citations": [],
    }

    result = await engine.render("answer_partial", context)

    assert isinstance(result, str)
    assert "Research Results (Partial)" in result
    assert "rare disease research" in result
    assert "partial response" in result.lower()
    assert "unavailable" in result.lower()


@pytest.mark.asyncio
async def test_render_minimal_template():
    """Test rendering minimal answer template."""
    engine = TemplateEngine()

    context = {
        "query": "obscure medical condition",
        "results": {"pubmed": {"results": [{"pmid": "999", "title": "Single study"}]}},
    }

    result = await engine.render("answer_minimal", context)

    assert isinstance(result, str)
    assert "Research Results (Limited)" in result
    assert "obscure medical condition" in result
    assert "Limited results found" in result
    assert "refining your search" in result


@pytest.mark.asyncio
async def test_render_empty_template():
    """Test rendering empty results template."""
    engine = TemplateEngine()

    context = {"query": "non-existent condition"}

    result = await engine.render("answer_empty", context)

    assert isinstance(result, str)
    assert "No Results Found" in result
    assert "non-existent condition" in result
    assert "Suggestions:" in result
    assert "broader search terms" in result
    assert "PubMed, ClinicalTrials.gov" in result


def test_render_header():
    """Test header rendering."""
    engine = TemplateEngine()

    context = {
        "query": "test query",
        "timestamp": "2024-01-15T14:30:00",
        "frame": {
            "intent": "recent_pubs_by_topic",
            "entities": {"disease": "diabetes", "drug": "metformin"},
        },
    }

    header = engine._render_header(context)

    assert "Biomedical Research Results" in header
    assert "test query" in header
    assert "Recent Pubs By Topic" in header
    assert "2024-01-15 14:30:00 UTC" in header
    assert "**Disease:** diabetes" in header
    assert "**Drug:** metformin" in header


def test_render_quality_summary():
    """Test quality summary rendering."""
    engine = TemplateEngine()

    context = {
        "quality": {
            "overall_score": 0.75,
            "completeness_score": 0.8,
            "recency_score": 0.7,
            "authority_score": 0.9,
            "diversity_score": 0.6,
            "has_systematic_reviews": True,
            "has_recent_trials": False,
            "has_multiple_perspectives": True,
            "potential_conflicts": ["Results may be outdated", "Limited data"],
        }
    }

    quality_summary = engine._render_quality_summary(context)

    assert "Quality Assessment" in quality_summary
    assert "0.75/1.00" in quality_summary
    assert "**Completeness:** 0.80" in quality_summary
    assert "✅ Includes systematic reviews" in quality_summary
    assert "✅ Multiple perspectives represented" in quality_summary
    assert "⚠️ Results may be outdated" in quality_summary
    assert "⚠️ Limited data" in quality_summary


def test_render_quality_summary_empty():
    """Test quality summary with no quality data."""
    engine = TemplateEngine()

    context = {}

    quality_summary = engine._render_quality_summary(context)

    assert quality_summary == ""


def test_render_results_by_source():
    """Test results summary by source."""
    engine = TemplateEngine()

    context = {
        "results": {
            "pubmed": {
                "results": [
                    {
                        "pmid": "123",
                        "title": "Study 1",
                        "authors": ["Author A", "Author B"],
                        "journal": "Nature",
                        "year": 2023,
                    },
                    {
                        "pmid": "456",
                        "title": "Study 2",
                        "authors": ["Author C"],
                        "journal": "Science",
                    },
                ]
            },
            "clinicaltrials": {
                "results": [
                    {
                        "nct_id": "NCT123",
                        "title": "Important Trial",
                        "phase": "Phase 3",
                        "status": "Recruiting",
                        "sponsor": "Big Pharma",
                    }
                ]
            },
        }
    }

    results_summary = engine._render_results_by_source(context)

    assert "Results Summary" in results_summary
    assert "📚 PubMed Publications (2 found)" in results_summary
    assert "🧪 Clinical Trials (1 found)" in results_summary
    assert "Study 1" in results_summary
    assert "Important Trial" in results_summary
    assert "Authors: Author A, Author B" in results_summary
    assert "Phase: Phase 3" in results_summary


def test_format_pubmed_result():
    """Test PubMed result formatting."""
    engine = TemplateEngine()

    result = {
        "pmid": "789123",
        "title": "Breakthrough Medical Research",
        "authors": ["Dr. Smith", "Prof. Johnson", "Dr. Brown", "Dr. Extra"],
        "journal": "The Lancet",
        "year": 2024,
    }

    formatted = engine._format_pubmed_result(1, result)

    assert "1. **Breakthrough Medical Research**" in formatted
    assert "Authors: Dr. Smith, Prof. Johnson, Dr. Brown et al." in formatted
    assert "Journal: The Lancet (2024)" in formatted
    assert "PMID: [789123](https://pubmed.ncbi.nlm.nih.gov/789123)" in formatted


def test_format_trial_result():
    """Test clinical trial result formatting."""
    engine = TemplateEngine()

    result = {
        "nct_id": "NCT456789",
        "title": "Innovative Cancer Treatment",
        "phase": "Phase 2/3",
        "status": "Active, not recruiting",
        "sponsor": "University Hospital",
    }

    formatted = engine._format_trial_result(2, result)

    assert "2. **Innovative Cancer Treatment**" in formatted
    assert "Phase: Phase 2/3" in formatted
    assert "Status: Active, not recruiting" in formatted
    assert "Sponsor: University Hospital" in formatted
    assert (
        "ClinicalTrials.gov: [NCT456789](https://clinicaltrials.gov/ct2/show/NCT456789)"
        in formatted
    )


def test_format_rag_result():
    """Test RAG result formatting."""
    engine = TemplateEngine()

    result = {
        "title": "Important Medical Document",
        "score": 0.923,
        "snippet": "This document contains important information about medical treatments and their effectiveness in clinical practice and research.",
    }

    formatted = engine._format_rag_result(3, result)

    assert "3. **Important Medical Document**" in formatted
    assert "Relevance Score: 0.923" in formatted
    assert "This document contains important information" in formatted


def test_render_key_findings():
    """Test key findings rendering."""
    engine = TemplateEngine()

    context = {
        "results": {
            "pubmed": {"results": [{"pmid": "1"}, {"pmid": "2"}, {"pmid": "3"}]},
            "clinicaltrials": {"results": [{"nct_id": "NCT1"}, {"nct_id": "NCT2"}]},
        }
    }

    findings = engine._render_key_findings(context)

    assert "Key Findings" in findings
    assert "**5 total results** found across all sources" in findings
    assert "**3 Pubmed results** identified" in findings
    assert "**2 Clinicaltrials results** identified" in findings


def test_render_citations():
    """Test citations rendering."""
    engine = TemplateEngine()

    context = {
        "citations": [
            {
                "id": "1",
                "authors": ["Smith, J.", "Doe, A.", "Johnson, B."],
                "title": "Important Study",
                "journal": "Nature",
                "year": 2023,
                "pmid": "123456",
            },
            {
                "id": "2",
                "authors": ["Brown, C."],
                "title": "Clinical Trial Results",
                "nct_id": "NCT789",
                "year": 2024,
            },
        ]
    }

    citations = engine._render_citations(context)

    assert "References" in citations
    assert (
        "1. Smith, J., Doe, A., Johnson, B.. Important Study. *Nature*. 2023. PMID: [123456](https://pubmed.ncbi.nlm.nih.gov/123456)"
        in citations
    )
    assert (
        "2. Brown, C.. Clinical Trial Results. 2024. ClinicalTrials.gov: [NCT789](https://clinicaltrials.gov/ct2/show/NCT789)"
        in citations
    )


def test_render_citations_empty():
    """Test citations rendering with no citations."""
    engine = TemplateEngine()

    context = {"citations": []}

    citations = engine._render_citations(context)

    assert citations == ""


def test_render_footer():
    """Test footer rendering."""
    engine = TemplateEngine()

    context = {
        "metrics": {"execution_time": 2500.5, "cache_hit_rate": 0.75, "source_count": 3}
    }

    footer = engine._render_footer(context)

    assert "Execution Summary:" in footer
    assert "Total execution time: 2500.5ms" in footer
    assert "Cache hit rate: 75.0%" in footer
    assert "Sources queried: 3" in footer
    assert "Generated by Bio-MCP Orchestrator" in footer


@pytest.mark.asyncio
async def test_default_template_fallback():
    """Test fallback to comprehensive template."""
    engine = TemplateEngine()

    context = {
        "query": "test query",
        "timestamp": "2024-01-01T00:00:00",
        "results": {},
        "citations": [],
        "quality": {},
        "metrics": {},
    }

    # Use non-existent template name
    result = await engine.render("non_existent_template", context)

    # Should fallback to comprehensive template
    assert isinstance(result, str)
    assert "Biomedical Research Results" in result

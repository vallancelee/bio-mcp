"""Test citation extraction functionality."""

import pytest

from bio_mcp.orchestrator.synthesis.citation_extractor import CitationExtractor


@pytest.mark.asyncio
async def test_extract_citations_from_multiple_sources():
    """Test citation extraction from multiple data sources."""
    extractor = CitationExtractor()

    result_data = {
        "pubmed": {
            "results": [
                {
                    "pmid": "12345678",
                    "title": "A comprehensive study of diabetes management",
                    "authors": ["Smith, J.", "Doe, A.", "Johnson, B."],
                    "journal": "Nature Medicine",
                    "publication_date": "2023-01-15",
                }
            ]
        },
        "clinicaltrials": {
            "results": [
                {
                    "nct_id": "NCT12345678",
                    "title": "Phase 3 trial of new diabetes medication",
                    "phase": "Phase 3",
                    "status": "Recruiting",
                    "sponsor": "Pharma Corp",
                    "start_date": "2023-06-01",
                }
            ]
        },
    }

    citations = await extractor.extract_citations(result_data)

    assert len(citations) == 2
    assert citations[0].source in ["pubmed", "clinicaltrials"]
    assert citations[1].source in ["pubmed", "clinicaltrials"]
    # Should be sorted by relevance score
    assert citations[0].relevance_score >= citations[1].relevance_score


@pytest.mark.asyncio
async def test_extract_pubmed_citations():
    """Test PubMed citation extraction."""
    extractor = CitationExtractor()

    results = [
        {
            "pmid": "123456",
            "title": "Important Medical Study",
            "authors": ["Author, A.", "Researcher, B.", "Scientist, C.", "Extra, D."],
            "journal": "Nature",
            "publication_date": "2023-03-15",
        }
    ]

    citations = extractor._extract_pubmed_citations(results)

    assert len(citations) == 1
    citation = citations[0]
    assert citation.source == "pubmed"
    assert citation.title == "Important Medical Study"
    assert len(citation.authors) == 3  # Should limit to first 3
    assert citation.authors == ["Author, A.", "Researcher, B.", "Scientist, C."]
    assert citation.journal == "Nature"
    assert citation.year == 2023
    assert citation.pmid == "123456"
    assert citation.url == "https://pubmed.ncbi.nlm.nih.gov/123456"
    assert citation.relevance_score > 0


@pytest.mark.asyncio
async def test_extract_clinical_trial_citations():
    """Test clinical trial citation extraction."""
    extractor = CitationExtractor()

    results = [
        {
            "nct_id": "NCT98765432",
            "title": "Innovative Cancer Treatment Trial",
            "phase": "Phase 2",
            "status": "Active, not recruiting",
            "sponsor": "Big Pharma Inc",
            "start_date": "2022-09-10",
            "enrollment": 250,
        }
    ]

    citations = extractor._extract_clinical_trial_citations(results)

    assert len(citations) == 1
    citation = citations[0]
    assert citation.source == "clinicaltrials"
    assert citation.title == "Innovative Cancer Treatment Trial"
    assert citation.authors == ["Big Pharma Inc"]
    assert citation.year == 2022
    assert citation.nct_id == "NCT98765432"
    assert citation.url == "https://clinicaltrials.gov/ct2/show/NCT98765432"
    assert citation.relevance_score > 0


@pytest.mark.asyncio
async def test_extract_rag_citations():
    """Test RAG citation extraction."""
    extractor = CitationExtractor()

    results = [
        {
            "title": "Research Document",
            "score": 0.85,
            "url": "https://example.com/doc1",
        },
        {"title": "Another Document", "score": 0.72},
    ]

    citations = extractor._extract_rag_citations(results)

    assert len(citations) == 2
    citation1, citation2 = citations
    assert citation1.source == "rag"
    assert citation1.title == "Research Document"
    assert citation1.authors == []
    assert citation1.relevance_score == 0.85
    assert citation1.url == "https://example.com/doc1"

    assert citation2.source == "rag"
    assert citation2.title == "Another Document"
    assert citation2.relevance_score == 0.72
    assert citation2.url is None


def test_calculate_pubmed_relevance():
    """Test PubMed relevance score calculation."""
    extractor = CitationExtractor()

    # Recent publication in high-impact journal
    recent_high_impact = {
        "publication_date": "2024-01-01",
        "journal": "Nature Medicine",
    }
    score = extractor._calculate_pubmed_relevance(recent_high_impact)
    assert score >= 0.8  # Should get high score

    # Old publication in unknown journal
    old_unknown = {"publication_date": "2010-01-01", "journal": "Unknown Journal"}
    score = extractor._calculate_pubmed_relevance(old_unknown)
    assert score == 0.5  # Should get base score only

    # No date or journal info
    minimal = {}
    score = extractor._calculate_pubmed_relevance(minimal)
    assert score == 0.5  # Should get base score only


def test_calculate_trial_relevance():
    """Test clinical trial relevance score calculation."""
    extractor = CitationExtractor()

    # Phase 3 recruiting large trial
    phase3_recruiting_large = {
        "phase": "Phase 3",
        "status": "Recruiting",
        "enrollment": 1500,
    }
    score = extractor._calculate_trial_relevance(phase3_recruiting_large)
    assert score > 0.8  # Should get high score

    # Phase 1 completed small trial
    phase1_completed_small = {
        "phase": "Phase 1",
        "status": "Completed",
        "enrollment": 20,
    }
    score = extractor._calculate_trial_relevance(phase1_completed_small)
    assert score == 0.5  # Should get base score only

    # No phase/status/enrollment info
    minimal = {}
    score = extractor._calculate_trial_relevance(minimal)
    assert score == 0.5  # Should get base score only


@pytest.mark.asyncio
async def test_empty_results():
    """Test citation extraction with empty results."""
    extractor = CitationExtractor()

    result_data = {
        "pubmed": {"results": []},
        "clinicaltrials": {"results": []},
        "rag": {"results": []},
    }

    citations = await extractor.extract_citations(result_data)

    assert citations == []


@pytest.mark.asyncio
async def test_citation_counter_increments():
    """Test that citation counter increments properly."""
    extractor = CitationExtractor()

    result_data = {
        "pubmed": {
            "results": [
                {"pmid": "111", "title": "Study 1"},
                {"pmid": "222", "title": "Study 2"},
            ]
        }
    }

    citations = await extractor.extract_citations(result_data)

    assert len(citations) == 2
    assert citations[0].id == "1"
    assert citations[1].id == "2"


def test_handle_malformed_author_strings():
    """Test handling of malformed author strings."""
    extractor = CitationExtractor()

    # String authors instead of list
    results = [
        {
            "pmid": "123",
            "title": "Test Study",
            "authors": "Smith J, Doe A, Johnson B, Extra D",
            "journal": "Test Journal",
        }
    ]

    citations = extractor._extract_pubmed_citations(results)
    citation = citations[0]

    # Should be converted to list and limited to 3
    assert isinstance(citation.authors, list)
    assert len(citation.authors) <= 3


def test_handle_invalid_dates():
    """Test handling of invalid publication dates."""
    extractor = CitationExtractor()

    # Invalid date format
    results = [
        {
            "pmid": "123",
            "title": "Test Study",
            "publication_date": "invalid-date-format",
        }
    ]

    citations = extractor._extract_pubmed_citations(results)
    citation = citations[0]

    # Should handle gracefully
    assert citation.year is None


@pytest.mark.asyncio
async def test_citation_sorting_by_relevance():
    """Test that citations are sorted by relevance score."""
    extractor = CitationExtractor()

    result_data = {
        "rag": {
            "results": [
                {"title": "Low Score Doc", "score": 0.3},
                {"title": "High Score Doc", "score": 0.9},
                {"title": "Medium Score Doc", "score": 0.6},
            ]
        }
    }

    citations = await extractor.extract_citations(result_data)

    # Should be sorted by relevance score (descending)
    assert citations[0].title == "High Score Doc"
    assert citations[1].title == "Medium Score Doc"
    assert citations[2].title == "Low Score Doc"

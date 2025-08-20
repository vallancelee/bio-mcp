"""
Unit tests for PubMed document models.
"""

from datetime import datetime

import pytest

from bio_mcp.sources.pubmed.models import PubMedDocument


class TestPubMedDocument:
    """Test PubMed document model functionality."""
    
    def test_default_initialization(self):
        """Test document initialization with defaults."""
        doc = PubMedDocument(
            id="",
            source_id="",
            source="",
            title="Test Title"
        )
        
        assert doc.title == "Test Title"
        assert doc.pmid == ""
        assert doc.journal is None
        assert doc.doi is None
        assert doc.mesh_terms == []
        assert doc.keywords == []
        assert doc.impact_factor is None
        assert doc.citation_count == 0
    
    def test_pmid_initialization(self):
        """Test document initialization with PMID."""
        doc = PubMedDocument(
            id="",
            source_id="",
            source="",
            title="Test Title",
            pmid="12345"
        )
        
        # __post_init__ should set these fields
        assert doc.pmid == "12345"
        assert doc.source == "pubmed"
        assert doc.source_id == "12345"
        assert doc.id == "pubmed:12345"
    
    def test_post_init_only_sets_if_pmid_provided(self):
        """Test __post_init__ only sets fields when PMID is provided."""
        doc = PubMedDocument(
            id="custom:123",
            source_id="custom_id",
            source="custom",
            title="Test Title"
            # pmid defaults to ""
        )
        
        # Should not override existing values when pmid is empty
        assert doc.source == "custom"
        assert doc.source_id == "custom_id"
        assert doc.id == "custom:123"
    
    def test_get_search_content_title_only(self):
        """Test search content with title only."""
        doc = PubMedDocument(
            id="pubmed:123",
            source_id="123",
            source="pubmed",
            title="Biomarker Discovery",
            pmid="123"
        )
        
        content = doc.get_search_content()
        assert content == "Biomarker Discovery"
    
    def test_get_search_content_with_abstract(self):
        """Test search content with title and abstract."""
        doc = PubMedDocument(
            id="pubmed:123",
            source_id="123", 
            source="pubmed",
            title="Biomarker Discovery",
            abstract="This study investigates novel biomarkers.",
            pmid="123"
        )
        
        content = doc.get_search_content()
        assert content == "Biomarker Discovery This study investigates novel biomarkers."
    
    def test_get_search_content_with_mesh_terms(self):
        """Test search content includes MeSH terms."""
        doc = PubMedDocument(
            id="pubmed:123",
            source_id="123",
            source="pubmed", 
            title="Cancer Research",
            mesh_terms=["Neoplasms", "Biomarkers", "Drug Therapy"],
            pmid="123"
        )
        
        content = doc.get_search_content()
        assert content == "Cancer Research Neoplasms Biomarkers Drug Therapy"
    
    def test_get_search_content_with_keywords(self):
        """Test search content includes keywords."""
        doc = PubMedDocument(
            id="pubmed:123",
            source_id="123",
            source="pubmed",
            title="Immunotherapy",
            keywords=["CAR-T", "checkpoint inhibitor", "precision medicine"],
            pmid="123"
        )
        
        content = doc.get_search_content()
        assert content == "Immunotherapy CAR-T checkpoint inhibitor precision medicine"
    
    def test_get_search_content_comprehensive(self):
        """Test search content with all fields."""
        doc = PubMedDocument(
            id="pubmed:123",
            source_id="123",
            source="pubmed",
            title="Cancer Immunotherapy",
            abstract="Novel approach to treating cancer using immune system.",
            mesh_terms=["Immunotherapy", "Neoplasms"],
            keywords=["CAR-T", "precision medicine"],
            pmid="123"
        )
        
        content = doc.get_search_content()
        expected = "Cancer Immunotherapy Novel approach to treating cancer using immune system. Immunotherapy Neoplasms CAR-T precision medicine"
        assert content == expected
    
    def test_get_display_title_without_journal(self):
        """Test display title without journal information."""
        doc = PubMedDocument(
            id="pubmed:123",
            source_id="123",
            source="pubmed",
            title="Breakthrough in Gene Therapy",
            pmid="123"
        )
        
        display_title = doc.get_display_title()
        assert display_title == "Breakthrough in Gene Therapy"
    
    def test_get_display_title_with_journal(self):
        """Test display title with journal information."""
        doc = PubMedDocument(
            id="pubmed:123",
            source_id="123",
            source="pubmed",
            title="Breakthrough in Gene Therapy",
            journal="Nature Biotechnology",
            pmid="123"
        )
        
        display_title = doc.get_display_title()
        assert display_title == "Breakthrough in Gene Therapy (Nature Biotechnology)"
    
    def test_comprehensive_document_creation(self):
        """Test creating a comprehensive PubMed document."""
        publication_date = datetime(2023, 6, 15)
        
        doc = PubMedDocument(
            id="",  # Will be set by __post_init__
            source_id="",  # Will be set by __post_init__
            source="",  # Will be set by __post_init__
            title="Novel CAR-T Cell Therapy for Solid Tumors",
            abstract="This phase II trial demonstrates efficacy of modified CAR-T cells.",
            content="Full paper content here...",
            authors=["Smith J", "Johnson A", "Wilson B"],
            publication_date=publication_date,
            metadata={"study_type": "clinical_trial"},
            quality_score=85,
            pmid="34567890",
            journal="Cell",
            doi="10.1016/j.cell.2023.06.001",
            mesh_terms=["Immunotherapy", "Neoplasms", "T-Lymphocytes"],
            keywords=["CAR-T", "solid tumors", "immunotherapy"],
            impact_factor=38.637,
            citation_count=42
        )
        
        # Test __post_init__ behavior
        assert doc.source == "pubmed"
        assert doc.source_id == "34567890"
        assert doc.id == "pubmed:34567890"
        
        # Test all fields
        assert doc.title == "Novel CAR-T Cell Therapy for Solid Tumors"
        assert doc.abstract == "This phase II trial demonstrates efficacy of modified CAR-T cells."
        assert doc.authors == ["Smith J", "Johnson A", "Wilson B"]
        assert doc.publication_date == publication_date
        assert doc.quality_score == 85
        assert doc.pmid == "34567890"
        assert doc.journal == "Cell"
        assert doc.doi == "10.1016/j.cell.2023.06.001"
        assert doc.mesh_terms == ["Immunotherapy", "Neoplasms", "T-Lymphocytes"]
        assert doc.keywords == ["CAR-T", "solid tumors", "immunotherapy"]
        assert doc.impact_factor == 38.637
        assert doc.citation_count == 42
        
        # Test methods
        search_content = doc.get_search_content()
        assert "Novel CAR-T Cell Therapy for Solid Tumors" in search_content
        assert "Immunotherapy" in search_content
        assert "CAR-T" in search_content
        
        display_title = doc.get_display_title()
        assert display_title == "Novel CAR-T Cell Therapy for Solid Tumors (Cell)"


# Mark as unit tests
pytestmark = pytest.mark.unit
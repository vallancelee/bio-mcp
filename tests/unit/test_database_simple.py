"""
Simple database tests to verify TDD implementation works.
Testing basic functionality before full testcontainer integration.
"""

from datetime import date, datetime

import pytest

from bio_mcp.database import DatabaseConfig, DatabaseManager, PubMedDocument
from bio_mcp.error_handling import ValidationError


class TestDatabaseModels:
    """Test SQLAlchemy models for biomedical data."""
    
    def test_pubmed_document_model_creation(self):
        """Test PubMedDocument model creation and validation."""
        doc = PubMedDocument(
            pmid="12345678",
            title="CRISPR-Cas9 gene editing in human embryos",
            abstract="Abstract text here...",
            authors=["Smith, J.", "Doe, A.", "Johnson, B."],
            publication_date=date(2023, 6, 15),
            journal="Nature",
            doi="10.1038/nature12345",
            keywords=["CRISPR", "gene editing", "embryos"]
        )
        
        assert doc.pmid == "12345678"
        assert doc.title == "CRISPR-Cas9 gene editing in human embryos"
        assert doc.abstract == "Abstract text here..."
        assert len(doc.authors) == 3
        assert doc.authors[0] == "Smith, J."
        assert doc.publication_date == date(2023, 6, 15)
        assert doc.journal == "Nature"
        assert doc.doi == "10.1038/nature12345"
        assert "CRISPR" in doc.keywords
        assert isinstance(doc.created_at, datetime)
        assert isinstance(doc.updated_at, datetime)
    
    def test_pubmed_document_model_validation(self):
        """Test model validation requirements."""
        # Test required fields
        with pytest.raises(ValidationError):
            PubMedDocument(pmid=None, title="Missing PMID")
        
        with pytest.raises(ValidationError):
            PubMedDocument(pmid="12345678", title=None)
    
    def test_pubmed_document_model_defaults(self):
        """Test model default values."""
        doc = PubMedDocument(
            pmid="12345678",
            title="Test title"
        )
        
        assert doc.abstract is None
        assert doc.authors == []
        assert doc.publication_date is None
        assert doc.journal is None
        assert doc.doi is None
        assert doc.keywords == []
        assert doc.created_at is not None
        assert doc.updated_at is not None


class TestDatabaseConfig:
    """Test database configuration management."""
    
    def test_database_config_creation(self):
        """Test database configuration object."""
        config = DatabaseConfig(
            url="postgresql+asyncpg://user:pass@localhost:5432/testdb",
            pool_size=10,
            max_overflow=20,
            pool_timeout=30.0,
            echo=True
        )
        
        assert config.url == "postgresql+asyncpg://user:pass@localhost:5432/testdb"
        assert config.pool_size == 10
        assert config.max_overflow == 20
        assert config.pool_timeout == 30.0
        assert config.echo is True
    
    def test_database_config_defaults(self):
        """Test default configuration values."""
        config = DatabaseConfig()
        
        assert config.pool_size == 5
        assert config.max_overflow == 10
        assert config.pool_timeout == 30.0
        assert config.echo is False
        assert config.url is None


class TestDatabaseManager:
    """Test database manager basic functionality."""
    
    def test_database_manager_creation(self):
        """Test DatabaseManager creation."""
        config = DatabaseConfig(url="postgresql+asyncpg://test:test@localhost:5432/testdb")
        manager = DatabaseManager(config)
        
        assert manager.config == config
        assert manager.engine is None  # Not initialized yet
        assert manager.session_factory is None
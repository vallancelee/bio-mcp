"""
Contract test fixtures and configuration.

Provides minimal fixtures needed for contract testing without heavy integration dependencies.
"""

import pytest
from typing import Dict, Any, List

@pytest.fixture
def sample_pubmed_raw_data() -> Dict[str, Any]:
    """Sample raw PubMed data for contract testing."""
    return {
        "pmid": "12345678",
        "title": "Test Document for Contract Validation", 
        "abstract": "This is a test abstract for contract validation purposes.",
        "authors": ["Smith, John A", "Johnson, Mary B"],
        "journal": "Test Journal",
        "publication_date": "2023-06-15",
        "doi": "10.1000/test.doi",
        "mesh_terms": ["Neoplasms", "Drug Therapy"],
        "pub_types": ["Journal Article", "Research Support"]
    }

@pytest.fixture  
def sample_documents():
    """Mock sample documents fixture for contract tests."""
    # Return empty list - contract tests should work with mock responses
    return []

@pytest.fixture
def sample_checkpoint():
    """Mock checkpoint fixture for contract tests."""
    return "test_checkpoint_contract"
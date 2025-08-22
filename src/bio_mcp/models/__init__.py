"""
Multi-source document models for Bio-MCP.

This package provides the core abstractions for handling documents from multiple
biomedical sources (PubMed, ClinicalTrials.gov, etc.) with a stable, minimal
base model that allows source-specific extensions.
"""

from .document import Chunk, Document

__all__ = ["Chunk", "Document"]

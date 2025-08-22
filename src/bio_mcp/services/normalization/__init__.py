"""
Document normalization services for multi-source biomedical data.

This package provides normalizers that convert source-specific document formats
into the common Document model for downstream processing.
"""

from .pubmed import PubMedNormalizer

__all__ = ["PubMedNormalizer"]
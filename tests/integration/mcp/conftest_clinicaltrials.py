"""
ClinicalTrials.gov-specific test configuration.

Provides test fixtures with conservative rate limiting for integration tests.
"""

import os

import pytest_asyncio

from bio_mcp.sources.clinicaltrials.config import ClinicalTrialsConfig
from bio_mcp.services.services import get_service_manager


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_clinicaltrials_rate_limiting():
    """
    Auto-setup conservative rate limiting for ClinicalTrials tests.
    
    Sets environment variables to use more conservative rate limiting
    during integration tests to avoid hitting API limits.
    """
    # Store original values
    original_rate_limit = os.environ.get("BIO_MCP_CTGOV_RATE_LIMIT")
    original_timeout = os.environ.get("BIO_MCP_CTGOV_TIMEOUT")
    
    # Set conservative test values
    # Reduce to 2 requests per second (well below the 5/second limit)
    os.environ["BIO_MCP_CTGOV_RATE_LIMIT"] = "2"
    # Increase timeout to handle potential delays
    os.environ["BIO_MCP_CTGOV_TIMEOUT"] = "45.0"
    
    yield
    
    # Restore original values
    if original_rate_limit is not None:
        os.environ["BIO_MCP_CTGOV_RATE_LIMIT"] = original_rate_limit
    else:
        os.environ.pop("BIO_MCP_CTGOV_RATE_LIMIT", None)
        
    if original_timeout is not None:
        os.environ["BIO_MCP_CTGOV_TIMEOUT"] = original_timeout  
    else:
        os.environ.pop("BIO_MCP_CTGOV_TIMEOUT", None)


@pytest_asyncio.fixture(scope="function")
async def conservative_clinicaltrials_config() -> ClinicalTrialsConfig:
    """
    Provide a ClinicalTrials configuration with conservative rate limiting.
    """
    return ClinicalTrialsConfig(
        base_url="https://clinicaltrials.gov/api/v2",
        rate_limit_per_second=2,  # Very conservative
        timeout=45.0,  # Longer timeout
        retries=2,  # Fewer retries to reduce total calls
        page_size=10,  # Smaller page size
    )


@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_service_manager():
    """Clean up service manager between tests to prevent event loop issues."""
    yield
    
    # Clean up the service manager after each test
    service_manager = get_service_manager()
    
    # Clean up ClinicalTrials service if it exists
    if service_manager._clinicaltrials_service:
        try:
            await service_manager._clinicaltrials_service.cleanup()
        except Exception:
            pass  # Ignore cleanup errors
        service_manager._clinicaltrials_service = None
    
    # Clean up other services
    if service_manager._pubmed_service:
        try:
            await service_manager._pubmed_service.close()
        except Exception:
            pass
        service_manager._pubmed_service = None
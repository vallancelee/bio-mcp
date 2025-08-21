"""Lifecycle management for HTTP adapter - startup, shutdown, health checks."""

import os

from bio_mcp.http.health.database import DatabaseHealthChecker
from bio_mcp.http.health.interface import HealthCheckResult
from bio_mcp.http.health.orchestrator import HealthOrchestrator
from bio_mcp.http.health.weaviate import WeaviateHealthChecker

# Global health orchestrator instance
_health_orchestrator: HealthOrchestrator | None = None


def get_health_orchestrator() -> HealthOrchestrator:
    """Get or create the global health orchestrator.
    
    Returns:
        Configured health orchestrator instance
    """
    global _health_orchestrator
    
    if _health_orchestrator is None:
        _health_orchestrator = HealthOrchestrator(cache_ttl_seconds=30.0)
        
        # Add database health checker if configured
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            db_checker = DatabaseHealthChecker(database_url, timeout_seconds=5.0)
            _health_orchestrator.add_checker(db_checker)
        
        # Add Weaviate health checker if configured
        weaviate_url = os.getenv("WEAVIATE_URL")
        if weaviate_url:
            weaviate_checker = WeaviateHealthChecker(weaviate_url, timeout_seconds=5.0)
            _health_orchestrator.add_checker(weaviate_checker)
    
    return _health_orchestrator


async def check_readiness() -> bool:
    """Check if all dependencies are ready.
    
    Enhanced in T2 with actual dependency checks for:
    - Database connectivity and schema
    - Weaviate connectivity and classes
    
    Returns:
        True if all dependencies are ready, False otherwise.
    """
    orchestrator = get_health_orchestrator()
    result = await orchestrator.check_all()
    return result.healthy


async def get_health_status() -> HealthCheckResult:
    """Get detailed health status for all dependencies.
    
    Returns:
        HealthCheckResult with detailed status information
    """
    orchestrator = get_health_orchestrator()
    return await orchestrator.check_all()


async def startup() -> None:
    """Application startup tasks.
    
    Currently a no-op, but will be used in later phases for:
    - Database connection pool initialization
    - Weaviate client setup
    - Other service initialization
    """
    pass


async def shutdown() -> None:
    """Application shutdown tasks.
    
    Currently a no-op, but will be used in later phases for:
    - Graceful database connection cleanup
    - Service shutdown procedures
    """
    pass
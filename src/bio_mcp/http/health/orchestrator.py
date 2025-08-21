"""Health check orchestrator with caching and concurrent execution."""

import asyncio
import time
from typing import Any

from bio_mcp.http.health.interface import HealthChecker, HealthCheckResult


class HealthOrchestrator:
    """Orchestrates multiple health checkers with caching."""
    
    def __init__(self, cache_ttl_seconds: float = 30.0):
        """Initialize health orchestrator.
        
        Args:
            cache_ttl_seconds: Cache TTL for health check results
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self.checkers: list[HealthChecker] = []
        self._cache: HealthCheckResult | None = None
        self._cache_timestamp: float | None = None
    
    def add_checker(self, checker: HealthChecker) -> None:
        """Add a health checker to the orchestrator.
        
        Args:
            checker: Health checker to add
        """
        self.checkers.append(checker)
    
    async def check_all(self) -> HealthCheckResult:
        """Check health of all registered checkers.
        
        Returns cached results if within TTL, otherwise executes all checks
        concurrently and caches the result.
        
        Returns:
            HealthCheckResult with overall system health
        """
        # Check cache
        if self._is_cache_valid():
            # Return new result indicating cache hit
            return HealthCheckResult(
                healthy=self._cache.healthy,
                message=self._cache.message,
                details=self._cache.details,
                check_duration_ms=0.1,  # Indicate cache hit
                checker_name=self._cache.checker_name
            )
        
        start_time = time.time()
        
        # No checkers configured
        if not self.checkers:
            result = HealthCheckResult(
                healthy=True,
                message="System healthy: no health checkers configured",
                details={
                    "total_checks": 0,
                    "healthy_checks": 0,
                    "failed_checks": 0,
                    "checks": []
                },
                check_duration_ms=(time.time() - start_time) * 1000,
                checker_name="orchestrator"
            )
            self._cache_result(result)
            return result
        
        # Run all checks concurrently
        check_tasks = [
            self._run_checker_safely(checker) 
            for checker in self.checkers
        ]
        
        check_results = await asyncio.gather(*check_tasks)
        
        # Analyze results
        healthy_results = [r for r in check_results if r["healthy"]]
        failed_results = [r for r in check_results if not r["healthy"]]
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Determine overall health
        overall_healthy = len(failed_results) == 0
        
        if overall_healthy:
            message = f"All systems healthy: {len(check_results)} checks passed"
        else:
            message = f"System degraded: {len(failed_results)} of {len(check_results)} checks failed"
        
        result = HealthCheckResult(
            healthy=overall_healthy,
            message=message,
            details={
                "total_checks": len(check_results),
                "healthy_checks": len(healthy_results),
                "failed_checks": len(failed_results),
                "failed_checkers": [r["checker"] for r in failed_results],
                "checks": check_results
            },
            check_duration_ms=duration_ms,
            checker_name="orchestrator"
        )
        
        # Cache the result
        self._cache_result(result)
        
        return result
    
    async def _run_checker_safely(self, checker: HealthChecker) -> dict[str, Any]:
        """Run a single health checker safely.
        
        Args:
            checker: Health checker to run
            
        Returns:
            Dict with checker result and metadata
        """
        try:
            result = await checker.check_health()
            return {
                "checker": checker.name,
                "healthy": result.healthy,
                "message": result.message,
                "details": result.details,
                "duration_ms": result.check_duration_ms
            }
        except Exception as e:
            return {
                "checker": checker.name,
                "healthy": False,
                "message": f"Health check failed: {e!s}",
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": 0.0
            }
    
    def _is_cache_valid(self) -> bool:
        """Check if cached result is still valid.
        
        Returns:
            True if cache is valid, False otherwise
        """
        if self._cache is None or self._cache_timestamp is None:
            return False
        
        cache_age = time.time() - self._cache_timestamp
        return cache_age < self.cache_ttl_seconds
    
    def _cache_result(self, result: HealthCheckResult) -> None:
        """Cache a health check result.
        
        Args:
            result: Result to cache
        """
        self._cache = result
        self._cache_timestamp = time.time()
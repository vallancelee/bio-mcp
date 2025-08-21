"""Tests for health check orchestrator."""

import asyncio
import time

import pytest

from bio_mcp.http.health.interface import HealthChecker, HealthCheckResult
from bio_mcp.http.health.orchestrator import HealthOrchestrator


class MockHealthChecker(HealthChecker):
    """Mock health checker for testing."""
    
    def __init__(self, name: str, healthy: bool = True, duration_ms: float = 100.0, error: Exception | None = None):
        self._name = name
        self._healthy = healthy
        self._duration_ms = duration_ms
        self._error = error
    
    @property
    def name(self) -> str:
        return self._name
    
    async def check_health(self) -> HealthCheckResult:
        if self._error:
            raise self._error
        
        return HealthCheckResult(
            healthy=self._healthy,
            message=f"{self._name} is {'healthy' if self._healthy else 'unhealthy'}",
            details={"test": True},
            check_duration_ms=self._duration_ms,
            checker_name=self._name
        )


class TestHealthOrchestrator:
    """Test health check orchestrator."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create health orchestrator for testing."""
        return HealthOrchestrator(cache_ttl_seconds=60.0)
    
    def test_orchestrator_cache_ttl(self, orchestrator):
        """Test cache TTL configuration."""
        assert orchestrator.cache_ttl_seconds == 60.0
    
    def test_orchestrator_default_cache_ttl(self):
        """Test default cache TTL configuration."""
        orchestrator = HealthOrchestrator()
        assert orchestrator.cache_ttl_seconds == 30.0
    
    def test_add_checker(self, orchestrator):
        """Test adding health checkers."""
        checker = MockHealthChecker("test")
        orchestrator.add_checker(checker)
        
        assert len(orchestrator.checkers) == 1
        assert orchestrator.checkers[0] == checker
    
    def test_add_multiple_checkers(self, orchestrator):
        """Test adding multiple health checkers."""
        checker1 = MockHealthChecker("test1")
        checker2 = MockHealthChecker("test2")
        
        orchestrator.add_checker(checker1)
        orchestrator.add_checker(checker2)
        
        assert len(orchestrator.checkers) == 2
        assert orchestrator.checkers[0] == checker1
        assert orchestrator.checkers[1] == checker2
    
    @pytest.mark.asyncio
    async def test_check_all_healthy(self, orchestrator):
        """Test all healthy checkers."""
        checker1 = MockHealthChecker("database", healthy=True, duration_ms=50.0)
        checker2 = MockHealthChecker("weaviate", healthy=True, duration_ms=75.0)
        
        orchestrator.add_checker(checker1)
        orchestrator.add_checker(checker2)
        
        result = await orchestrator.check_all()
        
        assert result.healthy is True
        assert "all systems healthy" in result.message.lower()
        assert result.checker_name == "orchestrator"
        assert result.check_duration_ms > 0
        assert result.details is not None
        assert len(result.details["checks"]) == 2
        assert result.details["total_checks"] == 2
        assert result.details["healthy_checks"] == 2
        assert result.details["failed_checks"] == 0
    
    @pytest.mark.asyncio
    async def test_check_some_unhealthy(self, orchestrator):
        """Test mixed healthy/unhealthy checkers."""
        checker1 = MockHealthChecker("database", healthy=True)
        checker2 = MockHealthChecker("weaviate", healthy=False)
        
        orchestrator.add_checker(checker1)
        orchestrator.add_checker(checker2)
        
        result = await orchestrator.check_all()
        
        assert result.healthy is False
        assert "1 of 2 checks failed" in result.message
        assert result.details["healthy_checks"] == 1
        assert result.details["failed_checks"] == 1
        assert result.details["failed_checkers"] == ["weaviate"]
    
    @pytest.mark.asyncio
    async def test_check_with_exceptions(self, orchestrator):
        """Test checkers that raise exceptions."""
        checker1 = MockHealthChecker("database", healthy=True)
        checker2 = MockHealthChecker("weaviate", error=Exception("Connection timeout"))
        
        orchestrator.add_checker(checker1)
        orchestrator.add_checker(checker2)
        
        result = await orchestrator.check_all()
        
        assert result.healthy is False
        assert "1 of 2 checks failed" in result.message
        assert result.details["failed_checkers"] == ["weaviate"]
        # Exception checker should still appear in results
        weaviate_result = next(c for c in result.details["checks"] if c["checker"] == "weaviate")
        assert weaviate_result["healthy"] is False
        assert "Connection timeout" in weaviate_result["error"]
    
    @pytest.mark.asyncio
    async def test_caching_behavior(self, orchestrator):
        """Test health check result caching."""
        checker = MockHealthChecker("database", healthy=True)
        orchestrator.add_checker(checker)
        
        # First call should execute checker
        result1 = await orchestrator.check_all()
        
        # Second call within cache TTL should return cached result
        result2 = await orchestrator.check_all()
        
        assert result1.healthy == result2.healthy
        assert result1.message == result2.message
        # Second call should return cache indicator duration
        assert result2.check_duration_ms == 0.1
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, orchestrator):
        """Test cache expiration behavior."""
        # Use very short cache TTL
        orchestrator = HealthOrchestrator(cache_ttl_seconds=0.1)
        checker = MockHealthChecker("database", healthy=True)
        orchestrator.add_checker(checker)
        
        # First call
        result1 = await orchestrator.check_all()
        
        # Wait for cache to expire
        await asyncio.sleep(0.2)
        
        # Second call should re-execute checker
        result2 = await orchestrator.check_all()
        
        assert result1.healthy == result2.healthy
        # Both calls should have executed the checker (not cached)
        assert result2.check_duration_ms != 0.1  # Should not be cache indicator
    
    @pytest.mark.asyncio
    async def test_concurrent_checks(self, orchestrator):
        """Test concurrent health checks."""
        checker1 = MockHealthChecker("database", duration_ms=100.0)
        checker2 = MockHealthChecker("weaviate", duration_ms=150.0)
        
        orchestrator.add_checker(checker1)
        orchestrator.add_checker(checker2)
        
        start_time = time.time()
        result = await orchestrator.check_all()
        total_time = (time.time() - start_time) * 1000
        
        # Should run concurrently, so total time should be less than sum
        assert total_time < 200.0  # Less than 100 + 150
        assert result.healthy is True
        assert len(result.details["checks"]) == 2
    
    @pytest.mark.asyncio
    async def test_no_checkers(self, orchestrator):
        """Test orchestrator with no checkers."""
        result = await orchestrator.check_all()
        
        assert result.healthy is True
        assert "no health checkers configured" in result.message.lower()
        assert result.details["total_checks"] == 0
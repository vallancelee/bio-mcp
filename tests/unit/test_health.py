"""
Unit tests for health check functionality.
"""

import json
import time
from unittest.mock import patch

import pytest

from bio_mcp.config import config
from bio_mcp.health import (
    HealthCheck,
    HealthChecker,
    HealthReport,
    HealthStatus,
    health_check_main,
    health_checker,
)


class TestHealthStatus:
    """Test HealthStatus enum."""
    
    def test_health_status_values(self):
        """Test that health status has correct values."""
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.UNHEALTHY == "unhealthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNKNOWN == "unknown"


class TestHealthCheck:
    """Test HealthCheck dataclass."""
    
    def test_health_check_creation(self):
        """Test creating a health check result."""
        check = HealthCheck(
            name="test",
            status=HealthStatus.HEALTHY,
            message="Test message",
            duration_ms=1.5,
            details={"key": "value"}
        )
        
        assert check.name == "test"
        assert check.status == HealthStatus.HEALTHY
        assert check.message == "Test message"
        assert check.duration_ms == 1.5
        assert check.details == {"key": "value"}
    
    def test_health_check_to_dict(self):
        """Test converting health check to dictionary."""
        check = HealthCheck(
            name="test",
            status=HealthStatus.HEALTHY,
            message="Test message",
            duration_ms=1.5,
            details={"key": "value"}
        )
        
        result = check.to_dict()
        expected = {
            "name": "test",
            "status": "healthy",
            "message": "Test message",
            "duration_ms": 1.5,
            "details": {"key": "value"}
        }
        
        assert result == expected


class TestHealthReport:
    """Test HealthReport dataclass."""
    
    def test_health_report_creation(self):
        """Test creating a health report."""
        checks = [
            HealthCheck("test1", HealthStatus.HEALTHY, "OK"),
            HealthCheck("test2", HealthStatus.HEALTHY, "OK")
        ]
        
        report = HealthReport(
            status=HealthStatus.HEALTHY,
            timestamp="2023-01-01T00:00:00Z",
            version="1.0.0",
            uptime_seconds=123.45,
            checks=checks
        )
        
        assert report.status == HealthStatus.HEALTHY
        assert report.timestamp == "2023-01-01T00:00:00Z"
        assert report.version == "1.0.0"
        assert report.uptime_seconds == 123.45
        assert len(report.checks) == 2
    
    def test_health_report_to_dict(self):
        """Test converting health report to dictionary."""
        checks = [
            HealthCheck("test1", HealthStatus.HEALTHY, "OK"),
            HealthCheck("test2", HealthStatus.DEGRADED, "Warning")
        ]
        
        report = HealthReport(
            status=HealthStatus.DEGRADED,
            timestamp="2023-01-01T00:00:00Z",
            version="1.0.0",
            uptime_seconds=123.45,
            checks=checks
        )
        
        result = report.to_dict()
        
        assert result["status"] == "degraded"
        assert result["timestamp"] == "2023-01-01T00:00:00Z"
        assert result["version"] == "1.0.0"
        assert result["uptime_seconds"] == 123.45
        assert len(result["checks"]) == 2
        assert result["checks"][0]["name"] == "test1"
        assert result["checks"][1]["status"] == "degraded"


class TestHealthChecker:
    """Test HealthChecker class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.checker = HealthChecker()
    
    def test_health_checker_initialization(self):
        """Test health checker initialization."""
        assert self.checker.start_time > 0
        assert isinstance(self.checker._checks, dict)
        
        # Should have default checks registered
        assert "server" in self.checker._checks
        assert "config" in self.checker._checks
        assert "metrics" in self.checker._checks
    
    def test_register_check(self):
        """Test registering custom health checks."""
        async def custom_check():
            return HealthCheck("custom", HealthStatus.HEALTHY, "Custom check")
        
        self.checker.register_check("custom", custom_check)
        assert "custom" in self.checker._checks
        assert self.checker._checks["custom"] == custom_check
    
    def test_get_uptime(self):
        """Test uptime calculation."""
        # Should be very small since just created
        uptime = self.checker.get_uptime()
        assert uptime >= 0
        assert uptime < 1  # Should be less than 1 second
        
        # Mock start time to test calculation
        self.checker.start_time = time.time() - 100  # 100 seconds ago
        uptime = self.checker.get_uptime()
        assert 99 < uptime < 101  # Should be around 100 seconds
    
    @pytest.mark.asyncio
    async def test_server_check_success(self):
        """Test successful server health check."""
        result = await self.checker._check_server()
        
        assert result.name == "server"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "MCP server is running"
        assert result.duration_ms is not None
        assert result.duration_ms >= 0
    
    @pytest.mark.asyncio
    async def test_config_check_success(self):
        """Test successful config health check."""
        result = await self.checker._check_config()
        
        assert result.name == "config"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Configuration is valid"
        assert result.duration_ms is not None
        assert result.duration_ms >= 0
        assert result.details is not None
        assert "server_name" in result.details
        assert "log_level" in result.details
    
    @pytest.mark.asyncio
    async def test_config_check_failure(self):
        """Test config health check with validation failure."""
        with patch.object(config, 'validate', side_effect=ValueError("Invalid config")):
            result = await self.checker._check_config()
            
            assert result.name == "config"
            assert result.status == HealthStatus.UNHEALTHY
            assert "Configuration validation failed" in result.message
            assert "Invalid config" in result.message
    
    @pytest.mark.asyncio
    async def test_metrics_check_success(self):
        """Test successful metrics health check."""
        result = await self.checker._check_metrics()
        
        assert result.name == "metrics"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Metrics collection is working"
        assert result.duration_ms is not None
        assert result.duration_ms >= 0
        assert result.details is not None
        assert "total_requests" in result.details
        assert "success_rate" in result.details
        assert "uptime_seconds" in result.details
    
    @pytest.mark.asyncio
    async def test_metrics_check_failure(self):
        """Test metrics health check with failure."""
        with patch('bio_mcp.health.get_metrics_dict', side_effect=Exception("Metrics error")):
            result = await self.checker._check_metrics()
            
            assert result.name == "metrics"
            assert result.status == HealthStatus.UNHEALTHY
            assert "Metrics collection failed" in result.message
            assert "Metrics error" in result.message
    
    @pytest.mark.asyncio
    async def test_run_checks_all(self):
        """Test running all health checks."""
        results = await self.checker.run_checks()
        
        assert len(results) >= 3  # At least server, config, metrics
        check_names = [check.name for check in results]
        assert "server" in check_names
        assert "config" in check_names
        assert "metrics" in check_names
    
    @pytest.mark.asyncio
    async def test_run_checks_specific(self):
        """Test running specific health checks."""
        results = await self.checker.run_checks(["server", "config"])
        
        assert len(results) == 2
        check_names = [check.name for check in results]
        assert "server" in check_names
        assert "config" in check_names
        assert "metrics" not in check_names
    
    @pytest.mark.asyncio
    async def test_run_checks_unknown(self):
        """Test running unknown health check."""
        results = await self.checker.run_checks(["unknown_check"])
        
        assert len(results) == 1
        assert results[0].name == "unknown_check"
        assert results[0].status == HealthStatus.UNKNOWN
        assert "Unknown health check" in results[0].message
    
    @pytest.mark.asyncio
    async def test_run_checks_exception(self):
        """Test health check that throws exception."""
        async def failing_check():
            raise Exception("Check failed")
        
        self.checker.register_check("failing", failing_check)
        results = await self.checker.run_checks(["failing"])
        
        assert len(results) == 1
        assert results[0].name == "failing"
        assert results[0].status == HealthStatus.UNHEALTHY
        assert "Health check execution failed" in results[0].message
        assert "Check failed" in results[0].message
    
    @pytest.mark.asyncio
    async def test_get_health_report_healthy(self):
        """Test getting health report with all healthy checks."""
        report = await self.checker.get_health_report()
        
        assert isinstance(report, HealthReport)
        assert report.status == HealthStatus.HEALTHY
        assert report.timestamp is not None
        assert report.version == config.version
        assert report.uptime_seconds >= 0
        assert len(report.checks) >= 3
    
    @pytest.mark.asyncio
    async def test_get_health_report_unhealthy(self):
        """Test getting health report with unhealthy check."""
        async def unhealthy_check():
            return HealthCheck("test", HealthStatus.UNHEALTHY, "Failed")
        
        self.checker.register_check("unhealthy", unhealthy_check)
        report = await self.checker.get_health_report()
        
        assert report.status == HealthStatus.UNHEALTHY
    
    @pytest.mark.asyncio
    async def test_get_health_report_degraded(self):
        """Test getting health report with degraded check."""
        async def degraded_check():
            return HealthCheck("test", HealthStatus.DEGRADED, "Warning")
        
        self.checker.register_check("degraded", degraded_check)
        report = await self.checker.get_health_report()
        
        # With existing healthy checks + one degraded = overall degraded
        assert report.status == HealthStatus.DEGRADED
    
    @pytest.mark.asyncio
    async def test_get_health_report_mixed_statuses(self):
        """Test health report status calculation with mixed check results."""
        async def healthy_check():
            return HealthCheck("healthy", HealthStatus.HEALTHY, "OK")
        
        async def degraded_check():
            return HealthCheck("degraded", HealthStatus.DEGRADED, "Warning")
        
        async def unhealthy_check():
            return HealthCheck("unhealthy", HealthStatus.UNHEALTHY, "Failed")
        
        self.checker.register_check("healthy", healthy_check)
        self.checker.register_check("degraded", degraded_check)
        self.checker.register_check("unhealthy", unhealthy_check)
        
        # Unhealthy takes precedence
        report = await self.checker.get_health_report()
        assert report.status == HealthStatus.UNHEALTHY


class TestHealthCheckMain:
    """Test health check main function."""
    
    @pytest.mark.asyncio
    async def test_health_check_main_success(self, capsys):
        """Test main health check function with healthy status."""
        mock_report = HealthReport(
            status=HealthStatus.HEALTHY,
            timestamp="2023-01-01T00:00:00Z",
            version="1.0.0",
            uptime_seconds=100.0,
            checks=[HealthCheck("test", HealthStatus.HEALTHY, "OK")]
        )
        
        with patch('bio_mcp.health.health_checker.get_health_report') as mock_get_report:
            mock_get_report.return_value = mock_report
            
            with pytest.raises(SystemExit) as exc_info:
                await health_check_main()
            
            assert exc_info.value.code == 0  # Healthy exit code
            
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["status"] == "healthy"
            assert output["version"] == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_health_check_main_degraded(self, capsys):
        """Test main health check function with degraded status."""
        mock_report = HealthReport(
            status=HealthStatus.DEGRADED,
            timestamp="2023-01-01T00:00:00Z",
            version="1.0.0",
            uptime_seconds=100.0,
            checks=[HealthCheck("test", HealthStatus.DEGRADED, "Warning")]
        )
        
        with patch('bio_mcp.health.health_checker.get_health_report') as mock_get_report:
            mock_get_report.return_value = mock_report
            
            with pytest.raises(SystemExit) as exc_info:
                await health_check_main()
            
            assert exc_info.value.code == 1  # Degraded exit code
    
    @pytest.mark.asyncio
    async def test_health_check_main_unhealthy(self, capsys):
        """Test main health check function with unhealthy status."""
        mock_report = HealthReport(
            status=HealthStatus.UNHEALTHY,
            timestamp="2023-01-01T00:00:00Z",
            version="1.0.0",
            uptime_seconds=100.0,
            checks=[HealthCheck("test", HealthStatus.UNHEALTHY, "Failed")]
        )
        
        with patch('bio_mcp.health.health_checker.get_health_report') as mock_get_report:
            mock_get_report.return_value = mock_report
            
            with pytest.raises(SystemExit) as exc_info:
                await health_check_main()
            
            assert exc_info.value.code == 2  # Unhealthy exit code
    
    @pytest.mark.asyncio
    async def test_health_check_main_exception(self, capsys):
        """Test main health check function with exception."""
        with patch('bio_mcp.health.health_checker.get_health_report') as mock_get_report:
            mock_get_report.side_effect = Exception("Health check failed")
            
            with pytest.raises(SystemExit) as exc_info:
                await health_check_main()
            
            assert exc_info.value.code == 2  # Error exit code
            
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["status"] == "unhealthy"
            assert "Health check failed" in output["error"]


class TestGlobalHealthChecker:
    """Test global health checker instance."""
    
    def test_global_health_checker_exists(self):
        """Test that global health checker instance exists."""
        assert health_checker is not None
        assert isinstance(health_checker, HealthChecker)
    
    @pytest.mark.asyncio
    async def test_global_health_checker_works(self):
        """Test that global health checker works."""
        report = await health_checker.get_health_report()
        assert isinstance(report, HealthReport)
        assert report.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
"""
Health check functionality for Bio-MCP server.
Phase 1B: Health checks for container orchestration and monitoring.
"""

import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from .config import config
from .metrics import get_metrics_dict


class HealthStatus(str, Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result."""
    name: str
    status: HealthStatus
    message: str
    duration_ms: float | None = None
    details: dict[str, Any] | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class HealthReport:
    """Complete health report."""
    status: HealthStatus
    timestamp: str
    version: str
    uptime_seconds: float
    checks: list[HealthCheck]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "checks": [check.to_dict() for check in self.checks]
        }


class HealthChecker:
    """Health check manager for Bio-MCP server."""
    
    def __init__(self):
        self.start_time = time.time()
        self._checks: dict[str, callable] = {}
        
        # Register basic checks
        self.register_check("server", self._check_server)
        self.register_check("config", self._check_config)
        self.register_check("metrics", self._check_metrics)
    
    def register_check(self, name: str, check_func: callable):
        """Register a new health check function."""
        self._checks[name] = check_func
    
    def get_uptime(self) -> float:
        """Get server uptime in seconds."""
        return time.time() - self.start_time
    
    async def _check_server(self) -> HealthCheck:
        """Check basic server health."""
        start_time = time.time()
        
        try:
            # Basic server health - always healthy if we can run this
            duration = (time.time() - start_time) * 1000
            return HealthCheck(
                name="server",
                status=HealthStatus.HEALTHY,
                message="MCP server is running",
                duration_ms=duration
            )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return HealthCheck(
                name="server",
                status=HealthStatus.UNHEALTHY,
                message=f"Server check failed: {e!s}",
                duration_ms=duration
            )
    
    async def _check_config(self) -> HealthCheck:
        """Check configuration health."""
        start_time = time.time()
        
        try:
            # Validate configuration
            config.validate()
            
            duration = (time.time() - start_time) * 1000
            return HealthCheck(
                name="config",
                status=HealthStatus.HEALTHY,
                message="Configuration is valid",
                duration_ms=duration,
                details={
                    "server_name": config.server_name,
                    "log_level": config.log_level,
                    "has_pubmed_key": config.pubmed_api_key is not None,
                    "has_openai_key": config.openai_api_key is not None
                }
            )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return HealthCheck(
                name="config",
                status=HealthStatus.UNHEALTHY,
                message=f"Configuration validation failed: {e!s}",
                duration_ms=duration
            )
    
    async def _check_metrics(self) -> HealthCheck:
        """Check metrics collection health."""
        start_time = time.time()
        
        try:
            # Get metrics to ensure collection is working
            metrics = get_metrics_dict()
            
            duration = (time.time() - start_time) * 1000
            return HealthCheck(
                name="metrics",
                status=HealthStatus.HEALTHY,
                message="Metrics collection is working",
                duration_ms=duration,
                details={
                    "total_requests": metrics["server"]["total_requests"],
                    "success_rate": metrics["server"]["success_rate"],
                    "uptime_seconds": metrics["server"]["uptime_seconds"]
                }
            )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return HealthCheck(
                name="metrics",
                status=HealthStatus.UNHEALTHY,
                message=f"Metrics collection failed: {e!s}",
                duration_ms=duration
            )
    
    async def run_checks(self, check_names: list[str] | None = None) -> list[HealthCheck]:
        """Run health checks."""
        if check_names is None:
            check_names = list(self._checks.keys())
        
        results = []
        for name in check_names:
            if name in self._checks:
                try:
                    result = await self._checks[name]()
                    results.append(result)
                except Exception as e:
                    # Fallback error check if the check function itself fails
                    results.append(HealthCheck(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Health check execution failed: {e!s}"
                    ))
            else:
                results.append(HealthCheck(
                    name=name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Unknown health check: {name}"
                ))
        
        return results
    
    async def get_health_report(self, check_names: list[str] | None = None) -> HealthReport:
        """Get complete health report."""
        timestamp = datetime.now(UTC).isoformat()
        uptime = self.get_uptime()
        
        # Run all checks
        checks = await self.run_checks(check_names)
        
        # Determine overall status
        statuses = [check.status for check in checks]
        
        if all(status == HealthStatus.HEALTHY for status in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            overall_status = HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNKNOWN
        
        return HealthReport(
            status=overall_status,
            timestamp=timestamp,
            version=config.version,
            uptime_seconds=uptime,
            checks=checks
        )


# Global health checker instance
health_checker = HealthChecker()


async def health_check_main():
    """Main function for health check command."""
    try:
        health_report = await health_checker.get_health_report()
        
        # Print JSON status for container health checks
        print(json.dumps(health_report.to_dict(), indent=2))
        
        # Exit with appropriate code
        if health_report.status == HealthStatus.HEALTHY:
            sys.exit(0)
        elif health_report.status == HealthStatus.DEGRADED:
            sys.exit(1)  # Warning
        else:
            sys.exit(2)  # Unhealthy
            
    except Exception as e:
        # Error during health check
        error_report = {
            "status": "unhealthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "version": config.version,
            "error": str(e),
            "checks": []
        }
        print(json.dumps(error_report, indent=2))
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(health_check_main())
"""Database health checker implementation."""

import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from bio_mcp.http.health.interface import HealthChecker, HealthCheckResult


def get_expected_alembic_head() -> str:
    """Get the expected Alembic head revision.
    
    In a real implementation, this would read from the migration files
    or configuration. For now, return a placeholder.
    """
    return "latest"


class DatabaseHealthChecker(HealthChecker):
    """Database connectivity and schema health checker."""
    
    def __init__(self, database_url: str, timeout_seconds: float = 5.0):
        """Initialize database health checker.
        
        Args:
            database_url: Database connection URL
            timeout_seconds: Timeout for health checks
            
        Raises:
            ValueError: If database URL is invalid
        """
        if not database_url or not database_url.startswith(('postgresql://', 'sqlite://')):
            raise ValueError("Invalid database URL")
        
        self.database_url = database_url
        self._timeout_seconds = timeout_seconds
    
    @property
    def name(self) -> str:
        """Name of this health checker."""
        return "database"
    
    @property
    def timeout_seconds(self) -> float:
        """Timeout for database health checks."""
        return self._timeout_seconds
    
    async def check_health(self) -> HealthCheckResult:
        """Check database connectivity and schema status.
        
        Returns:
            HealthCheckResult with database health status
        """
        start_time = time.time()
        
        try:
            # Create async engine for health check
            engine = create_async_engine(
                self.database_url,
                pool_timeout=self.timeout_seconds,
                pool_recycle=3600
            )
            
            async with engine.connect() as connection:
                # Test basic connectivity
                result = await connection.execute(text("SELECT 1"))
                if result.scalar() != 1:
                    raise Exception("Basic connectivity test failed")
                
                # Check migration status
                migration_status = await self._check_migration_status(connection)
                
                # Dispose engine
                await engine.dispose()
                
                duration_ms = (time.time() - start_time) * 1000
                
                if migration_status["up_to_date"]:
                    return HealthCheckResult(
                        healthy=True,
                        message="Database connection healthy and migrations up to date",
                        details={
                            "migration_status": "up_to_date",
                            "current_version": migration_status["current_version"]
                        },
                        check_duration_ms=duration_ms,
                        checker_name=self.name
                    )
                else:
                    return HealthCheckResult(
                        healthy=False,
                        message="Database connection healthy but migrations outdated",
                        details={
                            "migration_status": "outdated",
                            "current_version": migration_status["current_version"],
                            "expected_version": migration_status["expected_version"]
                        },
                        check_duration_ms=duration_ms,
                        checker_name=self.name
                    )
                    
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                healthy=False,
                message=f"Database health check failed: {e!s}",
                details={
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                check_duration_ms=duration_ms,
                checker_name=self.name
            )
    
    async def _check_migration_status(self, connection) -> dict[str, any]:
        """Check Alembic migration status.
        
        Args:
            connection: Database connection
            
        Returns:
            Dict with migration status information
        """
        try:
            # Try to get current Alembic version
            result = await connection.execute(
                text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1")
            )
            current_version = result.scalar()
            expected_version = get_expected_alembic_head()
            
            return {
                "up_to_date": current_version == expected_version,
                "current_version": current_version,
                "expected_version": expected_version
            }
            
        except Exception:
            # If alembic_version table doesn't exist, assume no migrations applied
            return {
                "up_to_date": False,
                "current_version": None,
                "expected_version": get_expected_alembic_head()
            }
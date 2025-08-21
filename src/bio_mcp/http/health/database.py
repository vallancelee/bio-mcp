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
                
                # Check for jobs table specifically (required for job API)
                jobs_table_exists = await self._check_jobs_table_exists(connection)
                
                # Dispose engine
                await engine.dispose()
                
                duration_ms = (time.time() - start_time) * 1000
                
                # Determine overall health status
                all_good = migration_status["up_to_date"] and jobs_table_exists
                
                if all_good:
                    return HealthCheckResult(
                        healthy=True,
                        message="Database connection healthy, migrations up to date, jobs table ready",
                        details={
                            "migration_status": "up_to_date",
                            "current_version": migration_status["current_version"],
                            "jobs_table_exists": jobs_table_exists
                        },
                        check_duration_ms=duration_ms,
                        checker_name=self.name
                    )
                else:
                    issues = []
                    if not migration_status["up_to_date"]:
                        issues.append("migrations outdated")
                    if not jobs_table_exists:
                        issues.append("jobs table missing")
                    
                    return HealthCheckResult(
                        healthy=False,
                        message=f"Database issues detected: {', '.join(issues)}",
                        details={
                            "migration_status": "outdated" if not migration_status["up_to_date"] else "up_to_date",
                            "current_version": migration_status["current_version"],
                            "expected_version": migration_status["expected_version"],
                            "jobs_table_exists": jobs_table_exists
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
    
    async def _check_jobs_table_exists(self, connection) -> bool:
        """Check if jobs table exists and has required schema.
        
        Args:
            connection: Database connection
            
        Returns:
            True if jobs table exists with required columns
        """
        try:
            # Check if jobs table exists and has key columns
            result = await connection.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = 'jobs'
            """))
            table_exists = result.scalar() > 0
            
            if not table_exists:
                return False
            
            # Check for key columns
            result = await connection.execute(text("""
                SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_name = 'jobs' 
                AND column_name IN ('id', 'tool_name', 'status', 'parameters', 'created_at')
            """))
            required_columns = result.scalar()
            
            return required_columns >= 5  # All key columns present
            
        except Exception:
            # For SQLite or other databases that don't support information_schema
            try:
                # Try to query the jobs table directly
                await connection.execute(text(
                    "SELECT id, tool_name, status, parameters, created_at FROM jobs LIMIT 0"
                ))
                return True
            except Exception:
                return False
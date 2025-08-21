"""Tests for database health checker."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bio_mcp.http.health.database import DatabaseHealthChecker
from bio_mcp.http.health.interface import HealthCheckResult


class TestDatabaseHealthChecker:
    """Test database connectivity health checker."""
    
    @pytest.fixture
    def db_checker(self):
        """Create database health checker for testing."""
        return DatabaseHealthChecker("postgresql://test:test@localhost:5432/test")
    
    def test_checker_name(self, db_checker):
        """Test health checker name property."""
        assert db_checker.name == "database"
    
    def test_checker_timeout(self, db_checker):
        """Test default timeout configuration."""
        assert db_checker.timeout_seconds == 5.0
    
    @pytest.mark.asyncio
    async def test_check_health_successful_connection(self, db_checker):
        """Test successful database health check."""
        # Mock database connection and query
        mock_connection = AsyncMock()
        
        # Mock basic connectivity check (SELECT 1)
        mock_basic_result = MagicMock()
        mock_basic_result.scalar.return_value = 1
        
        # Mock the migration check 
        mock_migration_result = MagicMock()
        mock_migration_result.scalar.return_value = "latest"
        
        # Mock the jobs table existence check  
        mock_jobs_table_result = MagicMock()
        mock_jobs_table_result.scalar.return_value = 1  # Table exists
        
        # Mock the jobs table columns check
        mock_jobs_columns_result = MagicMock()
        mock_jobs_columns_result.scalar.return_value = 5  # All required columns exist
        
        mock_connection.execute.side_effect = [
            mock_basic_result,           # SELECT 1
            mock_migration_result,       # Migration version check
            mock_jobs_table_result,      # Jobs table existence check
            mock_jobs_columns_result     # Jobs table columns check
        ]
        
        # Create proper async context manager mock
        @asynccontextmanager
        async def mock_connect():
            yield mock_connection
        
        mock_engine = AsyncMock()
        mock_engine.connect = mock_connect
        mock_engine.dispose = AsyncMock()
        
        with patch('bio_mcp.http.health.database.create_async_engine', return_value=mock_engine):
            with patch('bio_mcp.http.health.database.get_expected_alembic_head', return_value="latest"):
                result = await db_checker.check_health()
        
        assert isinstance(result, HealthCheckResult)
        assert result.healthy is True
        assert "database" in result.message.lower()
        assert result.checker_name == "database"
        assert result.check_duration_ms > 0
    
    @pytest.mark.asyncio
    async def test_check_health_connection_failed(self, db_checker):
        """Test database health check with connection failure."""
        @asynccontextmanager
        async def mock_connect_fail():
            raise Exception("Connection refused")
            yield  # Never reached
        
        mock_engine = AsyncMock()
        mock_engine.connect = mock_connect_fail
        mock_engine.dispose = AsyncMock()
        
        with patch('bio_mcp.http.health.database.create_async_engine', return_value=mock_engine):
            result = await db_checker.check_health()
        
        assert result.healthy is False
        assert "failed" in result.message.lower()
        assert result.details is not None
        assert "error" in result.details
        assert result.details["error"] == "Connection refused"
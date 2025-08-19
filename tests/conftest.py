"""Pytest configuration and fixtures for Bio-MCP tests."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from bio_mcp.config import Config


@pytest.fixture
def test_config():
    """Provide a test configuration with safe defaults."""
    return Config(
        server_name="bio-mcp-test",
        log_level="DEBUG",
        version="0.1.0-test",
        build="test-build",
        commit="test-commit",
        database_url="sqlite:///:memory:",
        weaviate_url="http://localhost:8080",
        pubmed_api_key=None,
        openai_api_key=None
    )


@pytest.fixture
def mock_env_clean():
    """Provide a clean environment for testing."""
    # Remove Bio-MCP related environment variables
    bio_mcp_vars = [key for key in os.environ.keys() if key.startswith('BIO_MCP_')]
    other_vars = ['DATABASE_URL', 'WEAVIATE_URL', 'PUBMED_API_KEY', 'OPENAI_API_KEY']
    
    all_vars = bio_mcp_vars + other_vars
    
    with patch.dict(os.environ, {}, clear=False):
        # Remove only our variables
        for var in all_vars:
            os.environ.pop(var, None)
        yield


@pytest.fixture
def mock_env_with_values():
    """Provide environment with test values."""
    test_env = {
        'BIO_MCP_SERVER_NAME': 'test-server',
        'BIO_MCP_LOG_LEVEL': 'DEBUG',
        'BIO_MCP_VERSION': '1.0.0-test',
        'BIO_MCP_BUILD': 'test-123',
        'BIO_MCP_COMMIT': 'abc123def456',
        'DATABASE_URL': 'postgresql://test:test@localhost/testdb',
        'WEAVIATE_URL': 'http://test-weaviate:8080',
        'PUBMED_API_KEY': 'test-pubmed-key',
        'OPENAI_API_KEY': 'test-openai-key'
    }
    
    with patch.dict(os.environ, test_env, clear=False):
        yield test_env


@pytest.fixture
def project_root():
    """Provide path to project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def temp_data_dir(tmp_path):
    """Provide temporary directory for test data."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture(scope="session")
def docker_available():
    """Check if Docker is available for integration tests."""
    import subprocess
    
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "docker: marks tests that require Docker"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add unit marker to tests in unit directory
        if "tests/unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Add integration marker to tests in integration directory
        if "tests/integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add docker marker to docker-related tests
        if "docker" in item.name.lower() or "docker" in str(item.fspath).lower():
            item.add_marker(pytest.mark.docker)


def pytest_runtest_setup(item):
    """Set up individual test runs."""
    # Skip Docker tests if Docker is not available
    if item.get_closest_marker("docker"):
        docker_available = True
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            docker_available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            docker_available = False
        
        if not docker_available:
            pytest.skip("Docker not available")


# Test data fixtures
@pytest.fixture
def sample_ping_response():
    """Sample ping tool response for testing."""
    return {
        "status": "ok",
        "message": "pong",
        "server_info": {
            "name": "bio-mcp-test",
            "version": "0.1.0-test",
            "log_level": "DEBUG"
        }
    }


@pytest.fixture
def sample_tool_list():
    """Sample tool list for testing."""
    return [
        {
            "name": "ping",
            "description": "Simple ping tool to test server connectivity",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Optional message to echo back",
                        "default": "pong"
                    }
                },
                "additionalProperties": False
            }
        }
    ]
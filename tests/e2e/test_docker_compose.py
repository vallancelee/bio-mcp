"""End-to-end tests for Docker Compose setup.

These tests verify that the actual docker-compose.yml file works correctly
for deployment scenarios. They test the full stack integration including
service dependencies, networking, and persistence.
"""

import json
import subprocess
import time
from pathlib import Path

import pytest


@pytest.mark.e2e
@pytest.mark.docker
@pytest.mark.slow
class TestDockerComposeE2E:
    """End-to-end test of Docker Compose stack."""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Set up and tear down Docker Compose services."""
        # Ensure clean state
        subprocess.run(
            ["docker-compose", "down", "-v"],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True
        )
        
        yield
        
        # Clean up after test
        subprocess.run(
            ["docker-compose", "down", "-v"],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True
        )
    
    def test_docker_compose_services_start(self):
        """Test that Docker Compose services start successfully."""
        cwd = Path(__file__).parent.parent.parent
        
        # Start services
        result = subprocess.run(
            ["docker-compose", "up", "-d", "weaviate", "postgres"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minutes timeout
        )
        
        assert result.returncode == 0, f"Failed to start services: {result.stderr}"
        
        # Wait for services to be ready
        time.sleep(10)
        
        # Check that services are running
        result = subprocess.run(
            ["docker-compose", "ps", "--format", "json"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        
        # Parse JSON output
        services = []
        for line in result.stdout.strip().split('\n'):
            if line:
                services.append(json.loads(line))
        
        # Check that both services are running
        service_names = [s["Service"] for s in services]
        assert "weaviate" in service_names
        assert "postgres" in service_names
        
        # Check that services are healthy/running
        for service in services:
            assert service["State"] in ["running", "Up"]
    
    def test_weaviate_connectivity(self):
        """Test Weaviate service connectivity."""
        cwd = Path(__file__).parent.parent.parent
        
        # Start Weaviate
        subprocess.run(
            ["docker-compose", "up", "-d", "weaviate"],
            cwd=cwd,
            capture_output=True,
            timeout=60
        )
        
        # Wait for Weaviate to be ready
        time.sleep(15)
        
        # Test connectivity
        result = subprocess.run(
            ["curl", "-s", "http://localhost:8080/v1/meta"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        
        # Parse response
        try:
            meta = json.loads(result.stdout)
            assert "version" in meta
            assert "hostname" in meta
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON response from Weaviate: {result.stdout}")
    
    def test_postgres_connectivity(self):
        """Test PostgreSQL service connectivity."""
        cwd = Path(__file__).parent.parent.parent
        
        # Start PostgreSQL
        subprocess.run(
            ["docker-compose", "up", "-d", "postgres"],
            cwd=cwd,
            capture_output=True,
            timeout=60
        )
        
        # Wait for PostgreSQL to be ready
        time.sleep(10)
        
        # Test connectivity using docker exec
        result = subprocess.run(
            [
                "docker", "exec", "bio-mcp-postgres",
                "pg_isready", "-h", "localhost", "-p", "5432", "-U", "biomcp"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        assert "accepting connections" in result.stdout
    
    def test_service_dependencies(self):
        """Test that service dependencies work correctly."""
        cwd = Path(__file__).parent.parent.parent
        
        # Start all services including dependencies
        result = subprocess.run(
            ["docker-compose", "up", "-d"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=180  # 3 minutes for full stack
        )
        
        assert result.returncode == 0, f"Failed to start full stack: {result.stderr}"
        
        # Wait for all services to be ready
        time.sleep(30)
        
        # Check that all expected services are running
        result = subprocess.run(
            ["docker-compose", "ps", "--format", "json"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        
        # Parse and verify services
        services = []
        for line in result.stdout.strip().split('\n'):
            if line:
                services.append(json.loads(line))
        
        service_names = [s["Service"] for s in services]
        expected_services = ["weaviate", "postgres", "t2v-transformers"]
        
        for service in expected_services:
            assert service in service_names, f"Service {service} not found in running services"
        
        # Check that services are running
        for service in services:
            if service["Service"] in expected_services:
                assert service["State"] in ["running", "Up"], f"Service {service['Service']} not running"
    
    def test_volume_persistence(self):
        """Test that Docker volumes persist data correctly."""
        cwd = Path(__file__).parent.parent.parent
        
        # Start PostgreSQL
        subprocess.run(
            ["docker-compose", "up", "-d", "postgres"],
            cwd=cwd,
            capture_output=True,
            timeout=60
        )
        
        time.sleep(10)
        
        # Create test data
        result = subprocess.run(
            [
                "docker", "exec", "bio-mcp-postgres",
                "psql", "-U", "biomcp", "-d", "biomcp", "-c",
                "CREATE TABLE test_persistence (id SERIAL PRIMARY KEY, data TEXT);"
            ],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Failed to create test table: {result.stderr}"
        
        # Insert test data
        subprocess.run(
            [
                "docker", "exec", "bio-mcp-postgres",
                "psql", "-U", "biomcp", "-d", "biomcp", "-c",
                "INSERT INTO test_persistence (data) VALUES ('test_data');"
            ],
            capture_output=True
        )
        
        # Stop and restart services
        subprocess.run(
            ["docker-compose", "down"],
            cwd=cwd,
            capture_output=True
        )
        
        subprocess.run(
            ["docker-compose", "up", "-d", "postgres"],
            cwd=cwd,
            capture_output=True,
            timeout=60
        )
        
        time.sleep(10)
        
        # Verify data persisted
        result = subprocess.run(
            [
                "docker", "exec", "bio-mcp-postgres",
                "psql", "-U", "biomcp", "-d", "biomcp", "-c",
                "SELECT data FROM test_persistence WHERE id = 1;"
            ],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "test_data" in result.stdout, "Data did not persist across container restart"


@pytest.mark.e2e
@pytest.mark.docker
class TestDockerfileE2E:
    """End-to-end test of Dockerfile configuration."""
    
    def test_dockerfile_has_healthcheck(self):
        """Test that Dockerfile includes health check configuration."""
        dockerfile_path = Path(__file__).parent.parent.parent / "Dockerfile"
        dockerfile_content = dockerfile_path.read_text()
        
        assert "HEALTHCHECK" in dockerfile_content
        assert "uv run python" in dockerfile_content
    

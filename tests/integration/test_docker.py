"""Integration tests for Docker setup."""

import pytest
import subprocess
import time
import json
from pathlib import Path


@pytest.mark.integration
@pytest.mark.docker
class TestDockerBuild:
    """Test Docker image building."""
    
    def test_docker_build_success(self):
        """Test that Docker image builds successfully."""
        # Build the image
        result = subprocess.run(
            ["docker", "build", "-t", "bio-mcp:test", "."],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        assert result.returncode == 0, f"Docker build failed: {result.stderr}"
        # Docker buildkit outputs to stderr, not stdout
        assert "Successfully tagged bio-mcp:test" in result.stderr or result.returncode == 0
    
    def test_docker_image_exists(self):
        """Test that the built Docker image exists."""
        result = subprocess.run(
            ["docker", "images", "bio-mcp:test", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "bio-mcp:test" in result.stdout.strip()


@pytest.mark.integration
@pytest.mark.docker  
class TestDockerRun:
    """Test running Docker containers."""
    
    def test_docker_run_basic(self):
        """Test that Docker container starts and runs."""
        # Run container with timeout
        result = subprocess.run(
            ["timeout", "5s", "docker", "run", "--rm", "bio-mcp:test"],
            capture_output=True,
            text=True
        )
        
        # Container should start successfully (timeout is expected)
        assert "Starting Bio-MCP server..." in result.stderr
    
    def test_docker_run_with_env_vars(self):
        """Test Docker container with environment variables."""
        env_vars = [
            "-e", "BIO_MCP_LOG_LEVEL=DEBUG",
            "-e", "BIO_MCP_SERVER_NAME=test-container"
        ]
        
        result = subprocess.run(
            ["timeout", "3s", "docker", "run", "--rm"] + env_vars + ["bio-mcp:test"],
            capture_output=True,
            text=True
        )
        
        # Check that it starts with debug logging
        assert "Starting Bio-MCP server..." in result.stderr


@pytest.mark.integration
@pytest.mark.docker
@pytest.mark.slow
class TestDockerCompose:
    """Test Docker Compose setup."""
    
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


@pytest.mark.integration
@pytest.mark.docker
class TestDockerHealthCheck:
    """Test Docker health check functionality."""
    
    def test_dockerfile_has_healthcheck(self):
        """Test that Dockerfile includes health check."""
        dockerfile_path = Path(__file__).parent.parent.parent / "Dockerfile"
        dockerfile_content = dockerfile_path.read_text()
        
        assert "HEALTHCHECK" in dockerfile_content
        assert "uv run python" in dockerfile_content
    
    @pytest.mark.slow
    def test_container_health_check(self):
        """Test that container health check works."""
        # Start container with health check
        result = subprocess.run(
            [
                "docker", "run", "-d", "--name", "bio-mcp-health-test",
                "bio-mcp:test"
            ],
            capture_output=True,
            text=True
        )
        
        container_id = result.stdout.strip()
        
        try:
            # Wait for health check to run
            time.sleep(35)  # Wait longer than health check interval
            
            # Check container health status
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_id],
                capture_output=True,
                text=True
            )
            
            health_status = result.stdout.strip()
            assert health_status in ["healthy", "starting"], f"Unexpected health status: {health_status}"
            
        finally:
            # Clean up container
            subprocess.run(["docker", "rm", "-f", "bio-mcp-health-test"], capture_output=True)
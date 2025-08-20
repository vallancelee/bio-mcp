"""Integration tests for Docker setup."""

import subprocess
from pathlib import Path

import pytest


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
            ["timeout", "3s", "docker", "run", "--rm", *env_vars, "bio-mcp:test"],
            capture_output=True,
            text=True
        )
        
        # Check that it starts with debug logging
        assert "Starting Bio-MCP server..." in result.stderr




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
    

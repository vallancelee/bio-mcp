"""Tests for HTTP FastAPI application endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bio_mcp.http.app import create_app
from bio_mcp.http.registry import ToolRegistry


@pytest.fixture
def mock_registry():
    """Create a mock registry for testing."""
    registry = ToolRegistry()
    
    # Mock ping tool
    def mock_ping_tool(name: str, arguments: dict):
        return {"message": "test pong"}
    
    # Mock a tool that raises an exception
    def mock_error_tool(name: str, arguments: dict):
        raise ValueError("Mock tool error")
    
    registry.register("ping", mock_ping_tool)
    registry.register("test.error", mock_error_tool)
    
    return registry


@pytest.fixture
def client(mock_registry):
    """Create test client with mock registry."""
    app = create_app(registry=mock_registry)
    return TestClient(app)


class TestHealthEndpoints:
    """Test health and liveness endpoints."""
    
    def test_healthz_returns_200(self, client):
        """Test /healthz endpoint returns 200 OK."""
        response = client.get("/healthz")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_readyz_returns_200_when_ready(self, client):
        """Test /readyz endpoint returns 200 when dependencies ready."""
        # Mock all dependencies as ready
        with patch("bio_mcp.http.lifecycle.check_readiness", return_value=True):
            response = client.get("/readyz")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
    
    def test_readyz_returns_503_when_not_ready(self, client):
        """Test /readyz endpoint returns 503 when dependencies not ready."""
        # Mock dependencies as not ready
        with patch("bio_mcp.http.app.check_readiness", return_value=False):
            response = client.get("/readyz")
            
            assert response.status_code == 503
            data = response.json()
            assert data["detail"]["status"] == "not_ready"


class TestToolsEndpoint:
    """Test tools listing endpoint."""
    
    def test_list_tools_returns_tool_names(self, client):
        """Test GET /v1/mcp/tools returns list of tool names."""
        response = client.get("/v1/mcp/tools")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "tools" in data
        assert isinstance(data["tools"], list)
        assert "ping" in data["tools"]
        assert "test.error" in data["tools"]


class TestInvokeEndpoint:
    """Test tool invocation endpoint."""
    
    def test_invoke_successful_tool(self, client):
        """Test POST /v1/mcp/invoke with successful tool execution."""
        payload = {
            "tool": "ping",
            "params": {"message": "hello"}
        }
        
        response = client.post("/v1/mcp/invoke", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["tool"] == "ping"
        assert "result" in data
        assert "trace_id" in data
    
    def test_invoke_with_unknown_tool(self, client):
        """Test POST /v1/mcp/invoke with unknown tool returns error."""
        payload = {
            "tool": "nonexistent.tool",
            "params": {}
        }
        
        response = client.post("/v1/mcp/invoke", json=payload)
        
        assert response.status_code == 404
        data = response.json()
        
        # FastAPI puts error response in 'detail' field
        detail = data["detail"]
        assert detail["ok"] is False
        assert detail["error_code"] == "TOOL_NOT_FOUND"
        assert "trace_id" in detail
        assert detail["tool"] == "nonexistent.tool"
    
    def test_invoke_with_tool_error(self, client):
        """Test POST /v1/mcp/invoke handles tool execution errors."""
        payload = {
            "tool": "test.error",
            "params": {}
        }
        
        response = client.post("/v1/mcp/invoke", json=payload)
        
        assert response.status_code == 500
        data = response.json()
        
        # FastAPI puts error response in 'detail' field
        detail = data["detail"]
        assert detail["ok"] is False
        assert detail["error_code"] == "TOOL_EXECUTION_ERROR"
        assert "trace_id" in detail
        assert detail["tool"] == "test.error"
    
    def test_invoke_with_invalid_payload(self, client):
        """Test POST /v1/mcp/invoke with invalid payload returns validation error."""
        # Missing required 'tool' field
        payload = {
            "params": {}
        }
        
        response = client.post("/v1/mcp/invoke", json=payload)
        
        assert response.status_code == 422  # FastAPI validation error
    
    def test_invoke_generates_trace_id(self, client):
        """Test that every invoke request generates a unique trace_id."""
        payload = {
            "tool": "ping",
            "params": {}
        }
        
        response1 = client.post("/v1/mcp/invoke", json=payload)
        response2 = client.post("/v1/mcp/invoke", json=payload)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        assert data1["trace_id"] != data2["trace_id"]
    
    def test_invoke_with_idempotency_key(self, client):
        """Test POST /v1/mcp/invoke respects idempotency_key."""
        payload = {
            "tool": "ping",
            "params": {},
            "idempotency_key": "test-key-123"
        }
        
        response = client.post("/v1/mcp/invoke", json=payload)
        
        assert response.status_code == 200
        # Note: Full idempotency implementation comes in later tasks
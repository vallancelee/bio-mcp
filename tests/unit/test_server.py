"""Unit tests for MCP server functionality."""

from unittest.mock import patch

import pytest
from mcp.types import TextContent, Tool

from bio_mcp.main import call_tool, list_tools


class TestMCPServer:
    """Test cases for MCP server functionality."""
    
    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test that list_tools returns expected tools."""
        tools = await list_tools()
        
        assert isinstance(tools, list)
        assert len(tools) >= 1  # Should have at least the ping tool
        
        # Check that ping tool exists
        tool_names = [tool.name for tool in tools]
        assert "ping" in tool_names
        
        # Verify ping tool structure
        ping_tool = next(tool for tool in tools if tool.name == "ping")
        assert isinstance(ping_tool, Tool)
        assert ping_tool.name == "ping"
        assert "ping tool" in ping_tool.description.lower()
        assert ping_tool.inputSchema is not None
        assert ping_tool.inputSchema["type"] == "object"
        
        # Check schema structure
        properties = ping_tool.inputSchema["properties"]
        assert "message" in properties
        assert properties["message"]["type"] == "string"
        assert properties["message"]["default"] == "pong"
    
    @pytest.mark.asyncio
    async def test_call_tool_ping_default_message(self):
        """Test calling ping tool with default message."""
        result = await call_tool("ping", {})
        
        assert isinstance(result, list)
        assert len(result) == 1
        
        content = result[0]
        assert isinstance(content, TextContent)
        assert content.type == "text"
        assert "Bio-MCP Server Response: pong" in content.text
        assert "Version:" in content.text
        assert "Server Info:" in content.text
    
    @pytest.mark.asyncio
    async def test_call_tool_ping_custom_message(self):
        """Test calling ping tool with custom message."""
        custom_message = "hello world"
        result = await call_tool("ping", {"message": custom_message})
        
        assert isinstance(result, list)
        assert len(result) == 1
        
        content = result[0]
        assert isinstance(content, TextContent)
        assert f"Bio-MCP Server Response: {custom_message}" in content.text
    
    @pytest.mark.asyncio
    async def test_call_tool_ping_server_info(self):
        """Test that ping tool returns server information."""
        result = await call_tool("ping", {})
        
        content = result[0]
        response_text = content.text
        
        # Check that all expected server info is included
        assert "Version:" in response_text
        assert "Name:" in response_text
        assert "Log Level:" in response_text
        assert "Database:" in response_text
        assert "Weaviate:" in response_text
        assert "PubMed API:" in response_text
        assert "OpenAI API:" in response_text
    
    @pytest.mark.asyncio
    async def test_call_tool_ping_version_formatting(self):
        """Test version formatting in ping response."""
        with patch('bio_mcp.main.config') as mock_config:
            mock_config.version = "1.2.3"
            mock_config.build = "456"
            mock_config.commit = "abc123def456789"
            mock_config.server_name = "test-server"
            mock_config.log_level = "DEBUG"
            mock_config.database_url = "test-db"
            mock_config.weaviate_url = "test-weaviate"
            mock_config.pubmed_api_key = "test-key"
            mock_config.openai_api_key = None
            
            result = await call_tool("ping", {})
            content = result[0]
            
            # Check version formatting with build and commit
            assert "Version: v1.2.3-456 (abc123de)" in content.text
            assert "PubMed API: configured" in content.text
            assert "OpenAI API: not configured" in content.text
    
    @pytest.mark.asyncio
    async def test_call_tool_ping_version_without_build_info(self):
        """Test version formatting without build info."""
        with patch('bio_mcp.main.config') as mock_config:
            mock_config.version = "0.1.0"
            mock_config.build = None
            mock_config.commit = None
            mock_config.server_name = "bio-mcp"
            mock_config.log_level = "INFO"
            mock_config.database_url = "sqlite:///:memory:"
            mock_config.weaviate_url = "http://localhost:8080"
            mock_config.pubmed_api_key = None
            mock_config.openai_api_key = None
            
            result = await call_tool("ping", {})
            content = result[0]
            
            # Check simple version formatting
            assert "Version: v0.1.0" in content.text
            assert "PubMed API: not configured" in content.text
            assert "OpenAI API: not configured" in content.text
    
    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self):
        """Test calling unknown tool returns error response."""
        result = await call_tool("nonexistent", {})
        
        assert isinstance(result, list)
        assert len(result) == 1
        content = result[0]
        assert isinstance(content, TextContent)
        assert "Validation error" in content.text
    
    @pytest.mark.asyncio
    async def test_call_tool_ping_with_invalid_args(self):
        """Test ping tool handles various argument types with validation."""
        # Test with None message (should work as it's allowed)
        result = await call_tool("ping", {"message": None})
        content = result[0]
        assert "Bio-MCP Server Response: None" in content.text
        
        # Test with numeric message (should be validated and return error)
        result = await call_tool("ping", {"message": 42})
        content = result[0]
        assert "Error:" in content.text
        assert "must be a string" in content.text
        
        # Test with extra arguments (should be rejected due to additionalProperties: false)
        result = await call_tool("ping", {"message": "test", "extra": "ignored"})
        content = result[0]
        assert "Error:" in content.text
        assert "Unexpected fields" in content.text


@pytest.mark.unit
class TestMCPServerLogging:
    """Test logging functionality in MCP server."""
    
    @pytest.mark.asyncio
    async def test_ping_tool_logging(self):
        """Test that ping tool logs correctly."""
        import logging
        from io import StringIO
        
        # Capture log output
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        
        # Add handler to the structured logger's underlying logger
        from bio_mcp.main import logger
        underlying_logger = logger.logger
        underlying_logger.addHandler(handler)
        underlying_logger.setLevel(logging.INFO)
        
        try:
            await call_tool("ping", {"message": "test"})
            
            # Check log output
            log_output = log_stream.getvalue()
            assert "Processing ping tool request" in log_output or \
                   "Ping tool completed successfully" in log_output, \
                   f"Expected log messages not found in: {log_output}"
        
        finally:
            # Clean up
            underlying_logger.removeHandler(handler)


@pytest.mark.unit  
class TestMCPServerConfig:
    """Test server configuration integration."""
    
    def test_server_imports_config(self):
        """Test that server properly imports and uses config."""
        from bio_mcp.config import config
        from bio_mcp.main import server
        
        # Server should be created with config name
        assert server.name == config.server_name
    
    def test_logging_configuration(self):
        """Test that logging is configured from config."""
        import logging
        
        # Re-import to trigger logging configuration
        
        # Check that bio_mcp logger level is configured
        # The logger should inherit from root or have explicit level set
        # Since basicConfig is called, root level should be set
        assert logging.getLogger().hasHandlers()  # Should have handlers from basicConfig
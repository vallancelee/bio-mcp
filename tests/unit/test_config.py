"""Unit tests for config module."""

import os
from unittest.mock import patch

import pytest

from bio_mcp.config import Config


class TestConfig:
    """Test cases for Config class."""
    
    def test_config_defaults(self):
        """Test default configuration values."""
        config = Config()
        
        assert config.server_name == "bio-mcp"
        assert config.log_level == "INFO"
        assert config.database_url == "sqlite:///:memory:"
        assert config.weaviate_url == "http://localhost:8080"
        assert config.pubmed_api_key is None
        assert config.openai_api_key is None
    
    def test_config_from_env_defaults(self):
        """Test loading config from environment with defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config.from_env()
            
            assert config.server_name == "bio-mcp"
            assert config.log_level == "INFO"
            assert config.database_url == "sqlite:///:memory:"
            assert config.weaviate_url == "http://localhost:8080"
    
    def test_config_from_env_custom_values(self):
        """Test loading config from environment with custom values."""
        env_vars = {
            "BIO_MCP_SERVER_NAME": "test-server",
            "BIO_MCP_LOG_LEVEL": "DEBUG",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "WEAVIATE_URL": "http://test-weaviate:8080",
            "PUBMED_API_KEY": "test-pubmed-key",
            "OPENAI_API_KEY": "test-openai-key"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config.from_env()
            
            assert config.server_name == "test-server"
            assert config.log_level == "DEBUG"
            assert config.database_url == "postgresql://test:test@localhost/test"
            assert config.weaviate_url == "http://test-weaviate:8080"
            assert config.pubmed_api_key == "test-pubmed-key"
            assert config.openai_api_key == "test-openai-key"
    
    def test_config_version_info(self):
        """Test version information in config."""
        config = Config()
        
        # Version should be set from package
        assert config.version is not None
        assert isinstance(config.version, str)
        # Build and commit can be None in development
        assert config.build is None or isinstance(config.build, str)
        assert config.commit is None or isinstance(config.commit, str)
    
    def test_config_version_from_env(self):
        """Test version override from environment."""
        env_vars = {
            "BIO_MCP_VERSION": "1.2.3",
            "BIO_MCP_BUILD": "456",
            "BIO_MCP_COMMIT": "abc123def456"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config.from_env()
            
            assert config.version == "1.2.3"
            assert config.build == "456"
            assert config.commit == "abc123def456"
    
    def test_config_validation_valid_log_level(self):
        """Test config validation with valid log level."""
        config = Config(log_level="DEBUG")
        
        # Should not raise exception
        config.validate()
    
    def test_config_validation_invalid_log_level(self):
        """Test config validation with invalid log level."""
        config = Config(log_level="INVALID")
        
        with pytest.raises(ValueError, match="Invalid log level"):
            config.validate()
    
    def test_config_validation_edge_cases(self):
        """Test config validation with edge cases."""
        # Test each valid log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        
        for level in valid_levels:
            config = Config(log_level=level)
            config.validate()  # Should not raise
    
    def test_config_empty_string_handling(self):
        """Test that empty string environment variables are handled correctly."""
        env_vars = {
            "PUBMED_API_KEY": "",
            "OPENAI_API_KEY": "",
            "BIO_MCP_BUILD": "",
            "BIO_MCP_COMMIT": ""
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config.from_env()
            
            # Empty strings should be treated as None for optional fields
            assert config.pubmed_api_key == ""  # Empty string is preserved
            assert config.openai_api_key == ""
            assert config.build == ""
            assert config.commit == ""


@pytest.mark.unit
class TestConfigIntegration:
    """Integration tests for config module."""
    
    def test_global_config_instance(self):
        """Test that global config instance works."""
        from bio_mcp.config import config
        
        assert isinstance(config, Config)
        assert config.server_name is not None
        assert config.version is not None
    
    def test_config_validation_on_import(self):
        """Test that config validation works on module import."""
        # This test ensures the global config instance is valid
        from bio_mcp.config import config
        
        # Should not raise exception
        config.validate()
"""
Unit tests for security validation functionality.
"""

import pytest
from unittest.mock import patch

from bio_mcp.security import (
    SecurityValidator,
    SecurityConfig,
    SecurityLevel,
    validate_request_security,
    configure_security
)
from bio_mcp.error_handling import ValidationError


class TestSecurityConfig:
    """Test security configuration."""
    
    def test_default_config(self):
        """Test default security configuration."""
        config = SecurityConfig()
        
        assert config.max_payload_size == 1024 * 1024  # 1MB
        assert config.max_string_length == 10000
        assert config.max_array_length == 1000
        assert config.max_object_depth == 10
        assert config.max_object_keys == 100
        assert config.allow_html is False
        assert config.allow_scripts is False
        assert config.security_level == SecurityLevel.STANDARD
        assert config.enable_xss_protection is True
        assert config.enable_injection_protection is True
        assert config.enable_path_traversal_protection is True
    
    def test_custom_config(self):
        """Test custom security configuration."""
        config = SecurityConfig(
            max_payload_size=512 * 1024,
            max_string_length=5000,
            security_level=SecurityLevel.STRICT,
            allow_html=True
        )
        
        assert config.max_payload_size == 512 * 1024
        assert config.max_string_length == 5000
        assert config.security_level == SecurityLevel.STRICT
        assert config.allow_html is True


class TestSecurityValidator:
    """Test security validator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SecurityValidator()
        self.strict_validator = SecurityValidator(SecurityConfig(security_level=SecurityLevel.STRICT))
    
    def test_payload_size_validation_pass(self):
        """Test payload size validation with valid data."""
        small_data = {"message": "hello"}
        
        # Should not raise exception
        self.validator.validate_payload_size(small_data)
    
    def test_payload_size_validation_fail(self):
        """Test payload size validation with oversized data."""
        # Create oversized data
        large_string = "x" * (1024 * 1024 + 1)  # > 1MB
        large_data = {"message": large_string}
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_payload_size(large_data)
        
        assert "Payload size" in str(exc_info.value)
        assert "exceeds maximum" in str(exc_info.value)
    
    def test_string_length_validation_pass(self):
        """Test string length validation with valid strings."""
        short_string = "hello world"
        result = self.validator.validate_string_content(short_string, "test_field")
        
        assert result == "hello world"
    
    def test_string_length_validation_fail(self):
        """Test string length validation with oversized strings."""
        long_string = "x" * 10001  # Exceeds default limit
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_string_content(long_string, "test_field")
        
        assert "length" in str(exc_info.value)
        assert "exceeds maximum" in str(exc_info.value)
        assert "test_field" in str(exc_info.value)
    
    def test_xss_protection_script_tag(self):
        """Test XSS protection against script tags."""
        malicious_input = "<script>alert('xss')</script>"
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_string_content(malicious_input, "message")
        
        assert "XSS" in str(exc_info.value)
        assert "message" in str(exc_info.value)
    
    def test_xss_protection_javascript_url(self):
        """Test XSS protection against javascript URLs."""
        malicious_input = "javascript:alert('xss')"
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_string_content(malicious_input, "url")
        
        assert "XSS" in str(exc_info.value)
    
    def test_xss_protection_event_handlers(self):
        """Test XSS protection against event handlers."""
        malicious_inputs = [
            '<img onclick="alert(1)">',
            '<div onload="malicious()">',
            '<a onmouseover="attack()">',
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(ValidationError) as exc_info:
                self.validator.validate_string_content(malicious_input, "content")
            
            assert "XSS" in str(exc_info.value)
    
    def test_injection_protection_sql(self):
        """Test SQL injection protection."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1 UNION SELECT password FROM users",
            "admin'; INSERT INTO logs VALUES ('hacked'); --",
            "1' OR '1'='1",
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(ValidationError) as exc_info:
                self.validator.validate_string_content(malicious_input, "query")
            
            assert "injection" in str(exc_info.value)
    
    def test_path_traversal_protection(self):
        """Test path traversal protection."""
        malicious_inputs = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config",
            "/etc/passwd",
            "../../../../root/.ssh/id_rsa",
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(ValidationError) as exc_info:
                self.validator.validate_string_content(malicious_input, "path")
            
            assert "path traversal" in str(exc_info.value)
    
    def test_html_sanitization(self):
        """Test HTML content sanitization."""
        html_input = "<p>Hello <b>World</b> & 'quotes'</p>"
        result = self.validator.validate_string_content(html_input, "content")
        
        # Should be HTML escaped
        assert "&lt;p&gt;" in result
        assert "&lt;b&gt;" in result
        assert "&amp;" in result
        assert "&#x27;" in result  # Single quote
    
    def test_html_allowed_config(self):
        """Test HTML content when HTML is allowed."""
        config = SecurityConfig(allow_html=True)
        validator = SecurityValidator(config)
        
        html_input = "<p>Hello <b>World</b></p>"
        result = validator.validate_string_content(html_input, "content")
        
        # Should remain unchanged when HTML is allowed
        assert result == html_input
    
    def test_object_depth_validation_pass(self):
        """Test object depth validation with valid nesting."""
        nested_obj = {"level1": {"level2": {"level3": "value"}}}
        
        result = self.validator.validate_object_structure(nested_obj)
        assert result == {"level1": {"level2": {"level3": "value"}}}
    
    def test_object_depth_validation_fail(self):
        """Test object depth validation with excessive nesting."""
        # Create deeply nested object (11 levels deep)
        nested_obj = {"level": "start"}
        current = nested_obj
        for i in range(11):  # Exceeds default limit of 10
            current[f"level{i}"] = {}
            current = current[f"level{i}"]
        current["end"] = "value"
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_object_structure(nested_obj)
        
        assert "nesting depth" in str(exc_info.value)
        assert "exceeds maximum" in str(exc_info.value)
    
    def test_object_keys_validation_fail(self):
        """Test object key count validation."""
        # Create object with too many keys
        large_obj = {f"key{i}": f"value{i}" for i in range(101)}  # Exceeds limit of 100
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_object_structure(large_obj)
        
        assert "keys" in str(exc_info.value)
        assert "exceeds maximum" in str(exc_info.value)
    
    def test_array_length_validation_fail(self):
        """Test array length validation."""
        large_array = [f"item{i}" for i in range(1001)]  # Exceeds limit of 1000
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_object_structure(large_array)
        
        assert "Array" in str(exc_info.value)
        assert "exceeds maximum" in str(exc_info.value)
    
    def test_unsupported_type_validation(self):
        """Test validation of unsupported data types."""
        unsupported_obj = {"function": lambda x: x}  # Functions not supported
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_object_structure(unsupported_obj)
        
        assert "Unsupported data type" in str(exc_info.value)
    
    def test_non_string_keys_validation(self):
        """Test validation of non-string object keys."""
        invalid_obj = {123: "numeric key not allowed"}
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_object_structure(invalid_obj)
        
        assert "Non-string key" in str(exc_info.value)
    
    def test_valid_data_types(self):
        """Test validation of valid data types."""
        valid_obj = {
            "string": "hello",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "nested": {"inner": "value"}
        }
        
        result = self.validator.validate_object_structure(valid_obj)
        
        # Should pass validation and return sanitized version
        assert isinstance(result, dict)
        assert result["string"] == "hello"
        assert result["integer"] == 42
        assert result["float"] == 3.14
        assert result["boolean"] is True
        assert result["null"] is None
        assert result["array"] == [1, 2, 3]
        assert result["nested"]["inner"] == "value"
    
    def test_tool_request_validation_valid(self):
        """Test complete tool request validation with valid data."""
        tool_name = "ping"
        arguments = {"message": "hello world"}
        
        result = self.validator.validate_tool_request(tool_name, arguments)
        
        assert result["tool_name"] == "ping"
        assert result["arguments"]["message"] == "hello world"
    
    def test_tool_request_validation_malicious(self):
        """Test complete tool request validation with malicious data."""
        tool_name = "ping"
        arguments = {"message": "<script>alert('xss')</script>"}
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_tool_request(tool_name, arguments)
        
        assert "XSS" in str(exc_info.value)
    
    def test_tool_request_validation_oversized(self):
        """Test complete tool request validation with oversized data."""
        tool_name = "ping"
        # Create oversized arguments
        large_message = "x" * (1024 * 1024)
        arguments = {"message": large_message}
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_tool_request(tool_name, arguments)
        
        assert "Payload size" in str(exc_info.value)


class TestSecurityIntegration:
    """Test security validation integration."""
    
    def test_global_validator_function(self):
        """Test global validation function."""
        tool_name = "ping"
        arguments = {"message": "test"}
        
        result = validate_request_security(tool_name, arguments)
        
        assert result["tool_name"] == "ping"
        assert result["arguments"]["message"] == "test"
    
    def test_global_validator_malicious(self):
        """Test global validation function with malicious input."""
        tool_name = "ping"
        arguments = {"message": "javascript:alert('xss')"}
        
        with pytest.raises(ValidationError):
            validate_request_security(tool_name, arguments)
    
    def test_security_configuration(self):
        """Test security configuration update."""
        original_config = SecurityConfig()
        custom_config = SecurityConfig(
            max_string_length=5000,
            security_level=SecurityLevel.STRICT
        )
        
        # Configure new security settings
        configure_security(custom_config)
        
        # Test that new settings are applied
        long_string = "x" * 6000  # Should fail with new limit of 5000
        
        with pytest.raises(ValidationError):
            validate_request_security("ping", {"message": long_string})
        
        # Restore original config
        configure_security(original_config)


class TestSecurityLevels:
    """Test different security levels."""
    
    def test_strict_level(self):
        """Test strict security level."""
        config = SecurityConfig(security_level=SecurityLevel.STRICT)
        validator = SecurityValidator(config)
        
        # Strict level should be more restrictive
        # (Implementation can be enhanced based on specific strict requirements)
        assert validator.config.security_level == SecurityLevel.STRICT
    
    def test_permissive_level(self):
        """Test permissive security level."""
        config = SecurityConfig(security_level=SecurityLevel.PERMISSIVE)
        validator = SecurityValidator(config)
        
        # Permissive level should be less restrictive
        # (Implementation can be enhanced based on specific permissive requirements)
        assert validator.config.security_level == SecurityLevel.PERMISSIVE
    
    def test_standard_level(self):
        """Test standard security level (default)."""
        config = SecurityConfig(security_level=SecurityLevel.STANDARD)
        validator = SecurityValidator(config)
        
        assert validator.config.security_level == SecurityLevel.STANDARD


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SecurityValidator()
    
    def test_empty_string_validation(self):
        """Test validation of empty strings."""
        result = self.validator.validate_string_content("", "empty_field")
        assert result == ""
    
    def test_unicode_validation(self):
        """Test validation of Unicode content."""
        unicode_text = "Hello 世界 🌍 مرحبا"
        result = self.validator.validate_string_content(unicode_text, "unicode_field")
        # Should handle Unicode properly
        assert "Hello" in result
    
    def test_special_characters_validation(self):
        """Test validation of special characters."""
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        result = self.validator.validate_string_content(special_chars, "special_field")
        # Special chars should be preserved (unless HTML escaping applies)
        assert len(result) > 0
    
    def test_none_values(self):
        """Test validation of None values."""
        obj_with_none = {"value": None, "array": [None, "test"]}
        result = self.validator.validate_object_structure(obj_with_none)
        
        assert result["value"] is None
        assert result["array"][0] is None
        assert result["array"][1] == "test"
    
    def test_nested_malicious_content(self):
        """Test validation of deeply nested malicious content."""
        nested_malicious = {
            "level1": {
                "level2": {
                    "malicious": "<script>alert('deep xss')</script>"
                }
            }
        }
        
        with pytest.raises(ValidationError) as exc_info:
            self.validator.validate_object_structure(nested_malicious)
        
        assert "XSS" in str(exc_info.value)
"""
Security validation and protection for Bio-MCP server.
Phase 1C: Production-ready security enhancements.
"""

import html
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .error_handling import ValidationError
from .logging_config import get_logger

logger = get_logger(__name__)


class SecurityLevel(str, Enum):
    """Security validation levels."""
    STRICT = "strict"      # Maximum security, may reject some valid inputs
    STANDARD = "standard"  # Balanced security and usability
    PERMISSIVE = "permissive"  # Minimal security, maximum compatibility


@dataclass
class SecurityConfig:
    """Security validation configuration."""
    # Input size limits
    max_payload_size: int = 1024 * 1024  # 1MB default
    max_string_length: int = 10000       # 10KB strings
    max_array_length: int = 1000         # Array item limit
    max_object_depth: int = 10           # Nested object depth
    max_object_keys: int = 100           # Object key limit
    
    # Content validation
    allow_html: bool = False             # Allow HTML in strings
    allow_scripts: bool = False          # Allow script-like content
    security_level: SecurityLevel = SecurityLevel.STANDARD
    
    # Pattern validation
    enable_xss_protection: bool = True
    enable_injection_protection: bool = True
    enable_path_traversal_protection: bool = True


class SecurityValidator:
    """Enhanced security validation for MCP inputs."""
    
    def __init__(self, config: SecurityConfig | None = None):
        self.config = config or SecurityConfig()
        self._setup_patterns()
    
    def _setup_patterns(self):
        """Initialize security pattern matching."""
        # XSS patterns
        self.xss_patterns = [
            re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
            re.compile(r'javascript:', re.IGNORECASE),
            re.compile(r'on\w+\s*=', re.IGNORECASE),  # onclick, onload, etc.
            re.compile(r'<iframe[^>]*>', re.IGNORECASE),
            re.compile(r'<object[^>]*>', re.IGNORECASE),
            re.compile(r'<embed[^>]*>', re.IGNORECASE),
        ]
        
        # SQL injection patterns
        self.injection_patterns = [
            re.compile(r'union\s+select', re.IGNORECASE),
            re.compile(r'insert\s+into', re.IGNORECASE),
            re.compile(r'delete\s+from', re.IGNORECASE),
            re.compile(r'drop\s+table', re.IGNORECASE),
            re.compile(r'exec\s*\(', re.IGNORECASE),
            re.compile(r'<\s*script\s*>', re.IGNORECASE),
        ]
        
        # Path traversal patterns
        self.path_patterns = [
            re.compile(r'\.\./'),
            re.compile(r'\.\.\\'),
            re.compile(r'/etc/passwd'),
            re.compile(r'\\windows\\system32'),
        ]
    
    def validate_payload_size(self, data: Any) -> None:
        """Validate total payload size."""
        try:
            serialized = json.dumps(data, ensure_ascii=False)
            size = len(serialized.encode('utf-8'))
            
            if size > self.config.max_payload_size:
                raise ValidationError(
                    f"Payload size {size} exceeds maximum {self.config.max_payload_size} bytes",
                    {"size": size, "max_size": self.config.max_payload_size}
                )
                
            logger.debug("Payload size validation passed", size=size, max_size=self.config.max_payload_size)
            
        except (TypeError, ValueError) as e:
            raise ValidationError(f"Invalid payload for size validation: {e}")
    
    def validate_string_content(self, value: str, field_name: str = "field") -> str:
        """Validate and sanitize string content."""
        if not isinstance(value, str):
            return value
        
        # Length validation
        if len(value) > self.config.max_string_length:
            raise ValidationError(
                f"String field '{field_name}' length {len(value)} exceeds maximum {self.config.max_string_length}",
                {"field": field_name, "length": len(value), "max_length": self.config.max_string_length}
            )
        
        # Security pattern validation
        if self.config.enable_xss_protection:
            for pattern in self.xss_patterns:
                if pattern.search(value):
                    logger.warning("XSS pattern detected", field=field_name, pattern=pattern.pattern)
                    raise ValidationError(
                        f"Field '{field_name}' contains potentially malicious content (XSS)",
                        {"field": field_name, "violation": "xss_detected"}
                    )
        
        if self.config.enable_injection_protection:
            for pattern in self.injection_patterns:
                if pattern.search(value):
                    logger.warning("Injection pattern detected", field=field_name, pattern=pattern.pattern)
                    raise ValidationError(
                        f"Field '{field_name}' contains potentially malicious content (injection)",
                        {"field": field_name, "violation": "injection_detected"}
                    )
        
        if self.config.enable_path_traversal_protection:
            for pattern in self.path_patterns:
                if pattern.search(value):
                    logger.warning("Path traversal pattern detected", field=field_name, pattern=pattern.pattern)
                    raise ValidationError(
                        f"Field '{field_name}' contains potentially malicious content (path traversal)",
                        {"field": field_name, "violation": "path_traversal_detected"}
                    )
        
        # Content sanitization
        if not self.config.allow_html:
            # HTML entity encoding for safety
            sanitized = html.escape(value)
            if sanitized != value:
                logger.debug("HTML content sanitized", field=field_name, original_length=len(value))
            return sanitized
        
        return value
    
    def validate_object_structure(self, obj: Any, depth: int = 0, path: str = "root") -> Any:
        """Recursively validate object structure and content."""
        # Depth validation
        if depth > self.config.max_object_depth:
            raise ValidationError(
                f"Object nesting depth {depth} exceeds maximum {self.config.max_object_depth}",
                {"path": path, "depth": depth, "max_depth": self.config.max_object_depth}
            )
        
        if isinstance(obj, dict):
            # Key count validation
            if len(obj) > self.config.max_object_keys:
                raise ValidationError(
                    f"Object at '{path}' has {len(obj)} keys, exceeds maximum {self.config.max_object_keys}",
                    {"path": path, "key_count": len(obj), "max_keys": self.config.max_object_keys}
                )
            
            # Validate each key-value pair
            validated = {}
            for key, value in obj.items():
                # Validate key
                if not isinstance(key, str):
                    raise ValidationError(f"Non-string key found at '{path}': {type(key)}")
                
                sanitized_key = self.validate_string_content(key, f"{path}.{key}")
                new_path = f"{path}.{sanitized_key}"
                
                # Recursively validate value
                validated[sanitized_key] = self.validate_object_structure(value, depth + 1, new_path)
            
            return validated
        
        elif isinstance(obj, list):
            # Array length validation
            if len(obj) > self.config.max_array_length:
                raise ValidationError(
                    f"Array at '{path}' has {len(obj)} items, exceeds maximum {self.config.max_array_length}",
                    {"path": path, "length": len(obj), "max_length": self.config.max_array_length}
                )
            
            # Validate each item
            validated = []
            for i, item in enumerate(obj):
                item_path = f"{path}[{i}]"
                validated.append(self.validate_object_structure(item, depth + 1, item_path))
            
            return validated
        
        elif isinstance(obj, str):
            return self.validate_string_content(obj, path)
        
        elif isinstance(obj, int | float | bool) or obj is None:
            return obj
        
        else:
            # Unknown type
            raise ValidationError(
                f"Unsupported data type at '{path}': {type(obj)}",
                {"path": path, "type": str(type(obj))}
            )
    
    def validate_tool_request(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Comprehensive validation of tool request."""
        logger.debug("Starting security validation", tool=tool_name, config=self.config.security_level)
        
        # Validate payload size
        self.validate_payload_size({"tool": tool_name, "arguments": arguments})
        
        # Validate tool name
        sanitized_tool_name = self.validate_string_content(tool_name, "tool_name")
        
        # Validate arguments structure
        sanitized_arguments = self.validate_object_structure(arguments, path="arguments")
        
        logger.info("Security validation passed", tool=sanitized_tool_name)
        
        return {
            "tool_name": sanitized_tool_name,
            "arguments": sanitized_arguments
        }


# Global security validator instance
_default_config = SecurityConfig()
security_validator = SecurityValidator(_default_config)


def validate_request_security(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Convenience function for security validation."""
    return security_validator.validate_tool_request(tool_name, arguments)


def configure_security(config: SecurityConfig) -> None:
    """Configure global security settings."""
    global security_validator
    security_validator = SecurityValidator(config)
    logger.info("Security configuration updated", level=config.security_level)
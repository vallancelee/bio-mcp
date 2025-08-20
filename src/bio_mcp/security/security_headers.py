"""
Security headers and input validation for Bio-MCP server.
Phase 1C: Production MCP Server security enhancements.
"""

import re
import time
from dataclasses import dataclass
from typing import Any

from ..config.logging_config import get_logger
from ..core.error_handling import ErrorCode, MCPError

logger = get_logger(__name__)


@dataclass(frozen=True)
class SecurityConfig:
    """Security configuration parameters."""
    
    # Input validation limits
    MAX_STRING_LENGTH: int = 10000  # Maximum string input length
    MAX_QUERY_LENGTH: int = 1000    # Maximum search query length
    MAX_ARRAY_SIZE: int = 100       # Maximum array size
    MAX_PMID_LENGTH: int = 20       # Maximum PMID length
    
    # Rate limiting
    DEFAULT_RATE_LIMIT: int = 100   # Requests per minute per client
    BURST_LIMIT: int = 20           # Burst requests allowed
    
    # Security patterns
    SUSPICIOUS_PATTERNS: frozenset[str] = frozenset([
        # SQL injection patterns
        r"(?i)\b(union|select|insert|update|delete|drop|create|alter)\s",
        r"(?i)[\'\";].*(\bor\b|\band\b).*[\'\";]",
        r"(?i)\b(exec|execute|sp_|xp_)\b",
        
        # Script injection patterns  
        r"(?i)<script[^>]*>",
        r"(?i)javascript:",
        r"(?i)on\w+\s*=",
        
        # Path traversal
        r"\.\.\/",
        r"\.\.\\\\",
        
        # Command injection
        r"[;&|`$(){}[\]]",
        r"(?i)\b(rm|cat|ls|pwd|whoami|id|uname)\b",
    ])
    
    # Allowed characters for different input types
    PMID_PATTERN: re.Pattern = re.compile(r"^[0-9]{1,20}$")
    SAFE_STRING_PATTERN: re.Pattern = re.compile(r"^[a-zA-Z0-9\s\.\-_:@/,()[\]{}]+$")
    QUERY_PATTERN: re.Pattern = re.compile(r"^[a-zA-Z0-9\s\.\-_:@/,()[\]{}\"'*+?]+$")


class SecurityValidator:
    """Security validation for MCP inputs."""
    
    def __init__(self, config: SecurityConfig | None = None):
        self.config = config or SecurityConfig()
    
    def validate_input(self, field_name: str, value: Any, input_type: str = "string") -> None:
        """
        Validate input for security threats and format compliance.
        
        Args:
            field_name: Name of the input field
            value: Input value to validate
            input_type: Type of input (string, pmid, query, array)
            
        Raises:
            MCPError: If input fails security validation
        """
        if value is None:
            return  # Allow None values for optional fields
        
        # Type-specific validation
        if input_type == "string":
            self._validate_string(field_name, value)
        elif input_type == "pmid":
            self._validate_pmid(field_name, value)
        elif input_type == "query":
            self._validate_query(field_name, value)
        elif input_type == "array":
            self._validate_array(field_name, value)
        elif input_type == "number":
            self._validate_number(field_name, value)
        elif input_type == "boolean":
            self._validate_boolean(field_name, value)
        else:
            logger.warning("Unknown input type for validation", field=field_name, type=input_type)
    
    def _validate_string(self, field_name: str, value: Any) -> None:
        """Validate general string input."""
        if not isinstance(value, str):
            raise MCPError(
                f"Field '{field_name}' must be a string",
                ErrorCode.VALIDATION,
                {"field": field_name, "type": type(value).__name__}
            )
        
        # Length check
        if len(value) > self.config.MAX_STRING_LENGTH:
            raise MCPError(
                f"Field '{field_name}' exceeds maximum length of {self.config.MAX_STRING_LENGTH}",
                ErrorCode.VALIDATION,
                {"field": field_name, "length": len(value), "max_length": self.config.MAX_STRING_LENGTH}
            )
        
        # Security pattern check
        self._check_suspicious_patterns(field_name, value)
    
    def _validate_pmid(self, field_name: str, value: Any) -> None:
        """Validate PMID format."""
        if not isinstance(value, str):
            raise MCPError(
                f"PMID field '{field_name}' must be a string",
                ErrorCode.VALIDATION,
                {"field": field_name, "type": type(value).__name__}
            )
        
        if len(value) > self.config.MAX_PMID_LENGTH:
            raise MCPError(
                f"PMID '{field_name}' exceeds maximum length of {self.config.MAX_PMID_LENGTH}",
                ErrorCode.VALIDATION,
                {"field": field_name, "length": len(value)}
            )
        
        if not self.config.PMID_PATTERN.match(value):
            raise MCPError(
                f"PMID '{field_name}' contains invalid characters. Only digits allowed.",
                ErrorCode.VALIDATION,
                {"field": field_name, "value": value}
            )
    
    def _validate_query(self, field_name: str, value: Any) -> None:
        """Validate search query input."""
        if not isinstance(value, str):
            raise MCPError(
                f"Query field '{field_name}' must be a string",
                ErrorCode.VALIDATION,
                {"field": field_name, "type": type(value).__name__}
            )
        
        if len(value) > self.config.MAX_QUERY_LENGTH:
            raise MCPError(
                f"Query '{field_name}' exceeds maximum length of {self.config.MAX_QUERY_LENGTH}",
                ErrorCode.VALIDATION,
                {"field": field_name, "length": len(value)}
            )
        
        # More permissive pattern for search queries but still secure
        if not self.config.QUERY_PATTERN.match(value):
            raise MCPError(
                f"Query '{field_name}' contains invalid characters",
                ErrorCode.VALIDATION,
                {"field": field_name, "pattern": "alphanumeric with basic punctuation"}
            )
        
        # Security pattern check
        self._check_suspicious_patterns(field_name, value)
    
    def _validate_array(self, field_name: str, value: Any) -> None:
        """Validate array input."""
        if not isinstance(value, list):
            raise MCPError(
                f"Field '{field_name}' must be an array",
                ErrorCode.VALIDATION,
                {"field": field_name, "type": type(value).__name__}
            )
        
        if len(value) > self.config.MAX_ARRAY_SIZE:
            raise MCPError(
                f"Array '{field_name}' exceeds maximum size of {self.config.MAX_ARRAY_SIZE}",
                ErrorCode.VALIDATION,
                {"field": field_name, "size": len(value)}
            )
        
        # Validate each element
        for i, item in enumerate(value):
            if isinstance(item, str):
                self._validate_string(f"{field_name}[{i}]", item)
    
    def _validate_number(self, field_name: str, value: Any) -> None:
        """Validate numeric input."""
        if not isinstance(value, int | float):
            raise MCPError(
                f"Field '{field_name}' must be a number",
                ErrorCode.VALIDATION,
                {"field": field_name, "type": type(value).__name__}
            )
        
        # Range checks for common fields
        if field_name in ("limit", "top_k") and (value < 1 or value > 1000):
            raise MCPError(
                f"Field '{field_name}' must be between 1 and 1000",
                ErrorCode.VALIDATION,
                {"field": field_name, "value": value}
            )
        
        if field_name == "alpha" and (value < 0.0 or value > 1.0):
            raise MCPError(
                f"Field '{field_name}' must be between 0.0 and 1.0",
                ErrorCode.VALIDATION,
                {"field": field_name, "value": value}
            )
    
    def _validate_boolean(self, field_name: str, value: Any) -> None:
        """Validate boolean input."""
        if not isinstance(value, bool):
            raise MCPError(
                f"Field '{field_name}' must be a boolean",
                ErrorCode.VALIDATION,
                {"field": field_name, "type": type(value).__name__}
            )
    
    def _check_suspicious_patterns(self, field_name: str, value: str) -> None:
        """Check for suspicious security patterns."""
        for pattern in self.config.SUSPICIOUS_PATTERNS:
            if re.search(pattern, value):
                logger.warning(
                    "Suspicious pattern detected in input", 
                    field=field_name, 
                    pattern=pattern,
                    value_preview=value[:100] + "..." if len(value) > 100 else value
                )
                raise MCPError(
                    f"Input '{field_name}' contains potentially unsafe content",
                    ErrorCode.VALIDATION,
                    {"field": field_name, "reason": "suspicious_pattern"}
                )


@dataclass
class RequestContext:
    """Context for tracking request information."""
    client_id: str | None = None
    request_time: float = None
    tool_name: str | None = None
    ip_address: str | None = None
    
    def __post_init__(self):
        if self.request_time is None:
            self.request_time = time.time()


class SecurityHeaders:
    """Security headers and metadata for MCP responses."""
    
    @staticmethod
    def get_security_headers() -> dict[str, str]:
        """Get standard security headers for HTTP responses."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY", 
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'; script-src 'none'; object-src 'none'",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        }
    
    @staticmethod
    def get_response_metadata(context: RequestContext) -> dict[str, Any]:
        """Get response metadata including security context."""
        processing_time = time.time() - (context.request_time or time.time())
        
        return {
            "server": "Bio-MCP-Server/1.0",
            "processing_time_ms": round(processing_time * 1000, 2),
            "request_id": f"req_{int(context.request_time or 0) % 100000:05d}",
            "security_level": "production",
            "timestamp": int(time.time())
        }


# Global security validator instance
_security_validator: SecurityValidator | None = None


def get_security_validator() -> SecurityValidator:
    """Get the global security validator instance."""
    global _security_validator
    if _security_validator is None:
        _security_validator = SecurityValidator()
    return _security_validator


def validate_tool_input(tool_name: str, arguments: dict[str, Any]) -> RequestContext:
    """
    Enhanced security validation for tool inputs.
    
    Args:
        tool_name: Name of the tool being called
        arguments: Tool arguments to validate
        
    Returns:
        RequestContext with security metadata
        
    Raises:
        MCPError: If validation fails
    """
    validator = get_security_validator()
    context = RequestContext(tool_name=tool_name)
    
    logger.debug("Starting security validation", tool=tool_name, arg_count=len(arguments))
    
    # Tool-specific validation rules
    validation_rules = {
        "pubmed.search": {
            "term": "query",
            "limit": "number",
            "offset": "number"
        },
        "pubmed.get": {
            "pmid": "pmid"
        },
        "pubmed.sync": {
            "query": "query", 
            "limit": "number"
        },
        "pubmed.sync.incremental": {
            "query": "query",
            "limit": "number"
        },
        "rag.search": {
            "query": "query",
            "top_k": "number",
            "search_mode": "string",
            "alpha": "number",
            "rerank_by_quality": "boolean",
            "filters": "object"
        },
        "rag.get": {
            "doc_id": "string"
        },
        "corpus.checkpoint.create": {
            "checkpoint_id": "string",
            "name": "string", 
            "description": "string",
            "primary_queries": "array"
        },
        "corpus.checkpoint.get": {
            "checkpoint_id": "string"
        },
        "corpus.checkpoint.list": {
            "limit": "number",
            "offset": "number"
        },
        "corpus.checkpoint.delete": {
            "checkpoint_id": "string"
        }
    }
    
    # Apply validation rules
    if tool_name in validation_rules:
        rules = validation_rules[tool_name]
        for field_name, value in arguments.items():
            if field_name in rules:
                validator.validate_input(field_name, value, rules[field_name])
            else:
                # Unknown field - validate as string by default
                validator.validate_input(field_name, value, "string")
    else:
        # Unknown tool - validate all fields as strings
        for field_name, value in arguments.items():
            validator.validate_input(field_name, value, "string")
    
    logger.debug("Security validation completed", tool=tool_name, context_id=context.request_id)
    return context
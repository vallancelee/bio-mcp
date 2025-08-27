"""Error recovery functionality for orchestrator."""

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.state import NodeResult, OrchestratorState


class ErrorType(Enum):
    """Types of errors that can occur."""

    RATE_LIMIT = "rate_limit"
    NETWORK_TIMEOUT = "network_timeout"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    SERVICE_UNAVAILABLE = "service_unavailable"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Severity levels for errors."""

    RECOVERABLE = "recoverable"
    CRITICAL = "critical"
    NON_RECOVERABLE = "non_recoverable"


class RecoveryAction(Enum):
    """Recovery actions that can be taken."""

    RETRY_WITH_BACKOFF = "retry_with_backoff"
    SKIP_AND_CONTINUE = "skip_and_continue"
    PARTIAL_RESULTS = "partial_results"
    FAIL_PERMANENTLY = "fail_permanently"


@dataclass
class RecoveryStrategy:
    """Strategy for recovering from an error."""

    action: RecoveryAction
    reason: str
    should_continue: bool
    delay_seconds: float = 0.0


class ErrorClassifier:
    """Classifies errors to determine appropriate recovery strategies."""

    def __init__(self, config: OrchestratorConfig):
        """Initialize error classifier.

        Args:
            config: Orchestrator configuration
        """
        self.config = config

        # Error pattern mappings
        self.rate_limit_patterns = [
            r"rate limit",
            r"429.*too many requests",
            r"quota.*exceeded",
            r"throttling",
        ]

        self.timeout_patterns = [
            r"timeout",
            r"timed out",
            r"connection.*failed",
            r"connection.*refused",
            r"connection.*reset",
        ]

        self.auth_patterns = [
            r"authentication.*failed",
            r"invalid.*api.*key",
            r"unauthorized",
            r"401.*unauthorized",
            r"403.*forbidden",
        ]

        self.validation_patterns = [
            r"invalid.*parameter",
            r"validation.*error",
            r"invalid.*query",
            r"missing.*required",
            r"cannot be empty",
        ]

        self.service_patterns = [
            r"service.*unavailable",
            r"503.*service",
            r"server.*error",
            r"502.*bad gateway",
            r"504.*gateway timeout",
        ]

    def classify_error(
        self, node_result: NodeResult
    ) -> tuple[ErrorType, ErrorSeverity]:
        """Classify an error based on node result.

        Args:
            node_result: Failed node result

        Returns:
            Tuple of (error_type, severity)
        """
        error_msg = (
            node_result.error_message.lower() if node_result.error_message else ""
        )

        # Check rate limit patterns
        if self._matches_patterns(error_msg, self.rate_limit_patterns):
            return ErrorType.RATE_LIMIT, ErrorSeverity.RECOVERABLE

        # Check timeout patterns
        if self._matches_patterns(error_msg, self.timeout_patterns):
            return ErrorType.NETWORK_TIMEOUT, ErrorSeverity.RECOVERABLE

        # Check authentication patterns
        if self._matches_patterns(error_msg, self.auth_patterns):
            return ErrorType.AUTHENTICATION, ErrorSeverity.CRITICAL

        # Check validation patterns
        if self._matches_patterns(error_msg, self.validation_patterns):
            return ErrorType.VALIDATION, ErrorSeverity.NON_RECOVERABLE

        # Check service unavailable patterns
        if self._matches_patterns(error_msg, self.service_patterns):
            return ErrorType.SERVICE_UNAVAILABLE, ErrorSeverity.RECOVERABLE

        # Default classification
        return ErrorType.UNKNOWN, ErrorSeverity.RECOVERABLE

    def _matches_patterns(self, text: str, patterns: list[str]) -> bool:
        """Check if text matches any of the given patterns.

        Args:
            text: Text to check
            patterns: List of regex patterns

        Returns:
            True if any pattern matches
        """
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


class ErrorRecoveryManager:
    """Manages error recovery strategies and execution."""

    def __init__(
        self,
        config: OrchestratorConfig,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
    ):
        """Initialize error recovery manager.

        Args:
            config: Orchestrator configuration
            max_retries: Maximum number of retries per node
            base_retry_delay: Base delay for exponential backoff
        """
        self.config = config
        self.classifier = ErrorClassifier(config)
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay

    async def create_recovery_strategy(
        self, error_result: NodeResult, attempt: int, max_attempts: int
    ) -> RecoveryStrategy:
        """Create a recovery strategy for an error.

        Args:
            error_result: The failed node result
            attempt: Current attempt number (1-based)
            max_attempts: Maximum allowed attempts

        Returns:
            Recovery strategy to execute
        """
        error_type, severity = self.classifier.classify_error(error_result)

        # Check if we've reached max attempts
        if attempt >= max_attempts:
            return RecoveryStrategy(
                action=RecoveryAction.FAIL_PERMANENTLY,
                reason=f"Max retries ({max_attempts}) exceeded",
                should_continue=False,
            )

        # Determine recovery action based on error type and severity
        if severity == ErrorSeverity.CRITICAL:
            return RecoveryStrategy(
                action=RecoveryAction.FAIL_PERMANENTLY,
                reason=f"Critical {error_type.value} error - cannot recover",
                should_continue=False,
            )

        if severity == ErrorSeverity.NON_RECOVERABLE:
            return RecoveryStrategy(
                action=RecoveryAction.SKIP_AND_CONTINUE,
                reason=f"Non-recoverable {error_type.value} error - skipping node",
                should_continue=True,
            )

        # For recoverable errors, determine best action
        if self._should_retry(error_type, severity, attempt, max_attempts):
            delay = self._calculate_retry_delay(attempt)
            return RecoveryStrategy(
                action=RecoveryAction.RETRY_WITH_BACKOFF,
                reason=f"Recoverable {error_type.value} error - retrying with backoff",
                should_continue=True,
                delay_seconds=delay,
            )

        # If can't retry, try to continue with partial results
        return RecoveryStrategy(
            action=RecoveryAction.PARTIAL_RESULTS,
            reason=f"Using partial results due to {error_type.value} error",
            should_continue=True,
        )

    async def execute_recovery(
        self,
        strategy: RecoveryStrategy,
        state: OrchestratorState,
        error_result: NodeResult,
        node_name: str,
    ) -> OrchestratorState:
        """Execute a recovery strategy.

        Args:
            strategy: Recovery strategy to execute
            state: Current orchestrator state
            error_result: The failed node result
            node_name: Name of the failed node

        Returns:
            Updated state after recovery
        """
        # Apply delay if specified
        if strategy.delay_seconds > 0:
            await asyncio.sleep(strategy.delay_seconds)

        # Create error record
        error_record = {
            "node": node_name,
            "error": error_result.error_message,
            "timestamp": datetime.now(UTC).isoformat(),
            "strategy": strategy.action.value,
            "reason": strategy.reason,
        }

        # Update state based on recovery action
        updated_state = OrchestratorState(
            query=state["query"] if isinstance(state, dict) else state.query,
            config=state["config"] if isinstance(state, dict) else state.config,
            frame=state["frame"] if isinstance(state, dict) else state.frame,
            routing_decision=state["routing_decision"]
            if isinstance(state, dict)
            else state.routing_decision,
            pubmed_results=state["pubmed_results"]
            if isinstance(state, dict)
            else state.pubmed_results,
            ctgov_results=state.get("ctgov_results")
            if isinstance(state, dict)
            else getattr(state, "ctgov_results", None),
            rag_results=state.get("rag_results")
            if isinstance(state, dict)
            else getattr(state, "rag_results", None),
            tool_calls_made=list(state["tool_calls_made"])
            if isinstance(state, dict)
            else list(state.tool_calls_made),
            cache_hits=dict(state["cache_hits"])
            if isinstance(state, dict)
            else dict(state.cache_hits),
            latencies=dict(state["latencies"])
            if isinstance(state, dict)
            else dict(state.latencies),
            node_path=list(state["node_path"])
            if isinstance(state, dict)
            else list(state.node_path),
            messages=list(state["messages"])
            if isinstance(state, dict)
            else list(state.messages),
            errors=list(state["errors"]) + [error_record]
            if isinstance(state, dict)
            else list(state.errors) + [error_record],
            answer=state.get("answer")
            if isinstance(state, dict)
            else getattr(state, "answer", None),
            session_id=state.get("session_id")
            if isinstance(state, dict)
            else getattr(state, "session_id", None),
        )

        # Add recovery marker to node path
        if strategy.action == RecoveryAction.SKIP_AND_CONTINUE:
            updated_state["node_path"].append("recovery_skipped")
        elif strategy.action == RecoveryAction.PARTIAL_RESULTS:
            updated_state["node_path"].append("recovery_partial")
        elif strategy.action == RecoveryAction.RETRY_WITH_BACKOFF:
            updated_state["node_path"].append("recovery_retry")
        elif strategy.action == RecoveryAction.FAIL_PERMANENTLY:
            updated_state["node_path"].append("recovery_failed")

        return updated_state

    def _should_retry(
        self,
        error_type: ErrorType,
        severity: ErrorSeverity,
        attempt: int,
        max_attempts: int,
    ) -> bool:
        """Determine if we should retry based on error characteristics.

        Args:
            error_type: Type of error
            severity: Severity of error
            attempt: Current attempt number
            max_attempts: Maximum allowed attempts

        Returns:
            True if should retry
        """
        # Don't retry critical or non-recoverable errors
        if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.NON_RECOVERABLE]:
            return False

        # Don't retry if we've exceeded max attempts
        if attempt >= max_attempts:
            return False

        # Retry recoverable errors within limits
        return severity == ErrorSeverity.RECOVERABLE

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay using exponential backoff.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: delay = base_delay * (2 ^ (attempt - 1))
        return self.base_retry_delay * (2 ** (attempt - 1))

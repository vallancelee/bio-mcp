"""Test error recovery functionality."""
from datetime import datetime, UTC
from typing import Any

import pytest

from bio_mcp.orchestrator.config import OrchestratorConfig
from bio_mcp.orchestrator.error.recovery import (
    ErrorClassifier,
    ErrorRecoveryManager,
    ErrorSeverity,
    ErrorType,
    RecoveryAction,
    RecoveryStrategy,
)
from bio_mcp.orchestrator.state import NodeResult, OrchestratorState


class TestErrorClassifier:
    """Test ErrorClassifier implementation."""
    
    def test_init_error_classifier(self):
        """Test ErrorClassifier initialization."""
        config = OrchestratorConfig()
        classifier = ErrorClassifier(config)
        
        assert classifier.config == config
    
    def test_classify_rate_limit_error(self):
        """Test classification of rate limit errors."""
        config = OrchestratorConfig()
        classifier = ErrorClassifier(config)
        
        # Test rate limit error
        node_result = NodeResult(
            success=False,
            error_message="Rate limit exceeded: 429 Too Many Requests",
            node_name="pubmed_search"
        )
        
        error_type, severity = classifier.classify_error(node_result)
        
        assert error_type == ErrorType.RATE_LIMIT
        assert severity == ErrorSeverity.RECOVERABLE
    
    def test_classify_network_timeout_error(self):
        """Test classification of network timeout errors."""
        config = OrchestratorConfig()
        classifier = ErrorClassifier(config)
        
        # Test timeout error  
        node_result = NodeResult(
            success=False,
            error_message="Request timeout after 30 seconds",
            node_name="trials_search"
        )
        
        error_type, severity = classifier.classify_error(node_result)
        
        assert error_type == ErrorType.NETWORK_TIMEOUT
        assert severity == ErrorSeverity.RECOVERABLE
    
    def test_classify_authentication_error(self):
        """Test classification of authentication errors."""
        config = OrchestratorConfig()
        classifier = ErrorClassifier(config)
        
        # Test auth error
        node_result = NodeResult(
            success=False,
            error_message="Authentication failed: Invalid API key",
            node_name="pubmed_search"
        )
        
        error_type, severity = classifier.classify_error(node_result)
        
        assert error_type == ErrorType.AUTHENTICATION
        assert severity == ErrorSeverity.CRITICAL
    
    def test_classify_validation_error(self):
        """Test classification of validation errors."""
        config = OrchestratorConfig()
        classifier = ErrorClassifier(config)
        
        # Test validation error
        node_result = NodeResult(
            success=False,
            error_message="Invalid query parameter: term cannot be empty",
            node_name="pubmed_search"
        )
        
        error_type, severity = classifier.classify_error(node_result)
        
        assert error_type == ErrorType.VALIDATION
        assert severity == ErrorSeverity.NON_RECOVERABLE
    
    def test_classify_service_unavailable_error(self):
        """Test classification of service unavailable errors."""
        config = OrchestratorConfig()
        classifier = ErrorClassifier(config)
        
        # Test service unavailable
        node_result = NodeResult(
            success=False,
            error_message="Service unavailable: 503 Service Temporarily Unavailable",
            node_name="trials_search"
        )
        
        error_type, severity = classifier.classify_error(node_result)
        
        assert error_type == ErrorType.SERVICE_UNAVAILABLE
        assert severity == ErrorSeverity.RECOVERABLE
    
    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        config = OrchestratorConfig()
        classifier = ErrorClassifier(config)
        
        # Test unknown error
        node_result = NodeResult(
            success=False,
            error_message="Something weird happened internally",
            node_name="custom_node"
        )
        
        error_type, severity = classifier.classify_error(node_result)
        
        assert error_type == ErrorType.UNKNOWN
        assert severity == ErrorSeverity.RECOVERABLE  # Default to recoverable
    
    def test_classify_by_node_name(self):
        """Test error classification considering node context."""
        config = OrchestratorConfig()
        classifier = ErrorClassifier(config)
        
        # Same error message from different nodes
        generic_error = NodeResult(
            success=False,
            error_message="Connection failed",
            node_name="pubmed_search"
        )
        
        error_type, severity = classifier.classify_error(generic_error)
        assert error_type == ErrorType.NETWORK_TIMEOUT  # Connection issues treated as network
        
        # Test with different node
        frame_error = NodeResult(
            success=False,
            error_message="Connection failed",
            node_name="frame_parser"
        )
        
        error_type, severity = classifier.classify_error(frame_error)
        assert error_type == ErrorType.NETWORK_TIMEOUT


class TestErrorRecoveryManager:
    """Test ErrorRecoveryManager implementation."""
    
    def test_init_recovery_manager(self):
        """Test ErrorRecoveryManager initialization."""
        config = OrchestratorConfig()
        manager = ErrorRecoveryManager(config)
        
        assert manager.config == config
        assert isinstance(manager.classifier, ErrorClassifier)
        assert manager.max_retries == 3
        assert manager.base_retry_delay == 1.0
    
    @pytest.mark.asyncio
    async def test_create_recovery_strategy_rate_limit(self):
        """Test creating recovery strategy for rate limit errors."""
        config = OrchestratorConfig()
        manager = ErrorRecoveryManager(config)
        
        error_result = NodeResult(
            success=False,
            error_message="Rate limit exceeded",
            node_name="pubmed_search"
        )
        
        strategy = await manager.create_recovery_strategy(error_result, attempt=1, max_attempts=3)
        
        assert strategy.action == RecoveryAction.RETRY_WITH_BACKOFF
        assert strategy.delay_seconds > 0
        assert strategy.should_continue is True
        assert "rate_limit" in strategy.reason.lower()
    
    @pytest.mark.asyncio
    async def test_create_recovery_strategy_network_timeout(self):
        """Test creating recovery strategy for network timeout errors.""" 
        config = OrchestratorConfig()
        manager = ErrorRecoveryManager(config)
        
        error_result = NodeResult(
            success=False,
            error_message="Request timeout",
            node_name="trials_search" 
        )
        
        strategy = await manager.create_recovery_strategy(error_result, attempt=2, max_attempts=3)
        
        assert strategy.action == RecoveryAction.RETRY_WITH_BACKOFF
        assert strategy.delay_seconds > 0
        assert strategy.should_continue is True
    
    @pytest.mark.asyncio
    async def test_create_recovery_strategy_authentication(self):
        """Test creating recovery strategy for authentication errors."""
        config = OrchestratorConfig()
        manager = ErrorRecoveryManager(config)
        
        error_result = NodeResult(
            success=False,
            error_message="Invalid API key",
            node_name="pubmed_search"
        )
        
        strategy = await manager.create_recovery_strategy(error_result, attempt=1, max_attempts=3)
        
        assert strategy.action == RecoveryAction.FAIL_PERMANENTLY
        assert strategy.should_continue is False
        assert "authentication" in strategy.reason.lower()
    
    @pytest.mark.asyncio
    async def test_create_recovery_strategy_validation(self):
        """Test creating recovery strategy for validation errors."""
        config = OrchestratorConfig()
        manager = ErrorRecoveryManager(config)
        
        error_result = NodeResult(
            success=False,
            error_message="Invalid query parameter",
            node_name="pubmed_search"
        )
        
        strategy = await manager.create_recovery_strategy(error_result, attempt=1, max_attempts=3)
        
        assert strategy.action == RecoveryAction.SKIP_AND_CONTINUE
        assert strategy.should_continue is True
        assert "validation" in strategy.reason.lower()
    
    @pytest.mark.asyncio
    async def test_create_recovery_strategy_max_retries(self):
        """Test recovery strategy when max retries exceeded."""
        config = OrchestratorConfig()
        manager = ErrorRecoveryManager(config)
        
        error_result = NodeResult(
            success=False,
            error_message="Rate limit exceeded",
            node_name="pubmed_search"
        )
        
        # Simulate reaching max retries
        strategy = await manager.create_recovery_strategy(error_result, attempt=3, max_attempts=3)
        
        assert strategy.action == RecoveryAction.FAIL_PERMANENTLY
        assert strategy.should_continue is False
        assert "max retries" in strategy.reason.lower()
    
    @pytest.mark.asyncio
    async def test_execute_recovery_skip_and_continue(self):
        """Test executing skip and continue recovery."""
        config = OrchestratorConfig()
        manager = ErrorRecoveryManager(config)
        
        state = OrchestratorState(
            query="test query",
            config={},
            frame={},
            routing_decision=None,
            pubmed_results=None,
            tool_calls_made=[],
            cache_hits={},
            latencies={},
            node_path=["frame_parser"],
            messages=[],
            errors=[]
        )
        
        strategy = RecoveryStrategy(
            action=RecoveryAction.SKIP_AND_CONTINUE,
            reason="Validation error - skipping node",
            should_continue=True,
            delay_seconds=0
        )
        
        node_result = NodeResult(
            success=False,
            error_message="Invalid parameter",
            node_name="pubmed_search"
        )
        
        recovered_state = await manager.execute_recovery(strategy, state, node_result, "pubmed_search")
        
        # Should add error to state but continue
        assert len(recovered_state["errors"]) == 1
        assert recovered_state["errors"][0]["node"] == "pubmed_search"
        assert recovered_state["errors"][0]["strategy"] == "skip_and_continue"
        assert "recovery_skipped" in recovered_state["node_path"]
    
    @pytest.mark.asyncio
    async def test_execute_recovery_partial_results(self):
        """Test executing recovery with partial results preservation."""
        config = OrchestratorConfig()
        manager = ErrorRecoveryManager(config)
        
        # State with existing partial results
        state = OrchestratorState(
            query="diabetes research",
            config={},
            frame={"intent": "search"},
            routing_decision=None,
            pubmed_results={"results": [{"pmid": "12345"}], "total": 1},
            tool_calls_made=["pubmed.search"],
            cache_hits={"pubmed_search": True},
            latencies={"pubmed_search": 150.0},
            node_path=["frame_parser", "enhanced_pubmed"],
            messages=[{"role": "system", "content": "PubMed search completed"}],
            errors=[]
        )
        
        strategy = RecoveryStrategy(
            action=RecoveryAction.PARTIAL_RESULTS,
            reason="Network error - using partial results",
            should_continue=True,
            delay_seconds=0
        )
        
        node_result = NodeResult(
            success=False,
            error_message="Connection timeout",
            node_name="trials_search"
        )
        
        recovered_state = await manager.execute_recovery(strategy, state, node_result, "trials_search")
        
        # Should preserve existing results and mark as partial
        assert recovered_state["pubmed_results"] is not None
        assert len(recovered_state["errors"]) == 1
        assert recovered_state["errors"][0]["strategy"] == "partial_results"
        assert "recovery_partial" in recovered_state["node_path"]
    
    @pytest.mark.asyncio
    async def test_calculate_retry_delay(self):
        """Test retry delay calculation with exponential backoff."""
        config = OrchestratorConfig()
        manager = ErrorRecoveryManager(config)
        
        # Test exponential backoff
        delay1 = manager._calculate_retry_delay(1)
        delay2 = manager._calculate_retry_delay(2)
        delay3 = manager._calculate_retry_delay(3)
        
        assert delay1 == 1.0   # base delay
        assert delay2 == 2.0   # 2^1 * base
        assert delay3 == 4.0   # 2^2 * base
    
    def test_should_retry_logic(self):
        """Test retry decision logic."""
        config = OrchestratorConfig()
        manager = ErrorRecoveryManager(config)
        
        # Should retry for recoverable errors within limit
        assert manager._should_retry(ErrorType.RATE_LIMIT, ErrorSeverity.RECOVERABLE, 1, 3) is True
        assert manager._should_retry(ErrorType.NETWORK_TIMEOUT, ErrorSeverity.RECOVERABLE, 2, 3) is True
        
        # Should not retry for critical errors
        assert manager._should_retry(ErrorType.AUTHENTICATION, ErrorSeverity.CRITICAL, 1, 3) is False
        
        # Should not retry when max attempts reached
        assert manager._should_retry(ErrorType.RATE_LIMIT, ErrorSeverity.RECOVERABLE, 3, 3) is False
        assert manager._should_retry(ErrorType.NETWORK_TIMEOUT, ErrorSeverity.RECOVERABLE, 4, 3) is False
        
        # Should not retry non-recoverable errors
        assert manager._should_retry(ErrorType.VALIDATION, ErrorSeverity.NON_RECOVERABLE, 1, 3) is False
# T6: Back-Pressure & Per-Tool Concurrency Plan

**Goal:** Implement robust concurrency control with per-tool limits, back-pressure mechanisms, and graceful degradation to prevent system overload and ensure fair resource allocation.

## TDD Approach (Red-Green-Refactor)

1. **Write failing tests for global concurrency limits**
   - Test that system rejects requests beyond global limit
   - Test 429 (Too Many Requests) response with Retry-After header
   - Test queue depth monitoring and rejection
   - Test graceful degradation under load

2. **Write failing tests for per-tool semaphore behavior**
   - Test independent limits for different tools
   - Test that `pubmed.sync` limited to fewer concurrent than `rag.search`
   - Test semaphore release on success and failure
   - Test timeout handling doesn't leak semaphore permits

3. **Write failing tests for priority queue management**
   - Test high-priority tools get resources first
   - Test fair scheduling within same priority
   - Test queue reordering based on age/priority
   - Test queue overflow handling

4. **Implement semaphore-based concurrency control**
   - Create per-tool semaphores with configurable limits
   - Add queue depth monitoring and rejection logic
   - Implement Retry-After calculation based on queue state
   - Add circuit breaker for cascading failure prevention

5. **Refactor: extract concurrency manager with clean interfaces**
   - Create pluggable rate limiter interface
   - Implement priority-aware resource allocation
   - Add observability for queue depths and wait times
   - Create adaptive concurrency based on latency

## Clean Code Principles

- **Single Responsibility:** Separate rate limiting, queuing, and scheduling concerns
- **Open/Closed:** Extensible for new rate limiting strategies
- **Interface Segregation:** Clean API for different concurrency patterns
- **Dependency Inversion:** Abstract rate limiter interface, concrete implementations
- **Fail Fast:** Reject early when system is overloaded

## File Structure
```
src/bio_mcp/http/
├── concurrency/
│   ├── __init__.py
│   ├── manager.py       # Central concurrency coordinator
│   ├── limiters.py      # Rate limiter implementations
│   ├── semaphores.py    # Per-tool semaphore management
│   ├── queue.py         # Priority queue implementation
│   └── circuit.py       # Circuit breaker for failure isolation
├── middleware/
│   └── rate_limit.py    # HTTP middleware for rate limiting
```

## Implementation Details

### Per-Tool Concurrency Configuration
```python
TOOL_LIMITS = {
    # High-throughput, low-cost operations
    "rag.search": {
        "max_concurrent": 50,
        "queue_size": 100,
        "timeout_ms": 5000,
        "priority": 1
    },
    "rag.get": {
        "max_concurrent": 100,
        "queue_size": 200,
        "timeout_ms": 2000,
        "priority": 1
    },
    
    # Medium-throughput operations
    "pubmed.search": {
        "max_concurrent": 20,
        "queue_size": 40,
        "timeout_ms": 10000,
        "priority": 2
    },
    "pubmed.get": {
        "max_concurrent": 30,
        "queue_size": 60,
        "timeout_ms": 5000,
        "priority": 2
    },
    
    # Low-throughput, high-cost operations
    "pubmed.sync": {
        "max_concurrent": 5,
        "queue_size": 10,
        "timeout_ms": 300000,  # 5 minutes
        "priority": 3
    },
    "pubmed.sync_incremental": {
        "max_concurrent": 8,
        "queue_size": 16,
        "timeout_ms": 120000,  # 2 minutes
        "priority": 3
    },
    
    # Administrative operations
    "corpus.checkpoint.create": {
        "max_concurrent": 3,
        "queue_size": 6,
        "timeout_ms": 30000,
        "priority": 4
    }
}

# Global limits
GLOBAL_LIMITS = {
    "max_concurrent_total": 100,
    "max_queue_depth": 500,
    "max_memory_mb": 2048,
    "circuit_breaker_threshold": 0.5,  # 50% error rate
    "circuit_breaker_timeout": 60000   # 1 minute
}
```

### Back-Pressure Response Format
```json
{
  "ok": false,
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Tool 'pubmed.sync' has reached maximum concurrent requests (5)",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "tool": "pubmed.sync",
  "retry_after": 15,
  "queue_position": 3,
  "queue_depth": 8,
  "estimated_wait_ms": 15000
}
```

### Environment Configuration
```bash
# Global Concurrency
BIO_MCP_MAX_CONCURRENCY=100         # Total concurrent requests
BIO_MCP_MAX_QUEUE_DEPTH=500         # Maximum queued requests
BIO_MCP_QUEUE_TIMEOUT_MS=30000      # Queue wait timeout

# Per-Tool Overrides (optional)
BIO_MCP_TOOL_LIMIT_RAG_SEARCH=50
BIO_MCP_TOOL_LIMIT_PUBMED_SYNC=5
BIO_MCP_TOOL_QUEUE_PUBMED_SYNC=10

# Circuit Breaker
BIO_MCP_CIRCUIT_ENABLED=true
BIO_MCP_CIRCUIT_THRESHOLD=0.5       # Error rate threshold
BIO_MCP_CIRCUIT_TIMEOUT=60000       # Circuit open duration (ms)
BIO_MCP_CIRCUIT_HALF_OPEN_REQUESTS=3 # Requests in half-open state

# Adaptive Concurrency (Advanced)
BIO_MCP_ADAPTIVE_ENABLED=false      # Enable adaptive limits
BIO_MCP_ADAPTIVE_TARGET_P99=200     # Target P99 latency (ms)
BIO_MCP_ADAPTIVE_WINDOW=60000       # Measurement window (ms)
```

## Testing Strategy

### Unit Tests
```python
class TestConcurrencyLimits:
    """Test concurrency limit enforcement."""
    
    async def test_global_limit_enforcement(self):
        """Test global concurrent request limit."""
        
    async def test_per_tool_semaphore_limits(self):
        """Test individual tool concurrency limits."""
        
    async def test_queue_overflow_rejection(self):
        """Test requests rejected when queue full."""

class TestBackPressure:
    """Test back-pressure responses."""
    
    async def test_429_response_format(self):
        """Test 429 response includes Retry-After."""
        
    async def test_retry_after_calculation(self):
        """Test Retry-After based on queue state."""
        
    async def test_queue_position_tracking(self):
        """Test queue position in response."""

class TestCircuitBreaker:
    """Test circuit breaker behavior."""
    
    async def test_circuit_opens_on_errors(self):
        """Test circuit opens at error threshold."""
        
    async def test_circuit_half_open_recovery(self):
        """Test gradual recovery in half-open state."""
        
    async def test_circuit_closes_on_success(self):
        """Test circuit closes after successful requests."""
```

### Integration Tests
```python
class TestConcurrencyIntegration:
    """Test complete concurrency control system."""
    
    async def test_mixed_tool_load(self):
        """Test system handles mixed tool load correctly."""
        
    async def test_priority_scheduling(self):
        """Test high-priority tools get resources first."""
        
    async def test_graceful_degradation(self):
        """Test system degrades gracefully under load."""
        
    async def test_recovery_from_overload(self):
        """Test system recovers after overload."""
```

### Load Tests
```python
class TestLoadScenarios:
    """Test system under various load patterns."""
    
    async def test_sustained_load(self):
        """Test sustained high load handling."""
        
    async def test_burst_load(self):
        """Test burst traffic absorption."""
        
    async def test_mixed_priority_load(self):
        """Test fair scheduling under mixed load."""
```

## Performance Considerations

### Semaphore Optimization
- **Lock-free counting:** Use atomic operations where possible
- **Timeout handling:** Ensure timeouts release permits
- **Fair scheduling:** FIFO within priority levels
- **Async-safe:** No blocking in async context

### Queue Management
- **Bounded queues:** Prevent memory exhaustion
- **Priority queues:** Efficient O(log n) operations
- **Age tracking:** Prevent starvation
- **Metrics:** Queue depth and wait time histograms

### Circuit Breaker Efficiency
- **Sliding window:** Efficient error rate calculation
- **State machine:** Clear state transitions
- **Half-open probe:** Gradual recovery testing
- **Per-tool isolation:** Independent circuit breakers

## Acceptance Criteria

- [ ] Global concurrency limit enforced (100 default)
- [ ] Per-tool limits independently enforced
- [ ] 429 responses include Retry-After header
- [ ] Queue position provided in back-pressure response
- [ ] Circuit breaker prevents cascading failures
- [ ] No semaphore leaks under any error condition
- [ ] Priority scheduling for tool categories
- [ ] Graceful degradation under overload
- [ ] Metrics for queue depth and wait times
- [ ] Configuration via environment variables

## Success Metrics

1. **Overload Protection:** Zero OOM or crash under load
2. **Fair Scheduling:** P99 wait time <30s for priority tools
3. **Resource Utilization:** 80% CPU utilization at peak
4. **Error Prevention:** <0.1% timeout errors from overload
5. **Recovery Time:** <60s to recover from overload

## Advanced Features (Future)

### Adaptive Concurrency
```python
class AdaptiveConcurrencyController:
    """Dynamically adjust limits based on latency."""
    
    def adjust_limits(self, p99_latency: float):
        """Increase/decrease limits to maintain target latency."""
        if p99_latency > self.target_p99:
            self.decrease_limit()
        elif p99_latency < self.target_p99 * 0.8:
            self.increase_limit()
```

### Cost-Based Admission Control
```python
class CostBasedAdmission:
    """Admit requests based on resource cost."""
    
    TOOL_COSTS = {
        "rag.search": 1,      # Baseline cost
        "pubmed.search": 3,   # 3x more expensive
        "pubmed.sync": 20,    # 20x more expensive
    }
    
    def admit_request(self, tool: str) -> bool:
        """Check if request can be admitted based on cost."""
        cost = self.TOOL_COSTS.get(tool, 1)
        return self.available_budget >= cost
```

This comprehensive approach ensures robust concurrency control while maintaining system stability and fair resource allocation.
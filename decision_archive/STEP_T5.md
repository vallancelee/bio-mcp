# T5: Structured JSON Logging & Metrics Plan

**Goal:** Implement production-grade observability with structured JSON logging and comprehensive metrics for monitoring tool performance, errors, and system health.

## TDD Approach (Red-Green-Refactor)

1. **Write failing tests for JSON log output format**
   - Test that logs are valid JSON with required fields (ts, level, trace_id, etc.)
   - Test log level filtering and configuration from environment
   - Test sensitive data redaction (API keys, passwords)
   - Test log context preservation across async operations

2. **Write failing tests for tool-level metrics collection**
   - Test request counter increments per tool
   - Test error counter categorization by error_code
   - Test latency histogram buckets (p50, p95, p99)
   - Test concurrent request gauge tracking

3. **Write failing tests for metrics export formats**
   - Test Prometheus text format generation
   - Test CloudWatch EMF (Embedded Metric Format) output
   - Test metrics aggregation over time windows
   - Test cardinality limits for label combinations

4. **Implement structured logging with proper context**
   - Configure structlog with JSON renderer
   - Add request/response middleware for automatic logging
   - Implement log correlation with trace_id
   - Add performance timing decorators

5. **Refactor: extract observability module with clean interfaces**
   - Create metrics registry with pluggable backends
   - Implement logging configuration from environment
   - Add observability decorators for automatic instrumentation
   - Create health metrics aggregator

## Clean Code Principles

- **Separation of Concerns:** Logging, metrics, and tracing as independent components
- **Decorator Pattern:** Non-invasive instrumentation via decorators
- **Strategy Pattern:** Pluggable metrics backends (Prometheus, CloudWatch, StatsD)
- **Configuration over Code:** Environment-driven observability settings
- **Performance First:** Minimal overhead, async-safe, bounded memory usage

## File Structure
```
src/bio_mcp/http/
├── observability/
│   ├── __init__.py
│   ├── logging.py       # Structured logging configuration
│   ├── metrics.py       # Metrics collection and export
│   ├── decorators.py    # Instrumentation decorators
│   └── middleware.py    # Request/response logging middleware
├── config/
│   └── observability_config.py  # Settings from environment
```

## Implementation Details

### Structured Logging Format
```json
{
  "ts": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "msg": "Tool invocation completed",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "tool": "rag.search",
  "latency_ms": 145.3,
  "status": "success",
  "params_hash": "a3f5c921",
  "result_count": 10,
  "error_code": null,
  "tenant_id": "bio-research-001"
}
```

### Metrics Schema
```python
# Counters
bio_mcp_requests_total{tool="rag.search", status="success"}
bio_mcp_errors_total{tool="pubmed.sync", error_code="RATE_LIMIT"}

# Histograms
bio_mcp_latency_ms{tool="rag.search", quantile="0.95"}
bio_mcp_result_size_bytes{tool="pubmed.get", quantile="0.99"}

# Gauges
bio_mcp_inflight_requests{tool="pubmed.sync"}
bio_mcp_database_connections{state="active"}
bio_mcp_weaviate_vectors_total{}
```

### Environment Configuration
```bash
# Logging Configuration
BIO_MCP_LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR
BIO_MCP_JSON_LOGS=true              # Enable JSON structured logging
BIO_MCP_LOG_SAMPLING_RATE=1.0       # Sample rate for high-volume logs
BIO_MCP_REDACT_SENSITIVE=true       # Redact API keys and secrets

# Metrics Configuration
BIO_MCP_METRICS_ENABLED=true        # Enable metrics collection
BIO_MCP_METRICS_BACKEND=prometheus  # prometheus, cloudwatch, statsd
BIO_MCP_METRICS_PORT=9090          # Metrics endpoint port
BIO_MCP_METRICS_PATH=/metrics      # Metrics endpoint path
```

## Testing Strategy

### Unit Tests
```python
class TestStructuredLogging:
    """Test structured logging output and configuration."""
    
    def test_json_log_format(self, caplog):
        """Test that logs are valid JSON with required fields."""
        
    def test_trace_id_propagation(self):
        """Test trace_id flows through async operations."""
        
    def test_sensitive_data_redaction(self):
        """Test API keys are redacted from logs."""

class TestMetricsCollection:
    """Test metrics collection and aggregation."""
    
    def test_request_counter_increments(self):
        """Test request counters increment correctly."""
        
    def test_latency_histogram_buckets(self):
        """Test latency is recorded in correct buckets."""
        
    def test_concurrent_gauge_tracking(self):
        """Test inflight request gauge updates."""
```

### Integration Tests
```python
class TestObservabilityIntegration:
    """Test complete observability pipeline."""
    
    async def test_end_to_end_request_tracing(self):
        """Test request generates logs and metrics."""
        
    async def test_error_observability(self):
        """Test errors are logged and counted correctly."""
        
    async def test_metrics_export_format(self):
        """Test Prometheus endpoint returns valid metrics."""
```

## Performance Considerations

### Logging Performance
- **Async logging:** Use background thread for I/O
- **Sampling:** Configurable sampling for high-volume endpoints
- **Bounded queues:** Prevent memory exhaustion under load
- **Lazy evaluation:** Defer expensive computations

### Metrics Performance
- **Pre-aggregation:** Aggregate metrics in-process before export
- **Bounded cardinality:** Limit label combinations
- **Efficient storage:** Use fixed-size circular buffers
- **Batch export:** Bundle metrics for network efficiency

## Acceptance Criteria

- [ ] All logs output as valid JSON with consistent schema
- [ ] Trace IDs correlate logs across service boundaries
- [ ] Metrics available at `/metrics` in Prometheus format
- [ ] P95 latency tracked per tool with <1% overhead
- [ ] Error rates visible by tool and error code
- [ ] No sensitive data in logs (API keys, passwords)
- [ ] Configuration via environment variables
- [ ] CloudWatch EMF support for AWS deployment
- [ ] Performance overhead <2% for instrumentation
- [ ] Memory usage bounded under high load

## Success Metrics

1. **Observability Coverage:** 100% of tool invocations tracked
2. **Log Completeness:** All errors include trace_id and context
3. **Metrics Granularity:** Per-tool, per-error-code visibility
4. **Performance Impact:** <2% latency increase from instrumentation
5. **Operational Value:** Reduced MTTR through better visibility

This structured approach ensures production-grade observability while maintaining performance and clean architecture.
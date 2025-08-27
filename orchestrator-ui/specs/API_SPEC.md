# Bio-MCP Orchestrator UI - API Specification

## Overview

This document defines the complete API specification for the Bio-MCP Orchestrator UI backend services. The API provides endpoints for orchestrator execution, real-time streaming, session management, debug communication, and graph visualization.

## Base Configuration

### Base URL
```
Production: https://your-domain.com/orchestrator
Development: http://localhost:8001/orchestrator
```

### Authentication
Currently uses session-based authentication through the main Bio-MCP server. Future versions may implement API key authentication.

### Content Types
- Request: `application/json`
- Response: `application/json`
- Streaming: `text/event-stream` (SSE)
- WebSocket: `application/json` messages

## Core API Endpoints

### 1. Orchestrator Execution

#### Execute Orchestration
**POST** `/v1/orchestrator/query`

Initiate a new orchestration execution with streaming support.

**Request Body:**
```json
{
  "query": "string",
  "config": {
    "time_budget_ms": 5000,
    "fetch_policy": "cache_then_network",
    "max_parallel_calls": 5,
    "enable_partial_results": true,
    "extracted_entities": {
      "topic": "string",
      "indication": "string", 
      "company": "string",
      "trial_nct": "string"
    },
    "filters": {
      "date_from": "2023-01-01",
      "date_to": "2024-12-31",
      "phase": ["PHASE2", "PHASE3"],
      "status": ["RECRUITING", "ACTIVE_NOT_RECRUITING"],
      "journals": ["Nature", "Science"]
    }
  },
  "debug_mode": false,
  "session_name": "Optional Session Name"
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "status": "initiated",
  "query": "string",
  "estimated_duration_ms": 5000,
  "stream_url": "/v1/orchestrator/stream/{session_id}"
}
```

**Status Codes:**
- `200` - Successfully initiated
- `400` - Invalid request parameters
- `429` - Rate limit exceeded
- `500` - Server error

#### Stream Orchestration Results
**GET** `/v1/orchestrator/stream/{session_id}`

Server-Sent Events endpoint for real-time orchestration updates.

**Headers:**
```
Accept: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

**Event Types:**

**Status Update:**
```
event: status
data: {
  "session_id": "uuid",
  "status": "running|completed|failed",
  "current_node": "node_name",
  "progress_percentage": 75,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Node Execution Start:**
```
event: node_start
data: {
  "session_id": "uuid", 
  "node_name": "enhanced_pubmed",
  "timestamp": "2024-01-01T12:00:00Z",
  "estimated_duration_ms": 2000
}
```

**Node Execution Complete:**
```
event: node_complete
data: {
  "session_id": "uuid",
  "node_name": "enhanced_pubmed", 
  "execution_time_ms": 1250,
  "success": true,
  "result_preview": {
    "total_results": 15,
    "source": "pubmed"
  },
  "timestamp": "2024-01-01T12:00:01.250Z"
}
```

**Partial Results:**
```
event: partial_result
data: {
  "session_id": "uuid",
  "source": "pubmed|clinicaltrials|rag",
  "results": [
    {
      "id": "string",
      "title": "string", 
      "abstract": "string",
      "metadata": {...}
    }
  ],
  "metadata": {
    "total_expected": 50,
    "current_count": 15,
    "has_more": true
  },
  "timestamp": "2024-01-01T12:00:01Z"
}
```

**Final Result:**
```
event: result
data: {
  "session_id": "uuid",
  "query": "string",
  "answer": "synthesized answer",
  "checkpoint_id": "string",
  "node_path": ["parse_frame", "enhanced_pubmed", "synthesis"],
  "tool_calls_made": ["pubmed.search", "rag.search"],
  "cache_hits": {"pubmed_search": true, "rag_search": false},
  "latencies": {"enhanced_pubmed": 1250, "synthesis": 500},
  "errors": [],
  "pubmed_results": {...},
  "trials_results": {...},
  "rag_results": {...},
  "quality_metrics": {
    "completeness": 0.85,
    "recency": 0.92,
    "authority": 0.78,
    "relevance": 0.91,
    "overall_score": 0.87
  },
  "citations": [
    {
      "id": "1",
      "type": "pubmed",
      "pmid": "12345678",
      "title": "string",
      "authors": ["Author A", "Author B"],
      "journal": "Nature",
      "year": 2023,
      "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    }
  ],
  "timestamp": "2024-01-01T12:00:05Z"
}
```

**Error Event:**
```
event: error
data: {
  "session_id": "uuid",
  "error_code": "TIMEOUT|NETWORK_ERROR|VALIDATION_ERROR",
  "error_message": "string",
  "node_name": "string",
  "recoverable": true,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Completion Event:**
```
event: done
data: {
  "session_id": "uuid",
  "final_status": "completed|failed",
  "total_duration_ms": 4750,
  "timestamp": "2024-01-01T12:00:05Z"
}
```

### 2. Session Management

#### List Sessions
**GET** `/v1/orchestrator/sessions`

Retrieve paginated list of orchestration sessions.

**Query Parameters:**
- `limit` (integer, default: 50, max: 100) - Number of sessions per page
- `offset` (integer, default: 0) - Pagination offset
- `status` (string, optional) - Filter by status: `completed|running|failed|queued`
- `search` (string, optional) - Search in query or session name

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "uuid",
      "query": "string",
      "session_name": "string",
      "status": "completed",
      "debug_mode": false,
      "created_at": "2024-01-01T12:00:00Z",
      "started_at": "2024-01-01T12:00:01Z",
      "completed_at": "2024-01-01T12:00:05Z",
      "total_duration_ms": 4000,
      "tool_calls_count": 3,
      "error": null
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

#### Get Session Details
**GET** `/v1/orchestrator/session/{session_id}`

Retrieve complete details for a specific session.

**Response:**
```json
{
  "session_id": "uuid",
  "query": "string",
  "session_name": "string",
  "config": {...},
  "status": "completed",
  "debug_mode": false,
  "created_at": "2024-01-01T12:00:00Z",
  "started_at": "2024-01-01T12:00:01Z", 
  "completed_at": "2024-01-01T12:00:05Z",
  "error": null,
  "result": {
    "answer": "string",
    "checkpoint_id": "string",
    "node_path": ["parse_frame", "enhanced_pubmed"],
    "tool_calls_made": ["pubmed.search"],
    "cache_hits": {"pubmed_search": true},
    "latencies": {"enhanced_pubmed": 1250},
    "errors": [],
    "pubmed_results": {...},
    "trials_results": {...},
    "rag_results": {...},
    "quality_metrics": {...},
    "citations": [...]
  }
}
```

**Status Codes:**
- `200` - Success
- `404` - Session not found

#### Delete Session
**DELETE** `/v1/orchestrator/session/{session_id}`

Delete a session and all its associated data.

**Response:**
```json
{
  "message": "Session {session_id} deleted successfully"
}
```

**Status Codes:**
- `200` - Successfully deleted
- `404` - Session not found
- `409` - Cannot delete running session

### 3. Graph Visualization

#### Get Graph Structure
**GET** `/v1/orchestrator/graph/visualization`

Get the orchestrator graph structure for visualization.

**Response:**
```json
{
  "nodes": [
    {
      "id": "parse_frame",
      "type": "orchestrator_node",
      "label": "Parse Frame",
      "position": {"x": 0, "y": 100},
      "data": {
        "node_type": "processing",
        "description": "Parse query and extract entities",
        "expected_duration_ms": 500,
        "dependencies": []
      }
    },
    {
      "id": "enhanced_pubmed",
      "type": "orchestrator_node", 
      "label": "Enhanced PubMed",
      "position": {"x": 200, "y": 100},
      "data": {
        "node_type": "data_source",
        "description": "Search PubMed with entity extraction",
        "expected_duration_ms": 2000,
        "dependencies": ["parse_frame"]
      }
    }
  ],
  "edges": [
    {
      "id": "parse_frame->enhanced_pubmed",
      "source": "parse_frame",
      "target": "enhanced_pubmed", 
      "type": "orchestrator_edge",
      "data": {
        "condition": null,
        "weight": 1.0
      }
    }
  ],
  "layout": {
    "direction": "horizontal",
    "node_spacing": 200,
    "level_spacing": 150
  },
  "metadata": {
    "total_nodes": 6,
    "total_edges": 7,
    "graph_type": "langgraph_orchestrator",
    "estimated_total_duration_ms": 5000
  }
}
```

### 4. Debug Communication

Debug functionality uses WebSocket for bi-directional real-time communication.

#### WebSocket Connection
**WebSocket** `/ws/debug/{session_id}`

Establish WebSocket connection for debug communication.

**Connection Headers:**
```
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Version: 13
```

**Message Format:**
All WebSocket messages use JSON format:
```json
{
  "type": "string",
  "session_id": "uuid",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {...}
}
```

#### Debug Commands (Client → Server)

**Set Breakpoint:**
```json
{
  "type": "set_breakpoint",
  "session_id": "uuid",
  "node_name": "enhanced_pubmed",
  "enabled": true,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Step Execution:**
```json
{
  "type": "step",
  "session_id": "uuid", 
  "node_name": "enhanced_pubmed",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Inspect Node State:**
```json
{
  "type": "inspect_state",
  "session_id": "uuid",
  "node_name": "enhanced_pubmed", 
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Resume Execution:**
```json
{
  "type": "resume",
  "session_id": "uuid",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

#### Debug Events (Server → Client)

**Breakpoint Hit:**
```json
{
  "type": "breakpoint_hit",
  "session_id": "uuid",
  "node_name": "enhanced_pubmed",
  "state": {
    "input_data": {...},
    "current_state": {...},
    "execution_context": {...}
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Step Completed:**
```json
{
  "type": "step_completed", 
  "session_id": "uuid",
  "node_name": "enhanced_pubmed",
  "state": {...},
  "execution_time_ms": 1250,
  "timestamp": "2024-01-01T12:00:01.250Z"
}
```

**Breakpoint Acknowledged:**
```json
{
  "type": "breakpoint_set",
  "session_id": "uuid",
  "node_name": "enhanced_pubmed",
  "enabled": true,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**State Inspection Response:**
```json
{
  "type": "state_inspection",
  "session_id": "uuid",
  "node_name": "enhanced_pubmed",
  "state": {
    "input": {
      "entities": {...},
      "query": "string",
      "filters": {...}
    },
    "output": {
      "results": [...],
      "metadata": {...}
    },
    "internal_state": {
      "cache_key": "string",
      "api_calls_made": 3,
      "processing_time_ms": 1250
    },
    "performance": {
      "memory_usage_mb": 45,
      "cpu_time_ms": 890
    }
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Execution Resumed:**
```json
{
  "type": "execution_resumed",
  "session_id": "uuid",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### 5. Health and Status

#### Health Check
**GET** `/health`

Basic health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "orchestrator-api",
  "timestamp": "2024-01-01T12:00:00Z",
  "active_sessions": 5,
  "server_info": {
    "version": "1.0.0",
    "uptime_seconds": 86400
  }
}
```

#### Service Status
**GET** `/v1/orchestrator/status`

Detailed service status including dependencies.

**Response:**
```json
{
  "status": "operational",
  "services": {
    "orchestrator": {
      "status": "healthy",
      "active_sessions": 5,
      "total_sessions_today": 150
    },
    "database": {
      "status": "healthy",
      "connection_pool": "8/20"
    },
    "mcp_tools": {
      "status": "healthy", 
      "available_tools": 15
    },
    "streaming": {
      "status": "healthy",
      "active_connections": 12
    }
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Error Handling

### Error Response Format
All API errors return a consistent format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": "Additional technical details",
    "timestamp": "2024-01-01T12:00:00Z",
    "request_id": "uuid"
  }
}
```

### Error Codes

#### Client Errors (4xx)
- `INVALID_REQUEST` (400) - Malformed request body or parameters
- `VALIDATION_ERROR` (400) - Request validation failed
- `UNAUTHORIZED` (401) - Authentication required
- `FORBIDDEN` (403) - Insufficient permissions
- `SESSION_NOT_FOUND` (404) - Requested session does not exist
- `RATE_LIMITED` (429) - Too many requests

#### Server Errors (5xx)  
- `INTERNAL_ERROR` (500) - Unexpected server error
- `ORCHESTRATOR_UNAVAILABLE` (502) - Orchestrator service unavailable
- `SERVICE_TIMEOUT` (504) - Request timeout
- `RESOURCE_EXHAUSTED` (503) - Server overloaded

### Retry Strategy
- **Exponential Backoff**: Start with 1s, double each retry, max 30s
- **Max Retries**: 3 for most endpoints, 1 for mutations
- **Retry Conditions**: Network errors, 5xx errors, timeouts
- **No Retry**: 4xx errors (except 429), successful responses

## Rate Limiting

### Limits
- **Query Execution**: 10 requests per minute per IP
- **Session Management**: 60 requests per minute per IP  
- **Streaming Connections**: 5 concurrent connections per IP
- **WebSocket Debug**: 2 concurrent connections per IP

### Headers
Rate limit information in response headers:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
X-RateLimit-Retry-After: 60
```

## Authentication & Authorization

### Current Implementation
- Session-based authentication through main Bio-MCP server
- IP-based rate limiting
- No role-based access control (all authenticated users have full access)

### Future Enhancements
- API key authentication
- Role-based permissions (admin, user, readonly)
- OAuth2/OIDC integration
- Session management improvements

## Performance Considerations

### Response Times
- **Session List**: < 200ms
- **Session Details**: < 100ms
- **Graph Visualization**: < 50ms
- **Orchestration Initiation**: < 500ms
- **Streaming Latency**: < 50ms

### Caching
- **Graph Structure**: Cached for 10 minutes
- **Session List**: Cached for 30 seconds
- **Session Details**: No caching (real-time data)

### Connection Management
- **SSE Connections**: Auto-reconnect on failure
- **WebSocket**: Heartbeat every 30 seconds
- **Connection Pooling**: Database connections reused
- **Memory Management**: Cleanup completed sessions after 24h

## Security

### Data Protection
- All API communications over HTTPS in production
- Session data encrypted at rest
- No sensitive data in URL parameters
- CORS policy enforced

### Input Validation
- JSON schema validation on all endpoints
- SQL injection prevention
- XSS protection in text fields
- File upload restrictions (none currently)

### Monitoring
- Request logging with correlation IDs
- Performance metrics collection
- Error tracking and alerting
- Security event logging

## Versioning

### API Version Strategy
- URL-based versioning: `/v1/orchestrator/`
- Backward compatibility maintained for at least 2 major versions
- Deprecation notices 6 months before removal
- Version-specific documentation maintained

### Current Version: v1.0.0
- Semantic versioning for API changes
- Breaking changes require major version bump
- Feature additions increment minor version
- Bug fixes increment patch version

## SDK and Client Libraries

### JavaScript/TypeScript SDK
```typescript
import { OrchestratorClient } from '@bio-mcp/orchestrator-sdk'

const client = new OrchestratorClient({
  baseURL: 'https://api.example.com/orchestrator',
  apiKey: 'your-api-key' // Future enhancement
})

// Execute orchestration
const session = await client.executeQuery({
  query: 'GLP-1 diabetes trials',
  config: { debug_mode: true }
})

// Stream results
for await (const event of client.streamResults(session.session_id)) {
  console.log('Event:', event.type, event.data)
}
```

### Python SDK (Future)
```python
from bio_mcp.orchestrator import OrchestratorClient

client = OrchestratorClient(base_url="https://api.example.com/orchestrator")

session = await client.execute_query(
    query="GLP-1 diabetes trials",
    config={"debug_mode": True}
)

async for event in client.stream_results(session.session_id):
    print(f"Event: {event.type} - {event.data}")
```

## Testing

### API Testing
- **Unit Tests**: Mock HTTP responses
- **Integration Tests**: Real API endpoints 
- **E2E Tests**: Complete user workflows
- **Load Tests**: Performance under stress
- **Contract Tests**: API specification compliance

### Test Data
- **Mock Sessions**: Predefined test sessions
- **Sample Queries**: Biomedical test cases
- **Performance Benchmarks**: Response time expectations
- **Error Scenarios**: Comprehensive error coverage

This specification provides the complete API contract for the Bio-MCP Orchestrator UI backend services, ensuring reliable integration and comprehensive functionality for the frontend application.
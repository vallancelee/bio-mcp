# BioInvest AI Copilot POC - API Contract

This document defines the API contract between the frontend and backend services.

## API Base URL
- **Development**: `http://localhost:8002`
- **Base Path**: `/api`

## Authentication
Currently no authentication required (POC only).

## Common Response Headers
```
Content-Type: application/json
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: *
```

## Error Handling
All endpoints return errors in the following format:
```json
{
  "detail": "Error message",
  "status_code": 400
}
```

## Endpoints

### 1. Health Check
**GET** `/health`

Returns the health status of all backend services.

**Response:**
```json
{
  "status": "healthy" | "degraded",
  "components": {
    "bio_mcp": "healthy" | "unhealthy",
    "synthesis_service": "healthy" | "unhealthy"
  },
  "active_queries": number,
  "timestamp": string
}
```

### 2. Submit Research Query
**POST** `/api/research/query`

Submits a new research query for processing.

**Request Body:**
```json
{
  "query": string,
  "sources": string[],
  "options": {
    "max_results_per_source": number,
    "include_synthesis": boolean,
    "priority": "speed" | "comprehensive" | "balanced"
  }
}
```

**Response:**
```json
{
  "query_id": string,
  "status": "initiated" | "processing" | "completed" | "failed",
  "estimated_completion_time": number,
  "progress": {
    "pubmed": "pending" | "processing" | "completed" | "failed",
    "clinical_trials": "pending" | "processing" | "completed" | "failed", 
    "rag": "pending" | "processing" | "completed" | "failed"
  },
  "partial_results_available": boolean,
  "stream_url": string,
  "created_at": string
}
```

### 3. Stream Query Results (SSE)
**GET** `/api/research/stream/{query_id}`

Server-Sent Events endpoint for real-time query progress and results.

**Event Types:**
- `connected`: Initial connection established
- `progress`: Query progress update
- `partial_result`: Partial results from a source
- `query_completed`: Query fully completed
- `query_failed`: Query failed

**Event Data Schema:**
```json
{
  "query_id": string,
  "timestamp": string,
  "status"?: string,
  "progress"?: object,
  "source"?: string,
  "results"?: array,
  "total_found"?: number,
  "synthesis"?: object,
  "total_results"?: number,
  "error"?: string
}
```

### 4. Get Query Status
**GET** `/api/research/query/{query_id}`

Retrieves the current status and results for a specific query.

**Response:**
```json
{
  "query_id": string,
  "status": string,
  "query": string,
  "progress": {
    "pubmed": string,
    "clinical_trials": string,
    "rag": string
  },
  "results": {
    "pubmed"?: {
      "total_found": number,
      "results": PubMedResult[]
    },
    "clinical_trials"?: {
      "total_found": number,
      "results": ClinicalTrialResult[]
    },
    "rag"?: {
      "total_found": number,
      "results": RAGResult[]
    }
  },
  "synthesis"?: SynthesisResult,
  "created_at": string,
  "completed_at"?: string
}
```

### 5. Get Active Queries
**GET** `/api/research/active-queries`

Retrieves list of currently active queries.

**Response:**
```json
{
  "active_queries": [
    {
      "query_id": string,
      "status": string,
      "query": string,
      "created_at": string,
      "completed_at"?: string,
      "progress": {
        "pubmed": string,
        "clinical_trials": string,
        "rag": string
      },
      "sources": string[],
      "total_results": number
    }
  ],
  "total_count": number,
  "timestamp": string
}
```

### 6. Get Synthesis
**GET** `/api/research/synthesis/{query_id}`

Retrieves the AI synthesis for a completed query.

**Response:**
```json
{
  "summary": string,
  "key_insights": KeyInsight[],
  "competitive_analysis": CompetitiveAnalysis | null,
  "risk_assessment": RiskFactor[],
  "recommendations": string[],
  "quality_metrics": QualityMetrics,
  "citations": Citation[],
  "sources_summary": Record<string, number>,
  "generation_metadata": {
    "model_used": string,
    "generation_time_ms": number,
    "total_sources_analyzed": number,
    "analysis_timestamp": string,
    "langgraph_enabled"?: boolean,
    "execution_path"?: string[],
    "tool_calls"?: number
  }
}
```

### 7. LangGraph Visualization
**GET** `/api/langgraph/visualization`

Returns visualization data for the LangGraph workflow.

**Response:**
```json
{
  "nodes": [
    {
      "id": string,
      "label": string,
      "type": "processor" | "decision" | "tool"
    }
  ],
  "edges": [
    {
      "from": string,
      "to": string
    }
  ],
  "config": {
    "max_iterations": number,
    "checkpoint_enabled": boolean,
    "tracing_enabled": boolean
  }
}
```

### 8. LangGraph Status
**GET** `/api/langgraph/status`

Returns the current status of the LangGraph orchestrator.

**Response:**
```json
{
  "langgraph_enabled": boolean,
  "status": "operational" | "degraded" | "failed",
  "graph_initialized": boolean,
  "timestamp": string
}
```

## Data Models

### PubMedResult
```json
{
  "pmid": string,
  "title": string,
  "abstract": string,
  "authors": string[],
  "journal": string,
  "publication_date": string,
  "doi": string,
  "mesh_terms": string[],
  "keywords": string[],
  "citation_count": number,
  "impact_factor": number,
  "relevance_score": number
}
```

### ClinicalTrialResult
```json
{
  "nct_id": string,
  "title": string,
  "brief_summary": string,
  "conditions": string[],
  "interventions": string[],
  "phase": string,
  "status": string,
  "enrollment": {
    "target": number,
    "actual": number,
    "type": string
  },
  "dates": {
    "start_date": string,
    "completion_date"?: string,
    "last_update": string
  },
  "sponsors": {
    "lead_sponsor": string,
    "collaborators": string[]
  },
  "locations": [
    {
      "facility": string,
      "city": string,
      "state": string,
      "country": string
    }
  ],
  "primary_endpoint": string,
  "investment_score": number,
  "relevance_score": number
}
```

### RAGResult
```json
{
  "doc_id": string,
  "title": string,
  "content": string,
  "source": string,
  "metadata": {
    "document_type": string,
    "created_date": string,
    "author": string
  },
  "relevance_score": number,
  "chunks": [
    {
      "chunk_id": string,
      "text": string,
      "position": number,
      "relevance_score": number
    }
  ]
}
```

### KeyInsight
```json
{
  "insight": string,
  "supporting_evidence": string[],
  "confidence": number,
  "category": string
}
```

### CompetitiveAnalysis
```json
{
  "direct_competitors": [
    {
      "company": string,
      "drug": string,
      "brand": string,
      "competitive_advantage": string,
      "market_position": string,
      "threat_level": string
    }
  ],
  "competitive_threats": string[],
  "market_position": string,
  "competitive_advantages": string[],
  "risks": RiskFactor[]
}
```

### RiskFactor
```json
{
  "factor": string,
  "impact": number,
  "explanation": string,
  "severity": "low" | "medium" | "high" | "critical"
}
```

### QualityMetrics
```json
{
  "completeness": number,
  "recency": number,
  "authority": number,
  "diversity": number,
  "relevance": number,
  "overall_score": number
}
```

### Citation
```json
{
  "id": string,
  "type": string,
  "title": string,
  "authors": string[],
  "source": string,
  "year": number | null,
  "url": string | null,
  "snippet": string,
  "relevance_score": number
}
```

## Status Codes

- **200 OK**: Successful request
- **400 Bad Request**: Invalid request data
- **404 Not Found**: Resource not found
- **422 Unprocessable Entity**: Validation error
- **500 Internal Server Error**: Server error
- **503 Service Unavailable**: Service temporarily unavailable

## Rate Limiting

Currently no rate limiting implemented (POC only).

## Versioning

API version is currently `v1` (implicit). Future versions will use URL versioning:
- `/api/v1/research/query`
- `/api/v2/research/query`

## Development Notes

- All timestamps are in ISO 8601 format (UTC)
- Query IDs are UUID v4 format
- File sizes and timeouts are in the respective units specified
- Boolean fields use `true`/`false` (JSON standard)
- All APIs are currently synchronous except for SSE streaming

## Example Usage

### Submit Query and Stream Results
```javascript
// Submit query
const response = await fetch('/api/research/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: "GLP-1 market analysis",
    sources: ["pubmed", "clinical_trials"],
    options: {
      max_results_per_source: 50,
      include_synthesis: true,
      priority: "balanced"
    }
  })
});

const { query_id, stream_url } = await response.json();

// Stream results
const eventSource = new EventSource(stream_url);
eventSource.addEventListener('query_completed', (event) => {
  const data = JSON.parse(event.data);
  console.log('Query completed:', data);
  eventSource.close();
});
```
# BioInvest AI Copilot - API Design Specification

## Overview

The BioInvest AI Copilot API design follows REST principles with GraphQL extensions for complex queries and WebSocket connections for real-time updates. The API is designed for scalability, security, and developer experience, providing comprehensive endpoints for research, analytics, portfolio management, and collaboration features.

## API Design Principles

### Core Principles
- **RESTful Design**: Resource-oriented URLs with standard HTTP methods
- **GraphQL Flexibility**: Single endpoint for complex, nested data queries
- **Real-time Capabilities**: WebSocket and Server-Sent Events for live updates
- **API-First Development**: API designed before implementation
- **Backward Compatibility**: Versioned APIs with graceful deprecation
- **Developer Experience**: Clear documentation, SDKs, and testing tools

### Quality Standards
- **Response Time**: <200ms P95 for simple queries, <2s for complex operations
- **Availability**: 99.9% uptime with graceful degradation
- **Rate Limiting**: Fair usage policies with clear limits and quotas
- **Security**: OAuth 2.0, API keys, and request signing
- **Documentation**: OpenAPI 3.0 specification with interactive examples

## API Architecture

### Service-Oriented API Design

```mermaid
graph TB
    subgraph "Client Applications"
        WEB[Web App]
        MOBILE[Mobile App]
        SDK[SDK Clients]
        THIRD_PARTY[Third Party Apps]
    end
    
    subgraph "API Gateway Layer"
        GATEWAY[API Gateway]
        AUTH[Authentication]
        RATE_LIMIT[Rate Limiting]
        CACHE[Response Cache]
    end
    
    subgraph "API Services"
        RESEARCH_API[Research API]
        ANALYTICS_API[Analytics API]
        PORTFOLIO_API[Portfolio API]
        COLLAB_API[Collaboration API]
        NOTIFICATION_API[Notification API]
    end
    
    subgraph "Real-time Services"
        WEBSOCKET[WebSocket Server]
        SSE[Server-Sent Events]
        GRAPHQL[GraphQL Endpoint]
    end
    
    subgraph "Backend Services"
        RESEARCH_SVC[Research Service]
        ML_SVC[ML Service]
        DATA_SVC[Data Service]
        USER_SVC[User Service]
    end
    
    WEB --> GATEWAY
    MOBILE --> GATEWAY
    SDK --> GATEWAY
    THIRD_PARTY --> GATEWAY
    
    GATEWAY --> AUTH
    AUTH --> RATE_LIMIT
    RATE_LIMIT --> CACHE
    
    CACHE --> RESEARCH_API
    CACHE --> ANALYTICS_API
    CACHE --> PORTFOLIO_API
    CACHE --> COLLAB_API
    
    RESEARCH_API --> RESEARCH_SVC
    ANALYTICS_API --> ML_SVC
    PORTFOLIO_API --> DATA_SVC
    COLLAB_API --> USER_SVC
    
    GATEWAY --> WEBSOCKET
    GATEWAY --> SSE
    GATEWAY --> GRAPHQL
```

## REST API Specification

### Base Configuration

**Base URLs:**
- Production: `https://api.bioinvest.ai/v1`
- Staging: `https://api-staging.bioinvest.ai/v1`
- Development: `http://localhost:8000/v1`

**Authentication:**
```http
Authorization: Bearer <jwt_token>
X-API-Key: <api_key>
```

**Common Headers:**
```http
Content-Type: application/json
Accept: application/json
X-Request-ID: <uuid>
X-Client-Version: 1.0.0
```

### Research API

#### Submit Research Query
```http
POST /research/queries
Content-Type: application/json

{
  "query": "What are the competitive risks for Novo Nordisk's GLP-1 pipeline?",
  "entities": {
    "companies": ["Novo Nordisk"],
    "therapeutic_areas": ["Diabetes", "Obesity"],
    "drug_classes": ["GLP-1"]
  },
  "search_parameters": {
    "date_range": {
      "start": "2023-01-01",
      "end": "2024-12-31"
    },
    "sources": ["pubmed", "clinical_trials", "patents", "regulatory"],
    "max_results_per_source": 100,
    "include_preprints": false
  },
  "analysis_options": {
    "include_competitive_analysis": true,
    "include_risk_assessment": true,
    "generate_summary": true,
    "extract_key_insights": true
  }
}
```

**Response:**
```json
{
  "query_id": "q_abc123def456",
  "status": "processing",
  "estimated_completion_time": "2024-01-15T10:05:00Z",
  "progress": {
    "pubmed": "completed",
    "clinical_trials": "in_progress",
    "patents": "queued",
    "regulatory": "queued"
  },
  "partial_results_available": true,
  "stream_url": "/research/queries/q_abc123def456/stream",
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### Get Query Results
```http
GET /research/queries/q_abc123def456
```

**Response:**
```json
{
  "query_id": "q_abc123def456",
  "status": "completed",
  "query": "What are the competitive risks for Novo Nordisk's GLP-1 pipeline?",
  "results": {
    "summary": {
      "key_insights": [
        "Eli Lilly's tirzepatide (Mounjaro) shows superior efficacy in Phase 3 trials",
        "Multiple biosimilar threats to semaglutide patents expiring 2031",
        "Oral GLP-1 competitors emerging from Pfizer and Roche partnerships"
      ],
      "risk_assessment": {
        "competitive_threat_level": "high",
        "market_share_risk": 0.35,
        "patent_cliff_impact": 0.28,
        "regulatory_risk": 0.12
      }
    },
    "sources": {
      "pubmed": {
        "total_results": 234,
        "relevant_results": 89,
        "key_publications": [
          {
            "pmid": "37845123",
            "title": "Comparative efficacy of tirzepatide vs semaglutide in T2DM",
            "authors": ["Smith J", "Johnson A"],
            "journal": "New England Journal of Medicine",
            "publication_date": "2023-11-15",
            "relevance_score": 0.94,
            "key_findings": "Tirzepatide demonstrated 2.1kg additional weight loss vs semaglutide"
          }
        ]
      },
      "clinical_trials": {
        "total_trials": 67,
        "relevant_trials": 23,
        "key_trials": [
          {
            "nct_id": "NCT04537923",
            "title": "SURMOUNT-1: Tirzepatide for obesity management",
            "phase": "Phase 3",
            "status": "Completed",
            "primary_endpoint_met": true,
            "enrollment": 2539,
            "key_findings": "22.5% weight reduction at 72 weeks"
          }
        ]
      }
    },
    "competitive_analysis": {
      "direct_competitors": [
        {
          "company": "Eli Lilly",
          "drug": "tirzepatide",
          "brand_name": "Mounjaro",
          "competitive_advantage": "Dual GIP/GLP-1 mechanism",
          "market_position": "gaining_share",
          "threat_level": "high"
        }
      ],
      "pipeline_threats": [
        {
          "company": "Pfizer",
          "drug": "PF-06882961",
          "phase": "Phase 2",
          "mechanism": "Oral GLP-1",
          "expected_approval": "2027",
          "threat_level": "medium"
        }
      ]
    }
  },
  "metadata": {
    "processing_time_seconds": 45.2,
    "sources_queried": 4,
    "total_documents_reviewed": 1247,
    "ai_confidence_score": 0.87
  },
  "created_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:00:45Z"
}
```

#### Stream Query Progress
```http
GET /research/queries/q_abc123def456/stream
Accept: text/event-stream
```

**Server-Sent Events:**
```
event: progress
data: {"source": "pubmed", "status": "completed", "results_found": 89}

event: partial_result
data: {"source": "clinical_trials", "results": [...], "metadata": {...}}

event: analysis_update
data: {"competitive_analysis": {"competitors_identified": 5}}

event: completed
data: {"query_id": "q_abc123def456", "final_results": {...}}
```

### Analytics API

#### Predict Clinical Trial Success
```http
POST /analytics/predictions/clinical-trial-success
Content-Type: application/json

{
  "trial_data": {
    "nct_id": "NCT05123456",
    "drug_name": "BIO-12345",
    "indication": "Alzheimer's Disease",
    "phase": "Phase 3",
    "sponsor": "Biogen",
    "enrollment": {
      "target": 1800,
      "actual": 1650
    },
    "study_design": {
      "randomized": true,
      "blinded": true,
      "placebo_controlled": true,
      "adaptive": false
    },
    "primary_endpoint": "Change in CDR-SB from baseline to week 78",
    "mechanism_of_action": "Amyloid beta targeting",
    "prior_trials": [
      {
        "drug": "aducanumab",
        "outcome": "approved_controversial",
        "similarity_score": 0.78
      }
    ]
  },
  "analysis_options": {
    "include_confidence_intervals": true,
    "include_risk_factors": true,
    "include_comparisons": true,
    "generate_recommendations": true
  }
}
```

**Response:**
```json
{
  "prediction_id": "pred_789xyz",
  "success_probability": 0.34,
  "confidence_interval": {
    "lower": 0.28,
    "upper": 0.41,
    "confidence_level": 0.95
  },
  "risk_assessment": {
    "overall_risk": "high",
    "key_risk_factors": [
      {
        "factor": "indication_difficulty",
        "impact": -0.15,
        "explanation": "Alzheimer's disease has historically low success rates in Phase 3"
      },
      {
        "factor": "mechanism_precedent",
        "impact": -0.08,
        "explanation": "Previous amyloid-targeting drugs have shown mixed results"
      },
      {
        "factor": "enrollment_shortfall",
        "impact": -0.03,
        "explanation": "8.3% enrollment shortfall may impact statistical power"
      }
    ],
    "positive_factors": [
      {
        "factor": "sponsor_experience",
        "impact": +0.05,
        "explanation": "Biogen has deep experience in neurodegeneration"
      }
    ]
  },
  "comparable_trials": [
    {
      "nct_id": "NCT03887455",
      "drug": "aducanumab",
      "similarity_score": 0.78,
      "outcome": "approved",
      "lessons_learned": "FDA approval despite mixed efficacy data"
    }
  ],
  "recommendations": [
    "Monitor enrollment completion and potential protocol amendments",
    "Prepare comprehensive biomarker analysis to support primary endpoint",
    "Consider accelerated approval pathway given unmet medical need"
  ],
  "model_metadata": {
    "model_version": "clinical_trial_v2.1",
    "training_data_size": 12847,
    "last_updated": "2024-01-01T00:00:00Z",
    "feature_importance": {
      "indication": 0.23,
      "phase": 0.18,
      "sponsor": 0.15,
      "mechanism": 0.12,
      "study_design": 0.10
    }
  },
  "created_at": "2024-01-15T10:15:00Z"
}
```

#### FDA Approval Prediction
```http
POST /analytics/predictions/fda-approval
Content-Type: application/json

{
  "drug_data": {
    "drug_name": "Drug X",
    "generic_name": "compound-123",
    "indication": "Multiple Sclerosis",
    "regulatory_pathway": "BLA",
    "designation": ["Fast Track", "Orphan Drug"],
    "clinical_data": {
      "phase3_trials": 2,
      "primary_endpoint_met": true,
      "statistical_significance": 0.001,
      "effect_size": 0.65,
      "safety_profile": "acceptable"
    },
    "competitive_landscape": {
      "approved_competitors": 8,
      "differentiation": "novel_mechanism"
    },
    "sponsor": "Novartis"
  }
}
```

### Portfolio API

#### Get Portfolio Analysis
```http
GET /portfolio/analysis/{portfolio_id}?analysis_type=risk&include_scenarios=true
```

**Response:**
```json
{
  "portfolio_id": "port_456def",
  "analysis_timestamp": "2024-01-15T10:30:00Z",
  "risk_analysis": {
    "overall_risk_score": 0.72,
    "risk_breakdown": {
      "market_risk": 0.35,
      "regulatory_risk": 0.28,
      "clinical_risk": 0.23,
      "competitive_risk": 0.14
    },
    "concentration_risk": {
      "top_5_concentration": 0.68,
      "therapeutic_area_concentration": {
        "Oncology": 0.45,
        "CNS": 0.23,
        "Immunology": 0.32
      },
      "phase_concentration": {
        "Phase 3": 0.55,
        "Phase 2": 0.32,
        "Commercial": 0.13
      }
    },
    "correlation_analysis": {
      "highest_correlated_pairs": [
        {
          "asset1": "BIIB",
          "asset2": "RHHBY",
          "correlation": 0.74,
          "reason": "Both exposed to Alzheimer's regulatory risk"
        }
      ]
    }
  },
  "scenario_analysis": {
    "bear_case": {
      "probability": 0.20,
      "portfolio_return": -0.35,
      "key_assumptions": ["Multiple Phase 3 failures", "Regulatory setbacks"]
    },
    "base_case": {
      "probability": 0.60,
      "portfolio_return": 0.12,
      "key_assumptions": ["Normal success rates", "Stable market conditions"]
    },
    "bull_case": {
      "probability": 0.20,
      "portfolio_return": 0.48,
      "key_assumptions": ["Breakthrough approvals", "Market expansion"]
    }
  },
  "recommendations": [
    {
      "type": "diversification",
      "priority": "high",
      "description": "Reduce oncology concentration below 40%",
      "suggested_actions": ["Add CNS or rare disease exposure"]
    }
  ]
}
```

#### Binary Events Calendar
```http
GET /portfolio/catalysts?portfolio_id=port_456def&start_date=2024-01-01&end_date=2024-12-31
```

**Response:**
```json
{
  "events": [
    {
      "event_id": "evt_123abc",
      "event_type": "fda_decision",
      "date": "2024-03-15",
      "date_certainty": "confirmed",
      "asset": {
        "symbol": "BIIB",
        "drug": "aducanumab",
        "indication": "Alzheimer's Disease"
      },
      "event_description": "PDUFA date for supplemental BLA",
      "potential_impact": {
        "probability_positive": 0.65,
        "stock_impact_positive": 0.25,
        "stock_impact_negative": -0.15,
        "portfolio_impact": 0.08
      },
      "related_events": ["evt_456def"],
      "preparation_items": [
        "Monitor FDA advisory committee meeting",
        "Review label expansion commercial potential"
      ]
    }
  ],
  "summary": {
    "total_events": 23,
    "high_impact_events": 8,
    "average_days_to_next_event": 45,
    "portfolio_event_density": 0.15
  }
}
```

### Collaboration API

#### Create Research Workspace
```http
POST /collaboration/workspaces
Content-Type: application/json

{
  "name": "GLP-1 Competitive Analysis",
  "description": "Comprehensive analysis of GLP-1 competitive landscape",
  "type": "research_project",
  "privacy": "private",
  "members": [
    {
      "user_id": "user_123",
      "role": "owner",
      "permissions": ["read", "write", "admin"]
    },
    {
      "user_id": "user_456", 
      "role": "analyst",
      "permissions": ["read", "write"]
    }
  ],
  "settings": {
    "allow_external_sharing": false,
    "require_approval_for_insights": true,
    "enable_real_time_collaboration": true
  }
}
```

**Response:**
```json
{
  "workspace_id": "ws_789ghi",
  "name": "GLP-1 Competitive Analysis",
  "created_at": "2024-01-15T11:00:00Z",
  "owner": "user_123",
  "member_count": 2,
  "access_url": "/workspaces/ws_789ghi",
  "collaboration_features": {
    "real_time_editing": true,
    "comment_system": true,
    "version_history": true,
    "activity_feed": true
  }
}
```

#### Add Research Insight
```http
POST /collaboration/workspaces/ws_789ghi/insights
Content-Type: application/json

{
  "title": "Tirzepatide Superior Weight Loss Efficacy",
  "content": "SURMOUNT-1 trial data shows tirzepatide achieving 22.5% weight reduction vs 15% for semaglutide, representing significant competitive threat to Novo Nordisk",
  "type": "key_insight",
  "sources": [
    {
      "type": "clinical_trial",
      "identifier": "NCT04537923",
      "citation": "Jastreboff AM, et al. SURMOUNT-1 Trial. NEJM 2022"
    }
  ],
  "tags": ["competitive_threat", "weight_loss", "efficacy"],
  "confidence_level": "high",
  "impact_assessment": {
    "market_impact": "high",
    "investment_relevance": "high",
    "time_horizon": "immediate"
  }
}
```

## GraphQL API

### Schema Definition

```graphql
type Query {
  # Research queries
  research(id: ID!): ResearchQuery
  researchResults(
    filters: ResearchFilters
    pagination: Pagination
  ): ResearchResultConnection
  
  # Companies and drugs
  company(id: ID, ticker: String): Company
  companies(
    filters: CompanyFilters
    sort: CompanySort
    pagination: Pagination
  ): CompanyConnection
  
  drug(id: ID, name: String): Drug
  
  # Portfolio data
  portfolio(id: ID!): Portfolio
  portfolioAnalysis(id: ID!, analysisType: AnalysisType!): AnalysisResult
  
  # User and collaboration
  workspace(id: ID!): Workspace
  user: User
}

type Mutation {
  # Research operations
  submitResearchQuery(input: ResearchQueryInput!): ResearchQuery
  updateResearchQuery(id: ID!, input: ResearchQueryUpdateInput!): ResearchQuery
  
  # Workspace operations
  createWorkspace(input: WorkspaceInput!): Workspace
  addWorkspaceMember(workspaceId: ID!, userId: ID!, role: Role!): Workspace
  
  # Insights and annotations
  createInsight(input: InsightInput!): Insight
  addComment(targetId: ID!, content: String!): Comment
}

type Subscription {
  # Real-time research updates
  researchProgress(queryId: ID!): ResearchProgress
  
  # Workspace collaboration
  workspaceActivity(workspaceId: ID!): WorkspaceActivity
  
  # Market alerts
  portfolioAlerts(portfolioId: ID!): Alert
}

# Core types
type Company {
  id: ID!
  name: String!
  ticker: String
  marketCap: Float
  sector: String
  pipeline: [Drug!]!
  financials: FinancialMetrics
  researchMetrics: ResearchMetrics
  competitivePosition: CompetitiveAnalysis
  riskAssessment: RiskAssessment
}

type Drug {
  id: ID!
  name: String!
  genericName: String
  company: Company!
  indication: String!
  phase: String!
  mechanism: String
  clinicalTrials: [ClinicalTrial!]!
  regulatoryStatus: RegulatoryStatus
  competitiveLandscape: [CompetitiveThreat!]!
  commercialPotential: CommercialAssessment
}

type ResearchQuery {
  id: ID!
  query: String!
  status: QueryStatus!
  results: ResearchResults
  progress: QueryProgress!
  createdAt: DateTime!
  completedAt: DateTime
}

type Portfolio {
  id: ID!
  name: String!
  positions: [Position!]!
  performance: PerformanceMetrics!
  riskMetrics: RiskMetrics!
  catalysts: [BinaryEvent!]!
  analysis(type: AnalysisType!): AnalysisResult
}
```

### Example GraphQL Query

```graphql
query CompetitiveLandscape($companyId: ID!, $therapeuticArea: String!) {
  company(id: $companyId) {
    name
    ticker
    pipeline(therapeuticArea: $therapeuticArea) {
      name
      indication
      phase
      competitiveLandscape {
        directCompetitors {
          company {
            name
            ticker
          }
          drug {
            name
            phase
            advantageScore
          }
          threatLevel
        }
        pipelineThreats {
          expectedApproval
          mechanismComparison
          marketShareThreat
        }
      }
      clinicalTrials {
        nctId
        status
        primaryEndpoint
        enrollmentStatus {
          target
          actual
          percentage
        }
        keyDates {
          start
          estimatedCompletion
          dataReadout
        }
      }
    }
    financials {
      marketCap
      revenue(period: "TTM")
      rdSpending
      cashPosition
    }
    riskAssessment {
      overallScore
      riskFactors {
        category
        impact
        description
      }
    }
  }
}
```

## WebSocket API

### Connection Management

**WebSocket URL:** `wss://api.bioinvest.ai/ws`

**Authentication:**
```javascript
const ws = new WebSocket('wss://api.bioinvest.ai/ws', {
  headers: {
    'Authorization': 'Bearer ' + jwt_token
  }
});
```

### Message Protocol

All WebSocket messages follow this structure:
```json
{
  "type": "message_type",
  "id": "unique_message_id",
  "timestamp": "2024-01-15T10:00:00Z",
  "data": { /* message-specific data */ }
}
```

### Message Types

#### Subscribe to Research Progress
```json
{
  "type": "subscribe",
  "id": "sub_001",
  "channel": "research_progress",
  "filters": {
    "query_id": "q_abc123def456"
  }
}
```

**Progress Updates:**
```json
{
  "type": "research_progress",
  "id": "update_001",
  "timestamp": "2024-01-15T10:02:30Z",
  "data": {
    "query_id": "q_abc123def456",
    "source": "pubmed",
    "status": "processing",
    "progress_percentage": 45,
    "results_found": 23,
    "estimated_completion": "2024-01-15T10:05:00Z"
  }
}
```

#### Portfolio Alerts
```json
{
  "type": "subscribe",
  "id": "sub_002", 
  "channel": "portfolio_alerts",
  "filters": {
    "portfolio_id": "port_456def",
    "alert_types": ["regulatory", "clinical", "competitive"],
    "min_priority": "medium"
  }
}
```

**Alert Message:**
```json
{
  "type": "portfolio_alert",
  "id": "alert_001",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "alert_id": "alert_789xyz",
    "priority": "high",
    "category": "regulatory",
    "title": "FDA Fast Track Designation for BIIB Drug X",
    "description": "Biogen receives Fast Track designation for experimental Alzheimer's treatment",
    "affected_assets": [
      {
        "symbol": "BIIB",
        "impact_type": "positive",
        "estimated_impact": 0.15
      }
    ],
    "action_required": true,
    "expiry_time": "2024-01-15T18:00:00Z"
  }
}
```

#### Workspace Collaboration
```json
{
  "type": "workspace_update",
  "id": "collab_001",
  "timestamp": "2024-01-15T11:15:00Z",
  "data": {
    "workspace_id": "ws_789ghi",
    "event_type": "comment_added",
    "user": {
      "id": "user_456",
      "name": "John Analyst"
    },
    "content": {
      "comment_id": "comment_123",
      "target_type": "insight",
      "target_id": "insight_789",
      "comment_text": "Great analysis! Have we considered the IP landscape?"
    }
  }
}
```

## API Security

### Authentication Methods

#### JWT Bearer Tokens
```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...
```

**Token Payload:**
```json
{
  "sub": "user_123",
  "iss": "bioinvest-auth",
  "aud": "bioinvest-api",
  "exp": 1642291200,
  "iat": 1642204800,
  "scope": "research:read analytics:read portfolio:write",
  "org": "org_456"
}
```

#### API Keys for Service-to-Service
```http
X-API-Key: biv_live_abc123def456ghi789...
```

### Authorization & Permissions

#### Role-Based Access Control (RBAC)
```yaml
roles:
  analyst:
    permissions:
      - research:read
      - research:create
      - analytics:read
      - portfolio:read
  
  senior_analyst:
    permissions:
      - research:*
      - analytics:*
      - portfolio:read
      - portfolio:write
      - workspace:create
  
  portfolio_manager:
    permissions:
      - "*"  # Full access
```

#### Resource-Level Permissions
```json
{
  "resource_type": "portfolio",
  "resource_id": "port_456def",
  "permissions": [
    {
      "principal": "user_123",
      "principal_type": "user",
      "access": ["read", "write"]
    },
    {
      "principal": "org_456",
      "principal_type": "organization", 
      "access": ["read"]
    }
  ]
}
```

### Rate Limiting

#### Tier-Based Limits
```yaml
rate_limits:
  free_tier:
    requests_per_minute: 60
    requests_per_hour: 1000
    requests_per_day: 10000
    
  professional:
    requests_per_minute: 300
    requests_per_hour: 10000
    requests_per_day: 100000
    
  enterprise:
    requests_per_minute: 1000
    requests_per_hour: 50000
    requests_per_day: 1000000
```

#### Rate Limit Headers
```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 245
X-RateLimit-Reset: 1642291200
X-RateLimit-Retry-After: 60
```

## Error Handling

### Standard Error Response
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid parameters",
    "details": [
      {
        "field": "date_range.start",
        "message": "Start date must be before end date",
        "code": "INVALID_DATE_RANGE"
      }
    ],
    "request_id": "req_789xyz123",
    "timestamp": "2024-01-15T10:00:00Z",
    "documentation_url": "https://docs.bioinvest.ai/errors#VALIDATION_ERROR"
  }
}
```

### HTTP Status Codes
- `200` - Success
- `201` - Created
- `202` - Accepted (async processing)
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `409` - Conflict
- `422` - Unprocessable Entity
- `429` - Too Many Requests
- `500` - Internal Server Error
- `502` - Bad Gateway
- `503` - Service Unavailable

### Error Categories
```typescript
enum ErrorCodes {
  // Client Errors (4xx)
  INVALID_REQUEST = "INVALID_REQUEST",
  VALIDATION_ERROR = "VALIDATION_ERROR",
  AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED",
  INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS",
  RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND",
  RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED",
  
  // Server Errors (5xx)
  INTERNAL_ERROR = "INTERNAL_ERROR",
  SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE",
  TIMEOUT = "TIMEOUT",
  EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
}
```

## API Documentation & SDKs

### OpenAPI Specification
```yaml
openapi: 3.0.3
info:
  title: BioInvest AI Copilot API
  version: 1.0.0
  description: Intelligent biotech investment research platform
  contact:
    name: API Support
    url: https://docs.bioinvest.ai
    email: api-support@bioinvest.ai

servers:
  - url: https://api.bioinvest.ai/v1
    description: Production server
  - url: https://api-staging.bioinvest.ai/v1
    description: Staging server

security:
  - BearerAuth: []
  - ApiKeyAuth: []

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
```

### JavaScript/TypeScript SDK
```typescript
import { BioInvestClient } from '@bioinvest/sdk';

const client = new BioInvestClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.bioinvest.ai/v1'
});

// Submit research query
const query = await client.research.submitQuery({
  query: "What are the competitive risks for Novo Nordisk's GLP-1 pipeline?",
  sources: ['pubmed', 'clinical_trials', 'patents'],
  analysis_options: {
    include_competitive_analysis: true,
    generate_summary: true
  }
});

// Stream results
for await (const update of client.research.streamResults(query.query_id)) {
  console.log('Progress update:', update);
}

// Get portfolio analysis
const portfolio = await client.portfolio.getAnalysis('port_456def', {
  analysis_type: 'risk',
  include_scenarios: true
});
```

### Python SDK
```python
from bioinvest import BioInvestClient

client = BioInvestClient(
    api_key="your-api-key",
    base_url="https://api.bioinvest.ai/v1"
)

# Submit research query
query = client.research.submit_query(
    query="What are the competitive risks for Novo Nordisk's GLP-1 pipeline?",
    sources=["pubmed", "clinical_trials", "patents"],
    analysis_options={
        "include_competitive_analysis": True,
        "generate_summary": True
    }
)

# Async result streaming
async for update in client.research.stream_results(query.query_id):
    print(f"Progress update: {update}")

# Portfolio analysis
portfolio = client.portfolio.get_analysis(
    portfolio_id="port_456def",
    analysis_type="risk",
    include_scenarios=True
)
```

## Performance & Monitoring

### API Metrics
- **Latency Targets**: P95 <200ms for simple queries, <2s for complex analysis
- **Throughput**: 10,000+ requests per second at peak
- **Availability**: 99.9% uptime SLA
- **Error Rate**: <0.1% for non-timeout errors

### Monitoring Endpoints
```http
GET /health
GET /health/detailed
GET /metrics
GET /version
```

**Health Check Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:00:00Z",
  "version": "1.0.0",
  "services": {
    "database": "healthy",
    "ml_service": "healthy",
    "external_apis": "degraded"
  },
  "response_time_ms": 45
}
```

This comprehensive API design provides a robust, scalable, and developer-friendly interface for the BioInvest AI Copilot platform, enabling powerful biotech investment research capabilities through well-structured REST, GraphQL, and real-time APIs.
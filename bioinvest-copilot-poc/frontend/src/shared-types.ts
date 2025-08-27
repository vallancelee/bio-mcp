/**
 * BioInvest AI Copilot POC - Shared API Types
 * 
 * This file contains TypeScript type definitions that are shared between
 * the frontend and backend to ensure API contract consistency.
 */

// ============================================================================
// REQUEST/RESPONSE TYPES
// ============================================================================

export interface OrchestrationRequest {
  query: string
  sources: string[]
  options: {
    max_results_per_source: number
    include_synthesis: boolean
    priority: 'speed' | 'comprehensive' | 'balanced'
  }
}

export interface OrchestrationResponse {
  query_id: string
  status: 'initiated' | 'processing' | 'completed' | 'failed'
  estimated_completion_time: number
  progress: Record<string, SourceStatus>
  partial_results_available: boolean
  stream_url: string
  created_at: string
}

export interface ActiveQueriesResponse {
  active_queries: ActiveQuery[]
  total_count: number
  timestamp: string
}

export interface ActiveQuery {
  query_id: string
  status: string
  query: string
  created_at: string
  completed_at?: string
  progress: Record<string, SourceStatus>
  sources: string[]
  total_results: number
}

export interface HealthResponse {
  status: 'healthy' | 'degraded'
  components: {
    bio_mcp: 'healthy' | 'unhealthy'
    synthesis_service: 'healthy' | 'unhealthy'
  }
  active_queries: number
  timestamp: string
}

export interface LangGraphVisualizationResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  config: {
    max_iterations: number
    checkpoint_enabled: boolean
    tracing_enabled: boolean
  }
}

export interface LangGraphStatusResponse {
  langgraph_enabled: boolean
  status: 'operational' | 'degraded' | 'failed'
  graph_initialized: boolean
  timestamp: string
}

// ============================================================================
// SSE EVENT TYPES
// ============================================================================

export interface StreamEvent {
  event: StreamEventType
  timestamp: string
  data: any
  query_id: string
  source?: string
}

export type StreamEventType = 
  | 'connected'
  | 'progress'
  | 'partial_result'
  | 'source_started' 
  | 'source_completed' 
  | 'source_failed'
  | 'synthesis_started' 
  | 'synthesis_completed'
  | 'query_completed' 
  | 'query_failed'
  | 'message'

// ============================================================================
// DOMAIN MODELS
// ============================================================================

export type SourceStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface PubMedResult {
  pmid: string
  title: string
  abstract: string
  authors: string[]
  journal: string
  publication_date: string
  doi: string
  mesh_terms: string[]
  keywords: string[]
  citation_count: number
  impact_factor: number
  relevance_score: number
}

export interface ClinicalTrialResult {
  nct_id: string
  title: string
  brief_summary: string
  conditions: string[]
  interventions: string[]
  phase: string
  status: string
  enrollment: {
    target: number
    actual: number
    type: string
  }
  dates: {
    start_date: string
    completion_date?: string
    last_update: string
  }
  sponsors: {
    lead_sponsor: string
    collaborators: string[]
  }
  locations: Array<{
    facility: string
    city: string
    state: string
    country: string
  }>
  primary_endpoint: string
  investment_score: number
  relevance_score: number
}

export interface RAGResult {
  doc_id: string
  title: string
  content: string
  source: string
  metadata: {
    document_type: string
    created_date: string
    author: string
  }
  relevance_score: number
  chunks: Array<{
    chunk_id: string
    text: string
    position: number
    relevance_score: number
  }>
}

export interface KeyInsight {
  insight: string
  supporting_evidence: string[]
  confidence: number
  category: string
}

export interface CompetitiveAnalysis {
  direct_competitors: Array<{
    company: string
    drug: string
    brand: string
    competitive_advantage: string
    market_position: string
    threat_level: string
  }>
  competitive_threats: string[]
  market_position: string
  competitive_advantages: string[]
  risks: RiskFactor[]
}

export interface RiskFactor {
  factor: string
  impact: number
  explanation: string
  severity: 'low' | 'medium' | 'high' | 'critical'
}

export interface QualityMetrics {
  completeness: number
  recency: number
  authority: number
  diversity: number
  relevance: number
  overall_score: number
}

export interface Citation {
  id: string
  type: string
  title: string
  authors: string[]
  source: string
  year: number | null
  url: string | null
  snippet: string
  relevance_score: number
}

export interface SynthesisResult {
  summary: string
  key_insights: KeyInsight[]
  competitive_analysis: CompetitiveAnalysis | null
  risk_assessment: RiskFactor[]
  recommendations: string[]
  quality_metrics: QualityMetrics
  citations: Citation[]
  sources_summary: Record<string, number>
  generation_metadata: {
    model_used: string
    generation_time_ms: number
    total_sources_analyzed: number
    analysis_timestamp: string
    langgraph_enabled?: boolean
    execution_path?: string[]
    tool_calls?: number
  }
}

export interface QueryResults {
  query_id: string
  query: string
  status: string
  progress: Record<string, SourceStatus>
  results: {
    pubmed?: {
      total_found: number
      results: PubMedResult[]
    }
    clinical_trials?: {
      total_found: number
      studies: ClinicalTrialResult[]
    }
    rag?: {
      total_found: number
      documents: RAGResult[]
    }
  }
  synthesis?: SynthesisResult
  created_at: string
  completed_at?: string
}

// ============================================================================
// GRAPH VISUALIZATION TYPES
// ============================================================================

export interface GraphNode {
  id: string
  label: string
  type: 'processor' | 'decision' | 'tool'
}

export interface GraphEdge {
  from: string
  to: string
}

// ============================================================================
// API CLIENT INTERFACE
// ============================================================================

export interface ApiClient {
  submitQuery(request: OrchestrationRequest): Promise<OrchestrationResponse>
  getQueryStatus(queryId: string): Promise<QueryResults>
  getActiveQueries(): Promise<ActiveQuery[]>
  getSynthesis(queryId: string): Promise<SynthesisResult>
  getHealth(): Promise<HealthResponse>
  getLangGraphVisualization(): Promise<LangGraphVisualizationResponse>
  getLangGraphStatus(): Promise<LangGraphStatusResponse>
  createEventSource(streamUrl: string): EventSource
}

// ============================================================================
// UTILITY TYPES
// ============================================================================

export type ApiError = {
  detail: string
  status_code: number
}

export type ApiResponse<T> = T | ApiError

// Type guards
export const isApiError = (response: any): response is ApiError => {
  return response && typeof response.detail === 'string' && typeof response.status_code === 'number'
}

export const isHealthy = (health: HealthResponse): boolean => {
  return health.status === 'healthy'
}

export const isQueryCompleted = (query: QueryResults | ActiveQuery): boolean => {
  return query.status === 'completed'
}

export const isQueryFailed = (query: QueryResults | ActiveQuery): boolean => {
  return query.status === 'failed'
}

// ============================================================================
// CONSTANTS
// ============================================================================

export const API_ENDPOINTS = {
  HEALTH: '/health',
  SUBMIT_QUERY: '/api/research/query',
  QUERY_STATUS: '/api/research/query',
  ACTIVE_QUERIES: '/api/research/active-queries',
  SYNTHESIS: '/api/research/synthesis',
  STREAM: '/api/research/stream',
  LANGGRAPH_VISUALIZATION: '/api/langgraph/visualization',
  LANGGRAPH_STATUS: '/api/langgraph/status',
} as const

export const SOURCE_TYPES = ['pubmed', 'clinical_trials', 'rag'] as const
export const PRIORITY_LEVELS = ['speed', 'comprehensive', 'balanced'] as const
export const SEVERITY_LEVELS = ['low', 'medium', 'high', 'critical'] as const

// ============================================================================
// VERSION INFO
// ============================================================================

export const API_VERSION = 'v1'
export const CONTRACT_VERSION = '1.0.0'
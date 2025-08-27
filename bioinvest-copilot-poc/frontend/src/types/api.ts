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
  progress: Record<string, string>
  partial_results_available: boolean
  stream_url: string
  created_at: string
}

export interface StreamEvent {
  event: 'source_started' | 'source_completed' | 'source_failed' | 'synthesis_started' | 'synthesis_completed' | 'query_completed' | 'query_failed' | 'message' | 'connected' | 'progress'
  timestamp: string
  data: any
  query_id: string
  source?: string
}

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
  risks: Array<{
    factor: string
    impact: number
    explanation: string
    severity: string
  }>
}

export interface RiskFactor {
  factor: string
  impact: number
  explanation: string
  severity: string
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
  }
}

export interface ActiveQueriesResponse {
  active_queries: Array<{
    query_id: string
    status: string
    query: string
    created_at: string
    completed_at?: string
    progress: Record<string, string>
    sources: string[]
    total_results: number
  }>
  total_count: number
  timestamp: string
}

export interface QueryResults {
  query_id: string
  query: string
  status: string
  sources: {
    pubmed?: {
      results: PubMedResult[]
      total_results: number
      search_terms: string[]
      metadata: {
        query_translation: string
        search_time_ms: number
        cache_hit: boolean
      }
    }
    clinical_trials?: {
      studies: ClinicalTrialResult[]
      total_found: number
      search_terms: string[]
      metadata: {
        search_time_ms: number
        cache_hit: boolean
      }
    }
    rag?: {
      documents: RAGResult[]
      total_matches: number
      search_mode: string
      processing_time_ms: number
      metadata: {
        query_embedding_computed: boolean
        vector_search_time_ms: number
        rerank_time_ms: number
      }
    }
  }
  synthesis?: SynthesisResult
  metadata: {
    start_time: string
    completion_time?: string
    total_processing_time_ms?: number
  }
}
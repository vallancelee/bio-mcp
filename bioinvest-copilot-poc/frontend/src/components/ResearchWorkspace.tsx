import React, { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Brain, Loader2, GitBranch } from 'lucide-react'
import QueryBuilder from './QueryBuilder'
import StreamingResults from './StreamingResults'
import ResultsDisplay from './ResultsDisplay'
import LangGraphVisualizer from './LangGraphVisualizer'
import MiddlewareStatusPanel from './MiddlewareStatusPanel'
import GraphLegend from './GraphLegend'
import { useStreamingResults } from '@/hooks/useStreamingResults'
import { apiService } from '@/services/api'
import { EnhancedOrchestrationRequest, QueryResults } from '@/shared-types'

const ResearchWorkspace: React.FC = () => {
  console.log('ResearchWorkspace rendering')
  const [currentQuery, setCurrentQuery] = useState<{
    queryId: string
    streamUrl: string
    request: EnhancedOrchestrationRequest
  } | null>(null)
  const [finalResults, setFinalResults] = useState<QueryResults | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [showVisualization, setShowVisualization] = useState(false)

  // Stream results hook
  const {
    events,
    isConnected,
    error: streamError,
    reset: resetStream
  } = useStreamingResults({
    streamUrl: currentQuery?.streamUrl || null,
    queryId: currentQuery?.queryId || null,
    onComplete: useCallback((results: QueryResults) => {
      setFinalResults(results)
      setCurrentQuery(null)
    }, [])
  })

  // Query active queries
  const { data: activeQueries = [] } = useQuery({
    queryKey: ['active-queries'],
    queryFn: apiService.getActiveQueries,
    refetchInterval: 5000,
    enabled: !currentQuery
  })

  const handleSubmitQuery = async (request: EnhancedOrchestrationRequest) => {
    try {
      console.log('Submitting enhanced query:', request)
      setIsSubmitting(true)
      setFinalResults(null)
      resetStream()

      // Submit the enhanced query
      const response = await apiService.submitEnhancedQuery(request)
      console.log('Enhanced query response:', response)
      
      // Set up streaming
      setCurrentQuery({
        queryId: response.query_id,
        streamUrl: response.stream_url,
        request
      })
      console.log('Current query set:', response.query_id)
    } catch (error) {
      console.error('Failed to submit query:', error)
      // TODO: Show error toast
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleNewQuery = () => {
    setCurrentQuery(null)
    setFinalResults(null)
    resetStream()
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between py-6">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg">
                <Brain className="h-8 w-8 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  BioInvest AI Copilot
                </h1>
                <p className="text-sm text-gray-600">
                  Biotech investment research powered by AI
                </p>
              </div>
            </div>

            {/* Status and Controls */}
            <div className="flex items-center gap-4">
              {activeQueries.length > 0 && !currentQuery && (
                <div className="flex items-center gap-2 text-sm text-amber-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {activeQueries.length} active queries
                </div>
              )}
              
              {/* Visualization Toggle */}
              <button
                onClick={() => setShowVisualization(!showVisualization)}
                className={`flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors ${
                  showVisualization 
                    ? 'bg-blue-100 text-blue-700 border border-blue-300' 
                    : 'bg-gray-100 text-gray-600 border border-gray-300 hover:bg-gray-200'
                }`}
              >
                <GitBranch className="h-4 w-4" />
                LangGraph View
              </button>
              
              {currentQuery && (
                <button
                  onClick={handleNewQuery}
                  className="btn-secondary text-sm"
                  disabled={isSubmitting}
                >
                  New Query
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {showVisualization ? (
          /* LangGraph Visualization Mode */
          <div className="space-y-6">
            {/* Visualization Panels Row */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              <div className="xl:col-span-2">
                <LangGraphVisualizer
                  visualization={{
                    nodes: [
                      { id: 'parse_frame', label: 'Parse Frame', type: 'router', x: 50, y: 50 },
                      { id: 'router', label: 'Router', type: 'router', x: 200, y: 50 },
                      { id: 'pubmed_search', label: 'PubMed', type: 'source', x: 50, y: 150 },
                      { id: 'ctgov_search', label: 'ClinicalTrials', type: 'source', x: 200, y: 150 },
                      { id: 'rag_search', label: 'RAG Search', type: 'source', x: 350, y: 150 },
                      { id: 'synthesizer', label: 'Synthesize', type: 'synthesis', x: 200, y: 250 }
                    ],
                    edges: [
                      { from: 'parse_frame', to: 'router' },
                      { from: 'router', to: 'pubmed_search' },
                      { from: 'router', to: 'ctgov_search' },
                      { from: 'router', to: 'rag_search' },
                      { from: 'pubmed_search', to: 'synthesizer' },
                      { from: 'ctgov_search', to: 'synthesizer' },
                      { from: 'rag_search', to: 'synthesizer' }
                    ]
                  }}
                  currentPath={events.map(e => e.node_id).filter(Boolean)}
                  activeNode={currentQuery ? 'router' : undefined}
                  executionMetrics={events.reduce((acc, e) => {
                    if (e.node_id && e.latency_ms) {
                      acc[e.node_id] = e.latency_ms
                    }
                    return acc
                  }, {} as Record<string, number>)}
                />
                <GraphLegend />
              </div>
              
              <div>
                <MiddlewareStatusPanel
                  status={{
                    active_middleware: {
                      budget_enforcement: {
                        enabled: true,
                        active_queries: currentQuery ? 1 : 0,
                        default_budget_ms: 10000
                      },
                      error_recovery: {
                        enabled: true,
                        retry_strategy: 'exponential_backoff',
                        success_rate: 0.95
                      },
                      partial_results: {
                        enabled: true,
                        extraction_rate: 0.88
                      }
                    },
                    performance_metrics: {
                      average_execution_time: 3200,
                      timeout_rate: 0.02,
                      retry_rate: 0.05,
                      partial_results_rate: 0.12
                    }
                  }}
                />
              </div>
            </div>
            
            {/* Results Below Visualization */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div>
                <QueryBuilder
                  onSubmit={handleSubmitQuery}
                  isLoading={isSubmitting || !!currentQuery}
                />
              </div>
              
              <div className="lg:col-span-2">
                {(currentQuery || events.length > 0) && (
                  <StreamingResults
                    events={events}
                    isConnected={isConnected}
                    error={streamError}
                  />
                )}
                
                {finalResults && (
                  <div className="mt-6">
                    <ResultsDisplay results={finalResults} />
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          /* Standard Research Mode */
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column - Query Builder */}
            <div className="lg:col-span-1">
              <QueryBuilder
                onSubmit={handleSubmitQuery}
                isLoading={isSubmitting || !!currentQuery}
              />

              {/* Streaming Progress */}
              {(currentQuery || events.length > 0) && (
                <div className="mt-6">
                  <StreamingResults
                    events={events}
                    isConnected={isConnected}
                    error={streamError}
                  />
                </div>
              )}
            </div>

            {/* Right Column - Results */}
            <div className="lg:col-span-2">
              <ResultsDisplay results={finalResults} />
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-16 border-t border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-sm text-gray-600">
            <p>
              BioInvest AI Copilot POC • Powered by Bio-MCP and AI Synthesis
            </p>
            <p className="mt-1">
              For demonstration purposes only • Not for production use
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default ResearchWorkspace
import React, { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Brain, Loader2 } from 'lucide-react'
import QueryBuilder from './QueryBuilder'
import StreamingResults from './StreamingResults'
import ResultsDisplay from './ResultsDisplay'
import { useStreamingResults } from '@/hooks/useStreamingResults'
import { apiService } from '@/services/api'
import { OrchestrationRequest, QueryResults } from '@/shared-types'

const ResearchWorkspace: React.FC = () => {
  console.log('ResearchWorkspace rendering')
  const [currentQuery, setCurrentQuery] = useState<{
    queryId: string
    streamUrl: string
    request: OrchestrationRequest
  } | null>(null)
  const [finalResults, setFinalResults] = useState<QueryResults | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

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

  const handleSubmitQuery = async (request: OrchestrationRequest) => {
    try {
      console.log('Submitting query:', request)
      setIsSubmitting(true)
      setFinalResults(null)
      resetStream()

      // Submit the query
      const response = await apiService.submitQuery(request)
      console.log('Query response:', response)
      
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

            {/* Status Indicator */}
            <div className="flex items-center gap-4">
              {activeQueries.length > 0 && !currentQuery && (
                <div className="flex items-center gap-2 text-sm text-amber-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {activeQueries.length} active queries
                </div>
              )}
              
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
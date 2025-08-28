import React from 'react'
import { CheckCircle, Clock, AlertCircle, Loader2, Database, FileText, Activity } from 'lucide-react'
import { StreamEvent, BudgetStatus, MiddlewareStatusEvent, RetryAttemptEvent, PartialResultsEvent, SynthesisProgressEvent } from '../shared-types'
import { format } from 'date-fns'
import BudgetMonitor from './BudgetMonitor'
import RetryVisualizer, { RetryAttempt } from './RetryVisualizer'
import SynthesisProgress, { SynthesisStage } from './SynthesisProgress'
import PartialResultsIndicator, { PartialResultsData } from './PartialResultsIndicator'

interface StreamingResultsProps {
  events: StreamEvent[]
  isConnected: boolean
  error: string | null
}

const StreamingResults: React.FC<StreamingResultsProps> = ({
  events,
  isConnected,
  error
}) => {
  // Parse M3/M4 monitoring data from events
  const budgetStatus = events
    .filter(e => e.event === 'middleware_status')
    .slice(-1)[0]?.data?.budget as BudgetStatus | undefined
    
  const retryAttempts: RetryAttempt[] = events
    .filter(e => e.event === 'retry_attempt')
    .map(e => ({
      node: e.data.node,
      attempt: e.data.attempt,
      max_attempts: e.data.max_attempts,
      delay_ms: e.data.delay_ms,
      error: e.data.error,
      timestamp: e.timestamp
    }))
    
  const synthesisProgress = events
    .filter(e => e.event === 'synthesis_progress')
    .slice(-1)[0]?.data as SynthesisStage | undefined
    
  const partialResults = events
    .filter(e => e.event === 'partial_results')
    .slice(-1)[0]?.data as PartialResultsData | undefined
  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'source_started':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
      case 'source_completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'source_failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'synthesis_started':
        return <Loader2 className="h-4 w-4 animate-spin text-purple-500" />
      case 'synthesis_completed':
        return <CheckCircle className="h-4 w-4 text-purple-500" />
      case 'query_completed':
        return <CheckCircle className="h-4 w-4 text-green-600" />
      case 'query_failed':
        return <AlertCircle className="h-4 w-4 text-red-600" />
      default:
        return <Clock className="h-4 w-4 text-gray-400" />
    }
  }

  const getSourceIcon = (source?: string) => {
    switch (source) {
      case 'pubmed':
        return <FileText className="h-4 w-4 text-blue-600" />
      case 'clinical_trials':
        return <Activity className="h-4 w-4 text-green-600" />
      case 'rag':
        return <Database className="h-4 w-4 text-purple-600" />
      default:
        return null
    }
  }

  const getEventTitle = (event: StreamEvent) => {
    switch (event.event) {
      case 'source_started':
        return `Starting ${event.source} search...`
      case 'source_completed':
        return `${event.source} search completed`
      case 'source_failed':
        return `${event.source} search failed`
      case 'synthesis_started':
        return 'Starting AI synthesis...'
      case 'synthesis_completed':
        return 'AI synthesis completed'
      case 'query_completed':
        return 'Research analysis completed'
      case 'query_failed':
        return 'Research analysis failed'
      default:
        return event.event ? (event.event as string).replace(/_/g, ' ') : 'Unknown event'
    }
  }

  const getEventDetails = (event: StreamEvent) => {
    switch (event.event) {
      case 'source_completed':
        if (event.data?.results_count !== undefined) {
          return `Found ${event.data.results_count} results`
        }
        break
      case 'source_failed':
        return event.data?.error || 'Unknown error'
      case 'synthesis_completed':
        if (event.data?.insights_count) {
          return `Generated ${event.data.insights_count} key insights`
        }
        break
      case 'query_failed':
        return event.data?.error || 'Processing failed'
    }
    return null
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      return format(new Date(timestamp), 'HH:mm:ss')
    } catch {
      return timestamp
    }
  }

  const getStatusColor = () => {
    if (error) return 'text-red-600'
    if (!isConnected && events.length > 0) return 'text-green-600'
    if (isConnected) return 'text-blue-600'
    return 'text-gray-500'
  }

  const getStatusText = () => {
    if (error) return 'Error occurred'
    if (!isConnected && events.length > 0) return 'Analysis complete'
    if (isConnected) return 'Processing...'
    return 'Ready'
  }

  if (events.length === 0 && !error) {
    return (
      <div className="card p-6">
        <div className="text-center text-gray-500">
          <Clock className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p>Submit a research query to see real-time progress</p>
        </div>
      </div>
    )
  }

  return (
    <div className="streaming-results space-y-4">
      {/* Connection Status */}
      <div className="card">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Research Progress</h3>
            <div className="flex items-center gap-2">
              <div className={`h-2 w-2 rounded-full ${
                isConnected ? 'bg-green-400' : error ? 'bg-red-400' : 'bg-gray-400'
              }`} data-testid="connection-status" />
              <span className={`text-sm font-medium ${getStatusColor()}`}>
                {getStatusText()}
              </span>
            </div>
          </div>
        </div>
        
        {/* Real-time Monitoring Panels */}
        <div className="monitoring-grid grid grid-cols-1 lg:grid-cols-2 gap-4 p-4">
          {/* Budget Monitor */}
          {budgetStatus && <BudgetMonitor status={budgetStatus} />}
          
          {/* Retry Visualizer */}
          {retryAttempts.length > 0 && <RetryVisualizer attempts={retryAttempts} />}
          
          {/* Synthesis Progress */}
          {synthesisProgress && <SynthesisProgress stage={synthesisProgress} />}
          
          {/* Partial Results Indicator */}
          {partialResults && <PartialResultsIndicator data={partialResults} />}
        </div>
      </div>
      
      {/* Traditional Progress Display */}
      <div className="card">

      <div className="max-h-96 overflow-y-auto">
        {error && (
          <div className="p-4 border-b border-red-200 bg-red-50">
            <div className="flex items-center gap-2 text-red-700">
              <AlertCircle className="h-4 w-4" />
              <span className="font-medium">Connection Error</span>
            </div>
            <p className="text-sm text-red-600 mt-1">{error}</p>
          </div>
        )}

        <div className="divide-y divide-gray-200">
          {events.map((event, index) => {
            const details = getEventDetails(event)
            
            return (
              <div key={index} className="p-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-0.5">
                    {getEventIcon(event.event)}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {event.source && getSourceIcon(event.source)}
                      <p className="text-sm font-medium text-gray-900">
                        {getEventTitle(event)}
                      </p>
                    </div>
                    
                    {details && (
                      <p className="text-sm text-gray-600 mt-1">{details}</p>
                    )}
                    
                    {event.data && typeof event.data === 'object' && event.data.processing_time_ms && (
                      <p className="text-xs text-gray-500 mt-1">
                        Processing time: {event.data.processing_time_ms}ms
                      </p>
                    )}
                  </div>
                  
                  <div className="flex-shrink-0 text-xs text-gray-500">
                    {formatTimestamp(event.timestamp)}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
        </div>

        {events.length > 0 && (
          <div className="p-4 border-t border-gray-200 bg-gray-50">
            <div className="text-sm text-gray-600">
              <strong>{events.length}</strong> events • 
              Started {events.length > 0 && formatTimestamp(events[0].timestamp)}
              {events.length > 1 && events[events.length - 1].event === 'query_completed' && (
                <span> • Completed {formatTimestamp(events[events.length - 1].timestamp)}</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default StreamingResults
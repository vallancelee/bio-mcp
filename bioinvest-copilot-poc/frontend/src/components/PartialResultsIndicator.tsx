/**
 * PartialResultsIndicator Component
 * 
 * Shows when partial results are available due to timeouts, errors, or budget exhaustion
 * as defined in Milestone 3 of the implementation plan.
 */

import React from 'react'

export interface PartialResultsData {
  reason: 'timeout' | 'error' | 'budget_exhausted'
  completion_percentage: number
  available_sources: string[]
  total_results: number
}

interface PartialResultsIndicatorProps {
  data: PartialResultsData
}

export const PartialResultsIndicator: React.FC<PartialResultsIndicatorProps> = ({ data }) => {
  const getReasonIcon = (reason: string) => {
    const icons = {
      timeout: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-5 h-5">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      budget_exhausted: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-5 h-5">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
        </svg>
      ),
      error: (
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-5 h-5">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.084 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
      )
    }
    return icons[reason as keyof typeof icons] || icons.error
  }

  const getReasonMessage = (reason: string) => {
    const messages = {
      timeout: 'Query timed out - returning available results',
      budget_exhausted: 'Budget limit reached - returning available results',
      error: 'Some sources failed - returning successful results'
    }
    return messages[reason as keyof typeof messages] || 'Partial results available'
  }

  const getReasonColor = (reason: string) => {
    const colors = {
      timeout: 'border-blue-500 bg-blue-50 text-blue-800',
      budget_exhausted: 'border-orange-500 bg-orange-50 text-orange-800',
      error: 'border-yellow-500 bg-yellow-50 text-yellow-800'
    }
    return colors[reason as keyof typeof colors] || colors.error
  }

  const formatSourceName = (source: string): string => {
    const sourceNames = {
      pubmed: 'PubMed',
      clinical_trials: 'ClinicalTrials.gov',
      rag: 'RAG Search'
    }
    return sourceNames[source as keyof typeof sourceNames] || source
  }

  return (
    <div 
      className={`partial-results-alert rounded-lg border p-4 ${getReasonColor(data.reason)}`}
      data-testid="partial-results-indicator"
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          {getReasonIcon(data.reason)}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-lg mb-1">
            Partial Results ({Math.round(data.completion_percentage * 100)}% Complete)
          </div>
          
          <div className="text-sm mb-3">
            {getReasonMessage(data.reason)}
          </div>
          
          {/* Completion Progress Bar */}
          <div className="mb-4">
            <div className="flex justify-between text-sm mb-1">
              <span>Analysis Progress</span>
              <span>{Math.round(data.completion_percentage * 100)}%</span>
            </div>
            <div className="w-full bg-white bg-opacity-50 rounded-full h-2">
              <div 
                className="bg-current rounded-full h-2 transition-all duration-300"
                style={{ width: `${data.completion_percentage * 100}%` }}
              />
            </div>
          </div>
          
          {/* Available Sources */}
          <div className="mb-3">
            <span className="text-sm font-medium">Available sources:</span>
            <div className="flex flex-wrap gap-2 mt-1">
              {data.available_sources.map(source => (
                <span 
                  key={source} 
                  className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-white bg-opacity-70 border border-current border-opacity-30"
                >
                  {formatSourceName(source)}
                </span>
              ))}
            </div>
          </div>
          
          {/* Results Summary */}
          <div className="text-sm">
            <strong>{data.total_results}</strong> results available from partial analysis
          </div>
        </div>
        
        {/* Status Icon */}
        <div className="flex-shrink-0">
          <div className="w-6 h-6 bg-white bg-opacity-70 rounded-full flex items-center justify-center">
            <span className="text-sm font-bold">
              {Math.round(data.completion_percentage * 100)}%
            </span>
          </div>
        </div>
      </div>

      {/* Recommendations */}
      <div className="mt-4 pt-3 border-t border-current border-opacity-20">
        <div className="text-sm">
          <div className="font-medium mb-1">Recommendations:</div>
          <ul className="text-xs space-y-1 list-disc list-inside">
            {data.reason === 'timeout' && (
              <>
                <li>Try reducing the number of sources or results per source</li>
                <li>Consider increasing the budget limit for comprehensive analysis</li>
              </>
            )}
            {data.reason === 'budget_exhausted' && (
              <>
                <li>Increase budget allocation for more comprehensive results</li>
                <li>Use current results as a starting point for focused queries</li>
              </>
            )}
            {data.reason === 'error' && (
              <>
                <li>Check if external services are available</li>
                <li>Try re-running the query with different parameters</li>
              </>
            )}
            <li>Current partial results can still provide valuable insights</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

export default PartialResultsIndicator
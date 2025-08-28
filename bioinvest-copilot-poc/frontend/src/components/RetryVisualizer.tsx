/**
 * RetryVisualizer Component
 * 
 * Visualizes error recovery attempts with exponential backoff timing
 * as defined in Milestone 3 of the implementation plan.
 */

import React from 'react'

export interface RetryAttempt {
  node: string
  attempt: number
  max_attempts: number
  delay_ms: number
  error: string
  timestamp: string
}

interface RetryVisualizerProps {
  attempts: RetryAttempt[]
}

export const RetryVisualizer: React.FC<RetryVisualizerProps> = ({ attempts }) => {
  const formatDelayTime = (delayMs: number): string => {
    if (delayMs < 1000) {
      return `${delayMs}ms`
    }
    return `${(delayMs / 1000).toFixed(1)}s`
  }

  const getRetryIcon = (isActive: boolean) => (
    <div className={`w-4 h-4 ${isActive ? 'text-blue-500 animate-spin' : 'text-gray-400'}`}>
      <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
    </div>
  )

  const getBadgeVariant = (attempt: number, maxAttempts: number) => {
    const ratio = attempt / maxAttempts
    if (ratio >= 0.8) return 'bg-red-100 text-red-800 border border-red-200'
    if (ratio >= 0.5) return 'bg-yellow-100 text-yellow-800 border border-yellow-200'
    return 'bg-blue-100 text-blue-800 border border-blue-200'
  }

  if (attempts.length === 0) {
    return null
  }

  return (
    <div className="retry-visualizer bg-white rounded-lg border shadow-sm p-4" data-testid="retry-visualizer">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-4 h-4 text-green-500">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-gray-900">Error Recovery</h3>
        <span className="text-sm text-gray-500">({attempts.length} active)</span>
      </div>

      <div className="space-y-4">
        {attempts.map((attempt, index) => (
          <div key={index} className="retry-attempt border rounded-lg p-3 bg-gray-50" data-testid="retry-attempt">
            <div className="flex items-center gap-3">
              {getRetryIcon(true)}
              
              <div className="flex-1">
                <div className="font-medium text-sm text-gray-900">
                  {attempt.node}
                </div>
                <div className="text-xs text-gray-600 mt-1">
                  Next retry in {formatDelayTime(attempt.delay_ms)}
                </div>
                {attempt.error && (
                  <div className="text-xs text-red-600 mt-1 truncate" title={attempt.error}>
                    Error: {attempt.error}
                  </div>
                )}
              </div>
              
              <div className={`px-2 py-1 rounded-full text-xs font-medium ${getBadgeVariant(attempt.attempt, attempt.max_attempts)}`}>
                {attempt.attempt}/{attempt.max_attempts}
              </div>
            </div>
            
            {/* Exponential Backoff Visualization */}
            <div className="mt-3 ml-6">
              <div className="text-xs text-gray-500 mb-1">Backoff progression:</div>
              <div className="flex items-center gap-1">
                {Array.from({ length: attempt.max_attempts }, (_, i) => {
                  const width = Math.pow(2, i) * 8 // Exponential width
                  const maxWidth = 48 // Maximum width in pixels
                  const actualWidth = Math.min(width, maxWidth)
                  const isCompleted = i < attempt.attempt
                  const isCurrent = i === attempt.attempt - 1
                  
                  return (
                    <div
                      key={i}
                      className={`h-2 rounded transition-all duration-200 ${
                        isCompleted 
                          ? 'bg-red-400' 
                          : isCurrent 
                            ? 'bg-blue-400 animate-pulse'
                            : 'bg-gray-200'
                      }`}
                      style={{ width: `${actualWidth}px` }}
                      title={`Attempt ${i + 1}: ${Math.pow(2, i) * 1000}ms delay`}
                    />
                  )
                })}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Exponential backoff delays (hover for details)
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="mt-4 pt-3 border-t border-gray-200">
        <div className="text-sm text-gray-600">
          <div className="flex justify-between">
            <span>Total attempts:</span>
            <span className="font-medium">{attempts.reduce((sum, a) => sum + a.attempt, 0)}</span>
          </div>
          <div className="flex justify-between mt-1">
            <span>Success rate:</span>
            <span className="font-medium">
              {attempts.length > 0 ? '...' : 'N/A'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default RetryVisualizer
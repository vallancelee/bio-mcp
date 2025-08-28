/**
 * MiddlewareStatusPanel Component
 * 
 * Displays real-time status of M3 middleware components
 * Shows budget enforcement, error recovery, and partial results status
 */

import React from 'react'
import { Settings, Clock, RotateCcw, PieChart, Activity } from 'lucide-react'

export interface MiddlewareComponentStatus {
  enabled: boolean
  active_queries?: number
  success_rate?: number
  default_budget_ms?: number
  retry_strategy?: string
  extraction_rate?: number
}

export interface PerformanceMetrics {
  average_execution_time: number
  timeout_rate: number
  retry_rate: number
  partial_results_rate: number
}

export interface MiddlewareStatusData {
  active_middleware: {
    budget_enforcement: MiddlewareComponentStatus
    error_recovery: MiddlewareComponentStatus
    partial_results: MiddlewareComponentStatus
  }
  performance_metrics: PerformanceMetrics
}

interface MiddlewareStatusPanelProps {
  status: MiddlewareStatusData
}

const MiddlewareStatusPanel: React.FC<MiddlewareStatusPanelProps> = ({ status }) => {
  const getStatusBadgeClasses = (enabled: boolean): string => {
    return enabled 
      ? 'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800'
      : 'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800'
  }

  const formatTime = (timeMs: number): string => {
    return timeMs >= 1000 ? `${(timeMs / 1000).toFixed(1)}s` : `${Math.round(timeMs)}ms`
  }

  const formatPercentage = (rate: number): string => {
    return `${(rate * 100).toFixed(1)}%`
  }

  return (
    <div 
      className="middleware-status bg-white border border-gray-200 rounded-lg shadow-sm" 
      data-testid="middleware-status-panel"
    >
      <div className="border-b border-gray-200 px-6 py-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Settings className="h-4 w-4" />
          Middleware Components
        </h3>
      </div>
      
      <div className="px-6 py-4">
        <div className="space-y-4">
          {/* Budget Enforcement */}
          <div className="middleware-component" data-testid="budget-enforcement">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-blue-500" />
                <span className="font-medium">Budget Enforcement</span>
              </div>
              <span className={getStatusBadgeClasses(status.active_middleware.budget_enforcement.enabled)}>
                {status.active_middleware.budget_enforcement.enabled ? "Active" : "Inactive"}
              </span>
            </div>
            
            {status.active_middleware.budget_enforcement.enabled && (
              <div className="mt-2 ml-6 text-sm text-gray-600 space-y-1">
                {status.active_middleware.budget_enforcement.default_budget_ms && (
                  <div>
                    Default Budget: {formatTime(status.active_middleware.budget_enforcement.default_budget_ms)}
                  </div>
                )}
                {status.active_middleware.budget_enforcement.active_queries !== undefined && (
                  <div>
                    Active Queries: {status.active_middleware.budget_enforcement.active_queries}
                  </div>
                )}
              </div>
            )}
          </div>
          
          {/* Error Recovery */}
          <div className="middleware-component" data-testid="error-recovery">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <RotateCcw className="h-4 w-4 text-green-500" />
                <span className="font-medium">Error Recovery</span>
              </div>
              <span className={getStatusBadgeClasses(status.active_middleware.error_recovery.enabled)}>
                {status.active_middleware.error_recovery.enabled ? "Active" : "Inactive"}
              </span>
            </div>
            
            {status.active_middleware.error_recovery.enabled && (
              <div className="mt-2 ml-6 text-sm text-gray-600 space-y-1">
                {status.active_middleware.error_recovery.retry_strategy && (
                  <div>
                    Strategy: {status.active_middleware.error_recovery.retry_strategy}
                  </div>
                )}
                {status.active_middleware.error_recovery.success_rate !== undefined && (
                  <div>
                    Success Rate: {formatPercentage(status.active_middleware.error_recovery.success_rate)}
                  </div>
                )}
              </div>
            )}
          </div>
          
          {/* Partial Results */}
          <div className="middleware-component" data-testid="partial-results">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <PieChart className="h-4 w-4 text-yellow-500" />
                <span className="font-medium">Partial Results</span>
              </div>
              <span className={getStatusBadgeClasses(status.active_middleware.partial_results.enabled)}>
                {status.active_middleware.partial_results.enabled ? "Active" : "Inactive"}
              </span>
            </div>
            
            {status.active_middleware.partial_results.enabled && (
              <div className="mt-2 ml-6 text-sm text-gray-600">
                {status.active_middleware.partial_results.extraction_rate !== undefined && (
                  <div>
                    Extraction Rate: {formatPercentage(status.active_middleware.partial_results.extraction_rate)}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        
        {/* Performance Metrics */}
        <div className="performance-metrics mt-6 pt-4 border-t">
          <h4 className="font-medium mb-3 flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Performance Metrics
          </h4>
          
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="metric-item">
              <span className="text-gray-600">Avg Execution:</span>
              <div className="font-medium" data-testid="avg-execution-time">
                {formatTime(status.performance_metrics.average_execution_time)}
              </div>
            </div>
            
            <div className="metric-item">
              <span className="text-gray-600">Timeout Rate:</span>
              <div className="font-medium" data-testid="timeout-rate">
                {formatPercentage(status.performance_metrics.timeout_rate)}
              </div>
            </div>
            
            <div className="metric-item">
              <span className="text-gray-600">Retry Rate:</span>
              <div className="font-medium" data-testid="retry-rate">
                {formatPercentage(status.performance_metrics.retry_rate)}
              </div>
            </div>
            
            <div className="metric-item">
              <span className="text-gray-600">Partial Rate:</span>
              <div className="font-medium" data-testid="partial-rate">
                {formatPercentage(status.performance_metrics.partial_results_rate)}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default MiddlewareStatusPanel
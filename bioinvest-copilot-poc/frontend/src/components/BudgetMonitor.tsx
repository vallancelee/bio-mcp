/**
 * BudgetMonitor Component
 * 
 * Real-time visualization of budget consumption with danger zone warnings
 * as defined in Milestone 3 of the implementation plan.
 */

import React from 'react'
import { BudgetStatus } from '../shared-types'

interface BudgetMonitorProps {
  status: BudgetStatus
}

export const BudgetMonitor: React.FC<BudgetMonitorProps> = ({ status }) => {
  const getDangerLevel = (utilization: number): 'normal' | 'warning' | 'critical' => {
    if (utilization >= 0.9) return 'critical'
    if (utilization >= 0.8) return 'warning'
    return 'normal'
  }

  const getDangerLevelStyles = (level: string) => {
    const styles = {
      normal: 'bg-green-500',
      warning: 'bg-yellow-500',
      critical: 'bg-red-500'
    }
    return styles[level as keyof typeof styles] || styles.normal
  }

  const dangerLevel = getDangerLevel(status.utilization)
  const timeRemainingSeconds = Math.round(status.remaining_ms / 1000)
  const timeConsumedSeconds = Math.round(status.consumed_ms / 1000)

  return (
    <div className="budget-monitor bg-white rounded-lg border shadow-sm p-4" data-testid="budget-monitor">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-4 h-4 text-blue-500">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-gray-900">Budget Monitor</h3>
      </div>

      {/* Progress Bar with Zones */}
      <div className="relative mb-4">
        <div className="w-full bg-gray-200 rounded-full h-4">
          <div 
            className={`h-4 rounded-full transition-all duration-300 ${getDangerLevelStyles(dangerLevel)}`}
            style={{ width: `${Math.min(status.utilization * 100, 100)}%` }}
            data-testid="budget-progress"
          />
        </div>
        
        {/* Danger Zone Markers */}
        <div className="absolute top-0 left-[80%] w-px h-full bg-yellow-400 opacity-60" />
        <div className="absolute top-0 left-[90%] w-px h-full bg-red-500 opacity-60" />
      </div>

      {/* Time Remaining Display */}
      <div className="flex justify-between items-center text-sm text-gray-600 mb-3">
        <span>Consumed: {timeConsumedSeconds}s</span>
        <span className="font-medium">Remaining: {timeRemainingSeconds}s</span>
      </div>

      {/* Utilization Percentage */}
      <div className="text-center mb-3">
        <span className={`text-2xl font-bold ${
          dangerLevel === 'critical' ? 'text-red-600' :
          dangerLevel === 'warning' ? 'text-yellow-600' : 'text-green-600'
        }`}>
          {Math.round(status.utilization * 100)}%
        </span>
        <span className="text-sm text-gray-500 ml-1">utilized</span>
      </div>

      {/* Danger Zone Warning */}
      {status.utilization >= 0.8 && (
        <div 
          className={`p-3 rounded-lg ${
            dangerLevel === 'critical' 
              ? 'bg-red-50 border border-red-200 text-red-800'
              : 'bg-yellow-50 border border-yellow-200 text-yellow-800'
          }`}
          data-testid="budget-warning"
        >
          <div className="flex items-center gap-2">
            <div className="w-4 h-4">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.084 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <div>
              <div className="font-medium">
                {dangerLevel === 'critical' ? 'Critical Budget Usage!' : 'High Budget Usage'}
              </div>
              <div className="text-xs mt-1">
                {dangerLevel === 'critical' 
                  ? 'Query may timeout very soon. Consider stopping or waiting.'
                  : 'Budget usage high! Query may timeout soon.'
                }
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default BudgetMonitor
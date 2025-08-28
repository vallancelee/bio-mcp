/**
 * GraphLegend Component
 * 
 * Provides visual legend for understanding LangGraph visualization
 * Shows node types, statuses, and flow indicators
 */

import React from 'react'
import { Info, Play, CheckCircle, Clock, AlertCircle } from 'lucide-react'

const GraphLegend: React.FC = () => {
  const nodeTypes = [
    { icon: '📚', label: 'Source Node', description: 'Data retrieval (PubMed, ClinicalTrials)' },
    { icon: '⚙️', label: 'Middleware', description: 'Processing and state management' },
    { icon: '🧠', label: 'Synthesis', description: 'AI analysis and answer generation' },
    { icon: '🎯', label: 'Router', description: 'Decision and flow control' }
  ]

  const nodeStatuses = [
    { 
      icon: <Clock className="h-3 w-3 text-gray-400" />, 
      label: 'Pending', 
      description: 'Not yet started',
      className: 'bg-gray-100 border-gray-300 text-gray-600'
    },
    { 
      icon: <Play className="h-3 w-3 text-blue-500" />, 
      label: 'Active', 
      description: 'Currently executing',
      className: 'bg-blue-100 border-blue-500 text-blue-800'
    },
    { 
      icon: <CheckCircle className="h-3 w-3 text-green-500" />, 
      label: 'Completed', 
      description: 'Successfully finished',
      className: 'bg-green-100 border-green-500 text-green-800'
    },
    { 
      icon: <AlertCircle className="h-3 w-3 text-red-500" />, 
      label: 'Failed', 
      description: 'Encountered error',
      className: 'bg-red-100 border-red-500 text-red-800'
    }
  ]

  return (
    <div className="graph-legend bg-gray-50 rounded-lg p-4 mt-4" data-testid="graph-legend">
      <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
        <Info className="h-4 w-4" />
        Legend
      </h4>
      
      <div className="grid md:grid-cols-2 gap-4">
        {/* Node Types */}
        <div className="legend-section">
          <h5 className="text-sm font-medium text-gray-700 mb-2">Node Types</h5>
          <div className="space-y-2">
            {nodeTypes.map((type, index) => (
              <div key={index} className="flex items-center gap-2 text-sm">
                <span className="text-lg">{type.icon}</span>
                <div>
                  <div className="font-medium text-gray-900">{type.label}</div>
                  <div className="text-xs text-gray-600">{type.description}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Node Status */}
        <div className="legend-section">
          <h5 className="text-sm font-medium text-gray-700 mb-2">Execution Status</h5>
          <div className="space-y-2">
            {nodeStatuses.map((status, index) => (
              <div key={index} className="flex items-center gap-2 text-sm">
                <div className={`p-1 rounded border ${status.className}`}>
                  {status.icon}
                </div>
                <div>
                  <div className="font-medium text-gray-900">{status.label}</div>
                  <div className="text-xs text-gray-600">{status.description}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* Flow Indicators */}
      <div className="legend-section mt-4 pt-4 border-t border-gray-200">
        <h5 className="text-sm font-medium text-gray-700 mb-2">Flow Indicators</h5>
        <div className="flex items-center gap-6 text-sm">
          <div className="flex items-center gap-2">
            <svg width="20" height="8">
              <line x1="0" y1="4" x2="15" y2="4" stroke="#3B82F6" strokeWidth="2" markerEnd="url(#arrowhead)" />
            </svg>
            <span className="text-gray-600">Active path</span>
          </div>
          <div className="flex items-center gap-2">
            <svg width="20" height="8">
              <line x1="0" y1="4" x2="15" y2="4" stroke="#D1D5DB" strokeWidth="1" />
            </svg>
            <span className="text-gray-600">Inactive path</span>
          </div>
        </div>
      </div>
      
      {/* Performance Indicators */}
      <div className="legend-section mt-3">
        <h5 className="text-sm font-medium text-gray-700 mb-2">Performance Indicators</h5>
        <div className="text-xs text-gray-600 space-y-1">
          <div>• Node execution times shown below completed nodes</div>
          <div>• Active nodes have pulsing animation</div>
          <div>• Progress bar shows overall completion percentage</div>
        </div>
      </div>
    </div>
  )
}

export default GraphLegend
/**
 * LangGraphVisualizer Component
 * 
 * Interactive visualization of LangGraph workflow execution
 * Shows node progression, middleware interactions, and execution paths
 */

import React from 'react'
import { GitBranch, Play, CheckCircle, AlertCircle, Clock } from 'lucide-react'

export interface GraphNode {
  id: string
  label: string
  type: 'source' | 'middleware' | 'synthesis' | 'router'
  x: number
  y: number
}

export interface GraphEdge {
  from: string
  to: string
  label?: string
}

export interface LangGraphVisualizationData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

interface LangGraphVisualizerProps {
  visualization: LangGraphVisualizationData
  currentPath?: string[]
  activeNode?: string
  executionMetrics?: Record<string, number>
}

const LangGraphVisualizer: React.FC<LangGraphVisualizerProps> = ({
  visualization,
  currentPath = [],
  activeNode,
  executionMetrics = {}
}) => {
  const getNodeStatus = (nodeId: string): 'pending' | 'active' | 'completed' => {
    if (nodeId === activeNode) return 'active'
    if (currentPath.includes(nodeId)) return 'completed'
    return 'pending'
  }

  const getNodeTypeIcon = (type: string) => {
    const icons = {
      source: '📚',
      middleware: '⚙️', 
      synthesis: '🧠',
      router: '🎯'
    }
    return icons[type as keyof typeof icons] || '⚙️'
  }

  const getNodeStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <Play className="h-3 w-3 text-blue-500 animate-pulse" />
      case 'completed':
        return <CheckCircle className="h-3 w-3 text-green-500" />
      case 'pending':
        return <Clock className="h-3 w-3 text-gray-400" />
      default:
        return <AlertCircle className="h-3 w-3 text-red-500" />
    }
  }

  const getNodeStyleClasses = (status: string): string => {
    const baseClasses = 'absolute p-3 rounded-lg border-2 transition-all duration-300 min-w-24 text-center'
    
    switch (status) {
      case 'active':
        return `${baseClasses} bg-blue-100 border-blue-500 text-blue-800 shadow-lg scale-110`
      case 'completed':
        return `${baseClasses} bg-green-100 border-green-500 text-green-800 shadow-md`
      case 'pending':
        return `${baseClasses} bg-gray-100 border-gray-300 text-gray-600`
      default:
        return `${baseClasses} bg-red-100 border-red-500 text-red-800`
    }
  }

  const getEdgeStyleClasses = (isActive: boolean): string => {
    return isActive ? 'stroke-blue-500 stroke-2' : 'stroke-gray-300 stroke-1'
  }

  // Calculate dynamic positions if not provided
  const getNodePosition = (nodeId: string): { x: number; y: number } => {
    const node = visualization.nodes.find(n => n.id === nodeId)
    if (node && node.x !== undefined && node.y !== undefined) {
      return { x: node.x, y: node.y }
    }
    
    // Fallback: calculate simple layout
    const index = visualization.nodes.findIndex(n => n.id === nodeId)
    const cols = Math.ceil(Math.sqrt(visualization.nodes.length))
    const row = Math.floor(index / cols)
    const col = index % cols
    
    return {
      x: col * 150 + 50,
      y: row * 100 + 50
    }
  }

  return (
    <div 
      className="langgraph-visualizer bg-white border border-gray-200 rounded-lg shadow-sm" 
      data-testid="langgraph-visualizer"
    >
      <div className="border-b border-gray-200 px-6 py-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <GitBranch className="h-4 w-4" />
          LangGraph Execution Flow
        </h3>
      </div>
      
      <div className="p-6">
        {/* Graph Canvas */}
        <div className="relative bg-gray-50 rounded-lg p-6 min-h-[400px] overflow-hidden">
          {/* SVG for edges */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 1 }}>
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon
                  points="0 0, 10 3.5, 0 7"
                  fill="#3B82F6"
                />
              </marker>
            </defs>
            
            {/* Render edges */}
            {visualization.edges.map((edge, index) => {
              const fromPos = getNodePosition(edge.from)
              const toPos = getNodePosition(edge.to)
              const isActive = currentPath.includes(edge.from) && currentPath.includes(edge.to)
              
              // Calculate connection points (center of nodes)
              const fromX = fromPos.x + 50 // Node center offset
              const fromY = fromPos.y + 25
              const toX = toPos.x + 50
              const toY = toPos.y + 25
              
              return (
                <line
                  key={index}
                  x1={fromX}
                  y1={fromY}
                  x2={toX}
                  y2={toY}
                  className={getEdgeStyleClasses(isActive)}
                  markerEnd="url(#arrowhead)"
                />
              )
            })}
          </svg>
          
          {/* Render nodes */}
          {visualization.nodes.map((node) => {
            const status = getNodeStatus(node.id)
            const position = getNodePosition(node.id)
            const metrics = executionMetrics[node.id]
            
            return (
              <div
                key={node.id}
                className={getNodeStyleClasses(status)}
                style={{
                  left: `${position.x}px`,
                  top: `${position.y}px`,
                  zIndex: status === 'active' ? 10 : 2
                }}
                data-testid={`node-${node.id}`}
              >
                <div className="flex flex-col items-center gap-1">
                  {/* Node type icon */}
                  <div className="text-lg">
                    {getNodeTypeIcon(node.type)}
                  </div>
                  
                  {/* Node label */}
                  <div className="text-sm font-medium">
                    {node.label}
                  </div>
                  
                  {/* Status icon */}
                  <div className="flex items-center gap-1">
                    {getNodeStatusIcon(status)}
                  </div>
                  
                  {/* Performance metrics */}
                  {metrics && status === 'completed' && (
                    <div className="text-xs opacity-75">
                      {Math.round(metrics)}ms
                    </div>
                  )}
                </div>
                
                {/* Active node pulse effect */}
                {status === 'active' && (
                  <div className="absolute inset-0 rounded-lg border-2 border-blue-400 animate-ping opacity-75" />
                )}
              </div>
            )
          })}
        </div>
        
        {/* Execution Statistics */}
        {currentPath.length > 0 && (
          <div className="mt-4 p-3 bg-blue-50 rounded-lg">
            <div className="text-sm font-medium text-blue-800 mb-1">
              Execution Progress: {currentPath.length}/{visualization.nodes.length} nodes
            </div>
            <div className="text-xs text-blue-600">
              Current: {activeNode || 'Completed'}
            </div>
            
            {/* Progress bar */}
            <div className="mt-2 w-full bg-blue-200 rounded-full h-2">
              <div 
                className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${(currentPath.length / visualization.nodes.length) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default LangGraphVisualizer
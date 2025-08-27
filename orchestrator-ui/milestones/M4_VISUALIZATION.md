# M4 — Visualization & Debugging (2 days)

## Objective
Implement advanced graph visualization features and comprehensive debugging tools. This milestone transforms the basic graph view into a powerful debugging interface with node inspection, performance monitoring, session management, and advanced visualization capabilities.

## Dependencies
- **M1 — API Integration** completed (debug endpoints and WebSocket available)
- **M2 — Core UI Foundation** completed (React components and graph container ready)
- **M3 — Streaming Integration** completed (real-time updates working)
- Bio-MCP orchestrator with debug mode and state inspection capabilities

## Deliverables

### 1. Advanced Node Inspector

**File**: `src/components/NodeInspector/NodeInspector.tsx`
```tsx
import React, { useState, useEffect } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/Tabs'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { 
  Eye, 
  Play, 
  Pause, 
  RotateCcw, 
  Clock, 
  Database,
  Code,
  Activity,
  AlertTriangle,
  CheckCircle
} from 'lucide-react'
import { JSONViewer } from '../ui/JSONViewer'
import { useWebSocketDebug } from '../../hooks/useWebSocketDebug'
import type { OrchestrationSession } from '../../types/orchestrator'

interface NodeInspectorProps {
  session: OrchestrationSession
  selectedNodeId: string | null
  nodeData?: any
  onClose: () => void
}

export function NodeInspector({ session, selectedNodeId, nodeData, onClose }: NodeInspectorProps) {
  const [activeTab, setActiveTab] = useState('state')
  const [nodeState, setNodeState] = useState(null)
  const [executionHistory, setExecutionHistory] = useState<any[]>([])
  
  const {
    debugState,
    isConnected,
    setBreakpoint,
    stepExecution,
    inspectNodeState,
    resumeExecution
  } = useWebSocketDebug(session.session_id, session.debug_mode)

  useEffect(() => {
    if (selectedNodeId && isConnected) {
      inspectNodeState(selectedNodeId)
    }
  }, [selectedNodeId, isConnected, inspectNodeState])

  useEffect(() => {
    if (debugState?.inspectedState && debugState?.inspectedNode === selectedNodeId) {
      setNodeState(debugState.inspectedState)
    }
  }, [debugState, selectedNodeId])

  if (!selectedNodeId) {
    return (
      <Card className="p-6 text-center">
        <Eye className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Node Inspector</h3>
        <p className="text-gray-600">Select a node from the graph to inspect its state and execution details.</p>
      </Card>
    )
  }

  const isCurrentBreakpoint = debugState?.currentBreakpoint === selectedNodeId
  const hasBreakpoint = debugState?.breakpoints?.[selectedNodeId]
  const isExecuting = nodeData?.status === 'running'
  const hasCompleted = nodeData?.status === 'completed'
  const hasFailed = nodeData?.status === 'failed'

  const handleToggleBreakpoint = () => {
    setBreakpoint(selectedNodeId, !hasBreakpoint)
  }

  const handleStepExecution = () => {
    stepExecution(selectedNodeId)
  }

  const handleResumeExecution = () => {
    resumeExecution()
  }

  const getStatusBadge = () => {
    if (hasFailed) return <Badge variant="destructive">Failed</Badge>
    if (hasCompleted) return <Badge variant="success">Completed</Badge>
    if (isExecuting) return <Badge variant="default">Running</Badge>
    if (isCurrentBreakpoint) return <Badge variant="warning">Paused</Badge>
    return <Badge variant="secondary">Waiting</Badge>
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <Activity className="w-5 h-5 text-blue-600" />
            <h2 className="text-xl font-semibold text-gray-900">
              Node Inspector
            </h2>
          </div>
          {getStatusBadge()}
        </div>
        <Button variant="outline" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>

      {/* Node Information */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-semibold text-gray-900">{selectedNodeId}</h3>
            <p className="text-sm text-gray-600">
              {nodeData?.label || 'Orchestrator node'}
            </p>
          </div>
          <div className="flex space-x-2">
            {/* Performance Metrics */}
            {nodeData?.latency && (
              <div className="text-right">
                <div className="text-sm font-medium text-gray-900">
                  {nodeData.latency}ms
                </div>
                <div className="text-xs text-gray-500">Duration</div>
              </div>
            )}
          </div>
        </div>

        {/* Debug Controls */}
        {session.debug_mode && (
          <div className="flex space-x-2 pt-4 border-t border-gray-200">
            <Button
              variant={hasBreakpoint ? "default" : "outline"}
              size="sm"
              onClick={handleToggleBreakpoint}
              disabled={!isConnected}
            >
              <Pause className="w-4 h-4 mr-1" />
              {hasBreakpoint ? 'Remove Breakpoint' : 'Set Breakpoint'}
            </Button>
            
            {isCurrentBreakpoint && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleStepExecution}
                  disabled={!isConnected}
                >
                  <Play className="w-4 h-4 mr-1" />
                  Step
                </Button>
                <Button
                  variant="default"
                  size="sm"
                  onClick={handleResumeExecution}
                  disabled={!isConnected}
                >
                  <Play className="w-4 h-4 mr-1" />
                  Resume
                </Button>
              </>
            )}
            
            <Button
              variant="outline"
              size="sm"
              onClick={() => inspectNodeState(selectedNodeId)}
              disabled={!isConnected}
            >
              <RotateCcw className="w-4 h-4 mr-1" />
              Refresh
            </Button>
          </div>
        )}
      </Card>

      {/* Inspection Tabs */}
      <Card className="p-0">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="state" className="flex items-center gap-2">
              <Database className="w-4 h-4" />
              State
            </TabsTrigger>
            <TabsTrigger value="result" className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4" />
              Result
            </TabsTrigger>
            <TabsTrigger value="performance" className="flex items-center gap-2">
              <Clock className="w-4 h-4" />
              Performance
            </TabsTrigger>
            <TabsTrigger value="logs" className="flex items-center gap-2">
              <Code className="w-4 h-4" />
              Logs
            </TabsTrigger>
          </TabsList>

          <div className="p-6">
            <TabsContent value="state">
              <NodeStateView nodeState={nodeState} nodeId={selectedNodeId} />
            </TabsContent>
            
            <TabsContent value="result">
              <NodeResultView 
                result={nodeData?.result} 
                nodeId={selectedNodeId}
                status={nodeData?.status}
              />
            </TabsContent>
            
            <TabsContent value="performance">
              <NodePerformanceView 
                nodeData={nodeData}
                nodeId={selectedNodeId}
                session={session}
              />
            </TabsContent>
            
            <TabsContent value="logs">
              <NodeLogsView 
                nodeId={selectedNodeId}
                session={session}
                executionHistory={executionHistory}
              />
            </TabsContent>
          </div>
        </Tabs>
      </Card>
    </div>
  )
}

// Sub-components for different inspection views
function NodeStateView({ nodeState, nodeId }: { nodeState: any, nodeId: string }) {
  if (!nodeState) {
    return (
      <div className="text-center py-8">
        <Database className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        <p className="text-gray-500">No state information available</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h4 className="font-medium text-gray-900">Current State</h4>
      <JSONViewer data={nodeState} />
    </div>
  )
}

function NodeResultView({ result, nodeId, status }: { result: any, nodeId: string, status: string }) {
  if (status === 'waiting') {
    return (
      <div className="text-center py-8">
        <Clock className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        <p className="text-gray-500">Node hasn't executed yet</p>
      </div>
    )
  }

  if (status === 'running') {
    return (
      <div className="text-center py-8">
        <Activity className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
        <p className="text-blue-600">Node is currently executing...</p>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="text-center py-8">
        <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto mb-2" />
        <p className="text-amber-600">No result data available</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h4 className="font-medium text-gray-900">Execution Result</h4>
      <JSONViewer data={result} />
    </div>
  )
}

function NodePerformanceView({ nodeData, nodeId, session }: { 
  nodeData: any, 
  nodeId: string, 
  session: OrchestrationSession 
}) {
  const performanceMetrics = {
    executionTime: nodeData?.latency || 0,
    memoryUsage: nodeData?.memoryUsage || 'N/A',
    cacheHit: session.result?.cache_hits?.[nodeId] || false,
    apiCalls: nodeData?.apiCalls || 0,
    dataSize: nodeData?.dataSize || 'N/A'
  }

  return (
    <div className="space-y-4">
      <h4 className="font-medium text-gray-900">Performance Metrics</h4>
      
      <div className="grid grid-cols-2 gap-4">
        <div className="p-3 bg-gray-50 rounded-lg">
          <div className="text-sm text-gray-600">Execution Time</div>
          <div className="text-lg font-semibold text-gray-900">
            {performanceMetrics.executionTime}ms
          </div>
        </div>
        
        <div className="p-3 bg-gray-50 rounded-lg">
          <div className="text-sm text-gray-600">Cache Status</div>
          <div className="text-lg font-semibold">
            {performanceMetrics.cacheHit ? (
              <span className="text-green-600">Hit</span>
            ) : (
              <span className="text-red-600">Miss</span>
            )}
          </div>
        </div>
        
        <div className="p-3 bg-gray-50 rounded-lg">
          <div className="text-sm text-gray-600">API Calls</div>
          <div className="text-lg font-semibold text-gray-900">
            {performanceMetrics.apiCalls}
          </div>
        </div>
        
        <div className="p-3 bg-gray-50 rounded-lg">
          <div className="text-sm text-gray-600">Data Size</div>
          <div className="text-lg font-semibold text-gray-900">
            {performanceMetrics.dataSize}
          </div>
        </div>
      </div>
    </div>
  )
}

function NodeLogsView({ nodeId, session, executionHistory }: { 
  nodeId: string, 
  session: OrchestrationSession,
  executionHistory: any[]
}) {
  const nodeLogs = executionHistory.filter(log => log.node === nodeId)

  if (nodeLogs.length === 0) {
    return (
      <div className="text-center py-8">
        <Code className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        <p className="text-gray-500">No logs available for this node</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h4 className="font-medium text-gray-900">Execution Logs</h4>
      
      <div className="bg-gray-900 rounded-lg p-4 max-h-64 overflow-y-auto">
        <div className="text-green-400 font-mono text-sm space-y-1">
          {nodeLogs.map((log, index) => (
            <div key={index} className="flex items-start space-x-2">
              <span className="text-gray-500 text-xs">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className={`${
                log.level === 'error' ? 'text-red-400' :
                log.level === 'warn' ? 'text-yellow-400' :
                'text-green-400'
              }`}>
                {log.message}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
```

### 2. Performance Monitoring Dashboard

**File**: `src/components/PerformanceMonitor/PerformanceDashboard.tsx`
```tsx
import React, { useMemo } from 'react'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Progress } from '../ui/Progress'
import { 
  Clock, 
  Zap, 
  Database, 
  Activity,
  TrendingUp,
  TrendingDown,
  Minus
} from 'lucide-react'
import { PerformanceChart } from './PerformanceChart'
import type { OrchestrationSession } from '../../types/orchestrator'

interface PerformanceDashboardProps {
  session: OrchestrationSession
  historicalSessions?: OrchestrationSession[]
}

export function PerformanceDashboard({ session, historicalSessions = [] }: PerformanceDashboardProps) {
  const performanceMetrics = useMemo(() => {
    const result = session.result
    if (!result) return null

    const totalLatency = Object.values(result.latencies || {}).reduce((sum, time) => sum + time, 0)
    const nodeCount = result.node_path?.length || 0
    const averageNodeTime = nodeCount > 0 ? totalLatency / nodeCount : 0
    const cacheHitCount = Object.values(result.cache_hits || {}).filter(hit => hit).length
    const cacheHitRate = nodeCount > 0 ? (cacheHitCount / nodeCount) * 100 : 0
    const toolCallCount = result.tool_calls_made?.length || 0
    const errorCount = result.errors?.length || 0

    return {
      totalLatency,
      averageNodeTime,
      nodeCount,
      cacheHitRate,
      toolCallCount,
      errorCount,
      successRate: nodeCount > 0 ? ((nodeCount - errorCount) / nodeCount) * 100 : 100
    }
  }, [session.result])

  const benchmarkComparison = useMemo(() => {
    if (!performanceMetrics || historicalSessions.length === 0) return null

    const historical = historicalSessions
      .filter(s => s.status === 'completed')
      .map(s => {
        const latencies = Object.values(s.result?.latencies || {})
        return latencies.reduce((sum, time) => sum + time, 0)
      })

    if (historical.length === 0) return null

    const avgHistorical = historical.reduce((sum, time) => sum + time, 0) / historical.length
    const improvement = ((avgHistorical - performanceMetrics.totalLatency) / avgHistorical) * 100

    return {
      avgHistorical,
      currentLatency: performanceMetrics.totalLatency,
      improvement,
      trend: improvement > 5 ? 'better' : improvement < -5 ? 'worse' : 'similar'
    }
  }, [performanceMetrics, historicalSessions])

  if (!performanceMetrics) {
    return (
      <Card className="p-6 text-center">
        <Activity className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        <p className="text-gray-500">No performance data available</p>
      </Card>
    )
  }

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'better':
        return <TrendingUp className="w-4 h-4 text-green-600" />
      case 'worse':
        return <TrendingDown className="w-4 h-4 text-red-600" />
      default:
        return <Minus className="w-4 h-4 text-gray-400" />
    }
  }

  const getTrendColor = (trend: string) => {
    switch (trend) {
      case 'better':
        return 'text-green-600'
      case 'worse':
        return 'text-red-600'
      default:
        return 'text-gray-600'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Performance Dashboard</h2>
        <Badge variant="secondary">{session.status}</Badge>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Time</p>
              <p className="text-2xl font-semibold text-gray-900">
                {Math.round(performanceMetrics.totalLatency)}ms
              </p>
            </div>
            <Clock className="w-8 h-8 text-blue-500" />
          </div>
          {benchmarkComparison && (
            <div className="mt-2 flex items-center text-sm">
              {getTrendIcon(benchmarkComparison.trend)}
              <span className={`ml-1 ${getTrendColor(benchmarkComparison.trend)}`}>
                {Math.abs(Math.round(benchmarkComparison.improvement))}% vs avg
              </span>
            </div>
          )}
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Avg Node Time</p>
              <p className="text-2xl font-semibold text-gray-900">
                {Math.round(performanceMetrics.averageNodeTime)}ms
              </p>
            </div>
            <Zap className="w-8 h-8 text-yellow-500" />
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Cache Hit Rate</p>
              <p className="text-2xl font-semibold text-gray-900">
                {Math.round(performanceMetrics.cacheHitRate)}%
              </p>
            </div>
            <Database className="w-8 h-8 text-green-500" />
          </div>
          <div className="mt-2">
            <Progress value={performanceMetrics.cacheHitRate} className="h-2" />
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Success Rate</p>
              <p className="text-2xl font-semibold text-gray-900">
                {Math.round(performanceMetrics.successRate)}%
              </p>
            </div>
            <Activity className="w-8 h-8 text-purple-500" />
          </div>
        </Card>
      </div>

      {/* Performance Timeline Chart */}
      <Card className="p-6">
        <h3 className="font-semibold text-gray-900 mb-4">Execution Timeline</h3>
        <PerformanceChart 
          session={session}
          historicalSessions={historicalSessions.slice(-10)} // Last 10 sessions
        />
      </Card>

      {/* Detailed Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Node Performance Breakdown */}
        <Card className="p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Node Performance</h3>
          <div className="space-y-3">
            {session.result?.node_path?.map((nodeName: string) => {
              const latency = session.result?.latencies?.[nodeName] || 0
              const percentage = (latency / performanceMetrics.totalLatency) * 100
              const cacheHit = session.result?.cache_hits?.[nodeName]
              
              return (
                <div key={nodeName} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-medium text-gray-900">{nodeName}</span>
                      {cacheHit && <Badge variant="secondary" className="text-xs">Cached</Badge>}
                    </div>
                    <span className="text-sm text-gray-600">{latency}ms</span>
                  </div>
                  <Progress value={percentage} className="h-2" />
                </div>
              )
            })}
          </div>
        </Card>

        {/* Resource Utilization */}
        <Card className="p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Resource Utilization</h3>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">API Calls</span>
                <span className="font-medium">{performanceMetrics.toolCallCount}</span>
              </div>
              <div className="text-xs text-gray-500">
                Tools: {session.result?.tool_calls_made?.join(', ') || 'None'}
              </div>
            </div>
            
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Cache Efficiency</span>
                <span className="font-medium">{Math.round(performanceMetrics.cacheHitRate)}%</span>
              </div>
              <Progress value={performanceMetrics.cacheHitRate} className="h-2" />
            </div>
            
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Error Rate</span>
                <span className="font-medium">{Math.round(100 - performanceMetrics.successRate)}%</span>
              </div>
              <Progress 
                value={100 - performanceMetrics.successRate} 
                className="h-2"
                // Custom color for error rate
                style={{ '--progress-background': '#ef4444' } as React.CSSProperties}
              />
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
```

### 3. Session History Manager

**File**: `src/components/SessionManager/SessionHistoryManager.tsx`
```tsx
import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Input } from '../ui/Input'
import { 
  History, 
  Search, 
  Filter, 
  Trash2, 
  RefreshCw,
  Play,
  Clock,
  CheckCircle,
  XCircle,
  Eye
} from 'lucide-react'
import { orchestratorApi } from '../../utils/api'
import { formatDistance } from 'date-fns'
import type { OrchestrationSession } from '../../types/orchestrator'

interface SessionHistoryManagerProps {
  onSelectSession: (session: OrchestrationSession) => void
  onCompareSession: (session: OrchestrationSession) => void
  currentSessionId?: string
}

export function SessionHistoryManager({ 
  onSelectSession, 
  onCompareSession, 
  currentSessionId 
}: SessionHistoryManagerProps) {
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [page, setPage] = useState(0)
  const pageSize = 20

  const queryClient = useQueryClient()

  const { 
    data: sessionsData, 
    isLoading, 
    error,
    refetch 
  } = useQuery({
    queryKey: ['orchestrator-sessions', page, pageSize],
    queryFn: () => orchestratorApi.getSessions({ limit: pageSize, offset: page * pageSize }),
    keepPreviousData: true,
    staleTime: 30 * 1000, // 30 seconds
  })

  const deleteSessionMutation = useMutation({
    mutationFn: orchestratorApi.deleteSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orchestrator-sessions'] })
    },
    onError: (error) => {
      console.error('Failed to delete session:', error)
    }
  })

  const filteredSessions = React.useMemo(() => {
    if (!sessionsData?.sessions) return []

    return sessionsData.sessions.filter(session => {
      const matchesSearch = searchTerm === '' || 
        session.query.toLowerCase().includes(searchTerm.toLowerCase()) ||
        session.session_name?.toLowerCase().includes(searchTerm.toLowerCase())
      
      const matchesStatus = statusFilter === 'all' || session.status === statusFilter
      
      return matchesSearch && matchesStatus
    })
  }, [sessionsData?.sessions, searchTerm, statusFilter])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'running':
        return <Play className="w-4 h-4 text-blue-600" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-600" />
      default:
        return <Clock className="w-4 h-4 text-gray-400" />
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="success">Completed</Badge>
      case 'running':
        return <Badge variant="default">Running</Badge>
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    
    if (window.confirm('Are you sure you want to delete this session?')) {
      deleteSessionMutation.mutate(sessionId)
    }
  }

  const getPerformanceSummary = (session: OrchestrationSession) => {
    if (!session.result?.latencies) return null
    
    const totalTime = Object.values(session.result.latencies).reduce((sum, time) => sum + time, 0)
    const toolCount = session.result.tool_calls_made?.length || 0
    
    return { totalTime, toolCount }
  }

  if (error) {
    return (
      <Card className="p-6 text-center">
        <XCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
        <p className="text-red-600 mb-4">Failed to load sessions</p>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Retry
        </Button>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
          <History className="w-5 h-5" />
          Session History
        </h2>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Search and Filter Controls */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Search sessions by query or name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        
        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="all">All Status</option>
            <option value="completed">Completed</option>
            <option value="running">Running</option>
            <option value="failed">Failed</option>
            <option value="queued">Queued</option>
          </select>
        </div>
      </div>

      {/* Sessions List */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="text-center py-8">
            <RefreshCw className="w-8 h-8 text-gray-400 animate-spin mx-auto mb-2" />
            <p className="text-gray-500">Loading sessions...</p>
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="text-center py-8">
            <History className="w-8 h-8 text-gray-400 mx-auto mb-2" />
            <p className="text-gray-500">
              {searchTerm || statusFilter !== 'all' ? 'No sessions match your filters' : 'No sessions found'}
            </p>
          </div>
        ) : (
          filteredSessions.map((session) => {
            const performance = getPerformanceSummary(session)
            const isCurrentSession = session.session_id === currentSessionId
            
            return (
              <Card 
                key={session.session_id} 
                className={`p-4 cursor-pointer hover:shadow-md transition-shadow ${
                  isCurrentSession ? 'ring-2 ring-blue-500 ring-opacity-50' : ''
                }`}
                onClick={() => onSelectSession(session)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-3 mb-2">
                      {getStatusIcon(session.status)}
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-gray-900 truncate">
                          {session.session_name || `Session ${session.session_id.slice(0, 8)}`}
                        </h3>
                        <p className="text-sm text-gray-600 truncate">
                          {session.query}
                        </p>
                      </div>
                      {getStatusBadge(session.status)}
                    </div>
                    
                    <div className="flex items-center space-x-4 text-xs text-gray-500">
                      <span>
                        {formatDistance(new Date(session.created_at), new Date(), { addSuffix: true })}
                      </span>
                      
                      {performance && (
                        <>
                          <span>{Math.round(performance.totalTime)}ms</span>
                          <span>{performance.toolCount} tools</span>
                        </>
                      )}
                      
                      {session.debug_mode && (
                        <Badge variant="secondary" className="text-xs">Debug</Badge>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2 ml-4">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        onSelectSession(session)
                      }}
                      title="View details"
                    >
                      <Eye className="w-4 h-4" />
                    </Button>
                    
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        onCompareSession(session)
                      }}
                      title="Compare session"
                    >
                      <History className="w-4 h-4" />
                    </Button>
                    
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => handleDeleteSession(session.session_id, e)}
                      disabled={deleteSessionMutation.isPending}
                      title="Delete session"
                      className="text-red-600 hover:text-red-700"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </Card>
            )
          })
        )}
      </div>

      {/* Pagination */}
      {sessionsData && sessionsData.total > pageSize && (
        <div className="flex justify-between items-center">
          <p className="text-sm text-gray-600">
            Showing {page * pageSize + 1} to {Math.min((page + 1) * pageSize, sessionsData.total)} of {sessionsData.total} sessions
          </p>
          
          <div className="flex space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => p + 1)}
              disabled={(page + 1) * pageSize >= sessionsData.total}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
```

### 4. Enhanced Graph Visualization

**File**: `src/components/GraphView/AdvancedGraphVisualization.tsx`
```tsx
import React, { useCallback, useState } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  ConnectionMode,
  Panel,
  ReactFlowProvider,
  addEdge,
  Connection,
  NodeChange,
  EdgeChange
} from 'react-flow-renderer'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Switch } from '../ui/Switch'
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize, 
  Settings, 
  Play,
  Pause,
  RotateCcw,
  Layers,
  Eye,
  EyeOff
} from 'lucide-react'
import { AdvancedNodeRenderer } from './AdvancedNodeRenderer'
import { PerformanceOverlay } from './PerformanceOverlay'
import type { OrchestrationSession } from '../../types/orchestrator'

interface AdvancedGraphVisualizationProps {
  session?: OrchestrationSession
  graphData: any
  onNodeSelect: (nodeId: string | null) => void
  selectedNodeId: string | null
}

const nodeTypes = {
  advanced_node: AdvancedNodeRenderer,
}

export function AdvancedGraphVisualization({
  session,
  graphData,
  onNodeSelect,
  selectedNodeId
}: AdvancedGraphVisualizationProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  
  // Visualization settings
  const [showPerformanceOverlay, setShowPerformanceOverlay] = useState(true)
  const [showMiniMap, setShowMiniMap] = useState(true)
  const [animateExecution, setAnimateExecution] = useState(true)
  const [layoutDirection, setLayoutDirection] = useState<'horizontal' | 'vertical'>('horizontal')
  const [nodeSpacing, setNodeSpacing] = useState(200)

  // Layout algorithms
  const applyLayout = useCallback((direction: 'horizontal' | 'vertical', spacing: number) => {
    if (!graphData?.nodes) return

    const layoutNodes = graphData.nodes.map((node: any, index: number) => {
      const position = direction === 'horizontal'
        ? { x: index * spacing, y: 100 }
        : { x: 100, y: index * spacing }

      return {
        id: node.id,
        type: 'advanced_node',
        position,
        data: {
          ...node.data,
          label: node.label,
          status: getNodeStatus(node.id),
          performance: getNodePerformance(node.id),
          isSelected: selectedNodeId === node.id,
          onSelect: () => onNodeSelect(node.id),
        },
      }
    })

    const layoutEdges = graphData.edges.map((edge: any) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: 'smoothstep',
      animated: animateExecution && isEdgeActive(edge),
      style: {
        stroke: getEdgeColor(edge),
        strokeWidth: isEdgeActive(edge) ? 2 : 1,
      },
    }))

    setNodes(layoutNodes)
    setEdges(layoutEdges)
  }, [graphData, selectedNodeId, onNodeSelect, animateExecution])

  // Apply layout when settings change
  React.useEffect(() => {
    applyLayout(layoutDirection, nodeSpacing)
  }, [applyLayout, layoutDirection, nodeSpacing])

  const getNodeStatus = (nodeId: string): string => {
    if (!session?.result) return 'waiting'
    
    const { currentNode, nodePath, isComplete } = session.result
    
    if (currentNode === nodeId) return 'running'
    if (nodePath?.includes(nodeId)) return 'completed'
    if (isComplete) return 'waiting'
    
    return 'waiting'
  }

  const getNodePerformance = (nodeId: string) => {
    if (!session?.result) return null
    
    return {
      latency: session.result.latencies?.[nodeId],
      cacheHit: session.result.cache_hits?.[nodeId],
      result: session.result.nodeResults?.[nodeId],
    }
  }

  const isEdgeActive = (edge: any): boolean => {
    if (!session?.result) return false
    
    const { currentNode, nodePath } = session.result
    const sourceCompleted = nodePath?.includes(edge.source)
    const targetIsCurrent = currentNode === edge.target
    
    return sourceCompleted && targetIsCurrent
  }

  const getEdgeColor = (edge: any): string => {
    if (isEdgeActive(edge)) return '#3B82F6'
    if (session?.result?.nodePath?.includes(edge.target)) return '#10B981'
    return '#9CA3AF'
  }

  const handleNodesChange = useCallback((changes: NodeChange[]) => {
    // Allow position and selection changes
    onNodesChange(changes)
  }, [onNodesChange])

  const handleEdgesChange = useCallback((changes: EdgeChange[]) => {
    onEdgesChange(changes)
  }, [onEdgesChange])

  const handleNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    onNodeSelect(node.id)
  }, [onNodeSelect])

  const handlePaneClick = useCallback(() => {
    onNodeSelect(null)
  }, [onNodeSelect])

  const fitView = () => {
    // This would use ReactFlow's fitView function
    console.log('Fit view')
  }

  const resetZoom = () => {
    // This would reset zoom to 100%
    console.log('Reset zoom')
  }

  return (
    <div className="relative h-96 w-full border border-gray-200 rounded-lg overflow-hidden">
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onNodeClick={handleNodeClick}
          onPaneClick={handlePaneClick}
          nodeTypes={nodeTypes}
          connectionMode={ConnectionMode.Strict}
          fitView
          fitViewOptions={{ padding: 0.2 }}
        >
          <Controls position="bottom-right" />
          <Background color="#f8fafc" gap={20} />
          
          {showMiniMap && (
            <MiniMap
              position="bottom-left"
              nodeColor={(node) => {
                switch (node.data?.status) {
                  case 'completed': return '#10B981'
                  case 'running': return '#3B82F6'
                  case 'failed': return '#EF4444'
                  default: return '#9CA3AF'
                }
              }}
              maskColor="rgba(255,255,255,0.2)"
            />
          )}

          {/* Custom Controls Panel */}
          <Panel position="top-right" className="space-y-2">
            <Card className="p-3 space-y-3">
              <div className="text-sm font-medium text-gray-900">View Options</div>
              
              <div className="flex items-center justify-between">
                <label className="text-xs text-gray-600">Performance</label>
                <Switch
                  checked={showPerformanceOverlay}
                  onCheckedChange={setShowPerformanceOverlay}
                  size="sm"
                />
              </div>
              
              <div className="flex items-center justify-between">
                <label className="text-xs text-gray-600">Mini Map</label>
                <Switch
                  checked={showMiniMap}
                  onCheckedChange={setShowMiniMap}
                  size="sm"
                />
              </div>
              
              <div className="flex items-center justify-between">
                <label className="text-xs text-gray-600">Animation</label>
                <Switch
                  checked={animateExecution}
                  onCheckedChange={setAnimateExecution}
                  size="sm"
                />
              </div>

              <div className="pt-2 border-t border-gray-200">
                <div className="text-xs text-gray-600 mb-2">Layout</div>
                <select
                  value={layoutDirection}
                  onChange={(e) => setLayoutDirection(e.target.value as 'horizontal' | 'vertical')}
                  className="w-full text-xs px-2 py-1 border border-gray-300 rounded"
                >
                  <option value="horizontal">Horizontal</option>
                  <option value="vertical">Vertical</option>
                </select>
              </div>

              <div className="flex space-x-1">
                <Button variant="outline" size="sm" onClick={fitView}>
                  <Maximize className="w-3 h-3" />
                </Button>
                <Button variant="outline" size="sm" onClick={resetZoom}>
                  <RotateCcw className="w-3 h-3" />
                </Button>
              </div>
            </Card>
          </Panel>

          {/* Performance Overlay */}
          {showPerformanceOverlay && session && (
            <PerformanceOverlay session={session} />
          )}
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  )
}
```

### 5. Debug Control Panel

**File**: `src/components/DebugMode/DebugControlPanel.tsx`
```tsx
import React, { useState } from 'react'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { Switch } from '../ui/Switch'
import { 
  Bug, 
  Play, 
  Pause, 
  Square, 
  StepForward,
  RotateCcw,
  Settings,
  Activity,
  AlertTriangle,
  CheckCircle
} from 'lucide-react'
import { useWebSocketDebug } from '../../hooks/useWebSocketDebug'
import type { OrchestrationSession } from '../../types/orchestrator'

interface DebugControlPanelProps {
  session: OrchestrationSession
  graphNodes: any[]
  selectedNodeId: string | null
}

export function DebugControlPanel({ session, graphNodes, selectedNodeId }: DebugControlPanelProps) {
  const [autoStepEnabled, setAutoStepEnabled] = useState(false)
  const [stepInterval, setStepInterval] = useState(1000) // 1 second
  const [showAllBreakpoints, setShowAllBreakpoints] = useState(false)

  const {
    debugState,
    isConnected,
    connectionError,
    setBreakpoint,
    stepExecution,
    inspectNodeState,
    resumeExecution
  } = useWebSocketDebug(session.session_id, session.debug_mode)

  const isPaused = debugState?.isPaused || false
  const currentBreakpoint = debugState?.currentBreakpoint
  const breakpoints = debugState?.breakpoints || {}

  const getConnectionStatus = () => {
    if (connectionError) return 'error'
    if (isConnected) return 'connected'
    return 'disconnected'
  }

  const getStatusBadge = () => {
    switch (getConnectionStatus()) {
      case 'connected':
        return <Badge variant="success">Connected</Badge>
      case 'error':
        return <Badge variant="destructive">Error</Badge>
      default:
        return <Badge variant="secondary">Disconnected</Badge>
    }
  }

  const handleToggleBreakpoint = (nodeId: string) => {
    const isEnabled = breakpoints[nodeId] || false
    setBreakpoint(nodeId, !isEnabled)
  }

  const handleStepExecution = () => {
    if (selectedNodeId) {
      stepExecution(selectedNodeId)
    } else if (currentBreakpoint) {
      stepExecution(currentBreakpoint)
    }
  }

  const handleResumeExecution = () => {
    resumeExecution()
  }

  const clearAllBreakpoints = () => {
    Object.keys(breakpoints).forEach(nodeId => {
      if (breakpoints[nodeId]) {
        setBreakpoint(nodeId, false)
      }
    })
  }

  if (!session.debug_mode) {
    return (
      <Card className="p-6 text-center">
        <Bug className="w-8 h-8 text-gray-400 mx-auto mb-2" />
        <p className="text-gray-500">Debug mode is not enabled for this session</p>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Bug className="w-5 h-5 text-blue-600" />
            <h3 className="font-semibold text-gray-900">Debug Controls</h3>
          </div>
          {getStatusBadge()}
        </div>

        {connectionError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-red-600" />
              <span className="text-sm text-red-700">Debug connection error: {connectionError}</span>
            </div>
          </div>
        )}

        {/* Execution Controls */}
        <div className="space-y-3">
          <div className="flex items-center space-x-2">
            <Button
              variant={isPaused ? "default" : "outline"}
              size="sm"
              onClick={handleResumeExecution}
              disabled={!isConnected || !isPaused}
            >
              <Play className="w-4 h-4 mr-1" />
              Resume
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleStepExecution}
              disabled={!isConnected || (!isPaused && !selectedNodeId)}
            >
              <StepForward className="w-4 h-4 mr-1" />
              Step
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {/* Handle stop */}}
              disabled={!isConnected}
            >
              <Square className="w-4 h-4 mr-1" />
              Stop
            </Button>
          </div>

          {/* Current Status */}
          {isPaused && currentBreakpoint && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md">
              <div className="flex items-center space-x-2">
                <Pause className="w-4 h-4 text-yellow-600" />
                <span className="text-sm text-yellow-800">
                  Paused at breakpoint: <code className="font-mono text-xs">{currentBreakpoint}</code>
                </span>
              </div>
            </div>
          )}

          {debugState?.currentNode && !isPaused && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
              <div className="flex items-center space-x-2">
                <Activity className="w-4 h-4 text-blue-600 animate-pulse" />
                <span className="text-sm text-blue-800">
                  Currently executing: <code className="font-mono text-xs">{debugState.currentNode}</code>
                </span>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Breakpoints Management */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-gray-900">Breakpoints</h4>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={clearAllBreakpoints}
              disabled={!isConnected || Object.keys(breakpoints).length === 0}
            >
              Clear All
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowAllBreakpoints(!showAllBreakpoints)}
            >
              <Settings className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <div className="space-y-2">
          {showAllBreakpoints ? (
            // Show all nodes with breakpoint toggles
            graphNodes.map((node) => (
              <div key={node.id} className="flex items-center justify-between py-2 px-3 rounded bg-gray-50">
                <div className="flex items-center space-x-2">
                  <code className="text-xs font-mono text-gray-700">{node.id}</code>
                  {breakpoints[node.id] && (
                    <Badge variant="secondary" className="text-xs">Active</Badge>
                  )}
                </div>
                <Switch
                  checked={breakpoints[node.id] || false}
                  onCheckedChange={() => handleToggleBreakpoint(node.id)}
                  disabled={!isConnected}
                  size="sm"
                />
              </div>
            ))
          ) : (
            // Show only active breakpoints
            Object.entries(breakpoints)
              .filter(([_, enabled]) => enabled)
              .map(([nodeId, _]) => (
                <div key={nodeId} className="flex items-center justify-between py-2 px-3 rounded bg-red-50 border border-red-200">
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                    <code className="text-xs font-mono text-gray-900">{nodeId}</code>
                    {currentBreakpoint === nodeId && (
                      <Badge variant="warning" className="text-xs">Current</Badge>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleToggleBreakpoint(nodeId)}
                    disabled={!isConnected}
                  >
                    <RotateCcw className="w-3 h-3" />
                  </Button>
                </div>
              ))
          )}

          {Object.keys(breakpoints).length === 0 && (
            <div className="text-center py-4">
              <p className="text-sm text-gray-500">No breakpoints set</p>
            </div>
          )}
        </div>
      </Card>

      {/* Auto-stepping Options */}
      <Card className="p-4">
        <h4 className="font-medium text-gray-900 mb-3">Auto-stepping</h4>
        
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm text-gray-600">Enable auto-step</label>
            <Switch
              checked={autoStepEnabled}
              onCheckedChange={setAutoStepEnabled}
              disabled={!isConnected}
            />
          </div>

          {autoStepEnabled && (
            <div>
              <label className="block text-sm text-gray-600 mb-1">Step interval (ms)</label>
              <input
                type="range"
                min="500"
                max="5000"
                step="100"
                value={stepInterval}
                onChange={(e) => setStepInterval(Number(e.target.value))}
                className="w-full"
                disabled={!isConnected}
              />
              <div className="text-xs text-gray-500 text-center mt-1">
                {stepInterval}ms
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Debug Information */}
      {process.env.NODE_ENV === 'development' && debugState && (
        <Card className="p-4">
          <h4 className="font-medium text-gray-900 mb-3">Debug State</h4>
          <pre className="text-xs text-gray-600 bg-gray-50 p-3 rounded overflow-x-auto">
            {JSON.stringify(debugState, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  )
}
```

## Testing Requirements

### 1. Visualization Component Tests

**File**: `src/__tests__/components/NodeInspector.test.tsx`
```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { NodeInspector } from '../../components/NodeInspector/NodeInspector'

const mockSession = {
  session_id: 'test-session',
  debug_mode: true,
  status: 'running'
}

describe('NodeInspector', () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })

  const renderNodeInspector = (props = {}) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <NodeInspector
          session={mockSession}
          selectedNodeId="test-node"
          onClose={jest.fn()}
          {...props}
        />
      </QueryClientProvider>
    )
  }

  test('renders node inspector with selected node', () => {
    renderNodeInspector()
    expect(screen.getByText('Node Inspector')).toBeInTheDocument()
    expect(screen.getByText('test-node')).toBeInTheDocument()
  })

  test('shows debug controls when in debug mode', () => {
    renderNodeInspector()
    expect(screen.getByText('Set Breakpoint')).toBeInTheDocument()
    expect(screen.getByText('Refresh')).toBeInTheDocument()
  })

  test('displays different tabs for inspection', () => {
    renderNodeInspector()
    expect(screen.getByText('State')).toBeInTheDocument()
    expect(screen.getByText('Result')).toBeInTheDocument()
    expect(screen.getByText('Performance')).toBeInTheDocument()
    expect(screen.getByText('Logs')).toBeInTheDocument()
  })
})
```

### 2. Performance Monitor Tests

**File**: `src/__tests__/components/PerformanceDashboard.test.tsx`
```tsx
import { render, screen } from '@testing-library/react'
import { PerformanceDashboard } from '../../components/PerformanceMonitor/PerformanceDashboard'

const mockSession = {
  session_id: 'test-session',
  status: 'completed',
  result: {
    latencies: { node1: 100, node2: 200 },
    cache_hits: { node1: true, node2: false },
    node_path: ['node1', 'node2'],
    tool_calls_made: ['pubmed.search', 'rag.search'],
    errors: []
  }
}

describe('PerformanceDashboard', () => {
  test('displays key performance metrics', () => {
    render(<PerformanceDashboard session={mockSession} />)
    
    expect(screen.getByText('Performance Dashboard')).toBeInTheDocument()
    expect(screen.getByText('300ms')).toBeInTheDocument() // Total time
    expect(screen.getByText('50%')).toBeInTheDocument() // Cache hit rate
  })

  test('shows node performance breakdown', () => {
    render(<PerformanceDashboard session={mockSession} />)
    
    expect(screen.getByText('Node Performance')).toBeInTheDocument()
    expect(screen.getByText('node1')).toBeInTheDocument()
    expect(screen.getByText('node2')).toBeInTheDocument()
  })

  test('displays resource utilization', () => {
    render(<PerformanceDashboard session={mockSession} />)
    
    expect(screen.getByText('Resource Utilization')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument() // API calls count
  })
})
```

## Acceptance Criteria
- [ ] Advanced node inspector with state, result, performance, and logs tabs
- [ ] Performance dashboard with metrics, charts, and benchmarking
- [ ] Session history manager with search, filtering, and comparison
- [ ] Enhanced graph visualization with layout options and animations
- [ ] Debug control panel with breakpoints and step-through execution
- [ ] Real-time WebSocket debug communication working
- [ ] Node selection and inspection integrated with graph
- [ ] Performance monitoring and historical comparison
- [ ] Session replay and comparison functionality
- [ ] Comprehensive test coverage for all visualization components

## Files Created/Modified
- `src/components/NodeInspector/NodeInspector.tsx` - Advanced node inspection interface
- `src/components/PerformanceMonitor/PerformanceDashboard.tsx` - Performance metrics and monitoring
- `src/components/SessionManager/SessionHistoryManager.tsx` - Session management and history
- `src/components/GraphView/AdvancedGraphVisualization.tsx` - Enhanced graph visualization
- `src/components/DebugMode/DebugControlPanel.tsx` - Debug controls and breakpoint management
- Supporting components and utilities
- Comprehensive test suites for all new components

## Dependencies Required
No additional dependencies beyond M3 requirements. Enhanced use of existing libraries:
- `react-flow-renderer` for advanced graph features
- `date-fns` for date formatting in session history
- Native browser APIs for debugging features

## Next Steps
After completion, proceed to **M5 — Polish & Deployment** which will focus on final optimization, comprehensive testing, documentation, and deployment preparation.
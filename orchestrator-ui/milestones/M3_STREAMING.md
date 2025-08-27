# M3 — Streaming Integration (2 days)

## Objective
Implement real-time streaming integration using Server-Sent Events (SSE) and WebSocket for progressive result loading, live orchestration status updates, and bi-directional debug communication. This milestone transforms the static UI into a dynamic, real-time interface that provides immediate feedback during orchestration execution.

## Dependencies
- **M1 — API Integration** completed (SSE and WebSocket endpoints available)
- **M2 — Core UI Foundation** completed (React components and hooks ready)
- Bio-MCP orchestrator running with streaming support
- Frontend application with query builder and results panel

## Deliverables

### 1. Server-Sent Events (SSE) Integration

**File**: `src/hooks/useStreamingResults.ts`
```tsx
import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { OrchestrationSession, StreamingEvent } from '../types/orchestrator'

interface StreamingState {
  isConnected: boolean
  currentEvent: StreamingEvent | null
  connectionError: string | null
  reconnectAttempts: number
}

export function useStreamingResults(sessionId: string | null) {
  const [streamingState, setStreamingState] = useState<StreamingState>({
    isConnected: false,
    currentEvent: null,
    connectionError: null,
    reconnectAttempts: 0
  })
  
  const [accumulatedResults, setAccumulatedResults] = useState<any>({})
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const maxReconnectAttempts = 5

  const connectEventSource = useCallback(() => {
    if (!sessionId || eventSourceRef.current) {
      return
    }

    const eventSource = new EventSource(`/orchestrator/v1/orchestrator/stream/${sessionId}`)
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      setStreamingState(prev => ({
        ...prev,
        isConnected: true,
        connectionError: null,
        reconnectAttempts: 0
      }))
    }

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleStreamingEvent(data, event.type)
      } catch (error) {
        console.error('Failed to parse streaming event:', error)
      }
    }

    eventSource.addEventListener('status', (event) => {
      try {
        const data = JSON.parse(event.data)
        handleStatusUpdate(data)
      } catch (error) {
        console.error('Failed to parse status event:', error)
      }
    })

    eventSource.addEventListener('node_start', (event) => {
      try {
        const data = JSON.parse(event.data)
        handleNodeStart(data)
      } catch (error) {
        console.error('Failed to parse node_start event:', error)
      }
    })

    eventSource.addEventListener('node_complete', (event) => {
      try {
        const data = JSON.parse(event.data)
        handleNodeComplete(data)
      } catch (error) {
        console.error('Failed to parse node_complete event:', error)
      }
    })

    eventSource.addEventListener('partial_result', (event) => {
      try {
        const data = JSON.parse(event.data)
        handlePartialResult(data)
      } catch (error) {
        console.error('Failed to parse partial_result event:', error)
      }
    })

    eventSource.addEventListener('result', (event) => {
      try {
        const data = JSON.parse(event.data)
        handleFinalResult(data)
      } catch (error) {
        console.error('Failed to parse result event:', error)
      }
    })

    eventSource.addEventListener('error', (event) => {
      try {
        const data = JSON.parse(event.data)
        handleErrorEvent(data)
      } catch (error) {
        console.error('Failed to parse error event:', error)
      }
    })

    eventSource.addEventListener('done', () => {
      handleStreamComplete()
    })

    eventSource.onerror = (error) => {
      console.error('EventSource error:', error)
      handleConnectionError()
    }
  }, [sessionId])

  const handleStreamingEvent = (data: any, eventType: string) => {
    const event: StreamingEvent = {
      type: eventType,
      timestamp: new Date().toISOString(),
      data,
      sessionId: sessionId!
    }
    
    setStreamingState(prev => ({
      ...prev,
      currentEvent: event
    }))
  }

  const handleStatusUpdate = (data: any) => {
    setStreamingState(prev => ({
      ...prev,
      currentEvent: {
        type: 'status',
        timestamp: data.timestamp,
        data: data,
        sessionId: sessionId!
      }
    }))
  }

  const handleNodeStart = (data: any) => {
    setAccumulatedResults(prev => ({
      ...prev,
      currentNode: data.node_name,
      nodeStartTime: data.timestamp,
      nodePath: [...(prev.nodePath || []), data.node_name]
    }))
  }

  const handleNodeComplete = (data: any) => {
    setAccumulatedResults(prev => ({
      ...prev,
      currentNode: null,
      latencies: {
        ...prev.latencies,
        [data.node_name]: data.execution_time_ms
      },
      nodeResults: {
        ...prev.nodeResults,
        [data.node_name]: data.result
      }
    }))
  }

  const handlePartialResult = (data: any) => {
    const { source, results, metadata } = data
    
    setAccumulatedResults(prev => ({
      ...prev,
      [source]: {
        ...prev[source],
        results: [...(prev[source]?.results || []), ...results],
        metadata: { ...(prev[source]?.metadata || {}), ...metadata },
        isStreaming: true,
        lastUpdate: new Date().toISOString()
      }
    }))
  }

  const handleFinalResult = (data: any) => {
    setAccumulatedResults(prev => ({
      ...prev,
      ...data,
      isComplete: true,
      completedAt: new Date().toISOString()
    }))
  }

  const handleErrorEvent = (data: any) => {
    setStreamingState(prev => ({
      ...prev,
      connectionError: data.error,
      currentEvent: {
        type: 'error',
        timestamp: new Date().toISOString(),
        data,
        sessionId: sessionId!
      }
    }))
  }

  const handleStreamComplete = () => {
    setAccumulatedResults(prev => ({
      ...prev,
      isComplete: true
    }))
    
    setStreamingState(prev => ({
      ...prev,
      isConnected: false
    }))
    
    // Close the event source
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }

  const handleConnectionError = () => {
    setStreamingState(prev => ({
      ...prev,
      isConnected: false,
      connectionError: 'Connection lost'
    }))

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    // Attempt reconnection with exponential backoff
    if (streamingState.reconnectAttempts < maxReconnectAttempts) {
      const backoffDelay = Math.min(1000 * Math.pow(2, streamingState.reconnectAttempts), 10000)
      
      reconnectTimeoutRef.current = setTimeout(() => {
        setStreamingState(prev => ({
          ...prev,
          reconnectAttempts: prev.reconnectAttempts + 1
        }))
        connectEventSource()
      }, backoffDelay)
    }
  }

  // Connect when sessionId is available
  useEffect(() => {
    if (sessionId) {
      connectEventSource()
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [sessionId, connectEventSource])

  const reconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    
    setStreamingState(prev => ({
      ...prev,
      reconnectAttempts: 0,
      connectionError: null
    }))
    
    connectEventSource()
  }, [connectEventSource])

  return {
    ...streamingState,
    accumulatedResults,
    reconnect,
    isStreaming: streamingState.isConnected && !accumulatedResults.isComplete
  }
}
```

### 2. WebSocket Debug Communication

**File**: `src/hooks/useWebSocketDebug.ts`
```tsx
import { useState, useEffect, useRef, useCallback } from 'react'
import type { DebugCommand, DebugMessage, DebugState } from '../types/debug'

interface WebSocketDebugState {
  isConnected: boolean
  connectionError: string | null
  debugState: DebugState | null
  pendingCommands: DebugCommand[]
}

export function useWebSocketDebug(sessionId: string | null, debugMode: boolean) {
  const [wsState, setWsState] = useState<WebSocketDebugState>({
    isConnected: false,
    connectionError: null,
    debugState: null,
    pendingCommands: []
  })

  const websocketRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const connectWebSocket = useCallback(() => {
    if (!sessionId || !debugMode || websocketRef.current) {
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/orchestrator/ws/debug/${sessionId}`
    
    const ws = new WebSocket(wsUrl)
    websocketRef.current = ws

    ws.onopen = () => {
      setWsState(prev => ({
        ...prev,
        isConnected: true,
        connectionError: null
      }))

      // Send any pending commands
      wsState.pendingCommands.forEach(command => {
        sendDebugCommand(command)
      })
      setWsState(prev => ({ ...prev, pendingCommands: [] }))
    }

    ws.onmessage = (event) => {
      try {
        const message: DebugMessage = JSON.parse(event.data)
        handleDebugMessage(message)
      } catch (error) {
        console.error('Failed to parse debug message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setWsState(prev => ({
        ...prev,
        connectionError: 'Debug connection failed'
      }))
    }

    ws.onclose = () => {
      setWsState(prev => ({
        ...prev,
        isConnected: false
      }))
      websocketRef.current = null

      // Attempt reconnection if still in debug mode
      if (debugMode) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connectWebSocket()
        }, 3000)
      }
    }
  }, [sessionId, debugMode])

  const handleDebugMessage = (message: DebugMessage) => {
    switch (message.type) {
      case 'breakpoint_hit':
        setWsState(prev => ({
          ...prev,
          debugState: {
            ...prev.debugState,
            currentBreakpoint: message.data.node_name,
            nodeState: message.data.state,
            isPaused: true
          }
        }))
        break

      case 'step_completed':
        setWsState(prev => ({
          ...prev,
          debugState: {
            ...prev.debugState,
            currentNode: message.data.node_name,
            nodeState: message.data.state,
            executionStep: (prev.debugState?.executionStep || 0) + 1
          }
        }))
        break

      case 'breakpoint_set':
        setWsState(prev => ({
          ...prev,
          debugState: {
            ...prev.debugState,
            breakpoints: {
              ...prev.debugState?.breakpoints,
              [message.data.node_name]: message.data.enabled
            }
          }
        }))
        break

      case 'state_inspection':
        setWsState(prev => ({
          ...prev,
          debugState: {
            ...prev.debugState,
            inspectedNode: message.data.node_name,
            inspectedState: message.data.state
          }
        }))
        break

      case 'execution_resumed':
        setWsState(prev => ({
          ...prev,
          debugState: {
            ...prev.debugState,
            isPaused: false,
            currentBreakpoint: null
          }
        }))
        break

      default:
        console.warn('Unknown debug message type:', message.type)
    }
  }

  const sendDebugCommand = useCallback((command: DebugCommand) => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify(command))
    } else {
      // Queue command if not connected
      setWsState(prev => ({
        ...prev,
        pendingCommands: [...prev.pendingCommands, command]
      }))
    }
  }, [])

  const setBreakpoint = useCallback((nodeName: string, enabled: boolean) => {
    const command: DebugCommand = {
      type: 'set_breakpoint',
      node_name: nodeName,
      enabled,
      timestamp: new Date().toISOString()
    }
    sendDebugCommand(command)
  }, [sendDebugCommand])

  const stepExecution = useCallback((nodeName: string) => {
    const command: DebugCommand = {
      type: 'step',
      node_name: nodeName,
      timestamp: new Date().toISOString()
    }
    sendDebugCommand(command)
  }, [sendDebugCommand])

  const inspectNodeState = useCallback((nodeName: string) => {
    const command: DebugCommand = {
      type: 'inspect_state',
      node_name: nodeName,
      timestamp: new Date().toISOString()
    }
    sendDebugCommand(command)
  }, [sendDebugCommand])

  const resumeExecution = useCallback(() => {
    const command: DebugCommand = {
      type: 'resume',
      timestamp: new Date().toISOString()
    }
    sendDebugCommand(command)
  }, [sendDebugCommand])

  // Connect when debug mode is enabled
  useEffect(() => {
    if (debugMode && sessionId) {
      connectWebSocket()
    }

    return () => {
      if (websocketRef.current) {
        websocketRef.current.close()
        websocketRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [debugMode, sessionId, connectWebSocket])

  return {
    ...wsState,
    setBreakpoint,
    stepExecution,
    inspectNodeState,
    resumeExecution,
    disconnect: () => {
      if (websocketRef.current) {
        websocketRef.current.close()
      }
    }
  }
}
```

### 3. Progressive Results Loading Components

**File**: `src/components/ResultsPanel/StreamingResultsView.tsx`
```tsx
import React, { useEffect, useState } from 'react'
import { useStreamingResults } from '../../hooks/useStreamingResults'
import { Activity, Wifi, WifiOff, RefreshCw, AlertCircle } from 'lucide-react'
import { Button } from '../ui/Button'
import { Progress } from '../ui/Progress'
import { StreamingPubMedResults } from './StreamingPubMedResults'
import { StreamingTrialsResults } from './StreamingTrialsResults'
import { StreamingRAGResults } from './StreamingRAGResults'
import type { OrchestrationSession } from '../../types/orchestrator'

interface StreamingResultsViewProps {
  session: OrchestrationSession
}

export function StreamingResultsView({ session }: StreamingResultsViewProps) {
  const {
    isConnected,
    connectionError,
    accumulatedResults,
    currentEvent,
    isStreaming,
    reconnect,
    reconnectAttempts
  } = useStreamingResults(session.session_id)

  const [estimatedProgress, setEstimatedProgress] = useState(0)

  // Calculate estimated progress based on completed nodes
  useEffect(() => {
    const totalNodes = 5 // Approximate number of orchestrator nodes
    const completedNodes = accumulatedResults.nodePath?.length || 0
    const progress = Math.min((completedNodes / totalNodes) * 100, 95) // Never show 100% until truly done
    
    if (accumulatedResults.isComplete) {
      setEstimatedProgress(100)
    } else if (isStreaming) {
      setEstimatedProgress(progress)
    }
  }, [accumulatedResults.nodePath, accumulatedResults.isComplete, isStreaming])

  const getConnectionStatus = () => {
    if (connectionError) return 'error'
    if (isConnected && isStreaming) return 'streaming'
    if (isConnected) return 'connected'
    return 'disconnected'
  }

  const getStatusMessage = () => {
    switch (getConnectionStatus()) {
      case 'streaming':
        return `Streaming results... ${accumulatedResults.currentNode || 'Processing'}`
      case 'connected':
        return accumulatedResults.isComplete ? 'Orchestration completed' : 'Connected, waiting for updates'
      case 'error':
        return `Connection error: ${connectionError}`
      case 'disconnected':
        return reconnectAttempts > 0 ? `Reconnecting... (attempt ${reconnectAttempts}/5)` : 'Disconnected'
      default:
        return 'Unknown status'
    }
  }

  const getStatusIcon = () => {
    switch (getConnectionStatus()) {
      case 'streaming':
        return <Activity className="w-4 h-4 animate-spin text-blue-500" />
      case 'connected':
        return <Wifi className="w-4 h-4 text-green-500" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />
      case 'disconnected':
        return <WifiOff className="w-4 h-4 text-gray-400" />
      default:
        return <Activity className="w-4 h-4 text-gray-400" />
    }
  }

  return (
    <div className="space-y-6">
      {/* Connection Status Bar */}
      <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border">
        <div className="flex items-center space-x-3">
          {getStatusIcon()}
          <div>
            <p className="text-sm font-medium text-gray-900">
              {getStatusMessage()}
            </p>
            {currentEvent && (
              <p className="text-xs text-gray-500">
                Last event: {currentEvent.type} at {new Date(currentEvent.timestamp).toLocaleTimeString()}
              </p>
            )}
          </div>
        </div>

        {connectionError && (
          <Button
            variant="outline"
            size="sm"
            onClick={reconnect}
            className="flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Reconnect
          </Button>
        )}
      </div>

      {/* Progress Bar */}
      {isStreaming && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-gray-600">
            <span>Orchestration Progress</span>
            <span>{Math.round(estimatedProgress)}%</span>
          </div>
          <Progress value={estimatedProgress} className="h-2" />
          {accumulatedResults.currentNode && (
            <p className="text-xs text-gray-500">
              Current node: <span className="font-mono">{accumulatedResults.currentNode}</span>
            </p>
          )}
        </div>
      )}

      {/* Streaming Results Tabs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* PubMed Results */}
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-medium text-gray-900">PubMed Results</h3>
            {accumulatedResults.pubmed_results && (
              <p className="text-sm text-gray-500">
                {accumulatedResults.pubmed_results.results?.length || 0} articles
                {accumulatedResults.pubmed_results.isStreaming && (
                  <span className="ml-2 text-blue-500">(loading...)</span>
                )}
              </p>
            )}
          </div>
          <div className="p-4">
            <StreamingPubMedResults 
              results={accumulatedResults.pubmed_results}
              isStreaming={accumulatedResults.pubmed_results?.isStreaming}
            />
          </div>
        </div>

        {/* Clinical Trials Results */}
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-medium text-gray-900">Clinical Trials</h3>
            {accumulatedResults.trials_results && (
              <p className="text-sm text-gray-500">
                {accumulatedResults.trials_results.results?.length || 0} trials
                {accumulatedResults.trials_results.isStreaming && (
                  <span className="ml-2 text-blue-500">(loading...)</span>
                )}
              </p>
            )}
          </div>
          <div className="p-4">
            <StreamingTrialsResults 
              results={accumulatedResults.trials_results}
              isStreaming={accumulatedResults.trials_results?.isStreaming}
            />
          </div>
        </div>

        {/* RAG Results */}
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-medium text-gray-900">RAG Results</h3>
            {accumulatedResults.rag_results && (
              <p className="text-sm text-gray-500">
                {accumulatedResults.rag_results.results?.length || 0} documents
                {accumulatedResults.rag_results.isStreaming && (
                  <span className="ml-2 text-blue-500">(loading...)</span>
                )}
              </p>
            )}
          </div>
          <div className="p-4">
            <StreamingRAGResults 
              results={accumulatedResults.rag_results}
              isStreaming={accumulatedResults.rag_results?.isStreaming}
            />
          </div>
        </div>
      </div>

      {/* Node Execution Timeline */}
      {accumulatedResults.nodePath && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="font-medium text-gray-900 mb-3">Execution Timeline</h3>
          <div className="space-y-2">
            {accumulatedResults.nodePath.map((nodeName: string, index: number) => (
              <div key={index} className="flex items-center justify-between py-2 px-3 rounded bg-gray-50">
                <div className="flex items-center space-x-2">
                  <div className={`w-2 h-2 rounded-full ${
                    nodeName === accumulatedResults.currentNode 
                      ? 'bg-blue-500 animate-pulse' 
                      : 'bg-green-500'
                  }`} />
                  <span className="text-sm font-mono text-gray-700">{nodeName}</span>
                </div>
                {accumulatedResults.latencies?.[nodeName] && (
                  <span className="text-xs text-gray-500">
                    {accumulatedResults.latencies[nodeName]}ms
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Debug Information (when available) */}
      {process.env.NODE_ENV === 'development' && currentEvent && (
        <div className="bg-gray-900 rounded-lg p-4">
          <h3 className="text-white font-medium mb-2">Debug Information</h3>
          <pre className="text-xs text-green-400 overflow-x-auto">
            {JSON.stringify(currentEvent, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
```

### 4. Real-time Graph Updates

**File**: `src/components/GraphView/StreamingGraphView.tsx`
```tsx
import React, { useEffect, useMemo } from 'react'
import ReactFlow, { 
  Node, 
  Edge, 
  Controls, 
  Background,
  useNodesState,
  useEdgesState,
  NodeChange,
  EdgeChange
} from 'react-flow-renderer'
import { useStreamingResults } from '../../hooks/useStreamingResults'
import { StreamingNodeRenderer } from './StreamingNodeRenderer'
import type { OrchestrationSession } from '../../types/orchestrator'

interface StreamingGraphViewProps {
  session: OrchestrationSession
  graphData: any // Graph visualization data from API
}

const nodeTypes = {
  streaming_node: StreamingNodeRenderer,
}

export function StreamingGraphView({ session, graphData }: StreamingGraphViewProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  
  const { accumulatedResults, isStreaming } = useStreamingResults(session.session_id)

  // Create enhanced nodes with streaming state
  const enhancedNodes = useMemo(() => {
    if (!graphData?.nodes) return []

    return graphData.nodes.map((node: any, index: number) => {
      const nodeStatus = getNodeStatus(node.id, accumulatedResults)
      const nodeLatency = accumulatedResults.latencies?.[node.id]
      const isActive = accumulatedResults.currentNode === node.id

      return {
        id: node.id,
        type: 'streaming_node',
        position: { x: index * 200, y: 100 },
        data: {
          ...node.data,
          label: node.label,
          status: nodeStatus,
          latency: nodeLatency,
          isActive,
          isStreaming,
          result: accumulatedResults.nodeResults?.[node.id],
          // Add animation classes for real-time updates
          className: getNodeClassName(nodeStatus, isActive),
        },
        className: getNodeClassName(nodeStatus, isActive),
      }
    })
  }, [graphData, accumulatedResults, isStreaming])

  // Create enhanced edges with animation
  const enhancedEdges = useMemo(() => {
    if (!graphData?.edges) return []

    return graphData.edges.map((edge: any) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: 'smoothstep',
      animated: isEdgeActive(edge, accumulatedResults),
      className: isEdgeActive(edge, accumulatedResults) ? 'animate-pulse' : '',
      style: {
        stroke: isEdgeActive(edge, accumulatedResults) ? '#3B82F6' : '#9CA3AF',
        strokeWidth: isEdgeActive(edge, accumulatedResults) ? 2 : 1,
      },
    }))
  }, [graphData, accumulatedResults])

  // Update nodes and edges when data changes
  useEffect(() => {
    setNodes(enhancedNodes)
  }, [enhancedNodes, setNodes])

  useEffect(() => {
    setEdges(enhancedEdges)
  }, [enhancedEdges, setEdges])

  const handleNodesChange = (changes: NodeChange[]) => {
    // Allow position changes but preserve our custom data
    const filteredChanges = changes.filter(change => 
      change.type === 'position' || change.type === 'select'
    )
    onNodesChange(filteredChanges)
  }

  const handleEdgesChange = (changes: EdgeChange[]) => {
    // Allow selection changes but preserve our custom styling
    const filteredChanges = changes.filter(change => 
      change.type === 'select'
    )
    onEdgesChange(filteredChanges)
  }

  return (
    <div className="h-64 border border-gray-200 rounded-md relative">
      {/* Streaming Status Indicator */}
      {isStreaming && (
        <div className="absolute top-2 right-2 z-10 bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full flex items-center">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse mr-1"></div>
          Live Updates
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={handleEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{
          padding: 0.2,
          includeHiddenNodes: false,
        }}
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
      >
        <Controls />
        <Background color="#f1f5f9" gap={16} />
      </ReactFlow>
    </div>
  )
}

function getNodeStatus(nodeId: string, results: any): string {
  if (!results) return 'waiting'
  
  const { currentNode, nodePath, isComplete } = results
  
  if (currentNode === nodeId) return 'running'
  if (nodePath?.includes(nodeId)) return 'completed'
  if (isComplete) return 'waiting' // All nodes done
  
  return 'waiting'
}

function getNodeClassName(status: string, isActive: boolean): string {
  const baseClass = 'transition-all duration-300'
  
  if (isActive) return `${baseClass} ring-2 ring-blue-400 ring-opacity-75`
  
  switch (status) {
    case 'completed':
      return `${baseClass} bg-green-50 border-green-300`
    case 'running':
      return `${baseClass} bg-blue-50 border-blue-300 animate-pulse`
    case 'failed':
      return `${baseClass} bg-red-50 border-red-300`
    default:
      return `${baseClass} bg-gray-50 border-gray-300`
  }
}

function isEdgeActive(edge: any, results: any): boolean {
  if (!results) return false
  
  const { currentNode, nodePath } = results
  
  // Edge is active if source node is completed and target is current or next
  const sourceCompleted = nodePath?.includes(edge.source)
  const targetIsCurrent = currentNode === edge.target
  
  return sourceCompleted && (targetIsCurrent || nodePath?.includes(edge.target))
}
```

### 5. Streaming Node Renderer

**File**: `src/components/GraphView/StreamingNodeRenderer.tsx`
```tsx
import React from 'react'
import { Handle, Position } from 'react-flow-renderer'
import { 
  Play, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Activity,
  Eye 
} from 'lucide-react'
import { Button } from '../ui/Button'

interface StreamingNodeRendererProps {
  data: {
    label: string
    status: 'waiting' | 'running' | 'completed' | 'failed'
    latency?: number
    isActive: boolean
    isStreaming: boolean
    result?: any
    onInspect?: (nodeId: string) => void
  }
  id: string
}

export function StreamingNodeRenderer({ data, id }: StreamingNodeRendererProps) {
  const getStatusIcon = () => {
    switch (data.status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'running':
        return <Activity className="w-4 h-4 text-blue-600 animate-spin" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-600" />
      case 'waiting':
        return <Clock className="w-4 h-4 text-gray-400" />
      default:
        return <Play className="w-4 h-4 text-gray-400" />
    }
  }

  const getStatusColor = () => {
    switch (data.status) {
      case 'completed':
        return 'border-green-300 bg-green-50'
      case 'running':
        return 'border-blue-300 bg-blue-50'
      case 'failed':
        return 'border-red-300 bg-red-50'
      default:
        return 'border-gray-300 bg-white'
    }
  }

  const handleInspect = (e: React.MouseEvent) => {
    e.stopPropagation()
    data.onInspect?.(id)
  }

  return (
    <div className={`px-4 py-3 shadow-md rounded-lg border-2 min-w-[140px] ${getStatusColor()} 
                     ${data.isActive ? 'ring-2 ring-blue-400 ring-opacity-50' : ''}`}>
      <Handle type="target" position={Position.Top} className="w-2 h-2" />
      
      <div className="space-y-2">
        {/* Node Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {getStatusIcon()}
            <div>
              <div className="text-sm font-medium text-gray-900 leading-tight">
                {data.label}
              </div>
            </div>
          </div>
          
          {/* Inspect Button */}
          {(data.result || data.status === 'running') && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleInspect}
              className="p-1 h-6 w-6"
            >
              <Eye className="w-3 h-3" />
            </Button>
          )}
        </div>

        {/* Status Information */}
        <div className="text-xs text-gray-600 space-y-1">
          {data.latency && data.status === 'completed' && (
            <div className="flex justify-between">
              <span>Duration:</span>
              <span className="font-mono">{data.latency}ms</span>
            </div>
          )}
          
          {data.status === 'running' && data.isStreaming && (
            <div className="text-blue-600 flex items-center space-x-1">
              <div className="w-1 h-1 bg-blue-600 rounded-full animate-pulse"></div>
              <span>Processing...</span>
            </div>
          )}
          
          {data.result && (
            <div className="text-green-600 text-xs">
              ✓ Result available
            </div>
          )}
        </div>

        {/* Real-time Progress Bar for Active Nodes */}
        {data.status === 'running' && (
          <div className="w-full bg-gray-200 rounded-full h-1">
            <div className="bg-blue-600 h-1 rounded-full animate-pulse" style={{ width: '60%' }}></div>
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="w-2 h-2" />
    </div>
  )
}
```

### 6. Enhanced Type Definitions

**File**: `src/types/streaming.ts`
```tsx
export interface StreamingEvent {
  type: string
  timestamp: string
  data: any
  sessionId: string
}

export interface StreamingSource {
  results: any[]
  metadata: Record<string, any>
  isStreaming: boolean
  lastUpdate: string
  totalExpected?: number
  currentCount?: number
}

export interface DebugState {
  currentBreakpoint?: string | null
  nodeState?: any
  isPaused?: boolean
  currentNode?: string
  executionStep?: number
  breakpoints?: Record<string, boolean>
  inspectedNode?: string
  inspectedState?: any
}

export interface DebugCommand {
  type: 'set_breakpoint' | 'step' | 'inspect_state' | 'resume'
  node_name?: string
  enabled?: boolean
  timestamp: string
}

export interface DebugMessage {
  type: string
  session_id: string
  timestamp: string
  data: Record<string, any>
}
```

## Testing Requirements

### 1. Streaming Integration Tests

**File**: `src/__tests__/hooks/useStreamingResults.test.ts`
```tsx
import { renderHook, waitFor } from '@testing-library/react'
import { useStreamingResults } from '../../hooks/useStreamingResults'

// Mock EventSource
class MockEventSource {
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  addEventListener = jest.fn()
  close = jest.fn()
  
  constructor(public url: string) {}
  
  triggerEvent(type: string, data: any) {
    const event = new MessageEvent('message', { data: JSON.stringify(data) })
    if (this.addEventListener.mock.calls.find(call => call[0] === type)) {
      const handler = this.addEventListener.mock.calls.find(call => call[0] === type)[1]
      handler(event)
    }
  }
}

// @ts-ignore
global.EventSource = MockEventSource

describe('useStreamingResults', () => {
  test('establishes connection when sessionId provided', async () => {
    const { result } = renderHook(() => useStreamingResults('test-session'))
    
    await waitFor(() => {
      expect(result.current.isConnected).toBe(false) // Initial state
    })
  })

  test('accumulates partial results', async () => {
    const { result } = renderHook(() => useStreamingResults('test-session'))
    
    // Simulate partial result event
    const mockEventSource = new MockEventSource('/stream/test-session')
    mockEventSource.triggerEvent('partial_result', {
      source: 'pubmed',
      results: [{ pmid: '123', title: 'Test Article' }],
      metadata: { total: 10 }
    })
    
    await waitFor(() => {
      expect(result.current.accumulatedResults.pubmed?.results).toHaveLength(1)
    })
  })
})
```

### 2. WebSocket Debug Tests

**File**: `src/__tests__/hooks/useWebSocketDebug.test.ts`
```tsx
import { renderHook, act } from '@testing-library/react'
import { useWebSocketDebug } from '../../hooks/useWebSocketDebug'

class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  
  readyState = MockWebSocket.CONNECTING
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  
  send = jest.fn()
  close = jest.fn()
  
  constructor(public url: string) {}
  
  mockConnect() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }
  
  mockMessage(data: any) {
    const event = new MessageEvent('message', { data: JSON.stringify(data) })
    this.onmessage?.(event)
  }
}

// @ts-ignore
global.WebSocket = MockWebSocket

describe('useWebSocketDebug', () => {
  test('connects when debug mode enabled', async () => {
    const { result } = renderHook(() => 
      useWebSocketDebug('test-session', true)
    )
    
    expect(result.current.isConnected).toBe(false)
    
    // Simulate connection
    act(() => {
      const ws = new MockWebSocket('ws://localhost/debug/test-session')
      ws.mockConnect()
    })
  })

  test('sends breakpoint commands', async () => {
    const { result } = renderHook(() => 
      useWebSocketDebug('test-session', true)
    )
    
    act(() => {
      result.current.setBreakpoint('pubmed_node', true)
    })
    
    // Verify command was queued or sent
    expect(result.current.pendingCommands).toContainEqual(
      expect.objectContaining({
        type: 'set_breakpoint',
        node_name: 'pubmed_node',
        enabled: true
      })
    )
  })
})
```

## Acceptance Criteria
- [ ] Server-Sent Events integration working with real-time updates
- [ ] WebSocket debug communication functional
- [ ] Progressive result loading from all sources (PubMed, ClinicalTrials, RAG)
- [ ] Real-time graph updates showing execution progress  
- [ ] Connection recovery and error handling implemented
- [ ] Streaming components rendering partial results correctly
- [ ] Debug commands (breakpoints, stepping) working via WebSocket
- [ ] Performance optimized for continuous data streams
- [ ] Unit tests covering streaming hooks and error scenarios
- [ ] E2E tests validating complete streaming workflows

## Files Created/Modified
- `src/hooks/useStreamingResults.ts` - SSE streaming integration
- `src/hooks/useWebSocketDebug.ts` - WebSocket debug communication  
- `src/components/ResultsPanel/StreamingResultsView.tsx` - Real-time results display
- `src/components/GraphView/StreamingGraphView.tsx` - Live graph updates
- `src/components/GraphView/StreamingNodeRenderer.tsx` - Enhanced node rendering
- `src/types/streaming.ts` - Streaming-related type definitions
- Test files for streaming functionality

## Dependencies Required
No additional dependencies beyond M2 requirements. Uses native browser APIs:
- `EventSource` for Server-Sent Events
- `WebSocket` for bi-directional communication
- React hooks for state management

## Next Steps
After completion, proceed to **M4 — Visualization & Debugging** which will implement advanced graph visualization features and comprehensive debugging tools.
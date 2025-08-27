# M2 — Core UI Foundation (3 days)

## Objective
Build the React application foundation with TypeScript, essential components, and responsive layout. This milestone creates the core user interface for the orchestrator with query building, result display, and basic graph visualization capabilities.

## Dependencies
- **M1 — API Integration** completed (orchestrator API endpoints available)
- Node.js 18+ and npm/yarn for frontend development
- Bio-MCP server running with orchestrator endpoints accessible

## Deliverables

### 1. React Application Setup

**Directory Structure:**
```
src/bio_mcp/http/static/orchestrator/
├── package.json                    # Project configuration
├── tsconfig.json                   # TypeScript configuration
├── vite.config.ts                  # Vite build configuration
├── tailwind.config.js              # Tailwind CSS configuration
├── index.html                      # Main HTML entry point
├── src/
│   ├── main.tsx                    # Application entry point
│   ├── App.tsx                     # Root application component
│   ├── components/                 # Reusable UI components
│   │   ├── ui/                     # Base UI components
│   │   ├── QueryBuilder/           # Query construction interface
│   │   ├── ResultsPanel/           # Results display components
│   │   └── GraphView/              # Graph visualization container
│   ├── hooks/                      # Custom React hooks
│   ├── types/                      # TypeScript type definitions
│   ├── utils/                      # Utility functions
│   └── styles/                     # Global styles and CSS
├── public/                         # Static assets
└── tests/                          # Frontend test files
```

**File**: `package.json`
```json
{
  "name": "bio-mcp-orchestrator-ui",
  "version": "1.0.0",
  "type": "module",
  "description": "Bio-MCP Orchestrator Testing Interface",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@tanstack/react-query": "^4.35.0",
    "react-hook-form": "^7.45.0",
    "react-flow-renderer": "^10.3.17",
    "lucide-react": "^0.263.0",
    "date-fns": "^2.30.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^1.14.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.15",
    "@types/react-dom": "^18.2.7",
    "@typescript-eslint/eslint-plugin": "^6.0.0",
    "@typescript-eslint/parser": "^6.0.0",
    "@vitejs/plugin-react": "^4.0.3",
    "autoprefixer": "^10.4.14",
    "eslint": "^8.45.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.3",
    "postcss": "^8.4.27",
    "tailwindcss": "^3.3.0",
    "typescript": "^5.0.2",
    "vite": "^4.4.5",
    "vitest": "^0.34.0",
    "@testing-library/react": "^13.4.0",
    "@testing-library/jest-dom": "^6.1.0",
    "@playwright/test": "^1.36.0"
  }
}
```

**File**: `src/main.tsx`
```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import App from './App'
import './styles/globals.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 2,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </React.StrictMode>,
)
```

### 2. Core Application Structure

**File**: `src/App.tsx`
```tsx
import React, { useState } from 'react'
import { QueryBuilder } from './components/QueryBuilder/QueryBuilder'
import { ResultsPanel } from './components/ResultsPanel/ResultsPanel'
import { GraphView } from './components/GraphView/GraphView'
import { Header } from './components/ui/Header'
import { StatusBar } from './components/ui/StatusBar'
import { useOrchestrator } from './hooks/useOrchestrator'
import type { OrchestrationRequest, OrchestrationSession } from './types/orchestrator'

function App() {
  const [currentSession, setCurrentSession] = useState<OrchestrationSession | null>(null)
  const { executeQuery, isLoading, error } = useOrchestrator()

  const handleQuerySubmit = async (request: OrchestrationRequest) => {
    try {
      const session = await executeQuery(request)
      setCurrentSession(session)
    } catch (err) {
      console.error('Query execution failed:', err)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <StatusBar 
        isConnected={true}
        currentSession={currentSession}
      />
      
      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Query Builder Panel */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <QueryBuilder 
              onSubmit={handleQuerySubmit}
              isLoading={isLoading}
              error={error}
            />
          </div>

          {/* Graph Visualization Panel */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <GraphView 
              session={currentSession}
            />
          </div>
        </div>

        {/* Results Panel */}
        {currentSession && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <ResultsPanel session={currentSession} />
          </div>
        )}
      </main>
    </div>
  )
}

export default App
```

### 3. Query Builder Component

**File**: `src/components/QueryBuilder/QueryBuilder.tsx`
```tsx
import React, { useState, useEffect } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { Search, Settings, Play, Loader2 } from 'lucide-react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Textarea } from '../ui/Textarea'
import { Select } from '../ui/Select'
import { Switch } from '../ui/Switch'
import { EntityExtractor } from './EntityExtractor'
import { FilterPanel } from './FilterPanel'
import type { OrchestrationRequest } from '../../types/orchestrator'

interface QueryBuilderProps {
  onSubmit: (request: OrchestrationRequest) => void
  isLoading?: boolean
  error?: Error | null
}

export function QueryBuilder({ onSubmit, isLoading, error }: QueryBuilderProps) {
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [extractedEntities, setExtractedEntities] = useState({})
  
  const { control, handleSubmit, watch, setValue, reset } = useForm<OrchestrationRequest>({
    defaultValues: {
      query: '',
      config: {},
      debug_mode: false,
      session_name: ''
    }
  })

  const watchedQuery = watch('query')

  useEffect(() => {
    // Extract entities when query changes
    if (watchedQuery && watchedQuery.length > 10) {
      extractEntities(watchedQuery)
    }
  }, [watchedQuery])

  const extractEntities = async (query: string) => {
    // Simple entity extraction logic - in production, this could call an NLP API
    const entities: any = {}
    
    // Look for common biomedical patterns
    if (/diabetes|diabetic/i.test(query)) {
      entities.indication = 'diabetes'
    }
    if (/cancer|tumor|oncology/i.test(query)) {
      entities.indication = 'cancer'
    }
    if (/GLP-1|glucagon/i.test(query)) {
      entities.topic = 'GLP-1'
    }
    if (/phase\s*(1|2|3|I{1,3})/i.test(query)) {
      const match = query.match(/phase\s*(1|2|3|I{1,3})/i)
      entities.phase = match?.[1]
    }
    
    setExtractedEntities(entities)
  }

  const handleFormSubmit = (data: OrchestrationRequest) => {
    // Enhance request with extracted entities
    const enhancedRequest = {
      ...data,
      config: {
        ...data.config,
        extracted_entities: extractedEntities
      }
    }
    onSubmit(enhancedRequest)
  }

  const loadExampleQuery = (example: string) => {
    setValue('query', example)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
          <Search className="w-5 h-5" />
          Query Builder
        </h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          <Settings className="w-4 h-4" />
          {showAdvanced ? 'Simple' : 'Advanced'}
        </Button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-sm text-red-700">
            Error: {error.message}
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
        {/* Main Query Input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Natural Language Query
          </label>
          <Controller
            name="query"
            control={control}
            rules={{ required: 'Query is required', minLength: 3 }}
            render={({ field, fieldState }) => (
              <div>
                <Textarea
                  {...field}
                  placeholder="e.g., 'Latest clinical trials for GLP-1 receptor agonists in diabetes treatment'"
                  className="min-h-[100px]"
                  error={fieldState.error?.message}
                />
                {fieldState.error && (
                  <p className="mt-1 text-sm text-red-600">{fieldState.error.message}</p>
                )}
              </div>
            )}
          />
        </div>

        {/* Example Queries */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {[
            "GLP-1 receptor agonist trials for diabetes",
            "Phase 3 oncology trials with FDA breakthrough designation",
            "Recent publications on CRISPR gene therapy",
            "Clinical trials for Alzheimer's disease treatments"
          ].map((example, index) => (
            <Button
              key={index}
              variant="outline"
              size="sm"
              type="button"
              onClick={() => loadExampleQuery(example)}
              className="text-xs text-left justify-start h-auto p-2"
            >
              {example}
            </Button>
          ))}
        </div>

        {/* Entity Extraction Display */}
        {Object.keys(extractedEntities).length > 0 && (
          <EntityExtractor entities={extractedEntities} />
        )}

        {showAdvanced && (
          <div className="space-y-4 border-t border-gray-200 pt-4">
            {/* Session Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Session Name (Optional)
              </label>
              <Controller
                name="session_name"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    placeholder="e.g., 'GLP-1 Analysis Session'"
                  />
                )}
              />
            </div>

            {/* Debug Mode */}
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-gray-700">
                  Debug Mode
                </label>
                <p className="text-xs text-gray-500">
                  Enable step-by-step execution with breakpoints
                </p>
              </div>
              <Controller
                name="debug_mode"
                control={control}
                render={({ field }) => (
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                )}
              />
            </div>

            {/* Advanced Configuration */}
            <FilterPanel control={control} />
          </div>
        )}

        {/* Submit Button */}
        <div className="flex justify-between items-center pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => reset()}
            disabled={isLoading}
          >
            Clear
          </Button>
          
          <Button
            type="submit"
            disabled={isLoading}
            className="flex items-center gap-2"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {isLoading ? 'Executing...' : 'Execute Orchestration'}
          </Button>
        </div>
      </form>
    </div>
  )
}
```

### 4. Results Panel Component

**File**: `src/components/ResultsPanel/ResultsPanel.tsx`
```tsx
import React, { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/Tabs'
import { PubMedResults } from './PubMedResults'
import { ClinicalTrialsResults } from './ClinicalTrialsResults'
import { RAGResults } from './RAGResults'
import { SynthesisView } from './SynthesisView'
import { SessionInfo } from './SessionInfo'
import { FileText, TestTube, Database, Sparkles, Info } from 'lucide-react'
import type { OrchestrationSession } from '../../types/orchestrator'

interface ResultsPanelProps {
  session: OrchestrationSession
}

export function ResultsPanel({ session }: ResultsPanelProps) {
  const [activeTab, setActiveTab] = useState('synthesis')

  const getResultCount = (resultType: string) => {
    const results = session.result?.[resultType]
    if (!results) return 0
    return Array.isArray(results) ? results.length : results.total_results || 0
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900">
          Orchestration Results
        </h2>
        <SessionInfo session={session} />
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="synthesis" className="flex items-center gap-2">
            <Sparkles className="w-4 h-4" />
            Synthesis
          </TabsTrigger>
          <TabsTrigger value="pubmed" className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            PubMed ({getResultCount('pubmed_results')})
          </TabsTrigger>
          <TabsTrigger value="trials" className="flex items-center gap-2">
            <TestTube className="w-4 h-4" />
            Trials ({getResultCount('trials_results')})
          </TabsTrigger>
          <TabsTrigger value="rag" className="flex items-center gap-2">
            <Database className="w-4 h-4" />
            RAG ({getResultCount('rag_results')})
          </TabsTrigger>
          <TabsTrigger value="info" className="flex items-center gap-2">
            <Info className="w-4 h-4" />
            Session
          </TabsTrigger>
        </TabsList>

        <div className="mt-6">
          <TabsContent value="synthesis">
            <SynthesisView session={session} />
          </TabsContent>
          
          <TabsContent value="pubmed">
            <PubMedResults 
              results={session.result?.pubmed_results} 
              isLoading={session.status === 'running'}
            />
          </TabsContent>
          
          <TabsContent value="trials">
            <ClinicalTrialsResults 
              results={session.result?.trials_results}
              isLoading={session.status === 'running'}
            />
          </TabsContent>
          
          <TabsContent value="rag">
            <RAGResults 
              results={session.result?.rag_results}
              isLoading={session.status === 'running'}
            />
          </TabsContent>
          
          <TabsContent value="info">
            <SessionInfo session={session} detailed={true} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  )
}
```

### 5. Graph View Component

**File**: `src/components/GraphView/GraphView.tsx`
```tsx
import React, { useEffect, useState } from 'react'
import ReactFlow, { 
  Node, 
  Edge, 
  Controls, 
  Background,
  ReactFlowProvider,
  useNodesState,
  useEdgesState
} from 'react-flow-renderer'
import { useQuery } from '@tanstack/react-query'
import { Activity, Play, CheckCircle, XCircle, Clock } from 'lucide-react'
import { orchestratorApi } from '../../utils/api'
import type { OrchestrationSession } from '../../types/orchestrator'

interface GraphViewProps {
  session?: OrchestrationSession | null
}

const nodeTypes = {
  orchestrator_node: OrchestratorNode,
}

function OrchestratorNode({ data }: { data: any }) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'running':
        return <Play className="w-4 h-4 text-blue-500 animate-pulse" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />
      case 'waiting':
        return <Clock className="w-4 h-4 text-gray-400" />
      default:
        return <Activity className="w-4 h-4 text-gray-400" />
    }
  }

  return (
    <div className={`px-4 py-2 shadow-md rounded-md border-2 ${
      data.status === 'completed' ? 'border-green-300 bg-green-50' :
      data.status === 'running' ? 'border-blue-300 bg-blue-50' :
      data.status === 'failed' ? 'border-red-300 bg-red-50' :
      'border-gray-300 bg-white'
    }`}>
      <div className="flex items-center gap-2">
        {getStatusIcon(data.status)}
        <div>
          <div className="text-sm font-medium text-gray-900">
            {data.label}
          </div>
          {data.timing && (
            <div className="text-xs text-gray-500">
              {data.timing}ms
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function GraphView({ session }: GraphViewProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  // Fetch graph visualization data
  const { data: graphData, isLoading } = useQuery({
    queryKey: ['graph-visualization'],
    queryFn: () => orchestratorApi.getGraphVisualization(),
    staleTime: 10 * 60 * 1000, // 10 minutes - graph structure rarely changes
  })

  useEffect(() => {
    if (graphData) {
      // Convert API data to ReactFlow format
      const flowNodes: Node[] = graphData.nodes.map((node, index) => ({
        id: node.id,
        type: 'orchestrator_node',
        position: { x: index * 200, y: 100 },
        data: {
          ...node.data,
          label: node.label,
          status: getNodeStatus(node.id, session),
          timing: getNodeTiming(node.id, session),
        },
      }))

      const flowEdges: Edge[] = graphData.edges.map(edge => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: 'smoothstep',
        animated: isNodeActive(edge.source, session),
      }))

      setNodes(flowNodes)
      setEdges(flowEdges)
    }
  }, [graphData, session, setNodes, setEdges])

  const getNodeStatus = (nodeId: string, session?: OrchestrationSession | null): string => {
    if (!session || !session.result) return 'waiting'
    
    const nodePath = session.result.node_path || []
    const currentNode = session.result.current_node
    
    if (currentNode === nodeId) return 'running'
    if (nodePath.includes(nodeId)) return 'completed'
    if (session.status === 'failed' && nodePath.includes(nodeId)) return 'failed'
    
    return 'waiting'
  }

  const getNodeTiming = (nodeId: string, session?: OrchestrationSession | null): number | undefined => {
    if (!session?.result?.latencies) return undefined
    return session.result.latencies[nodeId]
  }

  const isNodeActive = (nodeId: string, session?: OrchestrationSession | null): boolean => {
    return session?.result?.current_node === nodeId
  }

  if (isLoading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-8 h-8 animate-spin mx-auto mb-2 text-gray-400" />
          <p className="text-sm text-gray-500">Loading graph...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
        <Activity className="w-5 h-5" />
        Orchestration Flow
      </h3>
      
      <div className="h-64 border border-gray-200 rounded-md">
        <ReactFlowProvider>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="top-right"
          >
            <Controls />
            <Background color="#aaa" gap={16} />
          </ReactFlow>
        </ReactFlowProvider>
      </div>

      {session && (
        <div className="text-sm text-gray-600 space-y-1">
          <p>Status: <span className="font-medium">{session.status}</span></p>
          {session.result?.node_path && (
            <p>Path: <span className="font-mono text-xs">
              {session.result.node_path.join(' → ')}
            </span></p>
          )}
        </div>
      )}
    </div>
  )
}
```

### 6. Base UI Components

**File**: `src/components/ui/Button.tsx`
```tsx
import React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../utils/cn'

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}
```

### 7. Custom Hooks

**File**: `src/hooks/useOrchestrator.ts`
```tsx
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { orchestratorApi } from '../utils/api'
import type { OrchestrationRequest, OrchestrationSession } from '../types/orchestrator'

export function useOrchestrator() {
  const [currentSession, setCurrentSession] = useState<OrchestrationSession | null>(null)

  const mutation = useMutation({
    mutationFn: orchestratorApi.executeQuery,
    onSuccess: (session) => {
      setCurrentSession(session)
    },
    onError: (error) => {
      console.error('Orchestration failed:', error)
    }
  })

  const executeQuery = async (request: OrchestrationRequest) => {
    const session = await mutation.mutateAsync(request)
    return session
  }

  return {
    executeQuery,
    currentSession,
    setCurrentSession,
    isLoading: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset
  }
}
```

### 8. Type Definitions

**File**: `src/types/orchestrator.ts`
```tsx
export interface OrchestrationRequest {
  query: string
  config: Record<string, any>
  debug_mode: boolean
  session_name?: string
}

export interface OrchestrationSession {
  session_id: string
  query: string
  config: Record<string, any>
  debug_mode: boolean
  session_name?: string
  status: 'created' | 'queued' | 'running' | 'completed' | 'failed'
  created_at: string
  started_at?: string
  completed_at?: string
  error?: string
  result?: OrchestrationResult
}

export interface OrchestrationResult {
  query: string
  answer?: string
  checkpoint_id?: string
  node_path: string[]
  current_node?: string
  tool_calls_made: string[]
  cache_hits: Record<string, boolean>
  latencies: Record<string, number>
  errors: any[]
  messages: any[]
  pubmed_results?: any
  trials_results?: any
  rag_results?: any
}

export interface GraphVisualizationData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  layout: Record<string, any>
  metadata: Record<string, any>
}

export interface GraphNode {
  id: string
  type: string
  label: string
  position: { x: number; y: number }
  data: Record<string, any>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
}
```

## Testing Requirements

### 1. Component Tests

**File**: `src/components/__tests__/QueryBuilder.test.tsx`
```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { QueryBuilder } from '../QueryBuilder/QueryBuilder'

describe('QueryBuilder', () => {
  const mockOnSubmit = jest.fn()
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  })

  const renderQueryBuilder = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <QueryBuilder onSubmit={mockOnSubmit} />
      </QueryClientProvider>
    )
  }

  test('renders query input field', () => {
    renderQueryBuilder()
    expect(screen.getByPlaceholderText(/Latest clinical trials/)).toBeInTheDocument()
  })

  test('submits query on form submission', async () => {
    renderQueryBuilder()
    
    const input = screen.getByPlaceholderText(/Latest clinical trials/)
    const submitBtn = screen.getByText('Execute Orchestration')
    
    fireEvent.change(input, { target: { value: 'diabetes research' } })
    fireEvent.click(submitBtn)
    
    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ query: 'diabetes research' })
      )
    })
  })

  test('shows entity extraction for biomedical queries', async () => {
    renderQueryBuilder()
    
    const input = screen.getByPlaceholderText(/Latest clinical trials/)
    fireEvent.change(input, { target: { value: 'GLP-1 diabetes phase 3 trials' } })
    
    await waitFor(() => {
      expect(screen.getByText('Extracted Entities')).toBeInTheDocument()
    })
  })
})
```

### 2. Integration Tests

**File**: `tests/e2e/orchestrator.spec.ts`
```typescript
import { test, expect } from '@playwright/test'

test.describe('Orchestrator UI', () => {
  test('complete query execution flow', async ({ page }) => {
    await page.goto('/orchestrator/')
    
    // Fill query
    await page.fill('textarea[placeholder*="clinical trials"]', 'diabetes GLP-1 trials')
    
    // Submit query
    await page.click('button:has-text("Execute Orchestration")')
    
    // Wait for results
    await expect(page.locator('.results-panel')).toBeVisible({ timeout: 10000 })
    
    // Check tabs are present
    await expect(page.locator('tab:has-text("PubMed")')).toBeVisible()
    await expect(page.locator('tab:has-text("Trials")')).toBeVisible()
    await expect(page.locator('tab:has-text("RAG")')).toBeVisible()
  })

  test('graph visualization displays correctly', async ({ page }) => {
    await page.goto('/orchestrator/')
    
    // Graph should be visible initially
    await expect(page.locator('.react-flow')).toBeVisible()
    
    // Nodes should be present
    await expect(page.locator('[data-testid="rf__node"]')).toHaveCount.greaterThan(0)
  })

  test('debug mode enables advanced controls', async ({ page }) => {
    await page.goto('/orchestrator/')
    
    // Enable advanced mode
    await page.click('button:has-text("Advanced")')
    
    // Enable debug mode
    await page.click('[data-testid="debug-mode-switch"]')
    
    // Debug controls should appear
    await expect(page.locator('[data-testid="debug-controls"]')).toBeVisible()
  })
})
```

## Acceptance Criteria
- [ ] React application with TypeScript configured and running
- [ ] Query builder interface with entity extraction working
- [ ] Results panel with tabbed interface for all sources
- [ ] Basic graph visualization using ReactFlow
- [ ] Responsive layout supporting desktop and tablet
- [ ] Form validation and error handling implemented  
- [ ] Custom hooks for orchestrator API integration
- [ ] Base UI component library created
- [ ] Component tests passing with good coverage
- [ ] E2E tests validating critical user flows

## Files Created
- Frontend application in `src/bio_mcp/http/static/orchestrator/`
- Core React components and hooks
- TypeScript type definitions
- Base UI component library  
- Test files for components and E2E flows
- Vite configuration and build setup

## Dependencies Required
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0", 
    "@tanstack/react-query": "^4.35.0",
    "react-hook-form": "^7.45.0",
    "react-flow-renderer": "^10.3.17",
    "lucide-react": "^0.263.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.3",
    "typescript": "^5.0.2",
    "tailwindcss": "^3.3.0",
    "@testing-library/react": "^13.4.0",
    "@playwright/test": "^1.36.0"
  }
}
```

## Next Steps
After completion, proceed to **M3 — Streaming Integration** which will implement real-time streaming updates and progressive result loading.
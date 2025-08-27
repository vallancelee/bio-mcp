# Bio-MCP Orchestrator UI - Component Specification

## Overview

This document defines the complete component architecture for the Bio-MCP Orchestrator UI React application. It includes component hierarchy, props interfaces, state management patterns, and interaction flows.

## Architecture Principles

### Component Design Philosophy
- **Single Responsibility**: Each component has one clear purpose
- **Composition over Inheritance**: Build complex UIs from simple, reusable components
- **Props Down, Events Up**: Data flows down through props, events bubble up
- **Separation of Concerns**: UI components separate from business logic
- **Accessibility First**: WCAG 2.1 AA compliance built-in

### State Management Strategy
- **Local State**: Component-specific state with `useState`
- **Server State**: API data with TanStack Query
- **Global State**: Minimal use of Context for cross-cutting concerns
- **Form State**: React Hook Form for complex forms
- **Real-time State**: Custom hooks for streaming data

## Component Hierarchy

```
App
├── AccessibilityProvider
├── Header
├── StatusBar
├── QueryBuilder/
│   ├── QueryBuilder
│   ├── EntityExtractor
│   ├── FilterPanel
│   └── AdvancedSettings
├── GraphView/
│   ├── GraphView
│   ├── StreamingGraphView
│   ├── AdvancedGraphVisualization
│   ├── StreamingNodeRenderer
│   └── PerformanceOverlay
├── ResultsPanel/
│   ├── ResultsPanel
│   ├── StreamingResultsView
│   ├── PubMedResults
│   ├── ClinicalTrialsResults
│   ├── RAGResults
│   └── SynthesisView
├── NodeInspector/
│   ├── NodeInspector
│   ├── NodeStateView
│   ├── NodeResultView
│   ├── NodePerformanceView
│   └── NodeLogsView
├── PerformanceMonitor/
│   ├── PerformanceDashboard
│   ├── PerformanceChart
│   └── MetricsDisplay
├── SessionManager/
│   ├── SessionHistoryManager
│   ├── SessionComparison
│   └── SessionDetails
├── DebugMode/
│   ├── DebugControlPanel
│   ├── BreakpointManager
│   └── StepControls
└── ui/
    ├── Button
    ├── Input
    ├── Textarea
    ├── Select
    ├── Switch
    ├── Tabs
    ├── Card
    ├── Badge
    ├── Progress
    ├── JSONViewer
    └── LoadingSpinner
```

## Core Components

### App Component

**File**: `src/App.tsx`

**Purpose**: Root application component managing global state and routing

**Props**: None (root component)

**State**:
```typescript
interface AppState {
  currentSession: OrchestrationSession | null
  selectedNodeId: string | null
  sidebarOpen: boolean
  theme: 'light' | 'dark' | 'auto'
}
```

**Key Responsibilities**:
- Initialize providers (Query Client, Accessibility)
- Manage current session state
- Handle global keyboard shortcuts
- Coordinate component communication

### Header Component

**File**: `src/components/ui/Header.tsx`

**Props**:
```typescript
interface HeaderProps {
  title?: string
  showLogo?: boolean
  actions?: React.ReactNode
}
```

**Features**:
- Application branding and title
- Global navigation controls
- User preferences menu
- Responsive design

### StatusBar Component

**File**: `src/components/ui/StatusBar.tsx`

**Props**:
```typescript
interface StatusBarProps {
  isConnected: boolean
  currentSession: OrchestrationSession | null
  toolCount?: number
  lastUpdate?: Date
}
```

**Features**:
- Connection status indicator
- Active session information
- Tool availability status
- Last update timestamp

## Query Building Components

### QueryBuilder Component

**File**: `src/components/QueryBuilder/QueryBuilder.tsx`

**Props**:
```typescript
interface QueryBuilderProps {
  onSubmit: (request: OrchestrationRequest) => void
  isLoading?: boolean
  error?: Error | null
  initialQuery?: string
  showAdvanced?: boolean
}
```

**State**:
```typescript
interface QueryBuilderState {
  query: string
  extractedEntities: ExtractedEntities
  showAdvanced: boolean
  isValidating: boolean
}
```

**Key Features**:
- Natural language query input
- Real-time entity extraction
- Form validation with React Hook Form
- Example query suggestions
- Advanced configuration panel

**Child Components**:

#### EntityExtractor
**Props**:
```typescript
interface EntityExtractorProps {
  entities: ExtractedEntities
  onEntityChange: (entities: ExtractedEntities) => void
  editable?: boolean
}

interface ExtractedEntities {
  topic?: string
  indication?: string
  company?: string
  trial_nct?: string
  phase?: string
  geographic_location?: string
}
```

#### FilterPanel
**Props**:
```typescript
interface FilterPanelProps {
  control: Control<OrchestrationRequest>
  filters: OrchestrationFilters
  onFiltersChange: (filters: OrchestrationFilters) => void
}

interface OrchestrationFilters {
  dateRange?: [Date, Date]
  phase?: string[]
  status?: string[]
  journals?: string[]
  minSampleSize?: number
  studyTypes?: string[]
}
```

#### AdvancedSettings
**Props**:
```typescript
interface AdvancedSettingsProps {
  control: Control<OrchestrationRequest>
  settings: AdvancedOrchestratorSettings
}

interface AdvancedOrchestratorSettings {
  timeBudgetMs: number
  fetchPolicy: 'cache_first' | 'network_only' | 'cache_then_network'
  maxParallelCalls: number
  enablePartialResults: boolean
  debugMode: boolean
  sessionName?: string
}
```

## Graph Visualization Components

### GraphView Component

**File**: `src/components/GraphView/GraphView.tsx`

**Props**:
```typescript
interface GraphViewProps {
  session?: OrchestrationSession | null
  onNodeSelect?: (nodeId: string | null) => void
  selectedNodeId?: string | null
  height?: string | number
  interactive?: boolean
}
```

**Features**:
- Basic ReactFlow integration
- Node status visualization
- Click-to-select functionality
- Responsive sizing

### StreamingGraphView Component

**File**: `src/components/GraphView/StreamingGraphView.tsx`

**Props**:
```typescript
interface StreamingGraphViewProps {
  session: OrchestrationSession
  graphData: GraphVisualizationData
  onNodeSelect: (nodeId: string | null) => void
  selectedNodeId: string | null
  enableStreaming?: boolean
}
```

**State**:
```typescript
interface StreamingGraphState {
  nodes: Node[]
  edges: Edge[]
  animationEnabled: boolean
  realTimeUpdates: boolean
}
```

**Features**:
- Real-time node status updates
- Animated execution flow
- Performance overlays
- Interactive node inspection

### AdvancedGraphVisualization Component

**File**: `src/components/GraphView/AdvancedGraphVisualization.tsx`

**Props**:
```typescript
interface AdvancedGraphVisualizationProps {
  session?: OrchestrationSession
  graphData: GraphVisualizationData
  onNodeSelect: (nodeId: string | null) => void
  selectedNodeId: string | null
  layoutOptions?: GraphLayoutOptions
}

interface GraphLayoutOptions {
  direction: 'horizontal' | 'vertical'
  nodeSpacing: number
  levelSpacing: number
  algorithm: 'dagre' | 'elk' | 'manual'
}
```

**Features**:
- Multiple layout algorithms
- Advanced visualization controls
- Performance monitoring overlay
- Zoom and pan controls
- Minimap support

### StreamingNodeRenderer Component

**File**: `src/components/GraphView/StreamingNodeRenderer.tsx`

**Props**:
```typescript
interface StreamingNodeRendererProps {
  data: StreamingNodeData
  id: string
  selected?: boolean
  dragging?: boolean
}

interface StreamingNodeData {
  label: string
  status: NodeStatus
  latency?: number
  isActive: boolean
  isStreaming: boolean
  result?: any
  performance?: NodePerformanceData
  onSelect?: (nodeId: string) => void
  onInspect?: (nodeId: string) => void
}

type NodeStatus = 'waiting' | 'running' | 'completed' | 'failed' | 'paused'
```

**Features**:
- Status-based styling
- Real-time animations
- Performance indicators
- Interactive controls
- Accessibility support

## Results Display Components

### ResultsPanel Component

**File**: `src/components/ResultsPanel/ResultsPanel.tsx`

**Props**:
```typescript
interface ResultsPanelProps {
  session: OrchestrationSession
  activeTab?: string
  onTabChange?: (tab: string) => void
}
```

**State**:
```typescript
interface ResultsPanelState {
  activeTab: string
  searchTerm: string
  sortBy: string
  filterBy: Record<string, any>
}
```

**Features**:
- Tabbed interface for different sources
- Search and filtering capabilities
- Export functionality
- Responsive layout

### StreamingResultsView Component

**File**: `src/components/ResultsPanel/StreamingResultsView.tsx`

**Props**:
```typescript
interface StreamingResultsViewProps {
  session: OrchestrationSession
  showProgress?: boolean
  enableAutoRefresh?: boolean
}
```

**Features**:
- Progressive result loading
- Real-time updates via SSE
- Connection status monitoring
- Error handling and recovery

### Source-Specific Result Components

#### PubMedResults Component
**Props**:
```typescript
interface PubMedResultsProps {
  results: PubMedSearchResults | null
  isStreaming?: boolean
  onArticleSelect?: (pmid: string) => void
  sortBy?: 'relevance' | 'date' | 'citations'
  showAbstracts?: boolean
}

interface PubMedSearchResults {
  results: PubMedArticle[]
  total_results: number
  search_terms: string[]
  metadata: {
    query_translation: string
    search_time_ms: number
    cache_hit: boolean
  }
}

interface PubMedArticle {
  pmid: string
  title: string
  abstract: string
  authors: string[]
  journal: string
  publication_date: string
  doi?: string
  pmc_id?: string
  mesh_terms: string[]
  keywords: string[]
  citation_count?: number
  impact_factor?: number
  quality_score?: number
}
```

#### ClinicalTrialsResults Component
**Props**:
```typescript
interface ClinicalTrialsResultsProps {
  results: ClinicalTrialsSearchResults | null
  isStreaming?: boolean
  onTrialSelect?: (nctId: string) => void
  showDetails?: boolean
  groupBy?: 'phase' | 'status' | 'sponsor'
}

interface ClinicalTrialsSearchResults {
  results: ClinicalTrial[]
  total_found: number
  filtered_count: number
  filters_applied: Record<string, any>
  search_terms: string[]
}

interface ClinicalTrial {
  nct_id: string
  title: string
  brief_summary: string
  detailed_description?: string
  conditions: string[]
  interventions: string[]
  phase: string
  status: string
  enrollment: {
    target: number
    actual?: number
    type: string
  }
  dates: {
    start_date: string
    completion_date?: string
    last_update: string
  }
  sponsors: {
    lead_sponsor: string
    collaborators: string[]
  }
  locations: Array<{
    facility: string
    city: string
    state?: string
    country: string
  }>
  investment_score?: number
  relevance_score?: number
  risk_assessment?: {
    completion_likelihood: number
    regulatory_risk: number
    competitive_risk: number
  }
}
```

#### RAGResults Component
**Props**:
```typescript
interface RAGResultsProps {
  results: RAGSearchResults | null
  isStreaming?: boolean
  onDocumentSelect?: (docId: string) => void
  showScores?: boolean
  highlightQuery?: boolean
}

interface RAGSearchResults {
  results: RAGDocument[]
  search_mode: 'hybrid' | 'semantic' | 'bm25'
  total_matches: number
  processing_time_ms: number
  query_embedding?: number[]
}

interface RAGDocument {
  doc_id: string
  title: string
  content: string
  source: string
  metadata: Record<string, any>
  scores: {
    bm25_score?: number
    vector_score?: number
    hybrid_score: number
    rerank_score?: number
  }
  chunks: Array<{
    chunk_id: string
    text: string
    position: number
    relevance_score: number
  }>
}
```

### SynthesisView Component

**File**: `src/components/ResultsPanel/SynthesisView.tsx`

**Props**:
```typescript
interface SynthesisViewProps {
  session: OrchestrationSession
  showCitations?: boolean
  showQualityMetrics?: boolean
  enableExport?: boolean
}

interface SynthesizedResult {
  answer: string
  checkpoint_id: string
  quality_metrics: QualityMetrics
  citations: Citation[]
  sources_summary: {
    pubmed_count: number
    trials_count: number
    rag_count: number
  }
  generation_metadata: {
    model_used: string
    prompt_version: string
    generation_time_ms: number
    token_count: number
  }
}

interface QualityMetrics {
  completeness: number     // 0-1, how complete the answer is
  recency: number         // 0-1, how recent the sources are
  authority: number       // 0-1, authority of sources
  diversity: number       // 0-1, diversity of source types
  relevance: number       // 0-1, relevance to query
  overall_score: number   // 0-1, weighted overall score
}

interface Citation {
  id: string
  type: 'pubmed' | 'clinicaltrials' | 'rag'
  title: string
  authors?: string[]
  source: string
  year?: number
  url?: string
  snippet: string
  relevance_score: number
}
```

## Node Inspection Components

### NodeInspector Component

**File**: `src/components/NodeInspector/NodeInspector.tsx`

**Props**:
```typescript
interface NodeInspectorProps {
  session: OrchestrationSession
  selectedNodeId: string | null
  nodeData?: NodeExecutionData
  onClose: () => void
  defaultTab?: string
}

interface NodeExecutionData {
  node_id: string
  status: NodeStatus
  start_time?: string
  end_time?: string
  duration_ms?: number
  input_data?: any
  output_data?: any
  error_data?: any
  performance_metrics?: NodePerformanceMetrics
  debug_info?: any
}

interface NodePerformanceMetrics {
  cpu_time_ms: number
  memory_peak_mb: number
  memory_current_mb: number
  api_calls_count: number
  cache_operations: {
    hits: number
    misses: number
    writes: number
  }
  network_io: {
    bytes_sent: number
    bytes_received: number
    request_count: number
  }
}
```

**Features**:
- Tabbed interface for different data views
- Real-time state inspection
- Performance metrics display
- Debug controls integration

### Node Detail Components

#### NodeStateView Component
**Props**:
```typescript
interface NodeStateViewProps {
  nodeState: any
  nodeId: string
  editable?: boolean
  onStateChange?: (newState: any) => void
}
```

#### NodeResultView Component
**Props**:
```typescript
interface NodeResultViewProps {
  result: any
  nodeId: string
  status: NodeStatus
  error?: Error
  showRaw?: boolean
}
```

#### NodePerformanceView Component
**Props**:
```typescript
interface NodePerformanceViewProps {
  nodeData: NodeExecutionData
  nodeId: string
  session: OrchestrationSession
  showComparison?: boolean
}
```

#### NodeLogsView Component
**Props**:
```typescript
interface NodeLogsViewProps {
  nodeId: string
  session: OrchestrationSession
  executionHistory: LogEntry[]
  logLevel?: 'debug' | 'info' | 'warn' | 'error'
}

interface LogEntry {
  timestamp: string
  level: 'debug' | 'info' | 'warn' | 'error'
  message: string
  node: string
  context?: Record<string, any>
}
```

## Performance Monitoring Components

### PerformanceDashboard Component

**File**: `src/components/PerformanceMonitor/PerformanceDashboard.tsx`

**Props**:
```typescript
interface PerformanceDashboardProps {
  session: OrchestrationSession
  historicalSessions?: OrchestrationSession[]
  showComparison?: boolean
  refreshInterval?: number
}
```

**Features**:
- Key performance metrics display
- Historical comparison charts
- Resource utilization monitoring
- Performance trend analysis

### PerformanceChart Component
**Props**:
```typescript
interface PerformanceChartProps {
  session: OrchestrationSession
  historicalSessions: OrchestrationSession[]
  chartType: 'timeline' | 'comparison' | 'trend'
  metric: 'latency' | 'throughput' | 'cache_hit_rate'
  height?: number
}
```

## Session Management Components

### SessionHistoryManager Component

**File**: `src/components/SessionManager/SessionHistoryManager.tsx`

**Props**:
```typescript
interface SessionHistoryManagerProps {
  onSelectSession: (session: OrchestrationSession) => void
  onCompareSession: (session: OrchestrationSession) => void
  currentSessionId?: string
  maxSessions?: number
}
```

**Features**:
- Paginated session list
- Search and filtering
- Session comparison tools
- Bulk operations

### SessionComparison Component
**Props**:
```typescript
interface SessionComparisonProps {
  sessions: OrchestrationSession[]
  comparisonType: 'performance' | 'results' | 'configuration'
  onClose: () => void
}
```

## Debug Mode Components

### DebugControlPanel Component

**File**: `src/components/DebugMode/DebugControlPanel.tsx`

**Props**:
```typescript
interface DebugControlPanelProps {
  session: OrchestrationSession
  graphNodes: GraphNode[]
  selectedNodeId: string | null
  onBreakpointChange?: (nodeId: string, enabled: boolean) => void
}
```

**Features**:
- Breakpoint management
- Step-by-step execution controls
- Auto-stepping configuration
- Debug session state display

## Base UI Components

### Button Component

**File**: `src/components/ui/Button.tsx`

**Props**:
```typescript
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link'
  size?: 'default' | 'sm' | 'lg' | 'icon'
  loading?: boolean
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
}
```

**Features**:
- Consistent styling with variants
- Loading states
- Icon support
- Full accessibility support
- Keyboard navigation

### Input Component

**File**: `src/components/ui/Input.tsx`

**Props**:
```typescript
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helper?: string
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
  loading?: boolean
}
```

### Select Component

**File**: `src/components/ui/Select.tsx`

**Props**:
```typescript
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  helper?: string
  options: SelectOption[]
  placeholder?: string
  searchable?: boolean
  multiple?: boolean
}

interface SelectOption {
  value: string
  label: string
  disabled?: boolean
  group?: string
}
```

### Tabs Component

**File**: `src/components/ui/Tabs.tsx`

**Props**:
```typescript
interface TabsProps {
  value: string
  onValueChange: (value: string) => void
  children: React.ReactNode
  className?: string
  orientation?: 'horizontal' | 'vertical'
}

interface TabsListProps {
  children: React.ReactNode
  className?: string
}

interface TabsTriggerProps {
  value: string
  children: React.ReactNode
  disabled?: boolean
  className?: string
}

interface TabsContentProps {
  value: string
  children: React.ReactNode
  className?: string
}
```

### JSONViewer Component

**File**: `src/components/ui/JSONViewer.tsx`

**Props**:
```typescript
interface JSONViewerProps {
  data: any
  collapsed?: boolean
  maxDepth?: number
  theme?: 'light' | 'dark'
  searchable?: boolean
  editable?: boolean
  onEdit?: (path: string[], value: any) => void
}
```

**Features**:
- Syntax highlighting
- Collapsible tree structure
- Search functionality
- Edit capabilities
- Copy to clipboard

## Custom Hooks

### Core Hooks

#### useOrchestrator Hook
```typescript
interface UseOrchestratorReturn {
  executeQuery: (request: OrchestrationRequest) => Promise<OrchestrationSession>
  currentSession: OrchestrationSession | null
  setCurrentSession: (session: OrchestrationSession | null) => void
  isLoading: boolean
  error: Error | null
  reset: () => void
}

function useOrchestrator(): UseOrchestratorReturn
```

#### useStreamingResults Hook
```typescript
interface UseStreamingResultsReturn {
  isConnected: boolean
  currentEvent: StreamingEvent | null
  connectionError: string | null
  accumulatedResults: any
  reconnect: () => void
  isStreaming: boolean
}

function useStreamingResults(sessionId: string | null): UseStreamingResultsReturn
```

#### useWebSocketDebug Hook
```typescript
interface UseWebSocketDebugReturn {
  debugState: DebugState | null
  isConnected: boolean
  connectionError: string | null
  setBreakpoint: (nodeId: string, enabled: boolean) => void
  stepExecution: (nodeId: string) => void
  inspectNodeState: (nodeId: string) => void
  resumeExecution: () => void
  disconnect: () => void
}

function useWebSocketDebug(sessionId: string | null, debugMode: boolean): UseWebSocketDebugReturn
```

#### usePerformanceMonitor Hook
```typescript
interface UsePerformanceMonitorReturn {
  startTiming: (label: string) => () => void
  getMetrics: (label: string) => PerformanceMetrics | null
  getAllMetrics: () => Record<string, PerformanceMetrics>
}

function usePerformanceMonitor(): UsePerformanceMonitorReturn
```

## Styling and Theming

### CSS Architecture
- **Utility-first**: Tailwind CSS for styling
- **Component variants**: Class Variance Authority (CVA) for component variants
- **Design tokens**: CSS custom properties for theming
- **Responsive**: Mobile-first responsive design
- **Dark mode**: System preference detection with manual override

### Theme Structure
```typescript
interface Theme {
  colors: {
    primary: ColorScale
    secondary: ColorScale
    accent: ColorScale
    neutral: ColorScale
    success: ColorScale
    warning: ColorScale
    error: ColorScale
  }
  spacing: SpacingScale
  typography: TypographyScale
  shadows: ShadowScale
  borderRadius: BorderRadiusScale
  animation: AnimationConfig
}
```

### Accessibility Features
- **Keyboard Navigation**: Full keyboard support
- **Screen Readers**: Comprehensive ARIA support
- **Color Contrast**: WCAG AA compliant color schemes
- **Focus Management**: Visible focus indicators
- **Motion Preferences**: Respect for reduced motion
- **Font Scaling**: Support for browser font size preferences

## Testing Strategy

### Component Testing
- **Unit Tests**: React Testing Library for component behavior
- **Integration Tests**: Test component interactions
- **Accessibility Tests**: jest-axe for a11y compliance
- **Visual Tests**: Chromatic for visual regression testing

### Test Utilities
```typescript
// Custom render with providers
function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions
): RenderResult

// Mock hooks for testing
function mockUseOrchestrator(): Partial<UseOrchestratorReturn>
function mockUseStreamingResults(): Partial<UseStreamingResultsReturn>

// Test data factories
function createMockSession(overrides?: Partial<OrchestrationSession>): OrchestrationSession
function createMockResults(type: 'pubmed' | 'trials' | 'rag'): any
```

## Performance Considerations

### Optimization Strategies
- **Code Splitting**: Lazy loading for routes and heavy components
- **Memoization**: React.memo for expensive components
- **Virtual Scrolling**: For large result sets
- **Debouncing**: Search inputs and real-time filters
- **Caching**: TanStack Query for server state
- **Bundle Analysis**: Regular bundle size monitoring

### Memory Management
- **Cleanup**: useEffect cleanup functions for subscriptions
- **Weak References**: For event listeners and callbacks
- **Garbage Collection**: Manual cleanup of large objects
- **Memory Profiling**: Regular monitoring in development

This component specification provides a comprehensive foundation for building the Bio-MCP Orchestrator UI with consistent, maintainable, and accessible React components.
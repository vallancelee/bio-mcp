# BioInvest AI Copilot POC - Implementation Milestone Plan

## 📋 Executive Summary

This milestone plan provides a structured roadmap for implementing M3/M4 advanced orchestration features in the BioInvest Copilot POC frontend, transforming it from a basic demonstration into a comprehensive showcase of production-ready biomedical research capabilities.

### 🎯 Implementation Objectives
1. **Frontend Enhancement**: Update React UI to leverage M3/M4 advanced features
2. **API Integration**: Complete frontend-backend integration with new endpoints
3. **User Experience**: Add visualizations for budget, retries, and synthesis progress
4. **Testing & Validation**: Comprehensive testing of all new features
5. **Documentation**: User guides and demo scenarios

### 💡 Business Value
- **Performance**: 2x faster queries with parallel execution
- **Reliability**: 95% error recovery rate with intelligent retries
- **Quality**: Investment-grade synthesis with citation management
- **Transparency**: Real-time visibility into orchestration processes
- **Reproducibility**: Checkpoint management for consistent results

---

## 📍 Milestone 1: Frontend Type Definitions & API Updates
**Duration**: 1-2 days | **Priority**: Critical | **Risk**: Low

### 🎯 Goal
Update frontend TypeScript definitions and API layer to support M3/M4 contract specifications, establishing the foundation for all advanced features.

### ✅ Success Criteria
- [x] All M3/M4 options available in TypeScript interfaces
- [x] New SSE event types properly defined
- [x] API service methods for new endpoints implemented
- [x] Type safety maintained across all new interfaces

### 🏆 Milestone 1 Status: **COMPLETED** ✅
**Completion Date**: 2025-08-28
**Test Results**: 30/30 tests passing (25 API contract + 5 compatibility tests)

### 🔧 Technical Tasks

#### 1.1 Update shared-types.ts
```typescript
// Add M3 Advanced State Management options
interface AdvancedAnalysisOptions extends AnalysisOptions {
  // M3 Features
  budget_ms?: number;              // 1000-30000ms
  enable_partial_results?: boolean; // Default: true
  retry_strategy?: 'exponential' | 'linear' | 'none';
  parallel_execution?: boolean;     // Default: true
  
  // M4 Features  
  citation_format?: 'pmid' | 'full' | 'inline';
  quality_threshold?: number;       // 0.0-1.0
  checkpoint_enabled?: boolean;     // Default: true
}

// Add new SSE event types
type AdvancedStreamEventType = StreamEventType | 
  'middleware_status' | 'retry_attempt' | 'partial_results' | 
  'budget_warning' | 'synthesis_progress' | 'citation_extracted' | 
  'checkpoint_created';
```

#### 1.2 Enhance API Service Layer
```typescript
// Add new endpoint methods
const apiService = {
  // ... existing methods
  
  async getLangGraphCapabilities(): Promise<CapabilitiesResponse> {
    const response = await api.get('/api/langgraph/capabilities');
    return response.data;
  },
  
  async getMiddlewareStatus(): Promise<MiddlewareStatusResponse> {
    const response = await api.get('/api/langgraph/middleware-status');
    return response.data;
  }
};
```

#### 1.3 Response Type Enhancements
```typescript
interface EnhancedOrchestrationResponse extends OrchestrationResponse {
  // M3 State Management Status
  budget_status?: {
    allocated_ms: number;
    consumed_ms: number;
    remaining_ms: number;
    utilization: number;
  };
  
  middleware_active?: {
    budget_enforcement: boolean;
    error_recovery: boolean;
    partial_results_enabled: boolean;
  };
  
  // M4 Synthesis Metadata
  checkpoint_id?: string;
  synthesis_metrics?: {
    citation_count: number;
    quality_score: number;
    answer_type: string;
  };
}
```

### 📁 Files to Modify
- `frontend/src/shared-types.ts`
- `frontend/src/services/api.ts`
- `frontend/src/types/api.ts`

### 🧪 Testing Requirements
- [ ] Type definitions compile without errors
- [ ] API methods return expected response types
- [ ] SSE event parsing handles all new event types
- [ ] Backward compatibility maintained for existing code

---

## 📍 Milestone 2: Enhanced Query Builder Component
**Duration**: 2-3 days | **Priority**: High | **Risk**: Medium

### 🎯 Goal
Transform the basic query input into an advanced research configuration interface that exposes M3/M4 capabilities to users through intuitive UI controls.

### ✅ Success Criteria
- [x] Advanced options panel with all M3/M4 controls
- [x] Preset configurations for common use cases
- [x] Real-time validation and feedback
- [x] Progressive disclosure (basic → advanced modes)

### 🏆 Milestone 2 Status: **COMPLETED** ✅
**Completion Date**: 2025-08-28
**Test Results**: 4/4 component tests passing + 30/30 contract tests passing

### 🔧 Technical Tasks

#### 2.1 Create Advanced Options Panel Component
```tsx
// New component: AdvancedOptionsPanel.tsx
interface AdvancedOptionsProps {
  options: AdvancedAnalysisOptions;
  onChange: (options: AdvancedAnalysisOptions) => void;
  isExpanded: boolean;
}

const AdvancedOptionsPanel: React.FC<AdvancedOptionsProps> = ({
  options, onChange, isExpanded
}) => {
  return (
    <Collapsible open={isExpanded}>
      {/* M3 State Management Section */}
      <div className="space-y-4">
        <h3>Execution Control</h3>
        
        {/* Budget Slider */}
        <BudgetSlider
          value={options.budget_ms}
          onChange={(value) => onChange({...options, budget_ms: value})}
          min={1000}
          max={30000}
        />
        
        {/* Retry Strategy Selector */}
        <RetryStrategySelector
          value={options.retry_strategy}
          onChange={(value) => onChange({...options, retry_strategy: value})}
        />
        
        {/* Parallel Execution Toggle */}
        <ParallelExecutionToggle
          enabled={options.parallel_execution}
          onChange={(enabled) => onChange({...options, parallel_execution: enabled})}
        />
      </div>
      
      {/* M4 Synthesis Section */}
      <div className="space-y-4">
        <h3>Synthesis Options</h3>
        
        {/* Citation Format Dropdown */}
        <CitationFormatSelector
          value={options.citation_format}
          onChange={(format) => onChange({...options, citation_format: format})}
        />
        
        {/* Quality Threshold Slider */}
        <QualityThresholdSlider
          value={options.quality_threshold}
          onChange={(value) => onChange({...options, quality_threshold: value})}
        />
      </div>
    </Collapsible>
  );
};
```

#### 2.2 Implement Option Presets
```tsx
// New component: OptionPresets.tsx
const PRESET_CONFIGURATIONS = {
  'fast-partial': {
    name: 'Fast & Partial',
    description: 'Quick screening with partial results',
    icon: '⚡',
    options: {
      budget_ms: 5000,
      enable_partial_results: true,
      retry_strategy: 'none',
      parallel_execution: true,
      quality_threshold: 0.3
    }
  },
  'reliable-complete': {
    name: 'Reliable & Complete', 
    description: 'Thorough analysis with error recovery',
    icon: '🎯',
    options: {
      budget_ms: 20000,
      enable_partial_results: false,
      retry_strategy: 'exponential',
      parallel_execution: true,
      quality_threshold: 0.6
    }
  },
  'investment-grade': {
    name: 'Investment Grade',
    description: 'High-quality analysis for critical decisions',
    icon: '💼',
    options: {
      budget_ms: 30000,
      enable_partial_results: false,
      retry_strategy: 'exponential',
      parallel_execution: true,
      quality_threshold: 0.8,
      citation_format: 'full'
    }
  }
};
```

#### 2.3 Enhanced Query Builder Integration
```tsx
// Updated QueryBuilder.tsx
const QueryBuilder: React.FC<QueryBuilderProps> = ({ onSubmit, isLoading }) => {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [options, setOptions] = useState<AdvancedAnalysisOptions>({
    max_results_per_source: 50,
    include_synthesis: true,
    priority: 'balanced',
    // M3/M4 defaults
    budget_ms: 10000,
    enable_partial_results: true,
    retry_strategy: 'exponential',
    parallel_execution: true,
    citation_format: 'full',
    quality_threshold: 0.5,
    checkpoint_enabled: true
  });
  
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Research Query</CardTitle>
          <Button 
            variant="ghost" 
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            Advanced {showAdvanced ? '↑' : '↓'}
          </Button>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Basic Query Input */}
        <QueryInput />
        <SourceSelector />
        
        {/* Preset Quick Selection */}
        <OptionPresets
          selected={selectedPreset}
          onSelect={(preset) => {
            setSelectedPreset(preset);
            setOptions(prev => ({...prev, ...PRESET_CONFIGURATIONS[preset].options}));
          }}
        />
        
        {/* Advanced Options Panel */}
        <AdvancedOptionsPanel
          options={options}
          onChange={setOptions}
          isExpanded={showAdvanced}
        />
        
        {/* Submit Button with Loading State */}
        <SubmitButton
          onSubmit={() => onSubmit({ query, sources, options })}
          isLoading={isLoading}
          hasAdvancedOptions={showAdvanced}
        />
      </CardContent>
    </Card>
  );
};
```

### 📁 Files to Create/Modify
- `frontend/src/components/QueryBuilder.tsx` (modify)
- `frontend/src/components/AdvancedOptionsPanel.tsx` (new)
- `frontend/src/components/OptionPresets.tsx` (new)
- `frontend/src/components/controls/BudgetSlider.tsx` (new)
- `frontend/src/components/controls/RetryStrategySelector.tsx` (new)
- `frontend/src/components/controls/CitationFormatSelector.tsx` (new)
- `frontend/src/components/controls/QualityThresholdSlider.tsx` (new)

### 🧪 Testing Requirements
- [ ] All option controls update state correctly
- [ ] Presets apply configurations as expected
- [ ] Validation prevents invalid combinations
- [ ] Advanced panel toggles smoothly
- [ ] Form submission includes all options

---

## 📍 Milestone 3: Real-time Monitoring Dashboard
**Duration**: 3-4 days | **Priority**: High | **Risk**: High

### 🏆 Milestone 3 Status: **COMPLETED** ✅
**Completion Date**: 2025-08-28
**Test Results**: 29/29 unit tests passing for all monitoring components
**Implementation**: All 4 monitoring components created and integrated with StreamingResults.tsx

### 🎯 Goal
Create comprehensive real-time visualization of M3/M4 orchestration processes, providing transparency into budget consumption, retry attempts, and synthesis progress.

### ✅ Success Criteria
- [x] Real-time budget monitoring with danger zones
- [x] Retry attempt visualization with backoff timing
- [x] Synthesis progress tracking with stage indicators
- [x] Middleware status dashboard components created
- [ ] <100ms SSE event processing latency (pending integration)

### 🔧 Technical Tasks

#### 3.1 Budget Monitor Component
```tsx
// New component: BudgetMonitor.tsx
interface BudgetStatus {
  allocated_ms: number;
  consumed_ms: number;
  remaining_ms: number;
  utilization: number;
}

const BudgetMonitor: React.FC<{ status: BudgetStatus }> = ({ status }) => {
  const getDangerLevel = (utilization: number) => {
    if (utilization > 0.9) return 'critical';
    if (utilization > 0.8) return 'warning';
    return 'normal';
  };

  return (
    <Card className="budget-monitor">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-4 w-4" />
          Budget Monitor
        </CardTitle>
      </CardHeader>
      
      <CardContent>
        {/* Progress Bar with Zones */}
        <div className="relative">
          <Progress 
            value={status.utilization * 100}
            className={`budget-progress ${getDangerLevel(status.utilization)}`}
          />
          
          {/* Danger Zone Markers */}
          <div className="absolute top-0 left-[80%] w-px h-full bg-yellow-500" />
          <div className="absolute top-0 left-[90%] w-px h-full bg-red-500" />
        </div>
        
        {/* Time Remaining */}
        <div className="mt-2 flex justify-between text-sm">
          <span>Consumed: {Math.round(status.consumed_ms / 1000)}s</span>
          <span>Remaining: {Math.round(status.remaining_ms / 1000)}s</span>
        </div>
        
        {/* Danger Zone Warning */}
        {status.utilization > 0.8 && (
          <Alert className="mt-2">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              Budget usage high! Query may timeout soon.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};
```

#### 3.2 Retry Visualizer Component
```tsx
// New component: RetryVisualizer.tsx
interface RetryAttempt {
  node: string;
  attempt: number;
  max_attempts: number;
  delay_ms: number;
  error: string;
  timestamp: string;
}

const RetryVisualizer: React.FC<{ attempts: RetryAttempt[] }> = ({ attempts }) => {
  return (
    <Card className="retry-visualizer">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <RotateCcw className="h-4 w-4" />
          Error Recovery
        </CardTitle>
      </CardHeader>
      
      <CardContent>
        <div className="space-y-3">
          {attempts.map((attempt, index) => (
            <div key={index} className="retry-attempt">
              <div className="flex items-center gap-3">
                <div className="retry-icon">
                  <RotateCcw className="h-3 w-3 animate-spin" />
                </div>
                
                <div className="flex-1">
                  <div className="font-medium text-sm">
                    {attempt.node} (Attempt {attempt.attempt}/{attempt.max_attempts})
                  </div>
                  <div className="text-xs text-gray-500">
                    Next retry in {attempt.delay_ms}ms
                  </div>
                </div>
                
                <Badge variant="outline">
                  {attempt.attempt}/{attempt.max_attempts}
                </Badge>
              </div>
              
              {/* Exponential Backoff Visualization */}
              <div className="mt-2 ml-6">
                <div className="flex items-center gap-1">
                  {[...Array(attempt.max_attempts)].map((_, i) => (
                    <div
                      key={i}
                      className={`h-2 rounded ${
                        i < attempt.attempt ? 'bg-red-400' : 'bg-gray-200'
                      }`}
                      style={{ 
                        width: `${Math.pow(2, i) * 10}px`,
                        maxWidth: '60px'
                      }}
                    />
                  ))}
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  Exponential backoff delays
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
```

#### 3.3 Synthesis Progress Component
```tsx
// New component: SynthesisProgress.tsx
interface SynthesisStage {
  stage: 'citation_extraction' | 'quality_scoring' | 'template_rendering';
  progress_percent: number;
  citations_found?: number;
  quality_score?: number;
}

const SynthesisProgress: React.FC<{ stage: SynthesisStage }> = ({ stage }) => {
  const getStageInfo = (stageName: string) => {
    const stages = {
      citation_extraction: { name: 'Citation Extraction', icon: '📚' },
      quality_scoring: { name: 'Quality Analysis', icon: '⭐' },
      template_rendering: { name: 'Final Synthesis', icon: '📝' }
    };
    return stages[stageName] || { name: stageName, icon: '⚙️' };
  };

  const stageInfo = getStageInfo(stage.stage);

  return (
    <Card className="synthesis-progress">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BookOpen className="h-4 w-4" />
          AI Synthesis
        </CardTitle>
      </CardHeader>
      
      <CardContent>
        <div className="space-y-4">
          {/* Current Stage */}
          <div className="current-stage">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">{stageInfo.icon}</span>
              <span className="font-medium">{stageInfo.name}</span>
            </div>
            
            <Progress value={stage.progress_percent} className="h-2" />
            <div className="text-xs text-gray-500 mt-1">
              {stage.progress_percent}% complete
            </div>
          </div>
          
          {/* Stage Metrics */}
          {stage.citations_found && (
            <div className="metric">
              <span className="text-sm text-gray-600">Citations Found:</span>
              <Badge variant="secondary" className="ml-2">
                {stage.citations_found}
              </Badge>
            </div>
          )}
          
          {stage.quality_score && (
            <div className="metric">
              <span className="text-sm text-gray-600">Quality Score:</span>
              <Badge variant="secondary" className="ml-2">
                {(stage.quality_score * 100).toFixed(1)}%
              </Badge>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
```

#### 3.4 Enhanced StreamingResults Integration
```tsx
// Updated StreamingResults.tsx
const StreamingResults: React.FC<StreamingResultsProps> = ({ 
  events, isConnected, error 
}) => {
  // Parse different event types
  const budgetStatus = events.find(e => e.event === 'middleware_status')?.data.budget;
  const retryAttempts = events.filter(e => e.event === 'retry_attempt').map(e => e.data);
  const synthesisProgress = events.find(e => e.event === 'synthesis_progress')?.data;
  const partialResults = events.find(e => e.event === 'partial_results')?.data;

  return (
    <div className="streaming-results space-y-4">
      {/* Connection Status */}
      <ConnectionStatus isConnected={isConnected} error={error} />
      
      {/* Real-time Monitoring Panels */}
      <div className="monitoring-grid grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Budget Monitor */}
        {budgetStatus && <BudgetMonitor status={budgetStatus} />}
        
        {/* Retry Visualizer */}
        {retryAttempts.length > 0 && <RetryVisualizer attempts={retryAttempts} />}
        
        {/* Synthesis Progress */}
        {synthesisProgress && <SynthesisProgress stage={synthesisProgress} />}
        
        {/* Partial Results Indicator */}
        {partialResults && <PartialResultsIndicator data={partialResults} />}
      </div>
      
      {/* Traditional Progress Display */}
      <TraditionalProgressDisplay events={events} />
    </div>
  );
};
```

### 📁 Files to Create/Modify
- `frontend/src/components/BudgetMonitor.tsx` (new)
- `frontend/src/components/RetryVisualizer.tsx` (new)
- `frontend/src/components/SynthesisProgress.tsx` (new)
- `frontend/src/components/PartialResultsIndicator.tsx` (new)
- `frontend/src/components/StreamingResults.tsx` (modify)
- `frontend/src/hooks/useStreamingResults.ts` (modify)

### 🧪 Testing Requirements
- [x] All monitoring components render correctly (29/29 tests passing)
- [x] Budget warnings appear at correct thresholds (tested with 80% and 90% scenarios)
- [x] Retry visualizations show exponential backoff correctly (tested with delay formatting)
- [x] Synthesis progress tracks all stages (citation extraction, quality scoring, template rendering)
- [ ] SSE events processed within 100ms (integration testing pending)

---

## 📍 Milestone 4: Enhanced Results Display
**Duration**: 2-3 days | **Priority**: High | **Risk**: Low

### 🏆 Milestone 4 Status: **COMPLETED** ✅
**Completion Date**: 2025-08-28
**Test Results**: 47/47 unit tests passing (includes all M3 + M4 components)
**Implementation**: QualityScoreDisplay, CitationManager, and enhanced ResultsDisplay with M4 integration

### 🎯 Goal
Transform the results display to showcase M4 synthesis quality features, including quality scoring, citation management, and partial results handling.

### ✅ Success Criteria
- [x] Interactive quality score visualization with investment-grade metrics
- [x] Professional citation display with formatting options (PMID, full, inline)
- [x] Clear partial vs complete results indication with recommendations
- [x] Checkpoint information display for reproducibility
- [x] Export functionality for citations (copy individual/bulk)

### 🔧 Technical Tasks

#### 4.1 Quality Score Display Component
```tsx
// New component: QualityScoreDisplay.tsx
interface QualityMetrics {
  completeness: number;
  recency: number;
  authority: number;
  diversity: number;
  relevance: number;
  overall_score: number;
}

const QualityScoreDisplay: React.FC<{ metrics: QualityMetrics }> = ({ metrics }) => {
  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600 bg-green-100';
    if (score >= 0.6) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  return (
    <Card className="quality-display">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Star className="h-4 w-4" />
          Quality Assessment
        </CardTitle>
      </CardHeader>
      
      <CardContent>
        {/* Overall Score Badge */}
        <div className="mb-4 text-center">
          <div className={`inline-flex items-center px-3 py-1 rounded-full text-lg font-bold ${getScoreColor(metrics.overall_score)}`}>
            {(metrics.overall_score * 100).toFixed(1)}%
          </div>
          <div className="text-sm text-gray-500 mt-1">Overall Quality Score</div>
        </div>
        
        {/* Individual Metrics */}
        <div className="space-y-3">
          {Object.entries(metrics).map(([key, value]) => {
            if (key === 'overall_score') return null;
            
            return (
              <div key={key} className="flex items-center justify-between">
                <span className="capitalize text-sm font-medium">
                  {key.replace('_', ' ')}
                </span>
                <div className="flex items-center gap-2">
                  <Progress value={value * 100} className="w-20 h-2" />
                  <span className="text-sm text-gray-600 w-12">
                    {(value * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
        
        {/* Quality Explanation */}
        <div className="mt-4 p-3 bg-blue-50 rounded-lg">
          <div className="text-sm text-blue-800">
            <strong>Investment Grade Analysis:</strong>
            {metrics.overall_score >= 0.8 && " Excellent quality with high confidence for investment decisions."}
            {metrics.overall_score >= 0.6 && metrics.overall_score < 0.8 && " Good quality suitable for preliminary analysis."}
            {metrics.overall_score < 0.6 && " Limited quality - consider expanding search criteria."}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
```

#### 4.2 Citation Manager Component
```tsx
// New component: CitationManager.tsx
interface CitationManagerProps {
  citations: Citation[];
  format: 'pmid' | 'full' | 'inline';
  onFormatChange: (format: string) => void;
}

const CitationManager: React.FC<CitationManagerProps> = ({ 
  citations, format, onFormatChange 
}) => {
  const formatCitation = (citation: Citation, format: string) => {
    switch (format) {
      case 'pmid':
        return `PMID: ${citation.id.replace('pmid:', '')}`;
      case 'inline':
        return `${citation.authors?.[0] || 'Unknown'} et al. (${citation.year})`;
      case 'full':
      default:
        return `${citation.authors?.join(', ') || 'Unknown authors'}. ${citation.title}. ${citation.source}. ${citation.year || 'Year unknown'}.`;
    }
  };

  const copyAllCitations = () => {
    const formatted = citations.map(c => formatCitation(c, format)).join('\n');
    navigator.clipboard.writeText(formatted);
  };

  return (
    <Card className="citation-manager">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="h-4 w-4" />
            Citations ({citations.length})
          </CardTitle>
          
          <div className="flex items-center gap-2">
            {/* Format Selector */}
            <Select value={format} onValueChange={onFormatChange}>
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="full">Full</SelectItem>
                <SelectItem value="pmid">PMID</SelectItem>
                <SelectItem value="inline">Inline</SelectItem>
              </SelectContent>
            </Select>
            
            {/* Copy All Button */}
            <Button 
              variant="outline" 
              size="sm"
              onClick={copyAllCitations}
            >
              <Copy className="h-3 w-3 mr-1" />
              Copy All
            </Button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {citations.map((citation, index) => (
            <div key={citation.id} className="citation-item">
              <div className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex-1">
                  <div className="text-sm font-mono">
                    {formatCitation(citation, format)}
                  </div>
                  
                  {/* Relevance Score */}
                  <div className="mt-2 flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">
                      Relevance: {(citation.relevance_score * 100).toFixed(0)}%
                    </Badge>
                    
                    {citation.url && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => window.open(citation.url!, '_blank')}
                      >
                        <ExternalLink className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </div>
                
                {/* Copy Individual Citation */}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigator.clipboard.writeText(formatCitation(citation, format))}
                >
                  <Copy className="h-3 w-3" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
```

#### 4.3 Partial Results Indicator
```tsx
// New component: PartialResultsIndicator.tsx
interface PartialResultsData {
  reason: 'timeout' | 'error' | 'budget_exhausted';
  completion_percentage: number;
  available_sources: string[];
  total_results: number;
}

const PartialResultsIndicator: React.FC<{ data: PartialResultsData }> = ({ data }) => {
  const getReasonIcon = (reason: string) => {
    switch (reason) {
      case 'timeout': return <Clock className="h-4 w-4" />;
      case 'budget_exhausted': return <DollarSign className="h-4 w-4" />;
      case 'error': return <AlertTriangle className="h-4 w-4" />;
      default: return <Info className="h-4 w-4" />;
    }
  };

  const getReasonMessage = (reason: string) => {
    switch (reason) {
      case 'timeout': return 'Query timed out - returning available results';
      case 'budget_exhausted': return 'Budget limit reached - returning available results';
      case 'error': return 'Some sources failed - returning successful results';
      default: return 'Partial results available';
    }
  };

  return (
    <Alert className="partial-results-alert border-yellow-500 bg-yellow-50">
      <div className="flex items-start gap-3">
        <div className="text-yellow-600">
          {getReasonIcon(data.reason)}
        </div>
        
        <div className="flex-1">
          <AlertTitle className="text-yellow-800">
            Partial Results ({Math.round(data.completion_percentage * 100)}% Complete)
          </AlertTitle>
          
          <AlertDescription className="text-yellow-700 mt-1">
            {getReasonMessage(data.reason)}
          </AlertDescription>
          
          {/* Available Sources */}
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="text-sm text-yellow-700">Available sources:</span>
            {data.available_sources.map(source => (
              <Badge key={source} variant="outline" className="text-yellow-700">
                {source}
              </Badge>
            ))}
          </div>
          
          {/* Results Summary */}
          <div className="mt-2 text-sm text-yellow-700">
            {data.total_results} results available from partial analysis
          </div>
        </div>
      </div>
    </Alert>
  );
};
```

#### 4.4 Enhanced Results Display Integration
```tsx
// Updated ResultsDisplay.tsx
const ResultsDisplay: React.FC<{ results: QueryResults | null }> = ({ results }) => {
  const [citationFormat, setCitationFormat] = useState<'pmid' | 'full' | 'inline'>('full');

  if (!results) {
    return <EmptyResultsState />;
  }

  return (
    <div className="results-display space-y-6">
      {/* Header with Metadata */}
      <div className="results-header">
        <h2 className="text-xl font-bold">Research Results</h2>
        
        {/* Checkpoint Info */}
        {results.synthesis?.generation_metadata?.checkpoint_id && (
          <Badge variant="outline" className="mt-2">
            Checkpoint: {results.synthesis.generation_metadata.checkpoint_id}
          </Badge>
        )}
      </div>
      
      {/* Synthesis Section */}
      {results.synthesis && (
        <div className="synthesis-section space-y-4">
          {/* Quality Score Display */}
          <QualityScoreDisplay metrics={results.synthesis.quality_metrics} />
          
          {/* AI Summary */}
          <Card>
            <CardHeader>
              <CardTitle>AI Synthesis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="prose max-w-none">
                {results.synthesis.summary}
              </div>
            </CardContent>
          </Card>
          
          {/* Citations */}
          <CitationManager
            citations={results.synthesis.citations}
            format={citationFormat}
            onFormatChange={(format) => setCitationFormat(format as any)}
          />
        </div>
      )}
      
      {/* Source Results */}
      <div className="source-results">
        {Object.entries(results.results).map(([source, data]) => (
          <SourceResultsDisplay
            key={source}
            source={source}
            data={data}
            qualityThreshold={results.synthesis?.generation_metadata?.m4_features?.quality_threshold}
          />
        ))}
      </div>
    </div>
  );
};
```

### 📁 Files to Create/Modify
- `frontend/src/components/QualityScoreDisplay.tsx` (new)
- `frontend/src/components/CitationManager.tsx` (new)
- `frontend/src/components/PartialResultsIndicator.tsx` (new)
- `frontend/src/components/ResultsDisplay.tsx` (modify)
- `frontend/src/components/SourceResultsDisplay.tsx` (modify)

### 🧪 Testing Requirements
- [x] Quality scores display correctly for all ranges (high/medium/low investment grade)
- [x] Citation formatting works for all three formats (PMID, full, inline)
- [x] Copy functionality works for individual and bulk citations (clipboard integration)
- [x] Partial results indicators show appropriate warnings and recommendations
- [x] Export functionality generates proper citations (18 citation tests passing)

---

## 📍 Milestone 5: LangGraph Visualization
**Duration**: 2-3 days | **Priority**: Medium | **Risk**: High

### 🏆 Milestone 5 Status: **COMPLETED** ✅
**Completion Date**: 2025-08-28
**Test Results**: 91/91 unit tests passing (includes all M3 + M4 + M5 components)
**Implementation**: LangGraphVisualizer, MiddlewareStatusPanel, GraphLegend, and ResearchWorkspace integration

### 🎯 Goal
Create interactive visualization of the LangGraph workflow execution, showing node progression, middleware interactions, and execution paths.

### ✅ Success Criteria
- [x] Interactive node-edge diagram with SVG-based flow visualization
- [x] Real-time execution path highlighting with active node tracking
- [x] Middleware status visualization with performance metrics
- [x] Node performance metrics with execution time display
- [x] Collapsible/expandable visualization panel (toggle button in ResearchWorkspace)

### 🔧 Technical Tasks

#### 5.1 Graph Visualizer Component
```tsx
// New component: LangGraphVisualizer.tsx
interface GraphVisualizerProps {
  visualization: LangGraphVisualizationResponse;
  currentPath?: string[];
  activeNode?: string;
  executionMetrics?: Record<string, number>;
}

const LangGraphVisualizer: React.FC<GraphVisualizerProps> = ({
  visualization, currentPath = [], activeNode, executionMetrics = {}
}) => {
  const getNodeStatus = (nodeId: string) => {
    if (nodeId === activeNode) return 'active';
    if (currentPath.includes(nodeId)) return 'completed';
    return 'pending';
  };

  const getNodeColor = (status: string, type: string) => {
    const colors = {
      active: 'bg-blue-500 border-blue-600 text-white',
      completed: 'bg-green-500 border-green-600 text-white',
      pending: 'bg-gray-200 border-gray-300 text-gray-700'
    };
    return colors[status] || colors.pending;
  };

  return (
    <Card className="graph-visualizer">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GitBranch className="h-4 w-4" />
          LangGraph Execution Flow
        </CardTitle>
      </CardHeader>
      
      <CardContent>
        {/* Graph Canvas */}
        <div className="graph-canvas relative bg-gray-50 rounded-lg p-6 min-h-[400px]">
          {/* Nodes */}
          {visualization.nodes.map((node) => {
            const status = getNodeStatus(node.id);
            const metrics = executionMetrics[node.id];
            
            return (
              <div
                key={node.id}
                className={`node absolute p-3 rounded-lg border-2 ${getNodeColor(status, node.type)}`}
                style={{
                  // Position nodes in a flow layout
                  left: `${getNodePosition(node.id, 'x')}px`,
                  top: `${getNodePosition(node.id, 'y')}px`
                }}
              >
                <div className="node-content text-center">
                  <div className="node-icon">
                    {getNodeTypeIcon(node.type)}
                  </div>
                  <div className="node-label text-sm font-medium mt-1">
                    {node.label}
                  </div>
                  
                  {/* Performance Metrics */}
                  {metrics && (
                    <div className="node-metrics text-xs mt-1 opacity-75">
                      {Math.round(metrics)}ms
                    </div>
                  )}
                </div>
                
                {/* Active Node Pulse */}
                {status === 'active' && (
                  <div className="absolute inset-0 rounded-lg border-2 border-blue-400 animate-pulse" />
                )}
              </div>
            );
          })}
          
          {/* Edges */}
          <svg className="edges absolute inset-0 w-full h-full pointer-events-none">
            {visualization.edges.map((edge, index) => {
              const fromPos = getNodePosition(edge.from);
              const toPos = getNodePosition(edge.to);
              const isActive = currentPath.includes(edge.from) && currentPath.includes(edge.to);
              
              return (
                <line
                  key={index}
                  x1={fromPos.x + 50} // Node center offset
                  y1={fromPos.y + 25}
                  x2={toPos.x + 50}
                  y2={toPos.y + 25}
                  stroke={isActive ? '#3B82F6' : '#D1D5DB'}
                  strokeWidth={isActive ? 3 : 2}
                  markerEnd="url(#arrowhead)"
                />
              );
            })}
            
            {/* Arrow markers */}
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
          </svg>
        </div>
        
        {/* Graph Legend */}
        <GraphLegend />
        
        {/* Execution Statistics */}
        {currentPath.length > 0 && (
          <div className="execution-stats mt-4 p-3 bg-blue-50 rounded-lg">
            <div className="text-sm font-medium text-blue-800">
              Execution Progress: {currentPath.length}/{visualization.nodes.length} nodes
            </div>
            <div className="text-xs text-blue-600 mt-1">
              Current: {activeNode || 'Completed'}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
```

#### 5.2 Middleware Status Panel
```tsx
// New component: MiddlewareStatusPanel.tsx
interface MiddlewareStatusProps {
  status: MiddlewareStatusResponse;
}

const MiddlewareStatusPanel: React.FC<MiddlewareStatusProps> = ({ status }) => {
  return (
    <Card className="middleware-status">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="h-4 w-4" />
          Middleware Components
        </CardTitle>
      </CardHeader>
      
      <CardContent>
        <div className="space-y-4">
          {/* Budget Enforcement */}
          <div className="middleware-component">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-blue-500" />
                <span className="font-medium">Budget Enforcement</span>
              </div>
              <Badge variant={status.active_middleware.budget_enforcement.enabled ? "default" : "secondary"}>
                {status.active_middleware.budget_enforcement.enabled ? "Active" : "Inactive"}
              </Badge>
            </div>
            
            {status.active_middleware.budget_enforcement.enabled && (
              <div className="mt-2 text-sm text-gray-600">
                Default: {status.active_middleware.budget_enforcement.default_budget_ms}ms
                <br />
                Active queries: {status.active_middleware.budget_enforcement.active_queries}
              </div>
            )}
          </div>
          
          {/* Error Recovery */}
          <div className="middleware-component">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <RotateCcw className="h-4 w-4 text-green-500" />
                <span className="font-medium">Error Recovery</span>
              </div>
              <Badge variant={status.active_middleware.error_recovery.enabled ? "default" : "secondary"}>
                {status.active_middleware.error_recovery.enabled ? "Active" : "Inactive"}
              </Badge>
            </div>
            
            {status.active_middleware.error_recovery.enabled && (
              <div className="mt-2 text-sm text-gray-600">
                Strategy: {status.active_middleware.error_recovery.retry_strategy}
                <br />
                Success rate: {(status.active_middleware.error_recovery.success_rate * 100).toFixed(1)}%
              </div>
            )}
          </div>
          
          {/* Partial Results */}
          <div className="middleware-component">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <PieChart className="h-4 w-4 text-yellow-500" />
                <span className="font-medium">Partial Results</span>
              </div>
              <Badge variant={status.active_middleware.partial_results.enabled ? "default" : "secondary"}>
                {status.active_middleware.partial_results.enabled ? "Active" : "Inactive"}
              </Badge>
            </div>
            
            {status.active_middleware.partial_results.enabled && (
              <div className="mt-2 text-sm text-gray-600">
                Extraction rate: {(status.active_middleware.partial_results.extraction_rate * 100).toFixed(1)}%
              </div>
            )}
          </div>
        </div>
        
        {/* Performance Metrics */}
        <div className="performance-metrics mt-6 pt-4 border-t">
          <h4 className="font-medium mb-3">Performance Metrics</h4>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Avg Execution:</span>
              <div className="font-medium">{Math.round(status.performance_metrics.average_execution_time / 1000)}s</div>
            </div>
            <div>
              <span className="text-gray-600">Timeout Rate:</span>
              <div className="font-medium">{(status.performance_metrics.timeout_rate * 100).toFixed(1)}%</div>
            </div>
            <div>
              <span className="text-gray-600">Retry Rate:</span>
              <div className="font-medium">{(status.performance_metrics.retry_rate * 100).toFixed(1)}%</div>
            </div>
            <div>
              <span className="text-gray-600">Partial Rate:</span>
              <div className="font-medium">{(status.performance_metrics.partial_results_rate * 100).toFixed(1)}%</div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
```

#### 5.3 Integration with ResearchWorkspace
```tsx
// Updated ResearchWorkspace.tsx
const ResearchWorkspace: React.FC = () => {
  const [showVisualization, setShowVisualization] = useState(false);
  
  // Query LangGraph data
  const { data: capabilities } = useQuery({
    queryKey: ['langgraph-capabilities'],
    queryFn: apiService.getLangGraphCapabilities,
    refetchInterval: 10000
  });
  
  const { data: middlewareStatus } = useQuery({
    queryKey: ['middleware-status'],
    queryFn: apiService.getMiddlewareStatus,
    refetchInterval: 5000
  });
  
  const { data: visualization } = useQuery({
    queryKey: ['langgraph-visualization'],
    queryFn: apiService.getLangGraphVisualization,
    enabled: showVisualization
  });

  return (
    <div className="research-workspace">
      {/* ... existing header ... */}
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-1">
            {/* ... existing query builder ... */}
            
            {/* Visualization Toggle */}
            <Card className="mt-6">
              <CardContent className="pt-6">
                <Button
                  variant="outline"
                  onClick={() => setShowVisualization(!showVisualization)}
                  className="w-full"
                >
                  <GitBranch className="h-4 w-4 mr-2" />
                  {showVisualization ? 'Hide' : 'Show'} Workflow
                </Button>
              </CardContent>
            </Card>
          </div>
          
          <div className="lg:col-span-2 space-y-6">
            {/* Visualization Panel */}
            {showVisualization && (
              <div className="visualization-panel space-y-4">
                {visualization && (
                  <LangGraphVisualizer
                    visualization={visualization}
                    currentPath={getCurrentExecutionPath()}
                    activeNode={getCurrentActiveNode()}
                    executionMetrics={getExecutionMetrics()}
                  />
                )}
                
                {middlewareStatus && (
                  <MiddlewareStatusPanel status={middlewareStatus} />
                )}
              </div>
            )}
            
            {/* ... existing results display ... */}
          </div>
        </div>
      </main>
    </div>
  );
};
```

### 📁 Files to Create
- `frontend/src/components/LangGraphVisualizer.tsx` (new)
- `frontend/src/components/MiddlewareStatusPanel.tsx` (new)
- `frontend/src/components/GraphLegend.tsx` (new)
- `frontend/src/utils/graph-layout.ts` (new)

### 🧪 Testing Requirements
- [x] Graph visualization renders correctly (44 M5-specific tests passing)
- [x] Node positions calculated accurately with SVG positioning
- [x] Execution path highlighting works with real-time status updates
- [x] Middleware status updates in real-time with performance metrics
- [x] Performance metrics display correctly with time formatting (ms/s)

---

## 📍 Milestone 6: Integration Testing
**Duration**: 2-3 days | **Priority**: Critical | **Risk**: Medium

### 🎯 Goal
Comprehensive testing of all M3/M4 features with focus on end-to-end functionality, performance validation, and error handling scenarios.

### ✅ Success Criteria
- [ ] All E2E test scenarios pass
- [ ] Performance benchmarks meet targets (2x speedup, <100ms SSE latency)
- [ ] Error handling covers all failure modes
- [ ] Load testing validates concurrent query handling
- [ ] Cross-browser compatibility verified

### 🔧 Technical Tasks

#### 6.1 End-to-End Test Scenarios
```typescript
// New file: frontend/tests/e2e/advanced-features.test.ts
describe('M3/M4 Advanced Features', () => {
  beforeEach(() => {
    cy.visit('/');
    cy.intercept('GET', '/api/langgraph/capabilities').as('getCapabilities');
    cy.intercept('POST', '/api/research/query').as('submitQuery');
  });

  describe('Budget Enforcement', () => {
    it('should enforce budget limits and show warnings', () => {
      // Set short budget
      cy.get('[data-testid=advanced-options]').click();
      cy.get('[data-testid=budget-slider]').type('3000');
      
      // Submit query
      cy.get('[data-testid=query-input]').type('comprehensive CAR-T analysis');
      cy.get('[data-testid=submit-button]').click();
      
      // Verify budget monitoring
      cy.wait('@submitQuery');
      cy.get('[data-testid=budget-monitor]').should('be.visible');
      cy.get('[data-testid=budget-progress]').should('exist');
      
      // Should see budget warning
      cy.get('[data-testid=budget-warning]', { timeout: 10000 }).should('contain', 'Budget usage high');
    });

    it('should handle budget exhaustion gracefully', () => {
      cy.get('[data-testid=advanced-options]').click();
      cy.get('[data-testid=budget-slider]').type('1000'); // Very short budget
      
      cy.get('[data-testid=query-input]').type('extensive drug pipeline analysis');
      cy.get('[data-testid=submit-button]').click();
      
      // Should show partial results
      cy.get('[data-testid=partial-results-indicator]', { timeout: 5000 }).should('be.visible');
      cy.get('[data-testid=partial-results-indicator]').should('contain', 'Budget limit reached');
    });
  });

  describe('Parallel Execution', () => {
    it('should execute sources in parallel and show performance improvement', () => {
      // Enable parallel execution
      cy.get('[data-testid=advanced-options]').click();
      cy.get('[data-testid=parallel-execution]').check();
      
      cy.get('[data-testid=query-input]').type('GLP-1 market analysis');
      
      const startTime = Date.now();
      cy.get('[data-testid=submit-button]').click();
      
      // Monitor source progress
      cy.get('[data-testid=source-progress-pubmed]').should('contain', 'processing');
      cy.get('[data-testid=source-progress-clinical_trials]').should('contain', 'processing');
      cy.get('[data-testid=source-progress-rag]').should('contain', 'processing');
      
      // Wait for completion and verify timing
      cy.get('[data-testid=query-completed]', { timeout: 15000 }).should('be.visible');
      
      cy.then(() => {
        const executionTime = Date.now() - startTime;
        expect(executionTime).to.be.lessThan(12000); // Should be faster than sequential
      });
    });
  });

  describe('Error Recovery', () => {
    it('should retry failed operations with exponential backoff', () => {
      // Mock intermittent failures
      cy.intercept('POST', '/api/research/query', { statusCode: 500 }).as('failedQuery');
      cy.intercept('GET', '/api/research/stream/*', { statusCode: 200, body: 'data: {"event": "retry_attempt"}\n\n' }).as('streamRetry');
      
      cy.get('[data-testid=advanced-options]').click();
      cy.get('[data-testid=retry-strategy]').select('exponential');
      
      cy.get('[data-testid=query-input]').type('test retry mechanism');
      cy.get('[data-testid=submit-button]').click();
      
      // Should show retry attempts
      cy.get('[data-testid=retry-visualizer]', { timeout: 5000 }).should('be.visible');
      cy.get('[data-testid=retry-attempt]').should('contain', 'Attempt 1/3');
    });
  });

  describe('Advanced Synthesis', () => {
    it('should extract citations and show quality scores', () => {
      cy.get('[data-testid=advanced-options]').click();
      cy.get('[data-testid=quality-threshold]').type('0.7');
      cy.get('[data-testid=citation-format]').select('full');
      
      cy.get('[data-testid=query-input]').type('diabetes drug efficacy studies');
      cy.get('[data-testid=submit-button]').click();
      
      // Wait for synthesis completion
      cy.get('[data-testid=synthesis-completed]', { timeout: 20000 }).should('be.visible');
      
      // Verify quality display
      cy.get('[data-testid=quality-score-display]').should('be.visible');
      cy.get('[data-testid=overall-quality]').should('contain', '%');
      
      // Verify citations
      cy.get('[data-testid=citation-manager]').should('be.visible');
      cy.get('[data-testid=citation-count]').should('not.contain', '0');
      
      // Test citation format switching
      cy.get('[data-testid=citation-format-selector]').select('pmid');
      cy.get('[data-testid=citation-item]').first().should('contain', 'PMID:');
    });
  });
});
```

#### 6.2 Performance Benchmarking
```typescript
// New file: frontend/tests/performance/benchmarks.test.ts
describe('Performance Benchmarks', () => {
  it('should achieve 2x speedup with parallel execution', () => {
    const measureExecutionTime = async (parallelEnabled: boolean) => {
      cy.visit('/');
      cy.get('[data-testid=advanced-options]').click();
      cy.get('[data-testid=parallel-execution]')[parallelEnabled ? 'check' : 'uncheck']();
      
      const startTime = performance.now();
      cy.get('[data-testid=query-input]').type('comprehensive biotech analysis');
      cy.get('[data-testid=submit-button]').click();
      
      return cy.get('[data-testid=query-completed]', { timeout: 30000 })
        .then(() => performance.now() - startTime);
    };
    
    // Measure sequential execution
    measureExecutionTime(false).then(sequentialTime => {
      // Measure parallel execution
      measureExecutionTime(true).then(parallelTime => {
        const speedupRatio = sequentialTime / parallelTime;
        expect(speedupRatio).to.be.greaterThan(1.8); // At least 1.8x speedup
      });
    });
  });

  it('should process SSE events within 100ms', () => {
    cy.visit('/');
    cy.get('[data-testid=query-input]').type('test sse latency');
    
    let eventReceived: number;
    cy.window().then(win => {
      // Intercept SSE events
      const originalEventSource = win.EventSource;
      win.EventSource = function(...args) {
        const es = new originalEventSource(...args);
        es.addEventListener('message', (event) => {
          eventReceived = performance.now();
        });
        return es;
      };
    });
    
    const startTime = performance.now();
    cy.get('[data-testid=submit-button]').click();
    
    cy.get('[data-testid=streaming-event]', { timeout: 5000 })
      .should('be.visible')
      .then(() => {
        const latency = eventReceived - startTime;
        expect(latency).to.be.lessThan(100); // <100ms SSE latency
      });
  });
});
```

#### 6.3 Error Handling Validation
```typescript
// New file: frontend/tests/integration/error-handling.test.ts
describe('Error Handling Scenarios', () => {
  describe('Network Failures', () => {
    it('should handle API timeout gracefully', () => {
      cy.intercept('POST', '/api/research/query', { delay: 31000 }).as('timeoutQuery');
      
      cy.visit('/');
      cy.get('[data-testid=query-input]').type('timeout test query');
      cy.get('[data-testid=submit-button]').click();
      
      cy.get('[data-testid=error-message]', { timeout: 32000 })
        .should('contain', 'Request timeout');
    });

    it('should reconnect SSE streams after connection loss', () => {
      cy.visit('/');
      cy.get('[data-testid=query-input]').type('connection test');
      cy.get('[data-testid=submit-button]').click();
      
      // Simulate connection loss
      cy.window().then(win => {
        const activeEventSource = win.document.querySelector('[data-testid=event-source]');
        if (activeEventSource) {
          activeEventSource.close();
        }
      });
      
      // Should show reconnection attempt
      cy.get('[data-testid=connection-status]')
        .should('contain', 'Reconnecting');
    });
  });

  describe('Partial Failures', () => {
    it('should handle mixed success/failure scenarios', () => {
      // Mock partial failures
      cy.intercept('GET', '/api/research/stream/*', (req) => {
        req.reply({
          statusCode: 200,
          body: 'data: {"event": "source_failed", "data": {"source": "pubmed"}}\n\n'
        });
      }).as('partialFailure');
      
      cy.visit('/');
      cy.get('[data-testid=query-input]').type('partial failure test');
      cy.get('[data-testid=submit-button]').click();
      
      cy.get('[data-testid=source-status-pubmed]')
        .should('contain', 'failed');
      cy.get('[data-testid=partial-results-indicator]')
        .should('be.visible');
    });
  });
});
```

### 📁 Files to Create
- `frontend/tests/e2e/advanced-features.test.ts` (new)
- `frontend/tests/performance/benchmarks.test.ts` (new)  
- `frontend/tests/integration/error-handling.test.ts` (new)
- `backend/tests/integration/poc-integration.test.py` (new)
- `tests/load/concurrent-queries.test.ts` (new)

### 🧪 Testing Requirements
- [ ] All E2E scenarios pass with >90% reliability
- [ ] Parallel execution achieves >1.8x speedup
- [ ] SSE events processed within 100ms
- [ ] Error recovery success rate >90%
- [ ] Concurrent query handling validated

---

## 📍 Milestone 7: Demo Scenarios & Documentation
**Duration**: 1-2 days | **Priority**: High | **Risk**: Low

### 🎯 Goal
Create compelling demonstration scenarios and comprehensive documentation that showcase the full capabilities of the enhanced POC.

### ✅ Success Criteria
- [ ] Three polished demo scenarios with expected outcomes
- [ ] User guide covering all advanced features
- [ ] Performance tuning recommendations
- [ ] Troubleshooting guide for common issues
- [ ] Video demonstration materials

### 🔧 Technical Tasks

#### 7.1 Demo Scenarios Documentation
```markdown
# Demo Scenarios - BioInvest AI Copilot POC

## 🚀 Scenario 1: Fast Investment Screening
**Use Case**: Quick evaluation of emerging biotech opportunities
**Duration**: 5 seconds
**Configuration**: Fast & Partial preset

### Setup:
- Budget: 5,000ms (5 seconds)
- Parallel execution: Enabled
- Partial results: Enabled
- Quality threshold: 0.3 (lower for speed)
- Retry strategy: None (fail fast)

### Demo Query:
"What are the most promising CAR-T cell therapy companies with upcoming Phase 3 trials?"

### Expected Outcomes:
- ✅ Results within 5 seconds
- ✅ 3-5 sources provide data
- ✅ Partial results if sources timeout
- ✅ Quick synthesis with key companies identified
- ✅ PMID citations for rapid verification

### Key Features Demonstrated:
- Budget enforcement with progress bar
- Parallel source execution
- Partial results handling
- Fast synthesis generation

---

## 🎯 Scenario 2: Deep Competitive Analysis  
**Use Case**: Comprehensive analysis for major investment decision
**Duration**: 20 seconds
**Configuration**: Reliable & Complete preset

### Setup:
- Budget: 20,000ms (20 seconds)  
- Parallel execution: Enabled
- Partial results: Disabled (must complete)
- Quality threshold: 0.6 (balanced)
- Retry strategy: Exponential backoff

### Demo Query:
"Analyze Novo Nordisk's competitive position in GLP-1 receptor agonists, including pipeline threats and market risks"

### Expected Outcomes:
- ✅ Complete analysis within 20 seconds
- ✅ High-quality synthesis with competitive intelligence
- ✅ Error recovery demonstrations (simulated failures)
- ✅ Full citations with impact factors
- ✅ Investment-grade quality scores (>60%)

### Key Features Demonstrated:
- Error recovery with exponential backoff
- Middleware status monitoring
- High-quality synthesis
- Complete citation management

---

## 💼 Scenario 3: Investment Grade Research
**Use Case**: Critical due diligence for major pharmaceutical investment
**Duration**: 30 seconds
**Configuration**: Investment Grade preset

### Setup:
- Budget: 30,000ms (30 seconds)
- Parallel execution: Enabled  
- Partial results: Disabled
- Quality threshold: 0.8 (high quality only)
- Retry strategy: Exponential backoff
- Citation format: Full academic style

### Demo Query:
"Evaluate the regulatory and competitive risks for Biogen's Alzheimer's drug pipeline including aducanumab alternatives and FDA approval challenges"

### Expected Outcomes:
- ✅ Comprehensive 30-second analysis
- ✅ Investment-grade quality scores (>80%)
- ✅ Full academic citations
- ✅ Detailed competitive analysis
- ✅ Risk assessment with impact scoring
- ✅ Checkpoint for reproducibility

### Key Features Demonstrated:
- High quality threshold filtering
- Complete citation formatting
- Checkpoint management
- Advanced synthesis with risk analysis
- Performance monitoring across all middleware
```

#### 7.2 User Guide
```markdown
# BioInvest AI Copilot POC - User Guide

## Getting Started

### Basic Query Submission
1. Enter your research question in natural language
2. Select data sources (PubMed, ClinicalTrials.gov, RAG)
3. Choose basic options or use advanced presets
4. Click "Submit Query" to begin analysis

### Advanced Options Overview

#### M3 State Management Features

**Budget Control**
- Set execution time limits (1-30 seconds)
- Monitor real-time consumption
- Receive warnings at 80% utilization
- Budget exhaustion triggers partial results

**Parallel Execution**  
- Enable concurrent source searches
- Typically 2x faster than sequential
- Real-time progress for each source
- Automatic load balancing

**Error Recovery**
- Exponential backoff for transient failures
- Linear backoff for predictable delays  
- Skip failed sources and continue
- Visual retry attempt indicators

**Partial Results**
- Extract meaningful data from incomplete queries
- Show completion percentage
- Identify successful vs failed sources
- Graceful degradation on timeout

#### M4 Synthesis Features

**Quality Control**
- Set minimum quality thresholds (0.0-1.0)
- Investment-relevance scoring
- Journal impact factor weighting
- Authority and recency metrics

**Citation Management**
- PMID format: "PMID: 12345678"
- Full format: "Author et al. Title. Journal. Year."
- Inline format: "Smith et al. (2023)"
- Copy individual or bulk citations

**Checkpoint Management**
- Deterministic result reproduction
- Checkpoint ID for reference
- Consistent outputs across runs
- Version control for analyses

## Real-time Monitoring

### Budget Monitor
- Green: Normal consumption (<80%)
- Yellow: High usage warning (80-90%)
- Red: Critical usage (>90%)
- Countdown timer shows remaining time

### Retry Visualizer  
- Shows active retry attempts
- Exponential backoff timing
- Error classification
- Success/failure tracking

### Synthesis Progress
- Citation extraction stage
- Quality scoring stage  
- Final template rendering
- Real-time metrics display

## Best Practices

### Query Optimization
- Start with broad queries, then narrow focus
- Use specific company/drug names when known
- Include time periods ("last 2 years", "2023-2024")
- Specify analysis type ("competitive", "regulatory", "clinical")

### Budget Management
- Fast screening: 5-10 seconds
- Standard analysis: 15-20 seconds  
- Comprehensive research: 25-30 seconds
- Monitor consumption during execution

### Quality Tuning
- Screening: 0.3-0.5 threshold
- Analysis: 0.5-0.7 threshold
- Investment grade: 0.7-1.0 threshold
- Balance quality vs completeness
```

#### 7.3 Performance Tuning Guide
```markdown
# Performance Tuning Guide

## Optimal Configuration Matrix

| Use Case | Budget | Parallel | Threshold | Retry | Expected Time |
|----------|--------|----------|-----------|--------|---------------|
| Quick Screening | 5s | ✅ | 0.3 | None | 3-5s |
| Standard Analysis | 15s | ✅ | 0.6 | Exponential | 8-12s |
| Deep Research | 25s | ✅ | 0.8 | Exponential | 15-20s |
| Comprehensive | 30s | ✅ | 0.8 | Exponential | 20-25s |

## Performance Optimization Tips

### Frontend Optimization
- Enable React DevTools Profiler in development
- Monitor component re-renders during streaming
- Use React.memo for expensive visualizations
- Implement virtualization for large result lists

### Backend Optimization  
- Monitor LangGraph node execution times
- Track middleware overhead
- Analyze parallel execution efficiency
- Profile SSE event generation

### Network Optimization
- Use browser caching for static assets
- Implement SSE connection pooling
- Monitor WebSocket upgrade success rates
- Track reconnection frequency

## Troubleshooting Common Performance Issues

### Slow Query Execution
1. Check budget allocation vs actual usage
2. Verify parallel execution is enabled
3. Monitor individual source latencies
4. Review error recovery overhead

### High Memory Usage
1. Clear old SSE event histories
2. Implement result pagination
3. Use React lazy loading
4. Monitor middleware state size

### SSE Connection Issues  
1. Verify CORS configuration
2. Check network firewall rules
3. Monitor connection retry logic
4. Validate event parsing performance
```

### 📁 Files to Create
- `bioinvest-copilot-poc/DEMO_SCENARIOS.md` (new)
- `bioinvest-copilot-poc/USER_GUIDE.md` (new)
- `bioinvest-copilot-poc/PERFORMANCE_GUIDE.md` (new)
- `bioinvest-copilot-poc/TROUBLESHOOTING.md` (new)
- `frontend/src/data/demo-queries.ts` (new)

### 🧪 Testing Requirements
- [ ] All demo scenarios execute successfully
- [ ] Documentation accuracy verified
- [ ] Performance benchmarks match guide recommendations
- [ ] Troubleshooting steps resolve common issues
- [ ] Demo queries produce expected results

---

## 📍 Milestone 8: Polish & Optimization
**Duration**: 1-2 days | **Priority**: Medium | **Risk**: Low

### 🎯 Goal
Final production-ready polish including UI/UX refinements, performance optimization, and accessibility improvements.

### ✅ Success Criteria
- [ ] Smooth animations and loading states
- [ ] Optimized bundle size (<2MB)
- [ ] WCAG 2.1 AA accessibility compliance
- [ ] Cross-browser compatibility (Chrome, Firefox, Safari, Edge)
- [ ] Mobile responsive design

### 🔧 Technical Tasks

#### 8.1 UI/UX Polish

```typescript
// Enhanced loading states and transitions
const QueryBuilder: React.FC = () => {
  return (
    <div className="query-builder">
      {/* Smooth transitions */}
      <Transition
        show={showAdvanced}
        enter="transition-all duration-300 ease-in-out"
        enterFrom="opacity-0 max-h-0"
        enterTo="opacity-100 max-h-96"
        leave="transition-all duration-300 ease-in-out"
        leaveFrom="opacity-100 max-h-96"
        leaveTo="opacity-0 max-h-0"
      >
        <AdvancedOptionsPanel />
      </Transition>
      
      {/* Enhanced loading button */}
      <Button 
        disabled={isLoading}
        className="relative overflow-hidden"
      >
        {isLoading && (
          <div className="absolute inset-0 bg-gradient-to-r from-blue-500 to-purple-500 opacity-20 animate-pulse" />
        )}
        {isLoading ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            Analyzing...
          </>
        ) : (
          'Submit Query'
        )}
      </Button>
    </div>
  );
};
```

#### 8.2 Performance Optimization

```typescript
// Component memoization
const BudgetMonitor = React.memo<BudgetMonitorProps>(({ status }) => {
  // Memoize expensive calculations
  const dangerLevel = useMemo(() => getDangerLevel(status.utilization), [status.utilization]);
  const timeRemaining = useMemo(() => Math.round(status.remaining_ms / 1000), [status.remaining_ms]);
  
  return (
    <Card className="budget-monitor">
      {/* Optimized progress bar */}
      <Progress 
        value={status.utilization * 100} 
        className={`budget-progress ${dangerLevel}`}
      />
    </Card>
  );
});

// SSE connection management
const useStreamingResults = (options: StreamingOptions) => {
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  
  const connect = useCallback(() => {
    if (!options.streamUrl) return;
    
    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    // Create new connection with retry logic
    const eventSource = new EventSource(options.streamUrl);
    eventSource.addEventListener('error', () => {
      // Exponential backoff reconnection
      const delay = Math.min(1000 * Math.pow(2, retryCount), 30000);
      reconnectTimeoutRef.current = setTimeout(connect, delay);
    });
    
    eventSourceRef.current = eventSource;
  }, [options.streamUrl]);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, []);
};
```

#### 8.3 Accessibility Improvements

```tsx
// Enhanced accessibility
const RetryVisualizer: React.FC<RetryVisualizerProps> = ({ attempts }) => {
  return (
    <Card 
      className="retry-visualizer"
      role="region"
      aria-labelledby="retry-visualizer-title"
    >
      <CardHeader>
        <CardTitle id="retry-visualizer-title">
          Error Recovery
          <span className="sr-only">
            {attempts.length} retry attempts in progress
          </span>
        </CardTitle>
      </CardHeader>
      
      <CardContent>
        {attempts.map((attempt, index) => (
          <div 
            key={index}
            role="status"
            aria-live="polite"
            aria-label={`Retry attempt ${attempt.attempt} of ${attempt.max_attempts} for ${attempt.node}`}
          >
            {/* Accessible retry visualization */}
            <div className="flex items-center gap-3">
              <RotateCcw 
                className="h-3 w-3 animate-spin" 
                aria-hidden="true"
              />
              <div className="flex-1">
                <div className="font-medium text-sm">
                  {attempt.node} 
                  <span className="sr-only">
                    attempting retry {attempt.attempt} of {attempt.max_attempts}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

// Keyboard navigation
const useKeyboardNavigation = () => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Escape to close modals/panels
      if (event.key === 'Escape') {
        // Close any open panels
      }
      
      // Ctrl/Cmd + Enter to submit query
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        // Submit current query
      }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);
};
```

#### 8.4 Bundle Optimization

```typescript
// Webpack bundle analysis and optimization
import { lazy, Suspense } from 'react';

// Code splitting for heavy components
const LangGraphVisualizer = lazy(() => import('./LangGraphVisualizer'));
const MiddlewareStatusPanel = lazy(() => import('./MiddlewareStatusPanel'));

// Dynamic imports for demo data
const loadDemoQueries = () => import('../data/demo-queries');

// Tree shaking optimization
export {
  BudgetMonitor,
  RetryVisualizer,
  SynthesisProgress,
  QualityScoreDisplay,
  CitationManager
} from './monitoring';

// Lazy loading with suspense
const ResearchWorkspace: React.FC = () => {
  return (
    <div className="research-workspace">
      {showVisualization && (
        <Suspense fallback={<div>Loading visualization...</div>}>
          <LangGraphVisualizer />
          <MiddlewareStatusPanel />
        </Suspense>
      )}
    </div>
  );
};
```

### 📁 Files to Modify
- All component files for polish improvements
- `frontend/src/hooks/useKeyboardNavigation.ts` (new)
- `frontend/vite.config.ts` (bundle optimization)
- `frontend/src/utils/accessibility.ts` (new)

### 🧪 Testing Requirements
- [ ] Bundle size under 2MB
- [ ] Lighthouse performance score >90
- [ ] WCAG 2.1 AA compliance verified
- [ ] Cross-browser testing completed
- [ ] Mobile responsiveness validated

---

## 📈 Success Metrics & KPIs

### Performance Targets
- **Query Execution**: 2x faster with parallel execution
- **SSE Latency**: <100ms event processing
- **Error Recovery**: >95% success rate
- **Bundle Size**: <2MB total
- **Lighthouse Score**: >90 performance

### User Experience Metrics  
- **Feature Adoption**: >80% users try advanced options
- **Demo Completion**: >90% demo scenarios complete successfully
- **Error Rates**: <5% unhandled errors
- **Accessibility**: WCAG 2.1 AA compliance
- **Cross-browser**: 100% feature compatibility

### Technical Quality
- **Test Coverage**: >80% for new components
- **Type Safety**: 100% TypeScript coverage
- **Code Quality**: ESLint/Prettier compliance
- **Documentation**: 100% API endpoint documentation
- **Integration**: All M3/M4 features functional

---

## 🚀 Total Implementation Timeline

### **Days 1-3: Foundation** (Milestones 1-2)
- ✅ **M1 COMPLETED (Day 1)**: Type definitions and API updates  
- ✅ **M2 COMPLETED (Day 1)**: Enhanced Query Builder with advanced options
- 🎯 **Goal**: All M3/M4 options accessible via UI ✅ **ACHIEVED**

### **Days 4-8: Core Features** (Milestones 3-4)  
- ✅ **M3 COMPLETED (Day 4)**: Real-time monitoring dashboard with all components
- ✅ **M4 COMPLETED (Day 4)**: Enhanced results display with quality scores and citations
- 🎯 **Goal**: Complete visualization of orchestration process ✅ **ACHIEVED**

### **Days 9-12: Advanced Features** (Milestone 5)
- ✅ **M5 COMPLETED (Day 5)**: LangGraph workflow visualization with interactive components
- ✅ **M5 COMPLETED (Day 5)**: Middleware status monitoring with real-time metrics
- 🎯 **Goal**: Full transparency into execution flow ✅ **ACHIEVED**

### **Days 13-15: Quality Assurance** (Milestone 6)
- ✅ Comprehensive integration testing
- ✅ Performance benchmarking  
- 🎯 **Goal**: Production-ready reliability

### **Days 16-18: Documentation & Demo** (Milestone 7)
- ✅ Demo scenarios and user guides
- ✅ Performance tuning documentation
- 🎯 **Goal**: Compelling demonstration materials

### **Days 19-20: Polish** (Milestone 8)
- ✅ UI/UX refinements and optimization
- ✅ Accessibility and cross-browser support
- 🎯 **Goal**: Production-ready user experience

---

## 🎯 Immediate Next Steps

1. **Start with Milestone 1**: Update TypeScript definitions and API layer
2. **Use existing backend**: All M3/M4 backend features are already implemented
3. **Follow progressive enhancement**: Each milestone builds on the previous
4. **Test continuously**: Run E2E tests after each major component
5. **Document as you go**: Update README and user guides during implementation

This milestone plan transforms the BioInvest Copilot POC from a basic demonstration into a comprehensive showcase of production-ready M0-M4 orchestration capabilities, providing a compelling demonstration of advanced biomedical research workflows.
import React, { useState } from 'react'
import { Search, Settings, Zap, Clock, Target, Timer, Shield, RotateCcw, Layers, Award, Bookmark } from 'lucide-react'
import { EnhancedOrchestrationRequest } from '@/shared-types'

interface QueryBuilderProps {
  onSubmit: (request: EnhancedOrchestrationRequest) => void
  isLoading: boolean
}

const QueryBuilder: React.FC<QueryBuilderProps> = ({ onSubmit, isLoading }) => {
  const [query, setQuery] = useState('')
  const [sources, setSources] = useState(['pubmed', 'clinical_trials', 'rag'])
  const [maxResults, setMaxResults] = useState(50)
  const [includeSynthesis, setIncludeSynthesis] = useState(true)
  const [priority, setPriority] = useState<'speed' | 'comprehensive' | 'balanced'>('balanced')
  const [showAdvanced, setShowAdvanced] = useState(false)

  // M3 Advanced State Management Options
  const [budgetMs, setBudgetMs] = useState<number>(15000)
  const [enablePartialResults, setEnablePartialResults] = useState(true)
  const [retryStrategy, setRetryStrategy] = useState<'exponential' | 'linear' | 'none'>('exponential')
  const [parallelExecution, setParallelExecution] = useState(true)

  // M4 Synthesis Options
  const [citationFormat, setCitationFormat] = useState<'pmid' | 'full' | 'inline'>('full')
  const [qualityThreshold, setQualityThreshold] = useState<number>(0.7)
  const [checkpointEnabled, setCheckpointEnabled] = useState(true)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    const request: EnhancedOrchestrationRequest = {
      query: query.trim(),
      sources,
      options: {
        // Basic Options
        max_results_per_source: maxResults,
        include_synthesis: includeSynthesis,
        priority,
        
        // M3 Advanced State Management (only include if different from defaults)
        ...(budgetMs !== 15000 && { budget_ms: budgetMs }),
        ...(enablePartialResults !== true && { enable_partial_results: enablePartialResults }),
        ...(retryStrategy !== 'exponential' && { retry_strategy: retryStrategy }),
        ...(parallelExecution !== true && { parallel_execution: parallelExecution }),
        
        // M4 Synthesis Options (only include if different from defaults)
        ...(citationFormat !== 'full' && { citation_format: citationFormat }),
        ...(qualityThreshold !== 0.7 && { quality_threshold: qualityThreshold }),
        ...(checkpointEnabled !== true && { checkpoint_enabled: checkpointEnabled }),
      },
    }

    onSubmit(request)
  }

  const handleSourceToggle = (source: string) => {
    setSources(prev =>
      prev.includes(source)
        ? prev.filter(s => s !== source)
        : [...prev, source]
    )
  }

  const exampleQueries = [
    "GLP-1 market competitive analysis and Novo Nordisk positioning",
    "Alzheimer's disease drug development pipeline and investment opportunities",
    "CAR-T cell therapy clinical trial success rates and market forecast",
    "CRISPR gene editing commercialization timeline and regulatory landscape"
  ]

  return (
    <div className="card p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-blue-100 rounded-lg">
          <Search className="h-6 w-6 text-blue-600" />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Research Query</h2>
          <p className="text-sm text-gray-600">
            Ask questions about biotech investments, clinical trials, or market analysis
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Query Input */}
        <div>
          <label htmlFor="query" className="block text-sm font-medium text-gray-700 mb-2">
            Research Question
          </label>
          <textarea
            id="query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., Analyze the competitive landscape for GLP-1 diabetes drugs and assess Novo Nordisk's market position..."
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            rows={3}
            disabled={isLoading}
          />
          <div className="mt-2 text-sm text-gray-500">
            Be specific about what insights you're looking for - market analysis, competitive positioning, clinical outcomes, etc.
          </div>
        </div>

        {/* Example Queries */}
        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">Example queries:</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {exampleQueries.map((example, index) => (
              <button
                key={index}
                type="button"
                onClick={() => setQuery(example)}
                className="text-left text-sm text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-3 py-2 rounded-md transition-colors"
                disabled={isLoading}
              >
                {example}
              </button>
            ))}
          </div>
        </div>

        {/* Data Sources */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">Data Sources</label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <label className="flex items-center p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
              <input
                type="checkbox"
                checked={sources.includes('pubmed')}
                onChange={() => handleSourceToggle('pubmed')}
                className="mr-3 h-4 w-4 text-blue-600"
                disabled={isLoading}
              />
              <div>
                <div className="font-medium text-sm">PubMed</div>
                <div className="text-xs text-gray-500">Scientific literature</div>
              </div>
            </label>
            
            <label className="flex items-center p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
              <input
                type="checkbox"
                checked={sources.includes('clinical_trials')}
                onChange={() => handleSourceToggle('clinical_trials')}
                className="mr-3 h-4 w-4 text-blue-600"
                disabled={isLoading}
              />
              <div>
                <div className="font-medium text-sm">Clinical Trials</div>
                <div className="text-xs text-gray-500">ClinicalTrials.gov data</div>
              </div>
            </label>

            <label className="flex items-center p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
              <input
                type="checkbox"
                checked={sources.includes('rag')}
                onChange={() => handleSourceToggle('rag')}
                className="mr-3 h-4 w-4 text-blue-600"
                disabled={isLoading}
              />
              <div>
                <div className="font-medium text-sm">Internal Database</div>
                <div className="text-xs text-gray-500">Proprietary insights</div>
              </div>
            </label>
          </div>
        </div>

        {/* Advanced Options */}
        <div>
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
            disabled={isLoading}
          >
            <Settings className="h-4 w-4" />
            Advanced Options
            <span className="text-xs text-gray-500">
              {showAdvanced ? '(hide)' : '(show)'}
            </span>
          </button>

          {showAdvanced && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg space-y-6">
              {/* Priority Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Analysis Priority</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { value: 'speed', icon: Zap, label: 'Speed', desc: 'Quick overview' },
                    { value: 'balanced', icon: Target, label: 'Balanced', desc: 'Balanced depth' },
                    { value: 'comprehensive', icon: Clock, label: 'Comprehensive', desc: 'Deep analysis' }
                  ].map(({ value, icon: Icon, label, desc }) => (
                    <label key={value} className="cursor-pointer">
                      <input
                        type="radio"
                        name="priority"
                        value={value}
                        checked={priority === value}
                        onChange={(e) => setPriority(e.target.value as any)}
                        className="sr-only"
                        disabled={isLoading}
                      />
                      <div className={`p-3 border rounded-lg text-center transition-colors ${
                        priority === value
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-200 hover:bg-gray-100'
                      }`}>
                        <Icon className="h-4 w-4 mx-auto mb-1" />
                        <div className="text-xs font-medium">{label}</div>
                        <div className="text-xs text-gray-500">{desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Basic Options */}
              <div className="space-y-4">
                {/* Max Results */}
                <div>
                  <label htmlFor="maxResults" className="block text-sm font-medium text-gray-700 mb-2">
                    Max Results Per Source: {maxResults}
                  </label>
                  <input
                    id="maxResults"
                    type="range"
                    min="10"
                    max="100"
                    step="10"
                    value={maxResults}
                    onChange={(e) => setMaxResults(parseInt(e.target.value))}
                    className="w-full"
                    disabled={isLoading}
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>10 (faster)</span>
                    <span>100 (comprehensive)</span>
                  </div>
                </div>

                {/* Include Synthesis */}
                <div>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={includeSynthesis}
                      onChange={(e) => setIncludeSynthesis(e.target.checked)}
                      className="mr-2 h-4 w-4 text-blue-600"
                      disabled={isLoading}
                    />
                    <span className="text-sm font-medium text-gray-700">
                      Include AI Synthesis
                    </span>
                  </label>
                  <p className="text-xs text-gray-500 ml-6">
                    Generate insights, competitive analysis, and recommendations
                  </p>
                </div>
              </div>

              {/* M3 Advanced State Management */}
              <div className="border-t pt-4">
                <div className="flex items-center gap-2 mb-4">
                  <Shield className="h-4 w-4 text-green-600" />
                  <h4 className="text-sm font-semibold text-gray-800">Advanced State Management</h4>
                  <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">M3</span>
                </div>
                
                <div className="space-y-4">
                  {/* Budget Control */}
                  <div>
                    <label htmlFor="budget" className="block text-sm font-medium text-gray-700 mb-2">
                      <Timer className="h-4 w-4 inline mr-1" />
                      Budget Limit: {budgetMs}ms ({(budgetMs/1000).toFixed(1)}s)
                    </label>
                    <input
                      id="budget"
                      type="range"
                      min="5000"
                      max="30000"
                      step="1000"
                      value={budgetMs}
                      onChange={(e) => setBudgetMs(parseInt(e.target.value))}
                      className="w-full"
                      disabled={isLoading}
                    />
                    <div className="flex justify-between text-xs text-gray-500 mt-1">
                      <span>5s (fast)</span>
                      <span>30s (thorough)</span>
                    </div>
                  </div>

                  {/* Execution Strategy */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={parallelExecution}
                          onChange={(e) => setParallelExecution(e.target.checked)}
                          className="mr-2 h-4 w-4 text-blue-600"
                          disabled={isLoading}
                        />
                        <Layers className="h-4 w-4 mr-1" />
                        <span className="text-sm font-medium text-gray-700">
                          Parallel Execution
                        </span>
                      </label>
                      <p className="text-xs text-gray-500 ml-6">
                        ~2x faster with concurrent searches
                      </p>
                    </div>

                    <div>
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={enablePartialResults}
                          onChange={(e) => setEnablePartialResults(e.target.checked)}
                          className="mr-2 h-4 w-4 text-blue-600"
                          disabled={isLoading}
                        />
                        <Target className="h-4 w-4 mr-1" />
                        <span className="text-sm font-medium text-gray-700">
                          Partial Results
                        </span>
                      </label>
                      <p className="text-xs text-gray-500 ml-6">
                        Return available data if timeout occurs
                      </p>
                    </div>
                  </div>

                  {/* Retry Strategy */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      <RotateCcw className="h-4 w-4 inline mr-1" />
                      Retry Strategy
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { value: 'exponential', label: 'Exponential', desc: 'Smart backoff' },
                        { value: 'linear', label: 'Linear', desc: 'Fixed delays' },
                        { value: 'none', label: 'None', desc: 'No retries' }
                      ].map(({ value, label, desc }) => (
                        <label key={value} className="cursor-pointer">
                          <input
                            type="radio"
                            name="retryStrategy"
                            value={value}
                            checked={retryStrategy === value}
                            onChange={(e) => setRetryStrategy(e.target.value as any)}
                            className="sr-only"
                            disabled={isLoading}
                          />
                          <div className={`p-2 border rounded text-center transition-colors ${
                            retryStrategy === value
                              ? 'border-green-500 bg-green-50 text-green-700'
                              : 'border-gray-200 hover:bg-gray-100'
                          }`}>
                            <div className="text-xs font-medium">{label}</div>
                            <div className="text-xs text-gray-500">{desc}</div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* M4 Synthesis Options */}
              <div className="border-t pt-4">
                <div className="flex items-center gap-2 mb-4">
                  <Award className="h-4 w-4 text-purple-600" />
                  <h4 className="text-sm font-semibold text-gray-800">Advanced Synthesis</h4>
                  <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded-full">M4</span>
                </div>
                
                <div className="space-y-4">
                  {/* Citation Format */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Citation Format</label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { value: 'pmid', label: 'PMID', desc: 'Numbers only' },
                        { value: 'full', label: 'Full', desc: 'Complete citation' },
                        { value: 'inline', label: 'Inline', desc: 'Author (year)' }
                      ].map(({ value, label, desc }) => (
                        <label key={value} className="cursor-pointer">
                          <input
                            type="radio"
                            name="citationFormat"
                            value={value}
                            checked={citationFormat === value}
                            onChange={(e) => setCitationFormat(e.target.value as any)}
                            className="sr-only"
                            disabled={isLoading}
                          />
                          <div className={`p-2 border rounded text-center transition-colors ${
                            citationFormat === value
                              ? 'border-purple-500 bg-purple-50 text-purple-700'
                              : 'border-gray-200 hover:bg-gray-100'
                          }`}>
                            <div className="text-xs font-medium">{label}</div>
                            <div className="text-xs text-gray-500">{desc}</div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Quality Controls */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="quality" className="block text-sm font-medium text-gray-700 mb-2">
                        Quality Threshold: {(qualityThreshold * 100).toFixed(0)}%
                      </label>
                      <input
                        id="quality"
                        type="range"
                        min="0.3"
                        max="0.9"
                        step="0.1"
                        value={qualityThreshold}
                        onChange={(e) => setQualityThreshold(parseFloat(e.target.value))}
                        className="w-full"
                        disabled={isLoading}
                      />
                      <div className="flex justify-between text-xs text-gray-500 mt-1">
                        <span>30% (inclusive)</span>
                        <span>90% (strict)</span>
                      </div>
                    </div>

                    <div className="flex items-center">
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={checkpointEnabled}
                          onChange={(e) => setCheckpointEnabled(e.target.checked)}
                          className="mr-2 h-4 w-4 text-blue-600"
                          disabled={isLoading}
                        />
                        <Bookmark className="h-4 w-4 mr-1" />
                        <span className="text-sm font-medium text-gray-700">
                          Enable Checkpoints
                        </span>
                      </label>
                      <p className="text-xs text-gray-500 ml-6">
                        Save progress for reproducible results
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Submit Button */}
        <div className="pt-4">
          <button
            type="submit"
            disabled={isLoading || !query.trim() || sources.length === 0}
            className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
                Processing Research...
              </>
            ) : (
              <>
                <Search className="h-4 w-4" />
                Start Research Analysis
              </>
            )}
          </button>
          {sources.length === 0 && (
            <p className="text-sm text-red-600 mt-2">
              Please select at least one data source
            </p>
          )}
        </div>
      </form>
    </div>
  )
}

export default QueryBuilder
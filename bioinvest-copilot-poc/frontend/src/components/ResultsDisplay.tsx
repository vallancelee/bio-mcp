import React, { useState } from 'react'
import { 
  FileText, 
  Activity, 
  Database, 
  TrendingUp, 
  AlertTriangle, 
  Target, 
  ExternalLink,
  ChevronDown,
  ChevronRight,
  BarChart3,
  Award,
  Calendar,
  Users
} from 'lucide-react'
import { QueryResults, PubMedResult, ClinicalTrialResult, RAGResult } from '@/shared-types'
import { format } from 'date-fns'
import QualityScoreDisplay, { QualityMetrics } from './QualityScoreDisplay'
import CitationManager, { Citation, CitationFormat } from './CitationManager'
import PartialResultsIndicator, { PartialResultsData } from './PartialResultsIndicator'

interface ResultsDisplayProps {
  results: QueryResults | null
  partialResults?: PartialResultsData
}

const ResultsDisplay: React.FC<ResultsDisplayProps> = ({ results, partialResults }) => {
  const [activeTab, setActiveTab] = useState<'summary' | 'pubmed' | 'trials' | 'insights'>('summary')
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())
  const [citationFormat, setCitationFormat] = useState<CitationFormat>('full')

  if (!results) {
    return (
      <div className="card p-8 text-center">
        <Database className="h-12 w-12 mx-auto mb-4 text-gray-400" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No Results Yet</h3>
        <p className="text-gray-600">Submit a research query to see detailed analysis and insights</p>
      </div>
    )
  }

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedItems)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedItems(newExpanded)
  }

  const getQualityColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600 bg-green-100'
    if (score >= 0.6) return 'text-yellow-600 bg-yellow-100'
    return 'text-red-600 bg-red-100'
  }

  const renderSynthesisSummary = () => {
    if (!results.synthesis) {
      return (
        <div className="text-center py-8">
          <TrendingUp className="h-12 w-12 mx-auto mb-4 text-gray-400" />
          <p className="text-gray-600">AI synthesis not available for this query</p>
        </div>
      )
    }

    const { synthesis } = results

    // Convert citations to proper format
    const formattedCitations: Citation[] = synthesis.citations?.map(citation => ({
      id: citation.pmid || citation.id || 'unknown',
      title: citation.title || 'Unknown title',
      authors: citation.authors || [],
      source: citation.journal || citation.source || 'Unknown source',
      year: citation.year?.toString() || 'Unknown year',
      url: citation.url,
      relevance_score: citation.relevance_score || 0.5
    })) || []

    return (
      <div className="space-y-6">
        {/* Quality Score Display */}
        <QualityScoreDisplay metrics={synthesis.quality_metrics as QualityMetrics} />

        {/* Executive Summary */}
        <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              AI Synthesis
            </h3>
          </div>
          <div className="px-6 py-4">
            <div className="prose max-w-none">
              <p className="text-gray-700 leading-relaxed">{synthesis.summary}</p>
            </div>
          </div>
        </div>

        {/* Citations Manager */}
        {formattedCitations.length > 0 && (
          <CitationManager
            citations={formattedCitations}
            format={citationFormat}
            onFormatChange={setCitationFormat}
          />
        )}

        {/* Checkpoint Information */}
        {synthesis.generation_metadata?.checkpoint_id && (
          <div className="mt-4">
            <span className="inline-flex items-center px-2 py-1 rounded border border-gray-300 text-xs">
              Checkpoint: {synthesis.generation_metadata.checkpoint_id}
            </span>
          </div>
        )}

        {/* Key Insights */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Target className="h-5 w-5" />
            Key Insights
          </h3>
          <div className="space-y-4">
            {synthesis.key_insights.map((insight, index) => (
              <div key={index} className="border-l-4 border-blue-500 pl-4">
                <div className="flex items-center justify-between mb-2">
                  <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
                    insight.category === 'competitive_threat' ? 'bg-red-100 text-red-800' :
                    insight.category === 'market_opportunity' ? 'bg-green-100 text-green-800' :
                    insight.category === 'patent_risk' ? 'bg-orange-100 text-orange-800' :
                    'bg-blue-100 text-blue-800'
                  }`}>
                    {insight.category.replace('_', ' ')}
                  </span>
                  <span className="text-sm font-medium text-gray-600">
                    {Math.round(insight.confidence * 100)}% confidence
                  </span>
                </div>
                <p className="text-gray-900 font-medium mb-2">{insight.insight}</p>
                <ul className="text-sm text-gray-600 space-y-1">
                  {insight.supporting_evidence.map((evidence, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-gray-400 mt-1">•</span>
                      {evidence}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Competitive Analysis */}
        {synthesis.competitive_analysis && (
          <div className="card p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Competitive Analysis
            </h3>
            
            <div className="mb-6">
              <h4 className="font-medium text-gray-900 mb-3">Market Position</h4>
              <p className="text-gray-700">{synthesis.competitive_analysis?.market_position}</p>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-medium text-gray-900 mb-3">Direct Competitors</h4>
                <div className="space-y-3">
                  {synthesis.competitive_analysis?.direct_competitors?.map((competitor, index) => (
                    <div key={index} className="border rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">{competitor.company}</span>
                        <span className={`px-2 py-1 rounded-full text-xs ${
                          competitor.threat_level === 'high' ? 'bg-red-100 text-red-800' :
                          competitor.threat_level === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-green-100 text-green-800'
                        }`}>
                          {competitor.threat_level} threat
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-1">
                        <strong>{competitor.drug}</strong> ({competitor.brand})
                      </p>
                      <p className="text-sm text-gray-700">{competitor.competitive_advantage}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-medium text-gray-900 mb-3">Risk Assessment</h4>
                <div className="space-y-3">
                  {synthesis.competitive_analysis?.risks?.map((risk, index) => (
                    <div key={index} className="border rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium capitalize">
                          {risk.factor.replace('_', ' ')}
                        </span>
                        <span className={`px-2 py-1 rounded-full text-xs ${
                          risk.severity === 'high' ? 'bg-red-100 text-red-800' :
                          risk.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-green-100 text-green-800'
                        }`}>
                          {risk.severity}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-1">
                        Impact: <strong>{Math.round(Math.abs(risk.impact) * 100)}%</strong> negative
                      </p>
                      <p className="text-sm text-gray-700">{risk.explanation}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Recommendations */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Strategic Recommendations
          </h3>
          <div className="space-y-3">
            {synthesis.recommendations.map((recommendation, index) => (
              <div key={index} className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg">
                <span className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white text-sm font-medium rounded-full flex items-center justify-center">
                  {index + 1}
                </span>
                <p className="text-gray-900">{recommendation}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  const renderPubMedResults = () => {
    const pubmedResults = results.results.pubmed?.results || []
    
    if (pubmedResults.length === 0) {
      return (
        <div className="text-center py-8">
          <FileText className="h-12 w-12 mx-auto mb-4 text-gray-400" />
          <p className="text-gray-600">No PubMed results available</p>
        </div>
      )
    }

    return (
      <div className="space-y-4">
        {pubmedResults.map((article: PubMedResult, _) => (
          <div key={article.pmid} className="card p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <h4 className="text-lg font-semibold text-gray-900 mb-2">
                  {article.title}
                </h4>
                <div className="flex items-center gap-4 text-sm text-gray-600 mb-3">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-4 w-4" />
                    {article.publication_date}
                  </span>
                  <span className="flex items-center gap-1">
                    <Award className="h-4 w-4" />
                    IF: {article.impact_factor}
                  </span>
                  <span className="flex items-center gap-1">
                    <Users className="h-4 w-4" />
                    {article.citation_count} citations
                  </span>
                </div>
                <p className="text-gray-600 mb-3">{article.journal}</p>
                <p className="text-sm text-gray-700">{article.authors.join(', ')}</p>
              </div>
              <div className="flex flex-col items-end gap-2">
                <div className={`px-3 py-1 rounded-full text-sm font-medium ${getQualityColor(article.relevance_score)}`}>
                  {Math.round(article.relevance_score * 100)}% relevance
                </div>
                <a
                  href={`https://pubmed.ncbi.nlm.nih.gov/${article.pmid}/`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-blue-600 hover:text-blue-800 text-sm"
                >
                  View <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
            
            <div>
              <button
                onClick={() => toggleExpanded(`pubmed-${article.pmid}`)}
                className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 mb-2"
              >
                {expandedItems.has(`pubmed-${article.pmid}`) ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                Abstract
              </button>
              
              {expandedItems.has(`pubmed-${article.pmid}`) && (
                <div className="pl-6 pb-4">
                  <p className="text-sm text-gray-700 leading-relaxed mb-4">
                    {article.abstract}
                  </p>
                  {article.keywords.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {article.keywords.map((keyword, idx) => (
                        <span key={idx} className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded">
                          {keyword}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    )
  }

  const renderClinicalTrials = () => {
    const trialsResults = results.results.clinical_trials?.studies || []
    
    if (trialsResults.length === 0) {
      return (
        <div className="text-center py-8">
          <Activity className="h-12 w-12 mx-auto mb-4 text-gray-400" />
          <p className="text-gray-600">No clinical trials results available</p>
        </div>
      )
    }

    return (
      <div className="space-y-4">
        {trialsResults.map((trial: ClinicalTrialResult, _) => (
          <div key={trial.nct_id} className="card p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <h4 className="text-lg font-semibold text-gray-900 mb-2">
                  {trial.title}
                </h4>
                <div className="flex items-center gap-4 text-sm text-gray-600 mb-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    trial.phase.includes('3') ? 'bg-green-100 text-green-800' :
                    trial.phase.includes('2') ? 'bg-yellow-100 text-yellow-800' :
                    'bg-blue-100 text-blue-800'
                  }`}>
                    {trial.phase}
                  </span>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    trial.status === 'Completed' ? 'bg-green-100 text-green-800' :
                    trial.status === 'Active' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {trial.status}
                  </span>
                  <span className="flex items-center gap-1">
                    <Users className="h-4 w-4" />
                    {trial.enrollment.actual || trial.enrollment.target} participants
                  </span>
                </div>
                <p className="text-gray-600 mb-2">{trial.sponsors.lead_sponsor}</p>
                <p className="text-sm text-gray-700">{trial.conditions.join(', ')}</p>
              </div>
              <div className="flex flex-col items-end gap-2">
                <div className={`px-3 py-1 rounded-full text-sm font-medium ${getQualityColor(trial.relevance_score)}`}>
                  {Math.round(trial.relevance_score * 100)}% relevance
                </div>
                <a
                  href={`https://clinicaltrials.gov/ct2/show/${trial.nct_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-blue-600 hover:text-blue-800 text-sm"
                >
                  View <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
            
            <div>
              <button
                onClick={() => toggleExpanded(`trial-${trial.nct_id}`)}
                className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 mb-2"
              >
                {expandedItems.has(`trial-${trial.nct_id}`) ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                Details
              </button>
              
              {expandedItems.has(`trial-${trial.nct_id}`) && (
                <div className="pl-6 pb-4 space-y-3">
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {trial.brief_summary}
                  </p>
                  <div className="grid md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <p><strong>Primary Endpoint:</strong> {trial.primary_endpoint}</p>
                      <p><strong>Start Date:</strong> {format(new Date(trial.dates.start_date), 'MMM dd, yyyy')}</p>
                      {trial.dates.completion_date && (
                        <p><strong>Completion:</strong> {format(new Date(trial.dates.completion_date), 'MMM dd, yyyy')}</p>
                      )}
                    </div>
                    <div>
                      <p><strong>Interventions:</strong> {trial.interventions.join(', ')}</p>
                      {trial.locations.length > 0 && (
                        <p><strong>Locations:</strong> {trial.locations[0].city}, {trial.locations[0].country}</p>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    )
  }

  const renderInsights = () => {
    const ragResults = results.results.rag?.documents || []
    
    if (ragResults.length === 0) {
      return (
        <div className="text-center py-8">
          <Database className="h-12 w-12 mx-auto mb-4 text-gray-400" />
          <p className="text-gray-600">No internal insights available</p>
        </div>
      )
    }

    return (
      <div className="space-y-4">
        {ragResults.map((doc: RAGResult, _) => (
          <div key={doc.doc_id} className="card p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <h4 className="text-lg font-semibold text-gray-900 mb-2">
                  {doc.title}
                </h4>
                <div className="flex items-center gap-4 text-sm text-gray-600 mb-3">
                  <span>{doc.source}</span>
                  <span>{doc.metadata.document_type.replace('_', ' ')}</span>
                  <span>{doc.metadata.created_date}</span>
                </div>
              </div>
              <div className={`px-3 py-1 rounded-full text-sm font-medium ${getQualityColor(doc.relevance_score)}`}>
                {Math.round(doc.relevance_score * 100)}% relevance
              </div>
            </div>
            
            <div>
              <button
                onClick={() => toggleExpanded(`rag-${doc.doc_id}`)}
                className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 mb-2"
              >
                {expandedItems.has(`rag-${doc.doc_id}`) ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                Content
              </button>
              
              {expandedItems.has(`rag-${doc.doc_id}`) && (
                <div className="pl-6 pb-4">
                  <p className="text-sm text-gray-700 leading-relaxed mb-4">
                    {doc.content}
                  </p>
                  {doc.chunks.length > 0 && (
                    <div className="space-y-2">
                      <h5 className="text-sm font-medium text-gray-900">Relevant Sections:</h5>
                      {doc.chunks.map((chunk, _) => (
                        <div key={chunk.chunk_id} className="bg-gray-50 p-3 rounded">
                          <p className="text-sm text-gray-700">{chunk.text}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    )
  }

  const tabs = [
    { id: 'summary', label: 'AI Summary', icon: TrendingUp, count: results.synthesis ? 1 : 0 },
    { id: 'pubmed', label: 'Literature', icon: FileText, count: results.results.pubmed?.results.length || 0 },
    { id: 'trials', label: 'Clinical Trials', icon: Activity, count: results.results.clinical_trials?.studies.length || 0 },
    { id: 'insights', label: 'Internal Insights', icon: Database, count: results.results.rag?.documents.length || 0 },
  ]

  return (
    <div className="space-y-6">
      {/* Partial Results Indicator */}
      {partialResults && (
        <PartialResultsIndicator data={partialResults} />
      )}

      {/* Query Header */}
      <div className="card p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Research Results
        </h2>
        <p className="text-gray-600 mb-4">"{results.query}"</p>
        <div className="flex items-center gap-4 text-sm text-gray-500">
          <span>Query ID: {results.query_id}</span>
          <span>Status: {results.status}</span>
          {results.completed_at && (
            <span>
              Completed: {format(new Date(results.completed_at), 'MMM dd, yyyy HH:mm')}
            </span>
          )}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="card">
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8 px-6">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                  {tab.count > 0 && (
                    <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded-full text-xs">
                      {tab.count}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'summary' && renderSynthesisSummary()}
          {activeTab === 'pubmed' && renderPubMedResults()}
          {activeTab === 'trials' && renderClinicalTrials()}
          {activeTab === 'insights' && renderInsights()}
        </div>
      </div>
    </div>
  )
}

export default ResultsDisplay
/**
 * QualityScoreDisplay Component
 * 
 * Displays investment-grade quality metrics for biomedical research results
 * Shows overall quality score with detailed breakdown of individual metrics
 */

import React from 'react'
import { Star } from 'lucide-react'

export interface QualityMetrics {
  completeness: number
  recency: number
  authority: number
  diversity: number
  relevance: number
  overall_score: number
}

interface QualityScoreDisplayProps {
  metrics: QualityMetrics
}

const QualityScoreDisplay: React.FC<QualityScoreDisplayProps> = ({ metrics }) => {
  const getScoreColor = (score: number): string => {
    if (score >= 0.8) return 'text-green-600 bg-green-100'
    if (score >= 0.6) return 'text-yellow-600 bg-yellow-100'
    return 'text-red-600 bg-red-100'
  }

  const getInvestmentGradeText = (score: number): string => {
    if (score >= 0.8) return "Excellent quality with high confidence for investment decisions."
    if (score >= 0.6) return "Good quality suitable for preliminary analysis."
    return "Limited quality - consider expanding search criteria."
  }

  const formatMetricName = (key: string): string => {
    return key.replace('_', ' ').split(' ').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ')
  }

  return (
    <div className="quality-display bg-white border border-gray-200 rounded-lg shadow-sm" data-testid="quality-score-display">
      <div className="border-b border-gray-200 px-6 py-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Star className="h-4 w-4" />
          Quality Assessment
        </h3>
      </div>
      
      <div className="px-6 py-4">
        {/* Overall Score Badge */}
        <div className="mb-4 text-center">
          <div 
            className={`inline-flex items-center px-3 py-1 rounded-full text-lg font-bold ${getScoreColor(metrics.overall_score)}`}
            data-testid="overall-quality"
          >
            {(metrics.overall_score * 100).toFixed(1)}%
          </div>
          <div className="text-sm text-gray-500 mt-1">Overall Quality Score</div>
        </div>
        
        {/* Individual Metrics */}
        <div className="space-y-3">
          {Object.entries(metrics).map(([key, value]) => {
            if (key === 'overall_score') return null
            
            return (
              <div key={key} className="flex items-center justify-between">
                <span className="text-sm font-medium">
                  {formatMetricName(key)}
                </span>
                <div className="flex items-center gap-2">
                  {/* Progress bar */}
                  <div className="w-20 h-2 bg-gray-200 rounded-full">
                    <div 
                      className="h-2 bg-blue-500 rounded-full transition-all duration-300"
                      style={{ width: `${value * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-600 w-12">
                    {(value * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            )
          })}
        </div>
        
        {/* Quality Explanation */}
        <div className="mt-4 p-3 bg-blue-50 rounded-lg">
          <div className="text-sm text-blue-800">
            <strong>Investment Grade Analysis:</strong>{' '}
            {getInvestmentGradeText(metrics.overall_score)}
          </div>
        </div>
      </div>
    </div>
  )
}

export default QualityScoreDisplay
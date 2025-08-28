/**
 * SynthesisProgress Component
 * 
 * Tracks AI synthesis progress through citation extraction, quality scoring, and rendering
 * as defined in Milestone 3 of the implementation plan.
 */

import React from 'react'

export interface SynthesisStage {
  stage: 'citation_extraction' | 'quality_scoring' | 'template_rendering'
  progress_percent: number
  citations_found?: number
  quality_score?: number
}

interface SynthesisProgressProps {
  stage: SynthesisStage
}

export const SynthesisProgress: React.FC<SynthesisProgressProps> = ({ stage }) => {
  const getStageInfo = (stageName: string) => {
    const stages = {
      citation_extraction: { 
        name: 'Citation Extraction', 
        icon: '📚',
        description: 'Extracting citations from sources'
      },
      quality_scoring: { 
        name: 'Quality Analysis', 
        icon: '⭐',
        description: 'Analyzing source quality and relevance'  
      },
      template_rendering: { 
        name: 'Final Synthesis', 
        icon: '📝',
        description: 'Generating comprehensive analysis'
      }
    }
    return stages[stageName as keyof typeof stages] || { 
      name: stageName, 
      icon: '⚙️',
      description: 'Processing...'
    }
  }

  const stageInfo = getStageInfo(stage.stage)

  const getProgressColor = (progress: number): string => {
    if (progress >= 90) return 'bg-green-500'
    if (progress >= 50) return 'bg-blue-500'
    return 'bg-blue-400'
  }

  const formatQualityScore = (score?: number): string => {
    if (score === undefined) return 'Calculating...'
    return `${(score * 100).toFixed(1)}%`
  }

  return (
    <div className="synthesis-progress bg-white rounded-lg border shadow-sm p-4" data-testid="synthesis-progress">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-4 h-4 text-purple-500">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-gray-900">AI Synthesis</h3>
      </div>

      <div className="space-y-4">
        {/* Current Stage */}
        <div className="current-stage">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-2xl" role="img" aria-label={stageInfo.name}>
              {stageInfo.icon}
            </span>
            <div className="flex-1">
              <div className="font-semibold text-gray-900">{stageInfo.name}</div>
              <div className="text-sm text-gray-600">{stageInfo.description}</div>
            </div>
            <div className="text-right">
              <div className="text-lg font-bold text-gray-900">
                {stage.progress_percent}%
              </div>
              <div className="text-xs text-gray-500">complete</div>
            </div>
          </div>
          
          {/* Progress Bar */}
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div 
              className={`h-3 rounded-full transition-all duration-500 ${getProgressColor(stage.progress_percent)}`}
              style={{ width: `${Math.min(stage.progress_percent, 100)}%` }}
            />
          </div>
        </div>
        
        {/* Stage Metrics */}
        <div className="grid grid-cols-2 gap-4">
          {stage.citations_found !== undefined && (
            <div className="metric bg-blue-50 rounded-lg p-3">
              <div className="text-sm text-blue-600 font-medium">Citations Found</div>
              <div className="text-xl font-bold text-blue-900">
                {stage.citations_found}
              </div>
            </div>
          )}
          
          {stage.quality_score !== undefined && (
            <div className="metric bg-green-50 rounded-lg p-3">
              <div className="text-sm text-green-600 font-medium">Quality Score</div>
              <div className="text-xl font-bold text-green-900">
                {formatQualityScore(stage.quality_score)}
              </div>
            </div>
          )}
        </div>

        {/* Stage Progress Indicators */}
        <div className="stage-indicators">
          <div className="text-sm font-medium text-gray-700 mb-2">Progress Pipeline</div>
          <div className="flex items-center justify-between">
            {['citation_extraction', 'quality_scoring', 'template_rendering'].map((stageName, index) => {
              const isCompleted = getStageOrder(stage.stage) > index
              const isCurrent = stage.stage === stageName
              const stageDetails = getStageInfo(stageName)
              
              return (
                <div key={stageName} className="flex flex-col items-center">
                  <div 
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium border-2 transition-all duration-300 ${
                      isCompleted 
                        ? 'bg-green-500 border-green-500 text-white'
                        : isCurrent
                          ? 'bg-blue-500 border-blue-500 text-white animate-pulse'
                          : 'bg-gray-100 border-gray-300 text-gray-500'
                    }`}
                    title={stageDetails.name}
                  >
                    {isCompleted ? '✓' : isCurrent ? '●' : index + 1}
                  </div>
                  <div className={`text-xs mt-1 text-center ${
                    isCurrent ? 'text-blue-600 font-medium' : 'text-gray-500'
                  }`}>
                    {stageDetails.name.split(' ')[0]}
                  </div>
                  
                  {/* Progress connector */}
                  {index < 2 && (
                    <div className={`absolute h-px w-12 mt-4 ${
                      isCompleted ? 'bg-green-500' : 'bg-gray-300'
                    }`} style={{ transform: `translateX(${24 + index * 48}px)` }} />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

// Helper function to determine stage order
const getStageOrder = (stage: string): number => {
  const order = {
    'citation_extraction': 0,
    'quality_scoring': 1, 
    'template_rendering': 2
  }
  return order[stage as keyof typeof order] ?? -1
}

export default SynthesisProgress
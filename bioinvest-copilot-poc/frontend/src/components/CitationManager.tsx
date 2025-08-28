/**
 * CitationManager Component
 * 
 * Professional citation display and management with multiple formatting options
 * Supports PMID, full academic, and inline citation formats
 */

import React from 'react'
import { BookOpen, Copy, ExternalLink, ChevronDown } from 'lucide-react'

export interface Citation {
  id: string
  title: string
  authors?: string[]
  source: string
  year?: string
  url?: string
  relevance_score: number
}

export type CitationFormat = 'pmid' | 'full' | 'inline'

interface CitationManagerProps {
  citations: Citation[]
  format: CitationFormat
  onFormatChange: (format: CitationFormat) => void
}

const CitationManager: React.FC<CitationManagerProps> = ({ 
  citations, 
  format, 
  onFormatChange 
}) => {
  const formatCitation = (citation: Citation, formatType: CitationFormat): string => {
    switch (formatType) {
      case 'pmid':
        return `PMID: ${citation.id.replace('pmid:', '')}`
      case 'inline':
        return `${citation.authors?.[0] || 'Unknown'} et al. (${citation.year || 'Year unknown'})`
      case 'full':
      default:
        return `${citation.authors?.join(', ') || 'Unknown authors'}. ${citation.title}. ${citation.source}. ${citation.year || 'Year unknown'}.`
    }
  }

  const copyAllCitations = (): void => {
    const formatted = citations.map(c => formatCitation(c, format)).join('\n')
    navigator.clipboard.writeText(formatted)
  }

  const copySingleCitation = (citation: Citation): void => {
    const formatted = formatCitation(citation, format)
    navigator.clipboard.writeText(formatted)
  }

  return (
    <div className="citation-manager bg-white border border-gray-200 rounded-lg shadow-sm" data-testid="citation-manager">
      <div className="border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <BookOpen className="h-4 w-4" />
            Citations 
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800" data-testid="citation-count">
              {citations.length}
            </span>
          </h3>
          
          <div className="flex items-center gap-2">
            {/* Format Selector */}
            <div className="relative">
              <select 
                value={format} 
                onChange={(e) => onFormatChange(e.target.value as CitationFormat)}
                className="w-24 px-3 py-1 text-sm border border-gray-300 rounded bg-white cursor-pointer"
                data-testid="citation-format-selector"
              >
                <option value="full">Full</option>
                <option value="pmid">PMID</option>
                <option value="inline">Inline</option>
              </select>
              <ChevronDown className="absolute right-2 top-1/2 transform -translate-y-1/2 h-3 w-3 text-gray-400 pointer-events-none" />
            </div>
            
            {/* Copy All Button */}
            <button 
              onClick={copyAllCitations}
              className="px-3 py-1 text-sm border border-gray-300 rounded bg-white hover:bg-gray-50 flex items-center gap-1"
              data-testid="copy-all-citations"
            >
              <Copy className="h-3 w-3" />
              Copy All
            </button>
          </div>
        </div>
      </div>
      
      <div className="px-6 py-4">
        {citations.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            No citations available
          </div>
        ) : (
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {citations.map((citation, index) => (
              <div key={citation.id} className="citation-item" data-testid="citation-item">
                <div className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <div className="text-sm font-mono">
                      {formatCitation(citation, format)}
                    </div>
                    
                    {/* Relevance Score */}
                    <div className="mt-2 flex items-center gap-2">
                      <span className="inline-flex items-center px-2 py-1 rounded border border-gray-300 text-xs">
                        Relevance: {(citation.relevance_score * 100).toFixed(0)}%
                      </span>
                      
                      {citation.url && (
                        <button
                          onClick={() => window.open(citation.url!, '_blank')}
                          className="p-1 text-gray-500 hover:text-gray-700"
                          data-testid="external-link"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  </div>
                  
                  {/* Copy Individual Citation */}
                  <button
                    onClick={() => copySingleCitation(citation)}
                    className="p-1 text-gray-500 hover:text-gray-700"
                    data-testid="copy-single-citation"
                  >
                    <Copy className="h-3 w-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default CitationManager
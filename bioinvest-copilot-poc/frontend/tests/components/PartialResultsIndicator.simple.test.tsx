/**
 * PartialResultsIndicator Simple Unit Tests
 * 
 * Testing individual functions and basic rendering with TDD approach
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PartialResultsIndicator, { PartialResultsData } from '../../src/components/PartialResultsIndicator'

describe('PartialResultsIndicator Simple Tests', () => {
  // Test 1: Basic rendering
  it('renders with test id', () => {
    const data: PartialResultsData = {
      reason: 'timeout',
      completion_percentage: 0.5,
      available_sources: ['pubmed'],
      total_results: 10
    }
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByTestId('partial-results-indicator')).toBeInTheDocument()
  })

  // Test 2: Title with percentage
  it('shows completion percentage in title', () => {
    const data: PartialResultsData = {
      reason: 'timeout',
      completion_percentage: 0.75,
      available_sources: ['pubmed'],
      total_results: 12
    }
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText(/75% Complete/)).toBeInTheDocument()
  })

  // Test 3: Timeout reason message
  it('shows timeout message for timeout reason', () => {
    const data: PartialResultsData = {
      reason: 'timeout',
      completion_percentage: 0.6,
      available_sources: ['pubmed'],
      total_results: 8
    }
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Query timed out - returning available results')).toBeInTheDocument()
  })

  // Test 4: Budget exhausted reason message
  it('shows budget exhausted message', () => {
    const data: PartialResultsData = {
      reason: 'budget_exhausted',
      completion_percentage: 0.4,
      available_sources: ['pubmed'],
      total_results: 5
    }
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Budget limit reached - returning available results')).toBeInTheDocument()
  })

  // Test 5: Error reason message
  it('shows error message for error reason', () => {
    const data: PartialResultsData = {
      reason: 'error',
      completion_percentage: 0.3,
      available_sources: ['pubmed'],
      total_results: 3
    }
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Some sources failed - returning successful results')).toBeInTheDocument()
  })

  // Test 6: Source formatting
  it('formats source names correctly', () => {
    const data: PartialResultsData = {
      reason: 'timeout',
      completion_percentage: 0.8,
      available_sources: ['pubmed', 'clinical_trials', 'rag'],
      total_results: 20
    }
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('PubMed')).toBeInTheDocument()
    expect(screen.getByText('ClinicalTrials.gov')).toBeInTheDocument()
    expect(screen.getByText('RAG Search')).toBeInTheDocument()
  })

  // Test 7: Recommendations section
  it('shows recommendations section', () => {
    const data: PartialResultsData = {
      reason: 'timeout',
      completion_percentage: 0.5,
      available_sources: ['pubmed'],
      total_results: 10
    }
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Recommendations:')).toBeInTheDocument()
  })

  // Test 8: Analysis progress section
  it('shows analysis progress section', () => {
    const data: PartialResultsData = {
      reason: 'timeout',
      completion_percentage: 0.6,
      available_sources: ['pubmed'],
      total_results: 12
    }
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Analysis Progress')).toBeInTheDocument()
    // Multiple 60% elements exist - verify at least one exists
    expect(screen.getAllByText('60%').length).toBeGreaterThan(0)
  })
})
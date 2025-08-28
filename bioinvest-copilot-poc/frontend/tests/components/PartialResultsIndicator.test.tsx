/**
 * PartialResultsIndicator Component Tests
 * 
 * Comprehensive tests for the M3 partial results indication functionality
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PartialResultsIndicator, { PartialResultsData } from '../../src/components/PartialResultsIndicator'

describe('PartialResultsIndicator', () => {
  const createMockData = (overrides: Partial<PartialResultsData> = {}): PartialResultsData => ({
    reason: 'timeout',
    completion_percentage: 0.6,
    available_sources: ['pubmed', 'clinical_trials'],
    total_results: 25,
    ...overrides
  })

  it('renders timeout scenario correctly', () => {
    const data = createMockData({
      reason: 'timeout',
      completion_percentage: 0.75,
      available_sources: ['pubmed', 'rag'],
      total_results: 15
    })
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByTestId('partial-results-indicator')).toBeInTheDocument()
    expect(screen.getByText('Partial Results (75% Complete)')).toBeInTheDocument()
    expect(screen.getByText('Query timed out - returning available results')).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
    expect(screen.getByText('results available from partial analysis')).toBeInTheDocument()
    expect(screen.getByText('PubMed')).toBeInTheDocument()
    expect(screen.getByText('RAG Search')).toBeInTheDocument()
  })

  it('renders budget exhausted scenario correctly', () => {
    const data = createMockData({
      reason: 'budget_exhausted',
      completion_percentage: 0.4,
      available_sources: ['clinical_trials'],
      total_results: 8
    })
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Partial Results (40% Complete)')).toBeInTheDocument()
    expect(screen.getByText('Budget limit reached - returning available results')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('results available from partial analysis')).toBeInTheDocument()
    expect(screen.getByText('ClinicalTrials.gov')).toBeInTheDocument()
  })

  it('renders error scenario correctly', () => {
    const data = createMockData({
      reason: 'error',
      completion_percentage: 0.3,
      available_sources: ['pubmed'],
      total_results: 12
    })
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Partial Results (30% Complete)')).toBeInTheDocument()
    expect(screen.getByText('Some sources failed - returning successful results')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('results available from partial analysis')).toBeInTheDocument()
    expect(screen.getByText('PubMed')).toBeInTheDocument()
  })

  it('formats source names correctly', () => {
    const data = createMockData({
      available_sources: ['pubmed', 'clinical_trials', 'rag', 'unknown_source']
    })
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('PubMed')).toBeInTheDocument()
    expect(screen.getByText('ClinicalTrials.gov')).toBeInTheDocument()
    expect(screen.getByText('RAG Search')).toBeInTheDocument()
    expect(screen.getByText('unknown_source')).toBeInTheDocument()
  })

  it('displays completion progress bar with correct percentage', () => {
    const data = createMockData({ completion_percentage: 0.67 })
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Partial Results (67% Complete)')).toBeInTheDocument()
    expect(screen.getByText('Analysis Progress')).toBeInTheDocument()
  })

  it('shows appropriate recommendations for timeout', () => {
    const data = createMockData({ reason: 'timeout' })
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Recommendations:')).toBeInTheDocument()
    expect(screen.getByText('Try reducing the number of sources or results per source')).toBeInTheDocument()
    expect(screen.getByText('Consider increasing the budget limit for comprehensive analysis')).toBeInTheDocument()
    expect(screen.getByText('Current partial results can still provide valuable insights')).toBeInTheDocument()
  })

  it('shows appropriate recommendations for budget exhausted', () => {
    const data = createMockData({ reason: 'budget_exhausted' })
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Increase budget allocation for more comprehensive results')).toBeInTheDocument()
    expect(screen.getByText('Use current results as a starting point for focused queries')).toBeInTheDocument()
  })

  it('shows appropriate recommendations for error', () => {
    const data = createMockData({ reason: 'error' })
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Check if external services are available')).toBeInTheDocument()
    expect(screen.getByText('Try re-running the query with different parameters')).toBeInTheDocument()
  })

  it('applies correct CSS classes based on reason', () => {
    const { rerender } = render(<PartialResultsIndicator data={createMockData({ reason: 'timeout' })} />)
    let indicator = screen.getByTestId('partial-results-indicator')
    expect(indicator).toHaveClass('border-blue-500', 'bg-blue-50', 'text-blue-800')
    
    rerender(<PartialResultsIndicator data={createMockData({ reason: 'budget_exhausted' })} />)
    indicator = screen.getByTestId('partial-results-indicator')
    expect(indicator).toHaveClass('border-orange-500', 'bg-orange-50', 'text-orange-800')
    
    rerender(<PartialResultsIndicator data={createMockData({ reason: 'error' })} />)
    indicator = screen.getByTestId('partial-results-indicator')
    expect(indicator).toHaveClass('border-yellow-500', 'bg-yellow-50', 'text-yellow-800')
  })

  it('handles edge case of 0% completion', () => {
    const data = createMockData({ completion_percentage: 0 })
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Partial Results (0% Complete)')).toBeInTheDocument()
    // Progress section should show 0% in Analysis Progress
  })

  it('handles edge case of 100% completion', () => {
    const data = createMockData({ completion_percentage: 1.0 })
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Partial Results (100% Complete)')).toBeInTheDocument()
    // Progress section should show 100% in Analysis Progress
  })

  it('handles empty available sources array', () => {
    const data = createMockData({ available_sources: [] })
    
    render(<PartialResultsIndicator data={data} />)
    
    expect(screen.getByText('Available sources:')).toBeInTheDocument()
    // Should not crash with empty array
    expect(screen.getByTestId('partial-results-indicator')).toBeInTheDocument()
  })
})
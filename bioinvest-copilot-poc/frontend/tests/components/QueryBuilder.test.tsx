/**
 * Enhanced QueryBuilder Component Tests
 * Verifies M3/M4 options are properly handled and submitted
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import QueryBuilder from '../../src/components/QueryBuilder'
import { EnhancedOrchestrationRequest } from '@/shared-types'

describe('Enhanced QueryBuilder', () => {
  const mockOnSubmit = vi.fn()

  beforeEach(() => {
    mockOnSubmit.mockClear()
  })

  it('should render basic query form', () => {
    render(<QueryBuilder onSubmit={mockOnSubmit} isLoading={false} />)
    
    expect(screen.getByLabelText('Research Question')).toBeInTheDocument()
    expect(screen.getByText('PubMed')).toBeInTheDocument()
    expect(screen.getByText('Clinical Trials')).toBeInTheDocument()
    expect(screen.getByText('Internal Database')).toBeInTheDocument()
  })

  it('should show M3/M4 advanced options when expanded', () => {
    render(<QueryBuilder onSubmit={mockOnSubmit} isLoading={false} />)
    
    // Click advanced options
    fireEvent.click(screen.getByText('Advanced Options'))
    
    // Check M3 features
    expect(screen.getByText('Advanced State Management')).toBeInTheDocument()
    expect(screen.getByText(/Budget Limit:/)).toBeInTheDocument()
    expect(screen.getByText('Parallel Execution')).toBeInTheDocument()
    expect(screen.getByText('Retry Strategy')).toBeInTheDocument()
    
    // Check M4 features  
    expect(screen.getByText('Advanced Synthesis')).toBeInTheDocument()
    expect(screen.getByText('Citation Format')).toBeInTheDocument()
    expect(screen.getByText(/Quality Threshold:/)).toBeInTheDocument()
    expect(screen.getByText('Enable Checkpoints')).toBeInTheDocument()
  })

  it('should submit enhanced request with M3/M4 options', async () => {
    render(<QueryBuilder onSubmit={mockOnSubmit} isLoading={false} />)
    
    // Fill in query
    const queryInput = screen.getByLabelText('Research Question')
    fireEvent.change(queryInput, { target: { value: 'Test M3/M4 query' } })
    
    // Expand advanced options
    fireEvent.click(screen.getByText('Advanced Options'))
    
    // Modify some M3/M4 options (only non-default values should be included)
    const budgetSlider = screen.getByLabelText(/Budget Limit:/)
    fireEvent.change(budgetSlider, { target: { value: '20000' } })
    
    const qualitySlider = screen.getByLabelText(/Quality Threshold:/)
    fireEvent.change(qualitySlider, { target: { value: '0.8' } })
    
    // Submit
    fireEvent.click(screen.getByText('Start Research Analysis'))
    
    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          query: 'Test M3/M4 query',
          sources: ['pubmed', 'clinical_trials', 'rag'],
          options: expect.objectContaining({
            max_results_per_source: 50,
            include_synthesis: true,
            priority: 'balanced',
            budget_ms: 20000,  // Changed from default
            quality_threshold: 0.8  // Changed from default
          })
        })
      )
    })
  })

  it('should maintain backward compatibility with default values', async () => {
    render(<QueryBuilder onSubmit={mockOnSubmit} isLoading={false} />)
    
    // Fill in query and submit with defaults
    const queryInput = screen.getByLabelText('Research Question')
    fireEvent.change(queryInput, { target: { value: 'Basic query' } })
    
    fireEvent.click(screen.getByText('Start Research Analysis'))
    
    await waitFor(() => {
      const call = mockOnSubmit.mock.calls[0][0] as EnhancedOrchestrationRequest
      
      // Should have basic options
      expect(call.options.max_results_per_source).toBe(50)
      expect(call.options.include_synthesis).toBe(true)
      expect(call.options.priority).toBe('balanced')
      
      // M3/M4 options should be undefined (using defaults, not included in request)
      expect(call.options.budget_ms).toBeUndefined()
      expect(call.options.enable_partial_results).toBeUndefined()
      expect(call.options.retry_strategy).toBeUndefined()
      expect(call.options.citation_format).toBeUndefined()
      expect(call.options.quality_threshold).toBeUndefined()
      expect(call.options.checkpoint_enabled).toBeUndefined()
    })
  })
})
/**
 * SynthesisProgress Component Tests
 * 
 * Comprehensive tests for the M4 synthesis progress tracking functionality
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SynthesisProgress, { SynthesisStage } from '../../src/components/SynthesisProgress'

describe('SynthesisProgress', () => {
  const createMockStage = (overrides: Partial<SynthesisStage> = {}): SynthesisStage => ({
    stage: 'citation_extraction',
    progress_percent: 50,
    ...overrides
  })

  it('renders citation extraction stage correctly', () => {
    const stage = createMockStage({
      stage: 'citation_extraction',
      progress_percent: 75,
      citations_found: 12
    })
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByTestId('synthesis-progress')).toBeInTheDocument()
    expect(screen.getByText('AI Synthesis')).toBeInTheDocument()
    expect(screen.getByText('Citation Extraction')).toBeInTheDocument()
    expect(screen.getByText('Extracting citations from sources')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('Citations Found')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('renders quality scoring stage correctly', () => {
    const stage = createMockStage({
      stage: 'quality_scoring',
      progress_percent: 60,
      quality_score: 0.85
    })
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('Quality Analysis')).toBeInTheDocument()
    expect(screen.getByText('Analyzing source quality and relevance')).toBeInTheDocument()
    expect(screen.getByText('60%')).toBeInTheDocument()
    expect(screen.getByText('Quality Score')).toBeInTheDocument()
    expect(screen.getByText('85.0%')).toBeInTheDocument()
  })

  it('renders template rendering stage correctly', () => {
    const stage = createMockStage({
      stage: 'template_rendering',
      progress_percent: 90
    })
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('Final Synthesis')).toBeInTheDocument()
    expect(screen.getByText('Generating comprehensive analysis')).toBeInTheDocument()
    expect(screen.getByText('90%')).toBeInTheDocument()
  })

  it('handles undefined quality score gracefully', () => {
    const stage = createMockStage({
      stage: 'quality_scoring',
      progress_percent: 30
    })
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.queryByText('Quality Score')).not.toBeInTheDocument()
  })

  it('handles undefined citations found gracefully', () => {
    const stage = createMockStage({
      stage: 'citation_extraction',
      progress_percent: 40
    })
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.queryByText('Citations Found')).not.toBeInTheDocument()
  })

  it('shows progress pipeline with correct states', () => {
    const stage = createMockStage({
      stage: 'quality_scoring',
      progress_percent: 50
    })
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('Progress Pipeline')).toBeInTheDocument()
    
    // Citation extraction should be completed (✓)
    // Quality scoring should be current (●) 
    // Template rendering should be pending (3)
    const buttons = screen.getAllByRole('generic').filter(el => 
      el.textContent === '✓' || el.textContent === '●' || el.textContent === '3'
    )
    
    expect(buttons.length).toBeGreaterThan(0)
  })

  it('applies correct progress bar colors based on percentage', () => {
    const highProgress = createMockStage({ progress_percent: 95 })
    const { rerender } = render(<SynthesisProgress stage={highProgress} />)
    
    // Should have green color for high progress
    let progressBar = document.querySelector('.bg-green-500')
    expect(progressBar).toBeInTheDocument()
    
    const mediumProgress = createMockStage({ progress_percent: 60 })
    rerender(<SynthesisProgress stage={mediumProgress} />)
    
    // Should have blue color for medium progress
    progressBar = document.querySelector('.bg-blue-500')
    expect(progressBar).toBeInTheDocument()
  })

  it('handles edge case of 0% progress', () => {
    const stage = createMockStage({ progress_percent: 0 })
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('handles edge case of 100% progress', () => {
    const stage = createMockStage({ progress_percent: 100 })
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('formats quality score correctly', () => {
    const stage = createMockStage({
      stage: 'quality_scoring',
      progress_percent: 50,
      quality_score: 0.867
    })
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('86.7%')).toBeInTheDocument()
  })

  it('shows appropriate stage icons', () => {
    const stage = createMockStage({ stage: 'citation_extraction' })
    
    render(<SynthesisProgress stage={stage} />)
    
    // Should contain the book emoji for citation extraction
    expect(screen.getByRole('img', { name: 'Citation Extraction' })).toBeInTheDocument()
  })
})
/**
 * SynthesisProgress Simple Unit Tests
 * 
 * Testing individual functions and basic rendering with TDD approach
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SynthesisProgress, { SynthesisStage } from '../../src/components/SynthesisProgress'

describe('SynthesisProgress Simple Tests', () => {
  // Test 1: Basic rendering
  it('renders component title', () => {
    const stage: SynthesisStage = {
      stage: 'citation_extraction',
      progress_percent: 50
    }
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('AI Synthesis')).toBeInTheDocument()
  })

  // Test 2: Stage name display
  it('shows citation extraction stage name', () => {
    const stage: SynthesisStage = {
      stage: 'citation_extraction',
      progress_percent: 30
    }
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('Citation Extraction')).toBeInTheDocument()
  })

  // Test 3: Quality scoring stage
  it('shows quality scoring stage name', () => {
    const stage: SynthesisStage = {
      stage: 'quality_scoring',
      progress_percent: 60
    }
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('Quality Analysis')).toBeInTheDocument()
  })

  // Test 4: Template rendering stage
  it('shows template rendering stage name', () => {
    const stage: SynthesisStage = {
      stage: 'template_rendering',
      progress_percent: 80
    }
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('Final Synthesis')).toBeInTheDocument()
  })

  // Test 5: Progress percentage display
  it('displays progress percentage', () => {
    const stage: SynthesisStage = {
      stage: 'citation_extraction',
      progress_percent: 45
    }
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('45%')).toBeInTheDocument()
  })

  // Test 6: Citations found display
  it('shows citations found when provided', () => {
    const stage: SynthesisStage = {
      stage: 'citation_extraction',
      progress_percent: 70,
      citations_found: 15
    }
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('Citations Found')).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
  })

  // Test 7: Quality score display
  it('shows quality score when provided', () => {
    const stage: SynthesisStage = {
      stage: 'quality_scoring',
      progress_percent: 80,
      quality_score: 0.75
    }
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('Quality Score')).toBeInTheDocument()
    expect(screen.getByText('75.0%')).toBeInTheDocument()
  })

  // Test 8: Progress pipeline section
  it('renders progress pipeline section', () => {
    const stage: SynthesisStage = {
      stage: 'citation_extraction',
      progress_percent: 50
    }
    
    render(<SynthesisProgress stage={stage} />)
    
    expect(screen.getByText('Progress Pipeline')).toBeInTheDocument()
  })
})
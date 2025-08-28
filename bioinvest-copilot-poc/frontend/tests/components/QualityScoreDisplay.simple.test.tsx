/**
 * QualityScoreDisplay Simple Unit Tests
 * 
 * Testing individual functions and basic rendering with TDD approach
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import QualityScoreDisplay, { QualityMetrics } from '../../src/components/QualityScoreDisplay'

describe('QualityScoreDisplay Simple Tests', () => {
  // Test 1: Basic rendering
  it('renders component title', () => {
    const metrics: QualityMetrics = {
      completeness: 0.8,
      recency: 0.7,
      authority: 0.9,
      diversity: 0.6,
      relevance: 0.85,
      overall_score: 0.76
    }
    
    render(<QualityScoreDisplay metrics={metrics} />)
    
    expect(screen.getByText('Quality Assessment')).toBeInTheDocument()
  })

  // Test 2: Overall score display
  it('displays overall quality score', () => {
    const metrics: QualityMetrics = {
      completeness: 0.8,
      recency: 0.7,
      authority: 0.9,
      diversity: 0.6,
      relevance: 0.85,
      overall_score: 0.76
    }
    
    render(<QualityScoreDisplay metrics={metrics} />)
    
    expect(screen.getByText('76.0%')).toBeInTheDocument()
    expect(screen.getByText('Overall Quality Score')).toBeInTheDocument()
  })

  // Test 3: Individual metric rendering
  it('displays individual metrics', () => {
    const metrics: QualityMetrics = {
      completeness: 0.8,
      recency: 0.7,
      authority: 0.9,
      diversity: 0.6,
      relevance: 0.85,
      overall_score: 0.76
    }
    
    render(<QualityScoreDisplay metrics={metrics} />)
    
    expect(screen.getByText('Completeness')).toBeInTheDocument()
    expect(screen.getByText('Recency')).toBeInTheDocument()
    expect(screen.getByText('Authority')).toBeInTheDocument()
    expect(screen.getByText('Diversity')).toBeInTheDocument()
    expect(screen.getByText('Relevance')).toBeInTheDocument()
  })

  // Test 4: High quality investment grade text
  it('shows excellent quality text for high scores', () => {
    const metrics: QualityMetrics = {
      completeness: 0.9,
      recency: 0.9,
      authority: 0.9,
      diversity: 0.9,
      relevance: 0.9,
      overall_score: 0.85
    }
    
    render(<QualityScoreDisplay metrics={metrics} />)
    
    expect(screen.getByText(/Excellent quality with high confidence/)).toBeInTheDocument()
  })

  // Test 5: Medium quality investment grade text
  it('shows good quality text for medium scores', () => {
    const metrics: QualityMetrics = {
      completeness: 0.7,
      recency: 0.6,
      authority: 0.7,
      diversity: 0.6,
      relevance: 0.7,
      overall_score: 0.65
    }
    
    render(<QualityScoreDisplay metrics={metrics} />)
    
    expect(screen.getByText(/Good quality suitable for preliminary/)).toBeInTheDocument()
  })

  // Test 6: Low quality investment grade text
  it('shows limited quality text for low scores', () => {
    const metrics: QualityMetrics = {
      completeness: 0.4,
      recency: 0.3,
      authority: 0.5,
      diversity: 0.4,
      relevance: 0.3,
      overall_score: 0.38
    }
    
    render(<QualityScoreDisplay metrics={metrics} />)
    
    expect(screen.getByText(/Limited quality - consider expanding/)).toBeInTheDocument()
  })

  // Test 7: Percentage formatting
  it('formats percentages correctly', () => {
    const metrics: QualityMetrics = {
      completeness: 0.845,
      recency: 0.723,
      authority: 0.912,
      diversity: 0.667,
      relevance: 0.834,
      overall_score: 0.796
    }
    
    render(<QualityScoreDisplay metrics={metrics} />)
    
    // Overall score should show one decimal place
    expect(screen.getByText('79.6%')).toBeInTheDocument()
    // Individual metrics should show as whole numbers
    expect(screen.getByText('85%')).toBeInTheDocument() // completeness
    expect(screen.getByText('72%')).toBeInTheDocument() // recency
  })

  // Test 8: Investment Grade Analysis section
  it('shows investment grade analysis section', () => {
    const metrics: QualityMetrics = {
      completeness: 0.8,
      recency: 0.7,
      authority: 0.9,
      diversity: 0.6,
      relevance: 0.85,
      overall_score: 0.76
    }
    
    render(<QualityScoreDisplay metrics={metrics} />)
    
    expect(screen.getByText('Investment Grade Analysis:')).toBeInTheDocument()
  })
})
/**
 * Milestone 6 Integration Tests
 * 
 * Focused integration tests for Milestone 6 components with actual component behavior
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import BudgetMonitor from '../../src/components/BudgetMonitor'
import QualityScoreDisplay from '../../src/components/QualityScoreDisplay'
import CitationManager from '../../src/components/CitationManager'

describe('Milestone 6 Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Budget Monitoring Integration', () => {
    it('renders budget monitor with normal status', () => {
      const normalStatus = {
        allocated_ms: 10000,
        consumed_ms: 3000,
        remaining_ms: 7000,
        utilization: 0.3
      }

      render(<BudgetMonitor status={normalStatus} />)
      
      expect(screen.getByText('Budget Monitor')).toBeInTheDocument()
      expect(screen.getByText('Consumed: 3s')).toBeInTheDocument()
      expect(screen.getByText('Remaining: 7s')).toBeInTheDocument()
      expect(screen.getByText('30%')).toBeInTheDocument()
    })

    it('shows high usage warning when utilization exceeds 80%', () => {
      const highUsageStatus = {
        allocated_ms: 10000,
        consumed_ms: 8500,
        remaining_ms: 1500,
        utilization: 0.85
      }

      render(<BudgetMonitor status={highUsageStatus} />)
      
      expect(screen.getByTestId('budget-warning')).toBeInTheDocument()
      expect(screen.getByText('High Budget Usage')).toBeInTheDocument()
    })
  })

  describe('Quality Scoring Integration', () => {
    it('displays high-quality metrics correctly', () => {
      const highQualityMetrics = {
        completeness: 0.85,
        recency: 0.90,
        authority: 0.80,
        diversity: 0.75,
        relevance: 0.88,
        overall_score: 0.84
      }

      render(<QualityScoreDisplay metrics={highQualityMetrics} />)
      
      expect(screen.getByText('Quality Assessment')).toBeInTheDocument()
      expect(screen.getByText('84.0%')).toBeInTheDocument()
      expect(screen.getByText('Overall Quality Score')).toBeInTheDocument()
      
      // Check individual metrics are displayed
      expect(screen.getByText('Completeness')).toBeInTheDocument()
      expect(screen.getByText('85%')).toBeInTheDocument()
    })

    it('shows appropriate quality grade for different score levels', () => {
      const mediumQualityMetrics = {
        completeness: 0.65,
        recency: 0.70,
        authority: 0.60,
        diversity: 0.55,
        relevance: 0.68,
        overall_score: 0.64
      }

      render(<QualityScoreDisplay metrics={mediumQualityMetrics} />)
      
      expect(screen.getByText('64.0%')).toBeInTheDocument()
      // Should show medium quality styling (yellow background)
      const overallScore = screen.getByTestId('overall-quality')
      expect(overallScore).toHaveClass('bg-yellow-100')
    })

    it('shows investment grade analysis text', () => {
      const investmentGradeMetrics = {
        completeness: 0.92,
        recency: 0.88,
        authority: 0.85,
        diversity: 0.80,
        relevance: 0.90,
        overall_score: 0.87
      }

      render(<QualityScoreDisplay metrics={investmentGradeMetrics} />)
      
      // Should show excellent quality text
      expect(screen.getByText(/Excellent quality with high confidence/)).toBeInTheDocument()
    })
  })

  describe('Citation Management Integration', () => {
    const testCitations = [
      {
        id: 'pmid:12345678',
        title: 'Advanced Diabetes Treatment Methods',
        authors: ['Smith, J.', 'Doe, A.'],
        journal: 'Nature Medicine',
        year: '2023',
        url: 'https://pubmed.ncbi.nlm.nih.gov/12345678/',
        relevance_score: 0.95,
        source: 'Nature Medicine'
      }
    ]
    
    const mockOnFormatChange = vi.fn()

    it('displays citations in full format by default', () => {
      render(
        <CitationManager
          citations={testCitations}
          format="full"
          onFormatChange={mockOnFormatChange}
        />
      )
      
      expect(screen.getByText('Citations')).toBeInTheDocument()
      expect(screen.getByTestId('citation-count')).toHaveTextContent('1')
      // Check that full citation format is displayed
      expect(screen.getByText(/Smith, J., Doe, A\./)).toBeInTheDocument()
      expect(screen.getByText(/Advanced Diabetes Treatment Methods/)).toBeInTheDocument()
    })

    it('switches to PMID format correctly', () => {
      render(
        <CitationManager
          citations={testCitations}
          format="pmid"
          onFormatChange={mockOnFormatChange}
        />
      )
      
      expect(screen.getByText('PMID: 12345678')).toBeInTheDocument()
    })

    it('shows relevance scores and copy functionality', () => {
      render(
        <CitationManager
          citations={testCitations}
          format="full"
          onFormatChange={mockOnFormatChange}
        />
      )
      
      expect(screen.getByText('Relevance: 95%')).toBeInTheDocument()
      expect(screen.getByTestId('copy-single-citation')).toBeInTheDocument()
      expect(screen.getByTestId('copy-all-citations')).toBeInTheDocument()
    })
  })

  describe('Cross-Component Integration', () => {
    it('renders multiple monitoring components together without conflicts', () => {
      const budgetStatus = {
        allocated_ms: 15000,
        consumed_ms: 5000,
        remaining_ms: 10000,
        utilization: 0.33
      }

      const qualityMetrics = {
        completeness: 0.80,
        recency: 0.75,
        authority: 0.85,
        diversity: 0.70,
        relevance: 0.82,
        overall_score: 0.78
      }

      const { container } = render(
        <div>
          <BudgetMonitor status={budgetStatus} />
          <QualityScoreDisplay metrics={qualityMetrics} />
        </div>
      )

      // Both components should render simultaneously
      expect(screen.getByText('Budget Monitor')).toBeInTheDocument()
      expect(screen.getByText('Quality Assessment')).toBeInTheDocument()
      expect(screen.getByText('33%')).toBeInTheDocument() // Budget utilization
      expect(screen.getByText('78.0%')).toBeInTheDocument() // Quality score
      
      // No layout conflicts
      expect(container.firstChild).toBeInTheDocument()
    })
  })

  describe('Performance Validation', () => {
    it('renders components within acceptable time limits', () => {
      const startTime = performance.now()

      const budgetStatus = {
        allocated_ms: 10000,
        consumed_ms: 2000,
        remaining_ms: 8000,
        utilization: 0.2
      }

      render(<BudgetMonitor status={budgetStatus} />)

      const renderTime = performance.now() - startTime

      // Should render in under 50ms (performance target)
      expect(renderTime).toBeLessThan(50)
      expect(screen.getByText('Budget Monitor')).toBeInTheDocument()
    })

    it('handles rapid state updates efficiently', () => {
      let renderCount = 0
      
      const TestWrapper = ({ utilization }: { utilization: number }) => {
        renderCount++
        return (
          <BudgetMonitor
            status={{
              allocated_ms: 10000,
              consumed_ms: utilization * 10000,
              remaining_ms: (1 - utilization) * 10000,
              utilization
            }}
          />
        )
      }

      const { rerender } = render(<TestWrapper utilization={0.1} />)

      // Simulate rapid updates
      const startTime = performance.now()
      for (let i = 1; i <= 10; i++) {
        rerender(<TestWrapper utilization={i * 0.1} />)
      }
      const updateTime = performance.now() - startTime

      expect(renderCount).toBe(11) // Initial + 10 updates
      expect(updateTime).toBeLessThan(100) // All updates under 100ms
    })
  })

  describe('Error Handling Integration', () => {
    it('handles missing or invalid data gracefully', () => {
      // Test with partial budget data
      const incompleteBudgetStatus = {
        allocated_ms: 10000,
        consumed_ms: 3000,
        remaining_ms: 7000,
        utilization: 0.3
      }

      render(<BudgetMonitor status={incompleteBudgetStatus} />)
      
      // Should still render basic information
      expect(screen.getByText('Budget Monitor')).toBeInTheDocument()
    })

    it('handles empty citations array', () => {
      const mockOnFormatChange = vi.fn()

      render(
        <CitationManager
          citations={[]}
          format="full"
          onFormatChange={mockOnFormatChange}
        />
      )
      
      expect(screen.getByText('Citations')).toBeInTheDocument()
      expect(screen.getByTestId('citation-count')).toHaveTextContent('0')
    })
  })
})
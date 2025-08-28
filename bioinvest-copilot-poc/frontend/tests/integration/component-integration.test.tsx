/**
 * Component Integration Tests
 * 
 * Tests integration between components created for Milestone 6
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import BudgetMonitor from '../../src/components/BudgetMonitor'
import RetryVisualizer from '../../src/components/RetryVisualizer'
import QualityScoreDisplay from '../../src/components/QualityScoreDisplay'
import CitationManager from '../../src/components/CitationManager'

// Mock data for testing
const mockBudgetStatus = {
  allocated_ms: 10000,
  consumed_ms: 3000,
  remaining_ms: 7000,
  utilization: 0.3
}

const mockRetryAttempts = [
  {
    node: 'pubmed_search',
    attempt: 1,
    max_attempts: 3,
    delay_ms: 2000,
    error: 'API timeout',
    timestamp: '2025-01-01T10:00:00Z'
  }
]

const mockQualityMetrics = {
  completeness: 0.85,
  recency: 0.90,
  authority: 0.80,
  diversity: 0.75,
  relevance: 0.88,
  overall_score: 0.84
}

const mockCitations = [
  {
    id: 'pmid:12345678',
    title: 'Test Research Paper',
    authors: ['Smith, J.', 'Doe, A.'],
    journal: 'Nature Medicine',
    year: '2023',
    url: 'https://pubmed.ncbi.nlm.nih.gov/12345678/',
    relevance_score: 0.95,
    source: 'Nature Medicine'
  }
]

describe('Component Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Budget Monitor Integration', () => {
    it('should render budget monitor with status data', () => {
      render(<BudgetMonitor status={mockBudgetStatus} />)
      
      expect(screen.getByText('Budget Monitor')).toBeInTheDocument()
      expect(screen.getByText('Consumed: 3s')).toBeInTheDocument()
      expect(screen.getByText('Remaining: 7s')).toBeInTheDocument()
    })

    it('should show warning when budget utilization is high', () => {
      const highUtilizationStatus = {
        ...mockBudgetStatus,
        consumed_ms: 8500,
        remaining_ms: 1500,
        utilization: 0.85
      }

      render(<BudgetMonitor status={highUtilizationStatus} />)
      
      expect(screen.getByText('Budget usage high! Query may timeout soon.')).toBeInTheDocument()
    })
  })

  describe('Retry Visualizer Integration', () => {
    it('should render retry attempts correctly', () => {
      render(<RetryVisualizer attempts={mockRetryAttempts} />)
      
      expect(screen.getByText('Error Recovery')).toBeInTheDocument()
      expect(screen.getByText('(1 active)')).toBeInTheDocument()
      expect(screen.getByText('Next retry in 2.0s')).toBeInTheDocument()
    })

    it('should handle empty retry attempts', () => {
      render(<RetryVisualizer attempts={[]} />)
      
      // Component returns null when no attempts, so nothing should be rendered
      expect(screen.queryByText('Error Recovery')).not.toBeInTheDocument()
    })
  })

  describe('Quality Score Integration', () => {
    it('should render quality metrics correctly', () => {
      render(<QualityScoreDisplay metrics={mockQualityMetrics} />)
      
      expect(screen.getByText('Quality Assessment')).toBeInTheDocument()
      expect(screen.getByText('84.0%')).toBeInTheDocument()
      expect(screen.getByText('Excellent quality with high confidence for investment decisions.')).toBeInTheDocument()
    })

    it('should show different quality grades', () => {
      const lowQualityMetrics = {
        ...mockQualityMetrics,
        overall_score: 0.45
      }

      render(<QualityScoreDisplay metrics={lowQualityMetrics} />)
      
      expect(screen.getByText('45.0%')).toBeInTheDocument()
      expect(screen.getByText('Limited quality - consider expanding search criteria.')).toBeInTheDocument()
    })
  })

  describe('Citation Manager Integration', () => {
    const mockFormatChange = vi.fn()

    it('should render citations in full format', () => {
      render(
        <CitationManager
          citations={mockCitations}
          format="full"
          onFormatChange={mockFormatChange}
        />
      )
      
      expect(screen.getByText('Citations')).toBeInTheDocument()
      expect(screen.getByText('1')).toBeInTheDocument()
      expect(screen.getByText('Smith, J., Doe, A.. Test Research Paper. Nature Medicine. 2023.')).toBeInTheDocument()
    })

    it('should render citations in PMID format', () => {
      render(
        <CitationManager
          citations={mockCitations}
          format="pmid"
          onFormatChange={mockFormatChange}
        />
      )
      
      expect(screen.getByText('PMID: 12345678')).toBeInTheDocument()
    })

    it('should render citations in inline format', () => {
      render(
        <CitationManager
          citations={mockCitations}
          format="inline"
          onFormatChange={mockFormatChange}
        />
      )
      
      expect(screen.getByText('Smith, J. et al. (2023)')).toBeInTheDocument()
    })
  })
})
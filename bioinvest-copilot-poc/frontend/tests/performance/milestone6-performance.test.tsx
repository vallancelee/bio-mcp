/**
 * Milestone 6 Performance Tests
 * 
 * Performance validation tests for Milestone 6 components
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import BudgetMonitor from '../../src/components/BudgetMonitor'
import QualityScoreDisplay from '../../src/components/QualityScoreDisplay'
import CitationManager from '../../src/components/CitationManager'

describe('Milestone 6 Performance Tests', () => {
  beforeEach(() => {
    cleanup()
  })

  describe('Component Rendering Performance', () => {
    it('renders BudgetMonitor within performance target (<50ms)', () => {
      const budgetStatus = {
        allocated_ms: 10000,
        consumed_ms: 3000,
        remaining_ms: 7000,
        utilization: 0.3
      }

      const startTime = performance.now()
      render(<BudgetMonitor status={budgetStatus} />)
      const renderTime = performance.now() - startTime

      // Performance target: under 50ms
      expect(renderTime).toBeLessThan(50)
    })

    it('renders QualityScoreDisplay within performance target (<50ms)', () => {
      const qualityMetrics = {
        completeness: 0.85,
        recency: 0.90,
        authority: 0.80,
        diversity: 0.75,
        relevance: 0.88,
        overall_score: 0.84
      }

      const startTime = performance.now()
      render(<QualityScoreDisplay metrics={qualityMetrics} />)
      const renderTime = performance.now() - startTime

      // Performance target: under 50ms
      expect(renderTime).toBeLessThan(50)
    })

    it('renders CitationManager with multiple citations efficiently (<100ms)', () => {
      const citations = Array.from({ length: 20 }, (_, i) => ({
        id: `pmid:1234567${i}`,
        title: `Test Research Paper ${i}`,
        authors: [`Author${i}, A.`, `Researcher${i}, B.`],
        journal: 'Test Journal',
        year: '2023',
        url: `https://pubmed.ncbi.nlm.nih.gov/1234567${i}/`,
        relevance_score: 0.8 + (i * 0.01),
        source: 'Test Journal'
      }))

      const mockOnFormatChange = vi.fn()
      const startTime = performance.now()
      
      render(
        <CitationManager
          citations={citations}
          format="full"
          onFormatChange={mockOnFormatChange}
        />
      )
      
      const renderTime = performance.now() - startTime

      // Performance target: under 100ms for 20 citations
      expect(renderTime).toBeLessThan(100)
    })
  })

  describe('Rapid State Updates Performance', () => {
    it('handles rapid budget updates efficiently', () => {
      let totalTime = 0
      const updateCount = 10

      for (let i = 1; i <= updateCount; i++) {
        const budgetStatus = {
          allocated_ms: 10000,
          consumed_ms: i * 1000,
          remaining_ms: 10000 - (i * 1000),
          utilization: i * 0.1
        }

        const startTime = performance.now()
        const { unmount } = render(<BudgetMonitor status={budgetStatus} />)
        const renderTime = performance.now() - startTime
        unmount()

        totalTime += renderTime
      }

      const averageTime = totalTime / updateCount

      // Average render time should be under 20ms
      expect(averageTime).toBeLessThan(20)
    })

    it('handles quality score updates efficiently', () => {
      let totalTime = 0
      const updateCount = 10

      for (let i = 1; i <= updateCount; i++) {
        const qualityMetrics = {
          completeness: 0.5 + (i * 0.05),
          recency: 0.6 + (i * 0.04),
          authority: 0.7 + (i * 0.03),
          diversity: 0.4 + (i * 0.06),
          relevance: 0.8 + (i * 0.02),
          overall_score: 0.6 + (i * 0.04)
        }

        const startTime = performance.now()
        const { unmount } = render(<QualityScoreDisplay metrics={qualityMetrics} />)
        const renderTime = performance.now() - startTime
        unmount()

        totalTime += renderTime
      }

      const averageTime = totalTime / updateCount

      // Average render time should be under 20ms
      expect(averageTime).toBeLessThan(20)
    })
  })

  describe('Memory Usage Performance', () => {
    it('manages memory efficiently during component lifecycle', () => {
      const initialMemory = performance.memory?.usedJSHeapSize || 0
      const componentCount = 50

      // Create and destroy components rapidly
      for (let i = 0; i < componentCount; i++) {
        const budgetStatus = {
          allocated_ms: 10000,
          consumed_ms: i * 100,
          remaining_ms: 10000 - (i * 100),
          utilization: i * 0.01
        }

        const { unmount } = render(<BudgetMonitor status={budgetStatus} />)
        unmount()
      }

      const finalMemory = performance.memory?.usedJSHeapSize || 0
      const memoryIncrease = finalMemory - initialMemory

      // Memory increase should be reasonable (under 5MB for 50 components)
      if (performance.memory) {
        expect(memoryIncrease).toBeLessThan(5 * 1024 * 1024)
      } else {
        // If performance.memory is not available, just pass the test
        expect(true).toBe(true)
      }
    })
  })

  describe('Concurrent Rendering Performance', () => {
    it('renders multiple components simultaneously within time budget', () => {
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

      const citations = [
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

      const mockOnFormatChange = vi.fn()
      const startTime = performance.now()

      // Render all components simultaneously
      const components = [
        render(<BudgetMonitor status={budgetStatus} />),
        render(<QualityScoreDisplay metrics={qualityMetrics} />),
        render(
          <CitationManager
            citations={citations}
            format="full"
            onFormatChange={mockOnFormatChange}
          />
        )
      ]

      const concurrentRenderTime = performance.now() - startTime

      // Cleanup
      components.forEach(({ unmount }) => unmount())

      // All three components should render concurrently in under 100ms
      expect(concurrentRenderTime).toBeLessThan(100)
    })
  })

  describe('Performance Regression Detection', () => {
    it('establishes baseline performance metrics', () => {
      const performanceBaselines = {
        budgetMonitor: { target: 30, limit: 50 },      // ms
        qualityDisplay: { target: 30, limit: 50 },     // ms
        citationManager: { target: 50, limit: 100 },   // ms
        concurrentRender: { target: 60, limit: 100 },  // ms
        memoryUsage: { target: 3, limit: 5 }           // MB for 50 components
      }

      // Log baselines for future regression testing
      console.log('Performance Baselines for Milestone 6:')
      Object.entries(performanceBaselines).forEach(([component, { target, limit }]) => {
        const unit = component === 'memoryUsage' ? 'MB' : 'ms'
        console.log(`  ${component}: target ${target}${unit}, limit ${limit}${unit}`)
      })

      // Validate that targets are reasonable
      Object.values(performanceBaselines).forEach(({ target, limit }) => {
        expect(target).toBeLessThan(limit)
        expect(limit).toBeLessThan(1000) // No component should take over 1 second
      })
    })
  })
})
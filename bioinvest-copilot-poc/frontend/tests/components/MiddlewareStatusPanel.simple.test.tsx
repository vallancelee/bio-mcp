/**
 * MiddlewareStatusPanel Simple Unit Tests
 * 
 * Testing individual functions and basic rendering with TDD approach
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MiddlewareStatusPanel, { MiddlewareStatusData } from '../../src/components/MiddlewareStatusPanel'

describe('MiddlewareStatusPanel Simple Tests', () => {
  const mockStatus: MiddlewareStatusData = {
    active_middleware: {
      budget_enforcement: {
        enabled: true,
        active_queries: 2,
        default_budget_ms: 5000
      },
      error_recovery: {
        enabled: true,
        retry_strategy: 'exponential_backoff',
        success_rate: 0.95
      },
      partial_results: {
        enabled: false,
        extraction_rate: 0.75
      }
    },
    performance_metrics: {
      average_execution_time: 3200,
      timeout_rate: 0.05,
      retry_rate: 0.12,
      partial_results_rate: 0.08
    }
  }

  // Test 1: Basic rendering
  it('renders component title', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByText('Middleware Components')).toBeInTheDocument()
  })

  // Test 2: Component test ID
  it('renders with correct test ID', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByTestId('middleware-status-panel')).toBeInTheDocument()
  })

  // Test 3: Budget enforcement section
  it('renders budget enforcement section', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByTestId('budget-enforcement')).toBeInTheDocument()
    expect(screen.getByText('Budget Enforcement')).toBeInTheDocument()
  })

  // Test 4: Error recovery section
  it('renders error recovery section', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByTestId('error-recovery')).toBeInTheDocument()
    expect(screen.getByText('Error Recovery')).toBeInTheDocument()
  })

  // Test 5: Partial results section
  it('renders partial results section', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByTestId('partial-results')).toBeInTheDocument()
    expect(screen.getByText('Partial Results')).toBeInTheDocument()
  })

  // Test 6: Active status badges
  it('shows Active badge for enabled components', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    // Budget enforcement is enabled
    const budgetSection = screen.getByTestId('budget-enforcement')
    expect(budgetSection).toHaveTextContent('Active')
    
    // Error recovery is enabled
    const errorSection = screen.getByTestId('error-recovery')
    expect(errorSection).toHaveTextContent('Active')
  })

  // Test 7: Inactive status badges
  it('shows Inactive badge for disabled components', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    // Partial results is disabled
    const partialSection = screen.getByTestId('partial-results')
    expect(partialSection).toHaveTextContent('Inactive')
  })

  // Test 8: Budget enforcement details
  it('displays budget enforcement details when enabled', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByText('Default Budget: 5.0s')).toBeInTheDocument()
    expect(screen.getByText('Active Queries: 2')).toBeInTheDocument()
  })

  // Test 9: Error recovery details
  it('displays error recovery details when enabled', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByText('Strategy: exponential_backoff')).toBeInTheDocument()
    expect(screen.getByText('Success Rate: 95.0%')).toBeInTheDocument()
  })

  // Test 10: Performance metrics section
  it('renders performance metrics section', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByText('Performance Metrics')).toBeInTheDocument()
  })

  // Test 11: Average execution time formatting
  it('formats average execution time correctly', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByTestId('avg-execution-time')).toHaveTextContent('3.2s')
  })

  // Test 12: Timeout rate formatting
  it('formats timeout rate as percentage', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByTestId('timeout-rate')).toHaveTextContent('5.0%')
  })

  // Test 13: Retry rate formatting
  it('formats retry rate as percentage', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByTestId('retry-rate')).toHaveTextContent('12.0%')
  })

  // Test 14: Partial rate formatting
  it('formats partial results rate as percentage', () => {
    render(<MiddlewareStatusPanel status={mockStatus} />)
    
    expect(screen.getByTestId('partial-rate')).toHaveTextContent('8.0%')
  })

  // Test 15: Millisecond time formatting
  it('formats small times in milliseconds', () => {
    const shortTimeStatus = {
      ...mockStatus,
      performance_metrics: {
        ...mockStatus.performance_metrics,
        average_execution_time: 750  // Less than 1000ms
      }
    }
    
    render(<MiddlewareStatusPanel status={shortTimeStatus} />)
    
    expect(screen.getByTestId('avg-execution-time')).toHaveTextContent('750ms')
  })
})
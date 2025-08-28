/**
 * RetryVisualizer Component Tests
 * 
 * Comprehensive tests for the M3 retry visualization functionality
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import RetryVisualizer, { RetryAttempt } from '../../src/components/RetryVisualizer'

describe('RetryVisualizer', () => {
  const createMockRetryAttempt = (overrides: Partial<RetryAttempt> = {}): RetryAttempt => ({
    node: 'pubmed_search',
    attempt: 1,
    max_attempts: 3,
    delay_ms: 1000,
    error: 'Connection timeout',
    timestamp: '2024-01-01T10:00:00Z',
    ...overrides
  })

  it('renders nothing when no retry attempts', () => {
    const { container } = render(<RetryVisualizer attempts={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders retry attempts with correct information', () => {
    const attempts = [
      createMockRetryAttempt(),
      createMockRetryAttempt({
        node: 'clinical_trials_search',
        attempt: 2,
        delay_ms: 2000,
        error: 'Rate limit exceeded'
      })
    ]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByTestId('retry-visualizer')).toBeInTheDocument()
    expect(screen.getByText('Error Recovery')).toBeInTheDocument()
    expect(screen.getByText('(2 active)')).toBeInTheDocument()
    
    expect(screen.getByText('pubmed_search')).toBeInTheDocument()
    expect(screen.getByText('clinical_trials_search')).toBeInTheDocument()
    
    expect(screen.getByText('Next retry in 1.0s')).toBeInTheDocument()
    expect(screen.getByText('Next retry in 2.0s')).toBeInTheDocument()
  })

  it('formats delay times correctly', () => {
    const attempts = [
      createMockRetryAttempt({ delay_ms: 500 }),
      createMockRetryAttempt({ node: 'test2', delay_ms: 1500 }),
      createMockRetryAttempt({ node: 'test3', delay_ms: 5000 })
    ]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByText('Next retry in 500ms')).toBeInTheDocument()
    expect(screen.getByText('Next retry in 1.5s')).toBeInTheDocument()
    expect(screen.getByText('Next retry in 5.0s')).toBeInTheDocument()
  })

  it('displays attempt ratios with correct badges', () => {
    const attempts = [
      createMockRetryAttempt({ attempt: 1, max_attempts: 3 }),
      createMockRetryAttempt({ node: 'test2', attempt: 2, max_attempts: 3 }),
      createMockRetryAttempt({ node: 'test3', attempt: 3, max_attempts: 3 })
    ]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByText('1/3')).toBeInTheDocument()
    expect(screen.getByText('2/3')).toBeInTheDocument()
    expect(screen.getByText('3/3')).toBeInTheDocument()
  })

  it('shows error messages when available', () => {
    const attempts = [
      createMockRetryAttempt({ error: 'Network timeout' }),
      createMockRetryAttempt({ node: 'test2', error: '' })
    ]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByText('Error: Network timeout')).toBeInTheDocument()
    // Test passes if error message is displayed
  })

  it('renders exponential backoff visualization', () => {
    const attempts = [createMockRetryAttempt({ max_attempts: 3 })]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByText('Backoff progression:')).toBeInTheDocument()
    expect(screen.getByText('Exponential backoff delays (hover for details)')).toBeInTheDocument()
  })

  it('displays retry attempt test id', () => {
    const attempts = [createMockRetryAttempt()]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByTestId('retry-attempt')).toBeInTheDocument()
  })

  it('shows summary statistics', () => {
    const attempts = [
      createMockRetryAttempt({ attempt: 1 }),
      createMockRetryAttempt({ node: 'test2', attempt: 2 })
    ]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByText('Total attempts:')).toBeInTheDocument()
    // Summary statistics should be visible
    expect(screen.getByText('Success rate:')).toBeInTheDocument()
  })
})
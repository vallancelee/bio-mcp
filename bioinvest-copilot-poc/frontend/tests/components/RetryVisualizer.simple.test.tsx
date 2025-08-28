/**
 * RetryVisualizer Simple Unit Tests
 * 
 * Testing individual functions and basic rendering with TDD approach
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import RetryVisualizer, { RetryAttempt } from '../../src/components/RetryVisualizer'

describe('RetryVisualizer Simple Tests', () => {
  // Test 1: Empty state
  it('renders nothing when no attempts provided', () => {
    const { container } = render(<RetryVisualizer attempts={[]} />)
    
    expect(container.firstChild).toBeNull()
  })

  // Test 2: Basic rendering with one attempt
  it('renders component with single attempt', () => {
    const attempts: RetryAttempt[] = [{
      node: 'test_node',
      attempt: 1,
      max_attempts: 3,
      delay_ms: 1000,
      error: 'test error',
      timestamp: '2024-01-01T10:00:00Z'
    }]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByTestId('retry-visualizer')).toBeInTheDocument()
    expect(screen.getByText('Error Recovery')).toBeInTheDocument()
  })

  // Test 3: Node name display
  it('displays node name correctly', () => {
    const attempts: RetryAttempt[] = [{
      node: 'pubmed_search',
      attempt: 1,
      max_attempts: 3,
      delay_ms: 1000,
      error: '',
      timestamp: '2024-01-01T10:00:00Z'
    }]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByText('pubmed_search')).toBeInTheDocument()
  })

  // Test 4: Attempt count display
  it('shows attempt ratio badge', () => {
    const attempts: RetryAttempt[] = [{
      node: 'test',
      attempt: 2,
      max_attempts: 5,
      delay_ms: 1000,
      error: '',
      timestamp: '2024-01-01T10:00:00Z'
    }]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByText('2/5')).toBeInTheDocument()
  })

  // Test 5: Delay formatting - milliseconds
  it('formats milliseconds correctly', () => {
    const attempts: RetryAttempt[] = [{
      node: 'test',
      attempt: 1,
      max_attempts: 3,
      delay_ms: 500,
      error: '',
      timestamp: '2024-01-01T10:00:00Z'
    }]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByText('Next retry in 500ms')).toBeInTheDocument()
  })

  // Test 6: Delay formatting - seconds
  it('formats seconds correctly', () => {
    const attempts: RetryAttempt[] = [{
      node: 'test',
      attempt: 1,
      max_attempts: 3,
      delay_ms: 2000,
      error: '',
      timestamp: '2024-01-01T10:00:00Z'
    }]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByText('Next retry in 2.0s')).toBeInTheDocument()
  })

  // Test 7: Active count display
  it('shows correct active attempt count', () => {
    const attempts: RetryAttempt[] = [
      {
        node: 'test1',
        attempt: 1,
        max_attempts: 3,
        delay_ms: 1000,
        error: '',
        timestamp: '2024-01-01T10:00:00Z'
      },
      {
        node: 'test2',
        attempt: 2,
        max_attempts: 3,
        delay_ms: 2000,
        error: '',
        timestamp: '2024-01-01T10:00:00Z'
      }
    ]
    
    render(<RetryVisualizer attempts={attempts} />)
    
    expect(screen.getByText('(2 active)')).toBeInTheDocument()
  })
})
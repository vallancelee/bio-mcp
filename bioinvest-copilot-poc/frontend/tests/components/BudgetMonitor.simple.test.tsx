/**
 * BudgetMonitor Simple Unit Tests
 * 
 * Testing individual functions and basic rendering with TDD approach
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import BudgetMonitor from '../../src/components/BudgetMonitor'
import { BudgetStatus } from '../../src/shared-types'

describe('BudgetMonitor Simple Tests', () => {
  // Test 1: Basic rendering
  it('renders the component title', () => {
    const status: BudgetStatus = {
      allocated_ms: 10000,
      consumed_ms: 1000,
      remaining_ms: 9000,
      utilization: 0.1
    }
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.getByText('Budget Monitor')).toBeInTheDocument()
  })

  // Test 2: Basic progress display
  it('displays utilization percentage', () => {
    const status: BudgetStatus = {
      allocated_ms: 10000,
      consumed_ms: 3000,
      remaining_ms: 7000,
      utilization: 0.3
    }
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.getByText('30%')).toBeInTheDocument()
  })

  // Test 3: Time formatting
  it('formats time in seconds correctly', () => {
    const status: BudgetStatus = {
      allocated_ms: 10000,
      consumed_ms: 2500,
      remaining_ms: 7500,
      utilization: 0.25
    }
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.getByText('Consumed: 3s')).toBeInTheDocument()
    expect(screen.getByText('Remaining: 8s')).toBeInTheDocument()
  })

  // Test 4: Warning threshold - none shown for low usage
  it('does not show warning for low usage', () => {
    const status: BudgetStatus = {
      allocated_ms: 10000,
      consumed_ms: 5000,
      remaining_ms: 5000,
      utilization: 0.5
    }
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.queryByTestId('budget-warning')).not.toBeInTheDocument()
  })

  // Test 5: Warning threshold - shown for high usage
  it('shows warning for high usage', () => {
    const status: BudgetStatus = {
      allocated_ms: 10000,
      consumed_ms: 8500,
      remaining_ms: 1500,
      utilization: 0.85
    }
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.getByTestId('budget-warning')).toBeInTheDocument()
  })

  // Test 6: Progress bar element exists
  it('renders progress bar', () => {
    const status: BudgetStatus = {
      allocated_ms: 10000,
      consumed_ms: 2000,
      remaining_ms: 8000,
      utilization: 0.2
    }
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.getByTestId('budget-progress')).toBeInTheDocument()
  })
})
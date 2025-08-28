/**
 * BudgetMonitor Component Tests
 * 
 * Comprehensive tests for the M3 budget monitoring functionality
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import BudgetMonitor from '../../src/components/BudgetMonitor'
import { BudgetStatus } from '../../src/shared-types'

describe('BudgetMonitor', () => {
  const createMockBudgetStatus = (overrides: Partial<BudgetStatus> = {}): BudgetStatus => ({
    allocated_ms: 10000,
    consumed_ms: 5000,
    remaining_ms: 5000,
    utilization: 0.5,
    ...overrides
  })

  it('renders budget monitor with normal usage', () => {
    const status = createMockBudgetStatus()
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.getByTestId('budget-monitor')).toBeInTheDocument()
    expect(screen.getByText('Budget Monitor')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByText('Consumed: 5s')).toBeInTheDocument()
    expect(screen.getByText('Remaining: 5s')).toBeInTheDocument()
  })

  it('shows warning state at 80% utilization', () => {
    const status = createMockBudgetStatus({
      consumed_ms: 8000,
      remaining_ms: 2000,
      utilization: 0.8
    })
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.getByTestId('budget-warning')).toBeInTheDocument()
    expect(screen.getByText('High Budget Usage')).toBeInTheDocument()
    expect(screen.getByText(/Budget usage high/)).toBeInTheDocument()
  })

  it('shows critical state at 90% utilization', () => {
    const status = createMockBudgetStatus({
      consumed_ms: 9000,
      remaining_ms: 1000,
      utilization: 0.9
    })
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.getByTestId('budget-warning')).toBeInTheDocument()
    expect(screen.getByText('Critical Budget Usage!')).toBeInTheDocument()
    expect(screen.getByText(/Query may timeout very soon/)).toBeInTheDocument()
  })

  it('handles edge case of 100% utilization', () => {
    const status = createMockBudgetStatus({
      consumed_ms: 10000,
      remaining_ms: 0,
      utilization: 1.0
    })
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.getByText('100%')).toBeInTheDocument()
    expect(screen.getByText('Remaining: 0s')).toBeInTheDocument()
    expect(screen.getByTestId('budget-warning')).toBeInTheDocument()
  })

  it('handles fractional seconds correctly', () => {
    const status = createMockBudgetStatus({
      allocated_ms: 1500,
      consumed_ms: 750,
      remaining_ms: 750,
      utilization: 0.5
    })
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.getByText('Consumed: 1s')).toBeInTheDocument()
    expect(screen.getByText('Remaining: 1s')).toBeInTheDocument()
  })

  it('renders progress bar with correct width', () => {
    const status = createMockBudgetStatus({ utilization: 0.75 })
    
    render(<BudgetMonitor status={status} />)
    
    const progressBar = screen.getByTestId('budget-progress')
    expect(progressBar).toHaveStyle({ width: '75%' })
  })

  it('does not show warning for usage below 80%', () => {
    const status = createMockBudgetStatus({ utilization: 0.79 })
    
    render(<BudgetMonitor status={status} />)
    
    expect(screen.queryByTestId('budget-warning')).not.toBeInTheDocument()
  })
})
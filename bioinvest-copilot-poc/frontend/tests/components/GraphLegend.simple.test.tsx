/**
 * GraphLegend Simple Unit Tests
 * 
 * Testing individual functions and basic rendering with TDD approach
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import GraphLegend from '../../src/components/GraphLegend'

describe('GraphLegend Simple Tests', () => {
  // Test 1: Basic rendering
  it('renders component title', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Legend')).toBeInTheDocument()
  })

  // Test 2: Component test ID
  it('renders with correct test ID', () => {
    render(<GraphLegend />)
    
    expect(screen.getByTestId('graph-legend')).toBeInTheDocument()
  })

  // Test 3: Node types section
  it('renders node types section', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Node Types')).toBeInTheDocument()
  })

  // Test 4: Execution status section
  it('renders execution status section', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Execution Status')).toBeInTheDocument()
  })

  // Test 5: Flow indicators section
  it('renders flow indicators section', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Flow Indicators')).toBeInTheDocument()
  })

  // Test 6: Performance indicators section
  it('renders performance indicators section', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Performance Indicators')).toBeInTheDocument()
  })

  // Test 7: Source node type
  it('displays source node type', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Source Node')).toBeInTheDocument()
    expect(screen.getByText('Data retrieval (PubMed, ClinicalTrials)')).toBeInTheDocument()
  })

  // Test 8: Middleware node type
  it('displays middleware node type', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Middleware')).toBeInTheDocument()
    expect(screen.getByText('Processing and state management')).toBeInTheDocument()
  })

  // Test 9: Synthesis node type
  it('displays synthesis node type', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Synthesis')).toBeInTheDocument()
    expect(screen.getByText('AI analysis and answer generation')).toBeInTheDocument()
  })

  // Test 10: Router node type
  it('displays router node type', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Router')).toBeInTheDocument()
    expect(screen.getByText('Decision and flow control')).toBeInTheDocument()
  })

  // Test 11: Pending status
  it('displays pending status', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Pending')).toBeInTheDocument()
    expect(screen.getByText('Not yet started')).toBeInTheDocument()
  })

  // Test 12: Active status
  it('displays active status', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Currently executing')).toBeInTheDocument()
  })

  // Test 13: Completed status
  it('displays completed status', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Completed')).toBeInTheDocument()
    expect(screen.getByText('Successfully finished')).toBeInTheDocument()
  })

  // Test 14: Failed status
  it('displays failed status', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('Encountered error')).toBeInTheDocument()
  })

  // Test 15: Flow path descriptions
  it('displays flow path descriptions', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText('Active path')).toBeInTheDocument()
    expect(screen.getByText('Inactive path')).toBeInTheDocument()
  })

  // Test 16: Performance indicator descriptions
  it('displays performance indicator descriptions', () => {
    render(<GraphLegend />)
    
    expect(screen.getByText(/Node execution times shown below completed nodes/)).toBeInTheDocument()
    expect(screen.getByText(/Active nodes have pulsing animation/)).toBeInTheDocument()
    expect(screen.getByText(/Progress bar shows overall completion percentage/)).toBeInTheDocument()
  })

  // Test 17: Node type emojis
  it('displays node type emojis correctly', () => {
    render(<GraphLegend />)
    
    // Check if emojis are present (testing text content)
    expect(screen.getByText('📚')).toBeInTheDocument() // Source
    expect(screen.getByText('⚙️')).toBeInTheDocument() // Middleware
    expect(screen.getByText('🧠')).toBeInTheDocument() // Synthesis
    expect(screen.getByText('🎯')).toBeInTheDocument() // Router
  })
})
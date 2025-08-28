/**
 * LangGraphVisualizer Simple Unit Tests
 * 
 * Testing individual functions and basic rendering with TDD approach
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import LangGraphVisualizer, { LangGraphVisualizationData } from '../../src/components/LangGraphVisualizer'

describe('LangGraphVisualizer Simple Tests', () => {
  const mockVisualization: LangGraphVisualizationData = {
    nodes: [
      { id: 'node1', label: 'Parse Frame', type: 'router', x: 50, y: 50 },
      { id: 'node2', label: 'PubMed Search', type: 'source', x: 150, y: 100 },
      { id: 'node3', label: 'Synthesizer', type: 'synthesis', x: 100, y: 150 }
    ],
    edges: [
      { from: 'node1', to: 'node2' },
      { from: 'node2', to: 'node3' }
    ]
  }

  // Test 1: Basic rendering
  it('renders component title', () => {
    render(<LangGraphVisualizer visualization={mockVisualization} />)
    
    expect(screen.getByText('LangGraph Execution Flow')).toBeInTheDocument()
  })

  // Test 2: Component test ID
  it('renders with correct test ID', () => {
    render(<LangGraphVisualizer visualization={mockVisualization} />)
    
    expect(screen.getByTestId('langgraph-visualizer')).toBeInTheDocument()
  })

  // Test 3: Renders nodes
  it('renders all nodes', () => {
    render(<LangGraphVisualizer visualization={mockVisualization} />)
    
    expect(screen.getByText('Parse Frame')).toBeInTheDocument()
    expect(screen.getByText('PubMed Search')).toBeInTheDocument()
    expect(screen.getByText('Synthesizer')).toBeInTheDocument()
  })

  // Test 4: Node test IDs
  it('renders nodes with correct test IDs', () => {
    render(<LangGraphVisualizer visualization={mockVisualization} />)
    
    expect(screen.getByTestId('node-node1')).toBeInTheDocument()
    expect(screen.getByTestId('node-node2')).toBeInTheDocument()
    expect(screen.getByTestId('node-node3')).toBeInTheDocument()
  })

  // Test 5: Active node styling
  it('highlights active node correctly', () => {
    render(
      <LangGraphVisualizer 
        visualization={mockVisualization} 
        activeNode="node2"
      />
    )
    
    const activeNode = screen.getByTestId('node-node2')
    expect(activeNode).toHaveClass('bg-blue-100', 'border-blue-500')
  })

  // Test 6: Completed nodes in current path
  it('shows completed nodes correctly', () => {
    render(
      <LangGraphVisualizer 
        visualization={mockVisualization} 
        currentPath={['node1', 'node2']}
        activeNode="node3"
      />
    )
    
    const completedNode = screen.getByTestId('node-node1')
    expect(completedNode).toHaveClass('bg-green-100', 'border-green-500')
  })

  // Test 7: Pending nodes styling
  it('shows pending nodes correctly', () => {
    render(
      <LangGraphVisualizer 
        visualization={mockVisualization} 
        currentPath={['node1']}
        activeNode="node2"
      />
    )
    
    const pendingNode = screen.getByTestId('node-node3')
    expect(pendingNode).toHaveClass('bg-gray-100', 'border-gray-300')
  })

  // Test 8: Execution progress display
  it('shows execution progress when path exists', () => {
    render(
      <LangGraphVisualizer 
        visualization={mockVisualization} 
        currentPath={['node1', 'node2']}
      />
    )
    
    expect(screen.getByText('Execution Progress: 2/3 nodes')).toBeInTheDocument()
  })

  // Test 9: No progress when no path
  it('hides execution progress when no current path', () => {
    render(<LangGraphVisualizer visualization={mockVisualization} />)
    
    expect(screen.queryByText(/Execution Progress/)).not.toBeInTheDocument()
  })

  // Test 10: Execution metrics display
  it('displays execution metrics for completed nodes', () => {
    render(
      <LangGraphVisualizer 
        visualization={mockVisualization}
        currentPath={['node1']}
        executionMetrics={{ node1: 250 }}
      />
    )
    
    expect(screen.getByText('250ms')).toBeInTheDocument()
  })

  // Test 11: Current node display in progress
  it('displays current active node in progress', () => {
    render(
      <LangGraphVisualizer 
        visualization={mockVisualization} 
        currentPath={['node1']}
        activeNode="node2"
      />
    )
    
    expect(screen.getByText('Current: node2')).toBeInTheDocument()
  })

  // Test 12: Empty nodes handling
  it('handles empty node list gracefully', () => {
    const emptyVisualization = { nodes: [], edges: [] }
    
    render(<LangGraphVisualizer visualization={emptyVisualization} />)
    
    expect(screen.getByText('LangGraph Execution Flow')).toBeInTheDocument()
    // Progress section only shows when there's a current path
    expect(screen.queryByText(/Execution Progress/)).not.toBeInTheDocument()
  })
})
/**
 * CitationManager Simple Unit Tests
 * 
 * Testing individual functions and basic rendering with TDD approach
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import CitationManager, { Citation, CitationFormat } from '../../src/components/CitationManager'

// Mock navigator.clipboard
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn(() => Promise.resolve()),
  },
})

describe('CitationManager Simple Tests', () => {
  const mockCitations: Citation[] = [
    {
      id: 'pmid:12345678',
      title: 'Test Article Title',
      authors: ['Smith, J.', 'Doe, A.'],
      source: 'Test Journal',
      year: '2023',
      url: 'https://example.com',
      relevance_score: 0.85
    },
    {
      id: 'pmid:87654321',
      title: 'Another Test Article',
      authors: ['Johnson, B.'],
      source: 'Another Journal',
      year: '2022',
      relevance_score: 0.72
    }
  ]

  let mockOnFormatChange: (format: CitationFormat) => void

  beforeEach(() => {
    mockOnFormatChange = vi.fn()
    vi.clearAllMocks()
  })

  // Test 1: Basic rendering
  it('renders component title', () => {
    render(
      <CitationManager
        citations={mockCitations}
        format="full"
        onFormatChange={mockOnFormatChange}
      />
    )
    
    expect(screen.getByText('Citations')).toBeInTheDocument()
  })

  // Test 2: Citation count display
  it('displays correct citation count', () => {
    render(
      <CitationManager
        citations={mockCitations}
        format="full"
        onFormatChange={mockOnFormatChange}
      />
    )
    
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  // Test 3: Empty state
  it('shows empty state when no citations', () => {
    render(
      <CitationManager
        citations={[]}
        format="full"
        onFormatChange={mockOnFormatChange}
      />
    )
    
    expect(screen.getByText('No citations available')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  // Test 4: Full format display
  it('formats citations in full format correctly', () => {
    render(
      <CitationManager
        citations={[mockCitations[0]]}
        format="full"
        onFormatChange={mockOnFormatChange}
      />
    )
    
    expect(screen.getByText(/Smith, J\., Doe, A\./)).toBeInTheDocument()
    expect(screen.getByText(/Test Article Title/)).toBeInTheDocument()
    expect(screen.getByText(/Test Journal/)).toBeInTheDocument()
    expect(screen.getByText(/2023/)).toBeInTheDocument()
  })

  // Test 5: PMID format display
  it('formats citations in PMID format correctly', () => {
    render(
      <CitationManager
        citations={[mockCitations[0]]}
        format="pmid"
        onFormatChange={mockOnFormatChange}
      />
    )
    
    expect(screen.getByText('PMID: 12345678')).toBeInTheDocument()
  })

  // Test 6: Inline format display
  it('formats citations in inline format correctly', () => {
    render(
      <CitationManager
        citations={[mockCitations[0]]}
        format="inline"
        onFormatChange={mockOnFormatChange}
      />
    )
    
    expect(screen.getByText('Smith, J. et al. (2023)')).toBeInTheDocument()
  })

  // Test 7: Relevance score display
  it('displays relevance scores correctly', () => {
    render(
      <CitationManager
        citations={[mockCitations[0]]}
        format="full"
        onFormatChange={mockOnFormatChange}
      />
    )
    
    expect(screen.getByText('Relevance: 85%')).toBeInTheDocument()
  })

  // Test 8: External link button
  it('shows external link for citations with URLs', () => {
    render(
      <CitationManager
        citations={[mockCitations[0]]}
        format="full"
        onFormatChange={mockOnFormatChange}
      />
    )
    
    expect(screen.getByTestId('external-link')).toBeInTheDocument()
  })

  // Test 9: Copy buttons exist
  it('shows copy buttons', () => {
    render(
      <CitationManager
        citations={mockCitations}
        format="full"
        onFormatChange={mockOnFormatChange}
      />
    )
    
    expect(screen.getByTestId('copy-all-citations')).toBeInTheDocument()
    expect(screen.getAllByTestId('copy-single-citation')).toHaveLength(2)
  })

  // Test 10: Format selector exists
  it('shows format selector', () => {
    render(
      <CitationManager
        citations={mockCitations}
        format="full"
        onFormatChange={mockOnFormatChange}
      />
    )
    
    expect(screen.getByTestId('citation-format-selector')).toBeInTheDocument()
  })
})
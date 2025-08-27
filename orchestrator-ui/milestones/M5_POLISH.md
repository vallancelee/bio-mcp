# M5 — Polish & Deployment (1 day)

## Objective
Finalize the orchestrator UI with comprehensive testing, performance optimization, accessibility improvements, documentation, and deployment preparation. This milestone ensures the application is production-ready with excellent user experience and maintainability.

## Dependencies
- **M1-M4** completed (full functionality implemented)
- All major features working: API integration, core UI, streaming, visualization, and debugging
- React application with all components and hooks functional
- Bio-MCP orchestrator with complete API endpoints

## Deliverables

### 1. End-to-End Testing Suite

**File**: `tests/e2e/complete-orchestration-flow.spec.ts`
```typescript
import { test, expect, Page } from '@playwright/test'

test.describe('Complete Orchestration Flow', () => {
  let page: Page

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage()
    await page.goto('/orchestrator/')
    
    // Wait for application to load
    await expect(page.locator('h1:has-text("Bio-MCP Orchestrator")')).toBeVisible()
  })

  test('full biomedical query orchestration', async () => {
    // Step 1: Enter query
    const query = 'GLP-1 receptor agonist clinical trials for diabetes treatment Phase 3'
    await page.fill('textarea[placeholder*="clinical trials"]', query)
    
    // Step 2: Verify entity extraction
    await expect(page.locator('text=Extracted Entities')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('text=GLP-1')).toBeVisible()
    await expect(page.locator('text=diabetes')).toBeVisible()
    
    // Step 3: Configure advanced settings
    await page.click('button:has-text("Advanced")')
    await page.check('[data-testid="debug-mode-switch"]')
    await page.fill('[data-testid="session-name"]', 'E2E Test Session')
    
    // Step 4: Execute orchestration
    await page.click('button:has-text("Execute Orchestration")')
    
    // Step 5: Verify streaming connection
    await expect(page.locator('[data-testid="connection-status"]:has-text("Connected")')).toBeVisible({ timeout: 10000 })
    
    // Step 6: Monitor graph execution
    await expect(page.locator('.react-flow')).toBeVisible()
    await expect(page.locator('[data-testid="rf__node"]')).toHaveCount.greaterThan(0)
    
    // Wait for nodes to show execution progress
    await expect(page.locator('[data-testid="node-status-running"]')).toBeVisible({ timeout: 15000 })
    
    // Step 7: Verify streaming results appear
    await expect(page.locator('[data-testid="streaming-results"]')).toBeVisible({ timeout: 20000 })
    
    // Check that all three source tabs are present and populated
    const pubmedTab = page.locator('tab:has-text("PubMed")')
    const trialsTab = page.locator('tab:has-text("Trials")')
    const ragTab = page.locator('tab:has-text("RAG")')
    
    await expect(pubmedTab).toBeVisible()
    await expect(trialsTab).toBeVisible()
    await expect(ragTab).toBeVisible()
    
    // Step 8: Check results in each tab
    await pubmedTab.click()
    await expect(page.locator('[data-testid="pubmed-results"]')).toBeVisible()
    await expect(page.locator('[data-testid="result-count"]')).toContainText(/\d+ articles/)
    
    await trialsTab.click()
    await expect(page.locator('[data-testid="trials-results"]')).toBeVisible()
    
    await ragTab.click()
    await expect(page.locator('[data-testid="rag-results"]')).toBeVisible()
    
    // Step 9: Verify synthesis tab
    await page.click('tab:has-text("Synthesis")')
    await expect(page.locator('[data-testid="synthesized-answer"]')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('[data-testid="citations"]')).toBeVisible()
    await expect(page.locator('[data-testid="quality-metrics"]')).toBeVisible()
    
    // Step 10: Verify final orchestration completion
    await expect(page.locator('text=Orchestration completed')).toBeVisible({ timeout: 45000 })
  })

  test('debug mode with breakpoints', async () => {
    // Enable debug mode
    await page.fill('textarea[placeholder*="clinical trials"]', 'diabetes research')
    await page.click('button:has-text("Advanced")')
    await page.check('[data-testid="debug-mode-switch"]')
    
    // Set breakpoint
    await page.click('button:has-text("Execute Orchestration")')
    await expect(page.locator('[data-testid="debug-controls"]')).toBeVisible({ timeout: 10000 })
    
    // Click on a graph node to set breakpoint
    const firstNode = page.locator('[data-testid="rf__node"]').first()
    await firstNode.click()
    await page.click('button:has-text("Set Breakpoint")')
    
    // Verify breakpoint is active
    await expect(page.locator('[data-testid="active-breakpoint"]')).toBeVisible()
    
    // Test step execution
    await page.click('button:has-text("Step")')
    await expect(page.locator('text=Paused at breakpoint')).toBeVisible()
    
    // Resume execution
    await page.click('button:has-text("Resume")')
    await expect(page.locator('text=Execution resumed')).toBeVisible()
  })

  test('session history and replay', async () => {
    // Execute a query first
    await page.fill('textarea[placeholder*="clinical trials"]', 'oncology trials')
    await page.fill('[data-testid="session-name"]', 'History Test Session')
    await page.click('button:has-text("Execute Orchestration")')
    
    // Wait for completion
    await expect(page.locator('text=Orchestration completed')).toBeVisible({ timeout: 30000 })
    
    // Open session history
    await page.click('button:has-text("History")')
    await expect(page.locator('[data-testid="session-history"]')).toBeVisible()
    
    // Find and click on our session
    await expect(page.locator('text=History Test Session')).toBeVisible()
    await page.click('text=History Test Session')
    
    // Verify session details are loaded
    await expect(page.locator('[data-testid="session-details"]')).toBeVisible()
    await expect(page.locator('text=oncology trials')).toBeVisible()
    
    // Test session comparison
    await page.click('[data-testid="compare-session"]')
    await expect(page.locator('[data-testid="session-comparison"]')).toBeVisible()
  })

  test('error handling and recovery', async () => {
    // Test with invalid query or network issues
    await page.fill('textarea[placeholder*="clinical trials"]', 'test query')
    
    // Simulate network error by intercepting API calls
    await page.route('/orchestrator/v1/orchestrator/query', route => 
      route.fulfill({ status: 500, body: 'Server Error' })
    )
    
    await page.click('button:has-text("Execute Orchestration")')
    
    // Verify error handling
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('text=Server Error')).toBeVisible()
    
    // Test retry functionality
    await page.unroute('/orchestrator/v1/orchestrator/query')
    await page.click('button:has-text("Retry")')
    
    // Should work normally after retry
    await expect(page.locator('[data-testid="connection-status"]:has-text("Connected")')).toBeVisible({ timeout: 10000 })
  })

  test('performance under load', async () => {
    // Execute multiple queries simultaneously
    const queries = [
      'diabetes treatment',
      'cancer immunotherapy', 
      'alzheimer clinical trials',
      'cardiovascular research'
    ]
    
    for (const query of queries) {
      await page.fill('textarea[placeholder*="clinical trials"]', query)
      await page.click('button:has-text("Execute Orchestration")')
      
      // Don't wait for completion, just verify it starts
      await expect(page.locator('[data-testid="connection-status"]:has-text("Connected")')).toBeVisible({ timeout: 5000 })
      
      // Open new tab for next query (simulate multiple sessions)
      if (query !== queries[queries.length - 1]) {
        const newPage = await page.context().newPage()
        await newPage.goto('/orchestrator/')
        page = newPage
      }
    }
  })

  test('accessibility compliance', async () => {
    // Test keyboard navigation
    await page.keyboard.press('Tab') // Should focus on query textarea
    await expect(page.locator('textarea:focus')).toBeVisible()
    
    await page.keyboard.press('Tab') // Should move to execute button
    await expect(page.locator('button:focus:has-text("Execute")')).toBeVisible()
    
    // Test ARIA labels and screen reader support
    const queryInput = page.locator('textarea[placeholder*="clinical trials"]')
    await expect(queryInput).toHaveAttribute('aria-label')
    
    // Test color contrast and visual indicators
    const executeButton = page.locator('button:has-text("Execute Orchestration")')
    const buttonBg = await executeButton.evaluate(el => getComputedStyle(el).backgroundColor)
    expect(buttonBg).toBeTruthy() // Should have background color
    
    // Test focus indicators
    await queryInput.focus()
    const focusOutline = await queryInput.evaluate(el => getComputedStyle(el).outline)
    expect(focusOutline).not.toBe('none')
  })

  test('responsive design', async () => {
    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 }) // iPhone SE
    await expect(page.locator('.grid')).toHaveCSS('grid-template-columns', /1fr/) // Should stack on mobile
    
    // Test tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 }) // iPad
    await expect(page.locator('.container')).toBeVisible()
    
    // Test desktop viewport
    await page.setViewportSize({ width: 1920, height: 1080 })
    await expect(page.locator('.grid')).toHaveCSS('grid-template-columns', /repeat/) // Should use grid on desktop
  })
})
```

### 2. Performance Optimization

**File**: `src/utils/performance.ts`
```tsx
// Performance monitoring and optimization utilities
export class PerformanceMonitor {
  private static instance: PerformanceMonitor
  private metrics: Map<string, number[]> = new Map()
  
  static getInstance(): PerformanceMonitor {
    if (!PerformanceMonitor.instance) {
      PerformanceMonitor.instance = new PerformanceMonitor()
    }
    return PerformanceMonitor.instance
  }
  
  startTiming(label: string): () => void {
    const startTime = performance.now()
    
    return () => {
      const duration = performance.now() - startTime
      this.recordMetric(label, duration)
    }
  }
  
  recordMetric(label: string, value: number): void {
    if (!this.metrics.has(label)) {
      this.metrics.set(label, [])
    }
    this.metrics.get(label)!.push(value)
    
    // Keep only last 100 measurements
    const measurements = this.metrics.get(label)!
    if (measurements.length > 100) {
      measurements.shift()
    }
  }
  
  getMetrics(label: string) {
    const measurements = this.metrics.get(label) || []
    if (measurements.length === 0) return null
    
    const avg = measurements.reduce((sum, val) => sum + val, 0) / measurements.length
    const min = Math.min(...measurements)
    const max = Math.max(...measurements)
    
    return { avg, min, max, count: measurements.length }
  }
  
  getAllMetrics() {
    const result: Record<string, any> = {}
    for (const [label, _] of this.metrics) {
      result[label] = this.getMetrics(label)
    }
    return result
  }
}

// React hook for performance monitoring
export function usePerformanceMonitor(label: string) {
  const monitor = PerformanceMonitor.getInstance()
  
  return React.useCallback(() => {
    return monitor.startTiming(label)
  }, [monitor, label])
}

// Bundle size analysis
export function analyzeBundleSize() {
  if (process.env.NODE_ENV === 'development') {
    import('webpack-bundle-analyzer').then(({ analyze }) => {
      // This would be configured in build process
      console.log('Bundle analysis available in build process')
    })
  }
}

// Memory usage monitoring
export function monitorMemoryUsage() {
  if ('memory' in performance) {
    const memory = (performance as any).memory
    return {
      usedJSHeapSize: memory.usedJSHeapSize,
      totalJSHeapSize: memory.totalJSHeapSize,
      jsHeapSizeLimit: memory.jsHeapSizeLimit,
      usagePercentage: (memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100
    }
  }
  return null
}

// Component performance wrapper
export function withPerformanceMonitor<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  componentName: string
) {
  return React.memo((props: P) => {
    const monitor = usePerformanceMonitor(`component:${componentName}`)
    
    React.useEffect(() => {
      const stopTiming = monitor()
      return stopTiming
    })
    
    return <WrappedComponent {...props} />
  })
}
```

**File**: `vite.config.ts` (Optimization)
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  plugins: [
    react(),
    visualizer({
      filename: 'dist/bundle-analysis.html',
      open: true,
      gzipSize: true,
      brotliSize: true,
    }),
  ],
  build: {
    target: 'es2020',
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'query-vendor': ['@tanstack/react-query'],
          'flow-vendor': ['react-flow-renderer'],
          'form-vendor': ['react-hook-form'],
          'utils': ['date-fns', 'clsx', 'tailwind-merge'],
        },
      },
    },
    sourcemap: true,
    reportCompressedSize: false,
  },
  server: {
    proxy: {
      '/orchestrator/v1': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/orchestrator/ws': {
        target: 'ws://localhost:8001',
        ws: true,
      },
    },
  },
})
```

### 3. Accessibility Improvements

**File**: `src/components/ui/AccessibilityProvider.tsx`
```tsx
import React, { createContext, useContext, useState, useEffect } from 'react'

interface AccessibilityContextType {
  highContrast: boolean
  reducedMotion: boolean
  screenReaderMode: boolean
  fontSize: 'small' | 'medium' | 'large'
  announceMessage: (message: string) => void
}

const AccessibilityContext = createContext<AccessibilityContextType | null>(null)

export function AccessibilityProvider({ children }: { children: React.ReactNode }) {
  const [highContrast, setHighContrast] = useState(false)
  const [reducedMotion, setReducedMotion] = useState(false)
  const [screenReaderMode, setScreenReaderMode] = useState(false)
  const [fontSize, setFontSize] = useState<'small' | 'medium' | 'large'>('medium')

  // Detect user preferences
  useEffect(() => {
    // Check for reduced motion preference
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReducedMotion(mediaQuery.matches)
    
    const handleChange = (e: MediaQueryListEvent) => setReducedMotion(e.matches)
    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [])

  // Screen reader detection
  useEffect(() => {
    // Simple screen reader detection
    const isScreenReader = window.navigator.userAgent.includes('NVDA') ||
                          window.navigator.userAgent.includes('JAWS') ||
                          window.speechSynthesis !== undefined
    setScreenReaderMode(isScreenReader)
  }, [])

  // Live region for announcements
  const announceMessage = (message: string) => {
    const liveRegion = document.getElementById('live-region')
    if (liveRegion) {
      liveRegion.textContent = message
      // Clear after announcement
      setTimeout(() => {
        liveRegion.textContent = ''
      }, 1000)
    }
  }

  // Apply CSS custom properties based on settings
  useEffect(() => {
    const root = document.documentElement
    
    if (highContrast) {
      root.classList.add('high-contrast')
    } else {
      root.classList.remove('high-contrast')
    }
    
    if (reducedMotion) {
      root.classList.add('reduce-motion')
    } else {
      root.classList.remove('reduce-motion')
    }
    
    root.setAttribute('data-font-size', fontSize)
  }, [highContrast, reducedMotion, fontSize])

  return (
    <AccessibilityContext.Provider value={{
      highContrast,
      reducedMotion,
      screenReaderMode,
      fontSize,
      announceMessage
    }}>
      {children}
      {/* Live region for screen reader announcements */}
      <div 
        id="live-region" 
        aria-live="polite" 
        aria-atomic="true" 
        className="sr-only"
      />
    </AccessibilityContext.Provider>
  )
}

export function useAccessibility() {
  const context = useContext(AccessibilityContext)
  if (!context) {
    throw new Error('useAccessibility must be used within AccessibilityProvider')
  }
  return context
}

// Accessibility settings component
export function AccessibilitySettings() {
  const { highContrast, fontSize, announceMessage } = useAccessibility()
  
  return (
    <div className="accessibility-settings" role="region" aria-label="Accessibility Settings">
      <h3>Accessibility Preferences</h3>
      
      <div className="setting-group">
        <label htmlFor="high-contrast">
          <input 
            type="checkbox" 
            id="high-contrast"
            checked={highContrast}
            onChange={(e) => {
              // This would update context state
              announceMessage(e.target.checked ? 'High contrast enabled' : 'High contrast disabled')
            }}
          />
          Enable High Contrast
        </label>
      </div>
      
      <div className="setting-group">
        <label htmlFor="font-size">Font Size</label>
        <select 
          id="font-size"
          value={fontSize}
          onChange={(e) => {
            // This would update context state
            announceMessage(`Font size changed to ${e.target.value}`)
          }}
        >
          <option value="small">Small</option>
          <option value="medium">Medium</option>
          <option value="large">Large</option>
        </select>
      </div>
    </div>
  )
}
```

**File**: `src/styles/accessibility.css`
```css
/* High contrast mode */
.high-contrast {
  --color-primary: #000;
  --color-secondary: #fff;
  --color-accent: #ffff00;
  --color-error: #ff0000;
  --color-success: #00ff00;
  --border-color: #000;
  --shadow: 0 0 0 2px #000;
}

/* Reduced motion */
.reduce-motion *,
.reduce-motion *::before,
.reduce-motion *::after {
  animation-duration: 0.01ms !important;
  animation-iteration-count: 1 !important;
  transition-duration: 0.01ms !important;
  scroll-behavior: auto !important;
}

/* Font size scaling */
[data-font-size="small"] {
  font-size: 14px;
}

[data-font-size="medium"] {
  font-size: 16px;
}

[data-font-size="large"] {
  font-size: 18px;
}

/* Screen reader only content */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Focus indicators */
*:focus {
  outline: 2px solid var(--color-accent, #3B82F6);
  outline-offset: 2px;
}

.high-contrast *:focus {
  outline: 3px solid var(--color-accent);
  outline-offset: 3px;
}

/* Ensure sufficient color contrast */
.high-contrast .btn-primary {
  background-color: #000;
  color: #fff;
  border: 2px solid #fff;
}

.high-contrast .btn-primary:hover {
  background-color: #fff;
  color: #000;
  border: 2px solid #000;
}

/* Skip navigation link */
.skip-nav {
  position: absolute;
  top: -40px;
  left: 6px;
  z-index: 1000;
  padding: 8px;
  background: #000;
  color: #fff;
  text-decoration: none;
  border-radius: 4px;
}

.skip-nav:focus {
  top: 6px;
}

/* Ensure interactive elements are large enough */
button, 
input[type="checkbox"], 
input[type="radio"],
select {
  min-height: 44px;
  min-width: 44px;
}

/* High contrast mode improvements */
.high-contrast .bg-gray-50 {
  background-color: #fff;
  border: 1px solid #000;
}

.high-contrast .text-gray-600 {
  color: #000;
}

.high-contrast .border-gray-200 {
  border-color: #000;
}
```

### 4. Documentation and User Guides

**File**: `docs/USER_GUIDE.md`
```markdown
# Bio-MCP Orchestrator UI - User Guide

## Getting Started

The Bio-MCP Orchestrator UI provides a comprehensive interface for testing and debugging the Bio-MCP orchestration service. This guide will walk you through all the features and capabilities.

### Initial Setup

1. **Access the Interface**: Navigate to `/orchestrator/` on your Bio-MCP server
2. **Verify Connection**: Check the status bar shows "Connected" in green
3. **Review Available Tools**: The tool count should show the number of available MCP tools

## Core Features

### 1. Query Builder

The query builder helps you construct biomedical queries with intelligent entity extraction.

#### Basic Usage
1. Enter your query in natural language in the main textarea
2. The system will automatically extract relevant entities (topics, indications, companies, NCT IDs)
3. Click "Execute Orchestration" to start the process

#### Advanced Configuration
Click "Advanced" to access:
- **Session Name**: Give your session a memorable name
- **Debug Mode**: Enable step-by-step execution with breakpoints
- **Time Budget**: Set maximum execution time
- **Fetch Policy**: Choose caching behavior
- **Filters**: Apply date ranges, phases, status filters

#### Example Queries
- "Latest GLP-1 receptor agonist trials for diabetes treatment"
- "Phase 3 oncology trials with FDA breakthrough designation" 
- "Recent CRISPR gene therapy publications"
- "Clinical trials for Alzheimer's disease treatments"

### 2. Real-Time Orchestration Monitoring

#### Graph Visualization
- **Node Status**: Watch nodes change color as they execute (gray=waiting, blue=running, green=completed, red=failed)
- **Execution Flow**: Follow the path through the orchestration graph
- **Performance Timing**: See execution time for each node
- **Interactive Inspection**: Click nodes to inspect their state and results

#### Streaming Results
Results appear in real-time across three main sources:
- **PubMed**: Academic articles and research papers
- **ClinicalTrials.gov**: Clinical trial information
- **RAG**: Relevant documents from your knowledge base

### 3. Debug Mode

Enable debug mode for detailed control over execution:

#### Setting Breakpoints
1. Enable debug mode in query builder
2. Click on graph nodes to select them
3. Click "Set Breakpoint" in the node inspector
4. Red dots indicate active breakpoints

#### Step-by-Step Execution
- **Step**: Execute one node at a time
- **Resume**: Continue normal execution
- **Inspect State**: View detailed node state information

#### WebSocket Connection
Debug mode uses WebSocket for real-time communication:
- Green "Connected" badge indicates active debug session
- Commands are sent in real-time to the orchestrator
- State changes are reflected immediately in the UI

### 4. Results Analysis

#### Source-Specific Views

**PubMed Results**
- Article cards with abstracts and metadata
- Journal impact indicators
- Quality scores based on recency and relevance
- Direct PMID links
- Export to BibTeX/RIS formats

**Clinical Trials Results**
- Trial status and phase badges
- Enrollment metrics and timelines
- Investment relevance scoring
- Sponsor and location information
- Links to ClinicalTrials.gov

**RAG Results**
- Document chunks with similarity scores
- Source document provenance
- Vector/BM25 score breakdowns
- Semantic highlighting

#### Synthesis View
The final synthesized answer includes:
- **Comprehensive Answer**: AI-generated response combining all sources
- **Citations**: Numbered references to source materials
- **Quality Metrics**: Completeness, recency, authority scores
- **Checkpoint ID**: For reproducible results

### 5. Performance Monitoring

#### Real-Time Metrics
- **Total Execution Time**: Complete orchestration duration
- **Node Performance**: Individual node timing breakdown
- **Cache Hit Rate**: Percentage of cached vs fresh data
- **API Call Count**: Number of external API requests

#### Historical Comparison
- Compare current session with previous executions
- Performance trend analysis
- Identify bottlenecks and optimization opportunities

### 6. Session Management

#### Session History
- **Search**: Find sessions by query content or name
- **Filter**: By status (completed, running, failed)
- **Details**: View complete session information
- **Comparison**: Compare performance across sessions

#### Session Replay
1. Select a session from history
2. Click "View Details" to see full results
3. Use "Compare" to analyze differences with other sessions

## Advanced Features

### Accessibility Support

The interface includes comprehensive accessibility features:
- **Keyboard Navigation**: Full keyboard support for all functions
- **Screen Reader**: ARIA labels and live regions for status updates
- **High Contrast**: Toggle high contrast mode for better visibility
- **Font Size**: Adjustable font sizes (small/medium/large)
- **Reduced Motion**: Respects user's motion preferences

### Responsive Design

The interface adapts to different screen sizes:
- **Desktop**: Full feature set with side-by-side panels
- **Tablet**: Stacked layout with collapsible sections
- **Mobile**: Touch-friendly interface with simplified navigation

### Performance Optimization

- **Efficient Rendering**: Virtual scrolling for large result sets
- **Smart Caching**: Intelligent caching of API responses
- **Bundle Splitting**: Optimized loading of JavaScript bundles
- **Memory Management**: Automatic cleanup of unused resources

## Troubleshooting

### Connection Issues
**Symptom**: "Connection failed" or "Disconnected" status
**Solution**:
1. Check that Bio-MCP server is running
2. Verify orchestrator endpoints are accessible
3. Check network connectivity
4. Use browser developer tools to check for CORS issues

### Streaming Problems
**Symptom**: Results not updating in real-time
**Solution**:
1. Check SSE connection status in network tab
2. Verify firewall allows EventSource connections
3. Try refreshing the page
4. Check server logs for streaming errors

### Debug Mode Issues
**Symptom**: Breakpoints not working or WebSocket errors
**Solution**:
1. Ensure debug mode is enabled in both UI and server
2. Check WebSocket connection in browser developer tools
3. Verify no proxy is blocking WebSocket traffic
4. Try restarting the debug session

### Performance Issues
**Symptom**: Slow loading or unresponsive interface
**Solution**:
1. Check browser memory usage
2. Close unused browser tabs
3. Clear browser cache
4. Monitor performance metrics in the dashboard

## Best Practices

### Query Construction
- Use specific biomedical terms for better results
- Include relevant filters (dates, phases, status)
- Name sessions descriptively for easy identification
- Use debug mode for complex queries

### Performance Optimization
- Enable caching when possible
- Use appropriate time budgets
- Monitor resource usage in dashboard
- Compare performance across sessions

### Debugging
- Set strategic breakpoints at key decision points
- Inspect node state when execution pauses
- Use step-by-step execution for complex flows
- Save debug sessions for later analysis

## API Reference

For developers integrating with the orchestrator API, see:
- [API Specification](../specs/API_SPEC.md)
- [Component Documentation](../specs/COMPONENTS.md)
- [Data Flow Architecture](../specs/DATA_FLOW.md)

## Support

For additional help:
- Check the implementation documentation
- Review the milestone specifications
- File issues for bugs or feature requests
- Contact the development team for technical support
```

### 5. Production Build and Deployment

**File**: `Dockerfile`
```dockerfile
# Multi-stage build for production optimization
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./
COPY vite.config.ts ./
COPY tailwind.config.js ./
COPY postcss.config.js ./

# Install dependencies
RUN npm ci --only=production && npm cache clean --force

# Copy source code
COPY src/ ./src/
COPY public/ ./public/
COPY index.html ./

# Build application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
```

**File**: `nginx.conf`
```nginx
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    server {
        listen 80;
        server_name _;
        root /usr/share/nginx/html;
        index index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # Proxy API requests to backend
        location /orchestrator/v1/ {
            proxy_pass http://bio-mcp-server:8001;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
        }

        # WebSocket proxy for debug connections
        location /orchestrator/ws/ {
            proxy_pass http://bio-mcp-server:8001;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "Upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # SPA routing - serve index.html for all routes
        location / {
            try_files $uri $uri/ /index.html;
        }

        # Health check endpoint
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
    }
}
```

**File**: `docker-compose.yml`
```yaml
version: '3.8'

services:
  orchestrator-ui:
    build: .
    container_name: bio-mcp-orchestrator-ui
    ports:
      - "3000:80"
    environment:
      - NODE_ENV=production
    depends_on:
      - bio-mcp-server
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  bio-mcp-server:
    image: bio-mcp:latest
    container_name: bio-mcp-server
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/biomcp
      - WEAVIATE_URL=http://weaviate:8080
    depends_on:
      - db
      - weaviate
    restart: unless-stopped

  db:
    image: postgres:15
    container_name: bio-mcp-db
    environment:
      - POSTGRES_DB=biomcp
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  weaviate:
    image: semitechnologies/weaviate:latest
    container_name: bio-mcp-weaviate
    environment:
      - QUERY_DEFAULTS_LIMIT=25
      - AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true
      - PERSISTENCE_DATA_PATH=/var/lib/weaviate
    volumes:
      - weaviate_data:/var/lib/weaviate
    restart: unless-stopped

volumes:
  postgres_data:
  weaviate_data:
```

## Testing and Quality Assurance

### 1. Automated Test Suite

**File**: `scripts/test-all.sh`
```bash
#!/bin/bash
set -e

echo "🧪 Running complete test suite..."

# Unit tests
echo "📋 Running unit tests..."
npm run test:unit

# Integration tests  
echo "🔗 Running integration tests..."
npm run test:integration

# E2E tests
echo "🎭 Running E2E tests..."
npm run test:e2e

# Accessibility tests
echo "♿ Running accessibility tests..."
npm run test:a11y

# Performance tests
echo "⚡ Running performance tests..."
npm run test:perf

# Bundle analysis
echo "📦 Analyzing bundle size..."
npm run analyze

# Type checking
echo "🔍 Running type checks..."
npm run type-check

# Linting
echo "🧹 Running linter..."
npm run lint

# Security audit
echo "🔒 Running security audit..."
npm audit --audit-level moderate

echo "✅ All tests passed!"
```

### 2. Performance Budgets

**File**: `.github/workflows/performance-budget.yml`
```yaml
name: Performance Budget

on: [push, pull_request]

jobs:
  lighthouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      
      - name: Install dependencies
        run: npm ci
      
      - name: Build application
        run: npm run build
      
      - name: Run Lighthouse CI
        run: |
          npm install -g @lhci/cli
          lhci autorun
        env:
          LHCI_GITHUB_APP_TOKEN: ${{ secrets.LHCI_GITHUB_APP_TOKEN }}

      - name: Check bundle size
        run: |
          npm run analyze
          # Fail if bundle size exceeds limits
          node scripts/check-bundle-size.js
```

## Acceptance Criteria
- [ ] Complete E2E test suite covering all user workflows
- [ ] Performance optimizations with bundle size < 1MB gzipped
- [ ] Full accessibility compliance (WCAG 2.1 AA)
- [ ] Comprehensive error handling and user feedback
- [ ] Production-ready Docker container with optimized nginx config
- [ ] Complete user documentation and API reference
- [ ] Automated deployment pipeline with health checks
- [ ] Performance monitoring and metrics collection
- [ ] Security hardening and vulnerability scanning
- [ ] Cross-browser compatibility testing (Chrome, Firefox, Safari, Edge)

## Files Created/Modified
- Comprehensive E2E test suite with Playwright
- Performance optimization utilities and monitoring
- Accessibility provider and WCAG compliance features
- Complete user guide and API documentation
- Production Dockerfile and nginx configuration
- Docker Compose for full stack deployment
- Automated testing and deployment scripts
- Bundle analysis and performance budgets

## Dependencies Required
```json
{
  "devDependencies": {
    "@playwright/test": "^1.36.0",
    "rollup-plugin-visualizer": "^5.9.2",
    "terser": "^5.19.0",
    "@lhci/cli": "^0.12.0",
    "pa11y": "^6.2.3"
  }
}
```

## Final Deliverable
A production-ready Bio-MCP Orchestrator UI that provides:
- **Complete end-to-end visibility** into orchestration execution
- **Real-time streaming** of results from all data sources  
- **Advanced debugging capabilities** with breakpoints and step-through execution
- **Comprehensive performance monitoring** and historical analysis
- **Full accessibility compliance** for all users
- **Production-grade deployment** with monitoring and health checks
- **Extensive documentation** for users and developers

The application successfully enables thorough testing, debugging, and optimization of the entire Bio-MCP orchestrator pipeline while providing an excellent user experience across all devices and accessibility needs.
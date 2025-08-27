# Bio-MCP Orchestrator UI

A comprehensive web-based testing interface for the Bio-MCP LangGraph orchestrator, providing end-to-end visibility from user queries through orchestration to data source results.

## Overview

The Orchestrator UI enables thorough testing, debugging, and optimization of the Bio-MCP service by providing:

- **Real-time orchestration visualization** - Watch LangGraph execution with interactive node inspection
- **Streaming result display** - Progressive loading from PubMed, ClinicalTrials.gov, and RAG sources  
- **Advanced query builder** - Smart entity extraction and filtering capabilities
- **Debug mode** - Step-through execution with breakpoints and state inspection
- **Performance monitoring** - Track timing, caching, and resource usage
- **Session management** - Replay and compare orchestration runs

## Architecture

### Frontend Stack
- **React 18+** with TypeScript for type-safe component development
- **react-flow** for interactive LangGraph visualization 
- **TanStack Query** for efficient data fetching and caching
- **Tailwind CSS** for responsive styling
- **Vite** for fast development and optimized builds
- **EventSource/WebSocket** for real-time streaming

### Backend Integration
- **FastAPI** endpoints for orchestrator execution
- **Server-Sent Events (SSE)** for streaming updates
- **WebSocket** for bi-directional debug communication
- **Session storage** for history and replay capabilities
- **Graph serialization** for visualization data

## Key Features

### 1. Interactive Query Builder
```typescript
interface QueryInterface {
  naturalLanguageQuery: string;
  extractedEntities: {
    topic?: string;
    indication?: string; 
    company?: string;
    trial_nct?: string;
  };
  filters: {
    dateRange?: [Date, Date];
    phase?: string[];
    status?: string[];
    journals?: string[];
  };
  advancedOptions: {
    timeBudgetMs: number;
    fetchPolicy: 'cache_first' | 'network_only' | 'cache_then_network';
    maxParallelCalls: number;
    enablePartialResults: boolean;
  };
}
```

### 2. LangGraph Visualization
- Interactive flow diagram showing node execution
- Real-time highlighting of active nodes
- Click-to-inspect node state and results
- Parallel execution branch visualization
- Routing decision display
- Performance timing overlays

### 3. Streaming Results Panel
```typescript
interface StreamingResults {
  sessionId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  currentNode: string;
  nodeResults: Map<string, NodeResult>;
  progressPercentage: number;
  elapsedTimeMs: number;
  
  pubmedResults: StreamingSource;
  clinicalTrialsResults: StreamingSource;
  ragResults: StreamingSource;
  
  synthesizedAnswer?: {
    content: string;
    citations: Citation[];
    qualityScore: QualityMetrics;
    checkpointId: string;
  };
}
```

### 4. Source-Specific Views

**PubMed Tab:**
- Article cards with abstracts and metadata
- Quality indicators (journal impact, recency scores)
- Direct PMID links and export functionality
- Search term highlighting

**ClinicalTrials Tab:**
- Trial status and phase badges
- Enrollment metrics and timelines
- Investment relevance scoring
- Sponsor and location information

**RAG Tab:**
- Semantic similarity scores
- Source document chunks with highlighting
- Vector/BM25 score breakdowns
- Document provenance links

### 5. Debug Mode
- Step-by-step execution control
- Breakpoint setting on graph nodes
- Complete state inspection at each step
- Manual node re-execution
- Performance profiling dashboard
- Token usage and cost tracking

## Project Structure

```
orchestrator-ui/
├── README.md                     # This file
├── IMPLEMENTATION_PLAN.md        # Development roadmap
├── milestones/
│   ├── M1_API_INTEGRATION.md    # Backend orchestrator API
│   ├── M2_CORE_UI.md            # React application core
│   ├── M3_STREAMING.md          # Real-time data flow
│   ├── M4_VISUALIZATION.md      # Graph visualization & debug
│   └── M5_POLISH.md             # Testing & deployment
└── specs/
    ├── API_SPEC.md              # REST API specifications
    ├── COMPONENTS.md            # React component design
    └── DATA_FLOW.md             # State management architecture
```

## Getting Started

### Prerequisites
- Node.js 18+ and npm/yarn
- Bio-MCP server running with orchestrator enabled
- Access to PubMed, ClinicalTrials.gov APIs
- Weaviate instance for RAG functionality

### Development Setup
```bash
# Navigate to project directory
cd orchestrator-ui

# Install dependencies
npm install

# Start development server
npm run dev

# Backend: Enable orchestrator endpoints
cd ../src/bio_mcp/http
uvicorn orchestrator_app:app --reload --port 8001
```

### Environment Configuration
```bash
# Required environment variables
VITE_API_BASE_URL=http://localhost:8001
VITE_WS_URL=ws://localhost:8001/ws
VITE_ENABLE_DEBUG=true

# Optional: Analytics and monitoring
VITE_SENTRY_DSN=your-sentry-dsn
VITE_GOOGLE_ANALYTICS_ID=your-ga-id
```

## Usage Examples

### Basic Query Flow
1. Enter biomedical query: "Latest GLP-1 receptor agonist trials for diabetes"
2. Watch entity extraction identify: topic="GLP-1", indication="diabetes" 
3. Apply filters: phase=["PHASE2", "PHASE3"], dateRange=[2023, 2024]
4. Execute orchestration and view real-time graph execution
5. Inspect streaming results from all sources
6. Review synthesized answer with citations and quality scores

### Debug Workflow
1. Enable debug mode in query builder
2. Set breakpoints on specific nodes (e.g., "enhanced_pubmed", "synthesis")
3. Execute query and pause at breakpoints
4. Inspect node state, inputs, outputs, and performance metrics
5. Manually re-execute nodes with modified parameters
6. Compare results across different execution paths

### Performance Analysis
1. Run identical queries with different configurations
2. Compare execution times, cache hit rates, and resource usage
3. Analyze parallel vs sequential execution performance
4. Profile memory usage and API call efficiency
5. Export performance reports for optimization

## Testing Strategy

### Unit Testing
- React component testing with Jest and React Testing Library
- API integration testing with MSW (Mock Service Worker)
- State management testing with custom hooks

### Integration Testing
- End-to-end orchestration flows with Playwright
- WebSocket/SSE streaming validation
- Cross-browser compatibility testing

### Performance Testing
- Large dataset handling (1000+ results)
- Concurrent user simulation
- Memory leak detection
- Network condition simulation

## Deployment

### Production Build
```bash
npm run build
npm run preview  # Test production build locally
```

### Docker Deployment
```bash
# Build container
docker build -t bio-mcp-orchestrator-ui .

# Run with Bio-MCP backend
docker-compose up orchestrator-ui
```

### Static Hosting
The built application can be deployed to:
- Vercel/Netlify for static hosting
- AWS S3 + CloudFront
- GitHub Pages
- Internal corporate hosting

## Contributing

### Development Workflow
1. Review milestone documentation in `/milestones/`
2. Check component specifications in `/specs/`
3. Follow TypeScript and React best practices
4. Ensure test coverage for new features
5. Update documentation for API changes

### Code Standards
- TypeScript strict mode enabled
- ESLint + Prettier for code formatting
- Conventional commit messages
- Component-based architecture
- Accessibility (WCAG 2.1) compliance

## Support

For questions and support:
- Review the implementation plan and milestone documentation
- Check the API specifications for backend integration
- Refer to component specs for React development
- File issues for bugs or feature requests

## License

This project is part of the Bio-MCP ecosystem and follows the same licensing terms.
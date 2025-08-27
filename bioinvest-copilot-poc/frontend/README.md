# BioInvest AI Copilot - Frontend POC

React frontend for the BioInvest AI Copilot proof-of-concept application.

## Features

- **Natural Language Queries**: Submit biotech research questions in plain English
- **Real-time Streaming**: Watch research progress with live updates via Server-Sent Events
- **Multi-source Data**: Integrate PubMed, ClinicalTrials.gov, and internal RAG insights
- **AI Synthesis**: Get intelligent analysis, competitive insights, and strategic recommendations
- **Interactive Results**: Explore detailed research findings with expandable content sections

## Technology Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **TailwindCSS** for utility-first styling
- **TanStack Query** for server state management
- **Lucide React** for icons
- **date-fns** for date formatting

## Development

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Type checking
npm run type-check

# Linting
npm run lint
```

### Backend Integration

The frontend is configured to proxy API requests to the FastAPI backend running on `http://localhost:8001`. Make sure the backend server is running before starting the frontend development server.

### Environment Configuration

The Vite development server is configured to:
- Run on port 5173
- Proxy `/api/*` requests to the backend at `localhost:8001`
- Enable hot module replacement for fast development

## API Integration

The frontend communicates with the backend through:

1. **REST API**: Submit queries and get status updates
2. **Server-Sent Events (SSE)**: Real-time streaming of research progress
3. **Query Management**: Track active queries and results

## Component Architecture

- `ResearchWorkspace`: Main application workspace
- `QueryBuilder`: Natural language query interface with advanced options
- `StreamingResults`: Real-time progress display with event stream
- `ResultsDisplay`: Comprehensive results viewer with tabbed interface
- Custom hooks for streaming results and API integration

## Key Features

### Query Builder
- Natural language input with example queries
- Configurable data sources (PubMed, Clinical Trials, RAG)
- Advanced options for analysis priority and result limits
- Real-time validation and loading states

### Streaming Interface
- Live progress updates via Server-Sent Events
- Source-specific status indicators
- Error handling and connection monitoring
- Processing time tracking

### Results Display
- Tabbed interface for different data sources
- AI synthesis with quality metrics and competitive analysis
- Expandable content sections for detailed exploration
- Citation links and metadata display

## Development Notes

This is a proof-of-concept implementation designed to demonstrate the end-to-end capabilities of the BioInvest AI Copilot platform. It includes simulated data and responses for demonstration purposes.
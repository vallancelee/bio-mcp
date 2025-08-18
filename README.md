# Bio-MCP Server

A production-ready **Model Context Protocol (MCP) server** for biomedical research and applications. Built with enterprise-grade monitoring, error handling, and container orchestration support.

## 🚀 Features

### 🏥 **Biomedical Focus**
- Designed for biomedical research workflows
- Integration with scientific databases and APIs
- Extensible tool architecture for domain-specific operations

### 🛡️ **Production Ready**
- **Health Monitoring**: JSON health checks with multiple validation layers
- **Graceful Shutdown**: SIGTERM/SIGINT signal handling with proper cleanup
- **Error Boundaries**: Comprehensive error handling with standardized responses
- **Metrics Collection**: Thread-safe performance and usage tracking
- **Input Validation**: Schema-based argument validation with detailed errors

### 📊 **Observability**
- **Structured Logging**: Auto-configuring JSON logs for container environments
- **Health Endpoints**: Container orchestration ready with health checks
- **Metrics Tracking**: Real-time tool usage, success rates, and performance data
- **Error Recovery**: Robust error boundaries with detailed error reporting

### 🐳 **Container Native**
- Docker and Kubernetes ready
- Health check integration for orchestration
- Environment-based configuration
- Semantic versioning with build metadata

## 🏁 Quick Start

### Prerequisites
- Python 3.12+
- [UV package manager](https://docs.astral.sh/uv/)
- Docker (optional, for containerized deployment)

### Installation

```bash
# Clone the repository
git clone https://github.com/vallancelee/bio-mcp.git
cd bio-mcp

# Set up development environment
make dev-setup
```

### Running the Server

```bash
# Start the MCP server
make run

# Or run with supporting services
make docker-up && make run
```

### Testing

```bash
# Run complete test suite
make test-all

# Run full build → test → deploy workflow
make workflow

# Test health endpoint
uv run python -m bio_mcp.health
```

## 🔧 Development

### Project Structure

```
bio-mcp/
├── src/bio_mcp/          # Main application code
│   ├── main.py           # MCP server implementation
│   ├── health.py         # Health check system
│   ├── metrics.py        # Metrics collection
│   ├── logging_config.py # Structured logging
│   ├── error_handling.py # Error boundaries
│   └── config.py         # Configuration management
├── tests/                # Comprehensive test suite
│   ├── unit/            # Unit tests (49 tests)
│   └── integration/     # Integration tests (9 tests)
├── docker-compose.yml   # Development services
├── Dockerfile           # Container definition
└── Makefile            # Development commands
```

### Available Tools

The server currently provides:

- **`ping`**: Health check tool with server information
- *More biomedical tools coming in future phases*

### Configuration

Configure via environment variables:

```bash
# Server settings
export BIO_MCP_LOG_LEVEL=INFO
export BIO_MCP_JSON_LOGS=true
export BIO_MCP_SERVER_NAME=bio-mcp

# Database connections (optional)
export BIO_MCP_DATABASE_URL=postgresql://localhost:5433/bio_mcp
export BIO_MCP_WEAVIATE_URL=http://localhost:8080

# API keys (for future biomedical integrations)
export BIO_MCP_PUBMED_API_KEY=your_key_here
export BIO_MCP_OPENAI_API_KEY=your_key_here
```

## 🐳 Docker Deployment

### Build and Run

```bash
# Build Docker image
make docker-build

# Run container
make docker-run

# Start with supporting services
make docker-up
```

### Health Checks

The container includes built-in health checks:

```bash
# Check container health
docker exec <container> uv run python -m bio_mcp.health
```

## 📊 Monitoring

### Health Endpoint

```bash
# Get JSON health report
uv run python -m bio_mcp.health
```

Example output:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:45Z",
  "version": "0.1.0",
  "uptime_seconds": 123.45,
  "checks": [
    {"name": "server", "status": "healthy", "message": "MCP server is running"},
    {"name": "config", "status": "healthy", "message": "Configuration is valid"},
    {"name": "metrics", "status": "healthy", "message": "Metrics collection is working"}
  ]
}
```

### Metrics

Access real-time metrics through the health system:

- **Tool Usage**: Call counts, success rates, timing
- **Performance**: Response times, error rates
- **System**: Uptime, memory usage

### Logging

Structured JSON logging with contextual information:

```json
{
  "@timestamp": "2025-01-15T10:30:45Z",
  "level": "INFO",
  "message": "Processing ping tool request",
  "service": {"name": "bio-mcp", "version": "0.1.0"},
  "tool": "ping",
  "request_message": "test"
}
```

## 🧪 Testing

Comprehensive test suite with 100% passing rate:

- **Unit Tests**: 49 tests covering all components
- **Integration Tests**: 9 tests for signal handling and Docker
- **Health Checks**: Validation of monitoring systems
- **Error Handling**: Boundary testing and recovery

```bash
# Run all tests
make test-all

# Run specific test categories
make test              # Unit tests only
make test-integration  # Integration tests
make test-docker       # Docker-specific tests
```

## 📈 Roadmap

### Phase 1: Foundation ✅
- [x] Basic MCP server with containerization
- [x] Robust monitoring and error handling
- [x] Comprehensive testing framework

### Phase 2: Biomedical Integration (Planned)
- [ ] PubMed/NCBI integration
- [ ] Biomedical database connectors
- [ ] Literature search and analysis tools

### Phase 3: Advanced Features (Planned)
- [ ] Vector database integration
- [ ] AI-powered biomedical analysis
- [ ] Multi-modal data processing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Run tests: `make test-all`
4. Commit changes: `git commit -m 'Add amazing feature'`
5. Push to branch: `git push origin feature/amazing-feature`
6. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/vallancelee/bio-mcp/issues)
- **Documentation**: See [contracts.md](contracts.md) for API details
- **Development**: Use `make test-help` for testing guidance

---

**Bio-MCP Server** - Production-ready biomedical MCP server with enterprise monitoring 🧬🚀
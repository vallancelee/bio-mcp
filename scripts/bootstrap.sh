#!/bin/bash
set -e

echo "🚀 Bio-MCP Development Setup"
echo "============================"

# Colors for output
BLUE='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}❌ Python 3.12+ required${NC}"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo -e "${RED}❌ Docker required${NC}"; exit 1; }
command -v uv >/dev/null 2>&1 || { echo -e "${RED}❌ UV required (pip install uv)${NC}"; exit 1; }

echo -e "${GREEN}✓ Prerequisites check passed${NC}"

# Navigate to project root
cd "$(dirname "$0")/.."

# Setup environment
echo -e "${YELLOW}Setting up environment...${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env from template${NC}"
else
    echo -e "${GREEN}✓ .env already exists${NC}"
fi

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
uv sync --dev
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p data logs
echo -e "${GREEN}✓ Directories created${NC}"

# Start services
echo -e "${YELLOW}Starting Docker services...${NC}"
docker-compose up -d postgres weaviate minio

# Wait for services
echo -e "${YELLOW}Waiting for services to be ready...${NC}"
sleep 10

# Check service health
echo -e "${YELLOW}Checking service health...${NC}"
if docker-compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
else
    echo -e "${RED}⚠ PostgreSQL not ready (may need more time)${NC}"
fi

if curl -s http://localhost:8080/v1/.well-known/ready >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Weaviate is ready${NC}"
else
    echo -e "${RED}⚠ Weaviate not ready (may need more time)${NC}"
fi

if curl -s http://localhost:9000/minio/health/live >/dev/null 2>&1; then
    echo -e "${GREEN}✓ MinIO is ready${NC}"
else
    echo -e "${RED}⚠ MinIO not ready (may need more time)${NC}"
fi

# Run migrations
echo -e "${YELLOW}Running database migrations...${NC}"
if uv run alembic upgrade head 2>/dev/null; then
    echo -e "${GREEN}✓ Migrations completed${NC}"
else
    echo -e "${YELLOW}⚠ Migrations skipped (may not be needed)${NC}"
fi

echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${BLUE}Services running:${NC}"
echo -e "  • PostgreSQL: localhost:5432"
echo -e "  • Weaviate: http://localhost:8080"
echo -e "  • MinIO S3: http://localhost:9000"
echo -e "  • MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "  ${GREEN}make quickstart${NC}     # Test the setup"
echo -e "  ${GREEN}make run-http${NC}       # Start the API server" 
echo -e "  ${GREEN}make run-worker${NC}     # Start the worker (separate terminal)"
echo ""
echo -e "${GREEN}Happy coding! 🎉${NC}"
#!/bin/bash
# Test runner script for Bio-MCP

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Running Bio-MCP Tests${NC}"
echo "=================================="

# Function to run tests with proper error handling
run_tests() {
    local test_type="$1"
    local test_args="$2"
    
    echo -e "\n${YELLOW}Running $test_type tests...${NC}"
    
    if uv run pytest $test_args; then
        echo -e "${GREEN}✓ $test_type tests passed${NC}"
        return 0
    else
        echo -e "${RED}✗ $test_type tests failed${NC}"
        return 1
    fi
}

# Run different test suites
FAILED=0

# Unit tests (fast)
if ! run_tests "Unit" "-m unit -v"; then
    FAILED=1
fi

# Integration tests (excluding Docker tests by default)
if ! run_tests "Integration" "-m 'integration and not docker' -v"; then
    FAILED=1
fi

# Docker tests (if Docker is available and requested)
if [ "$INCLUDE_DOCKER" = "true" ]; then
    echo -e "\n${YELLOW}Checking Docker availability...${NC}"
    if command -v docker >/dev/null 2>&1 && docker ps >/dev/null 2>&1; then
        echo -e "${GREEN}Docker is available${NC}"
        if ! run_tests "Docker" "-m docker -v -s"; then
            FAILED=1
        fi
    else
        echo -e "${YELLOW}Docker not available, skipping Docker tests${NC}"
    fi
fi

# Summary
echo -e "\n=================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! 🎉${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed! ❌${NC}"
    exit 1
fi
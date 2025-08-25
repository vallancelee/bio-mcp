# Decision Archive

This directory contains historical planning documents, implementation steps, and decision records that were used during the development of Bio-MCP but are no longer current.

## Contents

### Implementation Step Documents (STEP_*.md)
- **STEP_T0.md** to **STEP_T7.md** - Sequential implementation tasks for HTTP infrastructure
- These documents guided the development of the HTTP API layer on top of the existing MCP server

### RAG Implementation Documents (RAG_*.md)
- **RAG_IMPLEMENTATION_PLAN_V2.md** - Master plan for RAG system implementation  
- **RAG_STEP_1_MODELS.md** to **RAG_STEP_7_TESTING.md** - Detailed implementation steps for each RAG phase
- **RAG_OPTIONAL_WEAVIATE_NEW_SCHEMA.md** - Alternative Weaviate schema considerations

### Test Planning Documents (TEST_*.md)
- **TEST_CLEANUP_PLAN.md** - Plan for organizing and improving test suite
- **TEST_CLEANUP_SUMMARY.md** - Summary of test cleanup activities
- **TEST_PERFORMANCE_OPTIMIZATIONS.md** - Performance testing and optimization plans

### Priority and Onboarding Documents
- **NEXT_PRIORITIES.md** - Historical priority list (completed items)
- **ONBOARDING.md** - Early onboarding document (superseded by ARCHITECTURE.md)
- **ONBOARDING_IMPLEMENTATION_PLAN.md** - Implementation-focused onboarding guide

### Architecture and Refactoring Documents
- **MULTISOURCE_REFACTOR.md** - Plan for shared Document model (implemented)
- **MCP_TESTING.md** - Comprehensive MCP testing strategy (partially implemented)
- **PUBMED_SYNC_IMPLEMENTATION_PLAN.md** - Empty placeholder file

### Test Strategy Documents
- **INCREASE_TEST_COVERAGE.md** - Test coverage improvement strategy

## Current Documentation

For current project information, see:
- **ARCHITECTURE.md** - Comprehensive architecture documentation (replaces onboarding docs)
- **contracts.md** - API contracts and tool specifications  
- **README.md** - Project overview and setup instructions
- **IMPLEMENTATION_PLAN.md** - Current implementation status and roadmap

## Historical Context

These documents represent the evolution of Bio-MCP from a simple MCP server to a comprehensive biomedical research platform with:
- HTTP API infrastructure
- Advanced RAG capabilities with section boosting and quality ranking
- Production-ready testing and monitoring
- Comprehensive documentation and architectural planning

Many of the features planned in these documents have been successfully implemented and are now part of the production system.
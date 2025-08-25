# Environment Variables Configuration

This document describes all environment variables used by Bio-MCP for secure configuration management.

## 🔒 **Security Principles**

- **No hardcoded secrets**: All sensitive data must be externalized
- **Consistent naming**: All Bio-MCP variables use `BIO_MCP_` prefix
- **AWS SSM integration**: Production secrets stored in AWS Parameter Store
- **Environment separation**: Different values per environment (dev/stage/prod)

## 📋 **Complete Environment Variables**

### **Required Secrets (Production)**
```bash
# Database connection (PostgreSQL in production)
BIO_MCP_DATABASE_URL="postgresql://user:password@host:5432/dbname"

# External API keys
BIO_MCP_PUBMED_API_KEY="your-pubmed-api-key"     # Required for PubMed access
BIO_MCP_OPENAI_API_KEY="your-openai-api-key"     # Optional for AI features

# Vector database
BIO_MCP_WEAVIATE_URL="http://weaviate:8080"       # Weaviate endpoint
```

### **Server Configuration**
```bash
# Server identity
BIO_MCP_SERVER_NAME="bio-mcp"                     # Server instance name
BIO_MCP_LOG_LEVEL="INFO"                          # DEBUG|INFO|WARNING|ERROR

# Build information (set by CI/CD)
BIO_MCP_VERSION="1.0.0"                           # Application version
BIO_MCP_BUILD="build-123"                         # Build number
BIO_MCP_COMMIT="abc123def"                        # Git commit hash
```

### **Performance Tuning**
```bash
# Database connection pool
BIO_MCP_DB_POOL_SIZE="5"                          # Connection pool size
BIO_MCP_DB_MAX_OVERFLOW="10"                      # Max overflow connections
BIO_MCP_DB_POOL_TIMEOUT="30.0"                    # Pool timeout (seconds)
BIO_MCP_DB_ECHO="false"                           # SQL logging (true/false)

# PubMed API rate limiting
BIO_MCP_PUBMED_RATE_LIMIT="3"                     # Requests per second (0=disabled)
BIO_MCP_PUBMED_TIMEOUT="30.0"                     # Request timeout (seconds)

# Logging format
BIO_MCP_JSON_LOGS="true"                          # JSON logging for production
```

## 🏗️ **AWS ECS Integration**

### **Current ECS Task Definition**
The Terraform configuration in `bio-mcp-infra/ecs.tf` sets these secrets:

```hcl
secrets = [
  { name = "BIO_MCP_DATABASE_URL", valueFrom = aws_ssm_parameter.db_url.arn },
  { name = "BIO_MCP_PUBMED_API_KEY", valueFrom = aws_ssm_parameter.pubmed_api_key.arn },
  { name = "BIO_MCP_OPENAI_API_KEY", valueFrom = aws_ssm_parameter.openai_api_key.arn }
]
```

### **AWS SSM Parameters**
Secrets are stored in AWS Systems Manager Parameter Store:

```bash
# Database URL (constructed from RDS endpoint)
/bio-mcp/{env}/database-url

# API keys (set manually or via CI/CD)
/bio-mcp/{env}/pubmed-api-key
/bio-mcp/{env}/openai-api-key
```

## 🧪 **Development & Testing**

### **Local Development (.env file)**
Create `.env` file in project root:

```bash
# Local development setup
BIO_MCP_DATABASE_URL="postgresql://biomcp_admin:password@localhost:5432/bio_mcp"
BIO_MCP_WEAVIATE_URL="http://localhost:8080"
BIO_MCP_PUBMED_API_KEY="your-dev-api-key"
BIO_MCP_OPENAI_API_KEY="your-dev-openai-key"
BIO_MCP_LOG_LEVEL="DEBUG"
BIO_MCP_JSON_LOGS="false"
```

### **Docker Compose**
For local Docker development:

```yaml
services:
  bio-mcp:
    environment:
      - BIO_MCP_DATABASE_URL=postgresql://biomcp_admin:password@postgres:5432/bio_mcp
      - BIO_MCP_WEAVIATE_URL=http://weaviate:8080
      - BIO_MCP_LOG_LEVEL=INFO
      - BIO_MCP_JSON_LOGS=true
```

### **Testing**
Test environment uses in-memory databases and mock APIs:

```bash
BIO_MCP_DATABASE_URL="sqlite:///:memory:"
BIO_MCP_WEAVIATE_URL="http://localhost:8080"
BIO_MCP_LOG_LEVEL="DEBUG"
# API keys are mocked in tests
```

## 🔧 **Configuration Validation**

The application validates configuration on startup:

- **Required fields**: Database URL is required in production
- **Format validation**: URLs must be valid, log levels must be valid
- **Security checks**: No secrets logged, environment variable names validated
- **Fallback values**: Sensible defaults for non-sensitive configuration

## 🚨 **Security Best Practices**

### **✅ DO**
- Use AWS SSM Parameter Store for production secrets
- Use different secrets per environment
- Rotate API keys regularly
- Monitor secret access via CloudTrail
- Use least-privilege IAM roles

### **❌ DON'T**
- Hardcode secrets in source code
- Commit secrets to git
- Use production secrets in development
- Log sensitive environment variables
- Share secrets between environments

## 📊 **Production Monitoring**

Monitor these environment-related metrics:

- **Configuration errors**: Failed to load required environment variables
- **API key usage**: PubMed API rate limiting and quota usage
- **Database connections**: Pool utilization and connection errors
- **Secret rotation**: Automated monitoring of secret age

## 🔄 **Migration from Legacy Variables**

If migrating from legacy environment variables:

| Legacy Variable | New Variable | Status |
|----------------|--------------|---------|
| `DATABASE_URL` | `BIO_MCP_DATABASE_URL` | ✅ Updated |
| `PUBMED_API_KEY` | `BIO_MCP_PUBMED_API_KEY` | ✅ Updated |
| `OPENAI_API_KEY` | `BIO_MCP_OPENAI_API_KEY` | ✅ Updated |
| `WEAVIATE_URL` | `BIO_MCP_WEAVIATE_URL` | ✅ Updated |

All legacy variables are no longer supported to ensure consistent naming.
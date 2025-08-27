# BioInvest AI Copilot - Infrastructure Architecture

## Overview

The BioInvest AI Copilot infrastructure is designed as a cloud-native, containerized platform that supports high availability, auto-scaling, and global deployment. The architecture leverages modern DevOps practices with Infrastructure as Code (IaC), continuous deployment, and comprehensive observability to deliver a reliable and performant platform for biotech investment research.

## Infrastructure Principles

### Core Principles
- **Cloud-Native Architecture**: Microservices deployed in containers with orchestration
- **Multi-Cloud Strategy**: Primary AWS with Azure backup for disaster recovery
- **Infrastructure as Code**: All infrastructure defined and managed through code
- **Zero-Downtime Deployment**: Blue-green deployments with automated rollback
- **Security by Design**: Defense in depth with encryption and zero-trust networking
- **Observability First**: Comprehensive monitoring, logging, and alerting

### Quality Standards
- **Availability**: 99.9% uptime SLA with <100ms P95 response time
- **Scalability**: Auto-scale to handle 10x traffic spikes
- **Recovery**: <1 hour RTO, <5 minutes RPO for critical services
- **Security**: SOC2 Type II compliance with zero-trust architecture
- **Cost Optimization**: Automated resource optimization and cost monitoring

## High-Level Infrastructure Architecture

```mermaid
graph TB
    subgraph "Global Infrastructure"
        CDN[CloudFlare CDN]
        DNS[Route 53 DNS]
        WAF[Web Application Firewall]
    end
    
    subgraph "Primary Region (US-East-1)"
        subgraph "Production VPC"
            ALB[Application Load Balancer]
            
            subgraph "Public Subnets"
                NAT[NAT Gateway]
            end
            
            subgraph "Private Subnets - App Tier"
                EKS[EKS Cluster]
                subgraph "EKS Nodes"
                    API_PODS[API Services]
                    ML_PODS[ML Services]
                    WORKER_PODS[Background Workers]
                end
            end
            
            subgraph "Private Subnets - Data Tier"
                RDS[RDS PostgreSQL]
                ELASTICACHE[ElastiCache Redis]
                OPENSEARCH[OpenSearch]
            end
        end
        
        subgraph "Shared Services"
            ECR[Container Registry]
            S3[S3 Data Lake]
            SECRETS[Secrets Manager]
            KMS[Key Management]
        end
    end
    
    subgraph "DR Region (US-West-2)"
        DR_VPC[DR VPC]
        DR_RDS[Read Replica]
        DR_S3[S3 Cross-Region Replication]
    end
    
    subgraph "Monitoring & Observability"
        DATADOG[DataDog]
        PAGER[PagerDuty]
        GRAFANA[Grafana]
    end
    
    CDN --> WAF
    DNS --> CDN
    WAF --> ALB
    ALB --> EKS
    
    EKS --> RDS
    EKS --> ELASTICACHE
    EKS --> OPENSEARCH
    EKS --> S3
    
    RDS --> DR_RDS
    S3 --> DR_S3
    
    EKS --> DATADOG
    EKS --> PAGER
```

## Container Orchestration (Kubernetes)

### EKS Cluster Configuration

#### Cluster Setup
```yaml
# terraform/eks-cluster.tf
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "bioinvest-prod"
  cluster_version = "1.28"

  vpc_id                         = module.vpc.vpc_id
  subnet_ids                     = module.vpc.private_subnets
  cluster_endpoint_public_access = true
  
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
  }

  eks_managed_node_groups = {
    general = {
      desired_size = 3
      max_size     = 10
      min_size     = 3

      instance_types = ["m5.xlarge"]
      capacity_type  = "ON_DEMAND"

      k8s_labels = {
        Environment = "production"
        NodeType    = "general"
      }

      tags = {
        ExtraTag = "general-nodes"
      }
    }

    ml_workloads = {
      desired_size = 2
      max_size     = 8
      min_size     = 2

      instance_types = ["c5.2xlarge", "c5.4xlarge"]
      capacity_type  = "SPOT"

      k8s_labels = {
        Environment = "production"
        NodeType    = "ml-workload"
      }

      taints = {
        dedicated = {
          key    = "ml-workload"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      }
    }

    gpu_nodes = {
      desired_size = 1
      max_size     = 4
      min_size     = 0

      instance_types = ["p3.2xlarge", "g4dn.xlarge"]
      capacity_type  = "SPOT"

      k8s_labels = {
        Environment = "production"
        NodeType    = "gpu"
      }

      taints = {
        nvidia = {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      }
    }
  }

  tags = {
    Environment = "production"
    Terraform   = "true"
  }
}
```

### Namespace Organization
```yaml
# kubernetes/namespaces.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: bioinvest-api
  labels:
    name: bioinvest-api
    tier: application
---
apiVersion: v1
kind: Namespace
metadata:
  name: bioinvest-ml
  labels:
    name: bioinvest-ml
    tier: machine-learning
---
apiVersion: v1
kind: Namespace
metadata:
  name: bioinvest-workers
  labels:
    name: bioinvest-workers
    tier: background-processing
---
apiVersion: v1
kind: Namespace
metadata:
  name: monitoring
  labels:
    name: monitoring
    tier: observability
```

### Application Deployment
```yaml
# kubernetes/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: research-api
  namespace: bioinvest-api
  labels:
    app: research-api
    version: v1.0.0
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  selector:
    matchLabels:
      app: research-api
  template:
    metadata:
      labels:
        app: research-api
        version: v1.0.0
    spec:
      serviceAccountName: research-api-sa
      containers:
      - name: research-api
        image: bioinvest/research-api:v1.0.0
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secrets
              key: connection-string
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secrets
              key: connection-string
        - name: ML_SERVICE_URL
          value: "http://ml-service.bioinvest-ml.svc.cluster.local:8080"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        securityContext:
          allowPrivilegeEscalation: false
          runAsNonRoot: true
          runAsUser: 1000
          capabilities:
            drop:
            - ALL
---
apiVersion: v1
kind: Service
metadata:
  name: research-api-service
  namespace: bioinvest-api
spec:
  selector:
    app: research-api
  ports:
  - name: http
    port: 80
    targetPort: 8000
    protocol: TCP
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: research-api-ingress
  namespace: bioinvest-api
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/healthcheck-path: /health
    alb.ingress.kubernetes.io/ssl-redirect: '443'
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.bioinvest.ai
    secretName: api-tls-secret
  rules:
  - host: api.bioinvest.ai
    http:
      paths:
      - path: /v1/research
        pathType: Prefix
        backend:
          service:
            name: research-api-service
            port:
              number: 80
```

### Horizontal Pod Autoscaler
```yaml
# kubernetes/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: research-api-hpa
  namespace: bioinvest-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: research-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
```

## Data Storage Infrastructure

### PostgreSQL RDS Configuration
```hcl
# terraform/rds.tf
resource "aws_db_instance" "primary" {
  identifier = "bioinvest-prod-primary"

  # Engine Configuration
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.r6g.2xlarge"

  # Storage Configuration
  allocated_storage     = 1000
  max_allocated_storage = 10000
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id           = aws_kms_key.database.arn

  # Database Configuration
  db_name  = "bioinvest"
  username = "bioinvest_admin"
  password = random_password.master_password.result
  port     = 5432

  # Network Configuration
  vpc_security_group_ids = [aws_security_group.database.id]
  db_subnet_group_name   = aws_db_subnet_group.database.name
  publicly_accessible    = false

  # Backup Configuration
  backup_retention_period = 30
  backup_window          = "03:00-04:00"
  maintenance_window     = "Sun:04:00-Sun:05:00"
  delete_automated_backups = false

  # Monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.enhanced_monitoring.arn
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  # Performance Insights
  performance_insights_enabled = true
  performance_insights_retention_period = 7

  # High Availability
  multi_az = true
  
  tags = {
    Name        = "bioinvest-prod-primary"
    Environment = "production"
    Terraform   = "true"
  }
}

# Read Replicas for Load Distribution
resource "aws_db_instance" "read_replica" {
  count = 2
  
  identifier = "bioinvest-prod-read-${count.index + 1}"
  
  # Replica Configuration
  replicate_source_db = aws_db_instance.primary.identifier
  instance_class      = "db.r6g.xlarge"
  
  # Storage (inherited from primary)
  storage_encrypted = true
  
  # Network Configuration
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false
  
  # Monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.enhanced_monitoring.arn
  
  # Performance Insights
  performance_insights_enabled = true
  
  tags = {
    Name        = "bioinvest-prod-read-${count.index + 1}"
    Environment = "production"
    Terraform   = "true"
    Role        = "read-replica"
  }
}

# Cross-Region DR Replica
resource "aws_db_instance" "dr_replica" {
  provider = aws.us_west_2
  
  identifier = "bioinvest-prod-dr"
  
  # Replica Configuration
  replicate_source_db = aws_db_instance.primary.arn
  instance_class      = "db.r6g.xlarge"
  
  # Storage
  storage_encrypted = true
  
  # Network Configuration
  vpc_security_group_ids = [aws_security_group.database_dr.id]
  publicly_accessible    = false
  
  # Backup
  backup_retention_period = 7
  
  tags = {
    Name        = "bioinvest-prod-dr"
    Environment = "production"
    Terraform   = "true"
    Role        = "disaster-recovery"
  }
}
```

### Redis ElastiCache Cluster
```hcl
# terraform/elasticache.tf
resource "aws_elasticache_subnet_group" "redis" {
  name       = "bioinvest-redis-subnet-group"
  subnet_ids = data.aws_subnets.private.ids

  tags = {
    Name = "bioinvest-redis-subnet-group"
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "bioinvest-prod-redis"
  description                = "BioInvest Production Redis Cluster"
  
  # Engine Configuration
  engine               = "redis"
  engine_version       = "7.0"
  node_type           = "cache.r6g.xlarge"
  port                = 6379
  parameter_group_name = "default.redis7"
  
  # Cluster Configuration
  num_cache_clusters = 3
  
  # Network Configuration
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]
  
  # Security
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                = random_password.redis_auth.result
  
  # Backup
  snapshot_retention_limit = 7
  snapshot_window         = "03:00-05:00"
  maintenance_window      = "sun:05:00-sun:07:00"
  
  # High Availability
  automatic_failover_enabled = true
  multi_az_enabled          = true
  
  # Monitoring
  notification_topic_arn = aws_sns_topic.alerts.arn
  
  tags = {
    Name        = "bioinvest-prod-redis"
    Environment = "production"
    Terraform   = "true"
  }
}
```

### S3 Data Lake
```hcl
# terraform/s3.tf
resource "aws_s3_bucket" "data_lake" {
  bucket = "bioinvest-prod-data-lake"
  
  tags = {
    Name        = "bioinvest-prod-data-lake"
    Environment = "production"
    Terraform   = "true"
  }
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_encryption" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.s3.arn
        sse_algorithm     = "aws:kms"
      }
      bucket_key_enabled = true
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    id     = "raw_data_lifecycle"
    status = "Enabled"

    filter {
      prefix = "raw/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = 2555  # 7 years
    }
  }

  rule {
    id     = "processed_data_lifecycle"
    status = "Enabled"

    filter {
      prefix = "processed/"
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 365
      storage_class = "GLACIER"
    }
  }

  rule {
    id     = "ml_models_lifecycle"
    status = "Enabled"

    filter {
      prefix = "models/"
    }

    transition {
      days          = 365
      storage_class = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# Cross-region replication for disaster recovery
resource "aws_s3_bucket_replication_configuration" "data_lake_dr" {
  role   = aws_iam_role.replication.arn
  bucket = aws_s3_bucket.data_lake.id

  rule {
    id     = "disaster_recovery"
    status = "Enabled"

    filter {
      prefix = "critical/"
    }

    destination {
      bucket        = aws_s3_bucket.data_lake_dr.arn
      storage_class = "STANDARD_IA"
      
      encryption_configuration {
        replica_kms_key_id = aws_kms_key.s3_dr.arn
      }
    }
  }
}
```

## CI/CD Pipeline

### GitHub Actions Workflow
```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  AWS_REGION: us-east-1
  EKS_CLUSTER_NAME: bioinvest-prod
  ECR_REPOSITORY: bioinvest

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install poetry
        poetry install

    - name: Run linting
      run: |
        poetry run ruff check .
        poetry run black --check .
        poetry run mypy .

    - name: Run tests
      run: |
        poetry run pytest --cov=src --cov-report=xml
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  security-scan:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Run Snyk security scan
      uses: snyk/actions/python@master
      env:
        SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
      with:
        args: --severity-threshold=high

    - name: Run container security scan
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: 'bioinvest/api:${{ github.sha }}'
        format: 'sarif'
        output: 'trivy-results.sarif'

  build-and-push:
    needs: [test, security-scan]
    runs-on: ubuntu-latest
    
    outputs:
      image-tag: ${{ steps.build.outputs.image-tag }}
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}

    - name: Login to ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v1

    - name: Build and push Docker image
      id: build
      env:
        ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
        IMAGE_TAG: ${{ github.sha }}
      run: |
        docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
        docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
        echo "image-tag=$IMAGE_TAG" >> $GITHUB_OUTPUT

  deploy-staging:
    if: github.ref == 'refs/heads/main'
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: staging
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}

    - name: Update kubeconfig
      run: |
        aws eks update-kubeconfig --region ${{ env.AWS_REGION }} --name bioinvest-staging

    - name: Deploy to staging
      run: |
        helm upgrade --install bioinvest-api ./helm/bioinvest-api \
          --namespace bioinvest-api \
          --set image.tag=${{ needs.build-and-push.outputs.image-tag }} \
          --set environment=staging \
          --values ./helm/values-staging.yaml

    - name: Run smoke tests
      run: |
        kubectl wait --for=condition=ready pod -l app=bioinvest-api -n bioinvest-api --timeout=300s
        ./scripts/smoke-tests.sh staging

  deploy-production:
    if: github.ref == 'refs/heads/main'
    needs: [build-and-push, deploy-staging]
    runs-on: ubuntu-latest
    environment: production
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}

    - name: Update kubeconfig
      run: |
        aws eks update-kubeconfig --region ${{ env.AWS_REGION }} --name ${{ env.EKS_CLUSTER_NAME }}

    - name: Blue-Green Deployment
      run: |
        # Deploy to green environment
        helm upgrade --install bioinvest-api-green ./helm/bioinvest-api \
          --namespace bioinvest-api \
          --set image.tag=${{ needs.build-and-push.outputs.image-tag }} \
          --set environment=production \
          --set deployment.slot=green \
          --values ./helm/values-production.yaml
        
        # Wait for green deployment to be ready
        kubectl wait --for=condition=ready pod -l app=bioinvest-api,slot=green -n bioinvest-api --timeout=600s
        
        # Run health checks
        ./scripts/health-check.sh green
        
        # Switch traffic to green
        kubectl patch service bioinvest-api-service -n bioinvest-api -p '{"spec":{"selector":{"slot":"green"}}}'
        
        # Wait and verify
        sleep 60
        ./scripts/health-check.sh production
        
        # Clean up blue deployment
        helm uninstall bioinvest-api-blue -n bioinvest-api || true

  notify:
    if: always()
    needs: [deploy-production]
    runs-on: ubuntu-latest
    
    steps:
    - name: Notify Slack
      uses: 8398a7/action-slack@v3
      with:
        status: ${{ job.status }}
        channel: '#deployments'
        webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Helm Chart Structure
```yaml
# helm/bioinvest-api/Chart.yaml
apiVersion: v2
name: bioinvest-api
description: BioInvest AI Copilot API Service
version: 1.0.0
appVersion: "1.0.0"

dependencies:
- name: postgresql
  version: 12.1.6
  repository: https://charts.bitnami.com/bitnami
  condition: postgresql.enabled
```

```yaml
# helm/bioinvest-api/values.yaml
# Default values for bioinvest-api
replicaCount: 3

image:
  repository: 123456789.dkr.ecr.us-east-1.amazonaws.com/bioinvest
  pullPolicy: IfNotPresent
  tag: "latest"

nameOverride: ""
fullnameOverride: ""

serviceAccount:
  create: true
  annotations: {}
  name: ""

podAnnotations: {}

podSecurityContext:
  fsGroup: 1000
  runAsNonRoot: true
  runAsUser: 1000

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000

service:
  type: ClusterIP
  port: 80
  targetPort: 8000

ingress:
  enabled: true
  className: "alb"
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/ssl-redirect: '443'
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: api.bioinvest.ai
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: api-tls
      hosts:
        - api.bioinvest.ai

resources:
  limits:
    cpu: 1000m
    memory: 2Gi
  requests:
    cpu: 250m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

nodeSelector: {}

tolerations: []

affinity: {}

# Environment-specific configurations
env:
  DATABASE_URL:
    valueFrom:
      secretKeyRef:
        name: database-secrets
        key: connection-string
  REDIS_URL:
    valueFrom:
      secretKeyRef:
        name: redis-secrets
        key: connection-string

# Monitoring
monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
    interval: 30s
    path: /metrics

# Health checks
healthcheck:
  enabled: true
  livenessProbe:
    httpGet:
      path: /health
      port: 8000
    initialDelaySeconds: 30
    periodSeconds: 10
    timeoutSeconds: 5
    failureThreshold: 3
  readinessProbe:
    httpGet:
      path: /ready
      port: 8000
    initialDelaySeconds: 5
    periodSeconds: 5
    timeoutSeconds: 3
    failureThreshold: 3
```

## Network Architecture

### VPC Configuration
```hcl
# terraform/vpc.tf
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = "bioinvest-prod-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  database_subnets = ["10.0.201.0/24", "10.0.202.0/24", "10.0.203.0/24"]

  enable_nat_gateway = true
  enable_vpn_gateway = true
  enable_dns_hostnames = true
  enable_dns_support = true

  # VPC Flow Logs
  enable_flow_log                      = true
  create_flow_log_cloudwatch_iam_role  = true
  create_flow_log_cloudwatch_log_group = true

  # Network ACLs
  manage_default_network_acl = true
  default_network_acl_tags   = { Name = "${local.name}-default" }

  manage_default_route_table = true
  default_route_table_tags   = { Name = "${local.name}-default" }

  manage_default_security_group = true
  default_security_group_tags    = { Name = "${local.name}-default" }

  tags = {
    Terraform = "true"
    Environment = "production"
  }
}

# Security Groups
resource "aws_security_group" "alb" {
  name_prefix = "bioinvest-alb-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "bioinvest-alb-sg"
  }
}

resource "aws_security_group" "eks_nodes" {
  name_prefix = "bioinvest-eks-nodes-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "Node to node all ports/protocols"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  ingress {
    description     = "EKS Cluster API to node groups"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "bioinvest-eks-nodes-sg"
  }
}
```

## Monitoring and Observability

### Prometheus and Grafana Stack
```yaml
# kubernetes/monitoring/prometheus.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    rule_files:
      - "/etc/prometheus/rules/*.yml"
    
    scrape_configs:
      - job_name: 'kubernetes-apiservers'
        kubernetes_sd_configs:
        - role: endpoints
        scheme: https
        tls_config:
          ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
        bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
        relabel_configs:
        - source_labels: [__meta_kubernetes_namespace, __meta_kubernetes_service_name, __meta_kubernetes_endpoint_port_name]
          action: keep
          regex: default;kubernetes;https
      
      - job_name: 'kubernetes-nodes'
        kubernetes_sd_configs:
        - role: node
        relabel_configs:
        - action: labelmap
          regex: __meta_kubernetes_node_label_(.+)
        - target_label: __address__
          replacement: kubernetes.default.svc:443
        - source_labels: [__meta_kubernetes_node_name]
          regex: (.+)
          target_label: __metrics_path__
          replacement: /api/v1/nodes/${1}/proxy/metrics
      
      - job_name: 'bioinvest-api'
        kubernetes_sd_configs:
        - role: endpoints
          namespaces:
            names:
            - bioinvest-api
        relabel_configs:
        - source_labels: [__meta_kubernetes_service_annotation_prometheus_io_scrape]
          action: keep
          regex: true
        - source_labels: [__meta_kubernetes_service_annotation_prometheus_io_path]
          action: replace
          target_label: __metrics_path__
          regex: (.+)

    alerting:
      alertmanagers:
        - static_configs:
            - targets:
              - alertmanager:9093

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      serviceAccountName: prometheus
      containers:
      - name: prometheus
        image: prom/prometheus:v2.40.0
        args:
          - '--config.file=/etc/prometheus/prometheus.yml'
          - '--storage.tsdb.path=/prometheus/'
          - '--web.console.libraries=/etc/prometheus/console_libraries'
          - '--web.console.templates=/etc/prometheus/consoles'
          - '--storage.tsdb.retention.time=15d'
          - '--web.enable-lifecycle'
        ports:
        - containerPort: 9090
        resources:
          requests:
            cpu: 200m
            memory: 1Gi
          limits:
            cpu: 500m
            memory: 2Gi
        volumeMounts:
        - name: prometheus-config
          mountPath: /etc/prometheus
        - name: prometheus-storage
          mountPath: /prometheus
      volumes:
      - name: prometheus-config
        configMap:
          name: prometheus-config
      - name: prometheus-storage
        persistentVolumeClaim:
          claimName: prometheus-pvc
```

### DataDog Integration
```yaml
# kubernetes/monitoring/datadog.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: datadog-agent
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: datadog-agent
  template:
    metadata:
      labels:
        app: datadog-agent
      annotations:
        container.apparmor.security.beta.kubernetes.io/system-probe: unconfined
    spec:
      serviceAccountName: datadog-agent
      containers:
      - image: datadog/agent:7
        imagePullPolicy: Always
        name: datadog-agent
        ports:
        - containerPort: 8125
          name: dogstatsdport
          protocol: UDP
        - containerPort: 8126
          name: traceport
          protocol: TCP
        env:
        - name: DD_API_KEY
          valueFrom:
            secretKeyRef:
              name: datadog-secret
              key: api-key
        - name: DD_SITE
          value: "datadoghq.com"
        - name: DD_COLLECT_KUBERNETES_EVENTS
          value: "true"
        - name: DD_LEADER_ELECTION
          value: "true"
        - name: DD_APM_ENABLED
          value: "true"
        - name: DD_LOGS_ENABLED
          value: "true"
        - name: DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL
          value: "true"
        - name: DD_CONTAINER_EXCLUDE_LOGS
          value: "name:datadog-agent"
        - name: DD_KUBERNETES_KUBELET_HOST
          valueFrom:
            fieldRef:
              fieldPath: status.hostIP
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        volumeMounts:
        - name: dockersocket
          mountPath: /var/run/docker.sock
        - name: procdir
          mountPath: /host/proc
          readOnly: true
        - name: cgroups
          mountPath: /host/sys/fs/cgroup
          readOnly: true
        livenessProbe:
          exec:
            command:
            - ./probe.sh
          initialDelaySeconds: 15
          periodSeconds: 5
      volumes:
      - hostPath:
          path: /var/run/docker.sock
        name: dockersocket
      - hostPath:
          path: /proc
        name: procdir
      - hostPath:
          path: /sys/fs/cgroup
        name: cgroups
```

## Disaster Recovery

### Backup Strategy
```bash
#!/bin/bash
# scripts/backup-strategy.sh

# Database Backup
pg_dump -h $RDS_ENDPOINT -U $DB_USER -d $DB_NAME | \
  aws s3 cp - s3://bioinvest-backups/postgres/$(date +%Y-%m-%d)/backup.sql

# Redis Backup
redis-cli -h $REDIS_ENDPOINT --rdb /tmp/dump.rdb
aws s3 cp /tmp/dump.rdb s3://bioinvest-backups/redis/$(date +%Y-%m-%d)/dump.rdb

# Kubernetes State Backup
kubectl get all --all-namespaces -o yaml > /tmp/k8s-state.yaml
aws s3 cp /tmp/k8s-state.yaml s3://bioinvest-backups/kubernetes/$(date +%Y-%m-%d)/state.yaml

# Application Secrets Backup (encrypted)
kubectl get secrets --all-namespaces -o yaml | \
  gpg --cipher-algo AES256 --compress-algo 1 --s2k-mode 3 \
      --s2k-digest-algo SHA512 --s2k-count 65536 --force-mdc \
      --quiet --no-greeting --batch --yes --encrypt \
      --recipient backup@bioinvest.ai | \
  aws s3 cp - s3://bioinvest-backups/secrets/$(date +%Y-%m-%d)/secrets.gpg
```

### DR Runbook
```yaml
# disaster-recovery/runbook.md
# BioInvest AI Copilot - Disaster Recovery Runbook

## RTO: 1 Hour | RPO: 5 Minutes

### Phase 1: Assessment (5 minutes)
1. Determine scope of outage
2. Activate incident response team
3. Notify stakeholders via PagerDuty

### Phase 2: Failover (15 minutes)
1. Switch DNS to DR region
   ```bash
   aws route53 change-resource-record-sets \
     --hosted-zone-id Z123456789 \
     --change-batch file://dr-dns-change.json
   ```

2. Promote read replica to primary
   ```bash
   aws rds promote-read-replica \
     --db-instance-identifier bioinvest-prod-dr
   ```

3. Update application configuration
   ```bash
   kubectl patch configmap app-config \
     --patch '{"data":{"DATABASE_URL":"postgresql://dr-endpoint:5432/bioinvest"}}'
   ```

### Phase 3: Verification (10 minutes)
1. Health check all services
2. Verify data integrity
3. Test critical user flows

### Phase 4: Communication (30 minutes)
1. Update status page
2. Notify customers
3. Coordinate with support team
```

This comprehensive infrastructure architecture provides a robust, scalable, and secure foundation for the BioInvest AI Copilot platform, ensuring high availability, performance, and reliability for biotech investment research operations.
terraform {
  required_version = ">= 1.6.0"

  backend "s3" {
    bucket               = "bio-mcp-tfstate-298367968337-us-west-2"
    key                  = "terraform.tfstate"   # constant filename
    workspace_key_prefix = "envs"                # puts states under envs/<workspace>/
    region               = "us-west-2"
    dynamodb_table       = "terraform-locks"
    encrypt              = true
  }
}

locals {
  common_tags = {
    Project = "bio-mcp"
    Owner   = "you"
    Env     = var.env
  }
}

# Provider configuration is in providers.tf

# Default VPC + subnets as shared data sources
data "aws_vpc" "default" { default = true }

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Helpful outputs
output "rds_endpoint" {
  value = aws_db_instance.pg.address
}

output "ecs_cluster" {
  value = aws_ecs_cluster.bio.name
}

output "ecr_repo_url" {
  value = aws_ecr_repository.bio_mcp.repository_url
}

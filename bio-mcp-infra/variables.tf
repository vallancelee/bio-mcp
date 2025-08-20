variable "env" {
  description = "Environment name (dev|stage|prod)"
  type        = string
}

variable "my_ip_cidr" { description = "Your home IP, e.g. 1.2.3.4/32" }

variable "rds_master_username" { default = "biomcp_admin" }
variable "rds_master_password" { sensitive = true }
variable "app_db_password"     { sensitive = true }

variable "pubmed_api_key" { sensitive = true }
variable "openai_api_key" { sensitive = true }

variable "account_id" {
  description = "AWS Account ID"
  type        = string
}

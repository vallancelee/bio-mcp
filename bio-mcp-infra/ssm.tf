resource "aws_ssm_parameter" "db_url" {
  name  = "/bio-mcp/${var.env}/DB_URL"
  type  = "SecureString"
  value = "postgresql://biomcp_app:${var.app_db_password}@${aws_db_instance.pg.address}:5432/bio_mcp"
}

resource "aws_ssm_parameter" "pubmed_api_key" {
  name  = "/bio-mcp/${var.env}/PUBMED_API_KEY"
  type  = "SecureString"
  value = var.pubmed_api_key
}

resource "aws_ssm_parameter" "openai_api_key" {
  name  = "/bio-mcp/${var.env}/OPENAI_API_KEY"
  type  = "SecureString"
  value = var.openai_api_key
}

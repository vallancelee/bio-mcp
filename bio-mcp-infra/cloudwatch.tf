resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/bio-mcp-${var.env}"
  retention_in_days = 7
}

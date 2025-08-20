resource "aws_scheduler_schedule" "daily_sync" {
  name                  = "bio-mcp-daily-sync-${var.env}"
  schedule_expression   = "rate(1 day)"
  flexible_time_window { mode = "OFF" }

  target {
    arn      = aws_ecs_cluster.bio.arn
    role_arn = aws_iam_role.ecs_task_role.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.server.arn
      launch_type         = "FARGATE"
      network_configuration {
        subnets          = data.aws_subnets.default.ids
        assign_public_ip = true
        security_groups  = [aws_security_group.rds.id]
      }
      task_count = 1
    }

    input = jsonencode({
      containerOverrides = [{
        name = "server",
        command = ["python","-m","bio_mcp.clients.seed","--since","1d","--limit","500"]
      }]
    })
  }
}

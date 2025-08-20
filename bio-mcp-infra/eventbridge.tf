resource "aws_ecs_cluster" "bio" {
  name = "bio-mcp"
}

resource "aws_ecs_task_definition" "server" {
  family                   = "bio-mcp"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "server",
      image     = "${aws_ecr_repository.bio_mcp.repository_url}:latest",
      essential = true,
      portMappings = [{ containerPort = 3000, hostPort = 3000 }],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name,
          awslogs-region        = var.aws_region,
          awslogs-stream-prefix = "ecs"
        }
      },
      secrets = [
        { name = "BIO_MCP_DATABASE_URL", valueFrom = aws_ssm_parameter.db_url.arn },
        { name = "BIO_MCP_PUBMED_API_KEY", valueFrom = aws_ssm_parameter.pubmed_api_key.arn },
        { name = "BIO_MCP_OPENAI_API_KEY", valueFrom = aws_ssm_parameter.openai_api_key.arn }
      ]
    }
  ])
}

resource "aws_ecs_service" "server" {
  name            = "bio-mcp"
  cluster         = aws_ecs_cluster.bio.id
  task_definition = aws_ecs_task_definition.server.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = data.aws_subnets.default.ids
    assign_public_ip = true
    security_groups = [aws_security_group.rds.id]
  }
}

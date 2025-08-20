data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_role" {
  name = "bio-mcp-ecs-task-role-${var.env}"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "bio-mcp-task-policy-${var.env}"
  role = aws_iam_role.ecs_task_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      { Effect="Allow", Action=["ssm:GetParameter","ssm:GetParameters","kms:Decrypt"], Resource="*" },
      { Effect="Allow", Action=["s3:*"], Resource=[aws_s3_bucket.raw.arn, "${aws_s3_bucket.raw.arn}/*"] }
    ]
  })
}

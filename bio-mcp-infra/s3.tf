data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "raw" {
  bucket = "bio-mcp-raw-${var.env}-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
}

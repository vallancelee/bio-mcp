# VPC and subnet data sources are defined in main.tf

resource "aws_security_group" "rds" {
  name   = "bio-mcp-rds-sg-${var.env}"
  vpc_id = data.aws_vpc.default.id

  # allow ECS tasks & your IP for admin
  ingress {
    description      = "Admin from home IP"
    from_port        = 5432
    to_port          = 5432
    protocol         = "tcp"
    cidr_blocks      = [var.my_ip_cidr]
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "pg" {
  identifier              = "bio-mcp-${var.env}"
  allocated_storage       = 20
  engine                  = "postgres"
  engine_version          = "15"
  instance_class          = "db.t4g.micro"
  db_name                 = "bio_mcp"
  username                = var.rds_master_username
  password                = var.rds_master_password
  publicly_accessible     = true
  vpc_security_group_ids  = [aws_security_group.rds.id]
  skip_final_snapshot     = true
}

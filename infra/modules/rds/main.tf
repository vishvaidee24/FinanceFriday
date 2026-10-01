resource "aws_db_subnet_group" "this" {
  name_prefix = "${var.project_name}-"
  subnet_ids  = var.private_subnet_ids
}

resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-rds-"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from worker only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.worker_security_group_id]
  }
}

resource "aws_db_instance" "this" {
  identifier_prefix = "${var.project_name}-"

  engine         = "postgres"
  engine_version = "17"
  instance_class = var.db_instance_class

  db_name                     = var.db_name
  username                    = var.db_username
  manage_master_user_password = true

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible = false
  multi_az            = false

  backup_retention_period = 3

  deletion_protection = false
  skip_final_snapshot = true

  performance_insights_enabled = false
  monitoring_interval          = 0
  auto_minor_version_upgrade   = true
}

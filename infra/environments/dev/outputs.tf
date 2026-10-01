output "deployed_account_id" {
  description = "Account Terraform actually deployed the finance infrastructure into."
  value       = data.aws_caller_identity.current.account_id
}

output "raw_bucket_name" {
  value = module.s3.raw_bucket_name
}

output "rds_endpoint" {
  value = module.rds.endpoint
}

output "worker_instance_id" {
  value = module.worker.instance_id
}

output "rds_master_user_secret_arn" {
  value = module.rds.master_user_secret_arn
}

output "alpaca_secret_arn" {
  value = aws_secretsmanager_secret.alpaca.arn
}

output "fmp_secret_arn" {
  value = aws_secretsmanager_secret.fmp.arn
}

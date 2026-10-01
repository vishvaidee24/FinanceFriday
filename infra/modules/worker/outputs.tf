output "worker_security_group_id" { value = aws_security_group.worker.id }
output "instance_id" { value = aws_instance.worker.id }
output "iam_role_name" { value = aws_iam_role.worker.name }

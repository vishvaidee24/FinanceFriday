$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$InfraDir = Join-Path $RepoRoot "infra\environments\dev"
Set-Location $InfraDir

$FINANCE_ACCOUNT_ID = terraform output -raw deployed_account_id
$WORKER_ID = terraform output -raw worker_instance_id
$RDS_HOST = terraform output -raw rds_endpoint
$SECRET_ARN = terraform output -raw rds_master_user_secret_arn

aws configure set role_arn "arn:aws:iam::${FINANCE_ACCOUNT_ID}:role/OrganizationAccountAccessRole" --profile finance-dev

aws configure set source_profile default --profile finance-dev

aws configure set region us-east-1 --profile finance-dev

$SSM_PARAMS = @{
    host            = @($RDS_HOST)
    portNumber      = @("5432")
    localPortNumber = @("5433")
}

$SSM_PARAMS | ConvertTo-Json -Compress | Set-Content -Encoding ascii .\ssm-params.json

aws ssm start-session `
    --profile finance-dev `
    --target $WORKER_ID `
    --document-name AWS-StartPortForwardingSessionToRemoteHost `
    --parameters file://ssm-params.json
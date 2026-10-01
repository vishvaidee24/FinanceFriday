param(
    [string]$Profile = "finance-dev",
    [int]$LocalPort = 15432
)

$ErrorActionPreference = "Stop"

$Region = "us-east-1"
$WorkerId = "i-04e30cde58d33935f"
$RdsHost = "finance-platform-d4f95f41b19e3256667dab3369.cq1u4cwyqmuw.us-east-1.rds.amazonaws.com"
$SecretArn = "arn:aws:secretsmanager:us-east-1:534670738003:secret:rds!db-69994a7d-70a7-4f07-bef7-7ae26972d968-o7icRm"

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "AWS CLI is not installed or is not on PATH."
}

if (-not (Get-Command session-manager-plugin -ErrorAction SilentlyContinue)) {
    throw "AWS Session Manager plugin is not installed or is not on PATH."
}

aws sts get-caller-identity --profile $Profile --region $Region --output json | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "AWS authentication failed for profile '$Profile'."
}

$SecretJson = aws secretsmanager get-secret-value `
    --secret-id $SecretArn `
    --query SecretString `
    --output text `
    --profile $Profile `
    --region $Region
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read the RDS credential from Secrets Manager."
}

$Credential = $SecretJson | ConvertFrom-Json
$Credential.password | Set-Clipboard

Write-Host ""
Write-Host "DBeaver PostgreSQL connection"
Write-Host "  Host:     localhost"
Write-Host "  Port:     $LocalPort"
Write-Host "  Database: finance"
Write-Host "  Username: $($Credential.username)"
Write-Host "  Password: copied to clipboard"
Write-Host ""
Write-Host "Keep this window open while DBeaver is connected. Press Ctrl+C to close the tunnel."

$SsmParameters = @{
    host = @($RdsHost)
    portNumber = @("5432")
    localPortNumber = @("$LocalPort")
} | ConvertTo-Json -Compress

$ParameterFile = Join-Path ([System.IO.Path]::GetTempPath()) "financefriday-ssm-parameters.json"
$SsmParameters | Set-Content -LiteralPath $ParameterFile -Encoding Ascii

try {
    aws ssm start-session `
        --target $WorkerId `
        --document-name AWS-StartPortForwardingSessionToRemoteHost `
        --parameters "file://$($ParameterFile.Replace('\', '/'))" `
        --profile $Profile `
        --region $Region
} finally {
    Remove-Item -LiteralPath $ParameterFile -Force -ErrorAction SilentlyContinue
}

if ($LASTEXITCODE -ne 0) {
    throw "The SSM port-forwarding session ended with an error."
}

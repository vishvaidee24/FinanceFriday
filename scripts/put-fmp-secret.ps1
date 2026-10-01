param(
    [string]$Profile = "finance-dev"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $RepoRoot ".env"
$StateFile = Join-Path $RepoRoot "infra\environments\dev\terraform.tfstate"

$ApiKeyLine = Get-Content -LiteralPath $EnvFile |
    Where-Object { $_ -match '^FMP_API_KEY=' } |
    Select-Object -First 1
if (-not $ApiKeyLine) {
    throw "FMP_API_KEY is missing from .env"
}
$ApiKey = ($ApiKeyLine -split '=', 2)[1].Trim()
if (-not $ApiKey) {
    throw "FMP_API_KEY is empty in .env"
}

$State = Get-Content -Raw -LiteralPath $StateFile | ConvertFrom-Json
$SecretArn = $State.outputs.fmp_secret_arn.value
if (-not $SecretArn) {
    throw "Apply Terraform first so the FMP secret exists"
}

$TempFile = New-TemporaryFile
try {
    $SecretJson = @{ FMP_API_KEY = $ApiKey } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText(
        $TempFile.FullName,
        $SecretJson,
        [System.Text.UTF8Encoding]::new($false)
    )
    aws secretsmanager put-secret-value `
        --profile $Profile `
        --region us-east-1 `
        --secret-id $SecretArn `
        --secret-string "file://$($TempFile.FullName)" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to populate the FMP secret"
    }
    Write-Host "FMP secret populated successfully."
}
finally {
    Remove-Item -LiteralPath $TempFile.FullName -Force -ErrorAction SilentlyContinue
}

param(
    [switch]$Data,
    [switch]$Transform,
    [switch]$Security,
    [string]$GitleaksPath = 'gitleaks'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent

function Invoke-Check {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed with exit code $LASTEXITCODE. Resolve this before continuing."
    }
}

$previousDbtTelemetry = $env:DBT_SEND_ANONYMOUS_USAGE_STATS
Push-Location $projectRoot
try {
    Write-Host 'Checking Python style, types, and offline tests.'
    $runArgs = @('run', '--locked', '--group', 'data', '--group', 'warehouse')
    if ($Transform) { $runArgs += @('--group', 'transform') }
    if ($Security) { $runArgs += @('--group', 'audit') }
    if ($Transform) {
        $env:DBT_SEND_ANONYMOUS_USAGE_STATS = 'false'
        Invoke-Check 'uv' ($runArgs + @('dbt', '--version'))
    }
    Invoke-Check 'uv' ($runArgs + @('ruff', 'check', '.'))
    Invoke-Check 'uv' ($runArgs + @('ruff', 'format', '--check', '.'))
    Invoke-Check 'uv' ($runArgs + @('mypy'))
    Invoke-Check 'uv' ($runArgs + @('pytest'))
    Invoke-Check 'uv' @('pip', 'check')
    if ($Transform) {
        Invoke-Check 'uv' ($runArgs + @('python', '-m', 'src.warehouse', 'dbt-parse'))
    }

    Write-Host 'Checking frontend formatting, lint, types, and production compilation.'
    $npmProgram = if ($env:OS -eq 'Windows_NT') { 'npm.cmd' } else { 'npm' }
    foreach ($task in @('format:check', 'lint', 'typecheck', 'build')) {
        Invoke-Check $npmProgram @('--prefix', 'web', 'run', $task)
    }

    if ($Data) {
        Write-Host 'Verifying the existing local dataset and regenerating quality evidence.'
        Invoke-Check 'uv' ($runArgs + @('python', '-m', 'src.ingestion.olist', '--verify'))
        Invoke-Check 'uv' ($runArgs + @('python', '-m', 'src.validation.run'))
    }
    if ($Security) {
        Write-Host 'Checking known dependency advisories and Git history for secrets.'
        Invoke-Check 'uv' ($runArgs + @('pip-audit', '--local'))
        Invoke-Check $npmProgram @('--prefix', 'web', 'audit', '--audit-level=low')
        Invoke-Check $GitleaksPath @('git', '.', '--log-opts=--all', '--redact', '--no-banner')
    }
    Write-Host 'All selected checks passed.'
} finally {
    $env:DBT_SEND_ANONYMOUS_USAGE_STATS = $previousDbtTelemetry
    Pop-Location
}

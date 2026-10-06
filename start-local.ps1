param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    throw 'Run .\setup-local.ps1 first.'
}
if (-not (Test-Path -LiteralPath 'config.json')) {
    throw 'Copy config.example.json to config.json and configure it first.'
}

$TokenFile = Join-Path $ProjectRoot '.local-token'
if (-not (Test-Path -LiteralPath $TokenFile)) {
    $Bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Fill($Bytes)
    [Convert]::ToHexString($Bytes).ToLowerInvariant() | Set-Content -LiteralPath $TokenFile -NoNewline
}
$env:API_TOKEN = (Get-Content -LiteralPath $TokenFile -Raw).Trim()
$env:CONFIG_PATH = (Resolve-Path -LiteralPath 'config.json').Path
$env:DATA_DIR = (Resolve-Path -LiteralPath 'data').Path

Write-Host "Job automation is starting at http://127.0.0.1:$Port"
Write-Host "Use .\jobbot-local.ps1 status, run, or excel in a second PowerShell window."
& .\.venv\Scripts\python.exe -m uvicorn jobbot.api:app --host 127.0.0.1 --port $Port

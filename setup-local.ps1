$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    $Python = Get-Command py -ErrorAction SilentlyContinue
    if ($Python) {
        & py -3 -m venv .venv
    } else {
        throw 'Python 3.11+ is required. Install Python, then run this script again.'
    }
}

& .\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
if (-not (Test-Path -LiteralPath 'config.json')) {
    Copy-Item -LiteralPath 'config.example.json' -Destination 'config.json'
    Write-Host 'Created config.json. Fill your profile and job-board slugs before starting.'
}
Write-Host 'Local setup is ready.'

param(
    [ValidateSet('status', 'run', 'excel')]
    [string]$Command = 'status',
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot
$TokenFile = Join-Path $ProjectRoot '.local-token'
if (-not (Test-Path -LiteralPath $TokenFile)) {
    throw 'Start the service with .\start-local.ps1 first.'
}
$Headers = @{ Authorization = 'Bearer ' + (Get-Content -LiteralPath $TokenFile -Raw).Trim() }
$BaseUrl = "http://127.0.0.1:$Port"

switch ($Command) {
    'status' {
        $Health = Invoke-RestMethod -Uri "$BaseUrl/health" -Headers $Headers
        $Jobs = Invoke-RestMethod -Uri "$BaseUrl/jobs" -Headers $Headers
        [pscustomobject]@{
            Service = $Health.status
            TotalJobs = @($Jobs).Count
            Prepared = @($Jobs | Where-Object status -eq 'prepared').Count
            Applied = @($Jobs | Where-Object status -eq 'applied').Count
            NeedsReview = @($Jobs | Where-Object status -eq 'needs_review').Count
        } | Format-List
    }
    'run' {
        Invoke-RestMethod -Method Post -Uri "$BaseUrl/run" -Headers $Headers | Format-List
    }
    'excel' {
        $Output = Join-Path $ProjectRoot 'jobs.xlsx'
        Invoke-WebRequest -Uri "$BaseUrl/excel" -Headers $Headers -OutFile $Output
        Write-Host "Downloaded: $Output"
    }
}

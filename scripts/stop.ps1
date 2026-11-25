$ErrorActionPreference = 'SilentlyContinue'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $ProjectRoot '.bestshot-runtime'
$PidFiles = @(
    (Join-Path $RuntimeRoot 'backend.pid'),
    (Join-Path $RuntimeRoot 'frontend.pid')
)

foreach ($PidFile in $PidFiles) {
    if (Test-Path -LiteralPath $PidFile) {
        $ProcessId = Get-Content -LiteralPath $PidFile | Select-Object -First 1
        if ($ProcessId -match '^\d+$') {
            & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
        }
        Remove-Item -LiteralPath $PidFile -Force
    }
}

Write-Host 'BestShot-photos has stopped.' -ForegroundColor Green
Start-Sleep -Seconds 1

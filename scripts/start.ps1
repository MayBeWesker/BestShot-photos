$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $ProjectRoot 'backend'
$FrontendRoot = Join-Path $ProjectRoot 'frontend'
$RuntimeRoot = Join-Path $ProjectRoot '.bestshot-runtime'
$PythonExe = Join-Path $BackendRoot '.venv\Scripts\python.exe'
$BackendPidFile = Join-Path $RuntimeRoot 'backend.pid'
$FrontendPidFile = Join-Path $RuntimeRoot 'frontend.pid'
$BackendLog = Join-Path $RuntimeRoot 'backend.log'
$FrontendLog = Join-Path $RuntimeRoot 'frontend.log'
$BackendErrorLog = Join-Path $RuntimeRoot 'backend-error.log'
$FrontendErrorLog = Join-Path $RuntimeRoot 'frontend-error.log'
$AppUrl = 'http://127.0.0.1:5173'
$HealthUrl = 'http://127.0.0.1:8000/api/health'

New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null

function Test-BestShotReady {
    try {
        $Health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
        $Page = Invoke-WebRequest -Uri $AppUrl -UseBasicParsing -TimeoutSec 2
        return ($Health.status -eq 'ok' -and $Page.StatusCode -eq 200)
    }
    catch {
        return $false
    }
}

if (Test-BestShotReady) {
    Start-Process $AppUrl
    Write-Host 'BestShot-photos is already running. The browser has been opened.' -ForegroundColor Green
    exit 0
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Host 'First launch: preparing the Python environment...' -ForegroundColor Yellow
    python -m venv (Join-Path $BackendRoot '.venv')
    & $PythonExe -m pip install -r (Join-Path $BackendRoot 'requirements.txt')
}

# Existing installations may predate HEIC support. Install newly added backend
# dependencies without forcing a full environment rebuild.
& $PythonExe -c "import pillow_heif, httpx" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Updating backend dependencies (image formats and DeepSeek)...' -ForegroundColor Yellow
    & $PythonExe -m pip install -r (Join-Path $BackendRoot 'requirements.txt')
}

if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot 'node_modules'))) {
    Write-Host 'First launch: preparing frontend dependencies...' -ForegroundColor Yellow
    npm --prefix $FrontendRoot install
}

Write-Host 'Starting BestShot-photos...' -ForegroundColor Cyan

$BackendProcess = Start-Process -FilePath $PythonExe -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory $BackendRoot -WindowStyle Hidden -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErrorLog -PassThru
$FrontendProcess = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev') -WorkingDirectory $FrontendRoot -WindowStyle Hidden -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErrorLog -PassThru

Set-Content -LiteralPath $BackendPidFile -Value $BackendProcess.Id -Encoding ascii
Set-Content -LiteralPath $FrontendPidFile -Value $FrontendProcess.Id -Encoding ascii

$Ready = $false
for ($Attempt = 1; $Attempt -le 30; $Attempt++) {
    Start-Sleep -Seconds 1
    if (Test-BestShotReady) {
        $Ready = $true
        break
    }
    if ($BackendProcess.HasExited -or $FrontendProcess.HasExited) {
        break
    }
}

if (-not $Ready) {
    if (-not $BackendProcess.HasExited) { Stop-Process -Id $BackendProcess.Id -Force }
    if (-not $FrontendProcess.HasExited) { Stop-Process -Id $FrontendProcess.Id -Force }
    throw "BestShot-photos failed to start. Logs: $RuntimeRoot"
}

Start-Process $AppUrl
Write-Host 'BestShot-photos is ready. The browser has been opened.' -ForegroundColor Green
Write-Host 'You can close this window.'
Start-Sleep -Seconds 2


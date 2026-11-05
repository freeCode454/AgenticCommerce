param([ValidateSet('Setup', 'Start', 'Stop', 'Status')][string]$Action = 'Start')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$recordPath = Join-Path $projectRoot '.local-run.json'

function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
}

function Stop-LocalProcesses {
    if (Test-Path -LiteralPath $recordPath) {
        $records = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
        foreach ($record in $records) {
            $ownedProcess = Get-Process -Id $record.id -ErrorAction SilentlyContinue
            if ($ownedProcess -and $ownedProcess.StartTime.ToUniversalTime().Ticks -eq $record.startedUtcTicks -and $ownedProcess.Path -eq $record.path) {
                Stop-Process -Id $record.id
            }
        }
        Remove-Item -LiteralPath $recordPath
    }
}

if ($Action -eq 'Stop') {
    Stop-LocalProcesses
    if (Test-Path -LiteralPath '.env.local') {
        Invoke-Checked 'docker' @('compose', '--env-file', '.env.local', '-f', 'docker-compose.infra.yml', 'stop')
    }
    Write-Host 'Project processes stopped. Development volumes were retained.'
    exit
}

if ($Action -eq 'Status') {
    if (Test-Path -LiteralPath '.env.local') {
        Invoke-Checked 'docker' @('compose', '--env-file', '.env.local', '-f', 'docker-compose.infra.yml', 'ps')
        $config = & $pythonPath -c 'import json; from app.conf.config import settings; print(json.dumps({"port":settings.APP_PORT,"frontend":settings.FRONTEND_PORT}))' | ConvertFrom-Json
        try { Invoke-RestMethod -Uri "http://127.0.0.1:$($config.port)/ready" -TimeoutSec 5 | ConvertTo-Json -Depth 4 }
        catch { Write-Host 'Backend is not ready.' }
        Write-Host "Frontend: http://127.0.0.1:$($config.frontend)"
    } else { Write-Host 'Run Setup first.' }
    exit
}

if (Test-Path -LiteralPath $recordPath) { throw 'A local process record exists. Run Status or Stop before starting again.' }
Invoke-Checked 'uv' @('sync', '--frozen', '--extra', 'dev')
Invoke-Checked $pythonPath @('-m', 'app.scripts.setup_local')
Invoke-Checked 'docker' @('compose', '--env-file', '.env.local', '-f', 'docker-compose.infra.yml', 'up', '-d', '--wait', '--wait-timeout', '90')
Invoke-Checked $pythonPath @('-m', 'alembic', 'upgrade', 'head')
Invoke-Checked $pythonPath @('-m', 'app.scripts.bootstrap_local')
if (!(Test-Path -LiteralPath 'frontend\node_modules\vite\bin\vite.js')) {
    Push-Location -LiteralPath 'frontend'
    try { Invoke-Checked 'npm.cmd' @('ci') } finally { Pop-Location }
}
if ($Action -eq 'Setup') { Write-Host 'Setup complete. Login credentials are in .env.local.'; exit }

$config = & $pythonPath -c 'import json; from app.conf.config import settings; print(json.dumps({"port":settings.APP_PORT,"frontend":settings.FRONTEND_PORT}))' | ConvertFrom-Json
foreach ($port in @($config.port, $config.frontend)) {
    $socket = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $socket.ConnectAsync('127.0.0.1', $port)
        if ($connect.Wait(500) -and $socket.Connected) { throw "Port $port is already occupied." }
    } catch [System.AggregateException] { } finally { $socket.Dispose() }
}
New-Item -ItemType Directory -Path 'logs' -Force | Out-Null
$startedRecords = @()
try {
    $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', $config.port) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'logs\backend.out.log') -RedirectStandardError (Join-Path $projectRoot 'logs\backend.err.log') -PassThru
    $startedRecords += [pscustomobject]@{ id = $backendProcess.Id; startedUtcTicks = $backendProcess.StartTime.ToUniversalTime().Ticks; path = $backendProcess.Path }
    $startedRecords | ConvertTo-Json -AsArray | Set-Content -LiteralPath $recordPath -Encoding utf8
    $vitePath = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
    $frontendProcess = Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @("`"$vitePath`"") -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'logs\frontend.out.log') -RedirectStandardError (Join-Path $projectRoot 'logs\frontend.err.log') -PassThru
    $startedRecords += [pscustomobject]@{ id = $frontendProcess.Id; startedUtcTicks = $frontendProcess.StartTime.ToUniversalTime().Ticks; path = $frontendProcess.Path }
    $startedRecords | ConvertTo-Json -AsArray | Set-Content -LiteralPath $recordPath -Encoding utf8
    $ready = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) { throw 'A local service exited. Check logs.' }
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:$($config.port)/ready" -TimeoutSec 3
            if ($response.status -eq 'ready') { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (!$ready) { throw 'Backend readiness timed out. Check logs.' }
    Write-Host "Frontend: http://127.0.0.1:$($config.frontend)"
    Write-Host "API docs: http://127.0.0.1:$($config.port)/docs"
    Write-Host 'Administrator email and password: BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD in .env.local.'
} catch {
    Stop-LocalProcesses
    throw
}

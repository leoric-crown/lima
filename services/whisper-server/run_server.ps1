# LIMA Whisper CUDA Server Launcher (Windows)
# Sets up CUDA library paths and runs the server with NVIDIA GPU acceleration

param(
    [string]$Port,
    [string]$ServerHost,
    [string]$Model,
    [string]$Device,
    [string]$ComputeType,
    [switch]$Background,
    [string]$LogFile,
    [string]$PidFile
)

# Load .env from project root if it exists
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$EnvFile = Join-Path $ProjectRoot ".env"

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $Matches[1].Trim()
            $value = $Matches[2].Trim()
            $value = $value -replace '^["'']|["'']$', ''
            if ($key -in @('NATIVE_WHISPER_HOST', 'NATIVE_WHISPER_PORT')) {
                [Environment]::SetEnvironmentVariable($key, $value, 'Process')
            }
        }
    }
}

# Use env vars if set, otherwise use defaults
if (-not $Port) {
    $Port = if ($env:NATIVE_WHISPER_PORT) { $env:NATIVE_WHISPER_PORT } else { "9001" }
}
if (-not $ServerHost) {
    $ServerHost = if ($env:NATIVE_WHISPER_HOST) { $env:NATIVE_WHISPER_HOST } else { "0.0.0.0" }
}

# Handle background mode: re-launch self hidden with output to log file
if ($Background) {
    $scriptPath = $MyInvocation.MyCommand.Path
    $argList = @(
        "-ExecutionPolicy", "Bypass",
        "-File", $scriptPath,
        "-Port", $Port,
        "-ServerHost", $ServerHost
    )
    if ($Model) { $argList += "-Model"; $argList += $Model }
    if ($Device) { $argList += "-Device"; $argList += $Device }
    if ($ComputeType) { $argList += "-ComputeType"; $argList += $ComputeType }

    # Start hidden process with output redirected to log file
    # Use cmd wrapper to merge stderr into stdout (PowerShell can't redirect both to same file)
    $cmdArgs = "/c powershell $($argList -join ' ') > `"$LogFile`" 2>&1"
    $proc = Start-Process -FilePath "cmd" -ArgumentList $cmdArgs -WindowStyle Hidden -PassThru

    # Write PID to file for tracking
    if ($PidFile) {
        $proc.Id | Out-File -FilePath $PidFile -Encoding ascii -NoNewline
    }

    Write-Host "Started in background (PID: $($proc.Id))"
    Write-Host "  Logs: $LogFile"
    exit 0
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "LIMA Faster-Whisper Server (CUDA) - Windows" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Change to script directory
Set-Location $ScriptDir

$VenvPath = Join-Path $ScriptDir ".venv"
$CudnnLib = Join-Path $VenvPath "Lib\site-packages\nvidia\cudnn\bin"
$CublasLib = Join-Path $VenvPath "Lib\site-packages\nvidia\cublas\bin"

# Step 1: Sync dependencies
Write-Host "Syncing dependencies..." -ForegroundColor Cyan
& uv sync

# Step 2: Install CUDA libraries if not present
if (-not (Test-Path $CudnnLib)) {
    Write-Host "Installing CUDA libraries (nvidia-cudnn-cu12)..." -ForegroundColor Cyan
    & uv pip install nvidia-cudnn-cu12
}

# Step 3: Add CUDA DLLs to PATH
$PathsToAdd = @()
if (Test-Path $CudnnLib) { $PathsToAdd += $CudnnLib }
if (Test-Path $CublasLib) { $PathsToAdd += $CublasLib }

if ($PathsToAdd.Count -gt 0) {
    $NewPath = ($PathsToAdd -join ";")
    $env:PATH = "$NewPath;$env:PATH"
    Write-Host "Added CUDA library paths for GPU acceleration:" -ForegroundColor Green
    foreach ($p in $PathsToAdd) {
        Write-Host "  - $p" -ForegroundColor Gray
    }
} else {
    Write-Host "Warning: CUDA libraries not found after install." -ForegroundColor Yellow
    Write-Host "  Falling back to CPU mode..." -ForegroundColor Yellow
}

# Build command arguments
$ServerArgs = @("--port", $Port, "--host", $ServerHost)

if ($Model) {
    $ServerArgs += "--model"
    $ServerArgs += $Model
}
if ($Device) {
    $ServerArgs += "--device"
    $ServerArgs += $Device
}
if ($ComputeType) {
    $ServerArgs += "--compute-type"
    $ServerArgs += $ComputeType
}

# Run the server
Write-Host ""
& uv run server_cuda.py @ServerArgs

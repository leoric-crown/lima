# LIMA Whisper CUDA Server Launcher (Windows)
# Sets up CUDA library paths and runs the server with NVIDIA GPU acceleration

param(
    [string]$Port,
    [string]$ServerHost,
    [string]$Model,
    [string]$Device,
    [string]$ComputeType
)

# Load .env from project root if it exists
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$EnvFile = Join-Path $ProjectRoot ".env"

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        # Skip comments and empty lines
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
        # Parse KEY=VALUE
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $Matches[1].Trim()
            $value = $Matches[2].Trim()
            # Remove surrounding quotes
            $value = $value -replace '^["'']|["'']$', ''
            # Only set specific variables we need
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

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "LIMA Faster-Whisper Server (CUDA) - Windows" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Change to script directory
Set-Location $ScriptDir

# Find cuDNN and cuBLAS DLLs in venv
$VenvPath = Join-Path $ScriptDir ".venv"
$CudnnLib = Join-Path $VenvPath "Lib\site-packages\nvidia\cudnn\bin"
$CublasLib = Join-Path $VenvPath "Lib\site-packages\nvidia\cublas\bin"

# Add DLLs to PATH (Windows equivalent of LD_LIBRARY_PATH)
$PathsToAdd = @()
if (Test-Path $CudnnLib) { $PathsToAdd += $CudnnLib }
if (Test-Path $CublasLib) { $PathsToAdd += $CublasLib }

if ($PathsToAdd.Count -gt 0) {
    $NewPath = ($PathsToAdd -join ";")
    $env:PATH = "$NewPath;$env:PATH"
    Write-Host "✓ Added CUDA library paths for GPU acceleration:" -ForegroundColor Green
    foreach ($p in $PathsToAdd) {
        Write-Host "  - $p" -ForegroundColor Gray
    }
} else {
    Write-Host "⚠ Warning: CUDA libraries not found." -ForegroundColor Yellow
    Write-Host "  Run: uv pip install nvidia-cudnn-cu12" -ForegroundColor Yellow
    Write-Host "  Falling back to CPU mode..." -ForegroundColor Yellow
}

# Build command arguments
$Args = @("--port", $Port, "--host", $ServerHost)

if ($Model) {
    $Args += @("--model", $Model)
}
if ($Device) {
    $Args += @("--device", $Device)
}
if ($ComputeType) {
    $Args += @("--compute-type", $ComputeType)
}

# Run the server
Write-Host ""
& uv run server_cuda.py @Args

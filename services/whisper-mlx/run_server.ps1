# LIMA Whisper CUDA Server Launcher (Windows)
# Sets up CUDA library paths and runs the server with NVIDIA GPU acceleration

param(
    [string]$Port = "9001",
    [string]$ServerHost = "0.0.0.0",
    [string]$Model,
    [string]$Device,
    [string]$ComputeType
)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "LIMA Faster-Whisper Server (CUDA) - Windows" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Get the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
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

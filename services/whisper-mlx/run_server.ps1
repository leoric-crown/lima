# LIMA Whisper CUDA Server Launcher (Windows)
# Sets up CUDA library paths and runs the server with NVIDIA GPU acceleration

param(
    [string]$Port = "9001",
    [string]$Host = "0.0.0.0",
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

# Find cuDNN DLLs in venv
$VenvPath = Join-Path $ScriptDir ".venv"
$CudnnLib = Join-Path $VenvPath "Lib\site-packages\nvidia\cudnn\bin"

# Add cuDNN DLLs to PATH (Windows equivalent of LD_LIBRARY_PATH)
if (Test-Path $CudnnLib) {
    $env:PATH = "$CudnnLib;$env:PATH"
    Write-Host "✓ Added cuDNN library path for GPU acceleration" -ForegroundColor Green
    Write-Host "  Path: $CudnnLib" -ForegroundColor Gray
} else {
    Write-Host "⚠ Warning: cuDNN libraries not found at: $CudnnLib" -ForegroundColor Yellow
    Write-Host "  Run: uv pip install nvidia-cudnn-cu12" -ForegroundColor Yellow
    Write-Host "  Falling back to CPU mode..." -ForegroundColor Yellow
}

# Build command arguments
$Args = @("--port", $Port, "--host", $Host)

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

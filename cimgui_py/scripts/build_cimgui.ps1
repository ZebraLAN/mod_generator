# Build cimgui.dll with GLFW + OpenGL3 backend
# Usage: .\scripts\build_cimgui.ps1
# Prerequisites: Visual Studio 2022 with C++ workload, CMake, LuaJIT

$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $PSScriptRoot
$CIMGUI = Join-Path $ROOT "vendor\cimgui"
$BUILD_DIR = Join-Path $CIMGUI "build_dll"
$OUT_DIR = Join-Path $ROOT "lib"

# =============================================================================
# Step 1: Run cimgui generator (to get comments in definitions.json)
# =============================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 1: Running cimgui generator" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check LuaJIT
$luajit = Get-Command luajit -ErrorAction SilentlyContinue
if (-not $luajit) {
    Write-Host "LuaJIT not found. Installing via winget..." -ForegroundColor Yellow
    winget install DEVCOM.LuaJIT --accept-package-agreements
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# Run generator with comments option (requires cl.exe in PATH)
$generatorDir = Join-Path $CIMGUI "generator"
Push-Location $generatorDir
try {
    Write-Host "Running generator with 'internal comments' option..."
    # Use VS Developer environment for cl.exe
    $vsPath = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -latest -property installationPath
    $cmd = "`"$vsPath\Common7\Tools\VsDevCmd.bat`" -arch=amd64 && luajit generator.lua cl `"internal comments`""
    cmd /c $cmd
    if ($LASTEXITCODE -ne 0) { throw "Generator failed" }
    Write-Host "Generator completed successfully" -ForegroundColor Green
}
finally {
    Pop-Location
}

# =============================================================================
# =============================================================================
# Step 2: Download GLFW if needed
# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Step 2: Downloading GLFW" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$GLFW_DIR = Join-Path $ROOT "vendor\glfw"
$GLFW_VERSION = "3.4"
$GLFW_URL = "https://github.com/glfw/glfw/releases/download/$GLFW_VERSION/glfw-$GLFW_VERSION.bin.WIN64.zip"

if (-not (Test-Path (Join-Path $GLFW_DIR "include"))) {
    Write-Host "Downloading GLFW $GLFW_VERSION..."
    $zipPath = Join-Path $ROOT "glfw.zip"
    Invoke-WebRequest -Uri $GLFW_URL -OutFile $zipPath

    Write-Host "Extracting GLFW..."
    Expand-Archive -Path $zipPath -DestinationPath (Join-Path $ROOT "vendor") -Force
    Rename-Item (Join-Path $ROOT "vendor\glfw-$GLFW_VERSION.bin.WIN64") $GLFW_DIR -ErrorAction SilentlyContinue
    Remove-Item $zipPath
} else {
    Write-Host "GLFW already present" -ForegroundColor Green
}

$GLFW_INCLUDE = Join-Path $GLFW_DIR "include"
$GLFW_LIB = Join-Path $GLFW_DIR "lib-vc2022"

# =============================================================================
# Step 3: Build cimgui.dll
# =============================================================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Step 3: Building cimgui.dll" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Create build directory
if (-not (Test-Path $BUILD_DIR)) {
    New-Item -ItemType Directory -Path $BUILD_DIR | Out-Null
}

# Configure with CMake
Write-Host "Configuring with CMake..."
Push-Location $BUILD_DIR
try {
    cmake .. `
        -G "Visual Studio 17 2022" `
        -A x64 `
        -DIMGUI_STATIC=OFF `
        -DCIMGUI_BACKEND_GLFW=ON `
        -DCIMGUI_BACKEND_OPENGL3=ON `
        -DGLFW_INCLUDE_DIR="$GLFW_INCLUDE" `
        -DGLFW_LIBRARY_DIR="$GLFW_LIB"

    if ($LASTEXITCODE -ne 0) { throw "CMake configure failed" }

    # Build
    Write-Host "Building..."
    cmake --build . --config Release

    if ($LASTEXITCODE -ne 0) { throw "CMake build failed" }

    # Copy output
    Write-Host "Copying output..."
    if (-not (Test-Path $OUT_DIR)) {
        New-Item -ItemType Directory -Path $OUT_DIR | Out-Null
    }

    Copy-Item "Release\cimgui.dll" $OUT_DIR -Force
    Copy-Item "Release\cimgui.lib" $OUT_DIR -Force

    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "Build complete!" -ForegroundColor Green
    Write-Host "Output: $OUT_DIR\cimgui.dll" -ForegroundColor Green
    Write-Host "Output: $OUT_DIR\cimgui.lib" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
}
finally {
    Pop-Location
}

param(
    [int]$BackendPort = 8765
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Starting AutoReview desktop dev workflow..."
Write-Host "Backend port: $BackendPort"

if (Test-Path Env:ELECTRON_RUN_AS_NODE) {
    Remove-Item Env:ELECTRON_RUN_AS_NODE
}

if (-not (Test-Path "node_modules")) {
    npm install
}

npm --workspace apps/desktop run dev

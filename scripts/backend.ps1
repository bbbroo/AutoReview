param(
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m uvicorn apps.backend.autoreview_backend.main:app --host 127.0.0.1 --port $Port

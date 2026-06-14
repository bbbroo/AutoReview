param(
    [string]$OutDir = "examples/generated_sample"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m ng_drawing_qa.cli --generate-sample $OutDir
Write-Host "Generated sample project at $OutDir"

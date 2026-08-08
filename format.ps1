$ErrorActionPreference = "Stop"

Write-Host "Formatting..."
uv run ruff format .
Write-Host ""

Write-Host "Linting..."
uv run ruff check . --fix
Write-Host ""

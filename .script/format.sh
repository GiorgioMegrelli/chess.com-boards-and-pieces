#!/usr/bin/env bash

set -e

echo "Formatting..."
uv run ruff format .
echo ""

echo "Linting..."
uv run ruff check . --fix
echo ""

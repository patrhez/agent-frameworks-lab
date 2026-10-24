#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/.uv-cache}"
export PYDANTIC_AI_NO_BANNER=1
for project in crewai autogen pydantic_ai openai_agents; do
    echo "Testing $project"
    if [[ "$project" == crewai ]]; then
        (cd "$ROOT/$project" && uv run pytest tests ../shared/tests "$@")
    else
        (cd "$ROOT/$project" && uv run pytest tests "$@")
    fi
done

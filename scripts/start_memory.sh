#!/usr/bin/env bash
# Starts the shared memory service (Cognee) on http://127.0.0.1:8765. Leave it running.
cd "$(dirname "$0")/.." || exit 1
exec uv run uvicorn memory.service:app --host 127.0.0.1 --port 8765

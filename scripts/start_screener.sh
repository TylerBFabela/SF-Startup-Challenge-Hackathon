#!/usr/bin/env bash
# Connects the Python Screener agent to Band. Needs agent_config.yaml and .env. Leave it running.
cd "$(dirname "$0")/.." || exit 1
exec uv run python -m agents.screener

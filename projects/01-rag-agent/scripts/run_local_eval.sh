#!/usr/bin/env bash
# Run the 01-rag-agent CLI against the LOCAL Ollama endpoint, never hosted.
#
# Why this exists (S1, 2026-11-21): pydantic-settings loads the CWD-relative
# .env file - including the untracked projects/01-rag-agent/.env - even when
# the operator unsets shell variables. That once sent a "local" reproduction
# to the hosted endpoint (~$0.02, recorded in the agent-loop-bounds report).
# Exported empty values beat the .env file in pydantic-settings precedence,
# and `is_hosted_active()` treats empty as unset -> the platform factory
# falls through to local Ollama.
#
# Usage (from projects/01-rag-agent):
#   scripts/run_local_eval.sh evaluate --heldout --heldout-file ... --reports-dir ...
#   scripts/run_local_eval.sh chat --verify
set -euo pipefail
export LLM_API_KEY=
export LLM_BASE_URL=
exec uv run python -m rag_agent.cli "$@"

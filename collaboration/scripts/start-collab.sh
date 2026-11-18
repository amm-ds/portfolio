#!/usr/bin/env bash
# Launch Claude Code and Kimi Code side by side from the repository root.
# Override either command with CLAUDE_CMD or KIMI_CMD if the binaries use
# different names on this machine.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SESSION="portfolio-collab"
CLAUDE_CMD="${CLAUDE_CMD:-claude}"
KIMI_CMD="${KIMI_CMD:-kimi}"

usage() {
  cat <<'MSG'
Usage: start-collab.sh [--print]

Launches Claude Code and Kimi Code from the repository root.
Uses tmux when available; otherwise prints the exact commands to run.

Environment:
  CLAUDE_CMD  Claude Code command name or launch command
  KIMI_CMD    Kimi Code command name or launch command
MSG
}

print_commands() {
  printf 'Left pane:\n  cd %q && %s\n\n' "$ROOT" "$CLAUDE_CMD"
  printf 'Right pane:\n  cd %q && %s\n' "$ROOT" "$KIMI_CMD"
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--print" ]]; then
  print_commands
  exit 0
fi

if [[ -n "${1:-}" ]]; then
  usage >&2
  exit 2
fi

if ! command -v "$CLAUDE_CMD" >/dev/null 2>&1; then
  printf 'Claude Code command not found: %s\nSet CLAUDE_CMD to the correct command.\n' "$CLAUDE_CMD" >&2
  exit 1
fi

if ! command -v "$KIMI_CMD" >/dev/null 2>&1; then
  printf 'Kimi Code command not found: %s\nSet KIMI_CMD to the correct command.\n' "$KIMI_CMD" >&2
  exit 1
fi

if ! command -v tmux >/dev/null 2>&1; then
  cat >&2 <<'MSG'
tmux is not installed, so the side-by-side launcher cannot open panes here.
Install tmux, or run these commands in two adjacent terminals:
MSG
  print_commands >&2
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  exec tmux attach -t "$SESSION"
fi

tmux new-session -d -s "$SESSION" -c "$ROOT"
tmux send-keys -t "$SESSION:0.0" "$CLAUDE_CMD" C-m
tmux split-window -h -t "$SESSION:0" -c "$ROOT"
tmux send-keys -t "$SESSION:0.1" "$KIMI_CMD" C-m
tmux select-pane -t "$SESSION:0.0"
exec tmux attach -t "$SESSION"

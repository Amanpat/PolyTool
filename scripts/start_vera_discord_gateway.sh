#!/usr/bin/env bash
# start_vera_discord_gateway.sh
# Operator script: starts the vera-hermes-agent Discord gateway in a tmux session.
# Run from WSL: bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/start_vera_discord_gateway.sh
# Or from Windows: wsl bash -lc "bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/start_vera_discord_gateway.sh"

set -euo pipefail

SESSION="vera-hermes-discord"
PROFILE="vera-hermes-agent"
LOG_DIR="/home/patel/.hermes/profiles/${PROFILE}/logs"

# Kill any stale session
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "[start_vera_discord_gateway] Session '$SESSION' already exists — killing stale session"
  tmux kill-session -t "$SESSION"
fi

# Start gateway in a new detached tmux session
echo "[start_vera_discord_gateway] Starting hermes -p ${PROFILE} gateway run in tmux session '${SESSION}'"
tmux new-session -d -s "$SESSION" "hermes -p ${PROFILE} gateway run 2>&1 | tee ${LOG_DIR}/gateway.log"

echo "[start_vera_discord_gateway] Gateway started. To attach: tmux attach -t ${SESSION}"
echo "[start_vera_discord_gateway] To view logs: tail -f ${LOG_DIR}/gateway.log"
echo "[start_vera_discord_gateway] To stop: tmux kill-session -t ${SESSION}"

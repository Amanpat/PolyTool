#!/usr/bin/env bash
# Healthcheck for vera-hermes-agent operator instance.
# Run from Windows: wsl bash -lc "bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/vera_hermes_healthcheck.sh"
# Or from WSL directly: bash scripts/vera_hermes_healthcheck.sh
#
# Exit 0 = instance is up and responding. Exit 1 = failed.

set -euo pipefail

PROFILE="vera-hermes-agent"
EXPECTED="vera hermes agent ready"

echo "=== vera-hermes-agent healthcheck ==="
echo ""

# 1. Verify binary
echo "1. Hermes binary..."
HERMES_VERSION=$(hermes --version 2>&1 | head -1)
echo "   $HERMES_VERSION"

# 2. Verify profile exists
echo "2. Profile presence..."
PROFILE_PATH=$(hermes profile list 2>&1 | grep "$PROFILE" | head -1)
if [ -z "$PROFILE_PATH" ]; then
  echo "   FAIL: profile '$PROFILE' not found in 'hermes profile list'"
  exit 1
fi
echo "   OK — $PROFILE found"

# 3. Verify SOUL.md has read-only scope (not empty template)
echo "3. SOUL.md scope declaration..."
SOUL_PATH="/home/patel/.hermes/profiles/$PROFILE/SOUL.md"
if grep -q "Read-only operator" "$SOUL_PATH" 2>/dev/null; then
  echo "   OK — read-only scope declared"
else
  echo "   WARN: SOUL.md missing read-only scope declaration"
fi

# 4. Confirm no gateway running (expected for operator baseline)
echo "4. Gateway state..."
GW_STATUS=$(hermes -p "$PROFILE" gateway status 2>&1 | head -1)
echo "   $GW_STATUS (expected: stopped)"

# 5. Confirm no cron jobs
echo "5. Scheduled jobs..."
CRON_OUT=$(hermes -p "$PROFILE" cron list 2>&1 | head -1)
echo "   $CRON_OUT (expected: none)"

# 6. Live chat round-trip (provider-dependent — quota exhaustion is WARN not FAIL)
echo "6. Chat round-trip..."
REPLY=$(vera-hermes-agent chat -Q -q "Reply with exactly: $EXPECTED" 2>&1 | tail -1) || true
if [ "$REPLY" = "$EXPECTED" ]; then
  echo "   OK — got: $REPLY"
elif echo "$REPLY" | grep -q "429\|session usage limit\|quota"; then
  echo "   WARN — LLM provider quota exhausted (profile/config OK; run 'hermes auth list' for reset timer)"
  echo ""
  echo "=== PARTIAL PASS — profile healthy; LLM provider quota exhausted ==="
  exit 0
else
  echo "   FAIL — expected '$EXPECTED', got: $REPLY"
  exit 1
fi

echo ""
echo "=== PASS — vera-hermes-agent is healthy ==="

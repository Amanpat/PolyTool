#!/usr/bin/env bash
# Validates the command patterns used in the polytool-dev-logs SKILL.md.
# Run from WSL: bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/test_vera_dev_logs_commands.sh
#
# Each test validates one command pattern the skill uses.

set -uo pipefail

DEV_LOGS_DIR="/mnt/d/Coding Projects/Polymarket/PolyTool/docs/dev_logs"

echo "=== polytool-dev-logs command pattern tests ==="
echo ""

echo "1. Path accessible?"
if ls "$DEV_LOGS_DIR"/*.md >/dev/null 2>&1; then
    COUNT=$(ls "$DEV_LOGS_DIR"/*.md | wc -l)
    echo "   PASS — $COUNT files found"
else
    echo "   FAIL — path not accessible: $DEV_LOGS_DIR"
    exit 1
fi

echo ""
echo "2. Latest 5 logs (filename only):"
ls -t "$DEV_LOGS_DIR"/*.md | head -5 | xargs -I{} basename {}
echo "   PASS"

echo ""
echo "3. Keyword filter by filename — 'ris':"
MATCHES=$(ls -t "$DEV_LOGS_DIR"/*.md | grep -i 'ris' | head -5 | xargs -I{} basename {})
echo "$MATCHES"
if [ -n "$MATCHES" ]; then
    echo "   PASS"
else
    echo "   WARN — no ris matches (unexpected for this repo)"
fi

echo ""
echo "4. Keyword filter by filename — 'hermes':"
MATCHES=$(ls -t "$DEV_LOGS_DIR"/*.md | grep -i 'hermes' | head -5 | xargs -I{} basename {})
echo "$MATCHES"
if [ -n "$MATCHES" ]; then
    echo "   PASS"
else
    echo "   WARN — no hermes matches (unexpected for this repo)"
fi

echo ""
echo "5. Date filter — 2026-04-23:"
DATED=$(ls "$DEV_LOGS_DIR"/2026-04-23_*.md 2>/dev/null | xargs -I{} basename {} | head -5)
if [ -n "$DATED" ]; then
    echo "$DATED"
    echo "   PASS"
else
    echo "   WARN — no files for 2026-04-23"
fi

echo ""
echo "6. Keyword in file content — 'hermes':"
CONTENT_HITS=$(grep -ril 'hermes' "$DEV_LOGS_DIR"/*.md 2>/dev/null | xargs -I{} basename {} | sort -r | head -5)
if [ -n "$CONTENT_HITS" ]; then
    echo "$CONTENT_HITS"
    echo "   PASS"
else
    echo "   WARN — no content matches for 'hermes'"
fi

echo ""
echo "7. Count by date:"
ls "$DEV_LOGS_DIR"/*.md | sed 's|.*/||' | cut -d_ -f1 | sort | uniq -c | sort -rn | head -8
echo "   PASS"

echo ""
echo "8. Read header of most recent file (first 15 lines):"
MOST_RECENT=$(ls -t "$DEV_LOGS_DIR"/*.md | head -1)
head -15 "$MOST_RECENT"
echo "   PASS — read $(basename "$MOST_RECENT")"

echo ""
echo "=== All command pattern tests complete ==="

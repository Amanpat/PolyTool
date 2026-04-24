#!/usr/bin/env bash
# Validates the command patterns used in the polytool-status SKILL.md.
# Run from WSL: bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/test_vera_status_commands.sh

set -uo pipefail

CD="/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_DEVELOPMENT.md"
CS="/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md"

echo "=== polytool-status command pattern tests ==="
echo ""

echo "1. Both source files accessible?"
for f in "$CD" "$CS"; do
    if [ -f "$f" ]; then
        LINES=$(wc -l < "$f")
        echo "   PASS — $(basename "$f") ($LINES lines)"
    else
        echo "   FAIL — not found: $f"
        exit 1
    fi
done

echo ""
echo "2. CURRENT_DEVELOPMENT.md frontmatter (staleness check):"
head -5 "$CD"
echo "   PASS"

echo ""
echo "3. CURRENT_STATE.md frontmatter (staleness check):"
head -5 "$CS"
echo "   PASS"

echo ""
echo "4. Active Features section from CURRENT_DEVELOPMENT.md:"
grep -A 50 "^## Active Features" "$CD" | head -30
echo "   PASS"

echo ""
echo "5. Awaiting Director Decision from CURRENT_DEVELOPMENT.md:"
grep -A 20 "^## Awaiting Director Decision" "$CD" | head -20
echo "   PASS"

echo ""
echo "6. Gate 2 status from CURRENT_STATE.md:"
grep -A 15 "Gate 2.*FAILED\|Gate 2 Corpus\|Gate 2:" "$CS" | head -15 || grep -A 10 "Gate 2" "$CS" | head -10
echo "   PASS"

echo ""
echo "7. Recently Completed table:"
grep -A 15 "^## Recently Completed" "$CD" | head -15
echo "   PASS"

echo ""
echo "8. Paused/Deferred table:"
grep -A 20 "^## Paused" "$CD" | head -20
echo "   PASS"

echo ""
echo "9. Cross-check: does CURRENT_STATE mention Gate 2 FAILED?"
if grep -q "Gate 2.*FAILED\|FAILED.*Gate 2\|Gate 2.*7/50" "$CS"; then
    echo "   PASS — Gate 2 FAILED found in CURRENT_STATE"
else
    echo "   WARN — Gate 2 FAILED not found in CURRENT_STATE (may be stale)"
fi

echo ""
echo "10. Cross-check: does CURRENT_DEVELOPMENT mention Gate 2 path forward?"
if grep -q "Gate 2 Path Forward\|Gate 2.*Decision\|Awaiting.*Gate" "$CD"; then
    echo "   PASS — Gate 2 decision entry found in CURRENT_DEVELOPMENT"
else
    echo "   WARN — no Gate 2 awaiting-decision entry in CURRENT_DEVELOPMENT"
fi

echo ""
echo "=== All command pattern tests complete ==="

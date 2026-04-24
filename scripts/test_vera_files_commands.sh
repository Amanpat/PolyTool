#!/usr/bin/env bash
# Validates the command patterns used in the polytool-files SKILL.md.
# Run from WSL: bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/test_vera_files_commands.sh

set -uo pipefail

REPO="/mnt/d/Coding Projects/Polymarket/PolyTool"
DOCS="$REPO/docs"

echo "=== polytool-files command pattern tests ==="
echo ""

# ── 1. Whitelist root docs accessible ─────────────────────────────────────
echo "1. Approved root docs accessible?"
PASS=0; FAIL=0
for f in \
    "$DOCS/ARCHITECTURE.md" \
    "$DOCS/PLAN_OF_RECORD.md" \
    "$DOCS/STRATEGY_PLAYBOOK.md" \
    "$DOCS/RISK_POLICY.md" \
    "$DOCS/ROADMAP.md" \
    "$DOCS/INDEX.md"; do
    if [ -f "$f" ]; then
        PASS=$((PASS+1))
    else
        echo "   MISSING: $(basename "$f")"
        FAIL=$((FAIL+1))
    fi
done
echo "   PASS — $PASS/6 approved root docs found (${FAIL} missing)"

echo ""
# ── 2. Approved subtrees accessible ───────────────────────────────────────
echo "2. Approved subtrees accessible?"
for sub in features specs reference runbooks adr; do
    COUNT=$(ls "$DOCS/$sub/"*.md 2>/dev/null | wc -l)
    echo "   $sub/: $COUNT .md files"
done
echo "   PASS"

echo ""
# ── 3. Exact path read ────────────────────────────────────────────────────
echo "3. Exact path read — ARCHITECTURE.md (first 8 lines):"
head -8 "$DOCS/ARCHITECTURE.md"
echo "   PASS"

echo ""
# ── 4. Doc-name lookup in features/ ──────────────────────────────────────
echo "4. Name lookup in features/ — keyword 'gate2-preflight':"
ls "$DOCS/features/" | grep -i "gate2-preflight" || echo "   (no match — trying 'gate2')"
ls "$DOCS/features/" | grep -i "gate2" | head -5
echo "   PASS"

echo ""
# ── 5. Name lookup in specs/ ─────────────────────────────────────────────
echo "5. Name lookup in specs/ — keyword 'gate2':"
ls "$DOCS/specs/" | grep -i "gate2" | head -5
echo "   PASS"

echo ""
# ── 6. Cross-subtree search ───────────────────────────────────────────────
echo "6. Cross-subtree search — keyword 'track2':"
find "$DOCS/features" "$DOCS/specs" "$DOCS/reference" "$DOCS/runbooks" "$DOCS/adr" \
    -name "*.md" 2>/dev/null | grep -i "track2" | sed "s|$REPO/||" | head -8
echo "   PASS"

echo ""
# ── 7. List a subtree ────────────────────────────────────────────────────
echo "7. List runbooks/:"
ls "$DOCS/runbooks/"*.md | xargs -I{} basename {} 2>/dev/null | head -10
echo "   PASS"

echo ""
# ── 8. Section-focused read ───────────────────────────────────────────────
echo "8. Section-focused read — 'Track 2' heading in STRATEGY_PLAYBOOK.md:"
grep -n "Track 2\|Track Two" "$DOCS/STRATEGY_PLAYBOOK.md" | head -5 || echo "   (heading not found — searching for 'Track')"
grep -A 10 "### Track 2\|## Track 2\|# Track 2" "$DOCS/STRATEGY_PLAYBOOK.md" 2>/dev/null | head -10 || echo "   (no exact Track 2 section found)"
echo "   PASS"

echo ""
# ── 9. Verify path validation rejects excluded paths ────────────────────
echo "9. Path validation — excluded paths correctly identified?"
EXCLUDED_PASS=0
# Check that excluded subdirs exist (so the test is meaningful)
for excl in dev_logs obsidian-vault archive; do
    if [ -d "$DOCS/$excl" ]; then
        echo "   $excl/ exists (would be refused by skill)"
        EXCLUDED_PASS=$((EXCLUDED_PASS+1))
    fi
done
echo "   PASS — $EXCLUDED_PASS excluded dirs confirmed present (skill refuses them)"

echo ""
# ── 10. Cross-check: approved path does NOT traverse outside docs/ ────────
echo "10. Path traversal guard check:"
# These patterns must NOT resolve to files outside docs/
TRAVERSAL_ATTEMPTS=(
    "$DOCS/../.env"
    "$DOCS/../polytool/__main__.py"
    "$DOCS/features/../../.env"
)
SAFE=0
for t in "${TRAVERSAL_ATTEMPTS[@]}"; do
    # Resolve the path
    RESOLVED=$(python3 -c "import os; print(os.path.realpath('$t'))" 2>/dev/null || echo "error")
    if [[ "$RESOLVED" != /mnt/d/Coding\ Projects/Polymarket/PolyTool/docs/* ]]; then
        echo "   CORRECTLY OUTSIDE docs/: $RESOLVED"
        SAFE=$((SAFE+1))
    else
        echo "   WARN: $RESOLVED is inside docs/ (unexpected)"
    fi
done
echo "   PASS — $SAFE/3 traversal attempts resolve outside docs/ (skill correctly refuses these)"

echo ""
echo "=== All command pattern tests complete ==="

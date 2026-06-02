#!/usr/bin/env python3
"""
validate-vault-frontmatter.py — Validate YAML frontmatter in the PolyTool Obsidian vault.

Walks all .md files under the vault root and checks each against the frontmatter schema
defined in claude-memory/spec/vault-redesign-spec.md.

Skips legacy zones: Claude Desktop/, PolyTool/, 10-Session-Notes/, Templates/, ris-mirror/

Usage:
    python validate-vault-frontmatter.py [--vault-root PATH] [--report-path PATH]

Options:
    --vault-root PATH    Path to the vault root directory.
                         Default: ../obsidian-vault relative to this script.
    --report-path PATH   Path for the output report markdown file.
                         Default: <vault-root>/claude-memory/work-packets/
                                  2026-05-23-frontmatter-validation-report.md

Exit codes:
    0 — all checked files pass validation
    1 — one or more validation failures found
    2 — vault root does not exist or other fatal error
"""

import argparse
import sys
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ---------------------------------------------------------------------------
# Schema constants (from vault-redesign-spec-v1.md)
# ---------------------------------------------------------------------------

SKIP_DIRS = frozenset({
    "ris-mirror",
    "legacy",          # legacy/ isolates pre-redesign zones; skip the whole subtree
    "Claude Desktop",  # retained for safety if folder ever returns to vault root
    "PolyTool",
    "10-Session-Notes",
    "Templates",
    ".obsidian",
    ".smart-env",
    # repo-docs is now validated with a separate schema (see validate_repo_docs_file)
})

REPO_DOCS_DIR = "repo-docs"

VALID_TYPES = frozenset({
    "spec", "adr", "decision", "index", "log", "research", "concept",
    "entity", "mirror", "session_note", "work_packet", "prompt",
    "conversation", "idea", "reference",
})

VALID_STATUSES = frozenset({"draft", "active", "superseded", "archived"})

VALID_SOURCE_ZONES = frozenset({"repo", "claude_memory", "ris_mirror"})

# Spec-defined enum; "active" is NOT valid despite appearing in some skeleton examples
VALID_LIFECYCLES = frozenset({"draft", "reviewed", "verified", "stale", "archived"})

UNIVERSAL_REQUIRED = ("title", "type", "status", "source_zone", "last_updated", "lifecycle")

# Type-specific required frontmatter fields (subset — omits body-section-only requirements)
TYPE_SPECIFIC_REQUIRED: dict[str, tuple[str, ...]] = {
    "adr":          ("adr_number", "decision"),
    "decision":     ("decided_at", "decided_by"),
    "mirror":       ("mirror_of", "last_synced", "chroma_partition"),
    "session_note": ("session_date", "participants"),
    "spec":         ("spec_version", "spec_status"),
    "work_packet":  ("target_agent", "acceptance_criteria"),
}

VALID_SPEC_STATUSES = frozenset({"draft", "accepted", "implemented", "deprecated"})
VALID_CHROMA_PARTITIONS = frozenset({"user_data", "external_knowledge", "research", "signals"})

REPORT_RELATIVE = "claude-memory/work-packets/2026-05-23-frontmatter-validation-report.md"

# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> dict | None:
    """Return parsed frontmatter dict or None if absent/unparseable."""
    if not text.startswith("---"):
        return None
    second = text.find("\n---", 3)
    if second == -1:
        return None
    fm_text = text[3:second].strip()
    if not fm_text:
        return {}
    if HAS_YAML:
        try:
            result = yaml.safe_load(fm_text)
            return result if isinstance(result, dict) else {}
        except yaml.YAMLError:
            return None
    # Fallback: simple line-by-line parsing (no nested YAML support)
    result: dict = {}
    for line in fm_text.splitlines():
        if ": " in line:
            k, _, v = line.partition(": ")
            result[k.strip()] = v.strip().strip('"\'')
    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_file(path: Path) -> list[str]:
    """Return list of error strings. Empty list = pass."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return [f"READ_ERROR: {exc}"]

    fm = parse_frontmatter(text)
    if fm is None:
        return ["NO_FRONTMATTER: file has no valid YAML frontmatter block"]

    errors: list[str] = []

    # Universal required fields
    for field in UNIVERSAL_REQUIRED:
        val = fm.get(field)
        if val is None or str(val).strip() == "":
            errors.append(f"MISSING_REQUIRED: '{field}' is required")

    # Enum validation
    if "type" in fm and fm["type"] not in VALID_TYPES:
        errors.append(
            f"INVALID_ENUM: type='{fm['type']}' — valid: {', '.join(sorted(VALID_TYPES))}"
        )

    if "status" in fm and fm["status"] not in VALID_STATUSES:
        errors.append(
            f"INVALID_ENUM: status='{fm['status']}' — valid: {', '.join(sorted(VALID_STATUSES))}"
        )

    if "source_zone" in fm and fm["source_zone"] not in VALID_SOURCE_ZONES:
        errors.append(
            f"INVALID_ENUM: source_zone='{fm['source_zone']}' — valid: {', '.join(sorted(VALID_SOURCE_ZONES))}"
        )

    if "lifecycle" in fm and fm["lifecycle"] not in VALID_LIFECYCLES:
        errors.append(
            f"INVALID_ENUM: lifecycle='{fm['lifecycle']}' — valid: {', '.join(sorted(VALID_LIFECYCLES))}"
        )

    # Type-specific required fields
    doc_type = str(fm.get("type", ""))
    if doc_type in TYPE_SPECIFIC_REQUIRED:
        for field in TYPE_SPECIFIC_REQUIRED[doc_type]:
            val = fm.get(field)
            if val is None or str(val).strip() == "" or val == [] or val == "[]":
                errors.append(
                    f"MISSING_TYPE_FIELD: '{field}' required for type='{doc_type}'"
                )

    # Additional enum checks for type-specific fields
    if doc_type == "spec" and "spec_status" in fm:
        if fm["spec_status"] not in VALID_SPEC_STATUSES:
            errors.append(
                f"INVALID_ENUM: spec_status='{fm['spec_status']}' — valid: {', '.join(sorted(VALID_SPEC_STATUSES))}"
            )

    if doc_type == "mirror" and "chroma_partition" in fm:
        if fm["chroma_partition"] not in VALID_CHROMA_PARTITIONS:
            errors.append(
                f"INVALID_ENUM: chroma_partition='{fm['chroma_partition']}' — valid: {', '.join(sorted(VALID_CHROMA_PARTITIONS))}"
            )

    return errors


# ---------------------------------------------------------------------------
# Repo-docs validation (Zone A schema)
# ---------------------------------------------------------------------------

def validate_repo_docs_file(path: Path) -> list[str]:
    """Validate a repo-docs/ file against Zone A schema rules."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return [f"READ_ERROR: {exc}"]

    fm = parse_frontmatter(text)
    if fm is None:
        return ["NO_FRONTMATTER: file has no valid YAML frontmatter block"]

    errors: list[str] = []

    # source_zone must be "repo"
    sz = fm.get("source_zone", "")
    if sz != "repo":
        errors.append(f"REPO_DOCS: source_zone='{sz}' — must be 'repo'")

    # mirror_of must be set and non-empty
    mo = fm.get("mirror_of", "")
    if not mo or str(mo).strip() == "":
        errors.append("REPO_DOCS: mirror_of is missing or empty — must point to repo source path")

    # lifecycle must be "reviewed"
    lc = fm.get("lifecycle", "")
    if lc != "reviewed":
        errors.append(f"REPO_DOCS: lifecycle='{lc}' — must be 'reviewed' for Zone A files")

    return errors


# ---------------------------------------------------------------------------
# Directory filtering
# ---------------------------------------------------------------------------

def should_skip(path: Path, vault_root: Path) -> bool:
    try:
        parts = path.relative_to(vault_root).parts
    except ValueError:
        return False
    return bool(parts) and parts[0] in SKIP_DIRS


def is_repo_docs(path: Path, vault_root: Path) -> bool:
    try:
        parts = path.relative_to(vault_root).parts
    except ValueError:
        return False
    return bool(parts) and parts[0] == REPO_DOCS_DIR


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------

def write_report(
    report_path: Path,
    vault_root: Path,
    results: list[tuple[Path, list[str]]],
    skipped: list[Path],
) -> None:
    passing = [(p, e) for p, e in results if not e]
    failing = [(p, e) for p, e in results if e]

    today = "2026-05-23"
    lines: list[str] = [
        "---",
        "title: Frontmatter Validation Report 2026-05-23",
        "type: work_packet",
        "status: active",
        "source_zone: claude_memory",
        f"last_updated: {today}",
        "lifecycle: reviewed",
        "target_agent: claude-code",
        "acceptance_criteria:",
        "  - All new vault files pass frontmatter validation",
        "  - Zero INVALID_ENUM or MISSING_REQUIRED errors in new vault zones",
        "  - All repo-docs/ files pass Zone A schema (source_zone=repo, mirror_of set, lifecycle=reviewed)",
        "---",
        "",
        "# Frontmatter Validation Report",
        "",
        f"**Generated:** {today}  ",
        f"**Vault root:** `{vault_root}`  ",
        f"**Files checked:** {len(results)} (claude-memory + repo-docs)  ",
        f"**Skipped (legacy zones):** {len(skipped)}  ",
        f"**Passing:** {len(passing)}  ",
        f"**Failing:** {len(failing)}  ",
        "",
        "---",
        "",
    ]

    if failing:
        lines += [
            f"## Failures ({len(failing)} files)",
            "",
            "| File | Error |",
            "|------|-------|",
        ]
        for path, errors in sorted(failing, key=lambda x: str(x[0])):
            rel = path.relative_to(vault_root)
            for err in errors:
                safe_err = err.replace("|", "\\|")
                lines.append(f"| `{rel}` | {safe_err} |")
        lines.append("")
    else:
        lines += ["## Failures", "", "None — all files pass.", ""]

    lines += [
        f"## Passing Files ({len(passing)})",
        "",
    ]
    for path, _ in sorted(passing, key=lambda x: str(x[0])):
        rel = path.relative_to(vault_root)
        lines.append(f"- `{rel}`")

    lines += [
        "",
        f"## Skipped Files ({len(skipped)})",
        "",
        f"Skipped directories: {', '.join(f'`{d}/`' for d in sorted(SKIP_DIRS))}",
        "",
        "## Connections",
        "",
        "- [[claude-memory/spec/vault-redesign-spec]]",
        "- [[claude-memory/work-packets/2026-05-23-vault-redesign-execution-report]]",
        "",
    ]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="validate-vault-frontmatter",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--vault-root",
        type=Path,
        default=Path(__file__).parent.parent / "obsidian-vault",
        metavar="PATH",
        help="Vault root directory (default: ../obsidian-vault relative to this script)",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Output report path "
            f"(default: <vault-root>/{REPORT_RELATIVE})"
        ),
    )
    args = parser.parse_args()

    vault_root: Path = args.vault_root.resolve()
    if not vault_root.is_dir():
        print(f"Error: vault root does not exist or is not a directory: {vault_root}", file=sys.stderr)
        return 2

    report_path: Path = (
        args.report_path if args.report_path else vault_root / REPORT_RELATIVE
    )

    all_md = sorted(vault_root.rglob("*.md"))
    results: list[tuple[Path, list[str]]] = []
    skipped: list[Path] = []

    for f in all_md:
        if should_skip(f, vault_root):
            skipped.append(f)
        elif is_repo_docs(f, vault_root):
            results.append((f, validate_repo_docs_file(f)))
        else:
            results.append((f, validate_file(f)))

    passing = [r for r in results if not r[1]]
    failing = [r for r in results if r[1]]

    write_report(report_path, vault_root, results, skipped)

    print(
        f"Validation: {len(results)} checked, {len(passing)} pass, "
        f"{len(failing)} fail, {len(skipped)} skipped (legacy)"
    )
    print(f"Report: {report_path}")

    if failing:
        print(f"\nFailures ({len(failing)} files):")
        for path, errors in sorted(failing, key=lambda x: str(x[0])):
            rel = path.relative_to(vault_root)
            print(f"  {rel}")
            for err in errors:
                print(f"    {err}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
fix-wikilinks.py — Scan claude-memory/ and vault root .md files, resolve broken wikilinks.

Auto-fixes unambiguous broken links in place.
Writes manual-review work packet for ambiguous/unresolvable links.

Usage:
    python docs/scripts/fix-wikilinks.py [--dry-run] [--vault-root PATH]
"""

import argparse
import pathlib
import re
import sys
from collections import defaultdict
from datetime import date

# Force UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VAULT_ROOT_DEFAULT = pathlib.Path(__file__).parent.parent / "obsidian-vault"

# Zones to SCAN for wikilinks (files that may contain broken links)
SCAN_ZONES = {"claude-memory", "root"}

# Zones to include in the FILE CATALOG (targets that links can point to)
CATALOG_ZONES = {"claude-memory", "repo-docs", "ris-mirror", "root", "Templates"}

# Legacy zone prefix remappings: old prefix → new zone prefix
LEGACY_REMAPS = {
    "09-Decisions/": "claude-memory/decisions/",
    "08-Research/": "claude-memory/research/",
    "11-Prompt-Archive/": "claude-memory/prompts/",
    "10-Session-Notes/": "claude-memory/session-notes/",
    "12-Ideas/": "claude-memory/ideas/",
    "PolyTool/": "claude-memory/research/",
    "Claude Desktop/09-Decisions/": "claude-memory/decisions/",
    "Claude Desktop/08-Research/": "claude-memory/research/",
    "Claude Desktop/11-Prompt-Archive/": "claude-memory/prompts/",
    "Claude Desktop/10-Session-Notes/": "claude-memory/session-notes/",
    "01-Architecture/": "claude-memory/research/",
    "02-Strategy/": "claude-memory/research/",
    "03-Execution/": "claude-memory/research/",
    "04-Risk/": "claude-memory/research/",
    "05-Research/": "claude-memory/research/",
    "06-Ops/": "claude-memory/research/",
    "07-Ideas/": "claude-memory/ideas/",
}

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def slug_normalize(s: str) -> str:
    """Normalize to lowercase, spaces/underscores → hyphens, strip leading/trailing hyphens."""
    s = s.lower().replace(" ", "-").replace("_", "-")
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def build_file_catalog(vault_root: pathlib.Path) -> dict[str, list[pathlib.Path]]:
    """
    Build a catalog mapping normalized slugs to file paths.
    Returns dict: slug → [list of matching paths] (multiple = ambiguous).
    """
    catalog: dict[str, list[pathlib.Path]] = defaultdict(list)

    for f in vault_root.rglob("*.md"):
        rel = f.relative_to(vault_root)
        parts = rel.parts
        zone = parts[0] if len(parts) > 1 else "root"

        if zone not in CATALOG_ZONES and zone not in {".obsidian", ".smart-env"}:
            pass  # still include in catalog for resolution attempts

        # Index by multiple keys for fuzzy matching
        stem = f.stem
        rel_str = rel.as_posix().replace(".md", "")  # e.g. claude-memory/decisions/adr-0001-...

        # Key 1: full relative path without extension
        catalog[rel_str].append(f)

        # Key 2: normalized full path slug
        norm_full = slug_normalize(rel_str)
        if norm_full != rel_str:
            catalog[norm_full].append(f)

        # Key 3: stem only (last component)
        catalog[stem].append(f)

        # Key 4: normalized stem
        norm_stem = slug_normalize(stem)
        if norm_stem != stem:
            catalog[norm_stem].append(f)

    return dict(catalog)


def parse_wikilink(raw: str) -> tuple[str, str | None, str | None]:
    """
    Parse wikilink content into (target, alias, heading).
    [[target#heading|alias]] → ("target", "alias", "heading")
    [[target|alias]] → ("target", "alias", None)
    [[target#heading]] → ("target", None, "heading")
    [[target]] → ("target", None, None)
    """
    alias = None
    heading = None
    content = raw

    if "|" in content:
        content, alias = content.rsplit("|", 1)

    if "#" in content:
        content, heading = content.split("#", 1)

    return content.strip(), alias, heading


def resolve_wikilink(
    target: str,
    source_file: pathlib.Path,
    vault_root: pathlib.Path,
    catalog: dict[str, list[pathlib.Path]],
) -> tuple[str, pathlib.Path | None, str]:
    """
    Try to resolve a wikilink target to a file path.
    Returns (status, resolved_path, note):
      status: "ok" | "auto_fixed" | "ambiguous" | "unresolved"
    """
    # Check 0: Vault-root short-name exception — [[index]], [[log]], [[CLAUDE]], [[AGENTS]], [[README]]
    # always resolve to the vault-root file regardless of how many _index.md files exist.
    if target in VAULT_ROOT_SHORT_NAMES:
        vrf = vault_root / f"{target}.md"
        if vrf.exists():
            return "ok", vrf, "vault-root short-name exception"

    # Check 1: exact match as-is
    if target in catalog:
        matches = catalog[target]
        if len(matches) == 1:
            rel = matches[0].relative_to(vault_root).as_posix().replace(".md", "")
            if rel == target:
                return "ok", matches[0], ""
            else:
                return "auto_fixed", matches[0], f"exact catalog match → {rel}"
        else:
            return "ambiguous", None, f"{len(matches)} files match '{target}'"

    # Check 2: apply legacy remaps
    for old_prefix, new_prefix in LEGACY_REMAPS.items():
        if target.startswith(old_prefix):
            remapped = new_prefix + target[len(old_prefix):]
            if remapped in catalog and len(catalog[remapped]) == 1:
                return "auto_fixed", catalog[remapped][0], f"legacy remap {old_prefix} → {new_prefix}"
            # Try without extension
            remapped_no_md = remapped.replace(".md", "")
            if remapped_no_md in catalog and len(catalog[remapped_no_md]) == 1:
                return "auto_fixed", catalog[remapped_no_md][0], f"legacy remap {old_prefix} → {new_prefix}"

    # Check 3: normalized target match
    norm_target = slug_normalize(target)
    if norm_target in catalog:
        matches = catalog[norm_target]
        if len(matches) == 1:
            return "auto_fixed", matches[0], f"slug normalization → {norm_target}"
        else:
            unique_paths = list({m.as_posix() for m in matches})
            if len(unique_paths) == 1:
                return "auto_fixed", matches[0], f"slug normalization (deduped) → {norm_target}"
            return "ambiguous", None, f"{len(unique_paths)} files match normalized '{norm_target}'"

    # Check 4: stem-only match (last path component)
    stem = pathlib.Path(target).stem
    norm_stem = slug_normalize(stem)

    if norm_stem in catalog:
        matches = catalog[norm_stem]
        # Deduplicate by path
        unique_paths = list({m.as_posix(): m for m in matches}.values())
        if len(unique_paths) == 1:
            return "auto_fixed", unique_paths[0], f"stem match '{norm_stem}'"
        # Try to disambiguate: prefer claude-memory zone
        cm_matches = [m for m in unique_paths if "claude-memory" in m.as_posix()]
        if len(cm_matches) == 1:
            return "auto_fixed", cm_matches[0], f"stem match '{norm_stem}' (preferred claude-memory zone)"
        return "ambiguous", None, f"{len(unique_paths)} files match stem '{norm_stem}': {[m.name for m in unique_paths[:3]]}"

    return "unresolved", None, f"no catalog entry for '{target}'"


def rewrite_wikilink(raw_link: str, new_target: pathlib.Path, vault_root: pathlib.Path) -> str:
    """Rewrite a wikilink to use the resolved path."""
    content, alias, heading = parse_wikilink(raw_link)
    new_rel = new_target.relative_to(vault_root).as_posix().replace(".md", "")

    new_content = new_rel
    if heading:
        new_content += f"#{heading}"
    if alias:
        new_content += f"|{alias}"
    return f"[[{new_content}]]"


VAULT_ROOT_EXEMPT = {"index.md", "log.md", "CLAUDE.md", "AGENTS.md", "README.md"}

# Short names that always resolve to the vault-root file per the Vault-Root Short-Name Exception.
# [[index]], [[log]], [[CLAUDE]], [[AGENTS]], [[README]] are valid from any zone.
VAULT_ROOT_SHORT_NAMES = {"index", "log", "CLAUDE", "AGENTS", "README"}


def collect_scan_files(vault_root: pathlib.Path) -> list[pathlib.Path]:
    """Collect .md files to scan for wikilinks."""
    files = []
    for f in vault_root.iterdir():
        if f.suffix == ".md" and f.name not in VAULT_ROOT_EXEMPT:
            files.append(f)
    for subdir in ("claude-memory", "repo-docs"):
        sd = vault_root / subdir
        if sd.exists():
            files.extend(sd.rglob("*.md"))
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description="Fix broken wikilinks in vault")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without writing")
    parser.add_argument("--vault-root", type=pathlib.Path, default=VAULT_ROOT_DEFAULT)
    args = parser.parse_args()

    vault_root = args.vault_root.resolve()
    if not vault_root.exists():
        print(f"ERROR: vault root not found: {vault_root}", file=sys.stderr)
        sys.exit(1)

    print(f"Vault root: {vault_root}")
    print(f"Dry run: {args.dry_run}")
    print()

    catalog = build_file_catalog(vault_root)
    print(f"File catalog: {len(catalog)} keys ({sum(1 for v in catalog.values() if len(v)==1)} unique, {sum(1 for v in catalog.values() if len(v)>1)} ambiguous keys)")

    scan_files = collect_scan_files(vault_root)
    print(f"Files to scan: {len(scan_files)}")
    print()

    stats = {"ok": 0, "auto_fixed": 0, "ambiguous": 0, "unresolved": 0, "files_changed": 0}
    manual_review: list[dict] = []
    auto_fixed_log: list[dict] = []

    # Regex to blank out code and comments before scanning for wikilinks
    INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
    FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
    HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

    for fpath in scan_files:
        text = fpath.read_text(encoding="utf-8-sig")
        new_text = text
        file_changed = False

        scan_text = FENCED_CODE_RE.sub(lambda m: " " * len(m.group()), text)
        scan_text = INLINE_CODE_RE.sub(lambda m: " " * len(m.group()), scan_text)
        scan_text = HTML_COMMENT_RE.sub(lambda m: " " * len(m.group()), scan_text)
        for match in WIKILINK_RE.finditer(scan_text):
            raw_link = match.group(1)
            target, alias, heading = parse_wikilink(raw_link)

            if not target:
                continue

            status, resolved, note = resolve_wikilink(target, fpath, vault_root, catalog)

            # For aliased links: resolve to check validity, but never auto-fix the display text
            if alias is not None:
                if status == "ok" or status == "auto_fixed":
                    stats["ok"] += 1
                elif status in ("ambiguous", "unresolved"):
                    stats[status] += 1
                    manual_review.append({
                        "file": fpath.relative_to(vault_root).as_posix(),
                        "wikilink": match.group(0),
                        "target": target,
                        "status": status,
                        "note": note,
                    })
                continue
            stats[status] += 1

            if status == "ok":
                pass

            elif status == "auto_fixed":
                old_full = match.group(0)
                new_full = rewrite_wikilink(raw_link, resolved, vault_root)
                if old_full != new_full:
                    new_text = new_text.replace(old_full, new_full, 1)
                    file_changed = True
                    auto_fixed_log.append({
                        "file": fpath.relative_to(vault_root).as_posix(),
                        "old": old_full,
                        "new": new_full,
                        "note": note,
                    })
                else:
                    stats["auto_fixed"] -= 1
                    stats["ok"] += 1

            elif status in ("ambiguous", "unresolved"):
                manual_review.append({
                    "file": fpath.relative_to(vault_root).as_posix(),
                    "wikilink": match.group(0),
                    "target": target,
                    "status": status,
                    "note": note,
                })

        if file_changed and not args.dry_run:
            fpath.write_text(new_text, encoding="utf-8")
            stats["files_changed"] += 1
        elif file_changed and args.dry_run:
            stats["files_changed"] += 1

    print("=== Results ===")
    print(f"  OK (already correct):   {stats['ok']}")
    print(f"  Auto-fixed:             {stats['auto_fixed']}")
    print(f"  Ambiguous (manual):     {stats['ambiguous']}")
    print(f"  Unresolved (manual):    {stats['unresolved']}")
    print(f"  Files changed:          {stats['files_changed']}")

    if auto_fixed_log:
        print(f"\nAuto-fixed links ({len(auto_fixed_log)}):")
        for entry in auto_fixed_log[:20]:
            print(f"  {entry['file']}: {entry['old']} -> {entry['new']} ({entry['note']})")
        if len(auto_fixed_log) > 20:
            print(f"  ... and {len(auto_fixed_log)-20} more")

    # Write manual review work packet
    wp_path = vault_root / "claude-memory" / "work-packets" / "2026-05-23-broken-wikilinks-manual-review.md"
    today = date.today().isoformat()

    manual_by_file: dict[str, list[dict]] = defaultdict(list)
    for entry in manual_review:
        manual_by_file[entry["file"]].append(entry)

    lines = [
        "---",
        "title: Broken Wikilinks Manual Review",
        "type: work_packet",
        "status: active",
        "source_zone: claude_memory",
        f"last_updated: {today}",
        "lifecycle: draft",
        "target_agent: human",
        "acceptance_criteria:",
        "  - All links in this file either resolved or removed",
        "---",
        "",
        "# Broken Wikilinks — Manual Review",
        "",
        f"> Generated by `docs/scripts/fix-wikilinks.py` on {today}.",
        f"> Auto-fixed: **{stats['auto_fixed']}** links across {stats['files_changed']} files.",
        f"> Requires manual resolution: **{len(manual_review)}** links ({stats['ambiguous']} ambiguous, {stats['unresolved']} unresolved).",
        "",
        "## Instructions",
        "",
        "For each link below:",
        "1. Open the source file in Obsidian.",
        "2. Find the wikilink shown.",
        "3. Replace with the correct target path, or remove if the concept was deleted/merged.",
        "4. Mark the row resolved by deleting it from this file.",
        "",
    ]

    if not manual_review:
        lines.append("_No broken wikilinks require manual review._")
    else:
        for file_path, entries in sorted(manual_by_file.items()):
            lines.append(f"## `{file_path}`")
            lines.append("")
            lines.append("| Wikilink | Status | Note |")
            lines.append("|----------|--------|------|")
            for e in entries:
                wl = e["wikilink"].replace("\n", " ").replace("[[", "\\[[").replace("]]", "\\]]").replace("|", "\\|")
                note = e["note"].replace("\n", " ").replace("|", "\\|")
                lines.append(f"| `{wl}` | {e['status']} | {note} |")
            lines.append("")

    lines.append("## Connections")
    lines.append("")
    lines.append("- [[claude-memory/work-packets/_index]]")
    lines.append("- [[index|Vault Home]]")
    lines.append("")

    if not args.dry_run:
        wp_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"\nManual review work packet written: {wp_path.relative_to(vault_root)}")
    else:
        print(f"\n[dry-run] Would write manual review work packet: {wp_path.relative_to(vault_root)}")

    return stats


if __name__ == "__main__":
    main()

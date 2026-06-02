#!/usr/bin/env python3
"""
sync-repo-docs.py — One-way sync: docs/ → docs/obsidian-vault/repo-docs/

Source (docs/) is authoritative. Mirror (repo-docs/) is the write target.
Direction is strictly one-way. Never writes to docs/.

Behaviors:
  NEW       — in docs/ but not in repo-docs/; create with full vault frontmatter
  DIVERGED  — body or non-vault frontmatter changed; update body + last_synced
  ORPHANED  — in repo-docs/ but source removed; add orphaned flag, never delete
  UNCHANGED — identical; skip

Filename normalization:
  All source filenames → lowercase, underscores/spaces → hyphens
  docs/adr/ files additionally get "adr-" prefix if not already present

Usage:
    python sync-repo-docs.py [--dry-run] [--verbose] [--vault-root PATH] [--repo-root PATH]

Exit codes:
    0 — completed (or dry-run complete)
    1 — one or more errors
    2 — fatal (required path missing)
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Fields written by the sync process; never taken from source content
VAULT_ADDED_FIELDS = frozenset({
    "source_zone", "mirror_of", "last_synced", "lifecycle", "generator",
    "orphaned", "orphaned_at",
})

# Fields that may be manually added in the vault and must be preserved on update
VAULT_MANUAL_FIELDS = frozenset({"supersedes", "superseded_by", "aliases"})

# Root-level docs/ files to sync.
# Value is the explicit vault filename override, or None to auto-normalize.
ROOT_DOCS_FILES: dict[str, "str | None"] = {
    "CURRENT_STATE.md": None,
    "ARCHITECTURE.md": None,
    "PLAN_OF_RECORD.md": None,
    "STRATEGY_PLAYBOOK.md": "overview.md",       # special: different vault name
    "ARCHITECT_CONTEXT_PACK.md": None,
    "CURRENT_DEVELOPMENT.md": None,
    "DOCS_BEST_PRACTICES.md": None,
    "INDEX.md": None,
    "KNOWLEDGE_BASE_CONVENTIONS.md": None,
    "PROJECT_CONTEXT_PUBLIC.md": None,
    "PROJECT_OVERVIEW.md": None,
    "README.md": None,
    "RISK_POLICY.md": None,
    "ROADMAP.md": None,
    "TODO.md": None,
}

# Files sourced from repo root (not docs/), with their explicit vault names
REPO_ROOT_EXTRA: dict[str, str] = {
    "CLAUDE.md": "claude-md-repo.md",
}

# Directory sync pairs: (source_subdir_in_docs, target_subdir_in_repo_docs)
DIR_MAP = [
    ("specs",              "specs"),
    ("adr",                "adrs"),
    ("features",           "features"),
    ("dev_logs",           "dev_logs"),
    ("runbooks",           "runbooks"),
    ("reference",          "reference"),
    ("external_knowledge", "external_knowledge"),
]

GENERATOR   = "repo-sync"
SOURCE_ZONE = "repo"
LIFECYCLE   = "reviewed"

ORPHAN_WARNING = (
    "> [!WARNING] Orphaned mirror — "
    "source file no longer exists in the repo. Content may be outdated.\n\n"
)

# ---------------------------------------------------------------------------
# Filename normalization
# ---------------------------------------------------------------------------

def normalize_name(src_name: str, add_adr_prefix: bool = False) -> str:
    """Convert source filename to vault mirror filename (lowercase-kebab)."""
    name = src_name.lower().replace("_", "-").replace(" ", "-")
    if add_adr_prefix and not name.startswith("adr-"):
        name = "adr-" + name
    return name


# ---------------------------------------------------------------------------
# Frontmatter parsing and serialization
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> "tuple[dict, str]":
    """Return (frontmatter_dict, body_text). Body excludes the frontmatter block."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_raw = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")

    if not fm_raw:
        return {}, body

    if HAS_YAML:
        try:
            result = yaml.safe_load(fm_raw)
            if isinstance(result, dict):
                return result, body
        except yaml.YAMLError:
            pass

    # Fallback: simple line-by-line (no nested YAML)
    result: dict = {}
    for line in fm_raw.splitlines():
        if ": " in line:
            k, _, v = line.partition(": ")
            result[k.strip()] = v.strip().strip("\"'")
    return result, body


def render_frontmatter(fm: dict) -> str:
    """Render frontmatter dict to YAML string (no --- delimiters)."""
    if HAS_YAML:
        return yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    # Fallback: simple serialization
    lines: list[str] = []
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {str(v).lower()}")
        else:
            val = str(v)
            if any(c in val for c in ":#{}[]|>&*!,?") or val.startswith(("-", "'")):
                lines.append(f'{k}: "{val}"')
            else:
                lines.append(f"{k}: {val}")
    return "\n".join(lines) + "\n"


def assemble_file(fm: dict, body: str) -> str:
    """Combine frontmatter dict and body into a complete file string."""
    fm_text = render_frontmatter(fm)
    return f"---\n{fm_text}---\n\n{body}"


# ---------------------------------------------------------------------------
# Vault frontmatter construction
# ---------------------------------------------------------------------------

_TYPE_FROM_DIR = {
    "adr":              "adr",
    "specs":            "spec",
    "features":         "reference",
    "dev_logs":         "session_note",
    "runbooks":         "reference",
    "reference":        "reference",
    "external_knowledge": "research",
}


def infer_type(source_path: Path) -> str:
    """Infer vault type from source file path."""
    for part in source_path.parts:
        if part in _TYPE_FROM_DIR:
            return _TYPE_FROM_DIR[part]
    name = source_path.stem.lower()
    if name.startswith("spec-") or name.startswith("spec_"):
        return "spec"
    if name.startswith("adr-") or re.match(r"^\d{4}-", source_path.name):
        return "adr"
    return "reference"


def derive_title(source_path: Path, source_fm: dict) -> str:
    """Get title from source frontmatter or derive from filename."""
    if source_fm.get("title"):
        return str(source_fm["title"])
    stem = source_path.stem
    # Strip leading SPEC-/ADR-/FEATURE- prefix
    stem = re.sub(r"^(SPEC|ADR|FEATURE)-?", "", stem, flags=re.IGNORECASE)
    # Strip leading YYYY-MM-DD date in dev_logs
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}[-_]", "", stem)
    # Strip leading 4-digit number (ADR/SPEC numbering)
    stem = re.sub(r"^\d{4}-", "", stem)
    return stem.replace("-", " ").replace("_", " ").title()


def make_vault_fm(
    *,
    title: str,
    doc_type: str,
    mirror_of: str,
    now_iso: str,
    source_fm: dict,
    existing_vault_fm: "dict | None" = None,
) -> dict:
    """Build ordered vault frontmatter for a mirror file."""
    fm: dict = {}

    # Required fields in logical display order
    fm["title"] = source_fm.get("title") or title
    fm["type"]   = source_fm.get("type")   or doc_type
    fm["status"] = source_fm.get("status") or "active"

    # Other source-defined non-vault fields (e.g. spec_version, adr_number)
    skip = VAULT_ADDED_FIELDS | VAULT_MANUAL_FIELDS | {"title", "type", "status"}
    for k, v in source_fm.items():
        if k not in skip:
            fm[k] = v

    # Vault-injected fields
    fm["source_zone"] = SOURCE_ZONE
    fm["mirror_of"]   = mirror_of
    fm["last_synced"] = now_iso
    fm["lifecycle"]   = LIFECYCLE
    fm["generator"]   = GENERATOR

    # Preserve manually-added vault fields from existing mirror
    if existing_vault_fm:
        for field in VAULT_MANUAL_FIELDS:
            if field in existing_vault_fm:
                fm[field] = existing_vault_fm[field]
        if existing_vault_fm.get("orphaned"):
            fm["orphaned"]    = existing_vault_fm["orphaned"]
            fm["orphaned_at"] = existing_vault_fm.get("orphaned_at", "")

    return fm


# ---------------------------------------------------------------------------
# Divergence detection
# ---------------------------------------------------------------------------

def is_diverged(src_fm: dict, src_body: str, mirror_fm: dict, mirror_body: str) -> bool:
    """True if source content differs from mirror (vault-added fields excluded).

    For source files with no frontmatter (most docs/ prose), only body is compared;
    title/type/status in the mirror were auto-generated and are not source-of-record.
    """
    if src_body.strip() != mirror_body.strip():
        return True

    if not src_fm:
        # Source has no frontmatter — title/type/status in mirror are vault-generated.
        return False

    # Both have frontmatter: compare only non-vault-managed fields.
    # One-sided check: verify source fields are faithfully present in mirror.
    # Mirror may carry auto-generated fields (title, type, status) not present in
    # source — these must not cause false divergence on re-run.
    skip = VAULT_ADDED_FIELDS | VAULT_MANUAL_FIELDS
    src_cmp    = {k: v for k, v in src_fm.items()    if k not in skip}
    mirror_cmp = {k: v for k, v in mirror_fm.items() if k not in skip}
    for k, v in src_cmp.items():
        if mirror_cmp.get(k) != v:
            return True
    return False


# ---------------------------------------------------------------------------
# Orphan handling
# ---------------------------------------------------------------------------

def apply_orphan(mirror_fm: dict, mirror_body: str, today: str) -> "tuple[dict, str]":
    """Mark frontmatter as orphaned and prepend warning to body."""
    fm = dict(mirror_fm)
    fm["orphaned"]    = True
    fm["orphaned_at"] = today
    fm["status"]      = "archived"

    if ORPHAN_WARNING.strip() not in mirror_body:
        mirror_body = ORPHAN_WARNING + mirror_body
    return fm, mirror_body


# ---------------------------------------------------------------------------
# Index generation
# ---------------------------------------------------------------------------

def write_dir_index(target_dir: Path, mirror_prefix: str, dry_run: bool, today: str) -> None:
    """Write/overwrite _index.md for target_dir listing all mirror files."""
    index_path = target_dir / "_index.md"
    files = sorted(p for p in target_dir.glob("*.md") if p.name != "_index.md")

    dir_name   = target_dir.name
    title      = f"repo-docs/{dir_name}"
    link_lines = "\n".join(f"- [[repo-docs/{dir_name}/{p.stem}|{p.stem}]]" for p in files)
    body       = f"# {title}\n\n{link_lines}\n"

    fm: dict = {
        "title":       title,
        "type":        "index",
        "status":      "active",
        "source_zone": SOURCE_ZONE,
        "mirror_of":   f"{mirror_prefix}/",
        "last_synced": f"{today}T00:00:00Z",
        "lifecycle":   LIFECYCLE,
        "generator":   GENERATOR,
    }
    if not dry_run:
        index_path.write_text(assemble_file(fm, body), encoding="utf-8")


# ---------------------------------------------------------------------------
# Per-file sync operation
# ---------------------------------------------------------------------------

SyncResult = dict  # keys: status, source (Path|None), mirror (Path)


def sync_one(
    source_path: Path,
    mirror_path: Path,
    mirror_of: str,
    dry_run: bool,
    verbose: bool,
    now_iso: str,
) -> SyncResult:
    """Sync a single source file to its mirror path."""
    src_text = source_path.read_text(encoding="utf-8-sig", errors="replace")
    src_fm, src_body = parse_frontmatter(src_text)

    title    = derive_title(source_path, src_fm)
    doc_type = infer_type(source_path)

    if mirror_path.exists():
        mirror_text = mirror_path.read_text(encoding="utf-8-sig", errors="replace")
        mirror_fm, mirror_body = parse_frontmatter(mirror_text)

        if not is_diverged(src_fm, src_body, mirror_fm, mirror_body):
            if verbose:
                print(f"    UNCHANGED  {mirror_path.name}")
            return {"status": "unchanged", "source": source_path, "mirror": mirror_path}

        new_fm = make_vault_fm(
            title=title, doc_type=doc_type, mirror_of=mirror_of,
            now_iso=now_iso, source_fm=src_fm, existing_vault_fm=mirror_fm,
        )
        if not dry_run:
            mirror_path.write_text(assemble_file(new_fm, src_body), encoding="utf-8")
        if verbose:
            print(f"    DIVERGED   {mirror_path.name}")
        return {"status": "diverged", "source": source_path, "mirror": mirror_path}

    # NEW
    new_fm = make_vault_fm(
        title=title, doc_type=doc_type, mirror_of=mirror_of,
        now_iso=now_iso, source_fm=src_fm,
    )
    if not dry_run:
        mirror_path.parent.mkdir(parents=True, exist_ok=True)
        mirror_path.write_text(assemble_file(new_fm, src_body), encoding="utf-8")
    if verbose:
        print(f"    NEW        {mirror_path.name}")
    return {"status": "new", "source": source_path, "mirror": mirror_path}


def orphan_one(
    mirror_path: Path,
    dry_run: bool,
    verbose: bool,
    today: str,
) -> SyncResult:
    """Flag an existing mirror file as orphaned."""
    mirror_text = mirror_path.read_text(encoding="utf-8-sig", errors="replace")
    mirror_fm, mirror_body = parse_frontmatter(mirror_text)

    if mirror_fm.get("orphaned"):
        if verbose:
            print(f"    ALREADY-ORPHANED  {mirror_path.name}")
        return {"status": "unchanged", "source": None, "mirror": mirror_path}

    new_fm, new_body = apply_orphan(mirror_fm, mirror_body, today)
    if not dry_run:
        mirror_path.write_text(assemble_file(new_fm, new_body), encoding="utf-8")
    if verbose:
        print(f"    ORPHANED   {mirror_path.name}")
    return {"status": "orphaned", "source": None, "mirror": mirror_path}


# ---------------------------------------------------------------------------
# Scope runners
# ---------------------------------------------------------------------------

def sync_root(
    docs_root: Path,
    repo_root: Path,
    vault_repo_docs: Path,
    dry_run: bool,
    verbose: bool,
    now_iso: str,
    today: str,
) -> list[SyncResult]:
    print("  [root files]")
    results: list[SyncResult] = []
    expected: set[str] = set()

    for src_name, vault_override in ROOT_DOCS_FILES.items():
        src_path = docs_root / src_name
        if not src_path.exists():
            continue
        vault_name = vault_override if vault_override else normalize_name(src_name)
        expected.add(vault_name)
        result = sync_one(
            src_path, vault_repo_docs / vault_name,
            f"docs/{src_name}", dry_run, verbose, now_iso,
        )
        results.append(result)

    for src_name, vault_name in REPO_ROOT_EXTRA.items():
        src_path = repo_root / src_name
        if not src_path.exists():
            continue
        expected.add(vault_name)
        result = sync_one(
            src_path, vault_repo_docs / vault_name,
            src_name, dry_run, verbose, now_iso,
        )
        results.append(result)

    # Orphan any root mirror files not in expected set
    for mirror_file in vault_repo_docs.glob("*.md"):
        if mirror_file.name in ("_index.md",) or mirror_file.name in expected:
            continue
        results.append(orphan_one(mirror_file, dry_run, verbose, today))

    return results


def sync_subdir(
    source_dir: Path,
    target_dir: Path,
    mirror_prefix: str,
    is_adr: bool,
    dry_run: bool,
    verbose: bool,
    now_iso: str,
    today: str,
) -> list[SyncResult]:
    print(f"  [{target_dir.name}/]")
    results: list[SyncResult] = []

    if not source_dir.exists():
        if verbose:
            print(f"    (source {source_dir.name}/ not found — skipping)")
        return results

    # Build expected mirror-name set from source files
    expected: set[str] = set()
    collision_check: dict[str, Path] = {}
    errors: list[str] = []

    for src_path in sorted(source_dir.glob("*.md")):
        vault_name = normalize_name(src_path.name, add_adr_prefix=is_adr)
        if vault_name in collision_check:
            errors.append(
                f"    COLLISION: {src_path.name} and "
                f"{collision_check[vault_name].name} both normalize to {vault_name}"
            )
            continue
        collision_check[vault_name] = src_path
        expected.add(vault_name)

        result = sync_one(
            src_path, target_dir / vault_name,
            f"{mirror_prefix}/{src_path.name}", dry_run, verbose, now_iso,
        )
        results.append(result)

    for err in errors:
        print(err, file=sys.stderr)

    # Orphan mirror files with no matching source
    if target_dir.exists():
        for mirror_file in target_dir.glob("*.md"):
            if mirror_file.name == "_index.md" or mirror_file.name in expected:
                continue
            results.append(orphan_one(mirror_file, dry_run, verbose, today))

    # Update (or create) the directory index
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        write_dir_index(target_dir, mirror_prefix, dry_run=False, today=today)

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sync-repo-docs",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Survey only; no files written",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print per-file status",
    )
    parser.add_argument(
        "--vault-root", type=Path,
        default=Path(__file__).parent.parent / "obsidian-vault",
        metavar="PATH",
        help="Path to vault root (default: ../obsidian-vault)",
    )
    parser.add_argument(
        "--repo-root", type=Path,
        default=Path(__file__).parent.parent.parent,
        metavar="PATH",
        help="Path to repo root (default: ../.. from this script)",
    )
    args = parser.parse_args()

    vault_root: Path = args.vault_root.resolve()
    repo_root:  Path = args.repo_root.resolve()
    docs_root        = repo_root / "docs"
    vault_repo_docs  = vault_root / "repo-docs"

    for p, label in [
        (vault_root,      "vault-root"),
        (repo_root,       "repo-root"),
        (docs_root,       "docs"),
        (vault_repo_docs, "repo-docs"),
    ]:
        if not p.is_dir():
            print(f"Error: {label} does not exist: {p}", file=sys.stderr)
            return 2

    now     = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    today   = now.strftime("%Y-%m-%d")

    if args.dry_run:
        print("DRY RUN — no files will be written\n")

    all_results: list[SyncResult] = []

    # Root files
    all_results.extend(
        sync_root(docs_root, repo_root, vault_repo_docs,
                  args.dry_run, args.verbose, now_iso, today)
    )

    # Subdirectories
    for src_subdir, tgt_subdir in DIR_MAP:
        source_dir = docs_root / src_subdir
        target_dir = vault_repo_docs / tgt_subdir
        all_results.extend(
            sync_subdir(
                source_dir, target_dir,
                mirror_prefix=f"docs/{src_subdir}",
                is_adr=(src_subdir == "adr"),
                dry_run=args.dry_run,
                verbose=args.verbose,
                now_iso=now_iso,
                today=today,
            )
        )

    # Summary
    counts: dict[str, int] = {}
    for r in all_results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    new       = counts.get("new", 0)
    diverged  = counts.get("diverged", 0)
    orphaned  = counts.get("orphaned", 0)
    unchanged = counts.get("unchanged", 0)
    total     = sum(counts.values())

    mode = "(dry-run) " if args.dry_run else ""
    print(f"\nSync {mode}complete:")
    print(f"  {new:5d}  new")
    print(f"  {diverged:5d}  diverged (updated)")
    print(f"  {orphaned:5d}  orphaned (flagged)")
    print(f"  {unchanged:5d}  unchanged")
    print(f"  {total:5d}  total")

    return 0


if __name__ == "__main__":
    sys.exit(main())

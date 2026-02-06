#!/usr/bin/env python3
"""Build a ready-to-paste LLM evidence bundle for a user."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from polymarket.rag.embedder import DEFAULT_EMBED_MODEL, SentenceTransformerEmbedder
from polymarket.rag.index import DEFAULT_COLLECTION, DEFAULT_PERSIST_DIR
from polymarket.rag.query import query_index
from polymarket.rag.reranker import CrossEncoderReranker, DEFAULT_RERANK_MODEL
from polytool.user_context import UserContext, resolve_user_context

logger = logging.getLogger(__name__)

DEFAULT_MODEL_HINT = "opus-4.5"

DEFAULT_QUESTIONS: List[Dict[str, str]] = [
    {"label": "profile", "question": "Summarize the user's profile and recent activity context."},
    {"label": "patterns", "question": "What trading patterns or strategy signals appear in the evidence?"},
    {"label": "risk", "question": "What risk signals or anomalies appear in the evidence?"},
    {"label": "execution", "question": "What evidence exists about execution quality, slippage, or fees?"},
    {"label": "markets", "question": "Which markets or categories dominate recent activity?"},
]


@dataclass(frozen=True)
class RagSettings:
    k: int = 8
    hybrid: bool = True
    rerank: bool = True
    top_k_vector: int = 25
    top_k_lexical: int = 25
    rrf_k: int = 60
    rerank_top_n: int = 50
    model: str = DEFAULT_EMBED_MODEL
    rerank_model: str = DEFAULT_RERANK_MODEL
    device: str = "auto"
    persist_dir: Path = DEFAULT_PERSIST_DIR
    collection: str = DEFAULT_COLLECTION
    private_only: bool = True
    public_only: bool = False
    include_archive: bool = False

    def to_manifest(self) -> dict:
        return {
            "k": self.k,
            "hybrid": self.hybrid,
            "rerank": self.rerank,
            "top_k_vector": self.top_k_vector,
            "top_k_lexical": self.top_k_lexical,
            "rrf_k": self.rrf_k,
            "rerank_top_n": self.rerank_top_n,
            "model": self.model,
            "rerank_model": self.rerank_model,
            "device": self.device,
            "persist_dir": _as_posix(self.persist_dir),
            "collection": self.collection,
            "private_only": self.private_only,
            "public_only": self.public_only,
            "include_archive": self.include_archive,
        }


def _utcnow() -> datetime:
    return datetime.utcnow()


def _short_uuid() -> str:
    return uuid.uuid4().hex[:8]


def _format_utc(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


def _as_posix(path: Path | str) -> str:
    return Path(path).as_posix()


def _parse_utc_timestamp(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _ensure_within_root(root: Path, target: Path) -> None:
    root_path = root.resolve()
    target_path = target.resolve()
    if os.path.commonpath([str(root_path), str(target_path)]) != str(root_path):
        raise ValueError("Output directory must live under kb/.")


def _build_user_prefixes(user_slug: str) -> List[str]:
    """Build path prefixes for RAG filtering based on canonical user slug."""
    if not user_slug:
        return []
    return [
        f"kb/users/{user_slug}/",
        f"artifacts/dossiers/{user_slug}/",
        f"artifacts/dossiers/users/{user_slug}/",
    ]


def _read_text(path: Path, label: str) -> str:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return path.read_text(encoding="utf-8")


def _append_block(lines: List[str], text: str) -> None:
    if text:
        lines.append(text.rstrip("\n"))
    else:
        lines.append("")


def _resolve_repo_relative(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return path.resolve().as_posix()
    return rel.as_posix()


def _write_devlog(
    *,
    date_label: str,
    now: datetime,
    user_slug: str,
    run_id: str,
    output_dir: Path,
    bundle_path: Path,
    questions_path: Optional[str],
    settings: RagSettings,
) -> Path:
    devlog_dir = Path("kb") / "devlog"
    devlog_dir.mkdir(parents=True, exist_ok=True)
    devlog_path = devlog_dir / f"{date_label}_llm_bundle_{user_slug}_{run_id}.md"

    questions_label = "default"
    if questions_path:
        questions_label = _resolve_repo_relative(Path(questions_path))

    settings_payload = json.dumps(settings.to_manifest(), indent=2, sort_keys=True)

    lines = [
        "---",
        f"date_utc: {_format_utc(now)}",
        "run_type: llm_bundle",
        f"user_slug: {user_slug}",
        f"run_id: {run_id}",
        "---",
        "",
        "# LLM Bundle Run",
        "",
        "## Summary",
        "TODO",
        "",
        "## Details",
        f"Bundle dir: {_resolve_repo_relative(output_dir)}",
        f"Questions file: {questions_label}",
        "RAG settings:",
        "```json",
        settings_payload,
        "```",
        f"Prompt to paste: {_resolve_repo_relative(bundle_path)}",
        "",
        "## Notes",
        "TODO",
        "",
        "## Next Steps",
        "TODO",
        "",
    ]

    devlog_path.write_text("\n".join(lines), encoding="utf-8")
    return devlog_path


def _resolve_dossier_dir(user_ctx: UserContext, dossier_path: Optional[str]) -> Path:
    if dossier_path:
        path = Path(dossier_path)
        if path.is_file():
            path = path.parent
        if not path.exists():
            raise FileNotFoundError(f"Dossier path not found: {path}")
        return path
    return _find_latest_dossier_dir(user_ctx)


def _find_latest_dossier_dir(user_ctx: UserContext) -> Path:
    base = user_ctx.artifacts_user_dir
    if not base.exists():
        raise FileNotFoundError(f"No dossier exports found under {base}")

    manifests = list(base.rglob("manifest.json"))
    if not manifests:
        raise FileNotFoundError(f"No dossier manifest.json found under {base}")

    def _manifest_key(path: Path) -> tuple[float, str]:
        ts = None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
        raw_ts = payload.get("created_at_utc", "")
        parsed = _parse_utc_timestamp(raw_ts)
        if parsed is None:
            try:
                ts = path.stat().st_mtime
            except OSError:
                ts = 0.0
        else:
            ts = parsed.timestamp()
        return (float(ts), path.as_posix())

    latest_manifest = max(manifests, key=_manifest_key)
    return latest_manifest.parent


def _normalize_questions(raw: Any) -> List[Dict[str, str]]:
    if raw is None:
        return DEFAULT_QUESTIONS
    if not isinstance(raw, list):
        raise ValueError("Questions file must contain a JSON/YAML list.")
    output: List[Dict[str, str]] = []
    for entry in raw:
        if isinstance(entry, str):
            question = entry.strip()
            label = ""
        elif isinstance(entry, dict):
            question = str(entry.get("question") or entry.get("q") or "").strip()
            label = str(entry.get("label") or entry.get("name") or "").strip()
        else:
            raise ValueError("Each question must be a string or object with 'question'.")
        if not question:
            raise ValueError("Question text cannot be empty.")
        payload: Dict[str, str] = {"question": question}
        if label:
            payload["label"] = label
        output.append(payload)
    if not output:
        raise ValueError("Questions list cannot be empty.")
    return output


def _load_questions(questions_path: Optional[str]) -> List[Dict[str, str]]:
    if not questions_path:
        return DEFAULT_QUESTIONS
    path = Path(questions_path)
    if not path.exists():
        raise FileNotFoundError(f"Questions file not found: {path}")
    raw_text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PyYAML is required to parse YAML questions files.") from exc
        data = yaml.safe_load(raw_text)
    else:
        data = json.loads(raw_text)
    return _normalize_questions(data)


def _run_rag_queries(
    questions: List[Dict[str, str]],
    settings: RagSettings,
    user_slug: Optional[str],
    prefixes: Optional[List[str]],
) -> List[dict]:
    if settings.k <= 0:
        raise ValueError("k must be positive.")

    embedder = SentenceTransformerEmbedder(model_name=settings.model, device=settings.device)
    reranker = None
    if settings.rerank:
        if not settings.hybrid:
            print("Warning: rerank enabled without hybrid retrieval.", file=sys.stderr)
        reranker = CrossEncoderReranker(
            model_name=settings.rerank_model,
            device=settings.device,
            cache_folder="kb/rag/models",
        )

    outputs: List[dict] = []
    for entry in questions:
        question = entry["question"]
        results = query_index(
            question=question,
            embedder=embedder,
            k=settings.k,
            persist_directory=settings.persist_dir,
            collection_name=settings.collection,
            filter_prefixes=prefixes,
            user_slug=user_slug,
            doc_types=None,
            private_only=settings.private_only,
            public_only=settings.public_only,
            date_from=None,
            date_to=None,
            include_archive=settings.include_archive,
            hybrid=settings.hybrid,
            lexical_only=False,
            top_k_vector=settings.top_k_vector,
            top_k_lexical=settings.top_k_lexical,
            rrf_k=settings.rrf_k,
            reranker=reranker,
            rerank_top_n=settings.rerank_top_n,
        )

        if settings.hybrid:
            mode = "hybrid+rerank" if settings.rerank else "hybrid"
        else:
            mode = "vector+rerank" if settings.rerank else "vector"

        payload: dict = {
            "question": question,
            "k": settings.k,
            "mode": mode,
            "filters": {
                "user_slug": user_slug,
                "doc_types": None,
                "private_only": settings.private_only and not settings.public_only,
                "public_only": settings.public_only,
                "date_from": None,
                "date_to": None,
                "include_archive": settings.include_archive,
                "prefix_backstop": prefixes or [],
            },
            "results": results,
        }
        if entry.get("label"):
            payload["label"] = entry["label"]
        outputs.append(payload)
    return outputs


def _collect_excerpts(payloads: Iterable[dict]) -> List[Dict[str, str]]:
    seen: set[str] = set()
    excerpts: List[Dict[str, str]] = []
    for payload in payloads:
        results = payload.get("results") or []
        for result in results:
            file_path = result.get("file_path", "")
            chunk_id = result.get("chunk_id", "")
            doc_id = result.get("doc_id", "")
            snippet = result.get("snippet", "")
            key = chunk_id or f"{file_path}|{doc_id}|{snippet}"
            if not key or key in seen:
                continue
            seen.add(key)
            excerpts.append({
                "file_path": file_path,
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "snippet": snippet,
            })
    return excerpts


def _render_bundle(
    *,
    user_handle: str,
    user_slug: str,
    created_at: str,
    run_id: str,
    dossier_path: str,
    memo_text: str,
    dossier_text: str,
    manifest_text: str,
    excerpts: List[Dict[str, str]],
) -> str:
    lines: List[str] = []
    lines.append("# Opus Evidence Bundle")
    lines.append("")
    lines.append(f"User: {user_handle}")
    lines.append(f"User slug: {user_slug}")
    lines.append(f"Created at (UTC): {created_at}")
    lines.append(f"Run id: {run_id}")
    lines.append(f"Dossier path: {dossier_path}")
    lines.append("")

    lines.append("## memo.md")
    lines.append("")
    _append_block(lines, memo_text)
    lines.append("")

    lines.append("## dossier.json")
    lines.append("")
    _append_block(lines, dossier_text)
    lines.append("")

    lines.append("## manifest.json")
    lines.append("")
    _append_block(lines, manifest_text)
    lines.append("")

    lines.append("## RAG excerpts")
    lines.append("")
    if not excerpts:
        lines.append("_No RAG excerpts returned._")
    else:
        for entry in excerpts:
            file_path = entry.get("file_path", "")
            snippet = entry.get("snippet", "")
            lines.append(f"[file_path: {file_path}]")
            _append_block(lines, snippet)
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an LLM evidence bundle from the latest dossier export and RAG excerpts.",
    )
    parser.add_argument("--user", required=True, help="Target user handle (with or without @).")
    parser.add_argument("--dossier-path", help="Optional dossier export path override.")
    parser.add_argument("--questions-file", help="JSON/YAML file listing RAG questions to run.")
    parser.add_argument(
        "--no-devlog",
        action="store_true",
        help="Skip writing a devlog entry for this run.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    user_raw = args.user.strip() if args.user else ""
    if not user_raw or user_raw == "@":
        print("Error: --user must be a non-empty handle.", file=sys.stderr)
        return 1

    # Use canonical identity resolver for consistent slug derivation
    original_handle = user_raw if user_raw.startswith("@") else f"@{user_raw}"
    user_ctx = resolve_user_context(
        handle=original_handle,
        wallet=None,  # llm-bundle only uses handle
        kb_root=Path("kb"),
        artifacts_root=Path("artifacts"),
        persist_mapping=False,  # Don't persist without wallet
    )
    user_slug = user_ctx.slug
    user_handle = user_ctx.handle or original_handle

    logger.debug(
        "Resolved UserContext: slug=%s handle=%s",
        user_slug,
        user_handle,
    )

    try:
        questions = _load_questions(args.questions_file)
    except (FileNotFoundError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        dossier_dir = _resolve_dossier_dir(user_ctx, args.dossier_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    memo_path = dossier_dir / "memo.md"
    dossier_json_path = dossier_dir / "dossier.json"
    manifest_path = dossier_dir / "manifest.json"

    try:
        memo_text = _read_text(memo_path, "memo.md")
        dossier_text = _read_text(dossier_json_path, "dossier.json")
        manifest_text = _read_text(manifest_path, "manifest.json")
    except (FileNotFoundError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    run_id = _short_uuid()
    now = _utcnow()
    date_label = now.strftime("%Y-%m-%d")

    output_dir = user_ctx.llm_bundles_dir / date_label / run_id

    try:
        _ensure_within_root(Path("kb"), output_dir)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    prefixes = _build_user_prefixes(user_slug)
    settings = RagSettings()
    try:
        rag_payloads = _run_rag_queries(questions, settings, user_slug, prefixes)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    excerpts = _collect_excerpts(rag_payloads)

    dossier_rel = _resolve_repo_relative(dossier_dir)
    created_at = _format_utc(now)

    bundle_text = _render_bundle(
        user_handle=user_handle,
        user_slug=user_slug,
        created_at=created_at,
        run_id=run_id,
        dossier_path=dossier_rel,
        memo_text=memo_text,
        dossier_text=dossier_text,
        manifest_text=manifest_text,
        excerpts=excerpts,
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = output_dir / "bundle.md"
    manifest_out_path = output_dir / "bundle_manifest.json"
    rag_queries_path = output_dir / "rag_queries.json"

    bundle_path.write_text(bundle_text, encoding="utf-8")
    rag_queries_path.write_text(json.dumps(rag_payloads, indent=2, sort_keys=True), encoding="utf-8")

    manifest_payload = {
        "created_at_utc": created_at,
        "user_slug": user_slug,
        "run_id": run_id,
        "model_hint": DEFAULT_MODEL_HINT,
        "dossier_path": dossier_rel,
        "rag_query_settings": settings.to_manifest(),
        "selected_excerpts": [
            {
                "file_path": entry.get("file_path", ""),
                "chunk_id": entry.get("chunk_id", ""),
                "doc_id": entry.get("doc_id", ""),
            }
            for entry in excerpts
        ],
    }
    manifest_out_path.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("LLM bundle created")
    print(f"Output dir: {output_dir}")
    print(f"Bundle: {bundle_path}")
    print(f"Manifest: {manifest_out_path}")
    print(f"RAG queries: {rag_queries_path}")
    if not args.no_devlog:
        devlog_path = _write_devlog(
            date_label=date_label,
            now=now,
            user_slug=user_slug,
            run_id=run_id,
            output_dir=output_dir,
            bundle_path=bundle_path,
            questions_path=args.questions_file,
            settings=settings,
        )
        print(f"Devlog: {devlog_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

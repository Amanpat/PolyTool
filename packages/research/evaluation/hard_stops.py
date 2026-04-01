"""RIS v1 evaluation gate — hard-stop pre-screening checks.

Hard stops reject documents before LLM scoring when the document is
fundamentally unsuitable: empty, too short, encoding garbage, or spam.
"""

from __future__ import annotations

import re

from packages.research.evaluation.types import EvalDocument, HardStopResult

# Pattern to detect repeated URLs (4+ occurrences of the same URL)
_URL_PATTERN = re.compile(r"https?://\S+")


def check_hard_stops(doc: EvalDocument) -> HardStopResult:
    """Run pre-screening hard-stop checks on a document.

    Checks are applied in order:
    1. empty_body     — body is None, empty, or whitespace-only
    2. too_short      — body shorter than 50 chars
    3. encoding_garbage — >80% non-ASCII characters
    4. spam_malformed — all-caps ratio >60% or repeated URLs (4+ occurrences)

    Returns HardStopResult(passed=True) if all checks pass.
    Returns HardStopResult(passed=False, ...) on the first failing check.
    """
    body = doc.body

    # Check 1: empty body
    if body is None or len(body.strip()) == 0:
        return HardStopResult(
            passed=False,
            reason="Document body is empty or whitespace-only.",
            stop_type="empty_body",
        )

    stripped = body.strip()

    # Check 2: too short
    if len(stripped) < 50:
        return HardStopResult(
            passed=False,
            reason=f"Document body is too short ({len(stripped)} chars; minimum is 50).",
            stop_type="too_short",
        )

    # Check 3: encoding garbage (>80% non-ASCII)
    total_chars = len(stripped)
    non_ascii_chars = sum(1 for c in stripped if ord(c) > 127)
    if total_chars > 0 and (non_ascii_chars / total_chars) > 0.80:
        ratio = non_ascii_chars / total_chars
        return HardStopResult(
            passed=False,
            reason=f"Document body contains {ratio:.1%} non-ASCII characters (limit 80%).",
            stop_type="encoding_garbage",
        )

    # Check 4: spam / malformed
    # 4a: All-caps ratio >60% of alphabetic characters
    alpha_chars = [c for c in stripped if c.isalpha()]
    if alpha_chars:
        upper_count = sum(1 for c in alpha_chars if c.isupper())
        caps_ratio = upper_count / len(alpha_chars)
        if caps_ratio > 0.60:
            return HardStopResult(
                passed=False,
                reason=f"Document body has {caps_ratio:.1%} uppercase characters (limit 60%).",
                stop_type="spam_malformed",
            )

    # 4b: Same URL repeated 4+ times
    urls = _URL_PATTERN.findall(stripped)
    if urls:
        from collections import Counter
        url_counts = Counter(urls)
        most_common_url, count = url_counts.most_common(1)[0]
        if count >= 4:
            return HardStopResult(
                passed=False,
                reason=f"Document body contains repeated URL ({count}x): {most_common_url[:60]}",
                stop_type="spam_malformed",
            )

    return HardStopResult(passed=True)

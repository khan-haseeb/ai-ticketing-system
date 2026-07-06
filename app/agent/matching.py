"""
Shared name-to-entity matching used by resolve_entities.py and execute_tool.py.

Distinguishes three outcomes instead of silently guessing:
- "unique": exactly one entity matches -> safe to auto-resolve
- "ambiguous": 2+ distinct entities match -> ask the user which one
- "none": nothing matches -> tell the user and ask how to proceed
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class MatchResult:
    status: str  # "unique" | "ambiguous" | "none"
    uid: Optional[str] = None
    candidates: Optional[list[tuple[str, str]]] = None


def resolve_name(query: str, candidates: list[tuple[str, str]]) -> MatchResult:
    """
    candidates: list of (name, uid) tuples. A single entity may appear more than
    once (e.g. once by name, once by email) - matches are deduped by uid before
    judging uniqueness, so that isn't mistaken for ambiguity.
    """
    if not query or not candidates:
        return MatchResult(status="none")

    q = query.lower().strip()

    tiers = [
        lambda: [(n, u) for n, u in candidates if n.lower() == q],
        lambda: [(n, u) for n, u in candidates if q in n.lower() or n.lower() in q],
        lambda: [
            (n, u) for n, u in candidates
            if set(re.split(r'\W+', q)) & set(re.split(r'\W+', n.lower()))
        ],
    ]

    for tier in tiers:
        matches = tier()
        if not matches:
            continue
        by_uid = {}
        for name, uid in matches:
            by_uid.setdefault(uid, name)
        if len(by_uid) == 1:
            return MatchResult(status="unique", uid=next(iter(by_uid)))
        return MatchResult(
            status="ambiguous",
            candidates=[(name, uid) for uid, name in by_uid.items()],
        )

    return MatchResult(status="none")

"""Evidence extraction and claim verification.

Evidence extraction (deterministic): splits each evidence-capable source's
retrieved text into passages and keeps the passages most relevant to the
lesson's concepts. These passages form the compact "evidence pack" given to
the generator.

Claim verification (deterministic): after generation — and after every
instructor save — each claim's citations are checked:

* cited IDs that do not exist are removed and noted;
* metadata-only sources (books, videos) cannot verify a claim;
* the quoted excerpt must actually appear in the retrieved text of a cited
  evidence source (whitespace/case-insensitive, or ≥85% token coverage).

This proves the quote is real; whether it *semantically* supports the claim
is judged separately by QC Layer 1. The status assigned here is therefore
conservative and labelled as an automated check.
"""
from __future__ import annotations

import re

from .._text import normalize_ws
from ..research.evaluation import tokenize

PASSAGES_PER_SOURCE = 6
PASSAGE_MAX_CHARS = 700
MAX_EVIDENCE_SOURCES = 12
TOKEN_COVERAGE_MATCH = 0.85


def split_passages(text: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n|(?<=[.!?])\s{2,}", text or "") if b.strip()]
    passages: list[str] = []
    for block in blocks:
        block = normalize_ws(block)
        while len(block) > PASSAGE_MAX_CHARS:
            cut = block.rfind(". ", 0, PASSAGE_MAX_CHARS)
            cut = cut + 1 if cut > 200 else PASSAGE_MAX_CHARS
            passages.append(block[:cut].strip())
            block = block[cut:].strip()
        if len(block) >= 40:
            passages.append(block)
    return passages


def extract_passages(content: str, terms: set[str], limit: int = PASSAGES_PER_SOURCE) -> list[str]:
    scored = []
    for idx, passage in enumerate(split_passages(content)):
        overlap = len(terms & tokenize(passage))
        if overlap:
            scored.append((overlap, -idx, passage))
    scored.sort(reverse=True)
    top = sorted(scored[:limit], key=lambda t: -t[1])  # restore document order
    return [p for _, _, p in top]


def run_evidence_extraction(lesson, terms: set[str]) -> dict:
    """Store relevant passages on each evidence source. Returns a summary."""
    evidence_sources = sorted(
        (s for s in lesson.sources if s.evidence_use == "evidence" and s.content),
        key=lambda s: -s.reliability_score,
    )[:MAX_EVIDENCE_SOURCES]
    total = 0
    for src in lesson.sources:
        extra = dict(src.extra or {})
        if src in evidence_sources:
            passages = extract_passages(src.content, terms)
            extra["passages"] = passages
            total += len(passages)
        else:
            extra.pop("passages", None)
        src.extra = extra
    return {"evidence_sources": len(evidence_sources), "passages": total}


def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[`*_>#|]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def excerpt_found(excerpt: str, content: str) -> bool:
    ex, body = _norm(excerpt), _norm(content)
    if not ex:
        return False
    if ex in body:
        return True
    ex_tokens = re.findall(r"[a-z0-9]+", ex)
    if len(ex_tokens) < 4:
        return False
    body_tokens = re.findall(r"[a-z0-9]+", body)
    # Sliding window: is (almost) every excerpt token present in some window
    # of comparable length? Tolerates ellipses and minor punctuation edits.
    window = len(ex_tokens) + 6
    need = set(ex_tokens)
    for start in range(0, max(1, len(body_tokens) - window + 1), 3):
        win = set(body_tokens[start : start + window])
        if len(need & win) / len(need) >= TOKEN_COVERAGE_MATCH:
            return True
    return False


def verify_claims(claims: list[dict], sources_by_key: dict) -> list[dict]:
    """Return claims with backend-assigned ``status``/``verification_note``."""
    verified = []
    for claim in claims:
        c = dict(claim)
        notes: list[str] = []
        cited = list(dict.fromkeys(c.get("source_ids") or []))
        unknown = [k for k in cited if k not in sources_by_key]
        if unknown:
            notes.append(f"Removed citation(s) to unknown source ID(s): {', '.join(unknown)}.")
        known = [k for k in cited if k in sources_by_key]
        c["source_ids"] = known
        evidence_capable = [k for k in known if sources_by_key[k].evidence_use == "evidence" and sources_by_key[k].content]
        metadata_only = [k for k in known if k not in evidence_capable]
        excerpt = (c.get("evidence_excerpt") or "").strip()

        if not known:
            status = "Unsupported"
            notes.append("No supporting source is cited.")
        elif not evidence_capable:
            status = "Unable to Verify"
            notes.append(
                f"Cited source(s) {', '.join(metadata_only)} are metadata-only or lack retrieved text; "
                "they cannot verify a specific claim."
            )
        elif not excerpt:
            status = "Unable to Verify"
            notes.append("No evidence excerpt was provided to check against the source text.")
        else:
            matched = [k for k in evidence_capable if excerpt_found(excerpt, sources_by_key[k].content)]
            if matched:
                claim_terms = tokenize(c.get("text"))
                overlap = len(claim_terms & tokenize(excerpt)) / max(1, len(claim_terms))
                if overlap >= 0.2:
                    status = "Supported"
                    notes.append(
                        f"Excerpt found verbatim in {', '.join(matched)}. Semantic support is reviewed by QC Layer 1."
                    )
                else:
                    status = "Partially Supported"
                    notes.append(
                        f"Excerpt found in {', '.join(matched)} but shares little wording with the claim."
                    )
            else:
                status = "Unable to Verify"
                notes.append("The quoted excerpt was NOT found in the retrieved text of the cited source(s).")
        if metadata_only and evidence_capable:
            notes.append(f"Metadata-only citation(s) {', '.join(metadata_only)} ignored for verification.")
        c["status"] = status
        c["verification_note"] = " ".join(notes)
        if status in ("Unsupported", "Unable to Verify", "Conflicting Evidence"):
            c["needs_research"] = True
        verified.append(c)
    return verified


def evidence_pack(lesson, max_chars: int = 45000) -> tuple[str, str]:
    """Render the evidence pack and metadata-only list for prompts."""
    parts, used = [], 0
    for src in sorted(lesson.sources, key=lambda s: -s.reliability_score):
        passages = (src.extra or {}).get("passages") or []
        if src.evidence_use != "evidence" or not passages:
            continue
        block = (
            f"[{src.source_key}] {src.title} — {src.author_or_domain} ({src.reliability_tier})\nURL: {src.url}\n"
            + "\n".join(f"  > {p}" for p in passages)
        )
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    meta = [
        f"[{s.source_key}] {s.source_type.upper()} METADATA-ONLY: {s.title} — {s.author_or_domain or 'unknown'}"
        for s in lesson.sources
        if s.source_type in ("book", "youtube")
    ]
    return ("\n\n".join(parts) or "(no retrieved evidence available)", "\n".join(meta) or "(none)")

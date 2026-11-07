"""Deterministic source normalisation, de-duplication and reliability scoring.

This is intentionally rule-based (not AI) so the rationale for every source
is reproducible and explainable:

    reliability = 0.55 * authority + 0.30 * relevance + 0.15 * content_availability

Authority comes from a transparent domain tier table; relevance is keyword
overlap between the source text and the lesson's title/objective/concepts
(blended with the search engine's own relevance score when available).
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .providers import RawSource, domain_of

AUTHORITY_WEIGHT, RELEVANCE_WEIGHT, CONTENT_WEIGHT = 0.55, 0.30, 0.15
MIN_EVIDENCE_CHARS = 200     # below this a page cannot meaningfully support claims
MIN_EVIDENCE_RELEVANCE = 0.15
EXCLUDE_RELEVANCE = 0.05

# (tier label, authority score, domains/suffixes). First match wins.
AUTHORITY_TIERS: list[tuple[str, float, tuple[str, ...]]] = [
    ("Official standard", 1.0, (
        "rfc-editor.org", "datatracker.ietf.org", "ietf.org", "w3.org", "whatwg.org",
        "iso.org", "ecma-international.org", "iana.org", "unicode.org",
    )),
    ("Official documentation", 0.9, (
        "developer.mozilla.org", "docs.python.org", "postgresql.org", "dev.mysql.com",
        "learn.microsoft.com", "docs.microsoft.com", "docs.oracle.com", "sqlite.org",
        "mariadb.com", "docs.aws.amazon.com", "cloud.google.com", "developer.apple.com",
        "nodejs.org", "react.dev", "docs.github.com", "kubernetes.io", "go.dev", "rust-lang.org",
        "developers.google.com", "web.dev",
    )),
    ("Government / university", 0.85, (".gov", ".edu", ".ac.uk", ".gov.uk", ".ac.in", ".edu.au")),
    ("Peer-reviewed / scholarly", 0.85, (
        "acm.org", "ieee.org", "springer.com", "sciencedirect.com", "nature.com", "arxiv.org",
        "jstor.org", "ncbi.nlm.nih.gov",
    )),
    ("Recognised educational", 0.7, (
        "khanacademy.org", "freecodecamp.org", "cs50.harvard.edu", "coursera.org", "edx.org",
        "britannica.com", "ocw.mit.edu", "openstax.org",
    )),
    ("Encyclopedic (secondary)", 0.6, ("wikipedia.org",)),
    ("Reputable technical site", 0.55, (
        "w3schools.com", "geeksforgeeks.org", "digitalocean.com", "ibm.com", "redhat.com",
        "cloudflare.com", "atlassian.com", "postman.com", "sqlshack.com", "sqltutorial.org",
        "tutorialspoint.com", "programiz.com", "realpython.com", "stackoverflow.com",
    )),
    ("User-generated / low authority", 0.3, (
        "medium.com", "quora.com", "reddit.com", "pinterest.com", "facebook.com",
        "linkedin.com", "dev.to", "hashnode.dev", "blogspot.com", "wordpress.com",
    )),
]
DEFAULT_WEB_TIER = ("General website", 0.45)

_STOPWORDS = set(
    "a an and are as at be between by can for from how in into is it its of on or that the their them "
    "these this to two use used using what when which with explain distinguish demonstrate describe "
    "understand learners learner able will should lesson introduction".split()
)
_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "ref"}


def tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    words = re.findall(r"[a-z0-9][a-z0-9+#.-]*", text.lower())
    return {w.strip(".-") for w in words if len(w) > 1 and w not in _STOPWORDS}


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in _TRACKING_PARAMS))
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(("https", host, path, "", query, ""))


def dedupe_key(src: RawSource) -> str:
    """Stable identity used to collapse duplicates across queries and reruns."""
    meta = src.get("metadata") or {}
    if src.get("source_type") == "youtube" and meta.get("video_id"):
        return f"youtube:{meta['video_id']}"
    if src.get("source_type") == "book":
        isbn = meta.get("isbn_13") or meta.get("isbn_10")
        if isbn:
            return f"book:isbn:{isbn}"
        title = re.sub(r"\W+", " ", (src.get("title") or "").lower()).strip()
        author = (src.get("author_or_domain") or "").split(",")[0].strip().lower()
        return f"book:{title}|{author}"[:500]
    return f"web:{normalize_url(src.get('url'))}"[:500]


def authority_for(domain: str | None) -> tuple[str, float]:
    if not domain:
        return DEFAULT_WEB_TIER
    for label, score, patterns in AUTHORITY_TIERS:
        for p in patterns:
            if p.startswith("."):
                if domain.endswith(p):
                    return label, score
            elif domain == p or domain.endswith("." + p):
                return label, score
    return DEFAULT_WEB_TIER


def relevance(src: RawSource, topic_terms: set[str]) -> float:
    if not topic_terms:
        return 0.0
    text = " ".join(filter(None, [src.get("title"), src.get("description"), (src.get("content") or "")[:4000]]))
    overlap = len(topic_terms & tokenize(text)) / len(topic_terms)
    provider = src.get("provider_score")
    if isinstance(provider, (int, float)):
        return round(min(1.0, 0.5 * overlap + 0.5 * float(provider)), 3)
    return round(min(1.0, overlap), 3)


def evaluate(src: RawSource, topic_terms: set[str]) -> dict:
    """Return reliability fields and the evidence-use decision for one source."""
    stype = src.get("source_type")
    rel = relevance(src, topic_terms)
    content_len = len(src.get("content") or "")
    content_score = min(1.0, content_len / 2000)
    reasons: list[str] = []

    if stype == "website":
        tier, authority = authority_for(src.get("author_or_domain"))
        reasons.append(f"{tier} ({src.get('author_or_domain')}).")
    elif stype == "book":
        tier, authority = "Published book (metadata only)", 0.7
        reasons.append("Published book; only catalogue metadata was retrieved, the text was not read.")
    else:
        tier, authority = "Video (metadata only)", 0.4
        reasons.append("Video; only title/description metadata was retrieved, no transcript.")

    score = round(AUTHORITY_WEIGHT * authority + RELEVANCE_WEIGHT * rel + CONTENT_WEIGHT * content_score, 3)
    reasons.append(f"Topic relevance {rel:.2f}.")

    if stype == "book":
        use = "further_reading"
    elif stype == "youtube":
        use = "supplementary"
    elif rel < EXCLUDE_RELEVANCE:
        use = "excluded"
        reasons.append("Excluded: little overlap with the lesson topic.")
    elif content_len >= MIN_EVIDENCE_CHARS and rel >= MIN_EVIDENCE_RELEVANCE:
        use = "evidence"
        reasons.append(f"{content_len} characters of page text retrieved; usable as evidence.")
    else:
        use = "supplementary"
        reasons.append(
            "Not enough retrieved text to verify claims against." if content_len < MIN_EVIDENCE_CHARS
            else "Relevance too low to be used as evidence."
        )
    if src.get("published_date"):
        reasons.append(f"Published {src['published_date']}.")
    return {
        "reliability_score": score,
        "reliability_tier": tier,
        "reliability_rationale": " ".join(reasons),
        "evidence_use": use,
        "relevance": rel,
    }


def dedupe(sources: list[RawSource]) -> list[RawSource]:
    """Remove duplicates, keeping the variant with the most retrieved content."""
    best: dict[str, RawSource] = {}
    for src in sources:
        key = dedupe_key(src)
        cur = best.get(key)
        if cur is None or len(src.get("content") or "") > len(cur.get("content") or ""):
            best[key] = src
    return list(best.values())

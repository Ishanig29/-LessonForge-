"""Build offline demo source fixtures from real documentation text.

Run once with network access to GitHub:
    python scripts/build_demo_fixtures.py

Text is downloaded from the public GitHub repositories that publish these
documents (httpwg, mdn/content, postgres/postgres, MicrosoftDocs/sql-docs),
converted to plain text and stored with explicit provenance so demo-mode
evidence is genuine text from the cited document, captured at a known date.
"""
import html
import json
import re
from datetime import date
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parents[1] / "app" / "demo" / "fixtures"
CAPTURED = date.today().isoformat()


def get(url: str) -> str:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def html_to_text(raw: str) -> str:
    body = re.sub(r"(?s)<(script|style).*?</\1>", "", raw)
    body = re.sub(r"</(p|div|h\d|li|dt|dd|pre|tr)>", "\n\n", body)
    text = html.unescape(re.sub(r"<[^>]+>", "", body)).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text)


def section(text: str, start: str, end: str) -> str:
    i = text.rfind("\n" + start + "\n")  # last match: skips the table of contents
    j = text.find("\n" + end, i + len(start) + 2)
    return text[i:j].strip()


def mdn_clean(md: str) -> str:
    md = md.split("---", 2)[2]
    md = re.sub(r'\{\{\s*\w+\("([^"]*)"(?:\s*,\s*"([^"]*)")?[^}]*\)\s*\}\}',
                lambda m: m.group(2) or m.group(1), md)
    md = re.sub(r"\{\{[^}]*\}\}", "", md)
    md = re.sub(r"(?s)<table.*?</table>", "", md)
    md = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
    md = md.split("## Specifications")[0].split("## Browser compatibility")[0]
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def sgml_text(seg: str) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", "", seg))
    t = "\n".join(l.strip() for l in t.splitlines())
    t = re.sub(r"(?<!\n)\n(?!\n)", " ", t)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", t)).strip()


def src(title, url, domain, content, mirror, published=None):
    return {
        "source_type": "website", "provider": "demo_fixture", "title": title, "url": url,
        "author_or_domain": domain, "description": content[:300], "content": content,
        "published_date": published, "provider_score": 0.9,
        "metadata": {"capture_note": f"Offline demo fixture: text captured {CAPTURED} from {mirror}. "
                                     "Not a live search result.", "mirror": mirror},
    }


def build_http():
    mirror = "https://raw.githubusercontent.com/httpwg/httpwg.github.io/main/specs/rfc9110.html"
    rfc = html_to_text(get(mirror))
    parts = [section(rfc, s, e) for s, e in [
        ("9.2.1. Safe Methods", "9.2.3. "), ("9.3.1. GET", "9.3.2. HEAD"), ("9.3.3. POST", "9.3.4. PUT"),
        ("15. Status Codes", "15.1. Overview"), ("15.3. Successful 2xx", "15.3.1. "),
        ("15.5. Client Error 4xx", "15.5.1. "), ("15.6. Server Error 5xx", "15.6.1. ")]]
    sources = [src("RFC 9110: HTTP Semantics (sections 9.2, 9.3.1, 9.3.3, 15)",
                   "https://www.rfc-editor.org/rfc/rfc9110.html", "rfc-editor.org", "\n\n".join(parts), mirror,
                   "2022-06")]
    base = "https://raw.githubusercontent.com/mdn/content/main/files/en-us/"
    for title, path, url in [
        ("GET request method - HTTP | MDN", "web/http/reference/methods/get/index.md",
         "https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/GET"),
        ("POST request method - HTTP | MDN", "web/http/reference/methods/post/index.md",
         "https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods/POST"),
        ("Idempotent - Glossary | MDN", "glossary/idempotent/index.md",
         "https://developer.mozilla.org/en-US/docs/Glossary/Idempotent"),
        ("HTTP response status codes - HTTP | MDN", "web/http/reference/status/index.md",
         "https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status"),
    ]:
        sources.append(src(title, url, "developer.mozilla.org", mdn_clean(get(base + path))[:9000],
                           base + path))
    return sources


def build_sql():
    pg_mirror = "https://raw.githubusercontent.com/postgres/postgres/master/doc/src/sgml/queries.sgml"
    lines = get(pg_mirror).splitlines()
    start = next(i for i, l in enumerate(lines) if "<term>Qualified joins" in l)
    end = next(i for i, l in enumerate(lines) if i > start and "clause is a shorthand that allows" in l)
    pg = sgml_text("\n".join(lines[start:end + 1]))
    ms_mirror = "https://raw.githubusercontent.com/MicrosoftDocs/sql-docs/live/docs/relational-databases/performance/joins.md"
    ms = get(ms_mirror).split("---", 2)[2]
    ms = re.sub(r":::[^\n]*\n", "", ms)
    ms = re.sub(r"\[!INCLUDE \[ssNoVersion\]\([^)]*\)\]", "SQL Server", ms)
    ms = re.sub(r"\[!INCLUDE \[[^\]]*\]\([^)]*\)\]", "", ms)
    ms = re.sub(r"<a id=[^>]*></a>", "", ms)
    ms = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", ms)
    ms = ms[: ms.find("## Nested Loops")] if "## Nested Loops" in ms else ms[:6000]
    return [
        src("PostgreSQL Documentation: 7.2. Table Expressions (Joined Tables)",
            "https://www.postgresql.org/docs/current/queries-table-expressions.html", "postgresql.org", pg,
            pg_mirror),
        src("Joins (SQL Server) - Microsoft Learn",
            "https://learn.microsoft.com/en-us/sql/relational-databases/performance/joins", "learn.microsoft.com",
            re.sub(r"\n{3,}", "\n\n", ms).strip()[:9000], ms_mirror),
    ]


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sources_http.json").write_text(json.dumps(build_http(), indent=2, ensure_ascii=False))
    (OUT / "sources_sql.json").write_text(json.dumps(build_sql(), indent=2, ensure_ascii=False))
    print("fixtures written to", OUT)

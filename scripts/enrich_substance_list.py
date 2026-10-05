"""
Fill missing PubChem IDs and Wikipedia links in examples/substance_list.csv.

Reads the semicolon-separated substance list, resolves the PubChem CID and the
English Wikipedia article for every substance whose columns are still empty,
and rewrites the CSV in place (preserving the leading note lines and header).

Run with: uv run scripts/enrich_substance_list.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "examples" / "substance_list.csv"
PUBCHEM_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/cids/JSON"
WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "flamecheck-data-enrichment/1.0 (contact: local script)"
SLEEP_PUBCHEM = 0.5  # be polite to the PUG REST API
SLEEP_WIKI = 0.2


def http_get_json(url: str) -> dict | None:
    """Fetch a URL and decode JSON, returning None on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            if attempt == 2:
                print(f"    WARN: {url} -> {exc}")
                return None
            time.sleep(2 * (attempt + 1))
    return None


def pubchem_cid(query: str) -> str:
    """Resolve a PubChem CID for a name or formula, or '' if not found."""
    data = http_get_json(PUBCHEM_URL.format(query=urllib.parse.quote(query)))
    if not isinstance(data, dict):
        return ""
    cids = data.get("IdentifierList", {}).get("CID")
    return str(cids[0]) if cids else ""


def wiki_title(query: str) -> str:
    """
    Resolve a Wikipedia article title for a query, or '' if no plausible match.

    Uses the MediaWiki search endpoint and accepts a hit only when the title
    matches the query closely (exact match, or one contains the other after
    normalising case and spaces).
    """
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": "5",
            "format": "json",
        }
    )
    data = http_get_json(f"{WIKI_SEARCH_URL}?{params}")
    if not isinstance(data, dict):
        return ""
    hits = data.get("query", {}).get("search", [])
    q = re.sub(r"\s+", " ", query).strip().lower()
    for hit in hits:
        title = hit.get("title", "")
        t = re.sub(r"\s+", " ", title).strip().lower()
        if t == q or (len(q) >= 4 and (q in t or t in q)):
            return title
    return ""


def candidate_queries(row: dict[str, str]) -> list[str]:
    """
    Ordered list of lookup queries for a substance row.

    For mixed-oxidation-state salts (e.g. 'Iron(II/III) bromide') the combined
    name does not exist as a compound, so the first listed oxidation state
    ('Iron(II) bromide') and the first listed formula are used as fallbacks.
    """
    name = row["name"].strip()
    queries = [name]
    fixed = re.sub(r"\((II)/III\)", "(II)", name)
    fixed = re.sub(r"\((II)/IV\)", "(II)", fixed)
    if fixed != name:
        queries.append(fixed)
    synonym = row.get("synonyms", "").strip()
    if synonym and synonym not in queries:
        queries.append(synonym)
    for formula in re.split(r"[/]", row.get("formula", "")):
        formula = formula.strip()
        if formula and formula not in queries:
            queries.append(formula)
    return queries


def main() -> None:
    raw_lines = CSV_PATH.read_text(encoding="utf-8").splitlines()
    # Layout: line 1 = note, line 2 = blank, line 3 = header, rest = data rows.
    header = raw_lines[2]
    rows = list(csv.reader(io.StringIO("\n".join(raw_lines[3:])), delimiter=";"))

    updated = 0
    for row in rows:
        if len(row) < 6:
            continue
        row_map = dict(zip(header.split(";"), row))
        queries = candidate_queries(row_map)

        if not row_map.get("pubchem_id", "").strip():
            cid = ""
            for q in queries:
                cid = pubchem_cid(q)
                time.sleep(SLEEP_PUBCHEM)
                if cid:
                    print(f"  pubchem {row_map['name']!r}: {q!r} -> {cid}")
                    break
            row[4] = cid

        if not row_map.get("wikipedia_link", "").strip():
            title = ""
            for q in queries:
                title = wiki_title(q)
                time.sleep(SLEEP_WIKI)
                if title:
                    print(f"  wiki    {row_map['name']!r}: {q!r} -> {title!r}")
                    break
            row[5] = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}" if title else ""
        updated += 1
        print(f"[{updated:2d}] {row_map['name']}")

    buf = io.StringIO()
    body = []
    for r in rows:
        buf.seek(0)
        buf.truncate(0)
        csv.writer(buf, delimiter=";").writerow(r)
        body.append(buf.getvalue().rstrip("\r\n"))
    CSV_PATH.write_text("\n".join([*raw_lines[:3], *body]) + "\n", encoding="utf-8")
    print(f"\nWrote {len(rows)} rows to {CSV_PATH}")


if __name__ == "__main__":
    main()

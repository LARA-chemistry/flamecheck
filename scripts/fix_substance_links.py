"""Verify and repair PubChem IDs and Wikipedia links in examples/substance_list.csv.

- Batch-resolves Wikipedia article titles through a small number of MediaWiki
  ``titles=`` requests (with redirect following), avoiding the per-query
  search rate limits.
- Verifies every PubChem CID through one PUG REST ``property/Title`` request,
  using a cache of already-verified CIDs (``scripts/.verified_cids.json``).
- Rewrites the CSV in place, sorted alphabetically by substance name.

Run with: uv run scripts/fix_substance_links.py
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.parse
import urllib.request

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "examples" / "substance_list.csv"
SNAPSHOT = BASE_DIR / "examples" / "substance_list_wiki.csv"
CID_CACHE = BASE_DIR / "scripts" / ".verified_cids.json"
TITLES_BATCH = 50  # MediaWiki limit for the ``titles`` parameter
WIKI_URL = "https://en.wikipedia.org/w/api.php"
PUBCHEM_PROPERTY_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cids}/property/Title/JSON"
USER_AGENT = "flamecheck-data-enrichment/1.0 (contact: local script)"

# Preferred article titles for rows whose stored link is missing or wrong,
# in order of preference (redirects are resolved by the API).
CANDIDATES: dict[str, list[str]] = {
    "Aluminum bromide": ["Aluminium bromide", "Aluminum bromide"],
    "Manganese bromide": ["Manganese(II) bromide", "Manganese bromide"],
    "Nickel(II) bromide": ["Nickel(II) bromide", "Nickel bromide"],
    "Aluminum acetate": ["Aluminium acetate", "Aluminum acetate"],
    "Iron(II/III) acetate": ["Iron(II) acetate", "Iron acetate"],
    "Tin(II/IV) acetate": ["Tin(II) acetate", "Tin(IV) acetate", "Tin acetate"],
    "Magnesium chloride": ["Magnesium chloride"],
    "Aluminum chloride": ["Aluminium chloride", "Aluminum chloride"],
    "Tin(II/IV) chloride": ["Tin(II) chloride", "Tin(IV) chloride", "Tin chloride"],
    "Aluminum carbonate": ["Aluminium carbonate", "Aluminum carbonate"],
    "Calcium carbonate": ["Calcium carbonate"],
    "Cobalt(II) carbonate": ["Cobalt(II) carbonate", "Cobalt carbonate"],
    "Sodium carbonate": ["Sodium carbonate"],
    "Ammonium carbonate": ["Ammonium carbonate"],
    "Manganese carbonate": ["Manganese(II) carbonate", "Manganese carbonate"],
    "Tin(II/IV) carbonate": ["Tin(II) carbonate", "Tin(IV) carbonate", "Tin carbonate"],
}


def http_get_json(url: str) -> dict | None:
    """Fetch a URL and decode JSON, returning None on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict) and "error" in data:
                    print(f"  WARN: {url} -> API error: {data['error']}")
                    return None
                return data
        except Exception as exc:
            if attempt == 3:
                print(f"  WARN: {url} -> {exc}")
                return None
            time.sleep(5 * (attempt + 1))
    return None


def snapshot_links() -> dict[str, str]:
    """Read name -> wikipedia_link pairs from the pre-wipe snapshot, if present."""
    if not SNAPSHOT.exists():
        return {}
    lines = SNAPSHOT.read_text(encoding="utf-8").splitlines()
    header = next((line for line in lines if line.startswith("name;")), "")
    if not header:
        return {}
    rows = list(csv.reader(io.StringIO("\n".join(lines[lines.index(header) + 1 :])), delimiter=";"))
    idx = {col: i for i, col in enumerate(header.split(";"))}
    return {r[idx["name"]].strip(): r[idx["wikipedia_link"]].strip() for r in rows if len(r) > idx["wikipedia_link"]}


def load_cache() -> dict[str, str]:
    """Load previously verified PubChem CIDs from the local cache file."""
    if CID_CACHE.exists():
        return json.loads(CID_CACHE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict[str, str]) -> None:
    """Persist verified PubChem CIDs to the local cache file."""
    CID_CACHE.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")


def resolve_titles(titles: list[str]) -> dict[str, str]:
    """Map each requested title to its canonical article title, '' if missing.

    Returns an empty dict when the API call fails entirely, so callers can
    fall back to previously stored links instead of wiping them.
    """
    resolved: dict[str, str] = {}
    for start in range(0, len(titles), TITLES_BATCH):
        chunk = titles[start : start + TITLES_BATCH]
        params = urllib.parse.urlencode(
            {"action": "query", "titles": "|".join(chunk), "redirects": "1", "format": "json"}
        )
        data = http_get_json(f"{WIKI_URL}?{params}")
        if not isinstance(data, dict) or "query" not in data:
            print(f"  WARN: title batch failed; keeping previously stored links")
            return resolved
        query = data["query"]
        redirects = {r["from"]: r["to"] for r in query.get("redirects", [])}
        normalized = {n["from"]: n["to"] for n in query.get("normalized", [])}
        pages = {p["title"]: p for p in query.get("pages", {}).values()}
        for requested in chunk:
            title = normalized.get(requested, requested)
            title = redirects.get(title, title)
            page = pages.get(title)
            resolved[requested] = page["title"] if page is not None and "missing" not in page else ""
        time.sleep(0.5)
    return resolved


def verify_cids(cids: list[str]) -> dict[str, str]:
    """Map each CID to the PubChem record title, '' if the CID does not exist.

    CIDs already in the local cache are not re-verified against PubChem.
    """
    cache = load_cache()
    for cid in cids:
        if cid in cache:
            cache.pop(cid)
    fresh = [cid for cid in cids if cid not in cache]
    titles: dict[str, str] = {cid: load_cache().get(cid, "") for cid in cids}
    if fresh:
        batch = ",".join(fresh)
        data = http_get_json(PUBCHEM_PROPERTY_URL.format(cids=batch))
        props = data.get("PropertyTable", {}).get("Properties", []) if isinstance(data, dict) else []
        if props:
            for prop in props:
                titles[str(prop["CID"])] = prop.get("Title", "")
        else:
            print("  batch CID check failed; falling back to per-CID requests")
            for cid in fresh:
                single = http_get_json(PUBCHEM_PROPERTY_URL.format(cids=cid))
                single_props = (
                    single.get("PropertyTable", {}).get("Properties", []) if isinstance(single, dict) else []
                )
                titles[cid] = single_props[0].get("Title", "") if single_props else ""
                time.sleep(0.5)
        for cid, title in titles.items():
            if title:
                cache[cid] = title
        save_cache(cache)
    return titles


def link_title(row: list[str]) -> str:
    """Extract the article title stored in the row's wikipedia_link column."""
    return row[5].strip().removeprefix("https://en.wikipedia.org/wiki/").replace("_", " ")


def main() -> None:
    raw_lines = CSV_PATH.read_text(encoding="utf-8").splitlines()
    header = raw_lines[2]
    rows = list(csv.reader(io.StringIO("\n".join(raw_lines[3:])), delimiter=";"))
    rows = [r for r in rows if len(r) >= 6]
    rows.sort(key=lambda r: r[0].strip())

    # 1. Resolve all candidate titles in batch (fall back to stored links on failure).
    snap = snapshot_links()
    wanted: set[str] = set()
    for row in rows:
        name = row[0].strip()
        if name in CANDIDATES:
            wanted.update(CANDIDATES[name])
        if link_title(row):
            wanted.add(link_title(row))
        if snap.get(name):
            wanted.add(snap[name])
    resolved = resolve_titles(sorted(wanted))

    # 2. Verify every PubChem CID (cached).
    cid_titles = verify_cids([row[4].strip() for row in rows])

    # 3. Pick the best title per row and rewrite the CSV.
    problems: list[str] = []
    for row in rows:
        name = row[0].strip()
        cid = row[4].strip()
        if cid and not cid_titles.get(cid):
            problems.append(f"{name}: PubChem CID {cid} not found")
            print(f"  !! {name}: CID {cid} NOT FOUND")
        candidates = CANDIDATES.get(name, [])
        stored = link_title(row)
        if stored:
            candidates.append(stored)
        if snap.get(name):
            candidates.append(snap[name])
        title = next((resolved[c] for c in candidates if resolved.get(c)), "")
        row[5] = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}" if title else ""
        if not title:
            problems.append(f"{name}: no Wikipedia article found")
            print(f"  !! {name}: no Wikipedia article found")
        print(f"{name}: CID={cid} ({cid_titles.get(cid, '?')!r}) wiki={title!r}")

    body = []
    buf = io.StringIO()
    for r in rows:
        buf.seek(0)
        buf.truncate(0)
        csv.writer(buf, delimiter=";").writerow(r)
        body.append(buf.getvalue().rstrip("\r\n"))
    note = (
        "The pubchem_id and wikipedia_link columns were filled by looking up each substance "
        "in PubChem (PUG REST) and on English Wikipedia. Rows are sorted alphabetically by name."
    )
    CSV_PATH.write_text("\n".join([note, "", header, *body]) + "\n", encoding="utf-8")

    print(f"\nWrote {len(rows)} rows to {CSV_PATH}")
    if problems:
        print(f"{len(problems)} unresolved items:")
        for p in problems:
            print(f"  - {p}")
    else:
        print("All 64 substances have a verified PubChem CID and Wikipedia link.")


if __name__ == "__main__":
    main()

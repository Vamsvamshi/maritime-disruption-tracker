"""
fetch_incidents.py — auto-update data/incidents.json from public sources.

Sources polled:
  1. CENTCOM press releases RSS  (public, no auth)
  2. UKMTO incident advisories   (public web page, scraped)

Auto-fetched incidents are added with "verified": false and lat/lon = null.
A human should review them, set coordinates, adjust severity, and set
"verified": true before the entries appear on the live map with full detail.

Usage:
  python scripts/fetch_incidents.py

GitHub Actions runs this daily at 06:00 UTC and commits any changes.
"""

import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
import xml.etree.ElementTree as ET

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "incidents.json"

# ── Source URLs ────────────────────────────────────────────────────────────────
# Verify these against the live sites if the fetch starts returning 404/403.
CENTCOM_RSS = (
    "https://www.centcom.mil/DesktopModules/ArticleCS/RSS.aspx"
    "?ContentType=1&Site=1&max=50"
)
UKMTO_URL = "https://www.ukmto.org/indian-ocean/incident-reports"

MARITIME_KEYWORDS = {
    "tanker", "vessel", "ship", "strait", "hormuz", "maritime", "persian gulf",
    "arabian gulf", "red sea", "black sea", "naval", "shipping", "lng", "houthi",
    "irgc", "iran", "drone strike", "mine", "attack", "seized", "fired upon",
    "warship", "explosion", "cargo ship", "oil tanker", "gas carrier",
}

UA = "SOH-Tracker/1.0 (public research; +https://github.com)"


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get(url: str, timeout: int = 20) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except URLError as exc:
        print(f"  [WARN] {url}: {exc}", file=sys.stderr)
        return None


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _is_maritime(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in MARITIME_KEYWORDS)


def _incident_id(date_str: str, title: str) -> str:
    digest = hashlib.sha1(f"{date_str}:{title}".encode()).hexdigest()[:8]
    return f"AUTO-{digest}"


def _parse_date(raw: str) -> str:
    """Parse RSS pubDate or ISO strings → YYYY-MM-DD."""
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _infer_region(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("hormuz", "persian gulf", "arabian gulf", "oman gulf", "iran", "irgc")):
        return "hormuz"
    if any(k in t for k in ("red sea", "bab el-mandeb", "houthi", "yemen", "bab-el-mandeb")):
        return "redsea"
    if any(k in t for k in ("black sea", "azov", "novorossiysk", "ukraine")):
        return "blacksea"
    if any(k in t for k in ("caspian", "kazakhstan", "cpc", "tengiz")):
        return "caspian"
    return "hormuz"  # CENTCOM default


# ── Sources ───────────────────────────────────────────────────────────────────
def fetch_centcom_rss() -> list[dict]:
    print("Fetching CENTCOM RSS…")
    raw = _get(CENTCOM_RSS)
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        print(f"  [WARN] RSS parse error: {exc}", file=sys.stderr)
        return []

    items = []
    for item in root.iter("item"):
        title   = (item.findtext("title") or "").strip()
        link    = (item.findtext("link")  or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        desc    = _strip_tags(item.findtext("description") or "")
        if _is_maritime(title + " " + desc):
            items.append({"title": title, "link": link, "pub_date": pub_date, "desc": desc})

    print(f"  → {len(items)} maritime-relevant items")
    return items


def fetch_ukmto_advisories() -> list[dict]:
    """
    UKMTO publishes plain-HTML advisories at UKMTO_URL.
    This is a best-effort scrape — adjust the selector if their layout changes.
    """
    print("Fetching UKMTO advisories…")
    raw = _get(UKMTO_URL)
    if not raw:
        return []

    html = raw.decode("utf-8", errors="replace")
    # Look for <a> links that point to individual advisories
    pattern = re.compile(
        r'href="([^"]*incident[^"]*)"[^>]*>\s*([^<]{10,120})', re.IGNORECASE
    )
    base = "https://www.ukmto.org"
    items = []
    for m in pattern.finditer(html):
        href, text = m.group(1).strip(), m.group(2).strip()
        if not href.startswith("http"):
            href = base + href
        # derive a rough date from the advisory text if present
        date_match = re.search(r"(\d{1,2}\s+\w+\s+\d{4})", text)
        pub_date = date_match.group(1) if date_match else ""
        items.append({"title": text, "link": href, "pub_date": pub_date, "desc": text})

    print(f"  → {len(items)} UKMTO links found")
    return [i for i in items if _is_maritime(i["title"])]


# ── Main ──────────────────────────────────────────────────────────────────────
def load_data() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"meta": {}, "incidents": []}


def save_data(data: dict) -> None:
    data["meta"]["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    data = load_data()
    existing_ids = {inc["id"] for inc in data["incidents"]}
    added = 0

    for raw_item in fetch_centcom_rss() + fetch_ukmto_advisories():
        date_str = _parse_date(raw_item["pub_date"])
        inc_id   = _incident_id(date_str, raw_item["title"])
        if inc_id in existing_ids:
            continue

        region = _infer_region(raw_item["title"] + " " + raw_item["desc"])
        new_inc = {
            "id":           inc_id,
            "date":         date_str,
            "region":       region,
            "location":     "See source — coordinates needed",
            "lat":          None,
            "lon":          None,
            "vessel":       None,
            "event":        raw_item["title"],
            "details":      raw_item["desc"][:500],
            "flow_impact":  "Pending assessment",
            "severity":     3,
            "fuel_type":    [],
            "verified":     False,
            "source_label": "CENTCOM / UKMTO (auto)",
            "source_url":   raw_item["link"],
        }
        data["incidents"].append(new_inc)
        existing_ids.add(inc_id)
        added += 1
        print(f"  [NEW] {date_str} — {raw_item['title'][:80]}")

    save_data(data)

    if added:
        print(f"\nAdded {added} new incident(s). Review items with \"verified\": false:")
        print("  • Set lat/lon coordinates")
        print("  • Adjust severity (1–5)")
        print("  • Set \"verified\": true to show full detail on the map")
    else:
        print("\nNo new incidents found. Timestamp updated.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

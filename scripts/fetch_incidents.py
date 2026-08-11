"""
fetch_incidents.py — polls 15+ credible public RSS feeds for new maritime,
energy, nuclear, and military incidents and appends them to data/incidents.json.

Sources: CENTCOM, UKMTO, BBC Middle East, Al Jazeera, OilPrice.com, Arab News,
Middle East Eye, Times of Israel, USNI News, Defense One, Breaking Defense,
gCaptain, Hellenic Shipping News, Splash247, Kyiv Post, UN News Middle East.

Auto-fetched incidents are added with "verified": false and lat/lon = null.
Review, add coordinates, adjust severity, and set "verified": true before
the entry shows full detail on the live map.
"""

import hashlib, json, re, sys, time
import urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

ROOT      = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "incidents.json"
UA        = "SOH-Tracker/2.0 (Deloitte ER&I public research)"

# ── All credible RSS sources ───────────────────────────────────────────────
RSS_FEEDS = [
    # Official / government
    ("CENTCOM",            "https://www.centcom.mil/DesktopModules/ArticleCS/RSS.aspx?ContentType=1&Site=1&max=50"),
    # Maritime / shipping
    ("gCaptain",           "https://gcaptain.com/feed/"),
    ("Hellenic Shipping",  "https://www.hellenicshippingnews.com/feed/"),
    ("Splash247",          "https://splash247.com/feed/"),
    ("Safety4Sea",         "https://safety4sea.com/feed/"),
    # Middle East news
    ("BBC Middle East",    "https://feeds.bbci.co.uk/news/world/middle-east/rss.xml"),
    ("Al Jazeera",         "https://www.aljazeera.com/xml/rss/all.xml"),
    ("OilPrice.com",       "https://oilprice.com/rss/main"),
    ("Arab News",          "https://www.arabnews.com/rss.xml"),
    ("Middle East Eye",    "https://www.middleeasteye.net/rss"),
    ("Times of Israel",    "https://www.timesofisrael.com/feed/"),
    # Defense / military
    ("USNI News",          "https://news.usni.org/feed"),
    ("Defense One",        "https://www.defenseone.com/rss/all/"),
    ("Breaking Defense",   "https://breakingdefense.com/feed/"),
    # Ukraine / Black Sea
    ("Kyiv Post",          "https://kyivpost.com/feed"),
    # UN / multilateral
    ("UN News ME",         "https://news.un.org/feed/subscribe/en/news/region/middle-east/feed/rss.xml"),
]

MARITIME_KEYWORDS = {
    "tanker","vessel","ship","strait","hormuz","maritime","persian gulf","arabian gulf",
    "red sea","bab el-mandeb","black sea","azov","novorossiysk","houthi","irgc","iran",
    "drone strike","mine","attack","seized","fired upon","warship","explosion",
    "cargo ship","oil tanker","gas carrier","nuclear","natanz","fordow","bushehr",
    "arak","isfahan","parchin","missile","airstrike","air strike","military base",
    "abadan","kharg","fujairah","ras laffan","aramco","abqaiq","cpc","kazakhstan",
    "shadow fleet","ukraine","russia","oil price","brent","lng","refinery","pipeline",
    "chokepoint","blockade","embargo","sanctions","iaea","centcom","5th fleet",
}

def _get(url: str, timeout: int = 20) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except URLError as e:
        print(f"  [WARN] {url[:60]}: {e}", file=sys.stderr)
        return None

def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()

def _is_relevant(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in MARITIME_KEYWORDS)

def _incident_id(date_str: str, title: str) -> str:
    return "AUTO-" + hashlib.sha1(f"{date_str}:{title}".encode()).hexdigest()[:8]

def _parse_date(raw: str) -> str:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
                "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _infer_region(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("hormuz","persian gulf","arabian gulf","iran","irgc","abadan","kharg","oman")):
        return "hormuz"
    if any(k in t for k in ("red sea","bab el-mandeb","houthi","yemen","aqaba")):
        return "redsea"
    if any(k in t for k in ("black sea","azov","novorossiysk","ukraine","russia","cpc")):
        return "blacksea"
    if any(k in t for k in ("caspian","kazakhstan","tengiz","kashagan")):
        return "caspian"
    if any(k in t for k in ("natanz","fordow","bushehr","isfahan","arak","parchin","nuclear","iaea")):
        return "iran"
    if any(k in t for k in ("iraq","erbil","baghdad","basra","anbar")):
        return "iraq"
    if any(k in t for k in ("saudi","aramco","abqaiq","riyadh")):
        return "saudi"
    return "hormuz"

def _infer_category(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("nuclear","natanz","fordow","bushehr","arak","parchin","iaea","enrichment","centrifuge")):
        return "nuclear"
    if any(k in t for k in ("refinery","terminal","pipeline","oil facility","aramco","abqaiq","kharg","abadan","ras laffan")):
        return "oilinfra"
    if any(k in t for k in ("lng","lpg","gas carrier","gas plant","south pars")):
        return "gas"
    if any(k in t for k in ("air base","military base","tower 22","al asad","al udeid","nsab","5th fleet","pentagon","centcom","airstrike","air strike","missile strike","cruise missile","bombers")):
        return "military"
    if any(k in t for k in ("base attack","base struck","base hit","soldiers killed","troops killed")):
        return "base"
    if any(k in t for k in ("houthi","militia","hezbollah","proxy","islamic resistance")):
        return "militia"
    if any(k in t for k in ("ceasefire","agreement","mou","memorandum","diplomacy","talks","negotiation","iaea")):
        return "diplomatic"
    if any(k in t for k in ("tanker","vessel","ship","shipping","maritime","port","fleet","cargo","chokepoint")):
        return "maritime"
    return "maritime"

def fetch_rss(source: str, url: str) -> list[dict]:
    raw = _get(url)
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"  [WARN] {source} parse error: {e}", file=sys.stderr)
        return []
    items, seen = [], set()
    for item in root.iter("item"):
        title    = _strip_tags(item.findtext("title")       or "")
        link     = (item.findtext("link")                   or "").strip()
        pub_date = (item.findtext("pubDate")                or "").strip()
        desc     = _strip_tags(item.findtext("description") or "")[:600]
        combined = title + " " + desc
        if _is_relevant(combined) and title not in seen:
            seen.add(title)
            items.append({"source": source, "title": title, "link": link,
                          "pub_date": pub_date, "desc": desc})
    return items

def fetch_ukmto() -> list[dict]:
    raw = _get("https://www.ukmto.org/indian-ocean/incident-reports")
    if not raw:
        return []
    html  = raw.decode("utf-8", errors="replace")
    base  = "https://www.ukmto.org"
    items = []
    for m in re.finditer(r'href="([^"]*incident[^"]*)"[^>]*>\s*([^<]{10,120})', html, re.I):
        href, text = m.group(1).strip(), m.group(2).strip()
        if not href.startswith("http"):
            href = base + href
        if _is_relevant(text):
            items.append({"source":"UKMTO","title":text,"link":href,"pub_date":"","desc":text})
    return items

def load_data() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8")) if DATA_FILE.exists() else {"meta":{},"incidents":[]}

def save_data(data: dict) -> None:
    data["meta"]["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def main() -> int:
    data         = load_data()
    existing_ids = {inc["id"] for inc in data["incidents"]}
    added        = 0

    all_items: list[dict] = []
    for source, url in RSS_FEEDS:
        print(f"Fetching {source}...")
        items = fetch_rss(source, url)
        print(f"  -> {len(items)} relevant items")
        all_items.extend(items)
        time.sleep(0.3)  # be polite to servers

    all_items.extend(fetch_ukmto())

    for item in all_items:
        date_str = _parse_date(item["pub_date"])
        inc_id   = _incident_id(date_str, item["title"])
        if inc_id in existing_ids:
            continue
        combined  = item["title"] + " " + item["desc"]
        region    = _infer_region(combined)
        category  = _infer_category(combined)
        new_inc = {
            "id":           inc_id,
            "date":         date_str,
            "region":       region,
            "category":     category,
            "location":     "See source — coordinates needed",
            "lat":          None,
            "lon":          None,
            "vessel":       None,
            "event":        item["title"],
            "details":      item["desc"][:500],
            "flow_impact":  "Pending assessment",
            "severity":     3,
            "fuel_type":    [],
            "verified":     False,
            "source_label": item["source"],
            "source_url":   item["link"],
        }
        data["incidents"].append(new_inc)
        existing_ids.add(inc_id)
        added += 1
        print(f"  [NEW] {date_str} | {category.upper():10} | {item['source']:18} | {item['title'][:70]}")

    save_data(data)

    if added:
        print(f"\nAdded {added} new incident(s).")
        print("Review items with \"verified\": false — set lat/lon, severity, and verified:true.")
    else:
        print("\nNo new incidents. Timestamp updated.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

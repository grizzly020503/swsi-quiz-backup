#!/usr/bin/env python3
import argparse
import calendar
import hashlib
import html
import json
import re
import socket
import time
from types import SimpleNamespace
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

from current_affairs_taxonomy import (
    canonical_agencies,
    canonical_concepts,
    canonical_fact_keys,
    concept_category_counts,
    concept_tags,
    english_policy_hits,
    is_english_dominant,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REGISTRY = ROOT / "data" / "current_affairs_sources.json"

DEFAULT_FEEDS = [
    {"name":"衛生福利部焦點新聞","url":"https://www.mohw.gov.tw/rss-16-1.html","region":"taiwan"},
    {"name":"衛生福利部公告訊息","url":"https://www.mohw.gov.tw/rss-18-1.html","region":"taiwan"},
    {"name":"中央社社會","url":"https://feeds.feedburner.com/rsscna/social","region":"taiwan"},
    {"name":"中央社生活","url":"https://feeds.feedburner.com/rsscna/lifehealth","region":"taiwan"},
    {"name":"中央社政治","url":"https://feeds.feedburner.com/rsscna/politics","region":"taiwan"},
    {"name":"中央社國際","url":"https://feeds.feedburner.com/rsscna/intworld","region":"international"},
]


def load_feeds():
    if SOURCE_REGISTRY.exists():
        try:
            payload = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
            rows = payload.get("sources") or []
            valid = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "").strip()
                url = str(row.get("url") or "").strip()
                region = str(row.get("region") or "").strip()
                source_type = str(row.get("source_type") or "news").strip()
                source_format = str(row.get("source_format") or "rss").strip()
                if (
                    name
                    and url.startswith("https://")
                    and region in {"taiwan", "international"}
                    and source_format in {"rss", "who_newsroom_json"}
                ):
                    valid.append({
                        "name": name,
                        "url": url,
                        "region": region,
                        "source_type": source_type if source_type in {"official", "news", "international"} else "news",
                        "source_format": source_format,
                    })
            if valid:
                return valid
        except Exception as exc:
            print(f"Source registry fallback: {exc}")
    return [dict(x, source_type=x.get("source_type", "news")) for x in DEFAULT_FEEDS]


CATEGORIES = [
    ("兒少保護", 4, ["兒虐","虐童","兒少保護","兒童權利","性剝削","托嬰","保母","安置","收出養","寄養","兒少","兒童","少年"]),
    ("家暴與性暴力", 4, ["家暴","家庭暴力","性侵","性暴力","性騷擾","跟蹤騷擾","保護令","性影像"]),
    ("心理健康與成癮", 3, ["心理健康","精神衛生","精神疾病","自殺","自傷","成癮","毒品","酒癮"]),
    ("長照與高齡", 3, ["長照","高齡","老人","失智","照顧者","住宿機構","居家照顧"]),
    ("社會救助與居住", 3, ["社會救助","低收入","中低收入","貧窮","弱勢家庭","街友","無家者","租屋","居住權","住宅"]),
    ("身障與人權", 3, ["身心障礙","身障","無障礙","CRPD","人權公約","合理調整"]),
    ("移工與新住民", 3, ["移工","外籍勞工","新住民","移民","難民","人口販運"]),
    ("勞動與社會保障", 3, ["勞保","就業保險","職業災害","職災","育嬰留職停薪","性別平等工作法","就業歧視","職場霸凌","勞工權益","失業給付","就業服務","身障就業","庇護工場","最低工資","勞退"]),
    ("教育與學生輔導", 3, ["學生輔導","校園霸凌","中途輟學","中輟","特殊教育","身心障礙學生","校園性別事件","學校社工","青少年輔導","弱勢學生"]),
    ("司法保護與修復式司法", 4, ["犯罪被害人","被害人保護","犯罪被害人權益保障","修復式司法","更生保護","保護管束","榮譽觀護人","觀護人","社區矯治","社區處遇","社會勞動","戒癮處遇","被害補償金"]),
    ("少年司法與犯罪防治", 3, ["少年事件","少年司法","少年犯罪","少年觀護","觸法少年"]),
    ("性別與家庭政策", 2, ["性別平等","婦女","育兒","托育","家庭政策","少子化","生育","婚姻平權"]),
    ("災害與社區工作", 2, ["災害救助","災民","安置中心","撤離","避難","社區韌性","震災","颱風","洪水","土石流"]),
    ("社工專業與社福制度", 4, ["社工","社會工作","社福","社會福利","社安網","保護服務","責任通報","通報制度","脆弱家庭"]),
]

CATEGORY_BASE = {category: base for category, base, _words in CATEGORIES}

POLICY_TERMS = ["修法","修正","政策","制度","改革","通報","補助","津貼","權益","福利","保護","安置","服務量能","人力不足","監察","行政院","衛福部","條例","施行細則","法規","草案","預告","指引","要點","給付","保險","保障"]
INTERNATIONAL_CORE = ["兒童權利","社會福利","社會政策","移民","難民","人權","心理健康","高齡","家暴","性暴力","災害","貧窮","身心障礙"]
LOW_VALUE_TERMS = ["好禮","選購","愛心捐贈","公益捐贈","徵求","招標","採購","徵件","動漫菸品","疫苗","流感","登革熱","牙醫醫療站","競賽","招生","徵才","表揚","書展","文化幣","科普","論壇","新書發表","急診","熱傷害","頒獎","典禮","成果發表","模擬投票","築夢","博覽會","開講","接見","訪問團","投資環境","評選","涉詐","詐領","起訴","演練","防衛韌性","課桌椅","揭牌","聯展","音樂會","媒體報導","澄清","駁斥","與事實不符"]
CHILD_WEAK = {"兒少","兒童","少年","保母"}
CHILD_STRONG = ["兒少保護","兒虐","虐童","兒童權利","性剝削","托嬰","安置","收出養","寄養","責任通報","兒童及少年福利與權益保障法","兒童權利公約","兒少生活狀況","生活狀況調查"]
FAMILY_POLICY_STRONG = ["托育","育兒","少子化","家庭政策","性別平等","育嬰留職停薪"]
DISASTER_STRONG = ["災害救助","災民","安置","撤離","避難","社區韌性"]
SUBJECT_MAP = {
    "兒少保護":["社會工作直接服務","社會政策與社會立法","社會工作"],
    "家暴與性暴力":["社會工作直接服務","社會政策與社會立法"],
    "心理健康與成癮":["人類行為與社會環境","社會工作直接服務"],
    "長照與高齡":["社會政策與社會立法","社會工作直接服務"],
    "社會救助與居住":["社會政策與社會立法","社會工作"],
    "身障與人權":["社會政策與社會立法","社會工作"],
    "移工與新住民":["社會工作","社會政策與社會立法"],
    "勞動與社會保障":["社會政策與社會立法","社會工作"],
    "教育與學生輔導":["社會工作直接服務","社會政策與社會立法","社會工作"],
    "司法保護與修復式司法":["社會工作直接服務","社會政策與社會立法","社會工作"],
    "少年司法與犯罪防治":["社會工作直接服務","社會政策與社會立法"],
    "性別與家庭政策":["社會政策與社會立法","社會工作"],
    "災害與社區工作":["社會工作","社會工作直接服務"],
    "社工專業與社福制度":["社會工作","社會工作直接服務","社會政策與社會立法"],
}


def parse_feed_with_retry(feed, attempts=3):
    last_error = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            parsed = feedparser.parse(
                feed["url"],
                request_headers={"User-Agent":"swsi-current-affairs-radar/1.1"},
            )
            if not (getattr(parsed, "bozo", False) and not parsed.entries):
                return parsed, None
            last_error = getattr(parsed, "bozo_exception", "RSS parse failed")
        except Exception as exc:
            parsed = None
            last_error = exc
        if attempt < attempts:
            print(f"Feed RETRY: {feed['name']} attempt={attempt} error={last_error}")
            time.sleep(0.5 * attempt)
    return parsed, last_error


def _who_item_link(raw_url):
    raw = str(raw_url or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("/news/"):
        return urljoin("https://www.who.int", raw)
    if raw.startswith("/"):
        return "https://www.who.int/news/item" + raw
    return urljoin("https://www.who.int/news/item/", raw)


def parse_who_newsroom_with_retry(feed, attempts=3):
    last_error = None
    ordered_url = feed["url"] + "?%24orderby=PublicationDate%20desc&%24top=100"
    for attempt in range(1, max(1, attempts) + 1):
        try:
            request = Request(
                ordered_url,
                headers={
                    "User-Agent": "swsi-current-affairs-radar/1.1",
                    "Accept": "application/json",
                },
            )
            with urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
            rows = payload.get("value") if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                raise ValueError("WHO Newsroom API payload missing value list")
            entries = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                title = clean_html(row.get("Title") or row.get("MetaTitle") or "")
                link = _who_item_link(row.get("ItemDefaultUrl") or "")
                summary = clean_html(
                    row.get("OpenGraphDescription")
                    or row.get("MetaDescription")
                    or row.get("Summary")
                    or row.get("Description")
                    or ""
                )[:600]
                raw_pub = (
                    row.get("PublicationDateAndTime")
                    or row.get("PublicationDate")
                    or row.get("DateCreated")
                )
                published_parsed = None
                if raw_pub:
                    try:
                        dt = datetime.fromisoformat(str(raw_pub).replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        published_parsed = dt.astimezone(timezone.utc).timetuple()
                    except (TypeError, ValueError):
                        published_parsed = None
                if title and link:
                    entries.append(SimpleNamespace(
                        title=title,
                        link=link,
                        summary=summary,
                        description=summary,
                        published_parsed=published_parsed,
                    ))
            if not entries:
                raise ValueError("WHO Newsroom API returned no usable entries")
            return SimpleNamespace(entries=entries, bozo=False), None
        except Exception as exc:
            last_error = exc
        if attempt < attempts:
            print(f"Feed RETRY: {feed['name']} attempt={attempt} error={last_error}")
            time.sleep(0.5 * attempt)
    return None, last_error


def parse_source_with_retry(feed, attempts=3):
    if feed.get("source_format", "rss") == "who_newsroom_json":
        return parse_who_newsroom_with_retry(feed, attempts=attempts)
    return parse_feed_with_retry(feed, attempts=attempts)


def clean_html(value):
    s = html.unescape(str(value or ""))
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def published_iso(entry):
    st = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not st:
        return None
    return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def score_english_international(title, summary, source_type="news"):
    text = f"{title} {summary}"
    concepts = canonical_concepts(text)
    if not concepts:
        return None
    category_counts = concept_category_counts(concepts)
    if not category_counts:
        return None

    title_concepts = canonical_concepts(title)
    policy_hits = english_policy_hits(text)
    if not title_concepts and not (len(concepts) >= 2 and policy_hits):
        return None

    category = max(
        category_counts,
        key=lambda name: (category_counts[name], CATEGORY_BASE.get(name, 0), name),
    )
    category_concepts = {
        key for key in concepts
        if concept_category_counts([key]).get(category)
    }
    base = max(4, CATEGORY_BASE.get(category, 3))
    score = base + min(2, max(0, len(category_concepts) - 1))
    if policy_hits:
        score += 1
    if source_type in {"official", "international"}:
        score += 1
    # International stories need stronger evidence than Taiwan-source stories.
    score -= 1
    if score < 5:
        return None

    tags = concept_tags(concepts)[:8]
    return min(10, score), category, tags


def score_item(title, summary, region, source_name, source_type="news"):
    text = f"{title} {summary}"
    if region == "international" and is_english_dominant(text):
        return score_english_international(title, summary, source_type)
    policy_hits = [w for w in POLICY_TERMS if w in text]
    best = None
    best_hits = []
    for category, base, words in CATEGORIES:
        title_hits = [w for w in words if w in title]
        all_hits = [w for w in words if w in text]
        if not all_hits:
            continue
        # RSS 摘要偶爾會帶到不相干關鍵字；沒有標題命中時必須至少兩個考點詞且有制度/政策訊號。
        if not title_hits and not (len(all_hits) >= 2 and policy_hits):
            continue
        # 「兒童／少年」本身太寬；即使官方摘要含政策字眼，也不能把
        # 書展、醫療衛教或科普活動誤當成兒少保護。弱標題命中時必須有明確
        # 保護／權利／法規／生活狀況調查脈絡。
        if category == "兒少保護" and title_hits and set(title_hits).issubset(CHILD_WEAK):
            if not any(w in text for w in CHILD_STRONG):
                continue
        # 單純天災新聞不納入；要與安置、撤離、救助、社區韌性等社工議題相連。
        if category == "災害與社區工作" and not any(w in text for w in DISASTER_STRONG):
            continue
        score = base + min(2, max(0, len(title_hits)-1))
        if policy_hits:
            score += 1
        if category == "性別與家庭政策" and policy_hits and any(w in title for w in FAMILY_POLICY_STRONG):
            score += 1
        # 標題直接命中只作同分時的分類優先依據，不直接灌 relevance 分數。
        # 這可避免「特殊教育＋公益活動」「長照＋刑案」只靠單一主題詞過門檻。
        title_evidence = len(title_hits)
        candidate = (score, title_evidence, category)
        if best is None or candidate[:2] > best[:2]:
            best = candidate
            best_hits = all_hits
    if best is None:
        return None
    score, _title_evidence, category = best
    if source_type == "official":
        score += 1
    if any(w in title for w in LOW_VALUE_TERMS):
        score -= 3
    if region == "international":
        if not any(w in text for w in INTERNATIONAL_CORE):
            return None
        score -= 1
    if score < 5:
        return None
    tags = list(dict.fromkeys(best_hits + policy_hits[:3]))[:10]
    return min(10, score), category, tags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="/tmp/current_affairs_payload.json")
    ap.add_argument("--days", type=int, default=21)
    args = ap.parse_args()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, args.days))
    items = {}
    fetched = 0
    feed_errors = []

    feeds = load_feeds()
    socket.setdefaulttimeout(12)
    for feed in feeds:
        parsed, parse_error = parse_source_with_retry(feed)
        if parsed is None or parse_error is not None:
            error = f"{feed['name']}: {parse_error or 'RSS parse failed'}"
            feed_errors.append(error)
            print(f"Feed ERROR: {error}")
            continue
        entry_count = len(parsed.entries or [])
        print(f"Feed OK: {feed['name']} entries={entry_count} format={feed.get('source_format', 'rss')}")
        for entry in parsed.entries:
            fetched += 1
            title = clean_html(getattr(entry, "title", ""))
            raw_link = str(getattr(entry, "link", "") or "").strip()
            link = urljoin(feed["url"], raw_link) if raw_link else ""
            summary = clean_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))[:600]
            pub = published_iso(entry)
            if not title or not link:
                continue
            if pub:
                try:
                    if datetime.fromisoformat(pub.replace("Z", "+00:00")) < cutoff:
                        continue
                except Exception:
                    pass
            scored = score_item(title, summary, feed["region"], feed["name"], feed.get("source_type", "news"))
            if not scored:
                continue
            score, category, tags = scored
            item_id = hashlib.sha256(link.encode("utf-8")).hexdigest()[:32]
            concept_keys = sorted(canonical_concepts(f"{title} {summary}"))
            agency_keys = sorted(canonical_agencies(f"{title} {summary}"))
            fact_keys = sorted(canonical_fact_keys(f"{title} {summary}"))
            row = {
                "id": item_id,
                "title": title[:500],
                "summary": summary,
                "source_name": feed["name"],
                "source_url": link,
                "source_feed": feed["url"],
                "source_type": feed.get("source_type", "news"),
                "published_at": pub,
                "region": feed["region"],
                "category": category,
                "relevance_score": score,
                "exam_tags": tags,
                "subjects": SUBJECT_MAP.get(category, ["社會工作"]),
                "concept_keys": concept_keys,
                "agency_keys": agency_keys,
                "fact_keys": fact_keys,
            }
            old = items.get(item_id)
            if old is None or row["relevance_score"] > old["relevance_score"]:
                items[item_id] = row

    accepted = sorted(items.values(), key=lambda x: (x["relevance_score"], x.get("published_at") or ""), reverse=True)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "fetched_count": fetched,
        "accepted_count": len(accepted),
        "feed_count": len(feeds),
        "feed_errors": feed_errors,
        "items": accepted[:100],
    }
    p = Path(args.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Current affairs radar: fetched={fetched}, accepted={len(accepted)}, errors={len(feed_errors)}")
    for row in accepted[:20]:
        print(f"[{row['relevance_score']}] {row['category']} | {row['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

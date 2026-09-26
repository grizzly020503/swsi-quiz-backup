#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from datetime import datetime

STOP_TAGS = {
    "政策", "制度", "福利", "保護", "行政院", "衛福部", "修正", "補助", "津貼",
    "高齡", "兒少", "兒童", "少年", "服務", "通報",
}

EXPLICIT_TOPICS = [
    ("longterm-care-3", "長照 3.0", ("長照3.0", "長照 3.0")),
    ("mental-health-act-rules", "精神衛生法施行細則", ("精神衛生法施行細則",)),
    ("child-growth-account", "臺灣兒少成長及未來帳戶", ("臺灣兒少成長及未來帳戶", "兒少成長及未來帳戶")),
]

ALLOWED = {
    "id", "title", "summary", "source_name", "source_url", "source_type", "published_at", "region",
    "category", "relevance_score", "exam_tags", "subjects",
    "concept_keys", "agency_keys", "fact_keys",
    "knowledge_root", "management_domains", "exam_subject_axes", "knowledge_topics",
}


def clean_row(row):
    out = {k: row.get(k) for k in ALLOWED if k in row}
    out["summary"] = str(out.get("summary") or "")[:280]
    out["exam_tags"] = list(dict.fromkeys(out.get("exam_tags") or []))[:10]
    out["subjects"] = list(dict.fromkeys(out.get("subjects") or []))
    out["concept_keys"] = list(dict.fromkeys(out.get("concept_keys") or []))
    out["agency_keys"] = list(dict.fromkeys(out.get("agency_keys") or []))
    out["fact_keys"] = list(dict.fromkeys(out.get("fact_keys") or []))
    out["knowledge_root"] = str(out.get("knowledge_root") or "")
    out["management_domains"] = list(dict.fromkeys(out.get("management_domains") or []))
    out["exam_subject_axes"] = list(dict.fromkeys(out.get("exam_subject_axes") or []))
    out["knowledge_topics"] = list(dict.fromkeys(out.get("knowledge_topics") or []))
    return out


def text_of(row):
    return f"{row.get('title') or ''} {row.get('summary') or ''}"


def law_names(row):
    # 官方新聞常以《法規名稱》標示；相同法規視為同一制度議題。
    return set(re.findall(r"《([^》]{2,40})》", text_of(row)))


def explicit_topic(row):
    text = text_of(row)
    for key, label, needles in EXPLICIT_TOPICS:
        if any(n in text for n in needles):
            return key, label
    return None


def informative_tags(row):
    return {str(x).strip() for x in (row.get("exam_tags") or []) if str(x).strip() and str(x).strip() not in STOP_TAGS}


def _within_days(a, b, days=3):
    try:
        da = datetime.fromisoformat(str(a or "").replace("Z", "+00:00"))
        db = datetime.fromisoformat(str(b or "").replace("Z", "+00:00"))
    except ValueError:
        return False
    return abs((da - db).total_seconds()) <= days * 86400


def _same_publisher_fact_duplicate(row, member):
    if str(row.get("source_name") or "") != str(member.get("source_name") or ""):
        return False
    if not _within_days(row.get("published_at"), member.get("published_at"), days=3):
        return False
    shared_facts = {
        str(x) for x in (row.get("fact_keys") or []) if str(x)
    }.intersection({
        str(x) for x in (member.get("fact_keys") or []) if str(x)
    })
    if not shared_facts:
        return False
    shared_tags = informative_tags(row).intersection(informative_tags(member))
    return bool(shared_tags)


def should_merge(row, cluster):
    first = cluster[0]
    if row.get("category") != first.get("category"):
        return False

    a_exp = explicit_topic(row)
    b_exp = explicit_topic(first)
    if a_exp or b_exp:
        return bool(a_exp and b_exp and a_exp[0] == b_exp[0])

    a_laws = law_names(row)
    b_laws = set().union(*(law_names(x) for x in cluster))
    if a_laws and b_laws and a_laws.intersection(b_laws):
        return True

    # Same publisher may issue multiple headlines for the same case. Merge only
    # when there are two independent anchors: a shared canonical fact (e.g.
    # the same significant amount) and a shared informative exam tag, within
    # a short time window. This prevents repeated articles from inflating a
    # trend while failing closed on unrelated stories.
    if any(_same_publisher_fact_duplicate(row, member) for member in cluster):
        return True

    a = informative_tags(row)
    b = set().union(*(informative_tags(x) for x in cluster))
    if not a or not b:
        return False
    shared = a.intersection(b)
    union = a.union(b)
    # 非明確政策名稱時採高門檻，避免把同類別不同新聞誤併。
    return len(shared) >= 3 and (len(shared) / max(1, len(union))) >= 0.60


def merge_cluster(cluster):
    members = sorted(
        cluster,
        key=lambda x: (int(x.get("relevance_score") or 0), x.get("published_at") or ""),
        reverse=True,
    )
    latest = max(members, key=lambda x: x.get("published_at") or "")
    representative = members[0]
    explicit = explicit_topic(representative)

    urls = []
    sources = []
    all_tags = []
    all_subjects = []
    all_concepts = []
    all_agencies = []
    all_facts = []
    for row in sorted(members, key=lambda x: x.get("published_at") or "", reverse=True):
        url = row.get("source_url") or ""
        if url and url not in urls:
            urls.append(url)
            sources.append({
                "source_name": row.get("source_name"),
                "source_url": url,
                "source_type": row.get("source_type") or "news",
                "published_at": row.get("published_at"),
                "title": row.get("title"),
            })
        all_tags.extend(row.get("exam_tags") or [])
        all_subjects.extend(row.get("subjects") or [])
        all_concepts.extend(row.get("concept_keys") or [])
        all_agencies.extend(row.get("agency_keys") or [])
        all_facts.extend(row.get("fact_keys") or [])

    article_count = len(urls) or len(members)
    source_names = {
        str(src.get("source_name") or "").strip()
        for src in sources
        if str(src.get("source_name") or "").strip()
    }
    source_count = len(source_names) or 1
    base_score = max(int(x.get("relevance_score") or 0) for x in members)
    # Repeated articles from the same publisher do not increase source coverage.
    coverage_bonus = 0 if source_count <= 1 else (1 if source_count <= 3 else 2)
    score = min(10, base_score + coverage_bonus)

    if explicit and source_count > 1:
        title = f"{explicit[1]}：近期制度與實務動態"
        topic_key = explicit[0]
    else:
        title = representative.get("title")
        topic_key = explicit[0] if explicit else representative.get("id")

    out = dict(representative)
    out.update({
        "id": f"topic:{topic_key}" if article_count > 1 else representative.get("id"),
        "title": title,
        "published_at": latest.get("published_at"),
        "source_name": representative.get("source_name") if source_count == 1 else f"綜合 {source_count} 個來源",
        "source_url": latest.get("source_url") or representative.get("source_url"),
        "relevance_score": score,
        "exam_tags": list(dict.fromkeys(all_tags))[:10],
        "subjects": list(dict.fromkeys(all_subjects)),
        "concept_keys": list(dict.fromkeys(all_concepts)),
        "agency_keys": list(dict.fromkeys(all_agencies)),
        "fact_keys": list(dict.fromkeys(all_facts)),
        "source_count": source_count,
        "article_count": article_count,
        "sources": sources,
        "clustered": len(members) > 1,
    })
    return out


def build(items):
    cleaned = [clean_row(x) for x in items]
    cleaned.sort(key=lambda x: (int(x.get("relevance_score") or 0), x.get("published_at") or ""), reverse=True)
    clusters = []
    for row in cleaned:
        target = None
        for cluster in clusters:
            if should_merge(row, cluster):
                target = cluster
                break
        if target is None:
            clusters.append([row])
        else:
            target.append(row)

    topics = [merge_cluster(c) for c in clusters]
    topics.sort(key=lambda x: (int(x.get("relevance_score") or 0), x.get("published_at") or ""), reverse=True)
    return topics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/tmp/current_affairs_payload.json")
    ap.add_argument("--output", default="auto/current_affairs.json")
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    src = json.loads(Path(args.input).read_text(encoding="utf-8"))
    topics = build(src.get("items", []))[: max(1, args.limit)]
    public = {
        "schema_version": 2,
        "source_feed_count": int(src.get("feed_count") or 0),
        "feed_error_count": len(src.get("feed_errors") or []),
        "optional_feed_error_count": len(src.get("optional_feed_errors") or []),
        "items": topics,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    old = None
    if out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            old = None

    if old == public:
        print(f"Public current-affairs snapshot unchanged: {len(topics)} topics")
        return 0

    out.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    merged = sum(1 for x in topics if x.get("clustered"))
    print(f"Public current-affairs snapshot updated: {len(topics)} topics, {merged} merged clusters")
    for row in topics[:10]:
        print(
            f"[{row.get('relevance_score')}] {row.get('source_count')} source(s) / "
            f"{row.get('article_count', row.get('source_count'))} article(s) | {row.get('title')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

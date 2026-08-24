#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

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
    "id", "title", "summary", "source_name", "source_url", "published_at", "region",
    "category", "relevance_score", "exam_tags", "subjects",
}


def clean_row(row):
    out = {k: row.get(k) for k in ALLOWED if k in row}
    out["summary"] = str(out.get("summary") or "")[:280]
    out["exam_tags"] = list(dict.fromkeys(out.get("exam_tags") or []))[:10]
    out["subjects"] = list(dict.fromkeys(out.get("subjects") or []))
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
    for row in sorted(members, key=lambda x: x.get("published_at") or "", reverse=True):
        url = row.get("source_url") or ""
        if url and url not in urls:
            urls.append(url)
            sources.append({
                "source_name": row.get("source_name"),
                "source_url": url,
                "published_at": row.get("published_at"),
                "title": row.get("title"),
            })
        all_tags.extend(row.get("exam_tags") or [])
        all_subjects.extend(row.get("subjects") or [])

    count = len(urls) or len(members)
    base_score = max(int(x.get("relevance_score") or 0) for x in members)
    coverage_bonus = 0 if count <= 1 else (1 if count <= 3 else 2)
    score = min(10, base_score + coverage_bonus)

    if explicit and count > 1:
        title = f"{explicit[1]}：近期制度與實務動態"
        topic_key = explicit[0]
    else:
        title = representative.get("title")
        topic_key = explicit[0] if explicit else representative.get("id")

    out = dict(representative)
    out.update({
        "id": f"topic:{topic_key}" if count > 1 else representative.get("id"),
        "title": title,
        "published_at": latest.get("published_at"),
        "source_name": representative.get("source_name") if count == 1 else f"綜合 {count} 則來源",
        "source_url": latest.get("source_url") or representative.get("source_url"),
        "relevance_score": score,
        "exam_tags": list(dict.fromkeys(all_tags))[:10],
        "subjects": list(dict.fromkeys(all_subjects)),
        "source_count": count,
        "sources": sources,
        "clustered": count > 1,
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
    public = {"schema_version": 2, "items": topics}

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
        print(f"[{row.get('relevance_score')}] {row.get('source_count')} source(s) | {row.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

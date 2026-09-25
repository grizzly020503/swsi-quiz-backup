#!/usr/bin/env python3
"""Deterministic event clustering helpers for SWSI current-affairs V2.

This module is intentionally model-free. It groups clearly similar current-affairs
items into canonical events while failing closed when evidence is weak.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Iterable

PUNCT_RE = re.compile(r"[\s\u3000，。！？、；：,.!?;:（）()\[\]【】《》〈〉「」『』\-—_／/]+")
DATEISH_RE = re.compile(r"\b(?:19|20)?\d{2}[./-]\d{1,2}(?:[./-]\d{1,2})?\b")
NUMBER_RE = re.compile(r"\d+(?:[,.]\d+)*")
TITLE_STOP = {
    "衛福部", "衛生福利部", "內政部", "行政院", "表示", "指出", "說明",
    "宣布", "新聞稿", "最新", "今日", "今天", "今", "持續", "推動",
}
AGENCIES = [
    "衛生福利部", "衛福部", "內政部", "勞動部", "教育部", "法務部",
    "行政院", "考試院", "國民健康署", "社會及家庭署", "移民署",
    "國土管理署", "警政署", "消防署",
]
LAW_SUFFIXES = ("法", "條例", "辦法", "施行細則", "公約")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def normalize_title(value: str) -> str:
    text = str(value or "")
    text = DATEISH_RE.sub(" ", text)
    text = NUMBER_RE.sub(" ", text)
    for token in TITLE_STOP:
        text = text.replace(token, " ")
    text = PUNCT_RE.sub("", text)
    return text.lower().strip()


def cjk_ngrams(text: str, n: int = 2) -> set[str]:
    s = normalize_title(text)
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i+n] for i in range(len(s) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def extract_agencies(text: str) -> set[str]:
    return {name for name in AGENCIES if name in text}


def extract_lawish(text: str) -> set[str]:
    candidates = set(re.findall(r"[一-龥A-Za-z0-9]{2,30}(?:法|條例|辦法|施行細則|公約)", text))
    return {x for x in candidates if x.endswith(LAW_SUFFIXES)}


def item_features(row: dict) -> dict:
    text = f"{row.get('title') or ''} {row.get('summary') or ''}"
    return {
        "title_norm": normalize_title(str(row.get("title") or "")),
        "ngrams": cjk_ngrams(str(row.get("title") or "")),
        "tags": {str(x).strip() for x in (row.get("exam_tags") or []) if str(x).strip()},
        "subjects": {str(x).strip() for x in (row.get("subjects") or []) if str(x).strip()},
        "agencies": extract_agencies(text),
        "laws": set(row.get("related_laws") or []) | extract_lawish(text),
        "published": parse_dt(row.get("published_at")),
        "category": str(row.get("category") or ""),
    }


def similarity(a: dict, b: dict, max_days: int = 10) -> tuple[float, list[str]]:
    fa, fb = item_features(a), item_features(b)
    if fa["category"] and fb["category"] and fa["category"] != fb["category"]:
        return 0.0, ["category-mismatch"]
    da, db = fa["published"], fb["published"]
    if da and db and abs((da - db).total_seconds()) > max_days * 86400:
        return 0.0, ["outside-time-window"]

    title_score = jaccard(fa["ngrams"], fb["ngrams"])
    tag_score = jaccard(fa["tags"], fb["tags"])
    subject_score = jaccard(fa["subjects"], fb["subjects"])
    shared_laws = fa["laws"] & fb["laws"]
    shared_agencies = fa["agencies"] & fb["agencies"]

    reasons: list[str] = []
    score = 0.0
    if title_score >= 0.62:
        score += 0.72
        reasons.append(f"title={title_score:.2f}")
    elif title_score >= 0.44:
        score += 0.50
        reasons.append(f"title={title_score:.2f}")
    elif title_score >= 0.30:
        score += 0.30
        reasons.append(f"title={title_score:.2f}")

    if shared_laws:
        score += 0.28
        reasons.append("law=" + ",".join(sorted(shared_laws)[:2]))
    if shared_agencies:
        score += 0.10
        reasons.append("agency=" + ",".join(sorted(shared_agencies)[:2]))
    if tag_score >= 0.50:
        score += 0.15
        reasons.append(f"tags={tag_score:.2f}")
    elif tag_score >= 0.25:
        score += 0.08
        reasons.append(f"tags={tag_score:.2f}")
    if subject_score >= 0.5:
        score += 0.05

    if title_score >= 0.62:
        return min(1.0, score), reasons
    if title_score >= 0.44 and (shared_laws or shared_agencies):
        return min(1.0, score), reasons
    if shared_laws and title_score >= 0.30 and (tag_score >= 0.25 or shared_agencies):
        return min(1.0, score), reasons
    return 0.0, reasons + ["below-fail-closed-threshold"]


def _stable_event_key(members: list[dict]) -> str:
    categories = sorted({str(x.get("category") or "") for x in members if x.get("category")})
    lawish = sorted({str(y) for x in members for y in (x.get("related_laws") or []) if y})
    tagish = sorted({str(y) for x in members for y in (x.get("exam_tags") or []) if y})
    titles = sorted(normalize_title(str(x.get("title") or "")) for x in members)
    basis = "|".join([
        ",".join(categories),
        ",".join(lawish[:3]),
        ",".join(tagish[:5]),
        titles[0] if titles else "",
    ])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def _choose_lead(members: list[dict]) -> dict:
    def rank(row: dict):
        official = 1 if row.get("source_type") == "official" or any(
            x in str(row.get("source_name") or "") for x in ("部", "院", "署")
        ) else 0
        return (
            official,
            int(row.get("signal_score") or 0),
            int(row.get("relevance_score") or 0),
            str(row.get("published_at") or ""),
        )
    return max(members, key=rank)


def build_event(members: list[dict], previous: dict | None = None) -> dict:
    lead = _choose_lead(members)
    dts = [parse_dt(x.get("published_at")) for x in members]
    dts = [x for x in dts if x]
    sources = sorted({str(x.get("source_name") or "") for x in members if x.get("source_name")})
    official_sources = sorted({
        str(x.get("source_name") or "") for x in members
        if x.get("source_name") and (
            x.get("source_type") == "official"
            or any(k in str(x.get("source_name") or "") for k in ("部", "院", "署"))
        )
    })
    evidence = []
    seen_urls = set()
    for row in sorted(members, key=lambda x: str(x.get("published_at") or ""), reverse=True):
        url = str(row.get("source_url") or "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        evidence.append({
            "source_name": row.get("source_name"),
            "source_url": url,
            "published_at": row.get("published_at"),
            "item_id": row.get("id"),
        })

    event_id = _stable_event_key(members)
    current_first = min(dts).isoformat().replace("+00:00", "Z") if dts else None
    current_last = max(dts).isoformat().replace("+00:00", "Z") if dts else None
    previous = previous or {}
    first_seen = previous.get("first_seen") or current_first
    if previous.get("first_seen") and current_first:
        old_dt, new_dt = parse_dt(previous.get("first_seen")), parse_dt(current_first)
        if old_dt and new_dt and new_dt < old_dt:
            first_seen = current_first
    observation_count = int(previous.get("observation_count") or 0) + 1

    related = {}
    for row in members:
        for q in row.get("related_exam_questions") or []:
            qid = str(q.get("id") or "")
            if qid:
                related[qid] = q

    return {
        "canonical_event_id": event_id,
        "title": lead.get("title"),
        "summary": str(lead.get("summary") or "")[:320],
        "category": lead.get("category"),
        "subjects": sorted({str(y) for x in members for y in (x.get("subjects") or []) if y}),
        "exam_tags": sorted({str(y) for x in members for y in (x.get("exam_tags") or []) if y}),
        "related_laws": sorted({str(y) for x in members for y in (x.get("related_laws") or []) if y}),
        "source_count": len(sources),
        "official_source_count": len(official_sources),
        "sources": sources,
        "evidence": evidence,
        "first_seen": first_seen,
        "last_seen": current_last,
        "observation_count": observation_count,
        "policy_signal": lead.get("policy_signal"),
        "essay_value": lead.get("essay_value"),
        "mcq_fact_density": lead.get("mcq_fact_density"),
        "signal_confidence": lead.get("signal_confidence"),
        "signal_score": lead.get("signal_score"),
        "exam_point_summary": lead.get("exam_point_summary"),
        "essay_direction": lead.get("essay_direction"),
        "mcq_focus": lead.get("mcq_focus") or [],
        "related_exam_questions": list(related.values())[:12],
    }


def cluster_items(items: Iterable[dict], previous_events: Iterable[dict] | None = None) -> list[dict]:
    rows = [dict(x) for x in items if isinstance(x, dict) and x.get("id")]
    rows.sort(key=lambda x: (str(x.get("published_at") or ""), str(x.get("id"))))
    groups: list[list[dict]] = []

    for row in rows:
        best_idx = None
        best_score = 0.0
        for idx, group in enumerate(groups):
            lead = _choose_lead(group)
            score, _ = similarity(row, lead)
            if score > best_score:
                best_idx, best_score = idx, score
        if best_idx is not None and best_score >= 0.58:
            groups[best_idx].append(row)
        else:
            groups.append([row])

    previous_map = {
        str(x.get("canonical_event_id")): x
        for x in (previous_events or [])
        if isinstance(x, dict) and x.get("canonical_event_id")
    }
    events = []
    for group in groups:
        probe = build_event(group)
        events.append(build_event(group, previous_map.get(probe["canonical_event_id"])))
    events.sort(key=lambda x: (
        -int(x.get("signal_score") or 0),
        -int(x.get("source_count") or 0),
        str(x.get("last_seen") or ""),
    ))
    return events

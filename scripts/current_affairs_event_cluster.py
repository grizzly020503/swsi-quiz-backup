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

from current_affairs_international import CATEGORY_SLUG, event_metadata

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
CROSS_LANGUAGE_STRONG_FACETS = {
    "child-sexual-abuse", "child-abuse", "gender-based-violence",
    "domestic-violence", "sexual-violence", "human-trafficking",
    "restorative-justice", "juvenile-justice", "victims-rights",
    "minimum-wage", "long-term-care", "dementia", "school-bullying",
}


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


def overlap_coefficient(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def extract_agencies(text: str) -> set[str]:
    return {name for name in AGENCIES if name in text}


def extract_lawish(text: str) -> set[str]:
    candidates = set(re.findall(r"[一-龥A-Za-z0-9]{2,30}(?:法|條例|辦法|施行細則|公約)", text))
    return {x for x in candidates if x.endswith(LAW_SUFFIXES)}


def item_features(row: dict) -> dict:
    text = f"{row.get('title') or ''} {row.get('summary') or ''}"
    category = str(row.get("category") or "")
    derived = event_metadata(
        str(row.get("title") or ""),
        str(row.get("summary") or ""),
        category,
        row.get("exam_tags") or [],
    )
    languages = {
        str(x).strip().lower()
        for x in (row.get("languages") or [row.get("language") or "zh"])
        if str(x).strip()
    }
    return {
        "title_norm": normalize_title(str(row.get("title") or "")),
        "ngrams": cjk_ngrams(str(row.get("title") or "")),
        "tags": {str(x).strip() for x in (row.get("exam_tags") or []) if str(x).strip()},
        "subjects": {str(x).strip() for x in (row.get("subjects") or []) if str(x).strip()},
        "agencies": extract_agencies(text),
        "laws": set(row.get("related_laws") or []) | extract_lawish(text),
        "published": parse_dt(row.get("published_at") or row.get("last_seen")),
        "category": category,
        "languages": languages or {"zh"},
        "facets": {str(x) for x in (row.get("event_facets") or derived["event_facets"]) if str(x)},
        "org_keys": {str(x) for x in (row.get("org_keys") or derived["org_keys"]) if str(x)},
        "numeric_anchors": {str(x) for x in (row.get("numeric_anchors") or derived["numeric_anchors"]) if str(x)},
    }


def similarity(a: dict, b: dict, max_days: int = 10) -> tuple[float, list[str]]:
    fa, fb = item_features(a), item_features(b)
    if fa["category"] and fb["category"] and fa["category"] != fb["category"]:
        return 0.0, ["category-mismatch"]
    da, db = fa["published"], fb["published"]
    if da and db and abs((da - db).total_seconds()) > max_days * 86400:
        return 0.0, ["outside-time-window"]

    cross_language = fa["languages"].isdisjoint(fb["languages"])
    if cross_language:
        if da and db and abs((da - db).total_seconds()) > 4 * 86400:
            return 0.0, ["cross-language-outside-4d"]
        shared_facets = fa["facets"] & fb["facets"]
        category_facet = CATEGORY_SLUG.get(fa["category"], fa["category"])
        specific_facets = {x for x in shared_facets if x != category_facet}
        shared_orgs = fa["org_keys"] & fb["org_keys"]
        shared_numbers = fa["numeric_anchors"] & fb["numeric_anchors"]
        reasons = []
        if specific_facets:
            reasons.append("facet=" + ",".join(sorted(specific_facets)[:3]))
        if shared_orgs:
            reasons.append("org=" + ",".join(sorted(shared_orgs)[:2]))
        if shared_numbers:
            reasons.append("number=" + ",".join(sorted(shared_numbers)[:3]))
        # Fail closed: a broad shared topic is never enough. Cross-language merge
        # needs two specific semantic facets + organization, OR one highly specific
        # facet + organization + shared numeric anchor.
        if len(specific_facets) >= 2 and shared_orgs:
            return 0.72, ["cross-language-multi-facet"] + reasons
        if (
            specific_facets.intersection(CROSS_LANGUAGE_STRONG_FACETS)
            and shared_orgs
            and shared_numbers
        ):
            return 0.66, ["cross-language-strong-anchor"] + reasons
        return 0.0, reasons + ["cross-language-below-threshold"]

    title_score = jaccard(fa["ngrams"], fb["ngrams"])
    title_cover = overlap_coefficient(fa["ngrams"], fb["ngrams"])
    tag_score = jaccard(fa["tags"], fb["tags"])
    subject_score = jaccard(fa["subjects"], fb["subjects"])
    shared_laws = fa["laws"] & fb["laws"]
    shared_agencies = fa["agencies"] & fb["agencies"]

    reasons: list[str] = []
    score = 0.0
    if title_score >= 0.62 or title_cover >= 0.72:
        score += 0.72
        reasons.append(f"title={title_score:.2f}/cover={title_cover:.2f}")
    elif title_score >= 0.44 or title_cover >= 0.48:
        score += 0.50
        reasons.append(f"title={title_score:.2f}/cover={title_cover:.2f}")
    elif title_score >= 0.30 or title_cover >= 0.38:
        score += 0.30
        reasons.append(f"title={title_score:.2f}/cover={title_cover:.2f}")

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

    if title_score >= 0.62 or title_cover >= 0.72:
        return min(1.0, score), reasons
    if (title_score >= 0.44 or title_cover >= 0.48) and (
        shared_laws or shared_agencies or tag_score >= 0.50
    ):
        return min(1.0, score), reasons
    if shared_laws and (title_score >= 0.30 or title_cover >= 0.38) and (
        tag_score >= 0.25 or shared_agencies
    ):
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


def _is_official(source_name: str, source_type: str | None = None) -> bool:
    if source_type == "official":
        return True
    name = str(source_name or "")
    return any(k in name for k in (
        "衛生福利部", "衛福部", "內政部", "勞動部", "教育部", "法務部",
        "行政院", "考試院", "署",
    ))


def _source_rows(row: dict) -> list[dict]:
    nested = row.get("sources")
    if isinstance(nested, list) and nested:
        out = []
        for src in nested:
            if not isinstance(src, dict):
                continue
            url = str(src.get("source_url") or "")
            if not url:
                continue
            out.append({
                "source_name": src.get("source_name") or row.get("source_name"),
                "source_url": url,
                "source_type": src.get("source_type") or row.get("source_type") or "news",
                "published_at": src.get("published_at") or row.get("published_at"),
                "item_id": row.get("id"),
            })
        if out:
            return out
    url = str(row.get("source_url") or "")
    return [{
        "source_name": row.get("source_name"),
        "source_url": url,
        "source_type": row.get("source_type") or "news",
        "published_at": row.get("published_at"),
        "item_id": row.get("id"),
    }] if url else []


def _choose_lead(members: list[dict]) -> dict:
    def rank(row: dict):
        official = 1 if any(_is_official(
            str(src.get("source_name") or ""), str(src.get("source_type") or "")
        ) for src in _source_rows(row)) else 0
        return (
            official,
            int(row.get("signal_score") or 0),
            int(row.get("relevance_score") or 0),
            str(row.get("published_at") or ""),
        )
    return max(members, key=rank)


def _previous_as_item(row: dict) -> dict:
    return {
        "id": row.get("canonical_event_id"),
        "title": row.get("title"),
        "summary": row.get("summary"),
        "category": row.get("category"),
        "exam_tags": row.get("exam_tags") or [],
        "subjects": row.get("subjects") or [],
        "related_laws": row.get("related_laws") or [],
        "published_at": row.get("last_seen"),
        "language": "multi" if len(row.get("languages") or []) > 1 else ((row.get("languages") or ["zh"])[0]),
        "languages": row.get("languages") or [],
        "event_facets": row.get("event_facets") or [],
        "org_keys": row.get("org_keys") or [],
        "numeric_anchors": row.get("numeric_anchors") or [],
        "languages": row.get("languages") or [],
        "event_facets": row.get("event_facets") or [],
        "org_keys": row.get("org_keys") or [],
        "numeric_anchors": row.get("numeric_anchors") or [],
    }


def build_event(members: list[dict], previous: dict | None = None) -> dict:
    lead = _choose_lead(members)
    evidence = []
    seen_urls = set()
    for row in members:
        for src in _source_rows(row):
            url = str(src.get("source_url") or "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            evidence.append(src)
    evidence.sort(key=lambda x: str(x.get("published_at") or ""), reverse=True)

    dts = [parse_dt(x.get("published_at")) for x in evidence]
    dts = [x for x in dts if x]
    source_names = sorted({str(x.get("source_name") or "") for x in evidence if x.get("source_name")})
    official_names = sorted({
        str(x.get("source_name") or "") for x in evidence
        if x.get("source_name") and _is_official(
            str(x.get("source_name") or ""), str(x.get("source_type") or "")
        )
    })

    previous = previous or {}
    event_id = str(previous.get("canonical_event_id") or _stable_event_key(members))
    current_first = min(dts).isoformat().replace("+00:00", "Z") if dts else None
    current_last = max(dts).isoformat().replace("+00:00", "Z") if dts else None
    first_seen = previous.get("first_seen") or current_first
    if previous.get("first_seen") and current_first:
        old_dt, new_dt = parse_dt(previous.get("first_seen")), parse_dt(current_first)
        if old_dt and new_dt and new_dt < old_dt:
            first_seen = current_first
    last_seen = current_last or previous.get("last_seen")
    if previous.get("last_seen") and current_last:
        old_last, new_last = parse_dt(previous.get("last_seen")), parse_dt(current_last)
        if old_last and new_last and old_last > new_last:
            last_seen = previous.get("last_seen")
    observation_dates = {
        str(x) for x in (previous.get("observation_dates") or []) if str(x)
    }
    for src in evidence:
        dt = parse_dt(src.get("published_at"))
        if dt:
            observation_dates.add(dt.date().isoformat())
    observation_dates = sorted(observation_dates)
    observation_count = len(observation_dates) or 1

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
        "languages": sorted({str(x.get("language") or "zh") for x in members}),
        "event_facets": sorted({str(y) for x in members for y in (x.get("event_facets") or []) if y}),
        "org_keys": sorted({str(y) for x in members for y in (x.get("org_keys") or []) if y}),
        "numeric_anchors": sorted({str(y) for x in members for y in (x.get("numeric_anchors") or []) if y}),
        "source_count": len(source_names),
        "official_source_count": len(official_names),
        "sources": source_names,
        "evidence": evidence,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "observation_count": observation_count,
        "observation_dates": observation_dates,
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

    previous = [
        x for x in (previous_events or [])
        if isinstance(x, dict) and x.get("canonical_event_id")
    ]
    previous_by_id = {str(x.get("canonical_event_id")): x for x in previous}
    used_previous: set[str] = set()
    events = []
    for group in groups:
        probe = build_event(group)
        matched = previous_by_id.get(probe["canonical_event_id"])
        if not matched:
            lead = _choose_lead(group)
            best_prev = None
            best_score = 0.0
            for old in previous:
                old_id = str(old.get("canonical_event_id"))
                if old_id in used_previous:
                    continue
                score, _ = similarity(lead, _previous_as_item(old), max_days=45)
                if score > best_score:
                    best_prev, best_score = old, score
            if best_prev is not None and best_score >= 0.58:
                matched = best_prev
        if matched:
            used_previous.add(str(matched.get("canonical_event_id")))
        events.append(build_event(group, matched))

    events.sort(key=lambda x: (
        -int(x.get("signal_score") or 0),
        -int(x.get("source_count") or 0),
        str(x.get("last_seen") or ""),
    ))
    return events

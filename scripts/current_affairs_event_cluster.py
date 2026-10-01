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

from current_affairs_taxonomy import (
    canonical_agencies,
    canonical_concepts,
    canonical_fact_keys,
    has_cjk,
)

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

FACT_ANCHOR_WEAK_TAGS = {
    "政策", "制度", "福利", "保護", "權益", "保障", "服務", "補助", "津貼",
    "高齡", "兒少", "兒童", "少年", "社工", "社會工作", "新聞", "事件",
    "行政院", "衛福部", "衛生福利部",
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
    title = str(row.get("title") or "")
    text = f"{title} {row.get('summary') or ''}"
    concepts = {str(x) for x in (row.get("concept_keys") or []) if str(x)}
    agency_keys = {str(x) for x in (row.get("agency_keys") or []) if str(x)}
    facts = {str(x) for x in (row.get("fact_keys") or []) if str(x)}
    if not concepts:
        concepts = canonical_concepts(text)
    if not agency_keys:
        agency_keys = canonical_agencies(text)
    if not facts:
        facts = canonical_fact_keys(text)
    return {
        "title_norm": normalize_title(title),
        "ngrams": cjk_ngrams(title),
        "tags": {str(x).strip() for x in (row.get("exam_tags") or []) if str(x).strip()},
        "subjects": {str(x).strip() for x in (row.get("subjects") or []) if str(x).strip()},
        "agencies": extract_agencies(text),
        "agency_keys": agency_keys,
        "concepts": concepts,
        "facts": facts,
        "language": "cjk" if has_cjk(title) else "latin",
        "laws": set(row.get("related_laws") or []) | extract_lawish(text),
        "published": parse_dt(row.get("published_at") or row.get("last_seen")),
        "category": str(row.get("category") or ""),
    }


def _significant_numeric_facts(features: dict) -> set[str]:
    out = set()
    for raw in features.get("facts") or set():
        value = str(raw or "").strip()
        if not value.startswith("num:"):
            continue
        try:
            number = abs(int(value.split(":", 1)[1]))
        except (TypeError, ValueError):
            continue
        if number >= 1000:
            out.add(value)
    return out


def _informative_fact_anchor_tags(features: dict) -> set[str]:
    return {
        str(tag).strip()
        for tag in (features.get("tags") or set())
        if str(tag).strip() and str(tag).strip() not in FACT_ANCHOR_WEAK_TAGS
    }


def _cross_publisher_fact_anchor(a: dict, b: dict, fa: dict, fb: dict) -> tuple[bool, list[str]]:
    source_a = str(a.get("source_name") or "").strip()
    source_b = str(b.get("source_name") or "").strip()
    if not source_a or not source_b or source_a == source_b:
        return False, []
    if str(a.get("source_type") or "") != "news" or str(b.get("source_type") or "") != "news":
        return False, []
    da, db = fa.get("published"), fb.get("published")
    if da is None or db is None or abs((da - db).total_seconds()) > 3 * 86400:
        return False, []
    shared_facts = _significant_numeric_facts(fa) & _significant_numeric_facts(fb)
    shared_tags = _informative_fact_anchor_tags(fa) & _informative_fact_anchor_tags(fb)
    if not shared_facts or not shared_tags:
        return False, []
    return True, [
        "cross-publisher-fact=" + ",".join(sorted(shared_facts)[:2]),
        "exam-tag=" + ",".join(sorted(shared_tags)[:2]),
    ]


def similarity(a: dict, b: dict, max_days: int = 10) -> tuple[float, list[str]]:
    fa, fb = item_features(a), item_features(b)
    if fa["category"] and fb["category"] and fa["category"] != fb["category"]:
        return 0.0, ["category-mismatch"]
    da, db = fa["published"], fb["published"]
    if da and db and abs((da - db).total_seconds()) > max_days * 86400:
        return 0.0, ["outside-time-window"]

    # Cross-publisher media follow-ups can have very different headlines.
    # Merge only when category (checked above), a 3-day window, one
    # significant numeric fact and one non-generic exam tag all agree.
    if fa["language"] == fb["language"]:
        anchored, anchor_reasons = _cross_publisher_fact_anchor(a, b, fa, fb)
        if anchored:
            return 0.72, anchor_reasons

    # Cross-language identity is intentionally stricter than same-language
    # title matching: same exam category + >=2 shared canonical concepts +
    # one independent anchor (same institution or same significant fact).
    if fa["language"] != fb["language"]:
        shared_concepts = fa["concepts"] & fb["concepts"]
        shared_agency_keys = fa["agency_keys"] & fb["agency_keys"]
        shared_facts = fa["facts"] & fb["facts"]
        if len(shared_concepts) >= 2 and (shared_agency_keys or shared_facts):
            reasons = ["bilingual-concepts=" + ",".join(sorted(shared_concepts)[:4])]
            score = 0.72 + min(0.12, 0.04 * (len(shared_concepts) - 2))
            if shared_agency_keys:
                score += 0.12
                reasons.append("agency-key=" + ",".join(sorted(shared_agency_keys)[:2]))
            if shared_facts:
                score += 0.10
                reasons.append("fact=" + ",".join(sorted(shared_facts)[:2]))
            return min(1.0, score), reasons
        return 0.0, [
            "cross-language-below-threshold",
            f"concepts={len(shared_concepts)}",
            f"agency={len(shared_agency_keys)}",
            f"facts={len(shared_facts)}",
        ]

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
        "concept_keys": row.get("concept_keys") or [],
        "agency_keys": row.get("agency_keys") or [],
        "fact_keys": row.get("fact_keys") or [],
        "published_at": row.get("last_seen"),
    }


def _merge_historical_stats(members: list[dict]) -> dict:
    stats = [
        x.get("historical_exam_stats")
        for x in members
        if isinstance(x.get("historical_exam_stats"), dict)
    ]
    stats = [x for x in stats if x]
    if not stats:
        related = {
            str(q.get("id")): q
            for row in members
            for q in (row.get("related_exam_questions") or [])
            if isinstance(q, dict) and q.get("id")
        }
        years = sorted({
            int(str(q.get("year")))
            for q in related.values()
            if str(q.get("year") or "").isdigit()
        })
        subjects = {}
        for q in related.values():
            subject = str(q.get("subject") or "").strip()
            if subject:
                subjects[subject] = subjects.get(subject, 0) + 1
        return {
            "matched_question_count": len(related),
            "weighted_match_count": float(len(related)),
            "match_breakdown": {"strong": 0, "medium": 0, "concept": len(related)},
            "matched_year_count": len(years),
            "matched_years": years,
            "earliest_exam_year": min(years) if years else None,
            "latest_exam_year": max(years) if years else None,
            "corpus_latest_year": max(years) if years else None,
            "years_since_last_exam": 0 if years else None,
            "subject_counts": dict(sorted(subjects.items())),
            "subject_count": len(subjects),
            "law_match_count": 0,
            "law_match_year_count": 0,
            "law_match_years": [],
            "high_confidence_match_count": 0,
            "matching_method": "related-question-fallback",
            "aggregation_method": "related-question-fallback",
        }

    richest = max(
        stats,
        key=lambda x: (
            float(x.get("weighted_match_count") or 0),
            int(x.get("matched_question_count") or 0),
            int(x.get("high_confidence_match_count") or 0),
        ),
    )
    years = sorted({
        int(y)
        for st in stats
        for y in (st.get("matched_years") or [])
        if str(y).isdigit()
    })
    law_years = sorted({
        int(y)
        for st in stats
        for y in (st.get("law_match_years") or [])
        if str(y).isdigit()
    })
    corpus_years = [
        int(st.get("corpus_latest_year"))
        for st in stats
        if str(st.get("corpus_latest_year") or "").isdigit()
    ]
    corpus_latest = max(corpus_years) if corpus_years else None
    latest = max(years) if years else None
    earliest = min(years) if years else None
    return {
        "matched_question_count": int(richest.get("matched_question_count") or 0),
        "weighted_match_count": float(richest.get("weighted_match_count") or 0),
        "match_breakdown": dict(richest.get("match_breakdown") or {}),
        "matched_year_count": len(years),
        "matched_years": years,
        "earliest_exam_year": earliest,
        "latest_exam_year": latest,
        "corpus_latest_year": corpus_latest,
        "years_since_last_exam": (
            max(0, corpus_latest - latest)
            if corpus_latest is not None and latest is not None
            else None
        ),
        "subject_counts": dict(richest.get("subject_counts") or {}),
        "subject_count": int(richest.get("subject_count") or 0),
        "law_match_count": max(int(st.get("law_match_count") or 0) for st in stats),
        "law_match_year_count": len(law_years),
        "law_match_years": law_years,
        "high_confidence_match_count": int(richest.get("high_confidence_match_count") or 0),
        "matching_method": richest.get("matching_method") or "event-evidence-v2.2",
        "aggregation_method": "max-quality-member-plus-year-union-v2.2",
    }


def _ordered_union(members: list[dict], key: str) -> list[str]:
    out = []
    seen = set()
    for row in members:
        for raw in row.get(key) or []:
            value = str(raw or "").strip()
            if value and value not in seen:
                seen.add(value)
                out.append(value)
    return out


def _merged_subject_topics(members: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in members:
        raw = row.get("subject_topics") or {}
        if not isinstance(raw, dict):
            continue
        for subject, topics in raw.items():
            subject = str(subject or "").strip()
            if not subject or not isinstance(topics, list):
                continue
            bucket = out.setdefault(subject, [])
            for topic in topics:
                value = str(topic or "").strip()
                if value and value not in bucket:
                    bucket.append(value)
    return {subject: topics[:6] for subject, topics in out.items()}


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
    historical_exam_stats = _merge_historical_stats(members)

    knowledge_root = next((str(x.get("knowledge_root")) for x in members if x.get("knowledge_root")), "")
    knowledge_model = next((str(x.get("knowledge_model")) for x in members if x.get("knowledge_model")), "")
    management_domains = _ordered_union(members, "management_domains")
    exam_subject_axes = _ordered_union(members, "exam_subject_axes")
    primary_exam_subject_axes = _ordered_union(members, "primary_exam_subject_axes")
    supporting_exam_subject_axes = [
        subject for subject in _ordered_union(members, "supporting_exam_subject_axes")
        if subject not in set(primary_exam_subject_axes)
    ]
    subject_topics = _merged_subject_topics(members)
    knowledge_topics = _ordered_union(members, "knowledge_topics")
    knowledge_paths = _ordered_union(members, "knowledge_paths")

    return {
        "canonical_event_id": event_id,
        "title": lead.get("title"),
        "summary": str(lead.get("summary") or "")[:320],
        "category": lead.get("category"),
        "subjects": sorted({str(y) for x in members for y in (x.get("subjects") or []) if y}),
        "knowledge_root": knowledge_root,
        "knowledge_model": knowledge_model,
        "management_domains": management_domains,
        "exam_subject_axes": exam_subject_axes,
        "primary_exam_subject_axes": primary_exam_subject_axes,
        "supporting_exam_subject_axes": supporting_exam_subject_axes,
        "subject_topics": subject_topics,
        "knowledge_topics": knowledge_topics,
        "knowledge_paths": knowledge_paths,
        "exam_tags": sorted({str(y) for x in members for y in (x.get("exam_tags") or []) if y}),
        "related_laws": sorted({str(y) for x in members for y in (x.get("related_laws") or []) if y}),
        "concept_keys": sorted({str(y) for x in members for y in (x.get("concept_keys") or []) if y}),
        "agency_keys": sorted({str(y) for x in members for y in (x.get("agency_keys") or []) if y}),
        "fact_keys": sorted({str(y) for x in members for y in (x.get("fact_keys") or []) if y}),
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
        "historical_exam_stats": historical_exam_stats,
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


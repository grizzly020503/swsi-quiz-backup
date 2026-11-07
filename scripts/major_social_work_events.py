#!/usr/bin/env python3
"""Conservative, deterministic major social-work event archive and essay practice.

Input: existing vetted V2 event clusters. No network, LLM, private records or
official exam mutation. Only independent corroborated systemic events enter.
Once admitted, an event stays in the historic archive when rolling feeds age
out, unless it is explicitly blocked or a new observation fails the gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
VERSION = "major-social-work-v1"
CATEGORIES = {
    "兒少保護", "家暴與性暴力", "心理健康與成癮", "長照與高齡",
    "身障與人權", "災害與社區工作", "教育與學生輔導",
    "社工專業與社福制度", "社會救助與居住", "性別與家庭政策",
    "少年司法與犯罪防治", "司法保護與修復式司法",
    "勞動與社會保障", "移工與新住民",
}
SUBJECTS = {
    "社會工作", "社會工作直接服務", "社會政策與社會立法",
    "人類行為與社會環境", "社會工作研究方法",
}
# An exam topic alone is NOT evidence of real-world systemic importance.
DOMAIN = (
    "社工", "社會安全網", "社福", "社會福利", "老人福利", "兒少保護", "兒童保護",
    "兒虐", "虐童", "安置", "寄養", "收出養", "長照", "長期照顧",
    "家庭照顧", "照顧者", "精神衛生", "精神健康", "身心障礙",
    "身障", "家庭暴力", "家暴", "性騷擾", "性侵害", "社會救助",
    "校園霸凌", "學生輔導", "弱勢", "保護令", "住宅政策",
    "兒童及少年", "少年事件處理", "精神衛生法", "家庭暴力防治法", "災害社工", "災害防救",
    "社區重建", "災民", "福利服務", "居住權", "社會住宅",
)
CHANGE = (
    "正式施行", "正式上路", "施行", "三讀", "公布", "修正", "修法",
    "核定", "啟動", "擴大", "增訂", "改革", "新制", "重大",
    "安置", "重建", "制度", "審議通過", "全面", "通過",
    "死亡", "致死", "虐死", "受虐", "崩塌", "洪災", "地震", "堰塞湖",
)
# Routine publicity must never be promoted only for matching policy keywords.
ROUTINE = (
    "工作坊", "記者會", "說明會", "研討會", "研習", "徵稿",
    "徵件", "展覽", "開幕", "得獎", "頒獎", "參訪", "交流活動",
    "宣導活動", "推廣活動", "講座", "論壇", "節慶", "疫情報告",
)
DRAFT = ("修正草案", "修法草案", "研議", "擬修", "修法討論", "修法建議")
ENACTED = ("三讀通過", "正式施行", "正式上路", "生效", "已公布", "行政院核定", "已核定")
CASE = ("致死", "虐死", "重傷", "失職", "重大災害", "洪災", "堰塞湖", "地震", "一家五口")
SYSTEM_RESPONSE = (
    "監察院", "社會安全網", "跨網絡", "保護服務", "社工",
    "社會局", "衛福部", "政府", "體系", "制度漏洞", "改革",
    "家庭照顧者", "資源分配", "照顧負荷", "社區重建",
)
TEMPLATES = {
    "兒少保護": ("兒童最佳利益、風險評估、法定通報與跨網絡合作", "兒少保護實務", "社會工作直接服務"),
    "家暴與性暴力": ("危險評估、保護措施、創傷知情與服務協作", "被害人保護", "社會工作直接服務"),
    "心理健康與成癮": ("危機介入、當事人自主、復元與社區支持", "精神衛生社會工作", "社會工作直接服務"),
    "長照與高齡": ("家庭照顧者支持、服務輸送與資源可近性", "長期照顧政策與實務", "社會政策與社會立法"),
    "身障與人權": ("自立生活、合理調整、反歧視與服務可近性", "身心障礙權益", "社會政策與社會立法"),
    "災害與社區工作": ("災害各階段工作、社區韌性與資源公平", "災害社會工作", "社會工作"),
    "教育與學生輔導": ("學生風險評估、校園支持與跨專業合作", "學校社會工作", "社會工作直接服務"),
    "社工專業與社福制度": ("專業倫理、服務輸送、人力與跨網絡協調", "社會工作制度", "社會工作"),
    "社會救助與居住": ("福利可近性、貧窮風險、資源連結與居住權", "社會救助制度", "社會政策與社會立法"),
    "性別與家庭政策": ("照顧分工、家庭支持、性別平等與制度回應", "家庭與性別政策", "人類行為與社會環境"),
    "少年司法與犯罪防治": ("少年最佳利益、去標籤、家庭支持與社區處遇", "少年司法與社會工作", "社會政策與社會立法"),
    "司法保護與修復式司法": ("被害人權益、倫理抉擇、跨網絡轉介與社區處遇", "司法社會工作", "社會工作直接服務"),
    "勞動與社會保障": ("勞動權益、弱勢就業與社會保障服務", "勞動與社會保障", "社會政策與社會立法"),
    "移工與新住民": ("文化能力、語言可近性、反歧視與家庭支持", "多元文化服務", "社會工作直接服務"),
}


def source_evidence(event: dict) -> list[dict]:
    rows, seen = [], set()
    for evidence in event.get("evidence") or []:
        if not isinstance(evidence, dict):
            continue
        name = str(evidence.get("source_name") or "").strip()
        url = str(evidence.get("source_url") or "").strip()
        published = str(evidence.get("published_at") or "")
        kind = str(evidence.get("source_type") or "").lower()
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if (not name or not published or len(url) > 2000
            or parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or url in seen):
            continue
        seen.add(url)
        rows.append({
            "source_name": name[:100],
            "source_url": url,
            "source_type": "official" if kind == "official" else "news",
            "published_at": published[:32],
        })
    return rows


def publisher_site(url: str) -> str:
    """Conservatively group articles from one publishing site despite subdomain aliases.

    This is not a full media-ownership registry: when two distinct source
    labels point to one registered-looking domain, they are not corroboration.
    """
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    labels = host.split(".")
    if len(labels) < 2:
        return host
    # Two-level country-code suffixes such as gov.tw / com.tw / co.uk.
    cc_second_level = {"com", "net", "org", "gov", "edu", "ac", "co", "or", "ne", "mil", "idv"}
    depth = 3 if (len(labels) >= 3 and len(labels[-1]) == 2
                  and labels[-2] in cc_second_level) else 2
    return ".".join(labels[-depth:])


def evaluate(event: dict, blocked_ids: set[str] | None = None) -> tuple[bool, str]:
    """Return fail-closed decision; no numeric ranking can override a failed gate."""
    if not isinstance(event, dict):
        return False, "invalid_event"
    event_id = str(event.get("canonical_event_id") or "")
    title = str(event.get("title") or "").strip()
    summary = str(event.get("summary") or "").strip()
    category = str(event.get("category") or "")
    if not event_id or event_id in (blocked_ids or set()):
        return False, "blocked_or_missing_identity"
    if not (12 <= len(title) <= 230) or not summary:
        return False, "missing_event_details"
    if category not in CATEGORIES or not (set(event.get("exam_subject_axes") or event.get("subjects") or []) & SUBJECTS):
        return False, "not_social_work_exam_scope"
    if any(term in title for term in ROUTINE):
        return False, "routine_activity"
    if not any(term in title for term in DOMAIN):
        # Disaster headlines can qualify if their summary specifically links
        # disaster social work and the event has robust independent proof.
        if not (any(term in title for term in ("洪災", "地震", "堰塞湖", "重大災害"))
                and any(term in summary for term in ("災害社工", "社區重建", "社會局", "安置"))):
            return False, "no_explicit_social_work_anchor"
    if not any(term in title for term in CHANGE):
        return False, "no_concrete_major_impact"
    if any(term in title for term in DRAFT) and not any(term in title for term in ENACTED):
        return False, "proposal_not_enacted_or_confidently_major"
    if str(event.get("essay_value") or "") != "high":
        return False, "essay_value_not_high"
    if str(event.get("signal_confidence") or "") not in {"high", "medium"}:
        return False, "exam_context_unreliable"
    evidence = source_evidence(event)
    independent = len({r["source_name"] for r in evidence})
    official = len({r["source_name"] for r in evidence if r["source_type"] == "official"})
    if (independent < 2 or independent != int(event.get("source_count") or 0)
        or official != int(event.get("official_source_count") or 0)):
        return False, "inconsistent_or_single_source"
    # Different labels on the same publisher's domain are not independent
    # confirmation, even if the upstream cluster counts them separately.
    publisher_sites = {publisher_site(r["source_url"]) for r in evidence}
    if len(publisher_sites) < independent:
        return False, "repackaged_same_publisher"
    observation_days = {r["published_at"][:10] for r in evidence}
    if official >= 1:
        # Same-day official policy may be major if there is an enacted outcome;
        # otherwise require a later observation instead of promoting one press cycle.
        if len(observation_days) < 2 and not any(t in title for t in ENACTED):
            return False, "insufficient_time_or_formal_outcome"
    elif independent < 3 or len(observation_days) < 2:
        return False, "missing_official_or_cross_day_confirmation"
    if any(k in title for k in CASE):
        if independent < 3 or not any(k in summary for k in SYSTEM_RESPONSE):
            return False, "isolated_tragedy_without_systemic_evidence"
    if not (
        str(event.get("policy_signal") or "") == "high"
        or (any(k in title for k in CASE) and any(k in summary for k in SYSTEM_RESPONSE))
    ):
        return False, "insufficient_systemic_policy_or_practice_effect"
    return True, "confirmed_cross_source_systemic_impact"


def practice_questions(event: dict) -> list[dict]:
    category = str(event.get("category") or "")
    dimensions, subject_label, default_subject = TEMPLATES[category]
    topic = str(event.get("title") or "").strip()
    subject_candidates = event.get("primary_exam_subject_axes") or event.get("subjects") or []
    subject = next((x for x in subject_candidates if x in SUBJECTS), default_subject)
    # Explicitly frame these as analysis exercises; this text does not declare
    # disputed allegations proven or an amendment already enacted.
    return [
        {
            "id": str(event["canonical_event_id"]) + "-essay-1",
            "type": "practice_only",
            "subject": subject,
            "question": (
                f"以多來源報導的「{topic}」所涉及之{subject_label}議題為背景，"
                f"請運用社會工作觀點，分析{dimensions}的主要挑戰，"
                "並提出社工在個案、家庭及跨專業網絡層次可採取的具體作法。（25 分）"
            ),
            "outline": [
                "先區分已獲證實的制度事實與仍待查證的報導",
                "分析個案／家庭需求、風險與社會結構因素",
                "依照相關倫理原則提出跨系統處遇或政策建議",
                "提出具體成效指標與可行的後續追蹤方式",
            ],
        },
        {
            "id": str(event["canonical_event_id"]) + "-essay-2",
            "type": "practice_only",
            "subject": subject,
            "question": (
                f"以「{topic}」反映的公共議題為例，"
                "試說明現行服務輸送或政策執行可能出現哪些制度斷點，"
                "並從權益保障、資源可近性、社工倫理及跨網絡合作四方面，"
                "提出改善方案及評估方法。（25 分）"
            ),
            "outline": [
                "釐清制度目標、適用對象及法律或政策的實際階段",
                "說明服務取得、資訊流通及跨機關合作的可能斷點",
                "提出可執行的短、中、長期改善方案",
                "以覆蓋率、可近性、服務品質及權益保障評估成果",
            ],
        },
    ]


def public_record(event: dict) -> dict:
    evidence = source_evidence(event)
    event_id = str(event["canonical_event_id"])
    return {
        "canonical_event_id": event_id,
        "title": str(event["title"])[:230],
        "summary": str(event.get("summary") or "")[:300],
        "category": str(event["category"]),
        "subjects": [x for x in (event.get("subjects") or []) if x in SUBJECTS][:5],
        "last_seen": str(event.get("last_seen") or "")[:32],
        "admission_rule": VERSION,
        "admission_basis": "至少兩個獨立來源，並符合重大制度或實務影響的多重門檻",
        "evidence": evidence[:5],
        "practice_essays": practice_questions(event),
    }


def build(events: list[dict], previous: list[dict], blocked_ids: set[str]) -> dict:
    # Retain previously vetted historical events as source feeds rotate;
    # reviewed blocklist always wins. Never carry forward a fresh failure.
    current_ids = {str(e.get("canonical_event_id") or "") for e in events if isinstance(e, dict)}
    records = {
        str(x["canonical_event_id"]): x
        for x in previous if isinstance(x, dict)
        and x.get("admission_rule") == VERSION
        and str(x.get("canonical_event_id") or "") not in current_ids | blocked_ids
        and len(x.get("evidence") or []) >= 2
        and len(x.get("practice_essays") or []) == 2
    }
    admissions = 0
    for event in events:
        ok, _reason = evaluate(event, blocked_ids)
        if ok:
            records[str(event["canonical_event_id"])] = public_record(event)
            admissions += 1
    ordered = sorted(records.values(), key=lambda x: (
        str(x.get("last_seen") or ""), str(x.get("canonical_event_id") or "")
    ), reverse=True)[:60]
    # Content hash prevents a new commit for a clock-only polling cycle.
    revision = hashlib.sha256(json.dumps(
        ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": 1,
        "selection_method": VERSION,
        "revision": revision,
        "event_count": len(ordered),
        "note": "僅自動收錄跨來源確認且具有重大社工實務／制度意義的事件；申論為平台自編練習題，非考選部官方命題或命中預測。",
        "events": ordered,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default=str(ROOT / "auto/current_affairs_events.json"))
    parser.add_argument("--output", default=str(ROOT / "auto/major_social_work_events.json"))
    parser.add_argument("--blocklist", default=str(ROOT / "data/major_event_blocklist.json"))
    args = parser.parse_args()
    src = json.loads(Path(args.events).read_text(encoding="utf-8"))
    if src.get("schema_version") != 1 or not isinstance(src.get("events"), list):
        raise SystemExit("Invalid source event cluster snapshot")
    policy = json.loads(Path(args.blocklist).read_text(encoding="utf-8"))
    if policy.get("schema_version") != 1 or not isinstance(policy.get("blocked_event_ids"), list):
        raise SystemExit("Invalid major-event blocklist")
    blocked = {str(x) for x in policy["blocked_event_ids"]}
    out = Path(args.output)
    previous = []
    if out.exists():
        prior = json.loads(out.read_text(encoding="utf-8"))
        if prior.get("schema_version") != 1 or prior.get("selection_method") != VERSION:
            raise SystemExit("Existing major-event archive has incompatible schema")
        previous = prior.get("events") or []
    built = build(src["events"], previous, blocked)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(built, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MAJOR SOCIAL WORK EVENTS: {built['event_count']} admitted/archived; revision={built['revision']}")


if __name__ == "__main__":
    main()

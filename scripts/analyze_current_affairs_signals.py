#!/usr/bin/env python3
"""Offline analyzer: turn current-affairs radar items into exam-signal fields.

Phase 1–2 helper for Issue #74 (時事庫 = 國考命題趨勢資料庫).

- Does NOT modify production files by default.
- Does NOT touch frontend, workflows, or Netlify.
- Reads auto/current_affairs.json and writes an enhanced snapshot for review.
- Optionally links items to past exam questions (CSV or JSON list).

Usage:
  python3 scripts/analyze_current_affairs_signals.py
  python3 scripts/analyze_current_affairs_signals.py \\
      --input auto/current_affairs.json \\
      --output audit/current_affairs_signals_preview.json \\
      --questions-csv data/questions_master_backup_20260824_2220.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

KNOWN_LAWS = [
    "兒童及少年福利與權益保障法",
    "老人福利法",
    "身心障礙者權益保障法",
    "家庭暴力防治法",
    "社會救助法",
    "社會工作師法",
    "長期照顧服務法",
    "兒童及少年性剝削防制條例",
    "性別平等工作法",
    "性侵害犯罪防治法",
    "特殊境遇家庭扶助條例",
    "國民年金法",
    "身心障礙者權利公約",
    "志願服務法",
    "兒童及少年未來教育與發展帳戶條例",
    "精神衛生法",
    "兒童權利公約",
    "公益勸募條例",
    "身心障礙者權利公約施行法",
    "病人自主權利法",
    "就業保險法",
    "兒童權利公約施行法",
    "全民健康保險法",
    "學生輔導法",
    "民法",
    "消除對婦女一切形式歧視公約施行法",
    "少年事件處理法",
    "性騷擾防治法",
    "毒品危害防制條例",
    "長期照顧服務機構法人條例",
    "人口販運防制法",
    "住宅法",
    "性別平等教育法",
    "社會福利基本法",
    "跟蹤騷擾防制法",
]

POLICY_HIGH = [
    "修法", "修正", "施行細則", "正式上路", "核定", "公告實施",
    "補助調增", "每月補助", "追溯自", "條例", "辦法修正",
    "制度上路", "正式實施", "院會通過", "通過修正",
]
POLICY_MEDIUM = [
    "政策", "制度", "改革", "研議", "檢討", "座談", "調查",
    "規劃", "方案", "支持措施", "權益保障", "服務量能",
]
POLICY_LOW = [
    "宣導", "活動", "記者會", "倡議", "響應", "節日", "月口號",
    "好禮", "選購", "徵件", "招標",
]

ESSAY_HIGH = [
    "權益", "落差", "困境", "風險", "倫理", "跨網絡", "跨專業",
    "社工角色", "專業責任", "人力不足", "執業環境", "保護", "安置",
    "家庭照顧", "復元", "去污名", "合理調整", "自立生活",
    "社會安全網", "制度改善", "爭議", "通報", "保護令",
]
ESSAY_MEDIUM = [
    "政策", "制度", "服務", "支持", "福利", "權益保障", "方案",
]
ESSAY_LOW = [
    "宣導", "活動", "記者會", "響應", "倡議活動",
]

MCQ_HIGH_PATTERNS = [
    r"\d{1,3}[,，]\d{3}",
    r"每月", r"每年", r"追溯自", r"自\d+年", r"第\d+條",
    r"主管機關", r"衛福部", r"內政部", r"勞動部",
    r"施行細則", r"補助方案",
]
MCQ_MEDIUM = ["補助", "津貼", "給付", "服務", "制度", "法規", "調查", "辦法", "條例"]

CATEGORY_ESSAY_HINT = {
    "兒少保護": "兒少最佳利益、責任通報、跨網絡合作與制度漏洞",
    "家暴與性暴力": "危險評估、保護令、創傷知情與跨網絡合作",
    "心理健康與成癮": "精神衛生、危機介入、復元取向與去污名",
    "長照與高齡": "在地老化、長照給付、家庭照顧者支持與服務輸送",
    "社會救助與居住": "最低生活保障、貧窮結構因素與居住權",
    "身障與人權": "CRPD、合理調整、自立生活與去機構化",
    "移工與新住民": "文化能力、勞動與社會權益、反歧視",
    "少年司法與犯罪防治": "保護優先、去標籤、家庭學校社區支持",
    "性別與家庭政策": "性別權力、照顧負荷與家庭政策",
    "災害與社區工作": "危機介入、安置資源分配與社區韌性",
    "社工專業與社福制度": "專業角色倫理、服務輸送、人力督導與政策落差",
}

WEAK_TAGS = {
    "政策", "制度", "福利", "保護", "權益", "服務", "補助", "津貼",
    "兒童", "少年", "老人", "高齡", "社工", "社會工作", "衛福部",
}

CATEGORY_MATCH_TERMS = {
    "兒少保護": ["兒童", "少年", "兒少", "通報", "安置", "最佳利益"],
    "家暴與性暴力": ["家暴", "家庭暴力", "性暴力", "保護令", "被害人", "危險評估"],
    "心理健康與成癮": ["精神衛生", "心理健康", "成癮", "危機介入", "復元", "去污名", "自殺"],
    "長照與高齡": ["長照", "高齡", "老人", "失智", "家庭照顧者", "照顧者", "在地老化"],
    "社會救助與居住": ["社會救助", "貧窮", "低收入", "最低生活", "住宅", "居住權", "脫貧"],
    "身障與人權": ["身心障礙", "障礙", "CRPD", "合理調整", "自立生活", "無障礙", "去機構化"],
    "移工與新住民": ["移工", "新住民", "移民", "文化能力", "反歧視", "勞動權益"],
    "少年司法與犯罪防治": ["少年司法", "少年事件", "曝險少年", "犯罪防治", "去標籤", "復歸"],
    "性別與家庭政策": ["性別", "性別平等", "家庭政策", "照顧負荷", "性別主流化", "工作家庭"],
    "災害與社區工作": ["災害", "災民", "社區", "韌性", "復原", "重建", "安置"],
    "社工專業與社福制度": ["社工", "社會工作", "專業", "倫理", "督導", "執業", "服務輸送"],
}


def text_of(row: dict) -> str:
    return f"{row.get('title') or ''} {row.get('summary') or ''}"


def extract_laws(text: str) -> list[str]:
    bracket = re.findall(r"《([^》]{2,40})》", text)
    known = [name for name in KNOWN_LAWS if name in text]
    return list(dict.fromkeys(bracket + known))[:8]


def level_from_hits(
    text: str,
    high_terms: list[str],
    medium_terms: list[str],
    low_terms: list[str] | None = None,
) -> str:
    low_terms = low_terms or []
    high = sum(1 for t in high_terms if t in text)
    medium = sum(1 for t in medium_terms if t in text)
    low = sum(1 for t in low_terms if t in text)
    if high >= 1 and low == 0:
        return "high"
    if high >= 1:
        return "medium"
    if medium >= 2:
        return "medium"
    if medium >= 1 and low == 0:
        return "medium"
    if low >= 1 and high == 0:
        return "low"
    return "low"


def score_policy_signal(text: str) -> str:
    return level_from_hits(text, POLICY_HIGH, POLICY_MEDIUM, POLICY_LOW)


def score_essay_value(text: str, category: str) -> str:
    high_terms = ESSAY_HIGH + ["社工", "專業", "家庭照顧者", "跨網絡"]
    base = level_from_hits(text, high_terms, ESSAY_MEDIUM, ESSAY_LOW)
    if category in {"社工專業與社福制度", "兒少保護", "家暴與性暴力", "身障與人權"} and base == "low":
        return "medium"
    return base


def score_mcq_fact_density(text: str) -> str:
    high_hits = sum(1 for pat in MCQ_HIGH_PATTERNS if re.search(pat, text))
    medium_hits = sum(1 for t in MCQ_MEDIUM if t in text)
    if high_hits >= 2:
        return "high"
    if high_hits == 1 or medium_hits >= 3:
        return "medium"
    if medium_hits >= 1:
        return "medium"
    return "low"


def build_exam_point_summary(
    row: dict,
    laws: list[str],
    policy: str,
    essay: str,
    mcq: str,
) -> str:
    category = str(row.get("category") or "時事")
    title = str(row.get("title") or "").strip()
    hint = CATEGORY_ESSAY_HINT.get(category, "政策／制度與社工實務考點")
    law_part = f"涉及「{'、'.join(laws[:2])}」。" if laws else ""

    parts: list[str] = []
    if policy == "high":
        parts.append("制度或給付已有明確變動")
    elif policy == "medium":
        parts.append("政策／制度動向值得追蹤")
    else:
        parts.append("偏宣導或活動訊息")

    if essay in {"high", "medium"}:
        parts.append(f"申論可從{hint}切入")
    if mcq == "high":
        parts.append("含較具體數字、日期或法規事實，利於選擇題")
    elif mcq == "medium":
        parts.append("有一定制度名詞與事實點")

    head = title[:48] + ("…" if len(title) > 48 else "")
    body = "；".join(parts)
    return f"{head}。{law_part}{body}。此為命題訊號，非命題保證。"


def confidence_for(policy: str, essay: str, mcq: str, laws: list[str], n_related: int) -> str:
    score = 0.0
    if policy == "high":
        score += 2
    elif policy == "medium":
        score += 1
    if essay == "high":
        score += 2
    elif essay == "medium":
        score += 1
    if mcq == "high":
        score += 2
    elif mcq == "medium":
        score += 1
    if laws:
        score += 1
    if n_related >= 2:
        score += 1
    elif n_related == 1:
        score += 0.5
    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def _split_keywords(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    s = str(raw).strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    parts = re.split(r"[,，;；|/\s]+", s)
    return [p for p in parts if p]


def load_questions_csv(path: Path, limit: int = 0) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            q = {
                "id": str(row.get("id") or "").strip(),
                "subject": str(row.get("subject") or "").strip(),
                "year": str(row.get("year") or "").strip(),
                "round": str(row.get("round") or "").strip(),
                "qno": str(row.get("qno") or "").strip(),
                "major": str(row.get("major") or "").strip(),
                "topic": str(row.get("topic") or "").strip(),
                "keywords": _split_keywords(row.get("keywords")),
                "question": str(row.get("question") or "").strip(),
                "law": str(row.get("law") or "").strip(),
            }
            if q["id"]:
                rows.append(q)
            if limit and len(rows) >= limit:
                break
    return rows


def load_questions_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and isinstance(data.get("questions"), list):
        items = data["questions"]
    elif isinstance(data, dict) and isinstance(data.get("items"), list):
        items = data["items"]
    else:
        raise SystemExit(f"Unsupported questions JSON shape: {path}")
    out = []
    for row in items:
        if not isinstance(row, dict):
            continue
        q = {
            "id": str(row.get("id") or "").strip(),
            "subject": str(row.get("subject") or "").strip(),
            "year": str(row.get("year") or "").strip(),
            "round": str(row.get("round") or "").strip(),
            "qno": str(row.get("qno") or "").strip(),
            "major": str(row.get("major") or "").strip(),
            "topic": str(row.get("topic") or "").strip(),
            "keywords": _split_keywords(row.get("keywords")),
            "question": str(row.get("question") or "").strip(),
            "law": str(row.get("law") or "").strip(),
        }
        if q["id"]:
            out.append(q)
    return out


def informative_tags(row: dict) -> set[str]:
    tags = set()
    for t in row.get("exam_tags") or []:
        s = str(t).strip()
        if s and s not in WEAK_TAGS and len(s) >= 2:
            tags.add(s)
    return tags


def match_questions(row: dict, laws: list[str], questions: list[dict], max_hits: int = 5) -> list[dict]:
    """Return related exam questions with fail-closed thresholds.

    Strong: shared law name
    Medium: subject overlap + informative tag / topic keyword overlap
    """
    if not questions:
        return []

    subjects = set(str(s) for s in (row.get("subjects") or []) if s)
    tags = informative_tags(row)
    category_terms = set(CATEGORY_MATCH_TERMS.get(str(row.get("category") or ""), []))
    scored: list[tuple[float, dict]] = []

    for q in questions:
        score = 0.0
        reasons: list[str] = []
        q_law = q.get("law") or ""
        q_text = f"{q.get('question') or ''} {q.get('topic') or ''} {q.get('major') or ''} {' '.join(q.get('keywords') or [])}"

        law_hit = None
        for law in laws:
            if law and (law in q_law or law in q_text):
                law_hit = law
                break
        if law_hit:
            score += 5.0
            reasons.append(f"法規「{law_hit}」")

        subj = q.get("subject") or ""
        subj_ok = (not subjects) or (subj in subjects)
        if not law_hit and not subj_ok:
            continue

        tag_hits = [t for t in tags if t in q_text or t in q_law]
        category_hits = [t for t in category_terms if t in q_text or t in q_law]
        combined_hits = list(dict.fromkeys(tag_hits + category_hits))
        if combined_hits:
            score += min(3.0, 1.0 * len(combined_hits))
            reasons.append("關鍵詞：" + "、".join(combined_hits[:4]))

        if score > 0 and subj_ok:
            score += 0.2

        if law_hit or len(combined_hits) >= 2:
            scored.append((score, {
                "id": q.get("id"),
                "subject": subj,
                "year": q.get("year"),
                "round": q.get("round"),
                "qno": q.get("qno"),
                "major": q.get("major"),
                "topic": q.get("topic"),
                "match_reason": "；".join(reasons) if reasons else "相關",
                "match_score": round(score, 2),
            }))

    scored.sort(key=lambda x: (-x[0], str(x[1].get("year") or ""), str(x[1].get("qno") or "")))
    seen = set()
    out = []
    for _, item in scored:
        qid = item.get("id")
        if not qid or qid in seen:
            continue
        seen.add(qid)
        out.append(item)
        if len(out) >= max_hits:
            break
    return out


def essay_direction_for(row: dict, laws: list[str]) -> str:
    category = str(row.get("category") or "時事")
    hint = CATEGORY_ESSAY_HINT.get(category, "事件脈絡、社工角色、政策工具與制度改善")
    if laws:
        return f"可從「{hint}」切入，並結合「{'、'.join(laws[:2])}」的制度與實務影響分析；此為練習方向，不代表命題保證。"
    return f"可從「{hint}」切入，分析問題成因、社工角色、政策／服務回應與制度改善；此為練習方向，不代表命題保證。"


def mcq_focus_for(row: dict, text: str, laws: list[str]) -> list[str]:
    facts: list[str] = []
    patterns = [
        r"\b\d{1,3}(?:[,，]\d{3})+(?:\.\d+)?%?",
        r"\b\d{4}\s*年(?:\d{1,2}\s*月)?",
        r"第\s*\d+\s*條",
    ]
    for pat in patterns:
        for m in re.findall(pat, text):
            if m not in facts:
                facts.append(m)
    for agency in ["衛福部", "衛生福利部", "內政部", "勞動部", "教育部", "法務部", "行政院", "考試院", "國民健康署"]:
        if agency in text and agency not in facts:
            facts.append(agency)
    for law in laws[:3]:
        if law not in facts:
            facts.append(law)
    for tag in row.get("exam_tags") or []:
        tag = str(tag).strip()
        if tag and tag not in WEAK_TAGS and tag not in facts:
            facts.append(tag)
    return facts[:8]


def analyze_item(row: dict, questions: list[dict], max_related: int = 5) -> dict:
    text = text_of(row)
    laws = extract_laws(text)
    policy = score_policy_signal(text)
    essay = score_essay_value(text, str(row.get("category") or ""))
    mcq = score_mcq_fact_density(text)
    related = match_questions(row, laws, questions, max_hits=max_related)
    summary = build_exam_point_summary(row, laws, policy, essay, mcq)
    essay_direction = essay_direction_for(row, laws)
    mcq_focus = mcq_focus_for(row, text, laws)
    conf = confidence_for(policy, essay, mcq, laws, len(related))

    out = dict(row)
    out.update(
        {
            "policy_signal": policy,
            "essay_value": essay,
            "mcq_fact_density": mcq,
            "exam_point_summary": summary,
            "essay_direction": essay_direction,
            "mcq_focus": mcq_focus,
            "related_laws": laws,
            "related_exam_questions": related,
            "signal_confidence": conf,
            "analysis_status": "auto",
        }
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline current-affairs exam-signal analyzer (Issue #74)")
    ap.add_argument("--input", default=str(ROOT / "auto" / "current_affairs.json"))
    ap.add_argument(
        "--output",
        default=str(ROOT / "audit" / "current_affairs_signals_preview.json"),
        help="Review output path. Default writes under audit/ and does not touch auto/.",
    )
    ap.add_argument("--questions-csv", default="", help="Optional questions CSV for related_exam_questions")
    ap.add_argument("--questions-json", default="", help="Optional questions JSON for related_exam_questions")
    ap.add_argument("--questions-limit", type=int, default=0, help="Optional cap when loading CSV (0=all)")
    ap.add_argument("--max-related", type=int, default=5, help="Max related questions per item")
    args = ap.parse_args()

    src_path = Path(args.input)
    if not src_path.exists():
        raise SystemExit(f"Input not found: {src_path}")

    src = json.loads(src_path.read_text(encoding="utf-8"))
    items = src.get("items") or []
    if not isinstance(items, list):
        raise SystemExit("Input items must be a list")

    questions: list[dict] = []
    if args.questions_csv:
        qpath = Path(args.questions_csv)
        if not qpath.exists():
            raise SystemExit(f"Questions CSV not found: {qpath}")
        questions = load_questions_csv(qpath, limit=max(0, args.questions_limit))
        print(f"Loaded {len(questions)} questions from CSV")
    elif args.questions_json:
        qpath = Path(args.questions_json)
        if not qpath.exists():
            raise SystemExit(f"Questions JSON not found: {qpath}")
        questions = load_questions_json(qpath)
        print(f"Loaded {len(questions)} questions from JSON")
    else:
        print("No --questions-csv/--questions-json provided; related_exam_questions will be empty")

    analyzed = [analyze_item(x, questions, max_related=max(1, args.max_related)) for x in items if isinstance(x, dict)]

    payload = {
        "schema_version": 2,
        "analyzer": "analyze_current_affairs_signals.py",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": str(src_path),
        "questions_source": args.questions_csv or args.questions_json or None,
        "questions_loaded": len(questions),
        "note": (
            "Offline preview for Issue #74. Not a production public snapshot. "
            "related_exam_questions uses fail-closed law/tag matching."
        ),
        "item_count": len(analyzed),
        "items": analyzed,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Analyzed {len(analyzed)} items -> {out}")
    for row in analyzed[:12]:
        related = row.get("related_exam_questions") or []
        print(
            f"[{row.get('policy_signal')}/{row.get('essay_value')}/{row.get('mcq_fact_density')}] "
            f"conf={row.get('signal_confidence')} related={len(related)} | "
            f"{row.get('category')} | {row.get('title')}"
        )
        if row.get("related_laws"):
            print(f"  laws: {', '.join(row['related_laws'][:4])}")
        for rq in related[:3]:
            print(
                f"  Q: {rq.get('id')} ({rq.get('subject')} {rq.get('year')}-{rq.get('qno')}) "
                f"— {rq.get('match_reason')}"
            )
        print(f"  point: {row.get('exam_point_summary')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

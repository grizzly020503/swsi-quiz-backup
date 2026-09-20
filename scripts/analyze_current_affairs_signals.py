#!/usr/bin/env python3
"""Offline analyzer: turn current-affairs radar items into exam-signal fields.

Phase 1 helper for Issue #74 (時事庫 = 國考命題趨勢資料庫).

- Does NOT modify production files by default.
- Does NOT touch frontend, workflows, or Netlify.
- Reads auto/current_affairs.json and writes an enhanced snapshot for review.

Usage:
  python3 scripts/analyze_current_affairs_signals.py
  python3 scripts/analyze_current_affairs_signals.py --input auto/current_affairs.json --output audit/current_affairs_signals_preview.json
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# High-value law names commonly tested (from data/legal_watch_names.json).
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
    "制度上路", "正式實施", "通過", "院會通過",
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
    "社會安全網", "制度改善", "爭議",
]
ESSAY_MEDIUM = [
    "政策", "制度", "服務", "支持", " quant", " quant", " quant",
]
# Fix accidental corruption above in ESSAY_MEDIUM - will rewrite cleanly

MCQ_HIGH = [
    r"\d{1,3}[,，]?\d{3}",  # amounts like 18,000 / 18000
    r"每月", r"每年", r"追溯自", r"自\d+年", r"第\d+條",
    r"主管機關", r"衛福部", r"內政部", r"勞動部",
    r"施行細則", r"辦法", r"條例", r"補助方案",
]
MCQ_MEDIUM = [
    "補助", "津貼", "給付", "服務", "制度", "法規", "調查",
]

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


def text_of(row: dict) -> str:
    return f"{row.get('title') or ''} {row.get('summary') or ''}"


def extract_bracket_laws(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"《([^》]{2,40})》", text)))


def extract_known_laws(text: str) -> list[str]:
    hits = [name for name in KNOWN_LAWS if name in text]
    return list(dict.fromkeys(hits))


def level_from_hits(text: str, high_terms: list[str], medium_terms: list[str], low_terms: list[str] | None = None) -> str:
    low_terms = low_terms or []
    high = sum(1 for t in high_terms if t in text)
    medium = sum(1 for t in medium_terms if t in text)
    low = sum(1 for t in low_terms if t in text)
    if high >= 1 and low == 0:
        return "high"
    if high >= 1 and low >= 1:
        return "medium"
    if medium >= 2 or (medium >= 1 and high == 0 and low == 0):
        return "medium"
    if low >= 1 and high == 0 and medium <= 1:
        return "low"
    return "medium" if medium >= 1 else "low"


def score_policy_signal(text: str) -> str:
    return level_from_hits(text, POLICY_HIGH, POLICY_MEDIUM, POLICY_LOW)


def score_essay_value(text: str, category: str) -> str:
    high_terms = ESSAY_HIGH + [
        "社工", "專業", "倫理", "通報", "保護令", "安置", "復元",
        "合理調整", "自立生活", "家庭照顧者", "跨網絡",
    ]
    medium_terms = ["政策", "制度", "服務", "支持", "福利", "權益保障", "方案"]
    low_terms = ["宣導", "活動", "記者會", "響應", "倡議活動"]
    base = level_from_hits(text, high_terms, medium_terms, low_terms)
    # Categories that are intrinsically more essay-friendly get a mild bump.
    if category in {"社工專業與社福制度", "兒少保護", "家暴與性暴力", "身障與人權"} and base == "low":
        return "medium"
    return base


def score_mcq_fact_density(text: str) -> str:
    high_hits = 0
    for pat in MCQ_HIGH:
        if re.search(pat, text):
            high_hits += 1
    medium_hits = sum(1 for t in MCQ_MEDIUM if t in text)
    if high_hits >= 2:
        return "high"
    if high_hits == 1 or medium_hits >= 3:
        return "medium"
    if medium_hits >= 1:
        return "medium"
    return "low"


def build_exam_point_summary(row: dict, laws: list[str], policy: str, essay: str, mcq: str) -> str:
    category = str(row.get("category") or "時事")
    title = str(row.get("title") or "").strip()
    hint = CATEGORY_ESSAY_HINT.get(category, "政策／制度與社工實務考點")
    law_part = f"涉及「{'、'.join(laws[:2])}」。" if laws else ""

    focus = []
    if policy == "high":
        focus.append("制度或給付已有明確變動")
    elif policy == "medium":
        focus.append("政策／制度動向值得追蹤")
    if essay in {"high", "medium"}:
        focus.append(f"申論可從{hint}切入")
    if mcq == "high":
        focus.append("含較具體的數字、日期或法規事實，利於選擇題記憶")
    elif mcq == "medium":
        focus.append("有一定制度名詞與事實點")

    focus_text = "；".join(focus) if focus else "可作為背景題材，命題訊號偏弱"
    # Keep summary short and signal-oriented (not a news rewrite).
    core = title[:40] + ("…
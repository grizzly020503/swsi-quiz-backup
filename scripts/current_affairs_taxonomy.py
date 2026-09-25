#!/usr/bin/env python3
"""Deterministic bilingual taxonomy helpers for SWSI current-affairs analysis.

No model calls and no translation API. English and Chinese phrases are mapped
into a small shared set of social-work exam concepts so classification and
cross-language event identity can fail closed.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

CONCEPTS = {
    "child_protection": {
        "category": "兒少保護",
        "tag": "兒少保護",
        "aliases": [
            "兒少保護", "兒童保護", "兒虐", "虐童", "child protection",
            "child safeguarding", "protect children",
        ],
    },
    "child_rights": {
        "category": "兒少保護",
        "tag": "兒童權利",
        "aliases": [
            "兒童權利", "兒童權利公約", "crc", "child rights",
            "rights of the child", "convention on the rights of the child",
        ],
    },
    "mental_health": {
        "category": "心理健康與成癮",
        "tag": "心理健康",
        "aliases": [
            "心理健康", "精神衛生", "mental health", "psychosocial support",
            "psychosocial wellbeing", "psychosocial well-being",
        ],
    },
    "suicide_prevention": {
        "category": "心理健康與成癮",
        "tag": "自殺防治",
        "aliases": ["自殺防治", "自殺預防", "suicide prevention", "prevent suicide"],
    },
    "disability_rights": {
        "category": "身障與人權",
        "tag": "身障權利",
        "aliases": [
            "身心障礙", "障礙者權利", "crpd", "disability rights",
            "persons with disabilities", "people with disabilities",
        ],
    },
    "refugees_migration": {
        "category": "移工與新住民",
        "tag": "移民與難民",
        "aliases": [
            "移民", "難民", "移工", "refugee", "refugees", "migrant",
            "migrants", "migration", "asylum seeker", "asylum seekers",
        ],
    },
    "gender_violence": {
        "category": "家暴與性暴力",
        "tag": "性別暴力",
        "aliases": [
            "家庭暴力", "家暴", "性暴力", "性侵", "gender-based violence",
            "gender based violence", "domestic violence", "sexual violence",
        ],
    },
    "social_protection": {
        "category": "社會救助與居住",
        "tag": "社會保障",
        "aliases": [
            "社會救助", "貧窮", "social protection", "social assistance",
            "income support", "poverty reduction",
        ],
    },
    "labor_rights": {
        "category": "勞動與社會保障",
        "tag": "勞動權益",
        "aliases": [
            "勞工權益", "勞動權益", "社會保險", "labour rights", "labor rights",
            "social security", "employment protection", "occupational safety",
        ],
    },
    "ageing_care": {
        "category": "長照與高齡",
        "tag": "高齡與照顧",
        "aliases": [
            "長照", "高齡", "失智", "long-term care", "long term care",
            "older persons", "older people", "ageing", "aging", "dementia",
        ],
    },
    "disaster_displacement": {
        "category": "災害與社區工作",
        "tag": "災害與安置",
        "aliases": [
            "災害救助", "災民", "撤離", "disaster displacement",
            "disaster response", "emergency shelter", "humanitarian emergency",
        ],
    },
    "juvenile_justice": {
        "category": "少年司法與犯罪防治",
        "tag": "少年司法",
        "aliases": [
            "少年司法", "觸法少年", "juvenile justice", "youth justice",
            "children in conflict with the law",
        ],
    },
    "restorative_justice": {
        "category": "司法保護與修復式司法",
        "tag": "修復式司法",
        "aliases": [
            "修復式司法", "犯罪被害人", "被害人保護", "restorative justice",
            "victim support", "victim protection", "crime victims",
        ],
    },
    "family_policy": {
        "category": "性別與家庭政策",
        "tag": "家庭政策",
        "aliases": [
            "托育", "育兒", "家庭政策", "少子化", "childcare", "child care",
            "family policy", "parental leave", "care leave",
        ],
    },
    "student_support": {
        "category": "教育與學生輔導",
        "tag": "學生輔導",
        "aliases": [
            "學生輔導", "校園霸凌", "中輟", "student support",
            "school counselling", "school counseling", "school bullying",
            "dropout prevention",
        ],
    },
}

AGENCIES = {
    "who": ["who", "world health organization", "世界衛生組織"],
    "unicef": ["unicef", "united nations children's fund", "聯合國兒童基金會"],
    "ilo": ["ilo", "international labour organization", "international labor organization", "國際勞工組織"],
    "un": ["united nations", "un news", "聯合國"],
    "unhcr": ["unhcr", "un refugee agency", "united nations high commissioner for refugees", "聯合國難民署"],
}

EN_POLICY_TERMS = [
    "policy", "policies", "law", "legislation", "reform", "guidance", "guideline",
    "standards", "strategy", "programme", "program", "services", "rights",
    "protection", "benefit", "benefits", "social protection", "framework",
    "action plan", "recommendation", "recommendations",
]

_CJK_RE = re.compile(r"[一-龥]")
_ASCII_WORD_RE = re.compile(r"[a-z0-9]")


def _contains(text: str, alias: str) -> bool:
    hay = str(text or "").casefold()
    needle = str(alias or "").casefold().strip()
    if not needle:
        return False
    if _ASCII_WORD_RE.search(needle) and not _CJK_RE.search(needle):
        pattern = re.escape(needle).replace(r"\ ", r"\s+")
        return re.search(r"(?<![a-z0-9])" + pattern + r"(?![a-z0-9])", hay) is not None
    return needle in hay


def canonical_concepts(text: str) -> set[str]:
    out = set()
    for key, spec in CONCEPTS.items():
        if any(_contains(text, alias) for alias in spec["aliases"]):
            out.add(key)
    return out


def concept_tags(keys) -> list[str]:
    return [
        str(CONCEPTS[key]["tag"])
        for key in sorted(set(keys or []))
        if key in CONCEPTS
    ]


def concept_category_counts(keys) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in set(keys or []):
        spec = CONCEPTS.get(key)
        if not spec:
            continue
        category = str(spec["category"])
        counts[category] = counts.get(category, 0) + 1
    return counts


def canonical_agencies(text: str) -> set[str]:
    out = set()
    for key, aliases in AGENCIES.items():
        if any(_contains(text, alias) for alias in aliases):
            out.add(key)
    return out


def english_policy_hits(text: str) -> list[str]:
    return [term for term in EN_POLICY_TERMS if _contains(text, term)]


def has_cjk(text: str) -> bool:
    return _CJK_RE.search(str(text or "")) is not None


def is_english_dominant(text: str) -> bool:
    s = str(text or "")
    letters = sum(ch.isascii() and ch.isalpha() for ch in s)
    cjk = len(_CJK_RE.findall(s))
    return letters >= 20 and letters >= max(1, cjk * 3)


def _number_key(raw: str, multiplier: Decimal = Decimal(1)) -> str | None:
    try:
        value = Decimal(raw.replace(",", "")) * multiplier
    except (InvalidOperation, AttributeError):
        return None
    if value != value.to_integral_value():
        return None
    number = int(value)
    if 1900 <= number <= 2100:
        return None
    if number < 100:
        return None
    return f"num:{number}"


def canonical_fact_keys(text: str) -> set[str]:
    s = str(text or "").casefold()
    out = set()

    for raw in re.findall(r"(\d+(?:\.\d+)?)\s*%", s):
        out.add(f"pct:{raw.rstrip('0').rstrip('.') if '.' in raw else raw}")

    for raw, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(million|billion)\b", s):
        key = _number_key(raw, Decimal(1_000_000 if unit == "million" else 1_000_000_000))
        if key:
            out.add(key)

    for raw, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(萬|億)", s):
        key = _number_key(raw, Decimal(10_000 if unit == "萬" else 100_000_000))
        if key:
            out.add(key)

    for raw in re.findall(r"\b\d{1,3}(?:,\d{3})+\b", s):
        key = _number_key(raw)
        if key:
            out.add(key)

    return out

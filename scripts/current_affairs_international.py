#!/usr/bin/env python3
"""Deterministic English-to-SWSI current-affairs taxonomy and cross-language metadata."""
from __future__ import annotations

import re

CATEGORY_SLUG = {
    "兒少保護": "child-protection",
    "家暴與性暴力": "gender-violence",
    "心理健康與成癮": "mental-health",
    "長照與高齡": "ageing-care",
    "社會救助與居住": "social-protection",
    "身障與人權": "disability-rights",
    "移工與新住民": "migration",
    "勞動與社會保障": "labor-social-security",
    "教育與學生輔導": "education-support",
    "司法保護與修復式司法": "justice-protection",
    "少年司法與犯罪防治": "juvenile-justice",
    "性別與家庭政策": "family-gender-policy",
    "災害與社區工作": "disaster-community",
    "社工專業與社福制度": "social-work-system",
}

# phrase -> Chinese exam tag, canonical event facet.
ENGLISH_RULES = [
    ("兒少保護", 4, {
        "child protection": ("兒少保護", "child-protection"),
        "child rights": ("兒童權利", "child-rights"),
        "children's rights": ("兒童權利", "child-rights"),
        "child sexual abuse": ("性剝削", "child-sexual-abuse"),
        "sexual exploitation of children": ("性剝削", "child-sexual-abuse"),
        "child sexual exploitation": ("性剝削", "child-sexual-abuse"),
        "child abuse": ("兒虐", "child-abuse"),
        "child marriage": ("兒童權利", "child-marriage"),
    }),
    ("家暴與性暴力", 4, {
        "domestic violence": ("家庭暴力", "domestic-violence"),
        "gender-based violence": ("性暴力", "gender-based-violence"),
        "violence against women": ("性暴力", "violence-against-women"),
        "sexual violence": ("性暴力", "sexual-violence"),
        "intimate partner violence": ("家庭暴力", "intimate-partner-violence"),
    }),
    ("心理健康與成癮", 3, {
        "mental health": ("心理健康", "mental-health"),
        "psychosocial support": ("心理社會支持", "psychosocial-support"),
        "suicide prevention": ("自殺防治", "suicide-prevention"),
        "substance use disorder": ("成癮", "substance-use"),
        "addiction services": ("成癮", "addiction-services"),
    }),
    ("長照與高齡", 3, {
        "older persons": ("高齡", "older-persons"),
        "older people": ("高齡", "older-persons"),
        "ageing": ("高齡", "ageing"),
        "long-term care": ("長照", "long-term-care"),
        "dementia": ("失智", "dementia"),
        "caregivers": ("照顧者", "caregivers"),
    }),
    ("社會救助與居住", 3, {
        "social protection": ("社會保障", "social-protection"),
        "cash transfers": ("現金給付", "cash-transfers"),
        "extreme poverty": ("貧窮", "poverty"),
        "housing rights": ("居住權", "housing-rights"),
        "homelessness": ("無家者", "homelessness"),
    }),
    ("身障與人權", 3, {
        "persons with disabilities": ("身心障礙", "disability-rights"),
        "people with disabilities": ("身心障礙", "disability-rights"),
        "disability rights": ("身障權利", "disability-rights"),
        "reasonable accommodation": ("合理調整", "reasonable-accommodation"),
        "crpd": ("CRPD", "crpd"),
    }),
    ("移工與新住民", 3, {
        "migrant workers": ("移工", "migrant-workers"),
        "refugees": ("難民", "refugees"),
        "asylum seekers": ("難民", "asylum"),
        "human trafficking": ("人口販運", "human-trafficking"),
        "trafficking in persons": ("人口販運", "human-trafficking"),
    }),
    ("勞動與社會保障", 3, {
        "social security": ("社會保障", "social-security"),
        "minimum wage": ("最低工資", "minimum-wage"),
        "unemployment protection": ("失業保障", "unemployment-protection"),
        "occupational safety": ("職業安全", "occupational-safety"),
        "labour rights": ("勞工權益", "labor-rights"),
        "labor rights": ("勞工權益", "labor-rights"),
        "decent work": ("勞動權益", "decent-work"),
    }),
    ("教育與學生輔導", 3, {
        "school bullying": ("校園霸凌", "school-bullying"),
        "school dropout": ("中輟", "school-dropout"),
        "inclusive education": ("融合教育", "inclusive-education"),
        "special education": ("特殊教育", "special-education"),
        "student support": ("學生輔導", "student-support"),
        "school counselling": ("學生輔導", "student-support"),
        "school counseling": ("學生輔導", "student-support"),
    }),
    ("司法保護與修復式司法", 4, {
        "victims' rights": ("犯罪被害人權益", "victims-rights"),
        "victim rights": ("犯罪被害人權益", "victims-rights"),
        "restorative justice": ("修復式司法", "restorative-justice"),
        "victim compensation": ("被害補償金", "victim-compensation"),
        "community corrections": ("社區處遇", "community-corrections"),
        "probation services": ("保護管束", "probation"),
    }),
    ("少年司法與犯罪防治", 3, {
        "juvenile justice": ("少年司法", "juvenile-justice"),
        "children in conflict with the law": ("觸法少年", "children-in-conflict-law"),
    }),
    ("性別與家庭政策", 3, {
        "gender equality": ("性別平等", "gender-equality"),
        "childcare": ("托育", "childcare"),
        "parental leave": ("育嬰留職停薪", "parental-leave"),
        "family policy": ("家庭政策", "family-policy"),
        "care economy": ("照顧經濟", "care-economy"),
    }),
    ("災害與社區工作", 3, {
        "disaster response": ("災害救助", "disaster-response"),
        "emergency shelter": ("安置", "emergency-shelter"),
        "community resilience": ("社區韌性", "community-resilience"),
        "disaster displacement": ("災害安置", "disaster-displacement"),
    }),
    ("社工專業與社福制度", 4, {
        "social work": ("社會工作", "social-work"),
        "social workers": ("社工", "social-work"),
        "social services": ("社會服務", "social-services"),
        "case management": ("個案管理", "case-management"),
        "child welfare services": ("兒少福利", "child-welfare-services"),
    }),
]

ENGLISH_POLICY_TERMS = {
    "policy", "policies", "law", "legislation", "rights", "protection",
    "framework", "guideline", "guidelines", "strategy", "reform", "standards",
    "services", "benefits", "social protection", "convention", "programme",
    "program", "support", "access", "coverage",
}

ENGLISH_LOW_VALUE = {
    "conference", "webinar", "ceremony", "award", "awards", "anniversary",
    "speech", "remarks", "commemoration", "exhibition", "workshop",
}

ORG_ALIASES = {
    "unicef": ("unicef", "united nations children's fund", "聯合國兒童基金會"),
    "who": ("world health organization", "who", "世界衛生組織", "世衛"),
    "ilo": ("international labour organization", "international labor organization", "ilo", "國際勞工組織"),
    "un": ("united nations", "聯合國"),
    "unhcr": ("unhcr", "un refugee agency", "聯合國難民署"),
}

BILINGUAL_FACETS = {
    "child-rights": ("child rights", "children's rights", "兒童權利"),
    "child-sexual-abuse": ("child sexual abuse", "child sexual exploitation", "性剝削", "兒少性剝削"),
    "mental-health": ("mental health", "心理健康"),
    "psychosocial-support": ("psychosocial support", "心理社會支持"),
    "social-protection": ("social protection", "社會保障", "社會救助"),
    "refugees": ("refugees", "難民"),
    "disability-rights": ("disability rights", "persons with disabilities", "身心障礙", "身障權利"),
    "ageing": ("ageing", "older persons", "高齡", "老人"),
    "long-term-care": ("long-term care", "長照"),
    "gender-based-violence": ("gender-based violence", "性暴力"),
    "domestic-violence": ("domestic violence", "家庭暴力", "家暴"),
    "social-security": ("social security", "社會保障"),
    "minimum-wage": ("minimum wage", "最低工資"),
    "childcare": ("childcare", "托育"),
    "juvenile-justice": ("juvenile justice", "少年司法"),
    "restorative-justice": ("restorative justice", "修復式司法"),
    "human-trafficking": ("human trafficking", "trafficking in persons", "人口販運"),
}


def _contains(text: str, phrase: str) -> bool:
    haystack = str(text or "")
    needle = str(phrase or "").strip()
    if not needle:
        return False
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 '\-]*", needle):
        pattern = r"(?<![A-Za-z0-9])" + re.escape(needle) + r"(?![A-Za-z0-9])"
        return re.search(pattern, haystack, flags=re.IGNORECASE) is not None
    return needle.casefold() in haystack.casefold()


def score_english_item(title: str, summary: str, source_type: str = "official"):
    title_text = str(title or "")
    text = f"{title or ''} {summary or ''}"
    best = None
    best_tags: list[str] = []
    best_facets: list[str] = []

    policy_hits = [p for p in ENGLISH_POLICY_TERMS if _contains(text, p)]
    for category, base, terms in ENGLISH_RULES:
        title_hits = [p for p in terms if _contains(title_text, p)]
        all_hits = [p for p in terms if _contains(text, p)]
        if not all_hits:
            continue
        if not title_hits and not (len(all_hits) >= 2 and policy_hits):
            continue
        score = base + min(2, max(0, len(title_hits) - 1))
        if policy_hits:
            score += 1
        if source_type == "official":
            score += 1
        if any(_contains(title_text, noise) for noise in ENGLISH_LOW_VALUE):
            score -= 3
        candidate = (score, len(title_hits), category)
        if best is None or candidate[:2] > best[:2]:
            best = candidate
            best_tags = [terms[p][0] for p in all_hits]
            best_facets = [terms[p][1] for p in all_hits]

    if best is None or best[0] < 5:
        return None
    score, _title_hits, category = best
    tags = list(dict.fromkeys(best_tags + ["國際官方"]))[:10]
    facets = list(dict.fromkeys([CATEGORY_SLUG.get(category, category)] + best_facets))
    return min(10, score), category, tags, facets


def event_metadata(title: str, summary: str, category: str, tags: list[str] | None = None) -> dict:
    text = f"{title or ''} {summary or ''}"
    facets = {CATEGORY_SLUG.get(category, category)}
    for key, aliases in BILINGUAL_FACETS.items():
        if any(_contains(text, alias) for alias in aliases):
            facets.add(key)

    # Chinese exam tags may already encode useful bilingual concepts.
    for tag in tags or []:
        for key, aliases in BILINGUAL_FACETS.items():
            if any(_contains(str(tag), alias) or _contains(alias, str(tag)) for alias in aliases):
                facets.add(key)

    orgs = set()
    for key, aliases in ORG_ALIASES.items():
        if any(_contains(text, alias) for alias in aliases):
            orgs.add(key)

    numbers = {
        token.replace(",", "")
        for token in re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", text)
        if token.replace(",", "") not in {"2024", "2025", "2026", "2027"}
    }
    return {
        "event_facets": sorted(facets),
        "org_keys": sorted(orgs),
        "numeric_anchors": sorted(numbers),
    }

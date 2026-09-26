#!/usr/bin/env python3
"""SWSI social-work knowledge tree for current-affairs classification.

This module is deterministic and model-free. It treats 社會工作管理 as the
cross-subject top layer used to organize current affairs. It is NOT an
additional national-exam subject.

Structure:
    社會工作管理
      -> management domains
      -> the five existing exam subjects
      -> event/topic tags

The classifier is intentionally additive. Existing current-affairs relevance,
event clustering and trend scoring remain separate contracts.
"""
from __future__ import annotations

from collections.abc import Iterable

KNOWLEDGE_ROOT = "社會工作管理"

EXAM_SUBJECTS = (
    "社會工作",
    "社會工作直接服務",
    "人類行為與社會環境",
    "社會工作研究方法",
    "社會政策與社會立法",
)

MANAGEMENT_DOMAINS = (
    "規劃與政策執行",
    "組織治理與責信",
    "人力與督導",
    "服務輸送與跨網絡",
    "方案與資源管理",
    "品質與風險管理",
    "成效評估與證據",
    "倫理與權利保障",
)

CATEGORY_SUBJECT_DEFAULTS = {
    "兒少保護": ("社會工作直接服務", "人類行為與社會環境", "社會政策與社會立法", "社會工作"),
    "家暴與性暴力": ("社會工作直接服務", "人類行為與社會環境", "社會政策與社會立法", "社會工作"),
    "心理健康與成癮": ("人類行為與社會環境", "社會工作直接服務", "社會工作", "社會政策與社會立法"),
    "長照與高齡": ("社會政策與社會立法", "社會工作直接服務", "人類行為與社會環境", "社會工作"),
    "社會救助與居住": ("社會政策與社會立法", "社會工作", "社會工作直接服務"),
    "身障與人權": ("社會政策與社會立法", "社會工作", "社會工作直接服務", "人類行為與社會環境"),
    "移工與新住民": ("社會工作", "社會政策與社會立法", "社會工作直接服務", "人類行為與社會環境"),
    "勞動與社會保障": ("社會政策與社會立法", "社會工作"),
    "教育與學生輔導": ("社會工作直接服務", "人類行為與社會環境", "社會工作", "社會政策與社會立法"),
    "司法保護與修復式司法": ("社會工作直接服務", "社會政策與社會立法", "社會工作"),
    "少年司法與犯罪防治": ("社會工作直接服務", "人類行為與社會環境", "社會政策與社會立法", "社會工作"),
    "性別與家庭政策": ("社會政策與社會立法", "人類行為與社會環境", "社會工作", "社會工作直接服務"),
    "災害與社區工作": ("社會工作", "社會工作直接服務", "人類行為與社會環境", "社會政策與社會立法"),
    "社工專業與社福制度": ("社會工作", "社會工作直接服務", "社會政策與社會立法"),
}

CATEGORY_MANAGEMENT_DEFAULTS = {
    "兒少保護": ("品質與風險管理", "服務輸送與跨網絡", "倫理與權利保障"),
    "家暴與性暴力": ("品質與風險管理", "服務輸送與跨網絡", "倫理與權利保障"),
    "心理健康與成癮": ("服務輸送與跨網絡", "倫理與權利保障", "品質與風險管理"),
    "長照與高齡": ("服務輸送與跨網絡", "方案與資源管理", "規劃與政策執行"),
    "社會救助與居住": ("規劃與政策執行", "方案與資源管理", "倫理與權利保障"),
    "身障與人權": ("倫理與權利保障", "服務輸送與跨網絡", "規劃與政策執行"),
    "移工與新住民": ("倫理與權利保障", "服務輸送與跨網絡", "規劃與政策執行"),
    "勞動與社會保障": ("規劃與政策執行", "倫理與權利保障", "方案與資源管理"),
    "教育與學生輔導": ("服務輸送與跨網絡", "品質與風險管理", "倫理與權利保障"),
    "司法保護與修復式司法": ("服務輸送與跨網絡", "倫理與權利保障", "規劃與政策執行"),
    "少年司法與犯罪防治": ("服務輸送與跨網絡", "倫理與權利保障", "品質與風險管理"),
    "性別與家庭政策": ("規劃與政策執行", "倫理與權利保障", "方案與資源管理"),
    "災害與社區工作": ("品質與風險管理", "服務輸送與跨網絡", "方案與資源管理"),
    "社工專業與社福制度": ("人力與督導", "組織治理與責信", "服務輸送與跨網絡"),
}

MANAGEMENT_TERM_RULES = {
    "規劃與政策執行": (
        "政策", "制度", "修法", "修正", "施行", "上路", "新制", "法規",
        "條例", "給付", "津貼", "補助", "資格", "計畫", "方案", "policy",
        "legislation", "reform", "implementation",
    ),
    "組織治理與責信": (
        "組織", "治理", "責信", "權責", "透明", "監督", "稽核", "法遵",
        "機構", "委外", "治理機制", "accountability", "governance",
    ),
    "人力與督導": (
        "社工人力", "人力不足", "人力", "督導", "案量", "工作負荷", "招募",
        "留任", "離職", "執業環境", "職場安全", "supervision", "workforce",
    ),
    "服務輸送與跨網絡": (
        "服務輸送", "跨網絡", "跨專業", "轉介", "協作", "合作", "通報",
        "個案管理", "訪視", "資源連結", "整合服務", "service delivery",
        "case management", "referral",
    ),
    "方案與資源管理": (
        "方案", "計畫", "補助", "預算", "資源配置", "資源連結", "委託",
        "委外", "給付", "服務量能", "resource allocation", "programme",
        "program",
    ),
    "品質與風險管理": (
        "風險", "風險評估", "品質", "重大事件", "兒虐", "虐童", "家暴",
        "性暴力", "危機", "安全", "保護", "安置", "檢討", "risk",
        "safeguarding", "quality",
    ),
    "成效評估與證據": (
        "成效", "評估", "統計", "調查結果", "研究", "指標", "監測", "資料",
        "實證", "evidence", "evaluation", "survey", "statistics", "report finds",
    ),
    "倫理與權利保障": (
        "倫理", "權益", "人權", "最佳利益", "自決", "保密", "知情同意",
        "合理調整", "反歧視", "兒童權利", "rights", "ethics",
        "reasonable accommodation",
    ),
}

SUBJECT_TERM_RULES = {
    "社會工作": (
        "社工", "社會工作", "倫理", "專業", "倡導", "增權", "充權", "優勢觀點",
        "社會正義", "社區", "文化能力", "人權", "社會支持", "social work",
        "advocacy", "empowerment",
    ),
    "社會工作直接服務": (
        "評估", "處遇", "介入", "通報", "安置", "個案管理", "危機介入",
        "家庭工作", "團體工作", "訪視", "轉介", "輔導", "保護服務",
        "case management", "intervention", "assessment", "referral",
    ),
    "人類行為與社會環境": (
        "兒童發展", "青少年", "高齡", "老化", "失智", "心理健康", "精神衛生",
        "創傷", "依附", "家庭系統", "成癮", "行為", "社會環境", "發展",
        "trauma", "attachment", "mental health", "dementia",
    ),
    "社會工作研究方法": (
        "研究", "調查結果", "統計", "抽樣", "問卷", "訪談", "資料分析",
        "成效評估", "評估研究", "指標", "信度", "效度", "survey",
        "statistics", "evaluation", "research", "data analysis",
    ),
    "社會政策與社會立法": (
        "政策", "制度", "修法", "修正", "法律", "法規", "條例", "施行細則",
        "補助", "津貼", "給付", "保險", "最低工資", "資格", "主管機關",
        "生效", "policy", "law", "legislation", "benefit", "social insurance",
    ),
}


def _ordered_unique(values: Iterable[str], allowed: tuple[str, ...] | None = None) -> list[str]:
    seen = set()
    out = []
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        if allowed is not None and value not in allowed:
            continue
        seen.add(value)
        out.append(value)
    return out


def _hits(text: str, terms: Iterable[str]) -> bool:
    hay = str(text or "").casefold()
    return any(str(term).casefold() in hay for term in terms if str(term).strip())


def classify_event_knowledge(
    text: str,
    *,
    category: str = "",
    exam_tags: Iterable[str] | None = None,
) -> dict:
    """Classify an accepted event into the management root and five-subject axes."""
    body = str(text or "")
    category = str(category or "").strip()
    tags = _ordered_unique(exam_tags or [])

    management = list(CATEGORY_MANAGEMENT_DEFAULTS.get(category, ()))
    for domain in MANAGEMENT_DOMAINS:
        if _hits(body, MANAGEMENT_TERM_RULES.get(domain, ())):
            management.append(domain)
    management = _ordered_unique(management, MANAGEMENT_DOMAINS)[:5]

    subjects = list(CATEGORY_SUBJECT_DEFAULTS.get(category, ("社會工作",)))
    for subject in EXAM_SUBJECTS:
        if _hits(body, SUBJECT_TERM_RULES.get(subject, ())):
            subjects.append(subject)
    subjects = _ordered_unique(subjects, EXAM_SUBJECTS)

    topics = _ordered_unique([category, *tags])[:10]

    return {
        "knowledge_root": KNOWLEDGE_ROOT,
        "management_domains": management,
        "exam_subject_axes": subjects,
        "knowledge_topics": topics,
    }

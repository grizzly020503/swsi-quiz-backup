#!/usr/bin/env python3
"""SWSI social-work knowledge tree for accepted current-affairs events.

This module is deterministic and model-free. It does NOT decide whether a news
item is allowed into the current-affairs database. Admission/relevance happens
upstream. This module only answers the learning question after an event has
already been accepted:

    社會工作管理（跨科整合層）
      -> management domains
      -> the five existing exam subjects
      -> subject-specific study topics

社會工作管理 is a platform organization lens, NOT a sixth national-exam
subject. The five subject names remain exactly aligned with the question bank.
"""
from __future__ import annotations

from collections.abc import Iterable

KNOWLEDGE_ROOT = "社會工作管理"
KNOWLEDGE_MODEL = "management-lens-over-five-exam-subjects-v2"

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

# Defaults come from the already-accepted event category. They are intentionally
# narrower than a "everything is related to everything" knowledge graph.
CATEGORY_SUBJECT_DEFAULTS = {
    "兒少保護": ("社會工作直接服務", "人類行為與社會環境", "社會政策與社會立法", "社會工作"),
    "家暴與性暴力": ("社會工作直接服務", "人類行為與社會環境", "社會政策與社會立法", "社會工作"),
    "心理健康與成癮": ("人類行為與社會環境", "社會工作直接服務", "社會工作"),
    "長照與高齡": ("社會政策與社會立法", "人類行為與社會環境", "社會工作直接服務"),
    "社會救助與居住": ("社會政策與社會立法", "社會工作"),
    "身障與人權": ("社會政策與社會立法", "社會工作", "人類行為與社會環境"),
    "移工與新住民": ("社會工作", "社會政策與社會立法", "人類行為與社會環境"),
    "勞動與社會保障": ("社會政策與社會立法", "社會工作"),
    "教育與學生輔導": ("社會工作直接服務", "人類行為與社會環境", "社會政策與社會立法", "社會工作"),
    "司法保護與修復式司法": ("社會工作直接服務", "社會政策與社會立法", "社會工作"),
    "少年司法與犯罪防治": ("社會工作直接服務", "人類行為與社會環境", "社會政策與社會立法", "社會工作"),
    "性別與家庭政策": ("社會政策與社會立法", "社會工作"),
    "災害與社區工作": ("社會工作", "社會工作直接服務", "人類行為與社會環境"),
    "社工專業與社福制度": ("社會工作", "社會政策與社會立法"),
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
    # Do not assume every story about a social worker is a staffing/supervision
    # story. Misconduct, for example, is primarily governance/accountability.
    "社工專業與社福制度": ("組織治理與責信", "倫理與權利保障"),
}

CATEGORY_SUBJECT_TOPICS = {
    "兒少保護": {
        "社會工作": ("專業倫理與兒童最佳利益", "權利倡導與社會正義"),
        "社會工作直接服務": ("兒少保護風險評估", "家庭評估與危機介入"),
        "人類行為與社會環境": ("兒童發展、依附與創傷", "家庭系統與風險保護因子"),
        "社會政策與社會立法": ("兒少福利與保護法制", "責任通報與保護體系"),
    },
    "家暴與性暴力": {
        "社會工作": ("被害人權利與專業倫理",),
        "社會工作直接服務": ("危險評估與安全計畫", "創傷知情與危機介入"),
        "人類行為與社會環境": ("創傷反應與家庭互動",),
        "社會政策與社會立法": ("家暴與性暴力防治制度", "保護令與被害人權益"),
    },
    "心理健康與成癮": {
        "社會工作": ("復元取向、去污名與權利保障",),
        "社會工作直接服務": ("危機介入、個案管理與資源連結",),
        "人類行為與社會環境": ("心理健康、精神疾病與成癮",),
        "社會政策與社會立法": ("精神衛生與社區支持制度",),
    },
    "長照與高齡": {
        "社會工作": ("高齡者權益與社區支持",),
        "社會工作直接服務": ("長照個案管理與家庭照顧者支持",),
        "人類行為與社會環境": ("老化、失智與生命歷程",),
        "社會政策與社會立法": ("長照制度、老人福利與社會保障",),
    },
    "社會救助與居住": {
        "社會工作": ("貧窮、社會排除與社會正義",),
        "社會工作直接服務": ("需求評估與資源連結",),
        "社會政策與社會立法": ("社會救助、所得保障與居住權",),
    },
    "身障與人權": {
        "社會工作": ("增權、自立生活與障礙者權利",),
        "社會工作直接服務": ("需求評估、個案管理與社區支持",),
        "人類行為與社會環境": ("障礙與環境互動",),
        "社會政策與社會立法": ("CRPD、合理調整與身障福利制度",),
    },
    "移工與新住民": {
        "社會工作": ("文化能力、反歧視與權利倡導",),
        "社會工作直接服務": ("跨文化評估與資源連結",),
        "人類行為與社會環境": ("遷移、適應與家庭社會環境",),
        "社會政策與社會立法": ("移民、勞動與社會權益制度",),
    },
    "勞動與社會保障": {
        "社會工作": ("勞動權益、社會正義與弱勢支持",),
        "社會政策與社會立法": ("社會保險、就業安全與勞動政策",),
    },
    "教育與學生輔導": {
        "社會工作": ("學校社會工作與權利倡導",),
        "社會工作直接服務": ("學生評估、危機介入與跨網絡服務",),
        "人類行為與社會環境": ("兒少發展、家庭與學校生態系統",),
        "社會政策與社會立法": ("學生輔導、教育權與校園保護制度",),
    },
    "司法保護與修復式司法": {
        "社會工作": ("人權、修復與社區復歸",),
        "社會工作直接服務": ("被害人支持、修復式處遇與個案服務",),
        "社會政策與社會立法": ("犯罪被害人權益與社區處遇制度",),
    },
    "少年司法與犯罪防治": {
        "社會工作": ("去標籤、權利保障與社區復歸",),
        "社會工作直接服務": ("少年評估、家庭工作與社區處遇",),
        "人類行為與社會環境": ("青少年發展、偏差行為與環境因素",),
        "社會政策與社會立法": ("少年司法與保護處分制度",),
    },
    "性別與家庭政策": {
        "社會工作": ("性別平等、照顧正義與家庭支持",),
        "社會工作直接服務": ("家庭工作與照顧支持",),
        "人類行為與社會環境": ("家庭系統、性別角色與生命歷程",),
        "社會政策與社會立法": ("家庭政策、托育與性別制度",),
    },
    "災害與社區工作": {
        "社會工作": ("社區工作、倡導與社區韌性",),
        "社會工作直接服務": ("災難危機介入、安置與資源連結",),
        "人類行為與社會環境": ("創傷、壓力因應與韌性",),
        "社會政策與社會立法": ("災害救助與社會安全網",),
    },
    "社工專業與社福制度": {
        "社會工作": ("專業倫理、專業責任與社會工作價值",),
        "社會政策與社會立法": ("社福服務體系、專業規範與制度責信",),
    },
}

# These rules only REFINE an already-accepted event. They never make a news
# item eligible for admission to the radar.
MANAGEMENT_TERM_RULES = {
    "規劃與政策執行": (
        "修法", "修正", "施行", "上路", "新制", "法規", "條例", "核定",
        "預告", "給付調整", "補助加碼", "資格放寬", "政策調整", "制度調整",
        "policy change", "implementation",
    ),
    "組織治理與責信": (
        "治理", "責信", "權責", "透明", "監督", "稽核", "法遵", "委外",
        "委託管理", "內控", "侵占", "挪用", "accountability", "governance",
    ),
    "人力與督導": (
        "社工人力", "專業人力", "照顧人力", "人力不足", "督導", "案量",
        "工作負荷", "留任", "離職", "執業環境", "職場安全",
        "supervision", "social work workforce",
    ),
    "服務輸送與跨網絡": (
        "服務輸送", "跨網絡", "跨專業", "跨局處", "轉介", "個案管理",
        "訪視", "資源連結", "整合服務", "責任通報", "case management",
        "referral", "service coordination",
    ),
    "方案與資源管理": (
        "方案管理", "資源配置", "預算", "補助", "委託", "委外", "給付",
        "服務量能", "服務據點", "名額", "resource allocation", "program funding",
    ),
    "品質與風險管理": (
        "風險", "風險評估", "品質管理", "重大事件", "兒虐", "虐童", "家暴",
        "性暴力", "危機", "安全事件", "疏失", "safeguarding",
        "risk management", "quality assurance",
    ),
    "成效評估與證據": (
        "成效評估", "評估研究", "調查結果", "統計資料", "統計顯示", "研究結果",
        "研究顯示", "實證", "evidence-based", "program evaluation",
        "survey finds", "research finds", "statistics",
    ),
    "倫理與權利保障": (
        "倫理", "權益", "人權", "最佳利益", "自決", "保密", "知情同意",
        "合理調整", "反歧視", "兒童權利", "權利保障", "rights", "ethics",
    ),
}

SUBJECT_TERM_RULES = {
    "社會工作": (
        "專業倫理", "社會工作價值", "社會正義", "倡導", "增權", "充權",
        "優勢觀點", "文化能力", "人權", "社區工作", "professional ethics",
        "advocacy", "empowerment",
    ),
    "社會工作直接服務": (
        "風險評估", "家庭評估", "需求評估", "處遇", "介入", "責任通報",
        "安置", "個案管理", "危機介入", "家庭工作", "團體工作", "訪視",
        "轉介", "保護服務", "接案", "結案", "case management",
        "intervention", "risk assessment", "referral",
    ),
    "人類行為與社會環境": (
        "兒童發展", "青少年發展", "生命週期", "生命歷程", "依附", "創傷",
        "家庭系統", "生態系統", "心理健康", "精神衛生", "成癮", "失智",
        "老化", "壓力因應", "韌性", "trauma", "attachment",
        "mental health", "dementia",
    ),
    "社會工作研究方法": (
        "調查結果", "統計資料", "統計顯示", "研究結果", "研究顯示", "樣本",
        "抽樣", "問卷", "深度訪談", "焦點團體", "資料分析", "成效評估",
        "評估研究", "信度", "效度", "evidence-based", "survey finds",
        "research finds", "statistics", "sampling", "validity", "reliability",
        "program evaluation",
    ),
    "社會政策與社會立法": (
        "修法", "修正", "法律", "法規", "條例", "施行細則", "補助", "津貼",
        "給付", "社會保險", "最低工資", "資格", "主管機關", "生效",
        "社會救助", "policy", "law", "legislation", "benefit",
    ),
}

RESEARCH_TOPIC_RULES = {
    "研究設計與資料蒐集": ("樣本", "抽樣", "問卷", "深度訪談", "焦點團體", "sampling"),
    "統計與資料解讀": ("統計資料", "統計顯示", "調查結果", "研究結果", "research finds", "survey finds", "statistics"),
    "方案與成效評估": ("成效評估", "評估研究", "program evaluation"),
    "測量品質與研究判讀": ("信度", "效度", "validity", "reliability"),
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
    """Map an accepted event into the management lens and five exam subjects."""
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

    # Research methods is evidence-sensitive. Never infer it from generic words
    # such as 資料、發展、評估 or from another subject's category default.
    if "社會工作研究方法" in subjects and not _hits(
        body, SUBJECT_TERM_RULES["社會工作研究方法"]
    ):
        subjects = [x for x in subjects if x != "社會工作研究方法"]

    subject_topics: dict[str, list[str]] = {}
    defaults = CATEGORY_SUBJECT_TOPICS.get(category, {})
    for subject in subjects:
        topics = list(defaults.get(subject, ()))
        if subject == "社會工作研究方法":
            for topic, terms in RESEARCH_TOPIC_RULES.items():
                if _hits(body, terms):
                    topics.append(topic)
            if not topics:
                topics.append("研究證據判讀")
        if topics:
            subject_topics[subject] = _ordered_unique(topics)[:4]

    knowledge_topics = _ordered_unique([category, *tags])[:10]
    paths = [f"{KNOWLEDGE_ROOT} > {domain}" for domain in management]
    for subject in subjects:
        for topic in subject_topics.get(subject, []):
            paths.append(f"{KNOWLEDGE_ROOT} > 五科整合 > {subject} > {topic}")

    return {
        "knowledge_root": KNOWLEDGE_ROOT,
        "knowledge_model": KNOWLEDGE_MODEL,
        "management_domains": management,
        "exam_subject_axes": subjects,
        "subject_topics": subject_topics,
        "knowledge_topics": knowledge_topics,
        "knowledge_paths": _ordered_unique(paths)[:20],
    }

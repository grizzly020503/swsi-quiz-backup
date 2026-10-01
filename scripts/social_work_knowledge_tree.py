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
KNOWLEDGE_MODEL = "management-hierarchy-over-five-exam-subjects-v3"

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

# The management layer is the organizing lens above the five exam subjects.
# A management domain only links to subjects that can explain that dimension;
# this avoids generating every possible domain × subject combination.
MANAGEMENT_SUBJECT_LINKS = {
    "規劃與政策執行": ("社會政策與社會立法", "社會工作"),
    "組織治理與責信": ("社會工作", "社會政策與社會立法", "社會工作研究方法"),
    "人力與督導": ("社會工作", "社會工作直接服務"),
    "服務輸送與跨網絡": ("社會工作直接服務", "社會工作", "社會政策與社會立法"),
    "方案與資源管理": ("社會工作", "社會政策與社會立法", "社會工作研究方法"),
    "品質與風險管理": ("社會工作直接服務", "社會工作", "社會工作研究方法"),
    "成效評估與證據": ("社會工作研究方法", "社會工作", "社會政策與社會立法"),
    "倫理與權利保障": (
        "社會工作", "社會工作直接服務", "社會政策與社會立法", "人類行為與社會環境",
    ),
}

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
    "社工專業與社福制度": ("社會工作", "社會政策與社會立法"),
}

CATEGORY_PRIMARY_SUBJECTS = {
    "兒少保護": ("社會工作直接服務", "社會政策與社會立法"),
    "家暴與性暴力": ("社會工作直接服務", "社會政策與社會立法"),
    "心理健康與成癮": ("人類行為與社會環境", "社會工作直接服務"),
    "長照與高齡": ("社會政策與社會立法", "社會工作直接服務"),
    "社會救助與居住": ("社會政策與社會立法", "社會工作"),
    "身障與人權": ("社會政策與社會立法", "社會工作"),
    "移工與新住民": ("社會工作", "社會政策與社會立法"),
    "勞動與社會保障": ("社會政策與社會立法",),
    "教育與學生輔導": ("社會工作直接服務", "社會政策與社會立法"),
    "司法保護與修復式司法": ("社會工作直接服務", "社會政策與社會立法"),
    "少年司法與犯罪防治": ("社會工作直接服務", "人類行為與社會環境"),
    "性別與家庭政策": ("社會政策與社會立法", "人類行為與社會環境"),
    "災害與社區工作": ("社會工作", "社會工作直接服務"),
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
    "勞動與社會保障": ("規劃與政策執行", "倫理與權利保障"),
    "教育與學生輔導": ("服務輸送與跨網絡", "品質與風險管理", "倫理與權利保障"),
    "司法保護與修復式司法": ("服務輸送與跨網絡", "倫理與權利保障", "規劃與政策執行"),
    "少年司法與犯罪防治": ("服務輸送與跨網絡", "倫理與權利保障", "品質與風險管理"),
    "性別與家庭政策": ("規劃與政策執行", "倫理與權利保障", "方案與資源管理"),
    "災害與社區工作": ("品質與風險管理", "服務輸送與跨網絡", "方案與資源管理"),
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

RESEARCH_TOPIC_RULES = {
    "研究設計與資料蒐集": ("抽樣", "問卷調查", "訪談研究", "sampling"),
    "統計與資料解讀": ("統計結果", "調查結果", "研究報告", "調查報告", "study finds", "survey results"),
    "方案與成效評估": ("成效評估", "評估研究", "evaluation study"),
    "測量品質與研究判讀": ("信度", "效度", "validity", "reliability"),
}

# The broad category "社工專業與社福制度" contains two distinct semantic lanes.
# If an event is about welfare budgets/benefits without real social-work profession
# evidence, keep it on the policy/system lane instead of inventing professional
# ethics or direct-practice relevance.
SOCIAL_WORK_PROFESSION_TERMS = (
    "社工", "社會工作者", "社工師", "社會工作師", "社會工作專業",
    "社工專業", "專業倫理", "專業責任", "專業督導", "社工督導",
    "社工人力", "社工案量", "執業環境", "social worker", "social work profession",
)
WELFARE_SYSTEM_TERMS = (
    "社福", "社會福利", "福利制度", "福利政策", "社福支出", "社福預算",
    "津貼", "給付", "補助", "福利給付", "追加預算", "社會安全網",
)
WELFARE_SYSTEM_MANAGEMENT_DEFAULTS = ("規劃與政策執行",)
WELFARE_SYSTEM_SUBJECT_DEFAULTS = ("社會政策與社會立法",)
WELFARE_SYSTEM_PRIMARY_SUBJECTS = ("社會政策與社會立法",)
WELFARE_SYSTEM_SUBJECT_TOPICS = {
    "社會政策與社會立法": ("社福服務體系、福利給付與制度責信",),
}

MANAGEMENT_TERM_RULES = {
    "規劃與政策執行": (
        "政策", "制度", "修法", "修正", "施行", "上路", "新制", "法規",
        "條例", "給付", "津貼", "補助", "資格", "計畫", "方案", "policy",
        "legislation", "reform", "implementation",
    ),
    "組織治理與責信": (
        "組織治理", "治理機制", "責信", "權責", "透明", "監督", "稽核",
        "法遵", "內控", "內部控制", "機構管理", "委外管理",
        "accountability", "governance",
    ),
    "人力與督導": (
        "社工人力", "人力不足", "專業人力", "照服人力", "照顧人力",
        "專業督導", "督導制度", "督導機制", "督導不足", "督導品質", "督導支持",
        "案量", "工作負荷", "招募", "留任", "離職", "執業環境",
        "職場安全", "supervision system", "supervision support",
        "social work workforce", "care workforce",
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
        "成效評估", "評估結果", "統計結果", "調查結果", "研究報告",
        "調查報告", "監測結果", "實證研究", "資料分析", "成效指標",
        "evaluation results", "survey results", "study finds", "report finds",
        "evidence review",
    ),
    "倫理與權利保障": (
        "倫理", "權益", "人權", "最佳利益", "自決", "保密", "知情同意",
        "合理調整", "反歧視", "兒童權利", "rights", "ethics",
        "reasonable accommodation",
    ),
}

SUBJECT_TERM_RULES = {
    "社會工作": (
        "社工", "社會工作", "專業倫理", "專業責任", "社工專業", "社會工作專業",
        "倡導", "增權", "充權", "優勢觀點", "社會正義", "社區", "文化能力",
        "人權", "社會支持", "social work", "advocacy", "empowerment",
    ),
    "社會工作直接服務": (
        "評估", "處遇", "介入", "通報", "安置", "個案管理", "危機介入",
        "家庭工作", "團體工作", "訪視", "訪查", "轉介", "輔導", "保護服務",
        "case management", "intervention", "assessment", "referral",
    ),
    "人類行為與社會環境": (
        "兒童發展", "青少年發展", "生命歷程", "發展階段", "高齡", "老化",
        "失智", "心理健康", "精神衛生", "創傷", "依附", "家庭系統",
        "人類行為", "社會環境", "成癮", "trauma", "attachment",
        "mental health", "dementia", "life course",
    ),
    "社會工作研究方法": (
        "調查結果", "統計結果", "研究報告", "調查報告", "研究方法",
        "抽樣設計", "抽樣", "問卷調查", "訪談研究", "資料分析",
        "成效評估", "評估研究", "信度", "效度", "survey results",
        "study finds", "evaluation study", "research methods", "data analysis",
    ),
    "社會政策與社會立法": (
        "政策", "制度", "修法", "修正", "法律", "法規", "條例", "施行細則",
        "補助", "津貼", "給付", "保險", "最低工資", "資格", "主管機關",
        "責任通報", "保護令", "權益保障",
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

    welfare_system_only = (
        category == "社工專業與社福制度"
        and _hits(body, WELFARE_SYSTEM_TERMS)
        and not _hits(body, SOCIAL_WORK_PROFESSION_TERMS)
    )

    management_defaults = (
        WELFARE_SYSTEM_MANAGEMENT_DEFAULTS
        if welfare_system_only
        else CATEGORY_MANAGEMENT_DEFAULTS.get(category, ())
    )
    management = list(management_defaults)
    for domain in MANAGEMENT_DOMAINS:
        if _hits(body, MANAGEMENT_TERM_RULES.get(domain, ())):
            management.append(domain)
    management = _ordered_unique(management, MANAGEMENT_DOMAINS)[:5]

    subject_defaults = (
        WELFARE_SYSTEM_SUBJECT_DEFAULTS
        if welfare_system_only
        else CATEGORY_SUBJECT_DEFAULTS.get(category, ("社會工作",))
    )
    subjects = list(subject_defaults)
    explicit_subjects = []
    for subject in EXAM_SUBJECTS:
        if _hits(body, SUBJECT_TERM_RULES.get(subject, ())):
            subjects.append(subject)
            explicit_subjects.append(subject)
    subjects = _ordered_unique(subjects, EXAM_SUBJECTS)

    category_primary = list(
        WELFARE_SYSTEM_PRIMARY_SUBJECTS
        if welfare_system_only
        else CATEGORY_PRIMARY_SUBJECTS.get(category, ())
    )
    primary_subjects = []
    if category_primary:
        # The first subject is the category's default lens. Additional subjects
        # become primary only when this specific event contains real evidence
        # for that subject, preventing broad category defaults from making every
        # story look equally relevant to three or four exam subjects.
        primary_subjects.append(category_primary[0])
        primary_subjects.extend(
            subject for subject in category_primary[1:]
            if subject in explicit_subjects
        )
    # Research methods is primary only when the event itself contains explicit
    # research/evaluation evidence.
    if "社會工作研究方法" in explicit_subjects:
        primary_subjects.append("社會工作研究方法")
    primary_subjects = _ordered_unique(primary_subjects, EXAM_SUBJECTS)[:3]
    if not primary_subjects and subjects:
        primary_subjects = subjects[:1]
    supporting_subjects = [subject for subject in subjects if subject not in primary_subjects]

    subject_topics: dict[str, list[str]] = {}
    defaults = (
        WELFARE_SYSTEM_SUBJECT_TOPICS
        if welfare_system_only
        else CATEGORY_SUBJECT_TOPICS.get(category, {})
    )
    for subject in subjects:
        topics_for_subject = list(defaults.get(subject, ()))
        if subject == "社會工作研究方法":
            for topic, terms in RESEARCH_TOPIC_RULES.items():
                if _hits(body, terms):
                    topics_for_subject.append(topic)
            if not topics_for_subject:
                topics_for_subject.append("研究證據判讀")
        if topics_for_subject:
            subject_topics[subject] = _ordered_unique(topics_for_subject)[:4]

    topics = _ordered_unique([category, *tags])[:10]
    paths = [f"{KNOWLEDGE_ROOT} > {domain}" for domain in management]

    # True hierarchy: management domain -> relevant exam subject -> concrete topic.
    # The five subjects remain the official exam axes; management organizes how
    # an event is understood across them rather than becoming a sixth subject.
    for domain in management:
        linked_subjects = [
            subject for subject in MANAGEMENT_SUBJECT_LINKS.get(domain, ())
            if subject in subjects
        ]
        for subject in linked_subjects:
            topics_for_subject = subject_topics.get(subject, [])
            if topics_for_subject:
                for topic in topics_for_subject:
                    paths.append(f"{KNOWLEDGE_ROOT} > {domain} > {subject} > {topic}")
            else:
                paths.append(f"{KNOWLEDGE_ROOT} > {domain} > {subject}")

    return {
        "knowledge_root": KNOWLEDGE_ROOT,
        "knowledge_model": KNOWLEDGE_MODEL,
        "management_domains": management,
        "exam_subject_axes": subjects,
        "primary_exam_subject_axes": primary_subjects,
        "supporting_exam_subject_axes": supporting_subjects,
        "subject_topics": subject_topics,
        "knowledge_topics": topics,
        "knowledge_paths": _ordered_unique(paths)[:30],
    }

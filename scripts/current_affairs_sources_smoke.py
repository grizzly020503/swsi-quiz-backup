#!/usr/bin/env python3
"""Regression contract for curated SWSI current-affairs sources and relevance."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import current_affairs_watch as watch

score_item = watch.score_item

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "current_affairs_sources.json"

REQUIRED = {
    "教育部即時新聞": "https://www.edu.tw/Rss_News.aspx?n=9E7AC85F1954DDA8",
    "教育部重要政策": "https://www.edu.tw/Rss_WebArchive.aspx?n=FB01D469347C76A7",
    "移民署新住民政策法規": "https://news.immigration.gov.tw/Rss/Content/8?lang=TW",
    "勞動部新聞稿": "https://www.mol.gov.tw/1607/1632/1633/RssList",
    "法務部新聞發布": "https://www.moj.gov.tw/2204/2795/2796/rss",
}

REQUIRED_MEDIA = {
    "TVBS新聞社會": "https://news.tvbs.com.tw/realtime/local",
    "中天新聞社會": "https://ctinews.com/rss/google-society.xml",
    "中天新聞生活": "https://ctinews.com/rss/google-life.xml",
    "自由時報社會": "https://news.ltn.com.tw/rss/society.xml",
    "自由時報生活": "https://news.ltn.com.tw/rss/life.xml",
    "聯合新聞網社會": "https://udn.com/rssfeed/news/2/6639?ch=news",
}


def scored(title: str, summary: str, source: str):
    return score_item(title, summary, "taiwan", source, "official")


def retry_contract() -> None:
    calls = {"count": 0}
    original_parse = watch.feedparser.parse
    original_sleep = watch.time.sleep

    def fake_parse(url, request_headers=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return SimpleNamespace(
                entries=[],
                bozo=True,
                bozo_exception=OSError("temporary network failure"),
            )
        return SimpleNamespace(entries=[{"title": "ok"}], bozo=False)

    try:
        watch.feedparser.parse = fake_parse
        watch.time.sleep = lambda _seconds: None
        parsed, error = watch.parse_feed_with_retry(
            {"name": "fixture", "url": "https://example.test/rss"},
            attempts=3,
        )
        assert error is None, error
        assert len(parsed.entries) == 1
        assert calls["count"] == 2, calls
    finally:
        watch.feedparser.parse = original_parse
        watch.time.sleep = original_sleep


def who_api_adapter_contract() -> None:
    calls = {"count": 0}
    original_urlopen = watch.urlopen
    original_sleep = watch.time.sleep

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    payload = {
        "value": [{
            "Title": "WHO issues new guidance on mental health and suicide prevention services",
            "ItemDefaultUrl": "/24-09-2026-who-mental-health-guidance",
            "PublicationDateAndTime": "2026-09-24T10:00:00Z",
            "OpenGraphDescription": "WHO guidance strengthens mental health services and suicide prevention policy.",
        }]
    }

    def fake_urlopen(request, timeout=12):
        calls["count"] += 1
        assert "%24orderby=PublicationDate%20desc" in request.full_url
        if calls["count"] == 1:
            raise OSError("temporary WHO API failure")
        return FakeResponse(payload)

    try:
        watch.urlopen = fake_urlopen
        watch.time.sleep = lambda _seconds: None
        parsed, error = watch.parse_who_newsroom_with_retry(
            {
                "name": "WHO Newsroom",
                "url": "https://www.who.int/api/newsroom/newsitems",
                "source_format": "who_newsroom_json",
            },
            attempts=3,
        )
        assert error is None, error
        assert calls["count"] == 2, calls
        assert len(parsed.entries) == 1
        entry = parsed.entries[0]
        assert entry.title.startswith("WHO issues new guidance")
        assert entry.link == "https://www.who.int/news/item/24-09-2026-who-mental-health-guidance"
        assert entry.published_parsed is not None
    finally:
        watch.urlopen = original_urlopen
        watch.time.sleep = original_sleep


def unicef_html_adapter_contract() -> None:
    calls = {"count": 0}
    original_urlopen = watch.urlopen
    original_sleep = watch.time.sleep

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"""
            <html><body>
              <div>25 September 2026</div>
              <a href="/press-releases/child-protection-policy">
                UNICEF calls for stronger child protection and child rights safeguards
              </a>
              <a href="/press-releases/child-protection-policy">
                UNICEF calls for stronger child protection and child rights safeguards
              </a>
              <div>23 September 2026</div>
              <a href="/press-releases/mental-health-support">
                Children affected by floods need urgent mental health and psychosocial support
              </a>
              <a href="/donate">Donate</a>
            </body></html>
            """

    def fake_urlopen(request, timeout=12):
        calls["count"] += 1
        assert request.full_url == "https://www.unicef.org/media/press-releases"
        if calls["count"] == 1:
            raise OSError("temporary UNICEF page failure")
        return FakeResponse()

    try:
        watch.urlopen = fake_urlopen
        watch.time.sleep = lambda _seconds: None
        parsed, error = watch.parse_unicef_press_with_retry(
            {
                "name": "UNICEF Press Releases",
                "url": "https://www.unicef.org/media/press-releases",
                "source_format": "unicef_press_html",
            },
            attempts=3,
        )
        assert error is None, error
        assert calls["count"] == 2, calls
        assert len(parsed.entries) == 2, parsed.entries
        first = parsed.entries[0]
        assert first.link == "https://www.unicef.org/press-releases/child-protection-policy"
        assert first.title.startswith("UNICEF calls for stronger child protection")
        assert first.published_parsed is not None
        assert parsed.entries[1].published_parsed is not None
    finally:
        watch.urlopen = original_urlopen
        watch.time.sleep = original_sleep


def ilo_html_adapter_contract() -> None:
    calls = {"count": 0}
    original_urlopen = watch.urlopen
    original_sleep = watch.time.sleep

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"""
            <html><body>
              <article>
                <a href="/resource/news/social-protection-expansion">
                  ILO project improves social protection coverage for over nine million people
                </a>
                <p>Policy reforms strengthen social protection systems and universal coverage.</p>
                <time datetime="2026-09-25">25 September 2026</time>
              </article>
              <article>
                <a href="/resource/news/refugee-decent-work">
                  ILO and UNHCR strengthen decent work for refugees and host communities
                </a>
                <p>Partnership expands employment protection and services for refugees.</p>
                <div>24 September 2026</div>
              </article>
              <a href="https://www.etf.europa.eu/external-story">External story</a>
              <a href="/resource/news/all-news-recent">All news</a>
            </body></html>
            """

    def fake_urlopen(request, timeout=12):
        calls["count"] += 1
        assert request.full_url == "https://www.ilo.org/resource/news/all-news-recent"
        if calls["count"] == 1:
            raise OSError("temporary ILO page failure")
        return FakeResponse()

    try:
        watch.urlopen = fake_urlopen
        watch.time.sleep = lambda _seconds: None
        parsed, error = watch.parse_ilo_news_with_retry(
            {
                "name": "ILO Newsroom",
                "url": "https://www.ilo.org/resource/news/all-news-recent",
                "source_format": "ilo_news_html",
            },
            attempts=3,
        )
        assert error is None, error
        assert calls["count"] == 2, calls
        assert len(parsed.entries) == 2, parsed.entries
        first = parsed.entries[0]
        assert first.link == "https://www.ilo.org/resource/news/social-protection-expansion"
        assert first.title.startswith("ILO project improves social protection")
        assert "universal coverage" in first.summary
        assert first.published_parsed is not None
        assert parsed.entries[1].published_parsed is not None
    finally:
        watch.urlopen = original_urlopen
        watch.time.sleep = original_sleep


def tvbs_html_adapter_contract() -> None:
    now = watch.datetime(2026, 9, 24, 10, 0, tzinfo=watch.timezone.utc)
    entries = watch.parse_tvbs_realtime_html(
        """
        <html><body>
          <a href="/local/4027033">
            <h2>北市社工涉侵占長者千萬遭羈押</h2>
            <p>社工師公會與衛福部回應，案件涉及專業倫理與長者保護。</p>
            <span>18 分鐘前</span>
          </a>
          <a href="/local/4027033">
            <h2>北市社工涉侵占長者千萬遭羈押</h2>
          </a>
        </body></html>
        """,
        now=now,
    )
    assert len(entries) == 1, entries
    entry = entries[0]
    assert entry.link == "https://news.tvbs.com.tw/local/4027033"
    assert entry.title == "北市社工涉侵占長者千萬遭羈押"
    assert "專業倫理" in entry.summary
    assert entry.published_parsed is not None


def main() -> int:
    retry_contract()
    who_api_adapter_contract()
    unicef_html_adapter_contract()
    ilo_html_adapter_contract()
    tvbs_html_adapter_contract()
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = payload.get("sources") or []
    assert payload.get("schema_version") == 1
    assert len(rows) >= 23, f"expected at least 23 curated sources, got {len(rows)}"

    urls = [str(x.get("url") or "") for x in rows]
    names = [str(x.get("name") or "") for x in rows]
    assert len(urls) == len(set(urls)), "duplicate feed URL"
    assert len(names) == len(set(names)), "duplicate feed name"
    assert all(url.startswith("https://") for url in urls), "all feeds must use HTTPS"

    by_name = {str(x.get("name")): x for x in rows}
    un_news = by_name.get("UN News English")
    assert un_news, "missing source: UN News English"
    assert un_news.get("url") == "https://news.un.org/feed/subscribe/en/news/all/rss.xml"
    assert un_news.get("region") == "international"
    assert un_news.get("source_type") == "official"

    who_news = by_name.get("WHO Newsroom")
    assert who_news, "missing source: WHO Newsroom"
    assert who_news.get("url") == "https://www.who.int/api/newsroom/newsitems"
    assert who_news.get("region") == "international"
    assert who_news.get("source_type") == "official"
    assert who_news.get("source_format") == "who_newsroom_json"

    unicef_news = by_name.get("UNICEF Press Releases")
    assert unicef_news, "missing source: UNICEF Press Releases"
    assert unicef_news.get("url") == "https://www.unicef.org/media/press-releases"
    assert unicef_news.get("region") == "international"
    assert unicef_news.get("source_type") == "official"
    assert unicef_news.get("source_format") == "unicef_press_html"

    ilo_news = by_name.get("ILO Newsroom")
    assert ilo_news, "missing source: ILO Newsroom"
    assert ilo_news.get("url") == "https://www.ilo.org/resource/news/all-news-recent"
    assert ilo_news.get("region") == "international"
    assert ilo_news.get("source_type") == "official"
    assert ilo_news.get("source_format") == "ilo_news_html"

    for name, url in REQUIRED.items():
        row = by_name.get(name)
        assert row, f"missing source: {name}"
        assert row.get("url") == url, (name, row.get("url"))
        assert row.get("region") == "taiwan", name
        assert row.get("source_type") == "official", name

    for name, url in REQUIRED_MEDIA.items():
        row = by_name.get(name)
        assert row, f"missing media source: {name}"
        assert row.get("url") == url, (name, row.get("url"))
        assert row.get("region") == "taiwan", name
        assert row.get("source_type") == "news", name
        assert row.get("optional") is True, name
    assert by_name["TVBS新聞社會"].get("source_format") == "tvbs_realtime_html"

    media_child_abuse = score_item(
        "兒童遭保母虐死 社工訪視與通報流程受檢視",
        "兒少保護事件引發責任通報、訪視與跨網絡制度檢討。",
        "taiwan",
        "TVBS新聞社會",
        "news",
    )
    assert media_child_abuse and media_child_abuse[1] == "兒少保護", media_child_abuse
    assert media_child_abuse[0] >= 5, media_child_abuse

    media_social_worker_misconduct = score_item(
        "北市社工涉侵占長者千萬遭羈押",
        "社工師公會與衛福部回應，案件涉及專業倫理與長者保護。",
        "taiwan",
        "TVBS新聞社會",
        "news",
    )
    assert media_social_worker_misconduct, media_social_worker_misconduct
    assert media_social_worker_misconduct[1] == "社工專業與社福制度", media_social_worker_misconduct
    assert media_social_worker_misconduct[0] >= 5, media_social_worker_misconduct

    job_title_only_social_worker_crime = score_item(
        "北市女社工盜領個案千萬老本遭羈押 15名牌包、精品曝光",
        "前社工涉嫌盜領受監護老人存款，警方查扣精品並依刑案偵辦。",
        "taiwan",
        "中天新聞社會",
        "news",
    )
    assert job_title_only_social_worker_crime is None, job_title_only_social_worker_crime

    generic_elder_crash = score_item(
        "83歲翁騎車遭撞身亡",
        "警方依交通事故程序調查，未涉及社福制度或照顧服務。",
        "taiwan",
        "TVBS新聞社會",
        "news",
    )
    assert generic_elder_crash is None, generic_elder_crash

    generic_crime = score_item(
        "男子酒後持刀傷人 警方到場逮捕",
        "一般刑案，未涉及社福制度或社會工作考點。",
        "taiwan",
        "中天新聞社會",
        "news",
    )
    assert generic_crime is None, generic_crime

    labor = scored(
        "勞動部修正就業保險給付規定 強化失業勞工權益",
        "新制調整失業給付、就業服務與社會保障。",
        "勞動部新聞稿",
    )
    assert labor and labor[1] == "勞動與社會保障", labor
    assert labor[0] >= 5, labor

    education = scored(
        "教育部修正學生輔導制度 強化中輟與弱勢學生支持",
        "政策聚焦學生輔導、跨專業合作及弱勢學生權益。",
        "教育部重要政策",
    )
    assert education and education[1] == "教育與學生輔導", education
    assert education[0] >= 5, education

    child_survey = scored(
        "敬請支持115年兒童及少年生活狀況調查",
        "依兒童及少年福利與權益保障法辦理生活狀況調查，作為社會福利政策與法規修訂依據。",
        "衛生福利部公告訊息",
    )
    assert child_survey is None, child_survey

    disability_survey = scored(
        "敬請支持115年身心障礙者生活狀況及需求調查",
        "依身心障礙者權益保障法辦理定期調查，請民眾配合訪查。",
        "衛生福利部公告訊息",
    )
    assert disability_survey is None, disability_survey

    childcare = scored(
        "企業托育補助新制提高支持力道",
        "新制提高托兒設施、育兒補貼與托育人員支持。",
        "勞動部新聞稿",
    )
    assert childcare and childcare[1] == "性別與家庭政策", childcare

    childcare_generic = scored(
        "響應0-6歲國家一起養 中央部會落實員工子女托育",
        "政策同時提到弱勢家庭、社會福利與托育支持。",
        "教育部即時新聞",
    )
    assert childcare_generic is None, childcare_generic

    childcare_activity = scored(
        "親子托育同樂活動週末登場",
        "邀請家庭參加親子遊戲與活動。",
        "教育部即時新聞",
    )
    assert childcare_activity is None, childcare_activity

    professional_misconduct = scored(
        "社工涉侵占服務對象財產 機構啟動內控與專業倫理檢討",
        "案件涉及服務對象財產、專業責任與機構內控，社工師公會要求檢討。",
        "TVBS新聞",
    )
    assert professional_misconduct and professional_misconduct[1] == "社工專業與社福制度", professional_misconduct

    victim_policy = scored(
        "犯罪被害人權益保障法保護服務新制上路 強化家庭支持與修復式司法",
        "法務部推動以家庭為中心的保護服務、被害補償與跨網絡合作。",
        "法務部新聞發布",
    )
    assert victim_policy and victim_policy[1] == "司法保護與修復式司法", victim_policy
    assert victim_policy[0] >= 5, victim_policy

    restorative = scored(
        "精進修復式司法與犯罪被害人保護服務",
        "制度強化修復式司法轉介、被害人權益及社區支持。",
        "法務部新聞發布",
    )
    assert restorative and restorative[1] == "司法保護與修復式司法", restorative

    who_mental = score_item(
        "WHO issues new guidance on mental health and suicide prevention services",
        "World Health Organization recommendations strengthen mental health services and suicide prevention policy.",
        "international",
        "WHO News",
        "international",
    )
    assert who_mental and who_mental[1] == "心理健康與成癮", who_mental
    assert who_mental[0] >= 5, who_mental
    assert "心理健康" in who_mental[2], who_mental

    unicef_child = score_item(
        "UNICEF calls for stronger child protection and child rights safeguards",
        "UNICEF policy guidance focuses on child protection services and the rights of the child.",
        "international",
        "UNICEF",
        "international",
    )
    assert unicef_child and unicef_child[1] == "兒少保護", unicef_child
    assert {"兒少保護", "兒童權利"}.issubset(set(unicef_child[2])), unicef_child

    ilo_social_protection = score_item(
        "ILO project improves social protection coverage for over nine million people",
        "Policy reforms strengthen social protection systems and universal coverage.",
        "international",
        "ILO Newsroom",
        "official",
    )
    assert ilo_social_protection is None, ilo_social_protection

    who_migrant_course = score_item(
        "From competencies to action: strengthening refugee and migrant health",
        "Policy-makers attended a Global Orientation Course on Refugee and Migrant Health.",
        "international",
        "WHO Newsroom",
        "official",
    )
    assert who_migrant_course is None, who_migrant_course

    retirement_reminder = scored(
        "延後退休續勞保：給付保障不中斷，年金累積年資無上限",
        "提醒65歲以上持續工作者可依既有規定續保，並說明展延年金。",
        "勞動部新聞稿",
    )
    assert retirement_reminder is None, retirement_reminder

    minimum_wage_change = scored(
        "最低工資連11漲 審議會決定自116年起調升至30,900元",
        "每月最低工資調升，時薪同步提高，待行政院核定。",
        "勞動部新聞稿",
    )
    assert minimum_wage_change and minimum_wage_change[1] == "勞動與社會保障", minimum_wage_change

    elder_service_expansion = scored(
        "衛福部擴大獨老服務 啟動70萬名長者關懷訪查",
        "因應超高齡社會，擴大獨居老人服務、長者社區安全網、關懷訪查與分級服務連結。",
        "衛生福利部焦點新聞",
    )
    assert elder_service_expansion and elder_service_expansion[1] == "長照與高齡", elder_service_expansion

    generic_world_news = score_item(
        "Global leaders gather for annual forum",
        "Officials discussed the economy and international cooperation.",
        "international",
        "International News",
        "news",
    )
    assert generic_world_news is None, generic_world_news

    noise_cases = [
        (
            "涉侵占1200萬買名牌包！甜美社工羈押禁見「3大理由曝」",
            "前北市社會局社工督導涉嫌盜領受監護宣告老人存款，法院裁定羈押禁見。",
            "TVBS新聞",
        ),
        (
            "教育部舉辦全國學生競賽",
            "歡迎學生踴躍參加競賽活動。",
            "教育部即時新聞",
        ),
        (
            "參觀國際兒童及青少年書展 鼓勵使用文化幣",
            "推動閱讀政策，邀請兒童與青少年參與文化活動。",
            "行政院本院新聞",
        ),
        (
            "外出牢記防熱4招 護兒童遠離熱傷害",
            "衛生單位提供兒童健康宣導與保護資訊。",
            "衛生福利部焦點新聞",
        ),
        (
            "燈塔引航 守護學子 大專校院專業輔導人員頒獎典禮",
            "表揚學生輔導與校園支持服務人員。",
            "教育部即時新聞",
        ),
        (
            "新住民模擬投票扎根民主",
            "新住民參與公民教育活動，推動政策宣導。",
            "移民署新住民政策法規",
        ),
        (
            "內政部伴新住民築夢 49組團隊創意發光",
            "新住民團隊成果發表與活動。",
            "內政部新聞發布",
        ),
        (
            "接見亞洲地區臺灣同鄉會回國訪問團 用新移民觀念創造投資環境",
            "接見訪問團並談新移民與投資政策。",
            "行政院本院新聞",
        ),
        (
            "教育部辦理大專校院優良校園無障礙建築物評選",
            "樹立校園無障礙環境典範。",
            "教育部即時新聞",
        ),
        (
            "前議員涉詐長照補助遭起訴",
            "檢方偵辦詐領長照補助刑案。",
            "中央社社會",
        ),
        (
            "國家防災日地震避難掩護演練",
            "強化校園師生應變疏散能力與防衛韌性。",
            "教育部即時新聞",
        ),
        (
            "企業與林業資源攜手打造特教生適性課桌椅",
            "支持特殊教育學生校園生活。",
            "教育部即時新聞",
        ),
        (
            "鄭部長出席榮譽觀護人聯合會辦公室揭牌儀式",
            "勉勵榮觀與更生保護單位攜手。",
            "法務部新聞發布",
        ),
        (
            "矯正聯展首度跨國交流 作業成品齊聚臺中",
            "法務部辦理矯正機關聯展活動。",
            "法務部新聞發布",
        ),
        (
            "犯保協會中秋感恩音樂會登場",
            "犯罪被害人保護協會辦理音樂會活動。",
            "法務部新聞發布",
        ),
        (
            "有關媒體報導法務部長下令少關人一文 本部澄清說明",
            "媒體報導與事實不符，法務部予以澄清。",
            "法務部新聞發布",
        ),
    ]
    for title, summary, source in noise_cases:
        result = scored(title, summary, source)
        assert result is None, (title, result)

    print(
        "CURRENT AFFAIRS SOURCE SMOKE OK: "
        f"{len(rows)} unique HTTPS sources; optional media RSS + WHO JSON + UNICEF/ILO HTML adapters guarded; "
        "high-precision exam-event gate enforced; policy changes/guidance accepted; surveys, reminders, courses and generic projects rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

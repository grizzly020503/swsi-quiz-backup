# SWSI Current-Affairs Source Policy

Last reviewed: 2026-09-26

## Purpose

This document records which external sources may be used by the SWSI current-affairs / exam-trend pipeline and why.

The current-affairs system is not a general news aggregator. Its purpose is:

> source → event dedupe → social-work / policy exam concept → historical questions → trend signal

Source count is not a KPI. A source should be added only when it improves exam-relevant evidence without weakening legal, reliability, privacy, copyright, or quality boundaries.

## Production baseline

The production baseline is currently **17 sources**:

1. 衛生福利部焦點新聞
2. 衛生福利部公告訊息
3. 中央社社會
4. 中央社生活
5. 中央社政治
6. 中央社國際
7. 內政部新聞發布
8. 行政院本院新聞
9. 教育部即時新聞
10. 教育部重要政策
11. 移民署新住民政策法規
12. 勞動部新聞稿
13. 法務部新聞發布
14. UN News English
15. WHO Newsroom
16. UNICEF Press Releases
17. ILO Newsroom

The exact machine-readable registry remains:

- `data/current_affairs_sources.json`

Production health remains fail-closed through Public Monitoring and Public Uptime.

## Eligibility rules

A new current-affairs source should satisfy all of the following before production:

1. **Authority / value**
   - official public-sector or international-organization source; or
   - a news source with a clear lawful programmatic-use path;
   - and it materially improves social-work national-exam relevance.

2. **Stable acquisition**
   - official RSS, API, open-data endpoint, or a narrowly scoped official page adapter;
   - no guessed endpoint;
   - no third-party mirror as a substitute for unavailable official access;
   - bounded retry and final feed-health reporting.

3. **Rights**
   - SWSI may lawfully use the required metadata/content for this transformed analysis;
   - do not bypass licences, paywalls, technical controls, robots restrictions, or contract entitlements;
   - do not copy article bodies merely because a page is publicly viewable.

4. **Minimal data use**
   - retain only the metadata needed for provenance and analysis, such as title, timestamp, source, canonical URL, and SWSI-authored categorization/analysis;
   - do not republish full copyrighted articles.

5. **Quality**
   - relevance regression before merge;
   - event dedupe before trend scoring;
   - source volume must not independently raise trend score;
   - false positives are fixed regression-first.

6. **International sources**
   - must pass the bilingual taxonomy / cross-language event-dedupe path;
   - must still map against the verified 4,800-question corpus;
   - no separate lower-standard pipeline for English sources.

## Source decisions

### Reuters — not integrated without licence

Decision: **Do not ingest Reuters content into the production current-affairs pipeline unless SWSI obtains an applicable Reuters licence / subscription.**

Reason:

- Reuters Agency presents RSS and API/content-delivery methods as ways to receive subscribed Reuters content.
- Reuters Connect and related delivery products use commercial subscription / licensing models.
- A publicly reachable Reuters page is not treated as permission for automated extraction into SWSI.

Official references:

- https://reutersagency.com/content-delivery-platforms/content-delivery
- https://reutersagency.com/content-delivery-platforms/reuters-connect/

Re-evaluate only if an explicit licence or official open-use program covers SWSI's intended metadata transformation.

### Associated Press (AP) — not integrated without contract / entitlement

Decision: **Do not crawl AP.org or ingest AP content without an applicable AP agreement / API entitlement.**

Reason:

- AP terms reserve Site Elements and prohibit automated crawling/scraping/repeated access except where authorized.
- AP Media API is for licensed multimedia content and depends on contract entitlements/API access.

Official references:

- https://www.ap.org/terms-and-conditions/
- https://api.ap.org/media/v/docs/Getting_Started_API.htm

Re-evaluate only if AP provides SWSI with an applicable licence/API entitlement.

### BBC — do not transform RSS/metadata without permission

Decision: **Do not add BBC RSS/metadata to SWSI's transformed event/trend database without applicable BBC permission/licence.**

Reason:

- BBC terms distinguish merely embedding an intact BBC News RSS feed from extracting (“plucking”) metadata.
- Business use of BBC metadata/RSS requires permission/licensing and may involve fees.
- SWSI does not merely display an intact feed; it extracts metadata, classifies it, clusters events, links historical questions, and produces derived trend data.

Official reference:

- https://downloads.bbc.co.uk/usingthebbc/bbc_terms_of_use_31March2022english.pdf
  - section: “Metadata and RSS feeds”

Re-evaluate if BBC publishes terms or an API/licence that explicitly covers this use.

### 衛生福利部社會及家庭署 — background-data candidate, not a current-affairs feed

Decision: **Do not add a guessed 社家署 RSS/news endpoint. No stable, verified current-affairs RSS/XML/API endpoint has been approved.**

However, official 社家署 datasets on the Taiwan Government Data Open Platform may be useful in a **separate background-evidence layer**, for example:

- 兒童及少年家外安置概況
- 兒童及少年安置及教養機構一覽表
- other published welfare statistics / institution lists

These datasets are marked with **政府資料開放授權條款－第1版** on data.gov.tw. They are periodic/statistical evidence, not a substitute for a live current-affairs feed.

Official references:

- https://data.gov.tw/dataset/161605
- https://data.gov.tw/dataset/161606
- https://data.gov.tw/license

If a stable official 社家署 policy-news endpoint is later found, treat it as a new source proposal and run the full source/adaptor/relevance regressions before production.

## What not to do

- Do not add Reuters/AP/BBC by scraping public webpages or using unofficial RSS mirrors.
- Do not call a source “integrated” merely because a URL responds.
- Do not use a static statistics dataset as if it were a current-affairs/news feed.
- Do not weaken relevance thresholds to justify source expansion.
- Do not duplicate an event across sources to inflate trend score.
- Do not bypass the existing source adapter, taxonomy, event clustering, historical-question matching, monitoring, and uptime contracts.

## Re-evaluation

A deferred source can be reconsidered when one of these becomes available:

- explicit licence/permission compatible with SWSI;
- official open-data/API terms compatible with transformed metadata analysis;
- a stable first-party endpoint with clear programmatic-use rights.

A re-evaluation should be a new, evidence-backed change. It is not an open release blocker for the current 17-source system.

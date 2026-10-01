#!/usr/bin/env python3
from __future__ import annotations

import historical_law_stage6_semantic as s6

# Stage 4 old-version HTML fallback must expose all historical articles.
html = """
<html><head><title>全國法規資料庫</title></head><body>
<div class="row"><div class="col-no">第 1 條</div><div class="col-data"><div class="law-article">
<div class="line-0000">本法規定甲乙丙丁。</div></div></div></div>
<div class="row"><div class="col-no">第 8 條</div><div class="col-data"><div class="law-article">
<div class="line-0000">緊急生活扶助每人每次補助三個月。</div></div></div></div>
</body></html>
"""
articles = s6.all_articles_from_page(html)
assert {row["article_no"] for row in articles} == {"1", "8"}, articles

# Strong historical top-1 agreement confirms the proposed article.
ranked = [
    {"article_no": "8", "score": 0.71, "shared_ngram_count": 21, "evidence": ["生活扶助"]},
    {"article_no": "1", "score": 0.31, "shared_ngram_count": 8, "evidence": ["規定"]},
]
status, evidence = s6.semantic_decision("8", ranked)
assert status == "historical_semantic_confirmed", (status, evidence)
assert evidence["expected_rank"] == 1

# Top-1 but weak separation is support only, not auto confirmation.
ranked = [
    {"article_no": "8", "score": 0.22, "shared_ngram_count": 6, "evidence": []},
    {"article_no": "1", "score": 0.20, "shared_ngram_count": 6, "evidence": []},
]
status, evidence = s6.semantic_decision("8", ranked)
assert status == "historical_semantic_support", (status, evidence)

# A different historical top article is a conflict even if semantically strong.
ranked = [
    {"article_no": "9", "score": 0.80, "shared_ngram_count": 24, "evidence": []},
    {"article_no": "8", "score": 0.30, "shared_ngram_count": 9, "evidence": []},
]
status, evidence = s6.semantic_decision("8", ranked)
assert status == "historical_semantic_conflict", (status, evidence)
assert evidence["expected_rank"] == 2

# No candidate is fail-closed conflict, never an implicit confirmation.
status, evidence = s6.semantic_decision("8", [])
assert status == "historical_semantic_conflict", (status, evidence)
assert evidence["expected_rank"] is None

print("HISTORICAL LAW STAGE6 SELFTEST OK")

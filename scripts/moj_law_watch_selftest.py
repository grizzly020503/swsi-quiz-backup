#!/usr/bin/env python3
"""Offline regression tests for article-level MOJ legal watch scoping."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "moj_law_watch.py"

spec = importlib.util.spec_from_file_location("moj_law_watch", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


html_v1 = """
<html><body>
<div id="pnLawFla">
<div>測試法</div>
<div>第 188 條</div><div>受僱人因執行職務，不法侵害他人之權利者，由僱用人負連帶責任。</div>
<div>第 189 條</div><div>承攬人因執行承攬事項，不法侵害他人權利者。</div>
<div>第 1055-1 條</div><div>法院為子女之最佳利益，依規定審酌一切情狀。</div>
</div>
<footer>頁尾版本 A</footer>
</body></html>
"""

html_v2 = """
<html><body>
<div id="pnLawFla">
<div>測試法</div>
<div>第 188 條</div><div>受僱人因執行職務，不法侵害他人之權利者，由僱用人負連帶責任。</div>
<div>第 189 條</div><div>承攬人因執行承攬事項，不法侵害他人權利者；本句已修正。</div>
<div>第 1055-1 條</div><div>法院為子女之最佳利益，依規定審酌一切情狀。</div>
</div>
<footer>頁尾版本 B</footer>
</body></html>
"""

first = module.extract_article_fingerprints(html_v1)
second = module.extract_article_fingerprints(html_v2)

require(set(first) == {"188", "189", "1055-1"}, f"unexpected article keys: {sorted(first)}")
require(module.diff_article_fingerprints({}, first) is None, "empty prior state must initialize baseline")
require(module.diff_article_fingerprints(first, second) == ["189"], "only changed article should be reported")
require(module.normalize_article_no("1055 - 1") == "1055-1", "sub-article normalization failed")
require(first["1055-1"] == second["1055-1"], "dynamic footer must not contaminate final article fingerprint")

# Fail closed if MOJ removes/renames the official law-body container.
require(
    module.extract_article_fingerprints("<html><body><div>第 1 條</div><footer>noise</footer></body></html>") == {},
    "missing #pnLawFla must disable article fingerprints",
)

# A repeated navigation heading must not replace a longer article body block.
duplicate_heading = """
<div id="pnLawFla">
<div>第 188 條</div>
<div>第 188 條</div><div>完整條文內容應該勝過只有標題的短區塊。</div>
</div>
"""
dupe = module.extract_article_fingerprints(duplicate_heading)
require("188" in dupe and len(dupe["188"]) == 64, "duplicate heading handling failed")

print("MOJ ARTICLE FINGERPRINT SELFTEST PASS")

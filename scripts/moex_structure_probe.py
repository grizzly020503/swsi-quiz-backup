#!/usr/bin/env python3
"""Read-only MOEX exam-page structure probe for SWSI.

This runs *before* PDF parsing in the future guarded intake path.  It answers a
narrow question: does the official exam page still expose the approved Social
Worker subject structure?

It never approves a new examination scheme.  Any observed subject/code drift is
reported as ``possible_scheme_change`` and must remain quarantined until the
versioned exam-scheme registry is reviewed against official evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from exam_scheme import load_registry, normalize_round, resolve_profile

BASE = "https://wwwq.moex.gov.tw/exam"
TARGET_CLASS_NAME = "社會工作師"
UA = "Mozilla/5.0 (compatible; swsi-moex-structure-probe/1.0; +https://github.com/grizzly020503/swsi-quiz-backup)"


class ProbeError(RuntimeError):
    pass


def exam_url(exam_code: str) -> str:
    if not re.fullmatch(r"\d{6}", exam_code):
        raise ProbeError(f"invalid exam code: {exam_code!r}")
    year = int(exam_code[:3]) + 1911
    return f"{BASE}/wFrmExamQandASearch.aspx?e={exam_code}&y={year}"


def session_from_exam_code(exam_code: str) -> tuple[str, str]:
    if not re.fullmatch(r"\d{6}", exam_code):
        raise ProbeError(f"invalid exam code: {exam_code!r}")
    suffix = exam_code[3:]
    round_name = "第一次" if suffix == "030" else "第二次" if suffix == "100" else ""
    if not round_name:
        raise ProbeError(f"unsupported social-worker exam suffix: {exam_code}")
    return exam_code[:3], round_name


def _clean_text(value: Any) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class TableRow:
    texts: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)

    def combined(self) -> str:
        return _clean_text(" ".join(self.inputs + self.texts))


class ExamPageParser(HTMLParser):
    """Collect row-level visible text, input values and links.

    MOEX currently renders each class/subject entry in table rows. Keeping the
    parser row-oriented makes unrelated professions before/after 社會工作師 unable
    to leak into the observed subject set.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[TableRow] = []
        self.current: TableRow | None = None
        self.href: str | None = None
        self.href_text: list[str] = []
        self.fallback = TableRow()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {str(k).lower(): (v or "") for k, v in attrs}
        if tag.lower() == "tr":
            if self.current is not None:
                self.rows.append(self.current)
            self.current = TableRow()
        row = self.current or self.fallback
        if tag.lower() == "input":
            value = _clean_text(attrs_map.get("value"))
            if value:
                row.inputs.append(value)
        if tag.lower() == "a":
            self.href = attrs_map.get("href") or ""
            self.href_text = []

    def handle_data(self, data: str) -> None:
        text = _clean_text(data)
        if not text:
            return
        row = self.current or self.fallback
        row.texts.append(text)
        if self.href is not None:
            self.href_text.append(text)

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower == "a" and self.href is not None:
            row = self.current or self.fallback
            row.links.append((self.href, _clean_text(" ".join(self.href_text))))
            self.href = None
            self.href_text = []
        if lower == "tr" and self.current is not None:
            self.rows.append(self.current)
            self.current = None

    def close(self) -> None:
        super().close()
        if self.current is not None:
            self.rows.append(self.current)
            self.current = None
        if self.fallback.texts or self.fallback.inputs or self.fallback.links:
            # Fallback preserves compatibility if MOEX changes markup but keeps
            # all content outside <tr>. Such a case will normally become
            # ambiguous/possible_scheme_change rather than silently accepted.
            self.rows.append(self.fallback)


def _subject_code_from_href(href: str) -> str | None:
    try:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        if str((qs.get("q") or [""])[0]) != "1":
            return None
        code = str((qs.get("s") or [""])[0]).strip()
        return code if code else None
    except Exception:
        return None


def _looks_like_class_header(row: TableRow) -> bool:
    combined = row.combined()
    if any(_subject_code_from_href(href) for href, _ in row.links):
        return False
    # Current MOEX values look like 高考_社會工作師 / 專技高考_營養師.
    return bool("_" in combined and any(token in combined for token in ("高考", "普考", "考試")))


def _subject_name(row: TableRow) -> str:
    # Input values are useful for locating class headers, but subject rows also
    # contain checkbox/input values that are not part of the visible subject
    # name. Derive the subject only from visible text.
    pieces = []
    for value in row.texts:
        value = _clean_text(value)
        if not value or value in {"試題", "答案"}:
            continue
        if "高考_" in value or "普考_" in value:
            continue
        pieces.append(value)
    text = _clean_text(" ".join(pieces))
    # Anchor labels may be duplicated by accessible/mobile markup.
    text = re.sub(r"(?:試題|答案)(?:\s*(?:試題|答案))*$", "", text).strip()
    return text


def extract_social_worker_subjects(html: str) -> dict[str, Any]:
    parser = ExamPageParser()
    parser.feed(html)
    parser.close()

    in_target = False
    target_found = False
    observed: dict[tuple[str, str], dict[str, Any]] = {}
    ambiguous_rows: list[str] = []

    for row in parser.rows:
        combined = row.combined()
        is_header = _looks_like_class_header(row)
        if TARGET_CLASS_NAME in combined and is_header:
            in_target = True
            target_found = True
            continue
        if in_target and is_header:
            break
        if not in_target:
            continue

        codes = []
        for href, label in row.links:
            code = _subject_code_from_href(href)
            if code:
                codes.append((code, href, label))
        if not codes:
            continue
        unique_codes = sorted({code for code, _href, _label in codes})
        name = _subject_name(row)
        if not name or len(unique_codes) != 1:
            ambiguous_rows.append(combined[:240])
            continue
        code = unique_codes[0]
        key = (code, name)
        if key not in observed:
            observed[key] = {
                "code": code,
                "name": name,
                "links": sorted({href for c, href, _label in codes if c == code}),
            }
        else:
            observed[key]["links"] = sorted(set(observed[key]["links"]) | {href for c, href, _label in codes if c == code})

    return {
        "target_class_found": target_found,
        "subjects": sorted(observed.values(), key=lambda row: (row["code"], row["name"])),
        "ambiguous_rows": ambiguous_rows,
    }


def compare_to_registry(exam_code: str, html: str, *, source_url: str | None = None) -> dict[str, Any]:
    registry = load_registry()
    roc_year, round_name = session_from_exam_code(exam_code)
    normalized_round = normalize_round(round_name, registry)
    profile = resolve_profile(registry, roc_year, normalized_round)
    extracted = extract_social_worker_subjects(html)
    source_url = source_url or exam_url(exam_code)

    base = {
        "schema_version": 1,
        "probe": "moex_exam_page_structure_v1",
        "exam_code": exam_code,
        "roc_year": roc_year,
        "round": normalized_round,
        "source_url": source_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "target_class_found": extracted["target_class_found"],
        "ambiguous_rows": extracted["ambiguous_rows"],
        "observed_subjects": extracted["subjects"],
        "requires_maintainer_decision": True,
        "safe_to_parse_pdfs": False,
    }

    if profile is None:
        return {**base, "status": "unapproved_scheme", "profile_id": None, "expected_subjects": [], "diffs": [{"field": "profile", "expected": "approved profile", "observed": None}]}

    expected = [
        {"code": str(row["code"]), "name": str(row["name"])}
        for row in profile.get("subjects") or []
    ]
    observed = [{"code": row["code"], "name": row["name"]} for row in extracted["subjects"]]
    diffs: list[dict[str, Any]] = []

    if not extracted["target_class_found"]:
        status = "target_class_missing"
        diffs.append({"field": "target_class", "expected": TARGET_CLASS_NAME, "observed": None})
    else:
        expected_set = {(row["code"], row["name"]) for row in expected}
        observed_set = {(row["code"], row["name"]) for row in observed}
        if expected_set != observed_set:
            diffs.append({
                "field": "subjects",
                "expected": sorted(expected_set),
                "observed": sorted(observed_set),
                "missing": sorted(expected_set - observed_set),
                "unexpected": sorted(observed_set - expected_set),
            })
        if extracted["ambiguous_rows"]:
            diffs.append({"field": "ambiguous_rows", "expected": [], "observed": extracted["ambiguous_rows"]})
        status = "match" if not diffs else "possible_scheme_change"

    return {
        **base,
        "status": status,
        "profile_id": profile["id"],
        "expected_subjects": expected,
        "diffs": diffs,
        "requires_maintainer_decision": status != "match",
        "safe_to_parse_pdfs": status == "match",
    }


def fetch_official_html(exam_code: str, *, timeout: int = 30) -> tuple[str, str]:
    url = exam_url(exam_code)
    response = requests.get(url, timeout=timeout, headers={"User-Agent": UA})
    response.raise_for_status()
    if len(response.content) < 1000:
        raise ProbeError(f"official page unexpectedly small: {len(response.content)} bytes")
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text, url


def probe_live(exam_code: str, *, timeout: int = 30) -> dict[str, Any]:
    try:
        html, url = fetch_official_html(exam_code, timeout=timeout)
        return compare_to_registry(exam_code, html, source_url=url)
    except Exception as exc:
        roc_year, round_name = session_from_exam_code(exam_code)
        return {
            "schema_version": 1,
            "probe": "moex_exam_page_structure_v1",
            "status": "source_error",
            "exam_code": exam_code,
            "roc_year": roc_year,
            "round": round_name,
            "source_url": exam_url(exam_code),
            "error_class": type(exc).__name__,
            "error_message": str(exc),
            "requires_maintainer_decision": True,
            "safe_to_parse_pdfs": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="MOEX 社工師官方頁面結構 discovery probe（唯讀）")
    parser.add_argument("--exam", required=True, help="六位數考試代碼，例如 115100")
    parser.add_argument("--fixture", type=Path, help="離線 HTML fixture；有指定時不連網")
    parser.add_argument("--output", type=Path, help="選擇性輸出 JSON report")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    if args.fixture:
        html = args.fixture.read_text(encoding="utf-8")
        result = compare_to_registry(args.exam, html, source_url=f"fixture://{args.fixture.name}")
    else:
        result = probe_live(args.exam, timeout=args.timeout)

    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result.get("status") == "match" else 3


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# Official MOJ legal-change watcher for the private SWSI question bank.
#
# Why direct-page mode?
# GitHub-hosted runners can reach law.moj.gov.tw but currently cannot route to
# sendlaw.moj.gov.tw/PublicData.  We therefore resolve each watched law through
# the official search page, then read its official LawAll page and modification
# date.  This keeps the source authoritative without depending on the blocked
# bulk-download host.

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin

import requests

SEARCH_BASE = "https://law.moj.gov.tw/Law/LawSearchResult.aspx?ty=ONEBAR&kw="
LAW_BASE = "https://law.moj.gov.tw/"
OFFICIAL_SOURCE = {
    "type": "law_moj_direct",
    "url": "https://law.moj.gov.tw/Law/LawSearchResult.aspx?ty=ONEBAR&kw=<法規名稱>",
}
MIN_WATCH_MATCHES = 20
DEFAULT_MIN_DAYS = 28
DEFAULT_RETRY_DAYS = 3
REQUEST_TIMEOUT = 30


def utc_now():
    return datetime.now(timezone.utc)


def iso_now():
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def key_name(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", clean_text(value)))


def load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def age_days(value):
    dt = parse_iso(value)
    if not dt:
        return None
    return (utc_now() - dt).total_seconds() / 86400


class LinkTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self._href = None
        self._parts = []
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._parts = []

    def handle_data(self, data):
        if data:
            self.text_parts.append(data)
            if self._href is not None:
                self._parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, clean_text(" ".join(self._parts))))
            self._href = None
            self._parts = []

    @property
    def text(self):
        return clean_text(" ".join(self.text_parts))


def fetch_html(session, url):
    last = None
    for attempt in range(2):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            if len(r.content) < 1000:
                raise RuntimeError(f"official page too small: {len(r.content)} bytes")
            return r.text
        except Exception as exc:
            last = exc
            if attempt == 0:
                time.sleep(0.4)
    raise RuntimeError(f"official page fetch failed: {last}")


def pcode_from_href(href):
    m = re.search(r"(?:[?&])pcode=([A-Za-z0-9]+)", str(href or ""), flags=re.I)
    return m.group(1).upper() if m else None


def candidate_pcodes(search_html, wanted_name):
    parser = LinkTextParser()
    parser.feed(search_html)
    wanted = key_name(wanted_name)

    exact = []
    others = []
    for href, label in parser.links:
        pcode = pcode_from_href(href)
        if not pcode:
            continue
        bucket = exact if key_name(label) == wanted else others
        if pcode not in bucket:
            bucket.append(pcode)

    # Some versions of the page expose pcode outside ordinary anchors.
    for pcode in re.findall(r"[?&]pcode=([A-Za-z0-9]+)", search_html, flags=re.I):
        pcode = pcode.upper()
        if pcode not in exact and pcode not in others:
            others.append(pcode)
    return exact + others


def roc_date_to_iso(roc_year, month, day):
    year = int(roc_year) + 1911
    return f"{year:04d}-{int(month):02d}-{int(day):02d}"


def extract_modified_date(page_text):
    # LawAll pages normally expose 修正日期.  For never-amended material,
    # 發布日期/公發布日 is still a stable official baseline date.
    patterns = [
        r"修正日期\s*[:：]?\s*民國\s*(\d{1,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        r"發布日期\s*[:：]?\s*民國\s*(\d{1,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        r"公發布日\s*[:：]?\s*民國\s*(\d{1,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    ]
    for pattern in patterns:
        m = re.search(pattern, page_text)
        if m:
            return roc_date_to_iso(*m.groups())
    return None


def page_matches_name(page_text, wanted_name):
    # The law name appears near the top of the official page.  Restricting the
    # search to the first section avoids accidentally matching related-law text.
    head = key_name(page_text[:15000])
    return key_name(wanted_name) in head


def resolve_official_record(session, name):
    search_url = SEARCH_BASE + quote(name)
    search_html = fetch_html(session, search_url)
    pcodes = candidate_pcodes(search_html, name)
    if not pcodes:
        return None

    # Exact-title candidates are ordered first; cap ambiguous fallbacks so one
    # odd query cannot fan out into dozens of page requests.
    for pcode in pcodes[:8]:
        page_url = urljoin(LAW_BASE, f"LawClass/LawAll.aspx?pcode={pcode}")
        try:
            html = fetch_html(session, page_url)
        except Exception:
            continue
        parser = LinkTextParser()
        parser.feed(html)
        text = parser.text
        if not page_matches_name(text, name):
            continue
        modified = extract_modified_date(text)
        abandoned = "廢止日期" in text[:15000] or "已廢止" in text[:15000]
        return {
            "canonical_name": name,
            "source_type": "law_moj_direct",
            "official_modified_date": modified,
            "official_url": page_url,
            "abandon_note": "廢止" if abandoned else None,
        }
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchlist", default="data/legal_watch_names.json")
    ap.add_argument("--state", default="data/legal_watch_state.json")
    ap.add_argument("--report", default="data/legal_watch_report.json")
    ap.add_argument("--attempt-state", default="data/legal_watch_attempt.json")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--min-days", type=int, default=DEFAULT_MIN_DAYS)
    ap.add_argument("--retry-days", type=int, default=DEFAULT_RETRY_DAYS)
    args = ap.parse_args()

    watchlist = load_json(args.watchlist, [])
    if not isinstance(watchlist, list) or not watchlist:
        raise RuntimeError("watchlist is empty or invalid")

    state = load_json(args.state, {})
    attempt_state = load_json(args.attempt_state, {})

    if not args.force:
        checked_age = age_days(state.get("checked_at"))
        if checked_age is not None and checked_age < max(1, args.min_days):
            print(f"Legal watch skipped: last success {checked_age:.1f} days ago; minimum is {args.min_days} days.")
            return 0
        if attempt_state.get("success") is False:
            attempt_age = age_days(attempt_state.get("attempted_at"))
            if attempt_age is not None and attempt_age < max(1, args.retry_days):
                print(f"Legal watch backoff: last failed attempt {attempt_age:.1f} days ago; retry after {args.retry_days} days.")
                return 0

    attempted_at = iso_now()
    write_json(args.attempt_state, {"attempted_at": attempted_at, "success": False, "error": None})

    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "swsi-law-watch/2.0 (+private educational question bank)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

        old_records = state.get("records") if isinstance(state.get("records"), dict) else {}
        baseline = not bool(old_records)
        checked_at = iso_now()
        report_records = []
        next_state_records = {}
        matched = changed = missing = 0
        lookup_errors = []

        for index, item in enumerate(watchlist, start=1):
            if isinstance(item, str):
                name, qcount = clean_text(item), 0
            else:
                name = clean_text(item.get("name"))
                qcount = int(item.get("question_count") or 0)
            if not name:
                continue

            found = None
            try:
                found = resolve_official_record(session, name)
            except Exception as exc:
                lookup_errors.append(f"{name}: {str(exc)[:240]}")

            old = old_records.get(name) if isinstance(old_records.get(name), dict) else {}
            previous_date = clean_text(old.get("official_modified_date")) or None

            if found:
                matched += 1
                current_date = clean_text(found.get("official_modified_date")) or None
                is_changed = bool(not baseline and previous_date and current_date and previous_date != current_date)
                changed += int(is_changed)
                rec = {
                    "canonical_name": name,
                    "question_count": qcount,
                    "found": True,
                    "source_type": found.get("source_type"),
                    "official_url": found.get("official_url"),
                    "official_modified_date": current_date,
                    "previous_modified_date": previous_date,
                    "changed": is_changed,
                    "abandon_note": found.get("abandon_note"),
                }
                next_state_records[name] = {
                    "question_count": qcount,
                    "source_type": found.get("source_type"),
                    "official_url": found.get("official_url"),
                    "official_modified_date": current_date,
                    "abandon_note": found.get("abandon_note"),
                }
                print(f"[{index}/{len(watchlist)}] FOUND {name} | {current_date or 'date unavailable'}")
            else:
                missing += 1
                rec = {
                    "canonical_name": name,
                    "question_count": qcount,
                    "found": False,
                    "source_type": None,
                    "official_url": None,
                    "official_modified_date": None,
                    "previous_modified_date": previous_date,
                    "changed": False,
                    "abandon_note": None,
                }
                # Preserve a previous verified baseline on a transient miss.
                next_state_records[name] = dict(old) if old else {
                    "question_count": qcount,
                    "source_type": None,
                    "official_url": None,
                    "official_modified_date": None,
                    "abandon_note": None,
                }
                print(f"[{index}/{len(watchlist)}] MISSING {name}")
            report_records.append(rec)
            time.sleep(0.05)

        if matched < MIN_WATCH_MATCHES:
            detail = "; ".join(lookup_errors[:5])
            raise RuntimeError(
                f"only {matched} watch names matched official law.moj.gov.tw pages; source/parser likely broken"
                + (f"; sample errors: {detail}" if detail else "")
            )

        report = {
            "schema_version": 2,
            "checked_at": checked_at,
            "baseline": baseline,
            "official_sources": [OFFICIAL_SOURCE],
            "source_record_counts": {"law_moj_direct": matched},
            "watch_count": len(report_records),
            "matched_count": matched,
            "missing_count": missing,
            "changed_count": changed,
            "lookup_error_count": len(lookup_errors),
            "lookup_errors": lookup_errors[:20],
            "records": report_records,
        }
        new_state = {
            "schema_version": 2,
            "checked_at": checked_at,
            "official_sources": [OFFICIAL_SOURCE],
            "source_record_counts": {"law_moj_direct": matched},
            "records": next_state_records,
        }
        write_json(args.report, report)
        write_json(args.state, new_state)
        write_json(
            args.attempt_state,
            {"attempted_at": attempted_at, "completed_at": iso_now(), "success": True, "error": None},
        )

        print(
            f"Legal watch complete: baseline={baseline}, matched={matched}, missing={missing}, "
            f"changed={changed}, lookup_errors={len(lookup_errors)}"
        )
        for r in report_records:
            if r.get("changed"):
                print(
                    f"CHANGED: {r['canonical_name']} "
                    f"{r.get('previous_modified_date')} -> {r.get('official_modified_date')}"
                )
        return 0
    except Exception as exc:
        write_json(
            args.attempt_state,
            {"attempted_at": attempted_at, "completed_at": iso_now(), "success": False, "error": str(exc)[:1000]},
        )
        raise


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Legal watch failed: {exc}", file=sys.stderr)
        sys.exit(2)

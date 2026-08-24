#!/usr/bin/env python3
# Official MOJ legal-change watcher for the private SWSI question bank.
import argparse
import io
import json
import re
import sys
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

SOURCES = [
    {"type": "law", "url": "https://sendlaw.moj.gov.tw/PublicData/GetFile.ashx?DType=XML&AuData=CF"},
    {"type": "command", "url": "https://sendlaw.moj.gov.tw/PublicData/GetFile.ashx?DType=XML&AuData=CM"},
]
NAME_TAGS = {"LawName", "法規名稱"}
DATE_TAGS = {"LawModifiedDate", "最新異動日期"}
URL_TAGS = {"LawURL", "法規網址"}
ABANDON_TAGS = {"LawAbandonNote", "廢止註記"}
MIN_SOURCE_RECORDS = 100
MIN_WATCH_MATCHES = 20
DEFAULT_MIN_DAYS = 28
DEFAULT_RETRY_DAYS = 3


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


def local_name(tag):
    return str(tag).split("}")[-1]


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def key_name(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", clean_text(value)))


def direct_child_map(elem):
    out = {}
    for child in list(elem):
        text = clean_text("".join(child.itertext()))
        if text:
            out.setdefault(local_name(child.tag), text)
    return out


def pick(mapping, names):
    for name in names:
        if mapping.get(name):
            return mapping[name]
    return ""


def extract_xml_bytes(content):
    bio = io.BytesIO(content)
    if zipfile.is_zipfile(bio):
        with zipfile.ZipFile(bio) as zf:
            candidates = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not candidates:
                candidates = [n for n in zf.namelist() if not n.endswith("/")]
            if not candidates:
                raise RuntimeError("MOJ ZIP contains no readable files")
            candidates.sort(key=lambda n: zf.getinfo(n).file_size, reverse=True)
            return zf.read(candidates[0])
    return content


def parse_records(xml_bytes, source_type):
    root = ET.fromstring(xml_bytes)
    records = {}
    for elem in root.iter():
        cmap = direct_child_map(elem)
        name = pick(cmap, NAME_TAGS)
        modified = pick(cmap, DATE_TAGS)
        if not name or not modified:
            continue
        records.setdefault(
            key_name(name),
            {
                "canonical_name": clean_text(name),
                "source_type": source_type,
                "official_modified_date": clean_text(modified),
                "official_url": clean_text(pick(cmap, URL_TAGS)) or None,
                "abandon_note": clean_text(pick(cmap, ABANDON_TAGS)) or None,
            },
        )
    return records


def download_source(source):
    headers = {
        "User-Agent": "swsi-law-watch/1.1 (+private educational question bank)",
        "Accept": "application/xml, application/zip, application/octet-stream, */*",
    }
    last = None
    for attempt in range(2):
        try:
            r = requests.get(source["url"], timeout=90, headers=headers)
            r.raise_for_status()
            records = parse_records(extract_xml_bytes(r.content), source["type"])
            if len(records) < MIN_SOURCE_RECORDS:
                raise RuntimeError(f"parsed too few records from {source['type']}: {len(records)}")
            return records
        except Exception as exc:
            last = exc
            if attempt == 1:
                break
    raise RuntimeError(f"MOJ {source['type']} download/parse failed: {last}")


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
        all_records = {}
        source_counts = {}
        for source in SOURCES:
            recs = download_source(source)
            source_counts[source["type"]] = len(recs)
            for k, v in recs.items():
                all_records.setdefault(k, v)

        old_records = state.get("records") if isinstance(state.get("records"), dict) else {}
        baseline = not bool(old_records)
        checked_at = iso_now()
        report_records = []
        next_state_records = {}
        matched = changed = missing = 0

        for item in watchlist:
            if isinstance(item, str):
                name, qcount = clean_text(item), 0
            else:
                name = clean_text(item.get("name"))
                qcount = int(item.get("question_count") or 0)
            if not name:
                continue

            found = all_records.get(key_name(name))
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
                next_state_records[name] = dict(old) if old else {
                    "question_count": qcount,
                    "source_type": None,
                    "official_url": None,
                    "official_modified_date": None,
                    "abandon_note": None,
                }
            report_records.append(rec)

        if matched < MIN_WATCH_MATCHES:
            raise RuntimeError(f"only {matched} watch names matched official datasets; parser/source likely broken")

        report = {
            "schema_version": 1,
            "checked_at": checked_at,
            "baseline": baseline,
            "official_sources": SOURCES,
            "source_record_counts": source_counts,
            "watch_count": len(report_records),
            "matched_count": matched,
            "missing_count": missing,
            "changed_count": changed,
            "records": report_records,
        }
        new_state = {
            "schema_version": 1,
            "checked_at": checked_at,
            "official_sources": SOURCES,
            "source_record_counts": source_counts,
            "records": next_state_records,
        }
        write_json(args.report, report)
        write_json(args.state, new_state)
        write_json(args.attempt_state, {"attempted_at": attempted_at, "completed_at": iso_now(), "success": True, "error": None})

        print(f"Legal watch complete: baseline={baseline}, matched={matched}, missing={missing}, changed={changed}, sources={source_counts}")
        for r in report_records:
            if r.get("changed"):
                print(f"CHANGED: {r['canonical_name']} {r.get('previous_modified_date')} -> {r.get('official_modified_date')}")
        return 0
    except Exception as exc:
        write_json(args.attempt_state, {"attempted_at": attempted_at, "completed_at": iso_now(), "success": False, "error": str(exc)[:1000]})
        raise


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Legal watch failed: {exc}", file=sys.stderr)
        sys.exit(2)

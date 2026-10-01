#!/usr/bin/env python3
"""Probe official MOJ Open API coverage for the historical-law target set.

The MOJ Open API publishes the current Chinese law/order corpus as ZIP archives
containing one JSON file. This probe is read-only and is intentionally separate
from Stage 4 until availability and target coverage are proven in Actions.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import time
import zipfile
from pathlib import Path
from typing import Any

import historical_law_provenance_core as hp

ROOT = Path(__file__).resolve().parents[1]
LAW_API = "https://law.moj.gov.tw/api/ch/law/json"
ORDER_API = "https://law.moj.gov.tw/api/ch/order/json"
DEFAULT_HISTORY_SNAPSHOT = ROOT / "auto/qa/historical_law_history_snapshot.v1.json"
DEFAULT_OUTPUT = ROOT / "auto/qa/historical_law_moj_api_probe.v1.json"
UA = "swsi-historical-law-open-api-probe/1.0 (+private educational question bank)"


def _download_payload(session: Any, url: str, attempts: int = 3) -> dict:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=180, headers={"User-Agent": UA})
            response.raise_for_status()
            content = bytes(response.content or b"")
            if content[:4] not in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
                raise RuntimeError(
                    f"MOJ Open API response is not ZIP: status={response.status_code}, prefix={content[:12]!r}"
                )
            with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
                names = [name for name in archive.namelist() if name.lower().endswith(".json")]
                if len(names) != 1:
                    raise RuntimeError(f"expected exactly one JSON in MOJ API ZIP, got {names[:10]}")
                raw = archive.read(names[0]).decode("utf-8-sig")
            payload = json.loads(raw)
            if not isinstance(payload.get("Laws"), list):
                raise RuntimeError("MOJ API payload missing Laws list")
            return payload
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    assert last_error is not None
    raise last_error


def _pcode(law: dict) -> str | None:
    return hp.pcode_from_url(str(law.get("LawURL") or ""))


def _article_no(value: object) -> str | None:
    text = str(value or "").strip().replace("之", "-")
    text = re.sub(r"^第\s*", "", text)
    text = re.sub(r"\s*條$", "", text)
    return hp.normalize_article_no(text)


def _article_summary(law: dict) -> tuple[int, list[str]]:
    numbers: list[str] = []
    for row in law.get("LawArticles") or []:
        if str(row.get("ArticleType") or "") == "C":
            continue
        no = _article_no(row.get("ArticleNo"))
        content = str(row.get("ArticleContent") or "").strip()
        if no and content:
            numbers.append(no)
    return len(numbers), numbers


def _index(payload: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for law in payload.get("Laws") or []:
        pcode = _pcode(law)
        if pcode:
            out[pcode.upper()] = law
    return out


def build_report(history_snapshot: dict, law_payload: dict, order_payload: dict) -> dict:
    law_index = _index(law_payload)
    order_index = _index(order_payload)
    records: list[dict] = []
    for target in history_snapshot.get("records") or []:
        pcode = str(target.get("pcode") or "").upper()
        expected_name = str(target.get("law_name") or "")
        collection = "law" if pcode in law_index else "order" if pcode in order_index else None
        source = law_index.get(pcode) or order_index.get(pcode)
        if source is None:
            records.append({
                "law_name": expected_name,
                "pcode": pcode,
                "status": "not_found",
            })
            continue
        count, numbers = _article_summary(source)
        api_name = str(source.get("LawName") or "")
        api_url = str(source.get("LawURL") or "")
        records.append({
            "law_name": expected_name,
            "pcode": pcode,
            "status": "ready" if count > 0 and api_name else "invalid_record",
            "collection": collection,
            "api_law_name": api_name,
            "name_matches": hp.clean_text(api_name) == hp.clean_text(expected_name),
            "api_law_url": api_url,
            "url_pcode_matches": (_pcode(source) or "").upper() == pcode,
            "modified_date": source.get("LawModifiedDate"),
            "article_count": count,
            "article_numbers_sample": numbers[:12],
            "has_histories": bool(source.get("LawHistories")),
        })
    return {
        "schema_version": 1,
        "method": "official MOJ Open API ZIP/JSON current corpus coverage probe; read-only",
        "law_api": LAW_API,
        "order_api": ORDER_API,
        "law_update_date": law_payload.get("UpdateDate"),
        "order_update_date": order_payload.get("UpdateDate"),
        "law_corpus_count": len(law_payload.get("Laws") or []),
        "order_corpus_count": len(order_payload.get("Laws") or []),
        "target_count": len(records),
        "ready_count": sum(r.get("status") == "ready" for r in records),
        "not_found_count": sum(r.get("status") == "not_found" for r in records),
        "protected_core_mutation_count": 0,
        "historical_version_checked_count": 0,
        "records": records,
    }


def main() -> int:
    import requests

    parser = argparse.ArgumentParser()
    parser.add_argument("--history-snapshot", default=str(DEFAULT_HISTORY_SNAPSHOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    history_snapshot = json.loads(Path(args.history_snapshot).read_text(encoding="utf-8"))
    session = requests.Session()
    try:
        law_payload = _download_payload(session, LAW_API)
        order_payload = _download_payload(session, ORDER_API)
    finally:
        session.close()
    report = build_report(history_snapshot, law_payload, order_payload)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "law_update_date": report.get("law_update_date"),
        "order_update_date": report.get("order_update_date"),
        "law_corpus_count": report.get("law_corpus_count"),
        "order_corpus_count": report.get("order_corpus_count"),
        "target_count": report.get("target_count"),
        "ready_count": report.get("ready_count"),
        "not_found_count": report.get("not_found_count"),
        "targets": [
            {
                "law_name": row.get("law_name"),
                "pcode": row.get("pcode"),
                "status": row.get("status"),
                "collection": row.get("collection"),
                "article_count": row.get("article_count"),
            }
            for row in report.get("records") or []
        ],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read-only source-observation shadow adapter for the existing MOJ legal watcher.

This adapter intentionally does not modify data/legal_watch_state.json,
data/legal_watch_report.json, Official Core, or any production store. It reads a
verified legal-watch report, re-fetches one already-resolved official LawAll URL,
and emits the shared source_observation_contract plus a separate shadow state.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests

from moj_law_watch import (
    ARTICLE_FINGERPRINT_VERSION,
    LinkTextParser,
    extract_article_fingerprints,
    page_matches_name,
)
from source_observation_contract import build_observation, canonical_url, source_id

ALLOWED_HOST = "law.moj.gov.tw"
DEFAULT_TIMEOUT = 30
TRUSTED_OUTCOMES = {"success_changed", "success_no_change", "correction_detected"}


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default):
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def assert_official_url(url: str) -> str:
    normalized = canonical_url(url)
    parsed = urlsplit(normalized)
    if parsed.hostname != ALLOWED_HOST:
        raise ValueError(f"shadow adapter only permits {ALLOWED_HOST}")
    if not parsed.path.lower().endswith("/lawall.aspx"):
        raise ValueError("shadow adapter only permits an existing MOJ LawAll URL")
    return normalized


def choose_record(report: dict, law_name: str | None = None) -> dict:
    records = report.get("records")
    if not isinstance(records, list):
        raise ValueError("legal-watch report records missing")
    for row in records:
        if not isinstance(row, dict) or row.get("found") is not True:
            continue
        if law_name and str(row.get("canonical_name") or "").strip() != law_name.strip():
            continue
        url = row.get("official_url")
        if not url:
            continue
        assert_official_url(str(url))
        return row
    raise ValueError("no matching verified MOJ LawAll record found in legal-watch report")


def strict_decode(body: bytes, encoding: str | None) -> tuple[str | None, bool, str]:
    candidates = []
    for value in (encoding, "utf-8"):
        value = str(value or "").strip()
        if value and value.lower() not in {x.lower() for x in candidates}:
            candidates.append(value)
    last = None
    for value in candidates:
        try:
            return body.decode(value, errors="strict"), False, value
        except (UnicodeDecodeError, LookupError) as exc:
            last = exc
    return None, True, candidates[0] if candidates else "utf-8"


def observe_record(*, record: dict, shadow_state: dict, session, fetched_at: str,
                   timeout: int = DEFAULT_TIMEOUT) -> tuple[dict, dict]:
    name = str(record.get("canonical_name") or "").strip()
    if not name:
        raise ValueError("canonical_name missing")
    requested_url = assert_official_url(str(record.get("official_url") or ""))
    sid = source_id(requested_url)
    previous_records = shadow_state.get("records") if isinstance(shadow_state.get("records"), dict) else {}
    previous = previous_records.get(sid) if isinstance(previous_records.get(sid), dict) else {}
    previous_normalized_hash = previous.get("normalized_content_hash")
    previous_trusted_hash = previous.get("last_trusted_hash")

    transport = "ok"
    http_status = None
    body = None
    decoded_text = None
    decode_failed = False
    parser_ok = False
    parser_contract_changed = False
    item_count = None
    final_url = None
    redirect_count = 0
    used_encoding = None

    try:
        response = session.get(requested_url, timeout=timeout, allow_redirects=True)
        http_status = int(response.status_code)
        body = bytes(response.content or b"")
        final_url = canonical_url(str(response.url or requested_url))
        redirect_count = len(getattr(response, "history", []) or [])
        final_host_ok = urlsplit(final_url).hostname == ALLOWED_HOST
        decoded_text, decode_failed, used_encoding = strict_decode(body, getattr(response, "encoding", None))

        if 200 <= http_status < 300 and not decode_failed and decoded_text is not None and final_host_ok:
            text_parser = LinkTextParser()
            text_parser.feed(decoded_text)
            name_ok = page_matches_name(text_parser.text, name)
            fingerprints = extract_article_fingerprints(decoded_text) if name_ok else {}
            parser_contract_changed = bool(name_ok and not fingerprints)
            parser_ok = bool(name_ok and fingerprints and not parser_contract_changed)
            item_count = len(fingerprints) if parser_ok else None
        elif 200 <= http_status < 300 and not final_host_ok:
            parser_ok = False
            item_count = None
    except requests.Timeout:
        transport = "timeout"
    except requests.RequestException:
        transport = "network_error"

    observation = build_observation(
        name=name,
        url=requested_url,
        source_type="official_law",
        region="taiwan",
        expected_format="html_lawall",
        parser_id="moj_law_watch_shadow",
        parser_version=ARTICLE_FINGERPRINT_VERSION,
        fetched_at=fetched_at,
        transport=transport,
        http_status=http_status,
        body=body,
        decoded_text=decoded_text,
        decode_failed=decode_failed,
        parser_ok=parser_ok,
        parser_contract_changed=parser_contract_changed,
        item_count=item_count,
        previous_normalized_hash=previous_normalized_hash,
        previous_trusted_hash=previous_trusted_hash,
        correction_from_hash=None,
        effective_at=record.get("official_modified_date"),
    )
    observation["adapter"] = {
        "mode": "shadow_read_only",
        "source_pipeline": "moj_law_watch",
        "requested_url": requested_url,
        "final_url": final_url,
        "redirect_count": redirect_count,
        "decode_encoding": used_encoding,
        "official_legal_watch_state_mutation": False,
        "official_legal_watch_report_mutation": False,
        "official_core_mutation": False,
        "production_publish_allowed": False,
    }

    next_records = dict(previous_records)
    trusted = observation["observation"].get("last_trusted_hash")
    normalized = observation["observation"].get("normalized_content_hash")
    if observation["observation"]["outcome"] in TRUSTED_OUTCOMES and trusted:
        next_records[sid] = {
            "canonical_name": name,
            "canonical_url": requested_url,
            "normalized_content_hash": normalized,
            "last_trusted_hash": trusted,
            "last_outcome": observation["observation"]["outcome"],
            "checked_at": fetched_at,
            "parser_version": ARTICLE_FINGERPRINT_VERSION,
        }
    elif previous:
        kept = dict(previous)
        kept["last_outcome"] = observation["observation"]["outcome"]
        kept["last_attempt_at"] = fetched_at
        next_records[sid] = kept

    next_state = {
        "schema_version": 1,
        "mode": "shadow_read_only",
        "records": next_records,
    }
    return observation, next_state


class _FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200, url: str, encoding: str = "utf-8", history=None):
        self.content = body
        self.status_code = status
        self.url = url
        self.encoding = encoding
        self.history = list(history or [])


class _FakeSession:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc

    def get(self, url, timeout=None, allow_redirects=True):
        if self.exc:
            raise self.exc
        return self.response


def _fixture_html(name="社會工作師法") -> bytes:
    return (
        "<html><body><h1>" + name + "</h1>"
        "<div id=\"pnLawFla\"><div>第 1 條</div><div>測試條文內容。</div>"
        "<div>第 2 條</div><div>第二條測試內容。</div></div></body></html>"
    ).encode("utf-8")


def self_test() -> dict:
    record = {
        "canonical_name": "社會工作師法",
        "found": True,
        "official_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=D0050077",
        "official_modified_date": "2025-01-01",
    }
    state = {"schema_version": 1, "mode": "shadow_read_only", "records": {}}
    response = _FakeResponse(_fixture_html(), url=record["official_url"])

    first, state = observe_record(record=record, shadow_state=state, session=_FakeSession(response), fetched_at="2026-10-02T12:00:00Z")
    assert first["observation"]["outcome"] == "success_changed"
    assert first["observation"]["raw_content_hash"]
    assert first["adapter"]["official_core_mutation"] is False

    second, state2 = observe_record(record=record, shadow_state=state, session=_FakeSession(response), fetched_at="2026-10-02T12:01:00Z")
    assert second["observation"]["outcome"] == "success_no_change"
    assert second["observation"]["replacement_allowed"] is False
    assert state2["records"]

    bad_redirect = _FakeResponse(_fixture_html(), url="https://evil.example.invalid/LawAll.aspx?pcode=D0050077", history=[object()])
    invalid, kept = observe_record(record=record, shadow_state=state2, session=_FakeSession(bad_redirect), fetched_at="2026-10-02T12:02:00Z")
    assert invalid["observation"]["outcome"] == "invalid_content"
    assert invalid["observation"]["last_trusted_hash"] == second["observation"]["last_trusted_hash"]
    assert kept["records"]

    missing_container = _FakeResponse(b"<html><body><h1>\xe7\xa4\xbe\xe6\x9c\x83\xe5\xb7\xa5\xe4\xbd\x9c\xe5\xb8\xab\xe6\xb3\x95</h1></body></html>", url=record["official_url"])
    parser_changed, _ = observe_record(record=record, shadow_state=state2, session=_FakeSession(missing_container), fetched_at="2026-10-02T12:03:00Z")
    assert parser_changed["observation"]["outcome"] == "parser_contract_changed"

    unavailable, _ = observe_record(record=record, shadow_state=state2, session=_FakeSession(exc=requests.Timeout("synthetic")), fetched_at="2026-10-02T12:04:00Z")
    assert unavailable["observation"]["outcome"] == "source_unavailable"
    assert unavailable["observation"]["last_trusted_hash"] == second["observation"]["last_trusted_hash"]

    return {
        "status": "pass",
        "cases": 5,
        "first_outcome": first["observation"]["outcome"],
        "second_outcome": second["observation"]["outcome"],
        "trusted_hash_preserved_on_failure": True,
        "official_state_mutation": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only MOJ legal-watch source observation shadow adapter")
    ap.add_argument("--report", default="data/legal_watch_report.json")
    ap.add_argument("--state", default="/tmp/swsi_moj_shadow_state.json")
    ap.add_argument("--output", default="/tmp/swsi_moj_shadow_observation.json")
    ap.add_argument("--law-name")
    ap.add_argument("--fetched-at")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    report_path = Path(args.report)
    report_before = report_path.read_bytes()
    report = json.loads(report_before.decode("utf-8"))
    record = choose_record(report, args.law_name)
    state_path = Path(args.state)
    shadow_state = load_json(state_path, {"schema_version": 1, "mode": "shadow_read_only", "records": {}})

    session = requests.Session()
    session.headers.update({
        "User-Agent": "swsi-source-observation-shadow/1.0 (+educational read-only verification)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    observation, next_state = observe_record(
        record=record,
        shadow_state=shadow_state,
        session=session,
        fetched_at=args.fetched_at or iso_now(),
        timeout=args.timeout,
    )
    write_json(Path(args.output), observation)
    write_json(state_path, next_state)

    if report_path.read_bytes() != report_before:
        raise RuntimeError("shadow adapter must not mutate the legal-watch report")

    summary = {
        "source": observation["source"]["name"],
        "source_id": observation["source"]["source_id"],
        "outcome": observation["observation"]["outcome"],
        "replacement_allowed": observation["observation"]["replacement_allowed"],
        "raw_hash_present": bool(observation["observation"]["raw_content_hash"]),
        "normalized_hash_present": bool(observation["observation"]["normalized_content_hash"]),
        "item_count": observation["observation"]["item_count"],
        "redirect_count": observation["adapter"]["redirect_count"],
        "shadow_only": True,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Replay evidence-adjudicated historical-law decisions and build a mixed verified registry.

The Stage 7 machine registry stays machine-only. This script consumes only cases
that Stage 6 deliberately left at ``historical_semantic_support`` and replays a
separate evidence adjudication against tracked question data plus Stage 4/5/6
artifacts. It never writes or copies protected Official Core into the output.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADJUDICATION = ROOT / "data/historical_law_evidence_adjudication.v1.json"
DEFAULT_MACHINE = ROOT / "data/historical_law_verified_priority10.v1.json"
DEFAULT_STAGE4 = ROOT / "auto/qa/historical_law_oldver_stage4.v1.json"
DEFAULT_STAGE5 = ROOT / "auto/qa/historical_law_stage5_promotion.v1.json"
DEFAULT_STAGE6 = ROOT / "auto/qa/historical_law_stage6_semantic.v1.json"
DEFAULT_LINKS = ROOT / "data/law_question_links_priority10.v1.json"
DEFAULT_SHARDS = ROOT / "cdn/question-shards"
DEFAULT_OUTPUT = ROOT / "data/historical_law_verified_combined.v1.json"

MACHINE_LEVEL = "machine_verified_historical_v1"
ADJUDICATED_LEVEL = "evidence_adjudicated_historical_v1"
ALLOWED_DECISIONS = {"confirmed", "held"}
VERSION_FIELDS = (
    "kind", "version_date", "effective_date", "effective_date_scope",
    "lnndate", "lser", "url",
)
PROTECTED_CORE_FIELDS = {
    "stem", "question", "options", "official_answer", "answer",
    "accepted_answers", "grading_mode",
}


def key(row: dict) -> tuple[str, str]:
    return str(row.get("law_name") or ""), str(row.get("question_id") or "")


def compact_version(value: object) -> dict:
    src = value if isinstance(value, dict) else {}
    return {field: src.get(field) for field in VERSION_FIELDS}


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", text).lower()


def require_https(url: object, hosts: tuple[str, ...], label: str) -> str:
    raw = str(url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        raise ValueError(f"{label} must be HTTPS on {hosts}: {raw}")
    return raw


def rows_by_key(payload: dict) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for row in payload.get("records") or []:
        k = key(row)
        if not all(k) or k in out:
            raise ValueError(f"invalid/duplicate record key: {k}")
        out[k] = row
    return out


def question_link_map(payload: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for card in payload.get("cards") or []:
        for row in card.get("questions") or []:
            qid = str(row.get("question_id") or "").strip()
            if not qid or qid in out:
                raise ValueError(f"invalid/duplicate law-link question id: {qid!r}")
            out[qid] = row
    return out


def load_question_shards(directory: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("questions") or []:
            qid = str(row.get("id") or row.get("question_id") or "").strip()
            if not qid:
                continue
            if qid in out:
                raise ValueError(f"duplicate question id across shards: {qid}")
            copy_row = dict(row)
            copy_row["_shard_path"] = path.as_posix()
            out[qid] = copy_row
    return out


def answer_option(row: dict, answer: str) -> str:
    letter = str(answer or "").strip().upper()
    if letter not in {"A", "B", "C", "D"}:
        raise ValueError(f"unsupported adjudication answer: {letter}")
    direct = row.get(f"opt_{letter.lower()}")
    if direct is not None:
        return str(direct)
    options = row.get("options")
    if isinstance(options, dict):
        return str(options.get(letter) or options.get(letter.lower()) or "")
    if isinstance(options, list):
        index = ord(letter) - ord("A")
        return str(options[index] if index < len(options) else "")
    return ""


def article_text(stage4_row: dict, article: str) -> str:
    snap = stage4_row.get("historical_version_snapshot") or {}
    matches = [
        row for row in (snap.get("articles") or [])
        if str(row.get("article_no") or row.get("article") or row.get("no") or "") == article
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one Stage4 article {article} for {key(stage4_row)}, got {len(matches)}"
        )
    return str(matches[0].get("text") or "")


def validate_machine_registry(payload: dict) -> list[dict]:
    if payload.get("schema_version") != 1:
        raise ValueError("machine registry schema_version must be 1")
    records = payload.get("records") or []
    if len(records) != payload.get("verified_record_count"):
        raise ValueError("machine registry verified_record_count drift")
    seen: set[tuple[str, str]] = set()
    for row in records:
        k = key(row)
        if not all(k) or k in seen:
            raise ValueError(f"invalid/duplicate machine registry key: {k}")
        seen.add(k)
        if row.get("historical_version_checked") is not True:
            raise ValueError(f"machine registry row lost checked=true: {k}")
        if row.get("verification_level") != MACHINE_LEVEL:
            raise ValueError(f"machine registry must stay machine-only: {k}")
        if PROTECTED_CORE_FIELDS & set(row):
            raise ValueError(f"machine registry contains protected core fields: {k}")
    return [dict(row) for row in records]


def validate_adjudication_payload(payload: dict) -> list[dict]:
    if payload.get("schema_version") != 1:
        raise ValueError("adjudication schema_version must be 1")
    if payload.get("verification_level") != ADJUDICATED_LEVEL:
        raise ValueError("unexpected adjudication verification_level")
    rows = payload.get("records") or []
    if len(rows) != payload.get("record_count"):
        raise ValueError("adjudication record_count drift")
    seen: set[tuple[str, str]] = set()
    for row in rows:
        k = key(row)
        if not all(k) or k in seen:
            raise ValueError(f"invalid/duplicate adjudication key: {k}")
        seen.add(k)
        if row.get("verification_level") != ADJUDICATED_LEVEL:
            raise ValueError(f"adjudication row uses unknown method: {k}")
        if row.get("decision") not in ALLOWED_DECISIONS:
            raise ValueError(f"invalid adjudication decision: {k}")
        if row.get("expected_stage6_status") != "historical_semantic_support":
            raise ValueError(f"adjudication may only consume Stage6 support/held cases: {k}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("historical_article_sha256") or "")):
            raise ValueError(f"invalid article fingerprint: {k}")
        if not row.get("stem_contains") or not row.get("answer_option_contains") or not row.get("article_contains"):
            raise ValueError(f"adjudication needs positive stem/option/article markers: {k}")
        if not isinstance(row.get("evidence_run_id"), int) or row["evidence_run_id"] <= 0:
            raise ValueError(f"invalid evidence run id: {k}")
        if not isinstance(row.get("evidence_artifact_id"), int) or row["evidence_artifact_id"] <= 0:
            raise ValueError(f"invalid evidence artifact id: {k}")
    return rows


def adjudicated_records(
    adjudication: dict,
    stage4: dict,
    stage5: dict,
    stage6: dict,
    links: dict,
    questions: dict[str, dict],
) -> list[dict]:
    s4 = rows_by_key(stage4)
    s5 = rows_by_key(stage5)
    s6 = rows_by_key(stage6)
    link_map = question_link_map(links)
    rows = validate_adjudication_payload(adjudication)
    confirmed: list[dict] = []

    for evidence in rows:
        k = key(evidence)
        qid = k[1]
        four = s4.get(k)
        five = s5.get(k)
        six = s6.get(k)
        link = link_map.get(qid)
        question = questions.get(qid)
        if not all((four, five, six, link, question)):
            raise ValueError(f"missing tracked evidence for adjudication: {k}")

        article = str(evidence.get("article") or "")
        expected_hash = str(evidence.get("historical_article_sha256") or "")
        if str(six.get("status") or "") != str(evidence.get("expected_stage6_status") or ""):
            raise ValueError(f"Stage6 status drift: {k}")
        if str(six.get("historical_decision_reason") or "") != str(evidence.get("expected_stage6_decision_reason") or ""):
            raise ValueError(f"Stage6 decision-reason drift: {k}")
        if str(six.get("suggested_article") or "") != article:
            raise ValueError(f"Stage6 article drift: {k}")
        if str(six.get("historical_article_sha256") or "") != expected_hash:
            raise ValueError(f"Stage6 article hash drift: {k}")

        if five.get("promotion_status") != "promotion_candidate":
            raise ValueError(f"Stage5 no longer marks promotion_candidate: {k}")
        history_url = require_https(five.get("official_history_url"), ("law.moj.gov.tw",), f"{k} Stage5 official_history_url")
        exam_date_url = require_https(five.get("exam_date_source_url"), ("wwwc.moex.gov.tw",), f"{k} Stage5 exam_date_source_url")

        if four.get("eligible_for_historical_version_checked") is not True:
            raise ValueError(f"Stage4 no longer eligible for historical verification: {k}")
        if str(four.get("suggested_article") or "") != article:
            raise ValueError(f"Stage4 article drift: {k}")
        if str(four.get("historical_article_sha256") or "") != expected_hash:
            raise ValueError(f"Stage4 article hash drift: {k}")
        if compact_version(four.get("selected_version")) != compact_version(six.get("selected_version")):
            raise ValueError(f"Stage4/Stage6 selected-version mismatch: {k}")
        version = compact_version(six.get("selected_version"))
        require_https(version.get("url"), ("law.moj.gov.tw",), f"{k} selected version")

        law_text = article_text(four, article)
        for marker in evidence.get("article_contains") or []:
            if norm(marker) not in norm(law_text):
                raise ValueError(f"exam-time article marker missing for {k}: {marker!r}")

        expected_answer = str(evidence.get("expected_official_answer") or "").strip().upper()
        if str(link.get("official_answer") or "").strip().upper() != expected_answer:
            raise ValueError(f"law-link official answer drift: {k}")
        if str(link.get("exam_code") or "") != str(evidence.get("exam_code") or ""):
            raise ValueError(f"law-link exam code drift: {k}")
        for marker in evidence.get("stem_contains") or []:
            if norm(marker) not in norm(link.get("stem")):
                raise ValueError(f"law-link stem marker missing for {k}: {marker!r}")

        q_answer = str(question.get("answer") or question.get("official_answer") or "").strip().upper()
        if q_answer != expected_answer:
            raise ValueError(f"question-shard official answer drift: {k}")
        q_stem = question.get("question") or question.get("q") or question.get("stem")
        for marker in evidence.get("stem_contains") or []:
            if norm(marker) not in norm(q_stem):
                raise ValueError(f"question-shard stem marker missing for {k}: {marker!r}")
        option = answer_option(question, expected_answer)
        for marker in evidence.get("answer_option_contains") or []:
            if norm(marker) not in norm(option):
                raise ValueError(f"official answer-option marker missing for {k}: {marker!r}")
        require_https(question.get("source_url"), ("wwwq.moex.gov.tw",), f"{k} question source_url")

        if evidence.get("decision") == "held":
            continue

        semantic = {
            "top_article": six.get("historical_top_article"),
            "top_score": six.get("historical_top_score"),
            "second_article": six.get("historical_second_article"),
            "second_score": six.get("historical_second_score"),
            "margin": six.get("historical_margin"),
            "decision_reason": six.get("historical_decision_reason"),
            "status_before_adjudication": six.get("status"),
        }
        confirmed.append({
            "law_name": k[0],
            "question_id": qid,
            "exam_code": evidence.get("exam_code"),
            "article": article,
            "historical_version_checked": True,
            "verification_level": ADJUDICATED_LEVEL,
            "verification_basis": (
                "Evidence adjudication of a Stage6 historical_semantic_support case: "
                "tracked official question/answer + selected answer-option markers + "
                "Stage4 official MOJ exam-time article fingerprint/text."
            ),
            "selected_version": version,
            "historical_article_sha256": expected_hash,
            "historical_semantic": semantic,
            "official_history_url": history_url,
            "exam_date_source_url": exam_date_url,
            "evidence_adjudication": {
                "decision": "confirmed",
                "method": ADJUDICATED_LEVEL,
                "evidence_run_id": evidence.get("evidence_run_id"),
                "evidence_artifact_id": evidence.get("evidence_artifact_id"),
            },
        })

    return sorted(confirmed, key=key)


def build_combined_registry(machine_registry: dict, adjudication: dict, stage4: dict, stage5: dict, stage6: dict, links: dict, questions: dict[str, dict]) -> dict:
    machine = validate_machine_registry(machine_registry)
    adjudicated = adjudicated_records(adjudication, stage4, stage5, stage6, links, questions)
    combined: dict[tuple[str, str], dict] = {}
    for row in machine + adjudicated:
        k = key(row)
        if k in combined:
            raise ValueError(f"machine/adjudicated verified-key conflict: {k}")
        if PROTECTED_CORE_FIELDS & set(row):
            raise ValueError(f"combined registry contains protected Official Core fields: {k}")
        combined[k] = row
    rows = [combined[k] for k in sorted(combined)]
    counts = {
        MACHINE_LEVEL: sum(row.get("verification_level") == MACHINE_LEVEL for row in rows),
        ADJUDICATED_LEVEL: sum(row.get("verification_level") == ADJUDICATED_LEVEL for row in rows),
    }
    return {
        "schema_version": 1,
        "scope": "priority10 historical-law verified student-safe metadata overlay",
        "method": "Union of the unchanged machine-only Stage7 registry and separately replayed evidence adjudications. Verification methods stay explicit; Official Core is not copied or modified.",
        "verified_record_count": len(rows),
        "historical_version_checked_count": sum(row.get("historical_version_checked") is True for row in rows),
        "verification_level_counts": counts,
        "records": rows,
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adjudication", default=str(DEFAULT_ADJUDICATION))
    parser.add_argument("--machine-registry", default=str(DEFAULT_MACHINE))
    parser.add_argument("--stage4", default=str(DEFAULT_STAGE4))
    parser.add_argument("--stage5", default=str(DEFAULT_STAGE5))
    parser.add_argument("--stage6", default=str(DEFAULT_STAGE6))
    parser.add_argument("--links", default=str(DEFAULT_LINKS))
    parser.add_argument("--shards-dir", default=str(DEFAULT_SHARDS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = build_combined_registry(
        load_json(Path(args.machine_registry)),
        load_json(Path(args.adjudication)),
        load_json(Path(args.stage4)),
        load_json(Path(args.stage5)),
        load_json(Path(args.stage6)),
        load_json(Path(args.links)),
        load_question_shards(Path(args.shards_dir)),
    )
    serialized = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    out_path = Path(args.output)
    if args.check:
        if not out_path.exists() or out_path.read_text(encoding="utf-8") != serialized:
            raise SystemExit("combined historical-law registry drift: regenerate with scripts/historical_law_evidence_adjudication.py")
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(serialized, encoding="utf-8")
    print(json.dumps({
        "verified_record_count": output["verified_record_count"],
        "machine_verified_count": output["verification_level_counts"][MACHINE_LEVEL],
        "evidence_adjudicated_count": output["verification_level_counts"][ADJUDICATED_LEVEL],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

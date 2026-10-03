#!/usr/bin/env python3
"""Replay evidence-adjudicated historical-law decisions from durable evidence.

The existing Stage 7 machine registry remains machine-only. This script consumes
only explicitly adjudicated cases that Stage 6 left at historical_semantic_support.
The replay source is the minimized, versioned evidence snapshot committed under
``data/`` plus the current tracked law-question links and question shards.

It does not depend on ephemeral ``auto/qa`` artifacts at runtime and never writes
or copies protected Official Core fields into the combined verified registry.
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
DEFAULT_EVIDENCE_SNAPSHOT = ROOT / "data/historical_law_evidence_snapshot.v1.json"
DEFAULT_LINKS = ROOT / "data/law_question_links_priority10.v1.json"
DEFAULT_SHARDS = ROOT / "cdn/question-shards"
DEFAULT_OUTPUT = ROOT / "data/historical_law_verified_combined.v1.json"

MACHINE_LEVEL = "machine_verified_historical_v1"
ADJUDICATED_LEVEL = "evidence_adjudicated_historical_v1"
ALLOWED_DECISIONS = {"confirmed", "held"}
VERSION_FIELDS = (
    "kind",
    "version_date",
    "effective_date",
    "effective_date_scope",
    "lnndate",
    "lser",
    "url",
)
PROTECTED_CORE_FIELDS = {
    "stem",
    "question",
    "options",
    "official_answer",
    "answer",
    "accepted_answers",
    "grading_mode",
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


def rows_by_key(payload: dict, label: str) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    rows = payload.get("records") or []
    if not isinstance(rows, list):
        raise ValueError(f"{label} records must be a list")
    for row in rows:
        k = key(row)
        if not all(k) or k in out:
            raise ValueError(f"{label} invalid/duplicate record key: {k}")
        out[k] = row
    return out


def question_link_map(payload: dict) -> dict[tuple[str, str], dict]:
    """Index explicit law-question pairs, not globally unique question IDs.

    One official question may legitimately be linked to more than one law. The
    invariant is uniqueness of (law_name, question_id), matching the registry's
    86 link pairs / 85 unique questions shape.
    """
    out: dict[tuple[str, str], dict] = {}
    for card in payload.get("cards") or []:
        law_name = str(card.get("law_name") or "").strip()
        if not law_name:
            raise ValueError("law-link card missing law_name")
        for row in card.get("questions") or []:
            qid = str(row.get("question_id") or "").strip()
            pair = (law_name, qid)
            if not qid or pair in out:
                raise ValueError(f"invalid/duplicate law-question pair: {pair!r}")
            out[pair] = row
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
    if not out:
        raise ValueError("question shard corpus is empty")
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


def validate_machine_registry(payload: dict) -> list[dict]:
    if payload.get("schema_version") != 1:
        raise ValueError("machine registry schema_version must be 1")
    records = payload.get("records") or []
    if len(records) != payload.get("verified_record_count"):
        raise ValueError("machine registry verified_record_count drift")
    if len(records) != payload.get("historical_version_checked_count"):
        raise ValueError("machine registry historical_version_checked_count drift")
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
            raise ValueError(f"adjudication may only consume Stage6 support cases: {k}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("historical_article_sha256") or "")):
            raise ValueError(f"invalid article fingerprint: {k}")
        if not row.get("stem_contains") or not row.get("answer_option_contains") or not row.get("article_contains"):
            raise ValueError(f"adjudication needs positive stem/option/article markers: {k}")
        if not isinstance(row.get("evidence_run_id"), int) or row["evidence_run_id"] <= 0:
            raise ValueError(f"invalid evidence run id: {k}")
        if not isinstance(row.get("evidence_artifact_id"), int) or row["evidence_artifact_id"] <= 0:
            raise ValueError(f"invalid evidence artifact id: {k}")
    return rows


def validate_evidence_snapshot(payload: dict) -> dict[tuple[str, str], dict]:
    if payload.get("schema_version") != 1:
        raise ValueError("evidence snapshot schema_version must be 1")
    rows = payload.get("records") or []
    if len(rows) != payload.get("record_count"):
        raise ValueError("evidence snapshot record_count drift")
    if not isinstance(payload.get("source_run_id"), int) or payload["source_run_id"] <= 0:
        raise ValueError("evidence snapshot source_run_id invalid")
    if not isinstance(payload.get("source_artifact_id"), int) or payload["source_artifact_id"] <= 0:
        raise ValueError("evidence snapshot source_artifact_id invalid")
    out = rows_by_key(payload, "evidence snapshot")
    for k, row in out.items():
        if row.get("stage4_status") != "historical_text_evidence_ready":
            raise ValueError(f"snapshot Stage4 status is not evidence-ready: {k}")
        if row.get("stage4_eligible") is not True:
            raise ValueError(f"snapshot Stage4 eligibility lost: {k}")
        if row.get("stage5_promotion_status") != "promotion_candidate":
            raise ValueError(f"snapshot Stage5 is no longer promotion_candidate: {k}")
        if row.get("stage6_status") != "historical_semantic_support":
            raise ValueError(f"snapshot must preserve Stage6 support/held state: {k}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("historical_article_sha256") or "")):
            raise ValueError(f"snapshot article fingerprint invalid: {k}")
        if not str(row.get("historical_article_text") or "").strip():
            raise ValueError(f"snapshot article text missing: {k}")
        require_https(
            (row.get("selected_version") or {}).get("url"),
            ("law.moj.gov.tw",),
            f"{k} snapshot selected version",
        )
        require_https(row.get("official_history_url"), ("law.moj.gov.tw",), f"{k} snapshot official_history_url")
        require_https(row.get("exam_date_source_url"), ("wwwc.moex.gov.tw",), f"{k} snapshot exam_date_source_url")
        if PROTECTED_CORE_FIELDS & set(row):
            raise ValueError(f"durable evidence snapshot contains protected Official Core: {k}")
    return out


def adjudicated_records(
    adjudication: dict,
    evidence_snapshot: dict,
    links: dict,
    questions: dict[str, dict],
) -> list[dict]:
    snapshot = validate_evidence_snapshot(evidence_snapshot)
    link_map = question_link_map(links)
    rows = validate_adjudication_payload(adjudication)
    confirmed: list[dict] = []

    source_run_id = evidence_snapshot["source_run_id"]
    source_artifact_id = evidence_snapshot["source_artifact_id"]

    for evidence in rows:
        k = key(evidence)
        qid = k[1]
        snap = snapshot.get(k)
        link = link_map.get(k)
        question = questions.get(qid)
        if not snap or not link or not question:
            raise ValueError(f"missing tracked evidence for adjudication: {k}")

        if evidence.get("evidence_run_id") != source_run_id:
            raise ValueError(f"evidence run id drift: {k}")
        if evidence.get("evidence_artifact_id") != source_artifact_id:
            raise ValueError(f"evidence artifact id drift: {k}")
        if str(snap.get("exam_code") or "") != str(evidence.get("exam_code") or ""):
            raise ValueError(f"snapshot exam code drift: {k}")

        article = str(evidence.get("article") or "")
        expected_hash = str(evidence.get("historical_article_sha256") or "")
        if str(snap.get("stage6_status") or "") != str(evidence.get("expected_stage6_status") or ""):
            raise ValueError(f"Stage6 status drift: {k}")
        if str(snap.get("stage6_decision_reason") or "") != str(evidence.get("expected_stage6_decision_reason") or ""):
            raise ValueError(f"Stage6 decision-reason drift: {k}")
        if str(snap.get("stage6_top_article") or "") != article:
            raise ValueError(f"Stage6 top-article drift: {k}")
        if str(snap.get("article") or "") != article:
            raise ValueError(f"snapshot article drift: {k}")
        if str(snap.get("historical_article_sha256") or "") != expected_hash:
            raise ValueError(f"historical article hash drift: {k}")

        version = compact_version(snap.get("selected_version"))
        require_https(version.get("url"), ("law.moj.gov.tw",), f"{k} selected version")
        history_url = require_https(snap.get("official_history_url"), ("law.moj.gov.tw",), f"{k} official_history_url")
        exam_date_url = require_https(snap.get("exam_date_source_url"), ("wwwc.moex.gov.tw",), f"{k} exam_date_source_url")

        law_text = str(snap.get("historical_article_text") or "")
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

        confirmed.append(
            {
                "law_name": k[0],
                "question_id": qid,
                "exam_code": evidence.get("exam_code"),
                "article": article,
                "historical_version_checked": True,
                "verification_level": ADJUDICATED_LEVEL,
                "verification_basis": (
                    "Evidence adjudication of a Stage6 historical_semantic_support case: "
                    "durable Stage2-6 official-law evidence snapshot + tracked official question/answer "
                    "+ selected answer-option markers."
                ),
                "selected_version": version,
                "historical_article_sha256": expected_hash,
                "historical_semantic": {
                    "top_article": snap.get("stage6_top_article"),
                    "top_score": snap.get("stage6_top_score"),
                    "second_article": snap.get("stage6_second_article"),
                    "second_score": snap.get("stage6_second_score"),
                    "margin": snap.get("stage6_margin"),
                    "decision_reason": snap.get("stage6_decision_reason"),
                    "status_before_adjudication": snap.get("stage6_status"),
                },
                "official_history_url": history_url,
                "exam_date_source_url": exam_date_url,
                "evidence_adjudication": {
                    "decision": "confirmed",
                    "method": ADJUDICATED_LEVEL,
                    "evidence_run_id": source_run_id,
                    "evidence_artifact_id": source_artifact_id,
                },
            }
        )

    return sorted(confirmed, key=key)


def build_combined_registry(
    machine_registry: dict,
    adjudication: dict,
    evidence_snapshot: dict,
    links: dict,
    questions: dict[str, dict],
) -> dict:
    machine = validate_machine_registry(machine_registry)
    adjudicated = adjudicated_records(adjudication, evidence_snapshot, links, questions)
    combined: dict[tuple[str, str], dict] = {}
    for row in machine + adjudicated:
        k = key(row)
        if k in combined:
            raise ValueError(f"machine/adjudicated verified-key conflict: {k}")
        if PROTECTED_CORE_FIELDS & set(row):
            raise ValueError(f"combined registry contains protected Official Core fields: {k}")
        combined[k] = row
    records = [combined[k] for k in sorted(combined)]
    counts = {
        MACHINE_LEVEL: sum(row.get("verification_level") == MACHINE_LEVEL for row in records),
        ADJUDICATED_LEVEL: sum(row.get("verification_level") == ADJUDICATED_LEVEL for row in records),
    }
    return {
        "schema_version": 1,
        "scope": "priority10 historical-law verified student-safe metadata overlay",
        "method": (
            "Union of the unchanged machine-only Stage7 registry and separately replayed evidence "
            "adjudications from a durable minimized official-law snapshot. Verification methods stay "
            "explicit; Official Core is not copied or modified."
        ),
        "verified_record_count": len(records),
        "historical_version_checked_count": sum(
            row.get("historical_version_checked") is True for row in records
        ),
        "verification_level_counts": counts,
        "records": records,
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adjudication", default=str(DEFAULT_ADJUDICATION))
    parser.add_argument("--machine-registry", default=str(DEFAULT_MACHINE))
    parser.add_argument("--evidence-snapshot", default=str(DEFAULT_EVIDENCE_SNAPSHOT))
    parser.add_argument("--links", default=str(DEFAULT_LINKS))
    parser.add_argument("--shards-dir", default=str(DEFAULT_SHARDS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    output = build_combined_registry(
        load_json(Path(args.machine_registry)),
        load_json(Path(args.adjudication)),
        load_json(Path(args.evidence_snapshot)),
        load_json(Path(args.links)),
        load_question_shards(Path(args.shards_dir)),
    )
    serialized = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    out_path = Path(args.output)
    if args.check:
        if not out_path.exists() or out_path.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "combined historical-law registry drift: regenerate with "
                "scripts/historical_law_evidence_adjudication.py"
            )
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(serialized, encoding="utf-8")

    print(
        json.dumps(
            {
                "verified_record_count": output["verified_record_count"],
                "machine_verified_count": output["verification_level_counts"][MACHINE_LEVEL],
                "evidence_adjudicated_count": output["verification_level_counts"][ADJUDICATED_LEVEL],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

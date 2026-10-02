#!/usr/bin/env python3
"""Build a deterministic bounded sample for high-risk explanation review.

This tool never mutates question data. It selects a stable cross-lane review
sample from the tracked official shards and records hashes so later reviewers
can prove that Official Core or explanation text did not silently change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SHARDS = ROOT / "cdn" / "question-shards"
MANIFEST = SHARDS / "manifest.json"
HISTORICAL = ROOT / "data" / "historical_law_verified_priority10.v1.json"
DEFAULT_OUTPUT = ROOT / "audit" / "high_risk_explanation_sample.v1.json"
SEED = "swsi-high-risk-explanation-sample-v1"
TARGET_PER_LANE = 5

NEGATIVE_PATTERNS = (
    "何者錯誤", "何者不正確", "何者不適當", "何者不宜", "何者不是",
    "不包括", "不包含", "不屬於", "錯誤的是", "不正確的是", "不適當的是",
)
NUMERIC_RE = re.compile(r"(?:\d+(?:\.\d+)?\s*(?:%|％|元|歲|年|月|日|人|次|分|小時|萬元|億元))")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def accepted_answers(row: dict[str, Any]) -> list[str]:
    raw = row.get("accepted_answers")
    if isinstance(raw, list):
        return [str(x).strip().upper() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip().upper() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            pass
        return [x.strip().upper() for x in re.split(r"[,/|\s]+", text) if x.strip()]
    return []


def official_core_hash(row: dict[str, Any]) -> str:
    payload = {
        "id": row.get("id"),
        "subject": row.get("subject"),
        "year": row.get("year"),
        "round": row.get("round"),
        "qno": row.get("qno"),
        "question": row.get("question") or row.get("q"),
        "opt_a": row.get("opt_a"),
        "opt_b": row.get("opt_b"),
        "opt_c": row.get("opt_c"),
        "opt_d": row.get("opt_d"),
        "answer": row.get("answer"),
        "accepted_answers": accepted_answers(row),
        "grading_mode": row.get("grading_mode") or "standard",
    }
    return sha256_text(payload)


def explanation_hash(row: dict[str, Any]) -> str:
    payload = {
        key: row.get(key)
        for key in ("exp_why", "exp_others", "exp_trap", "exp_raw", "mnemonic", "extension", "law", "mistake")
    }
    return sha256_text(payload)


def registry_id(question_id: str) -> str:
    match = re.fullmatch(r"([A-Z]+)-(\d{3})-(\d)-0*(\d+)", str(question_id or ""))
    if not match:
        return str(question_id or "")
    prefix, year, round_no, qno = match.groups()
    return f"{prefix}{year}-{round_no}-{int(qno)}"


def hash_rank(lane: str, row: dict[str, Any]) -> str:
    key = f"{SEED}|{lane}|{row.get('id','')}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def is_ready(row: dict[str, Any]) -> bool:
    return str(row.get("analysis_status") or "").lower() == "ready"


def is_legal(row: dict[str, Any]) -> bool:
    status = str(row.get("legal_status") or "").lower()
    return status not in ("", "not_applicable") or bool(str(row.get("law") or "").strip())


def is_negative(row: dict[str, Any]) -> bool:
    question = str(row.get("question") or row.get("q") or "")
    return any(marker in question for marker in NEGATIVE_PATTERNS)


def is_numeric(row: dict[str, Any]) -> bool:
    text = " ".join(str(row.get(key) or "") for key in ("question", "q", "exp_why", "exp_others", "law"))
    return bool(NUMERIC_RE.search(text))


def is_multi_answer(row: dict[str, Any]) -> bool:
    return len(accepted_answers(row)) > 1


def is_special_grading(row: dict[str, Any]) -> bool:
    return str(row.get("grading_mode") or "standard").lower() != "standard"


def load_corpus() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for shard in manifest.get("shards", []):
        path = SHARDS / shard["file"]
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != shard.get("sha256"):
            raise RuntimeError(f"shard checksum mismatch: {path.name}")
        payload = json.loads(raw)
        qrows = payload.get("questions", [])
        if len(qrows) != int(shard.get("question_count", -1)):
            raise RuntimeError(f"shard count mismatch: {path.name}")
        rows.extend(qrows)
    if len(rows) != int(manifest.get("total_questions", -1)):
        raise RuntimeError("manifest total_questions mismatch")
    ids = [str(row.get("id") or "") for row in rows]
    if len(set(ids)) != len(ids) or not all(ids):
        raise RuntimeError("question IDs are blank or duplicated")
    return manifest, rows


def compact_entry(row: dict[str, Any], lane: str, reason: str) -> dict[str, Any]:
    question = re.sub(r"\s+", " ", str(row.get("question") or row.get("q") or "")).strip()
    return {
        "lane": lane,
        "risk_reason": reason,
        "id": row.get("id"),
        "subject": row.get("subject"),
        "year": str(row.get("year") or ""),
        "round": row.get("round"),
        "qno": str(row.get("qno") or ""),
        "question_excerpt": question[:220],
        "answer": row.get("answer"),
        "accepted_answers": accepted_answers(row),
        "grading_mode": row.get("grading_mode") or "standard",
        "analysis_status": row.get("analysis_status"),
        "legal_status": row.get("legal_status"),
        "source_exam_code": row.get("source_exam_code"),
        "source_url": row.get("source_url"),
        "legal_source_url": row.get("legal_source_url"),
        "official_core_sha256": official_core_hash(row),
        "explanation_sha256": explanation_hash(row),
        "selection_sha256": hash_rank(lane, row),
        "review_state": "pending_source_review",
    }


def build_sample() -> dict[str, Any]:
    manifest, rows = load_corpus()
    historical_payload = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    historical = {
        str(rec.get("question_id")): rec
        for rec in historical_payload.get("records", [])
        if rec.get("historical_version_checked") is True
        and rec.get("verification_level") == "machine_verified_historical_v1"
    }

    lanes: list[tuple[str, Callable[[dict[str, Any]], bool], str]] = [
        ("special_grading", is_special_grading, "special grading semantics must stay isolated from ordinary semantic analysis"),
        ("multi_answer", is_multi_answer, "multiple accepted answers require exact accepted-set and explanation consistency"),
        ("historical_law", lambda r: registry_id(str(r.get("id") or "")) in historical, "exam-time law version has official historical provenance metadata"),
        ("legal_ready", lambda r: is_ready(r) and is_legal(r), "ready explanation contains legal/policy content and needs source/date scrutiny"),
        ("negative_ready", lambda r: is_ready(r) and is_negative(r), "negative wording can invert otherwise plausible explanation logic"),
        ("numeric_ready", lambda r: is_ready(r) and is_numeric(r), "numbers/dates/amounts are high-risk factual details"),
    ]

    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    lane_counts: dict[str, int] = {}
    candidate_counts: dict[str, int] = {}

    for lane, predicate, reason in lanes:
        candidates = [row for row in rows if predicate(row)]
        candidate_counts[lane] = len(candidates)
        candidates.sort(key=lambda row: (hash_rank(lane, row), str(row.get("id") or "")))
        picks = []
        for row in candidates:
            qid = str(row.get("id") or "")
            if qid in used:
                continue
            picks.append(row)
            used.add(qid)
            if len(picks) >= TARGET_PER_LANE:
                break
        if len(picks) < TARGET_PER_LANE:
            raise RuntimeError(f"lane {lane} has only {len(picks)} unique picks; need {TARGET_PER_LANE}")
        lane_counts[lane] = len(picks)
        selected.extend(compact_entry(row, lane, reason) for row in picks)

    return {
        "schema_version": 1,
        "purpose": "bounded deterministic high-risk explanation/source review sample; no question mutation",
        "seed": SEED,
        "dataset_revision": manifest.get("dataset_revision"),
        "manifest_generated_at": manifest.get("generated_at"),
        "source_total_questions": manifest.get("total_questions"),
        "source_shard_count": manifest.get("shard_count"),
        "target_per_lane": TARGET_PER_LANE,
        "candidate_counts": candidate_counts,
        "lane_counts": lane_counts,
        "sample_count": len(selected),
        "review_policy": {
            "official_core": "must remain byte-semantic equivalent; sample records pin SHA-256",
            "platform_explanation": "review source support, date/law applicability, negative wording, number accuracy and accepted-answer consistency",
            "machine_verified_historical": "metadata evidence is strong provenance, not an official explanation and not blanket corpus verification",
            "review_state": "pending_source_review until a separate evidence-backed review records the outcome",
        },
        "sample": selected,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    result = build_sample()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output

    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            raise SystemExit("HIGH-RISK SAMPLE DRIFT: regenerate audit/high_risk_explanation_sample.v1.json")
        print(f"HIGH-RISK SAMPLE OK count={result['sample_count']} lanes={result['lane_counts']}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output.relative_to(ROOT)} count={result['sample_count']} lanes={result['lane_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

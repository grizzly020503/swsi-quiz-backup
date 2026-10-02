#!/usr/bin/env python3
"""Versioned examination-scheme contract for SWSI official intake.

This module deliberately separates two questions:

1. Does an observed official payload match an already approved scheme profile?
2. If it does not, what structural difference was observed?

It NEVER auto-approves a new scheme. A mismatch is returned as a candidate
change that callers must quarantine before publishing/importing.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "data" / "exam_scheme_registry.v1.json"
ROUND_ORDER = {"第一次": 1, "第二次": 2}


class ExamSchemeError(RuntimeError):
    pass


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_round(value: Any, registry: dict) -> str:
    raw = str(value or "").strip()
    return str((registry.get("round_aliases") or {}).get(raw, raw))


def session_key(year: Any, round_name: Any, registry: dict) -> tuple[int, int]:
    year_text = str(year or "").strip()
    normalized_round = normalize_round(round_name, registry)
    if not year_text.isdigit() or normalized_round not in ROUND_ORDER:
        raise ExamSchemeError(
            f"invalid exam session metadata: year={year_text!r}, round={round_name!r}"
        )
    return int(year_text), ROUND_ORDER[normalized_round]


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict:
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ExamSchemeError(f"{path}: expected schema_version=1 object")
    if not str(raw.get("exam_type") or "").strip():
        raise ExamSchemeError(f"{path}: exam_type missing")
    profiles = raw.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ExamSchemeError(f"{path}: profiles must be a non-empty list")

    ids: set[str] = set()
    for index, profile in enumerate(profiles):
        if not isinstance(profile, dict):
            raise ExamSchemeError(f"{path}: profile {index} is not an object")
        ident = str(profile.get("id") or "").strip()
        if not ident or ident in ids:
            raise ExamSchemeError(f"{path}: profile id missing/duplicated: {ident!r}")
        ids.add(ident)
        if profile.get("status") != "approved":
            raise ExamSchemeError(f"{path}: executable profile {ident} must be approved")

        subjects = profile.get("subjects")
        if not isinstance(subjects, list) or not subjects:
            raise ExamSchemeError(f"{path}: {ident}.subjects must be a non-empty list")
        names = [str(x.get("name") or "").strip() for x in subjects if isinstance(x, dict)]
        codes = [str(x.get("code") or "").strip() for x in subjects if isinstance(x, dict)]
        prefixes = [str(x.get("prefix") or "").strip() for x in subjects if isinstance(x, dict)]
        if len(names) != len(subjects) or any(not x for x in names + codes + prefixes):
            raise ExamSchemeError(f"{path}: {ident}.subjects has incomplete entries")
        if len(set(names)) != len(names) or len(set(codes)) != len(codes) or len(set(prefixes)) != len(prefixes):
            raise ExamSchemeError(f"{path}: {ident}.subjects names/codes/prefixes must be unique")

        start = profile.get("effective_from") or {}
        session_key(start.get("roc_year"), start.get("round"), raw)
        end = profile.get("effective_to")
        if end is not None:
            if session_key(end.get("roc_year"), end.get("round"), raw) < session_key(
                start.get("roc_year"), start.get("round"), raw
            ):
                raise ExamSchemeError(f"{path}: {ident}.effective_to precedes effective_from")

        mcq = profile.get("mcq") or {}
        essay = profile.get("essay") or {}
        for cfg_name, cfg in (("mcq", mcq), ("essay", essay)):
            for field in ("per_subject", "expected_total", "qno_min", "qno_max"):
                try:
                    value = int(cfg[field])
                except Exception as exc:
                    raise ExamSchemeError(f"{path}: {ident}.{cfg_name}.{field} invalid") from exc
                if value < 0:
                    raise ExamSchemeError(f"{path}: {ident}.{cfg_name}.{field} must be >= 0")
        if int(mcq["expected_total"]) != int(mcq["per_subject"]) * len(subjects):
            raise ExamSchemeError(f"{path}: {ident}.mcq total does not match subjects × per_subject")
        if int(essay["expected_total"]) != int(essay["per_subject"]) * len(subjects):
            raise ExamSchemeError(f"{path}: {ident}.essay total does not match subjects × per_subject")
    return raw


def resolve_profile(registry: dict, year: Any, round_name: Any) -> dict | None:
    target = session_key(year, round_name, registry)
    candidates: list[tuple[tuple[int, int], dict]] = []
    for profile in registry.get("profiles") or []:
        start_raw = profile.get("effective_from") or {}
        start = session_key(start_raw.get("roc_year"), start_raw.get("round"), registry)
        end_raw = profile.get("effective_to")
        end = (
            session_key(end_raw.get("roc_year"), end_raw.get("round"), registry)
            if isinstance(end_raw, dict)
            else None
        )
        if start <= target and (end is None or target <= end):
            candidates.append((start, profile))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    return deepcopy(candidates[-1][1])


def profile_subject_names(profile: dict) -> list[str]:
    return [str(row["name"]) for row in profile.get("subjects") or []]


def expected_shape(profile: dict) -> dict:
    subjects = profile_subject_names(profile)
    mcq = profile["mcq"]
    essay = profile["essay"]
    return {
        "profile_id": profile["id"],
        "subjects": subjects,
        "mcq_total": int(mcq["expected_total"]),
        "mcq_per_subject": int(mcq["per_subject"]),
        "mcq_qno_min": int(mcq["qno_min"]),
        "mcq_qno_max": int(mcq["qno_max"]),
        "essay_required": bool(essay.get("required", True)),
        "essay_total": int(essay["expected_total"]),
        "essay_per_subject": int(essay["per_subject"]),
        "essay_qno_min": int(essay["qno_min"]),
        "essay_qno_max": int(essay["qno_max"]),
    }


def _qno(value: Any) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def observed_shape(payload: dict) -> dict:
    questions = payload.get("questions") or []
    essays = payload.get("essays") or []
    q_counts = Counter(str(row.get("subject") or "").strip() for row in questions)
    e_counts = Counter(str(row.get("subject") or "").strip() for row in essays)
    q_qnos: dict[str, set[int]] = defaultdict(set)
    e_qnos: dict[str, set[int]] = defaultdict(set)
    for row in questions:
        n = _qno(row.get("qno"))
        if n is not None:
            q_qnos[str(row.get("subject") or "").strip()].add(n)
    for row in essays:
        n = _qno(row.get("qno"))
        if n is not None:
            e_qnos[str(row.get("subject") or "").strip()].add(n)

    grading_modes = Counter(
        str(row.get("grading_mode") or "legacy_unspecified").strip() or "legacy_unspecified"
        for row in questions
    )
    return {
        "mcq_total": len(questions),
        "essay_total": len(essays),
        "mcq_by_subject": dict(sorted(q_counts.items())),
        "essay_by_subject": dict(sorted(e_counts.items())),
        "mcq_qnos": {k: sorted(v) for k, v in sorted(q_qnos.items())},
        "essay_qnos": {k: sorted(v) for k, v in sorted(e_qnos.items())},
        "grading_modes": dict(sorted(grading_modes.items())),
    }


def _add_diff(diffs: list[dict], field: str, expected: Any, observed: Any) -> None:
    if expected != observed:
        diffs.append({"field": field, "expected": expected, "observed": observed})


def compare_payload(payload: dict, registry: dict | None = None) -> dict:
    registry = registry or load_registry()
    if not isinstance(payload, dict):
        raise ExamSchemeError("exam payload must be an object")

    year = str(payload.get("roc_year") or "").strip()
    round_name = normalize_round(payload.get("round"), registry)
    exam_code = str(payload.get("exam_code") or "").strip()
    identity_issues: list[dict] = []

    try:
        session_key(year, round_name, registry)
    except ExamSchemeError as exc:
        return {
            "status": "invalid_identity",
            "approved": False,
            "exam_code": exam_code,
            "roc_year": year,
            "round": round_name,
            "profile_id": None,
            "identity_issues": [{"field": "session", "message": str(exc)}],
            "diffs": [],
            "expected": None,
            "observed": observed_shape(payload),
            "candidate_profile": None,
            "requires_maintainer_decision": True,
        }

    profile = resolve_profile(registry, year, round_name)
    if profile is None:
        return {
            "status": "unapproved_scheme",
            "approved": False,
            "exam_code": exam_code,
            "roc_year": year,
            "round": round_name,
            "profile_id": None,
            "identity_issues": [],
            "diffs": [],
            "expected": None,
            "observed": observed_shape(payload),
            "candidate_profile": _candidate_from_observation(payload, registry),
            "requires_maintainer_decision": True,
        }

    expected = expected_shape(profile)
    if str(payload.get("exam_type") or "").strip() != str(registry["exam_type"]):
        identity_issues.append(
            {
                "field": "exam_type",
                "expected": registry["exam_type"],
                "observed": payload.get("exam_type"),
            }
        )
    if exam_code:
        if len(exam_code) != 6 or not exam_code.isdigit():
            identity_issues.append({"field": "exam_code", "message": "expected six digits", "observed": exam_code})
        else:
            _add_diff(identity_issues, "exam_code.roc_year", year, exam_code[:3])
            suffixes = profile.get("exam_code_suffixes") or {}
            expected_suffix = str(suffixes.get(round_name) or "")
            if expected_suffix:
                _add_diff(identity_issues, "exam_code.round_suffix", expected_suffix, exam_code[3:])
    else:
        identity_issues.append({"field": "exam_code", "message": "missing"})

    questions = payload.get("questions")
    essays = payload.get("essays")
    if not isinstance(questions, list):
        identity_issues.append({"field": "questions", "message": "must be a list"})
        questions = []
    if not isinstance(essays, list):
        identity_issues.append({"field": "essays", "message": "must be a list"})
        essays = []

    for kind, rows in (("questions", questions), ("essays", essays)):
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                identity_issues.append({"field": f"{kind}[{index}]", "message": "must be an object"})
                continue
            row_year = str(row.get("year") or "").strip()
            row_round = normalize_round(row.get("round"), registry)
            row_code = str(row.get("source_exam_code") or "").strip()
            if row_year != year:
                identity_issues.append(
                    {"field": f"{kind}[{index}].year", "expected": year, "observed": row_year}
                )
            if row_round != round_name:
                identity_issues.append(
                    {"field": f"{kind}[{index}].round", "expected": round_name, "observed": row_round}
                )
            if row_code and row_code != exam_code:
                identity_issues.append(
                    {"field": f"{kind}[{index}].source_exam_code", "expected": exam_code, "observed": row_code}
                )

    observed = observed_shape({**payload, "questions": questions, "essays": essays})
    diffs: list[dict] = []
    _add_diff(diffs, "mcq.total", expected["mcq_total"], observed["mcq_total"])
    _add_diff(diffs, "essay.total", expected["essay_total"], observed["essay_total"])

    expected_subjects = expected["subjects"]
    observed_mcq_subjects = sorted(observed["mcq_by_subject"])
    observed_essay_subjects = sorted(observed["essay_by_subject"])
    _add_diff(diffs, "mcq.subjects", sorted(expected_subjects), observed_mcq_subjects)
    if expected["essay_required"] or observed["essay_total"]:
        _add_diff(diffs, "essay.subjects", sorted(expected_subjects), observed_essay_subjects)

    expected_mcq_qnos = list(range(expected["mcq_qno_min"], expected["mcq_qno_max"] + 1))
    expected_essay_qnos = list(range(expected["essay_qno_min"], expected["essay_qno_max"] + 1))
    for subject in expected_subjects:
        _add_diff(
            diffs,
            f"mcq.by_subject.{subject}",
            expected["mcq_per_subject"],
            observed["mcq_by_subject"].get(subject, 0),
        )
        _add_diff(
            diffs,
            f"mcq.qnos.{subject}",
            expected_mcq_qnos,
            observed["mcq_qnos"].get(subject, []),
        )
        _add_diff(
            diffs,
            f"essay.by_subject.{subject}",
            expected["essay_per_subject"],
            observed["essay_by_subject"].get(subject, 0),
        )
        _add_diff(
            diffs,
            f"essay.qnos.{subject}",
            expected_essay_qnos,
            observed["essay_qnos"].get(subject, []),
        )

    if identity_issues:
        status = "invalid_identity"
    elif diffs:
        status = "candidate_change"
    else:
        status = "match"
    return {
        "status": status,
        "approved": status == "match",
        "exam_code": exam_code,
        "roc_year": year,
        "round": round_name,
        "profile_id": profile["id"],
        "identity_issues": identity_issues,
        "diffs": diffs,
        "expected": expected,
        "observed": observed,
        "candidate_profile": _candidate_from_observation(payload, registry) if diffs else None,
        "requires_maintainer_decision": status != "match",
    }


def _candidate_from_observation(payload: dict, registry: dict) -> dict:
    observed = observed_shape(payload)
    subjects = sorted(set(observed["mcq_by_subject"]) | set(observed["essay_by_subject"]))
    return {
        "candidate_only": True,
        "auto_approved": False,
        "effective_from": {
            "roc_year": str(payload.get("roc_year") or "").strip(),
            "round": normalize_round(payload.get("round"), registry),
        },
        "observed_subjects": [
            {
                "name": subject,
                "mcq_count": observed["mcq_by_subject"].get(subject, 0),
                "essay_count": observed["essay_by_subject"].get(subject, 0),
            }
            for subject in subjects
        ],
        "observed_mcq_total": observed["mcq_total"],
        "observed_essay_total": observed["essay_total"],
        "note": "Observation only. Subject codes/prefixes and official rule changes must be verified before creating an approved executable profile.",
    }


def require_approved_payload(payload: dict, registry: dict | None = None, source: str = "payload") -> dict:
    result = compare_payload(payload, registry)
    if result["status"] != "match":
        compact = json.dumps(
            {
                "source": source,
                "status": result["status"],
                "profile_id": result["profile_id"],
                "identity_issues": result["identity_issues"],
                "diffs": result["diffs"],
                "candidate_profile": result["candidate_profile"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        raise ExamSchemeError(
            "exam scheme gate refused payload; keep it quarantined until the structure is verified: "
            + compact
        )
    return result

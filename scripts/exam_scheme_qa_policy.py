#!/usr/bin/env python3
"""Derive current-intake QA expectations from the approved exam-scheme registry.

The legacy question QA policy still owns risk/enrichment/grading semantics. This
module replaces only structural intake fields (subjects/counts/qno ranges and
answer letters) with the profile approved for the requested session.

Historical fixtures are not rewritten. If a future reform is approved as a new
profile with an effective date, the same caller automatically receives the new
structural expectations for sessions covered by that profile.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from exam_scheme import (
    DEFAULT_REGISTRY,
    ExamSchemeError,
    load_registry,
    normalize_round,
    resolve_profile,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_POLICY = ROOT / "data" / "question_qa_policy_v1.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def derive_qa_policy(
    base_policy: dict[str, Any],
    registry: dict[str, Any],
    year: Any,
    round_name: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (effective_policy, provenance) for one approved session."""
    normalized_round = normalize_round(round_name, registry)
    profile = resolve_profile(registry, year, normalized_round)
    if profile is None:
        raise ExamSchemeError(
            f"no approved exam-scheme profile covers year={year!r} round={round_name!r}"
        )

    policy = deepcopy(base_policy)
    subjects = [str(row["name"]) for row in profile.get("subjects") or []]
    if not subjects:
        raise ExamSchemeError(f"approved profile {profile.get('id')!r} has no subjects")

    mcq_profile = profile.get("mcq") or {}
    essay_profile = profile.get("essay") or {}
    policy["subjects"] = subjects
    # Use the registry aliases for session identity while retaining any legacy
    # aliases that are not in conflict.
    aliases = dict(policy.get("round_aliases") or {})
    aliases.update(registry.get("round_aliases") or {})
    policy["round_aliases"] = aliases

    mcq = dict(policy.get("mcq") or {})
    mcq.update(
        {
            "expected_total": int(mcq_profile["expected_total"]),
            "expected_per_subject": int(mcq_profile["per_subject"]),
            "qno_min": int(mcq_profile["qno_min"]),
            "qno_max": int(mcq_profile["qno_max"]),
        }
    )
    option_letters = mcq_profile.get("option_letters")
    if isinstance(option_letters, list) and option_letters:
        mcq["valid_answer_letters"] = [str(x) for x in option_letters]
    policy["mcq"] = mcq

    essay = dict(policy.get("essay") or {})
    essay.update(
        {
            "expected_total": int(essay_profile["expected_total"]),
            "expected_per_subject": int(essay_profile["per_subject"]),
            "qno_min": int(essay_profile["qno_min"]),
            "qno_max": int(essay_profile["qno_max"]),
            "required": bool(essay_profile.get("required", True)),
        }
    )
    policy["essay"] = essay

    provenance = {
        "registry_schema_version": int(registry.get("schema_version") or 0),
        "profile_id": str(profile["id"]),
        "roc_year": str(year).strip(),
        "round": normalized_round,
        "subject_count": len(subjects),
        "mcq_total": mcq["expected_total"],
        "essay_total": essay["expected_total"],
        "expected_total_items": mcq["expected_total"] + essay["expected_total"],
        "structural_source": "data/exam_scheme_registry.v1.json",
        "base_semantic_policy": "data/question_qa_policy_v1.json",
    }
    policy["exam_scheme"] = provenance
    return policy, provenance


def derive_from_paths(
    year: Any,
    round_name: Any,
    *,
    base_policy_path: Path = DEFAULT_BASE_POLICY,
    registry_path: Path = DEFAULT_REGISTRY,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base_policy = read_json(base_policy_path)
    registry = load_registry(registry_path)
    return derive_qa_policy(base_policy, registry, year, round_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive Unified QA structural policy from approved exam scheme")
    parser.add_argument("--year", required=True)
    parser.add_argument("--round", required=True)
    parser.add_argument("--base-policy", type=Path, default=DEFAULT_BASE_POLICY)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    try:
        policy, provenance = derive_from_paths(
            args.year,
            args.round,
            base_policy_path=args.base_policy,
            registry_path=args.registry,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, ExamSchemeError) as exc:
        raise SystemExit(f"cannot derive approved QA policy: {exc}") from exc

    rendered = json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    print(
        "EXAM SCHEME QA POLICY OK "
        f"profile={provenance['profile_id']} items={provenance['expected_total_items']}",
        file=__import__("sys").stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail closed when the student law-priority data or UI contract drifts."""
from __future__ import annotations

import json
import re
from pathlib import Path

from build_law_study_priority import DEFAULT_SOURCE, build_snapshot

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "auto" / "law_study_priority.json"
UI = ROOT / "monthly_patch_parts" / "80.knowledge-path.part"
TRUST_UI = ROOT / "monthly_patch_parts" / "86.law-trust-ui.part"


def fail(message: str) -> None:
    raise SystemExit("LAW STUDY PRIORITY SMOKE FAILED: " + message)


def main() -> int:
    expected = build_snapshot(DEFAULT_SOURCE)
    if not SNAPSHOT.exists():
        fail("missing auto/law_study_priority.json")
    actual = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if actual != expected:
        fail("committed snapshot differs from deterministic source derivation")

    source = json.loads(DEFAULT_SOURCE.read_text(encoding="utf-8"))
    method = str(source.get("method") or "")
    if "Exact law metadata name or explicit alias only" not in method or "No keyword-only stem match" not in method:
        fail("source linkage method no longer guarantees explicit metadata/alias matching")

    cards = source.get("cards") or []
    if len(cards) != actual["scope"]["priority_law_count"]:
        fail("priority law count mismatch")

    seen_names: set[str] = set()
    pair_count = 0
    global_ids: set[str] = set()
    recent_start = int(actual["scope"]["recent_start_year"])
    recent_end = int(actual["scope"]["recent_end_year"])

    for law in actual.get("laws") or []:
        name = str(law.get("law_name") or "")
        if not name or name in seen_names:
            fail("law names must be non-empty and unique")
        seen_names.add(name)

        ids = list(law.get("question_ids") or [])
        recent_ids = list(law.get("recent_question_ids") or [])
        if len(ids) != len(set(ids)):
            fail(f"{name}: duplicate question IDs would inflate counts")
        if len(recent_ids) != len(set(recent_ids)):
            fail(f"{name}: duplicate recent question IDs would inflate counts")
        if not set(recent_ids).issubset(set(ids)):
            fail(f"{name}: recent IDs must be a subset of all linked IDs")
        if int(law.get("all_linked_question_count", -1)) != len(ids):
            fail(f"{name}: all-history count does not match unique IDs")
        if int(law.get("recent_five_year_question_count", -1)) != len(recent_ids):
            fail(f"{name}: recent-five-year count does not match unique IDs")

        pair_count += len(ids)
        global_ids.update(ids)

    if pair_count != int(actual["scope"]["linked_law_question_pairs"]):
        fail("linked pair total mismatch")
    if len(global_ids) != int(actual["scope"]["unique_linked_questions"]):
        fail("unique linked-question total mismatch")
    if recent_end - recent_start != 4:
        fail("recent window must remain exactly five exam years")

    boundary = str(actual.get("student_boundary") or "")
    for phrase in ("不是關鍵字命中", "不是命題機率", "不代表每題歷史法規版本已核實"):
        if phrase not in boundary:
            fail("student-facing scope boundary lost: " + phrase)

    if not UI.exists() or not TRUST_UI.exists():
        fail("missing canonical knowledge-path or law-trust runtime owner")
    ui = UI.read_text(encoding="utf-8")
    trust_ui = TRUST_UI.read_text(encoding="utf-8")

    knowledge_owners = re.findall(r"\brenderLaws\s*=\s*function\b", ui)
    trust_owners = re.findall(r"\brenderLaws\s*=\s*function\b", trust_ui)
    if len(knowledge_owners) != 1:
        fail(f"knowledge path must keep exactly one renderLaws owner; found {len(knowledge_owners)}")
    if len(trust_owners) != 1:
        fail(f"law trust must keep exactly one renderLaws wrapper; found {len(trust_owners)}")

    for marker in (
        "auto/law_study_priority.json",
        "swsi-law-study-priority",
        "歷屆題目足跡",
        "查看全部可追溯題號",
        "decorateLawStudyPriority",
    ):
        if marker not in ui:
            fail("knowledge-path UI contract lost marker: " + marker)
    if "fetch(LAW_STUDY_PRIORITY_URL" not in ui:
        fail("knowledge path must load the traceable snapshot rather than duplicate study counts")
    if "window.SWSI_LAW_STUDY_PRIORITY" in ui or "window.SWSI_LAW_STUDY_PRIORITY" in trust_ui:
        fail("law study priority must not add a new direct window global")
    if "auto/law_study_priority.json" in trust_ui or "swsi-law-study-priority" in trust_ui:
        fail("law trust owner must remain separate from student study-priority UI")
    if "fetch(" in trust_ui:
        fail("law trust owner must preserve historical-law no-network boundary")
    if "不代表未來不會考" not in ui:
        fail("zero-recent-count copy must not imply zero future relevance")

    print(
        "LAW STUDY PRIORITY SMOKE OK: "
        f"laws={len(seen_names)} pairs={pair_count} unique_questions={len(global_ids)} "
        f"recent={recent_start}-{recent_end} owner_chain=80->86 no_new_global=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

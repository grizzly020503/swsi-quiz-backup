#!/usr/bin/env python3
"""Build exam-session question shards from the production Supabase read-only API.

This script does NOT deploy anything. It only writes a manifest + JSON shards.
Source of truth is the public read-only `questions` table in Supabase.

The historical baseline (ROC 104–115, two sessions per year) must always remain
complete. Future sessions such as 116-1 / 116-2 are discovered automatically once
a complete 200-question exam session exists in Supabase, so no annual code edit
is required.

Default layout:
  cdn/question-shards/manifest.json
  cdn/question-shards/104-1.json
  ...
  cdn/question-shards/115-2.json
  cdn/question-shards/116-1.json   # appears automatically in the future

The shard rows intentionally stay close to the current DB shape so the existing
frontend `normalize(r)` can keep doing legacy explanation normalization. The only
new answer metadata required by the future frontend is `accepted_answers`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
BASELINE_YEARS = [str(y) for y in range(104, 116)]
VALID_ROUNDS = ["第一次", "第二次"]
ROUND_ORDER = {name: i for i, name in enumerate(VALID_ROUNDS)}
EXPECTED_SUBJECTS = {
    "社會工作",
    "社會工作直接服務",
    "社會政策與社會立法",
    "人類行為與社會環境",
    "社會工作研究方法",
}
BASELINE_GROUPS = {(y, r) for y in BASELINE_YEARS for r in VALID_ROUNDS}
BASELINE_QUESTIONS = len(BASELINE_GROUPS) * 200

# Keep only fields needed by the current frontend normalizer / future CDN loader.
SELECT_FIELDS = [
    "id", "subject", "year", "round", "qno",
    "major", "topic", "keywords",
    "question", "opt_a", "opt_b", "opt_c", "opt_d",
    "answer", "accepted_answers",
    "exp_why", "exp_others", "exp_trap", "exp_raw",
    "mnemonic", "extension", "law", "mistake",
    "source_exam_code",
    "analysis_status",
    "legal_status", "legal_checked_at", "legal_note", "legal_source_url",
]


def frontend_config() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
    if url and key:
        return url, key

    text = INDEX.read_text(encoding="utf-8")
    um = re.search(r'url:\s*"(https://[^\"]+\.supabase\.co)"', text)
    km = re.search(r'key:\s*"(eyJ[^\"]+)"', text)
    if not um or not km:
        raise RuntimeError("Cannot locate Supabase public URL/key in env or index.html")
    return um.group(1).rstrip("/"), km.group(1)


def fetch_questions() -> list[dict]:
    base, key = frontend_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": "swsi-question-shard-builder/1.1",
    }
    rows: list[dict] = []
    offset = 0
    page = 1000
    select = ",".join(SELECT_FIELDS)

    while True:
        r = requests.get(
            f"{base}/rest/v1/questions",
            headers=headers,
            params={
                "select": select,
                "order": "year.asc,round.asc,subject.asc,qno.asc,id.asc",
                "offset": str(offset),
                "limit": str(page),
            },
            timeout=60,
        )
        r.raise_for_status()
        batch = r.json()
        if not isinstance(batch, list):
            raise RuntimeError("Supabase questions response is not a list")
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += len(batch)

    return rows


def qno_int(row: dict) -> int:
    raw = str(row.get("qno") or "").strip()
    if not raw.isdigit():
        raise RuntimeError(f"Non-numeric qno: {row.get('id')} -> {raw!r}")
    return int(raw)


def validate(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    if len(rows) < BASELINE_QUESTIONS:
        raise RuntimeError(
            f"Historical baseline requires at least {BASELINE_QUESTIONS} questions, got {len(rows)}"
        )

    ids = [str(r.get("id") or "") for r in rows]
    if len(set(ids)) != len(rows) or any(not x for x in ids):
        raise RuntimeError("Question IDs are missing or duplicated")

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        year = str(r.get("year") or "").strip()
        round_name = str(r.get("round") or "").strip()
        subject = str(r.get("subject") or "").strip()

        if not year.isdigit() or int(year) < 104:
            raise RuntimeError(f"Unexpected year {year!r}: {r.get('id')}")
        if round_name not in VALID_ROUNDS:
            raise RuntimeError(f"Unexpected round {round_name}: {r.get('id')}")
        if subject not in EXPECTED_SUBJECTS:
            raise RuntimeError(f"Unexpected subject {subject}: {r.get('id')}")
        if str(r.get("answer") or "") not in {"A", "B", "C", "D", "一律給分"}:
            raise RuntimeError(f"Invalid answer: {r.get('id')} -> {r.get('answer')}")

        accepted = r.get("accepted_answers")
        if accepted is not None:
            if not isinstance(accepted, list) or not accepted:
                raise RuntimeError(f"Invalid accepted_answers shape: {r.get('id')}")
            if len(set(accepted)) != len(accepted):
                raise RuntimeError(f"Duplicate accepted_answers: {r.get('id')}")
            if any(x not in {"A", "B", "C", "D"} for x in accepted):
                raise RuntimeError(f"Invalid accepted answer letter: {r.get('id')}")
            if r.get("answer") not in accepted:
                raise RuntimeError(f"Primary answer not in accepted_answers: {r.get('id')}")

        grouped[(year, round_name)].append(r)

    missing_baseline = sorted(
        BASELINE_GROUPS - set(grouped),
        key=lambda x: (int(x[0]), ROUND_ORDER[x[1]]),
    )
    if missing_baseline:
        raise RuntimeError(f"Historical baseline exam groups missing: {missing_baseline}")

    for key, group in grouped.items():
        if len(group) != 200:
            # Fail closed while a newly synced exam is incomplete. The currently
            # published CDN remains untouched and the next scheduled run retries.
            raise RuntimeError(f"{key}: expected complete 200-question session, got {len(group)}")

        counts = Counter(str(r["subject"]) for r in group)
        if set(counts) != EXPECTED_SUBJECTS or any(v != 40 for v in counts.values()):
            raise RuntimeError(f"{key}: subject distribution invalid: {dict(counts)}")

        by_subject: dict[str, set[int]] = defaultdict(set)
        for r in group:
            by_subject[str(r["subject"])].add(qno_int(r))
        for subject, nums in by_subject.items():
            if nums != set(range(1, 41)):
                raise RuntimeError(f"{key} {subject}: qno set is not 1..40")

    expected_total = len(grouped) * 200
    if len(rows) != expected_total:
        raise RuntimeError(
            f"Question total {len(rows)} does not match {len(grouped)} complete sessions ({expected_total})"
        )

    return grouped


def stable_json_bytes(data: object) -> bytes:
    return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def build(
    rows: list[dict],
    grouped: dict[tuple[str, str], list[dict]],
    outdir: Path,
) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)

    # Keep direct/local runs deterministic too; stale future shards should not
    # survive if the source dataset is intentionally rolled back.
    for old_json in outdir.glob("*.json"):
        old_json.unlink()

    manifest_rows = []
    shard_hashes = []
    total_bytes = 0
    group_keys = sorted(grouped, key=lambda x: (int(x[0]), ROUND_ORDER[x[1]]))

    for year, round_name in group_keys:
        round_no = 1 if round_name == "第一次" else 2
        group = grouped[(year, round_name)]
        group.sort(key=lambda r: (str(r["subject"]), qno_int(r), str(r["id"])))
        filename = f"{year}-{round_no}.json"
        payload = {
            "schema_version": 1,
            "year": year,
            "round": round_name,
            "question_count": len(group),
            "questions": group,
        }
        raw = stable_json_bytes(payload)
        digest = hashlib.sha256(raw).hexdigest()
        (outdir / filename).write_bytes(raw)
        total_bytes += len(raw)
        shard_hashes.append(f"{filename}:{digest}")
        manifest_rows.append({
            "year": year,
            "round": round_name,
            "file": filename,
            "question_count": len(group),
            "bytes": len(raw),
            "sha256": digest,
        })

    revision = hashlib.sha256("\n".join(shard_hashes).encode("utf-8")).hexdigest()[:20]
    manifest = {
        "schema_version": 1,
        "dataset_revision": revision,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "Supabase public.questions (read-only)",
        "total_questions": len(rows),
        "shard_count": len(manifest_rows),
        "baseline_shard_count": len(BASELINE_GROUPS),
        "total_uncompressed_bytes": total_bytes,
        "shards": manifest_rows,
    }
    (outdir / "manifest.json").write_bytes(stable_json_bytes(manifest))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Build SWSI exam-session question-bank JSON shards")
    ap.add_argument("--output-dir", default="cdn/question-shards")
    args = ap.parse_args()

    rows = fetch_questions()
    grouped = validate(rows)
    manifest = build(rows, grouped, Path(args.output_dir))

    multi = sum(1 for r in rows if r.get("accepted_answers"))
    all_give = sum(1 for r in rows if r.get("answer") == "一律給分")
    sizes = [int(x["bytes"]) for x in manifest["shards"]]
    print(
        json.dumps(
            {
                "questions": len(rows),
                "shards": manifest["shard_count"],
                "baseline_shards": manifest["baseline_shard_count"],
                "multi_answer_rows": multi,
                "all_give_rows": all_give,
                "revision": manifest["dataset_revision"],
                "total_bytes": manifest["total_uncompressed_bytes"],
                "min_shard_bytes": min(sizes),
                "max_shard_bytes": max(sizes),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

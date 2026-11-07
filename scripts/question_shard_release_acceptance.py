#!/usr/bin/env python3
"""Fail-closed student CDN shard release proof; no credentials or write requests.

The immutable 104-115 baseline remains mandatory. Future approved sessions are
accepted additively and checked against their actual manifest, not 4800/24.
--selftest is synthetic and offline. --live fetches public Cloudflare GETs only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://wandering-wave-4418.c022050333.workers.dev"
BASELINE = {f"{year}-{round_no}.json" for year in range(104, 116) for round_no in (1, 2)}
ROUNDS = {1: "第一次", 2: "第二次"}


def must(condition: bool, problem: str) -> None:
    if not condition:
        raise ValueError(problem)


def json_object(raw: bytes, label: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}: malformed JSON") from exc
    must(isinstance(value, dict), f"{label}: JSON object required")
    return value


def verify_local(root: Path) -> tuple[dict, dict[str, bytes]]:
    manifest_raw = (root / "manifest.json").read_bytes()
    manifest = json_object(manifest_raw, "manifest")
    must(manifest.get("schema_version") == 1, "manifest schema changed")
    parts = manifest.get("shards")
    must(isinstance(parts, list) and len(parts) >= 24, "missing historical shards")
    must(manifest.get("shard_count") == len(parts), "shard_count mismatch")
    must(manifest.get("baseline_shard_count") == 24, "historical baseline changed")
    must(isinstance(manifest.get("dataset_revision"), str) and
         re.fullmatch(r"[a-f0-9]{20}", manifest["dataset_revision"]) is not None,
         "invalid dataset revision")

    raw_files: dict[str, bytes] = {"manifest.json": manifest_raw}
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    seen_sessions: set[tuple[str, str]] = set()
    count = 0
    for meta in parts:
        must(isinstance(meta, dict), "invalid shard metadata")
        name = meta.get("file")
        must(isinstance(name, str) and
             re.fullmatch(r"(10[4-9]|11[0-9]|1[2-9][0-9])-[12]\.json", name) is not None,
             f"invalid shard filename: {name}")
        must(name not in seen_names, f"duplicate shard filename: {name}")
        seen_names.add(name)
        file_year, file_round = name[:-5].split("-")
        round_name = ROUNDS[int(file_round)]
        must(str(meta.get("year")) == file_year and meta.get("round") == round_name,
             f"{name}: manifest session metadata mismatch")
        must((file_year, round_name) not in seen_sessions, f"{name}: duplicate session")
        seen_sessions.add((file_year, round_name))
        must(meta.get("question_count") == 200, f"{name}: incomplete approved 200-question session")
        raw = (root / name).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        must(meta.get("sha256") == digest and meta.get("bytes") == len(raw),
             f"{name}: SHA-256/byte-length mismatch")
        payload = json_object(raw, name)
        questions = payload.get("questions")
        must(payload.get("schema_version") == 1 and
             str(payload.get("year")) == file_year and
             payload.get("round") == round_name and
             payload.get("question_count") == 200 and
             isinstance(questions, list) and len(questions) == 200,
             f"{name}: payload session/count mismatch")
        for row in questions:
            must(isinstance(row, dict), f"{name}: invalid row")
            rid = row.get("id")
            must(isinstance(rid, str) and rid.strip() and rid not in seen_ids,
                 f"{name}: empty or duplicate question ID")
            seen_ids.add(rid)
            must(str(row.get("year")) == file_year and row.get("round") == round_name,
                 f"{name}: question session ownership mismatch")
        raw_files[name] = raw
        count += len(questions)
    must(BASELINE.issubset(seen_names), "one or more historical baseline sessions missing")
    must(manifest.get("total_questions") == count and count == len(seen_ids),
         "manifest total/unique IDs mismatch")
    must(count == 200 * len(parts), "manifest session arithmetic mismatch")
    must(set(raw_files) == set(seen_names) | {"manifest.json"}, "unlisted local shard")
    must({p.name for p in root.glob("*.json")} == set(raw_files),
         "unlisted or missing shard file")
    return manifest, raw_files


def verify_hosted(expected: dict[str, bytes], get_file) -> None:
    # The full live manifest and EVERY shard must equal the reviewed tracked
    # bytes, including the future 116-1 session. Revision alone is insufficient.
    for name, wanted in expected.items():
        status, received, content_type = get_file(name)
        must(status == 200 and "json" in content_type.lower(),
             f"{name}: live HTTP/status/content-type invalid")
        must(received == wanted, f"{name}: hosted bytes differ from tracked release")


def public_get(name: str, nonce: str) -> tuple[int, bytes, str]:
    url = (ORIGIN + "/question-shards/" + name + "?" +
           urllib.parse.urlencode({"swsi_new_exam_release_check": nonce}))
    request = urllib.request.Request(url, headers={
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": "SWSI-Exam-Release-ReadOnly/1.0",
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as res:
            return int(res.status), res.read(8_000_001), res.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        return error.code, error.read(2048), error.headers.get("Content-Type", "")


def write_synthetic(root: Path, future: bool) -> None:
    sessions = sorted(BASELINE)
    if future:
        sessions += ["116-1.json"]
    shards = []
    for name in sessions:
        year, round_no = name[:-5].split("-")
        questions = [{"id": f"SYN-{name}-{i}", "year": year,
                      "round": ROUNDS[int(round_no)], "qno": str(i)}
                     for i in range(1, 201)]
        payload = {"schema_version": 1, "year": year,
                   "round": ROUNDS[int(round_no)], "question_count": 200,
                   "questions": questions}
        raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        (root / name).write_bytes(raw)
        shards.append({"year": year, "round": ROUNDS[int(round_no)], "file": name,
                       "question_count": 200, "bytes": len(raw),
                       "sha256": hashlib.sha256(raw).hexdigest()})
    manifest = {"schema_version": 1, "dataset_revision": "a" * 20,
                "shard_count": len(shards), "baseline_shard_count": 24,
                "total_questions": 200 * len(shards), "shards": shards}
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False))


def selftest() -> None:
    with tempfile.TemporaryDirectory(prefix="swsi-release-qa-") as temp:
        root = Path(temp)
        write_synthetic(root, future=True)
        manifest, raw = verify_local(root)
        must(manifest["shard_count"] == 25 and manifest["total_questions"] == 5000,
             "synthetic new exam not accepted")
        verify_hosted(raw, lambda name: (200, raw[name], "application/json"))
        def rejected(call):
            try:
                call()
            except (ValueError, OSError):
                return
            raise AssertionError("bad release passed fail-closed gate")

        rejected(lambda: verify_hosted(raw, lambda name: (
            200, b"stale" if name == "116-1.json" else raw[name], "application/json")))
        rejected(lambda: verify_hosted(raw, lambda name: (
            404 if name == "116-1.json" else 200, raw[name], "application/json")))
        original = (root / "116-1.json").read_bytes()
        (root / "116-1.json").write_bytes(original + b" ")
        rejected(lambda: verify_local(root))
        (root / "116-1.json").write_bytes(original)
        (root / "116-1.json").unlink()
        rejected(lambda: verify_local(root))
        (root / "116-1.json").write_bytes(original)
        manifest_path = root / "manifest.json"
        baseline = manifest_path.read_bytes()
        broken = json.loads(baseline)
        broken["shards"][0]["file"] = "116-1.json"
        manifest_path.write_text(json.dumps(broken))
        rejected(lambda: verify_local(root))
        manifest_path.write_bytes(baseline)
        assert verify_local(root)[0]["total_questions"] == 5000
    print("FUTURE SHARD RELEASE SELFTEST PASS: 25 shards / 5000 synthetic IDs, stale/missing/live corruption and baseline gates")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--root", type=Path, default=ROOT / "cdn/question-shards")
    ap.add_argument("--attempts", type=int, default=8)
    ap.add_argument("--pause", type=float, default=5)
    ap.add_argument("--check", default="manual")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    if not (args.local or args.live) or args.attempts < 1 or args.attempts > 12:
        raise SystemExit("select --local or --live (read-only)")
    manifest, expected = verify_local(args.root)
    if not args.live:
        print(f"SHARD RELEASE LOCAL PASS: {manifest['shard_count']} shards / {manifest['total_questions']} IDs")
        return 0
    last = ""
    for attempt in range(1, args.attempts + 1):
        try:
            verify_hosted(expected, lambda name: public_get(name, f"{args.check}-{attempt}"))
            print(f"SHARD RELEASE HOSTED PARITY PASS: {manifest['shard_count']} shards / "
                  f"{manifest['total_questions']} IDs / revision={manifest['dataset_revision']}")
            return 0
        except (ValueError, urllib.error.URLError, TimeoutError) as exc:
            last = f"{type(exc).__name__}: {exc}"
            print(f"Waiting for all hosted shards ({attempt}/{args.attempts}): {last}")
            if attempt < args.attempts:
                time.sleep(args.pause)
    raise SystemExit("SHARD RELEASE HOSTED PARITY FAILED: " + last)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""End-to-end regression against the real 4,800 read-only local shard rows."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from historical_source_url_repair_plan import load_local_shards, propose


def altered_url(url: str, *, s: str) -> str:
    parts = urlsplit(url)
    params = dict(parse_qsl(parts.query))
    params["s"] = s
    return urlunsplit(parts._replace(query=urlencode(params)))


def must_reject(rows: list[dict], phrase: str) -> None:
    try:
        propose(rows)
    except (ValueError, RuntimeError) as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError(f"did not reject: {phrase}")


def main() -> int:
    rows = load_local_shards()
    assert len(rows) == 4800
    no_change = propose(rows)
    assert no_change["status"] == "NO_CHANGE" and no_change["proposed_url_changes"] == 0

    index = next(i for i, r in enumerate(rows) if str(r["year"]) == "112"
                 and r["round"] == "第一次"
                 and r["subject"] == "社會政策與社會立法")
    original = rows[index]
    changed = [dict(r) for r in rows]
    changed[index]["source_url"] = altered_url(original["source_url"], s="0303")
    assert changed[index]["source_url"] != original["source_url"]
    proposal = propose(changed)
    assert proposal["status"] == "REVIEW_REQUIRED_NOT_APPLIED"
    assert proposal["proposed_url_changes"] == 1
    assert proposal["changed_fields"] == ["source_url"]
    assert proposal["patches"][0]["id"] == original["id"]
    assert proposal["patches"][0]["before"] != proposal["patches"][0]["after"]
    assert proposal["patches"][0]["official_pdf_sha256"]
    assert not proposal["production_written"] and not proposal["release_approved"]
    assert changed[index]["source_url"] != original["source_url"], "planner must not mutate rows"

    # The monthly CI mode must write a review-only artifact and fail on drift.
    with TemporaryDirectory(prefix="swsi-url-plan-test-") as temp:
        input_path = Path(temp) / "rows.json"
        output_path = Path(temp) / "candidate.json"
        input_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
        runner = Path(__file__).with_name("historical_source_url_repair_plan.py")
        proc = subprocess.run(
            [sys.executable, str(runner), "--input", str(input_path),
             "--out", str(output_path), "--fail-on-proposals"],
            capture_output=True, text=True, check=False, timeout=60,
        )
        assert proc.returncode == 2, (proc.stdout, proc.stderr)
        generated = json.loads(output_path.read_text(encoding="utf-8"))
        assert generated["proposed_url_changes"] == 1
        assert generated["production_written"] is False
        assert generated["release_approved"] is False

    # The monthly source + full Official Core/grade check shares one public
    # API snapshot. One altered answer must fail without rewriting that answer.
    with TemporaryDirectory(prefix="swsi-monthly-core-parity-") as temp:
        top = Path(temp)
        wrong = [dict(x) for x in rows]
        wrong[0]["answer"] = "SYNTHETIC_UNAPPROVED_ANSWER"
        input_path = top / "live.json"
        url_output = top / "url.json"
        core_output = top / "core.json"
        input_path.write_text(json.dumps(wrong, ensure_ascii=False), encoding="utf-8")
        cmd = [
            sys.executable, str(Path(__file__).with_name("historical_source_url_repair_plan.py")),
            "--input", str(input_path), "--out", str(url_output),
            "--core-parity-out", str(core_output),
            "--fail-on-proposals", "--fail-on-core-drift",
        ]
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
        assert run.returncode == 2, (run.stdout, run.stderr)
        assert json.loads(url_output.read_text(encoding="utf-8"))["proposed_url_changes"] == 0
        core = json.loads(core_output.read_text(encoding="utf-8"))
        assert core["status"] == "HOLD_REVIEW_DRIFT"
        assert core["summary"]["grading_drift"] == 1
        assert core["summary"]["official_wording_drift"] == 0
        assert not core["database_written"] and not core["release_approved"]
        assert wrong[0]["answer"] == "SYNTHETIC_UNAPPROVED_ANSWER"

    # A malicious/wrong source URL must HOLD the release; however the separate
    # grade/core diagnostic is still saved for investigation. The failure is
    # never converted into a successful URL proposal.
    with TemporaryDirectory(prefix="swsi-independent-evidence-") as temp:
        top = Path(temp)
        url_tampered = [dict(r) for r in rows]
        url_tampered[index]["source_url"] = (
            "https://wwwq.moex.gov.tw@evil.example/exam/wHandExamQandA_File.ashx"
        )
        input_path = top / "live.json"
        url_out = top / "url-proposal.json"
        core_out = top / "core-parity.json"
        input_path.write_text(json.dumps(url_tampered, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("historical_source_url_repair_plan.py")),
             "--input", str(input_path), "--out", str(url_out),
             "--core-parity-out", str(core_out),
             "--fail-on-proposals", "--fail-on-core-drift"],
            capture_output=True, text=True, check=False, timeout=90,
        )
        assert proc.returncode != 0, "wrong official URL must block release"
        assert "unsafe or malformed" in proc.stderr, proc.stderr
        assert not url_out.exists(), "unsafe URL must not become a proposal"
        core = json.loads(core_out.read_text(encoding="utf-8"))
        assert core["status"] == "MATCH", "core parity excludes URL-only proof"
        assert core["expected_questions"] == core["live_questions"] == 4800
        assert core["release_approved"] is False and core["database_written"] is False

    # Offline/full-corpus failure must not suppress scheduled live-source QA.
    workflow = (Path(__file__).resolve().parents[1] /
                ".github/workflows/full-corpus-qa.yml").read_text(encoding="utf-8")
    step = workflow.split("      - name: Monthly READ-ONLY production source URL drift audit\n", 1)[1]
    assert "if: ${{ !cancelled() && github.event_name == 'schedule' }}" in step.split("      - name:", 1)[0]
    assert "--core-parity-out /tmp/swsi-live-official-core-parity.json" in step
    assert "if: always() && github.event_name == 'schedule'" in workflow, (
        "independent artifacts must be retained even on a failed URL/core gate"
    )

    code_bad = [dict(r) for r in rows]
    code_bad[index]["source_exam_code"] = "000000"
    must_reject(code_bad, "exam_code disagreement")

    spoof = [dict(r) for r in rows]
    spoof[index]["source_url"] = (
        "https://wwwq.moex.gov.tw@evil.example/exam/wHandExamQandA_File.ashx"
    )
    must_reject(spoof, "unsafe or malformed")

    wrong_code = [dict(r) for r in rows]
    wrong_code[index]["source_url"] = original["source_url"].replace("code=112030", "code=000000")
    must_reject(wrong_code, "wrong exam_code")

    must_reject(rows[:-1], "historical coverage incomplete")
    duplicates = [dict(r) for r in rows]
    duplicates[1]["id"] = duplicates[0]["id"]
    must_reject(duplicates, "duplicate question ID")

    print("SOURCE URL PROPOSAL SELFTEST OK: 4800 no-op, source-only proposal, five safety rejections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

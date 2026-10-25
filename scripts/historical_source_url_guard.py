#!/usr/bin/env python3
"""Fail-closed historic MOEX source identity check for Supabase shard publishing.

A URL being present or returning 200 is NOT proof it is for the right exam,
category and subject. This guard uses the 120 frozen, PDF-header/index-matched
official source identities; it never calls the network or changes any records.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/moex_source_subjects.v1.json"
SUBJECTS = frozenset({
    "社會工作", "社會工作直接服務", "社會政策與社會立法",
    "人類行為與社會環境", "社會工作研究方法",
})
SESSIONS = frozenset(f"{y}-{rd}" for y in range(104, 116) for rd in (1, 2))


def url_identity(url: str) -> tuple[str, str, str]:
    """Check the complete official question URL contract, ignoring query order."""
    parts = urlsplit(url or "")
    if (parts.scheme != "https" or parts.netloc != "wwwq.moex.gov.tw"
            or parts.path != "/exam/wHandExamQandA_File.ashx"
            or parts.fragment or parts.username or parts.password):
        raise ValueError("untrusted source URL origin/path")
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    values = dict(pairs)
    if (len(pairs) != 5 or len(values) != 5
            or set(values) != {"c", "code", "q", "s", "t"}
            or values["q"] != "1" or values["t"] != "Q"):
        raise ValueError("invalid official question URL parameters")
    return values["code"], values["c"], values["s"]


def load_registry(path: Path = REGISTRY) -> dict[tuple[str, str], dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("records") if isinstance(doc, dict) else None
    if doc.get("schema_version") != 1 or not isinstance(rows, list) or len(rows) != 120:
        raise ValueError("official source registry must contain 120 pinned PDFs")
    index = {}
    for record in rows:
        key = (record.get("session"), record.get("subject"))
        if (key[0] not in SESSIONS or key[1] not in SUBJECTS or key in index
                or record.get("status") != "pdf_header_index_matched"):
            raise ValueError(f"unverified/duplicate official paper identity: {key}")
        line = re.search(r"科\s*目\s*[:：]\s*([^\r\n]+)", record.get("pdf_header") or "")
        if not line or "".join(line.group(1).split()) != "".join(key[1].split()):
            raise ValueError(f"wrong PDF header subject: {key}")
        try:
            identity = url_identity(record["url"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"registry URL invalid for {key}") from exc
        if identity != (record.get("exam_code"), str(record.get("c")), str(record.get("s"))):
            raise ValueError(f"registry URL does not match verified PDF: {key}")
        http = record.get("http") or {}
        if (http.get("http_status") != 200 or "pdf" not in str(http.get("mime", "")).lower()
                or http.get("sha256") != record.get("pdf_sha256")
                or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("pdf_sha256")))):
            raise ValueError(f"registry PDF bytes/evidence not confirmed: {key}")
        index[key] = record
    expected = {(s, subject) for s in SESSIONS for subject in SUBJECTS}
    if set(index) != expected:
        raise ValueError("incomplete official exam x subject registry coverage")
    return index


def validate_historical_source_urls(rows: list[dict], *, registry_path: Path = REGISTRY) -> int:
    """Reject a stale Supabase source_url BEFORE shard build or publication.

    Legacy pre-115 aliases are not trusted unless their exact code/c/s matches
    the separately audited paper. This cannot approve official question text,
    answers, enrichment or human-reviewed essay grading.
    """
    registry = load_registry(registry_path)
    observed = Counter()
    mismatches = []
    for row in rows:
        year = str(row.get("year") or "")
        if year not in {str(y) for y in range(104, 116)}:
            continue  # Future complete exams are governed by their own importer.
        rd = {"第一次": "1", "第二次": "2"}.get(row.get("round"))
        key = (f"{year}-{rd}", str(row.get("subject") or ""))
        expected = registry.get(key)
        observed[key] += 1
        try:
            actual = url_identity(row.get("source_url"))
        except (ValueError, TypeError):
            actual = None
        wanted = None if expected is None else (
            expected["exam_code"], str(expected["c"]), str(expected["s"]))
        if (expected is None or actual != wanted
                or row.get("source_exam_code") != expected["exam_code"]):
            mismatches.append(str(row.get("id") or "<missing-id>"))
    bad_counts = sorted(str(k) for k, n in observed.items() if n != 40)
    if set(observed) != set(registry) or bad_counts or mismatches:
        raise RuntimeError(
            "BLOCKED: historic Supabase MOEX source URLs do not match verified "
            "question-PDF exam/subject identities; refusing to rebuild/publish "
            f"shards. mismatched_rows={len(mismatches)} "
            f"groups={len(observed)}/120 bad_counts={bad_counts[:5]} "
            f"sample_ids={mismatches[:8]}. Do not auto-rewrite Official Core."
        )
    return sum(observed.values())

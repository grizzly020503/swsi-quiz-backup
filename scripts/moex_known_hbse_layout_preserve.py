#!/usr/bin/env python3
"""Preserve one previously locked 115-2 HBSE essay when PDF layout alone drifts.

This exception is tightly bound to independent official PDF evidence captured
2026-11-16: one ASCII space before the final NEET closing parenthesis.
It never changes the accepted historical wording, points or official lock.
Unknown edits and a changed official source PDF remain blocked by existing gates.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from moex_essay_drift_preflight import CORE_FIELDS, digest

ID = "E-115-2-HBSE-1"
EXAM = "115100"
ORIGINAL_Q_JSON_SHA256 = "4a7a7962fe38c284e1d80a237818f04c3f5b306f6c62fdc2fd3e58292fdea8d2"
REEXTRACTED_Q_JSON_SHA256 = "a4b35c1b2427a842944bbe3b7ca0c82c207171bb2d301bc1291b7836c1adb213"
ORIGINAL_PDF_SHA256 = "a53d97745e23d6c4eef21b49e27d37b847960957b7e9e3a438ac64840825bfa1"


class SourceFingerprintChanged(RuntimeError):
    pass


def preserve_exact_prior_q(
    candidate: dict, baseline_path: Path,
    *,
    pdf_supplier: Callable[[], bytes] | None = None,
    observed_pdf_sha256: str | None = None,
) -> bool:
    """Mutate only an exact, previously accepted space back to locked wording.

    Return False for any other change. In production the PDF must be downloaded
    a second time to check the immutable source fingerprint before proceeding.
    The observed_pdf_sha256 argument is only for deterministic offline tests.
    """
    if candidate.get("exam_code") != EXAM or not baseline_path.exists():
        return False
    previous = json.loads(baseline_path.read_text(encoding="utf-8"))
    if previous.get("exam_code") != EXAM:
        return False
    old_essays = previous.get("essays")
    new_essays = candidate.get("essays")
    if not isinstance(old_essays, list) or not isinstance(new_essays, list):
        return False
    if len(old_essays) != 10 or len(new_essays) != 10:
        return False
    if any(not isinstance(x, dict) for x in old_essays + new_essays):
        return False
    old_by_id = {x.get("id"): x for x in old_essays}
    new_by_id = {x.get("id"): x for x in new_essays}
    if len(old_by_id) != 10 or len(new_by_id) != 10 or set(old_by_id) != set(new_by_id):
        return False
    old_q = old_by_id[ID].get("q") if ID in old_by_id else None
    new_q = new_by_id[ID].get("q") if ID in new_by_id else None
    if old_q == new_q or not isinstance(old_q, str) or not isinstance(new_q, str):
        return False
    if digest(old_q) != ORIGINAL_Q_JSON_SHA256 or digest(new_q) != REEXTRACTED_Q_JSON_SHA256:
        return False
    # The unique difference must be removal of the known single ASCII space,
    # never any substantive wording, punctuation or English word-space change.
    if old_q.count("training ）") != 1 or new_q != old_q.replace("training ）", "training）", 1):
        return False
    for ident in old_by_id:
        for field in CORE_FIELDS:
            if ident == ID and field == "q":
                continue
            if old_by_id[ident].get(field) != new_by_id[ident].get(field):
                return False
    if observed_pdf_sha256 is None:
        if pdf_supplier is None:
            raise SourceFingerprintChanged("PDF supplier must be present for live verification")
        observed_pdf_sha256 = hashlib.sha256(pdf_supplier()).hexdigest()
    if observed_pdf_sha256 != ORIGINAL_PDF_SHA256:
        raise SourceFingerprintChanged("115100 HBSE PDF hash changed: manual official review required")
    new_by_id[ID]["q"] = old_q
    return True

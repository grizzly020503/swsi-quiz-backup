#!/usr/bin/env python3
"""Offline positive/negative contracts for pinned 115-2 HBSE PDF layout exception."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from moex_known_hbse_layout_preserve import (
    ID, ORIGINAL_PDF_SHA256, SourceFingerprintChanged, preserve_exact_prior_q,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "incoming" / "115100.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    original_row = next(x for x in original["essays"] if x["id"] == ID)
    original_q = original_row["q"]
    assert original_q.count("training ）") == 1, "pinned prior-question preimage changed"

    def fresh():
        c = copy.deepcopy(original)
        next(x for x in c["essays"] if x["id"] == ID)["q"] = original_q.replace(
            "training ）", "training）", 1
        )
        return c

    candidate = fresh()
    assert preserve_exact_prior_q(
        candidate, path, observed_pdf_sha256=ORIGINAL_PDF_SHA256
    )
    assert candidate == original, "known space drift must restore exact original"

    changed_text = fresh()
    next(x for x in changed_text["essays"] if x["id"] == ID)["q"] += "不核准字元"
    assert not preserve_exact_prior_q(
        changed_text, path, observed_pdf_sha256=ORIGINAL_PDF_SHA256
    ), "substantive drift must not be reconciled"

    changed_points = fresh()
    next(x for x in changed_points["essays"] if x["id"] == ID)["points"] = "25"
    assert not preserve_exact_prior_q(
        changed_points, path, observed_pdf_sha256=ORIGINAL_PDF_SHA256
    ), "point changes must not be reconciled"

    changed_other_essay = fresh()
    changed_other_essay["essays"][0]["q"] += "更動別題"
    assert not preserve_exact_prior_q(
        changed_other_essay, path, observed_pdf_sha256=ORIGINAL_PDF_SHA256
    ), "simultaneous drift must not be reconciled"

    changed_id = fresh()
    changed_id["essays"][0]["id"] += "-NEW"
    assert not preserve_exact_prior_q(
        changed_id, path, observed_pdf_sha256=ORIGINAL_PDF_SHA256
    ), "ID changes must not be reconciled"

    no_change = copy.deepcopy(original)
    assert not preserve_exact_prior_q(
        no_change, path, observed_pdf_sha256=ORIGINAL_PDF_SHA256
    )
    assert no_change == original

    wrong_pdf = fresh()
    try:
        preserve_exact_prior_q(wrong_pdf, path, observed_pdf_sha256="0" * 64)
    except SourceFingerprintChanged:
        pass
    else:
        raise AssertionError("different official PDF must stop")
    assert next(x for x in wrong_pdf["essays"] if x["id"] == ID)["q"] != original_q, (
        "wrong PDF must not change candidate data"
    )

    no_supplier = fresh()
    try:
        preserve_exact_prior_q(no_supplier, path)
    except SourceFingerprintChanged:
        pass
    else:
        raise AssertionError("unverified live PDF must stop")

    foreign_exam = fresh()
    foreign_exam["exam_code"] = "116100"
    assert not preserve_exact_prior_q(
        foreign_exam, path, observed_pdf_sha256=ORIGINAL_PDF_SHA256
    )
    print("MOEX HBSE SHA-pinned layout preservation: PASS (8 fail-closed checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

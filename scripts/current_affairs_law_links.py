#!/usr/bin/env python3
"""Fail-closed law / policy-instrument linkage for SWSI current affairs.

This layer intentionally separates:
- related statutes (``related_laws``), and
- programmes / subsidy schemes / policy measures (``related_policy_instruments``).

A matched statute means "this event is materially governed by / connected to this
statutory framework".  It MUST NOT be interpreted as evidence that the statute
was amended.  Rules live in a versioned JSON file and carry positive + negative
regression examples so broad category labels cannot silently create law links.
"""
from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = ROOT / "data" / "current_affairs_law_link_rules.v1.json"


def _text_of(row: dict) -> str:
    return f"{row.get('title') or ''} {row.get('summary') or ''}".strip()


def _matches(text: str, rule: dict) -> bool:
    text = str(text or "")
    required_any = [str(x) for x in (rule.get("required_any") or []) if str(x)]
    context_any = [str(x) for x in (rule.get("required_context_any") or []) if str(x)]
    required_all = [str(x) for x in (rule.get("required_all") or []) if str(x)]
    forbidden_any = [str(x) for x in (rule.get("forbidden_any") or []) if str(x)]

    if required_any and not any(term in text for term in required_any):
        return False
    if context_any and not any(term in text for term in context_any):
        return False
    if required_all and not all(term in text for term in required_all):
        return False
    if forbidden_any and any(term in text for term in forbidden_any):
        return False
    return bool(required_any or required_all)


def _validate_rule(rule: dict, bucket: str) -> None:
    rule_id = str(rule.get("id") or "").strip()
    if not rule_id:
        raise ValueError(f"{bucket}: rule id missing")
    if str(rule.get("confidence") or "") not in {"high", "medium"}:
        raise ValueError(f"{rule_id}: automatic linkage requires high/medium confidence")
    if bucket == "law_rules" and not str(rule.get("law") or "").strip():
        raise ValueError(f"{rule_id}: law missing")
    if bucket == "policy_instrument_rules" and not str(rule.get("name") or "").strip():
        raise ValueError(f"{rule_id}: policy instrument name missing")
    if not str(rule.get("authoritative_reference") or "").startswith("https://"):
        raise ValueError(f"{rule_id}: authoritative reference must be https")
    positives = [str(x) for x in (rule.get("positive_examples") or []) if str(x)]
    negatives = [str(x) for x in (rule.get("negative_examples") or []) if str(x)]
    if not positives or not negatives:
        raise ValueError(f"{rule_id}: positive + negative regression examples are required")
    for text in positives:
        if not _matches(text, rule):
            raise ValueError(f"{rule_id}: positive regression no longer matches: {text}")
    for text in negatives:
        if _matches(text, rule):
            raise ValueError(f"{rule_id}: negative regression falsely matches: {text}")


@lru_cache(maxsize=4)
def _load_rules_cached(path_text: str) -> dict:
    path = Path(path_text)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"unexpected law-link rule schema: {payload.get('schema_version')}")

    seen: set[str] = set()
    for bucket in ("law_rules", "policy_instrument_rules"):
        rows = payload.get(bucket) or []
        if not isinstance(rows, list):
            raise ValueError(f"{bucket} must be a list")
        for rule in rows:
            if not isinstance(rule, dict):
                raise ValueError(f"{bucket}: rule must be an object")
            _validate_rule(rule, bucket)
            rule_id = str(rule["id"])
            if rule_id in seen:
                raise ValueError(f"duplicate current-affairs law-link rule id: {rule_id}")
            seen.add(rule_id)
    return payload


def load_rules(path: Path | None = None) -> dict:
    return _load_rules_cached(str((path or DEFAULT_RULES).resolve()))


def _basis_record(rule: dict, *, name: str, kind: str) -> dict:
    out = {
        "rule_id": rule.get("id"),
        "name": name,
        "kind": kind,
        "confidence": rule.get("confidence"),
        "reason": rule.get("reason"),
        "authoritative_reference": rule.get("authoritative_reference"),
        "inference": "deterministic_rule",
    }
    if rule.get("article"):
        out["article"] = rule.get("article")
    return out


def infer_current_affairs_links(row: dict, rules_path: Path | None = None) -> dict:
    """Return additive public linkage fields without mutating ``row``.

    Existing explicit ``related_laws`` are preserved. Deterministic rules only
    add links when both a specific topic anchor and an independent context
    anchor match. Policy instruments are kept separate from statutes.
    """
    rules = load_rules(rules_path)
    text = _text_of(row)
    laws: list[str] = []
    seen_laws: set[str] = set()
    for raw in row.get("related_laws") or []:
        law = str(raw or "").strip()
        if law and law not in seen_laws:
            seen_laws.add(law)
            laws.append(law)

    basis: list[dict] = []
    for rule in rules.get("law_rules") or []:
        if not _matches(text, rule):
            continue
        law = str(rule.get("law") or "").strip()
        if law and law not in seen_laws:
            seen_laws.add(law)
            laws.append(law)
        basis.append(_basis_record(rule, name=law, kind="law"))

    instruments: list[dict] = []
    seen_instruments: set[tuple[str, str]] = set()
    for rule in rules.get("policy_instrument_rules") or []:
        if not _matches(text, rule):
            continue
        name = str(rule.get("name") or "").strip()
        kind = str(rule.get("kind") or "policy_measure").strip()
        identity = (name, kind)
        if identity in seen_instruments:
            continue
        seen_instruments.add(identity)
        instruments.append(_basis_record(rule, name=name, kind=kind))

    if laws:
        status = "law_linked"
        note = (
            "已連到具體法律；規則僅表示制度關聯，不代表該法律因本事件而修正。"
        )
    elif instruments:
        status = "policy_instrument_only"
        note = (
            "已辨識補助方案／政策措施，但未自動推定單一法律法源，避免把政策方案誤寫成修法。"
        )
    else:
        status = "unresolved"
        note = (
            "目前沒有足夠高信心的法規／制度連結；保留待來源核對，不為提高覆蓋率而硬配法規。"
        )

    return {
        "related_laws": laws,
        "related_policy_instruments": instruments,
        "law_link_status": status,
        "law_link_note": note,
        "law_link_basis": basis,
        "law_link_rules_schema": 1,
    }


def self_test() -> None:
    rules = load_rules()
    # Loading already executes every rule's positive + negative examples.
    # These cross-rule checks guard the most important false-positive boundary.
    public_childcare = {
        "title": "地方政府新增公共托育據點",
        "summary": "增加社區托育名額，未涉及雇主或職場托兒措施。",
        "related_laws": [],
    }
    out = infer_current_affairs_links(public_childcare)
    if "性別平等工作法" in out["related_laws"]:
        raise SystemExit("public childcare falsely linked to employer childcare law")

    employer_childcare = {
        "title": "企業托育補助開放申請",
        "summary": "雇主可提供員工育兒補貼與托兒措施。",
        "related_laws": [],
    }
    out = infer_current_affairs_links(employer_childcare)
    if "性別平等工作法" not in out["related_laws"]:
        raise SystemExit("employer childcare failed to link 性別平等工作法")

    wage = {
        "title": "最低工資審議會決定調升最低工資",
        "summary": "每月最低工資與每小時最低工資將公告新標準。",
        "related_laws": [],
    }
    out = infer_current_affairs_links(wage)
    if "最低工資法" not in out["related_laws"]:
        raise SystemExit("minimum-wage statutory link missing")

    if not rules.get("law_rules") or not rules.get("policy_instrument_rules"):
        raise SystemExit("law-link rule registry unexpectedly empty")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate deterministic current-affairs law-link rules")
    ap.add_argument("--rules", default=str(DEFAULT_RULES))
    args = ap.parse_args()
    load_rules(Path(args.rules))
    self_test()
    print("Current-affairs law-link rules: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

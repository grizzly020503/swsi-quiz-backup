#!/usr/bin/env python3
"""Regression tests for deterministic English current-affairs classification."""
from __future__ import annotations

from current_affairs_international import event_metadata, score_english_item


def main() -> int:
    child = score_english_item(
        "1 in 5 children across 21 countries have experienced tech-facilitated child sexual abuse – UNICEF",
        "UNICEF calls for stronger child protection and children's rights safeguards.",
        source_type="official",
    )
    assert child and child[1] == "兒少保護", child
    assert "性剝削" in child[2], child
    assert "child-sexual-abuse" in child[3], child

    mental = score_english_item(
        "WHO calls for integrated mental health and psychosocial support services for adolescents",
        "New guidelines strengthen access to community mental health services and psychosocial support.",
        source_type="official",
    )
    assert mental and mental[1] == "心理健康與成癮", mental

    labor = score_english_item(
        "ILO advances minimum wage and social security standards for decent work",
        "The policy framework strengthens labour rights and unemployment protection.",
        source_type="official",
    )
    assert labor and labor[1] == "勞動與社會保障", labor

    generic = score_english_item(
        "UN General Assembly opens annual debate",
        "World leaders deliver remarks at the opening session.",
        source_type="official",
    )
    assert generic is None, generic

    meta_en = event_metadata(
        "UNICEF: 1 in 5 children across 21 countries experienced child sexual abuse",
        "Child rights and protection report.",
        "兒少保護",
        ["兒童權利", "性剝削"],
    )
    meta_zh = event_metadata(
        "UNICEF：21國每5名兒少就1人遭科技促成性剝削",
        "兒童權利與保護。",
        "兒少保護",
        ["兒童權利", "性剝削"],
    )
    assert "unicef" in meta_en["org_keys"] and "unicef" in meta_zh["org_keys"]
    assert {"1", "5", "21"}.issubset(set(meta_en["numeric_anchors"]))
    assert {"1", "5", "21"}.issubset(set(meta_zh["numeric_anchors"]))
    assert "child-sexual-abuse" in meta_en["event_facets"]
    assert "child-sexual-abuse" in meta_zh["event_facets"]

    print(
        "CURRENT AFFAIRS INTERNATIONAL SMOKE OK: "
        "English exam taxonomy, noise rejection, bilingual metadata"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

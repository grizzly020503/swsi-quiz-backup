#!/usr/bin/env python3
"""Fail-closed contract for the current-affairs Supabase sync Edge Function."""
from __future__ import annotations

import json
import re
from pathlib import Path

import current_affairs_watch as watch

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "current_affairs_sources.json"
EDGE = ROOT / "supabase" / "functions" / "sync-current-affairs" / "index.ts"


def extract_raw_json(source: str, constant: str):
    pattern = rf"const\s+{re.escape(constant)}\s*=\s*String\.raw`(.*?)`;"
    match = re.search(pattern, source, flags=re.DOTALL)
    assert match, f"missing {constant} String.raw payload"
    return json.loads(match.group(1))


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    registry_rows = registry.get("sources") or []
    assert registry.get("schema_version") == 1
    assert registry_rows

    source = EDGE.read_text(encoding="utf-8")
    policy = extract_raw_json(source, "SOURCE_POLICY_JSON")
    categories = set(extract_raw_json(source, "CATEGORIES_JSON"))

    by_name = {str(row.get("name") or ""): row for row in registry_rows}
    assert len(by_name) == len(registry_rows), "duplicate current-affairs source name"
    assert set(policy) == set(by_name), (
        "Edge source policy must exactly match the curated source registry",
        sorted(set(by_name) - set(policy)),
        sorted(set(policy) - set(by_name)),
    )

    for name, row in by_name.items():
        cfg = policy[name]
        assert cfg.get("feed") == row.get("url"), (name, cfg.get("feed"), row.get("url"))
        assert cfg.get("region") == row.get("region"), (name, cfg.get("region"), row.get("region"))
        assert cfg.get("source_type") == row.get("source_type"), (
            name,
            cfg.get("source_type"),
            row.get("source_type"),
        )
        hosts = cfg.get("article_hosts") or []
        assert hosts and len(hosts) == len(set(hosts)), (name, hosts)
        for host in hosts:
            assert re.fullmatch(r"[a-z0-9.-]+", str(host)), (name, host)
            assert not str(host).startswith(".") and not str(host).endswith("."), (name, host)

    scanner_categories = {str(category) for category, _base, _words in watch.CATEGORIES}
    assert categories == scanner_categories, (
        "Edge category policy must exactly match current_affairs_watch.CATEGORIES",
        sorted(scanner_categories - categories),
        sorted(categories - scanner_categories),
    )

    # Source name alone is not enough: the production endpoint must bind each row
    # to the exact registry feed, expected region/type, and a source-specific
    # article host allowlist. Do not regress to an any-HTTPS policy.
    required_guards = (
        'SOURCE_POLICY.get(sourceName)',
        'String(x.source_feed || "") !== sourcePolicy.feed',
        'String(x.region || "") !== sourcePolicy.region',
        'String(x.source_type || "") !== sourcePolicy.source_type',
        'safeArticleUrl(x.source_url, sourcePolicy.article_hosts)',
        'host === root || host.endsWith(`.${root}`)',
    )
    for guard in required_guards:
        assert guard in source, f"missing fail-closed source guard: {guard}"

    # The endpoint intentionally keeps verify_jwt=false in Supabase because the
    # GitHub workflow uses a repository-scoped GITHUB_TOKEN and the function
    # performs its own repository-access verification before any DB write.
    assert 'https://api.github.com/repos/${REPO}' in source
    assert 'unauthorized GitHub workflow' in source

    # Preserve the #231 welfare-system fix when storing the legacy DB subjects
    # array: a policy-only knowledge classification must not be expanded back to
    # the old broad social-work/direct-service category map.
    assert 'function normalizedSubjects' in source
    assert 'axes.includes("社會政策與社會立法")' in source
    assert '!axes.includes("社會工作")' in source
    assert 'subjects: normalizedSubjects(x)' in source

    print(
        "CURRENT AFFAIRS SUPABASE SYNC POLICY OK: "
        f"sources={len(policy)}, categories={len(categories)}, "
        "feed/region/type/host binding=yes, custom GitHub auth preserved=yes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

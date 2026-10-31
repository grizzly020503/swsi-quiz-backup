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
PUBLIC_WORKFLOW = ROOT / ".github" / "workflows" / "public-monitoring-feed.yml"
MOEX_WORKFLOW = ROOT / ".github" / "workflows" / "moex-social-worker-sync.yml"


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
        assert hosts == row.get("article_hosts"), (name, "article host policy drift")
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

    # GitHub OIDC must be signature- and claim-verified before service-role
    # writes; public repository read access or a generic token is insufficient.
    for guard in (
        "verifyGitHubActionsOidcToken",
        "CURRENT_AFFAIRS_SYNC_POLICY",
        "public-monitoring-feed.yml@refs/heads/main",
        'new Set(["schedule", "workflow_dispatch", "workflow_run", "push"])',
        "GitHub Actions OIDC authorization rejected",
    ):
        assert guard in source, f"missing GitHub Actions OIDC guard: {guard}"
    assert 'validateCurrentAffairsPayload(body, {' in source, "missing scanner envelope guard"
    # The Edge must not accept fallback scans with fewer registry sources or
    # treat optional-only feed success as successful primary coverage.
    required_count = sum(not bool(row.get("optional", False)) for row in registry_rows)
    assert 0 < required_count <= len(registry_rows)
    assert f"const REQUIRED_FEED_COUNT = {required_count};" in source, "Edge required source count drift"
    assert "total: SOURCE_POLICY.size" in source
    assert "required: REQUIRED_FEED_COUNT" in source
    assert './payload_contract.ts' in source, "missing versioned scanner validator import"
    assert source.index("validateCurrentAffairsPayload(body, {") < source.index('const url = Deno.env.get("SUPABASE_URL")'), "scanner envelope validation must run before DB access"
    for forbidden in ("verifyRepoWriteToken", "repo?.permissions?.push === true"):
        assert forbidden not in source, f"legacy write-token auth remains: {forbidden}"

    # Do not silently report success when the sync's final DB operations fail.
    # This protects the operational heartbeat from misleading green results.
    for guard in (
        'const { error: archiveError } = await sb',
        'if (archiveError)',
        'current affairs archival failed',
        'const { error: auditError } = await sb.from("current_affairs_sync_runs").insert',
        'if (auditError)',
        'current affairs sync audit failed',
    ):
        assert guard in source, f"missing current-affairs write-result guard: {guard}"
    archived_idx = source.index('if (archiveError)')
    audited_idx = source.index('if (auditError)')
    success_idx = source.index('return json({ ok: true, upserted, feed_errors:')
    assert archived_idx < audited_idx < success_idx, "must reject failures before success"
    assert source[archived_idx:audited_idx].count('return json(') == 1
    assert source[audited_idx:success_idx].count('return json(') == 1

    # Preserve the #231 welfare-system fix when storing the legacy DB subjects
    # array: a policy-only knowledge classification must not be expanded back to
    # the old broad social-work/direct-service category map.
    assert 'function normalizedSubjects' in source
    assert 'axes.includes("社會政策與社會立法")' in source
    assert '!axes.includes("社會工作")' in source
    assert 'subjects: normalizedSubjects(x)' in source

    # Current affairs has one runtime owner. Public Monitoring Feed owns the scan,
    # Supabase candidate sync, and public snapshots. MOEX owns exams/law state and
    # must not grow a second current-affairs scanner/sync path again.
    public_workflow = PUBLIC_WORKFLOW.read_text(encoding="utf-8")
    moex_workflow = MOEX_WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "Scan social-work current affairs",
        "Sync current-affairs candidates to Supabase",
        "id: current_affairs_supabase",
        "--data-binary @/tmp/current_affairs_payload.json",
        "https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/sync-current-affairs",
        "Fail visibly if current-affairs Supabase sync failed",
        "steps.current_affairs_supabase.outcome != 'success'",
        "id-token: write",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "ACTIONS_ID_TOKEN_REQUEST_URL",
        "audience=swsi-supabase-sync",
        "::add-mask::$oidc_token",
    ):
        assert required in public_workflow, f"Public Monitoring Feed missing sync ownership contract: {required}"
    assert "continue-on-error: true" in public_workflow, (
        "Supabase sync must not block public snapshot rebuild/publish before the final visible failure gate"
    )
    assert "GH_REPO_TOKEN:" not in public_workflow, "legacy auth must be retired"
    assert "SUPABASE_SERVICE_ROLE_KEY" not in public_workflow, "no DB secret in GitHub Actions"

    for forbidden in (
        "Scan social-work current affairs",
        "Sync current-affairs candidates to Supabase",
        "scripts/current_affairs_watch.py --output /tmp/current_affairs_payload.json",
        "sync-current-affairs",
    ):
        assert forbidden not in moex_workflow, f"MOEX regained current-affairs ownership: {forbidden}"

    print(
        "CURRENT AFFAIRS SUPABASE SYNC POLICY OK: "
        f"sources={len(policy)}, categories={len(categories)}, "
        "feed/region/type/host binding=yes, GitHub OIDC verification=yes, "
        "single-owner=Public Monitoring Feed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

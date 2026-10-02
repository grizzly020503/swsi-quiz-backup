#!/usr/bin/env python3
"""Build a deterministic, content-free portability manifest from repo-owned files."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

ALLOWED_CLASSES = {
    "long_term_public_knowledge",
    "rebuild_contract",
    "short_term_diagnostic",
    "private_external",
}
ALLOWED_RETENTION = {"long_term", "short_term", "external_private"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_policy(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("policy must be schema_version=1")
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("policy rules[] must be non-empty")

    normalized: list[dict[str, Any]] = []
    seen_rule_ids: set[str] = set()
    for raw in rules:
        if not isinstance(raw, dict):
            raise ValueError("every policy rule must be an object")
        rule_id = str(raw.get("id") or "").strip()
        storage_class = str(raw.get("storage_class") or "").strip()
        retention = str(raw.get("retention") or "").strip()
        patterns = raw.get("patterns")
        if not rule_id or rule_id in seen_rule_ids:
            raise ValueError(f"missing or duplicate rule id: {rule_id!r}")
        seen_rule_ids.add(rule_id)
        if storage_class not in ALLOWED_CLASSES:
            raise ValueError(f"{rule_id}: invalid storage_class")
        if retention not in ALLOWED_RETENTION:
            raise ValueError(f"{rule_id}: invalid retention")
        if not isinstance(patterns, list) or not patterns or not all(
            isinstance(x, str) and x.strip() for x in patterns
        ):
            raise ValueError(f"{rule_id}: patterns must be non-empty strings")
        if storage_class == "private_external" and raw.get("include_in_manifest", False):
            raise ValueError(f"{rule_id}: private_external cannot be included in manifest")
        normalized.append(
            {
                "id": rule_id,
                "storage_class": storage_class,
                "retention": retention,
                "provider_independent": bool(raw.get("provider_independent", False)),
                "required": bool(raw.get("required", False)),
                "include_in_manifest": bool(
                    raw.get("include_in_manifest", storage_class != "private_external")
                ),
                "patterns": [x.strip() for x in patterns],
                "note": str(raw.get("note") or "").strip(),
            }
        )

    forbidden = payload.get("forbidden_private_patterns")
    if not isinstance(forbidden, list) or not all(
        isinstance(x, str) and x.strip() for x in forbidden
    ):
        raise ValueError("forbidden_private_patterns must be a list of strings")
    return normalized


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def resolve_pattern(root: Path, pattern: str) -> list[Path]:
    return sorted(p for p in root.glob(pattern) if p.is_file())


def build_manifest(
    root: Path,
    policy: dict[str, Any],
    source_revision: str | None = None,
) -> dict[str, Any]:
    rules = validate_policy(policy)
    forbidden = [str(x).strip() for x in policy.get("forbidden_private_patterns", [])]
    assigned: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    rule_results: list[dict[str, Any]] = []

    for rule in rules:
        matches: list[Path] = []
        for pattern in rule["patterns"]:
            matches.extend(resolve_pattern(root, pattern))
        # Overlap within one rule is harmless; overlap across classes/rules is ambiguous.
        unique = sorted({p.resolve() for p in matches})
        if rule["required"] and not unique:
            raise ValueError(f"required rule matched zero files: {rule['id']}")

        added = 0
        for absolute in unique:
            try:
                rel = absolute.relative_to(root.resolve()).as_posix()
            except ValueError as exc:
                raise ValueError(f"path escaped root: {absolute}") from exc

            if matches_any(rel, forbidden):
                raise ValueError(f"forbidden private path matched by manifest rule: {rel}")
            previous = assigned.get(rel)
            if previous and previous != rule["id"]:
                raise ValueError(
                    f"path assigned by multiple rules: {rel} ({previous}, {rule['id']})"
                )
            assigned[rel] = rule["id"]

            if not rule["include_in_manifest"]:
                continue
            rows.append(
                {
                    "path": rel,
                    "sha256": sha256(absolute),
                    "size_bytes": absolute.stat().st_size,
                    "storage_class": rule["storage_class"],
                    "retention": rule["retention"],
                    "provider_independent": rule["provider_independent"],
                    "rule_id": rule["id"],
                }
            )
            added += 1

        rule_results.append(
            {
                "rule_id": rule["id"],
                "matched_files": len(unique),
                "manifest_files": added,
                "required": rule["required"],
            }
        )

    rows.sort(key=lambda row: row["path"])
    class_counts: dict[str, int] = {}
    total_bytes = 0
    for row in rows:
        class_counts[row["storage_class"]] = class_counts.get(row["storage_class"], 0) + 1
        total_bytes += int(row["size_bytes"])

    return {
        "schema_version": 1,
        "source_revision": source_revision,
        "content_embedded": False,
        "private_payloads_embedded": False,
        "summary": {
            "files": len(rows),
            "bytes": total_bytes,
            "class_counts": dict(sorted(class_counts.items())),
        },
        "rules": rule_results,
        "files": rows,
    }


def self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "data").mkdir()
        (root / "scripts").mkdir()
        (root / "private-backups").mkdir()
        (root / "data" / "public.json").write_text('{"a":1}\n', encoding="utf-8")
        (root / "scripts" / "rebuild.py").write_text("print('ok')\n", encoding="utf-8")
        (root / "private-backups" / "db.dump.gpg").write_bytes(b"encrypted-private-fixture")

        base = {
            "schema_version": 1,
            "forbidden_private_patterns": [
                "private-backups/**",
                "**/*.dump.gpg",
                ".env",
                "**/.env",
            ],
            "rules": [
                {
                    "id": "public",
                    "storage_class": "long_term_public_knowledge",
                    "retention": "long_term",
                    "provider_independent": True,
                    "required": True,
                    "patterns": ["data/*.json"],
                },
                {
                    "id": "rebuild",
                    "storage_class": "rebuild_contract",
                    "retention": "long_term",
                    "provider_independent": True,
                    "required": True,
                    "patterns": ["scripts/*.py"],
                },
            ],
        }

        one = build_manifest(root, base, source_revision="fixture")
        two = build_manifest(root, base, source_revision="fixture")
        assert one == two
        assert one["summary"]["files"] == 2
        assert one["content_embedded"] is False
        assert one["private_payloads_embedded"] is False
        assert not any("private-backups" in row["path"] for row in one["files"])

        before_hash = next(
            row["sha256"] for row in one["files"] if row["path"] == "data/public.json"
        )
        (root / "data" / "public.json").write_text('{"a":2}\n', encoding="utf-8")
        changed = build_manifest(root, base, source_revision="fixture")
        after_hash = next(
            row["sha256"] for row in changed["files"] if row["path"] == "data/public.json"
        )
        assert before_hash != after_hash

        missing = json.loads(json.dumps(base))
        missing["rules"][0]["patterns"] = ["missing/*.json"]
        try:
            build_manifest(root, missing)
        except ValueError as exc:
            assert "matched zero files" in str(exc)
        else:
            raise AssertionError("missing required rule must fail closed")

        duplicate = json.loads(json.dumps(base))
        duplicate["rules"].append(
            {
                "id": "duplicate-public",
                "storage_class": "rebuild_contract",
                "retention": "long_term",
                "provider_independent": True,
                "required": True,
                "patterns": ["data/public.json"],
            }
        )
        try:
            build_manifest(root, duplicate)
        except ValueError as exc:
            assert "multiple rules" in str(exc)
        else:
            raise AssertionError("duplicate assignment must fail closed")

        private = json.loads(json.dumps(base))
        private["rules"].append(
            {
                "id": "bad-private",
                "storage_class": "short_term_diagnostic",
                "retention": "short_term",
                "provider_independent": False,
                "required": True,
                "patterns": ["private-backups/*"],
            }
        )
        try:
            build_manifest(root, private)
        except ValueError as exc:
            assert "forbidden private path" in str(exc)
        else:
            raise AssertionError("private path inclusion must fail closed")

        return {
            "ok": True,
            "cases": 5,
            "deterministic": True,
            "content_embedded": False,
            "private_payloads_embedded": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SWSI portable evidence manifest")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("data/portability_asset_policy.v1.json"),
    )
    parser.add_argument("--source-revision")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        payload = self_test()
    else:
        root = args.root.resolve()
        payload = build_manifest(
            root,
            read_json(args.policy),
            source_revision=args.source_revision,
        )

    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

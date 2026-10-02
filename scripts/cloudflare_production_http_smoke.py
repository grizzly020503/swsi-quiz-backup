#!/usr/bin/env python3
"""Read-only live parity check for SWSI Cloudflare production assets and Worker guards."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CDN = ROOT / "cdn"
ORIGIN = "https://wandering-wave-4418.c022050333.workers.dev"
UA = "SWSI-Cloudflare-Production-Parity/2.0"
PUBLIC_ORIGIN = "https://swsi-quiznetlify.netlify.app"
CURRENT_MODEL = "qwen/qwen3.8-27b"
LEGACY_MODEL = "qwen/qwen3.6-27b"


def fetch(path: str, check: str) -> tuple[int, bytes]:
    url = f"{ORIGIN}{path}?release_check={check}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return int(res.status), res.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()


def post_json(payload: dict, check: str, client_suffix: str) -> tuple[int, dict, dict[str, str]]:
    url = f"{ORIGIN}/api/ai?release_check={check}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "User-Agent": UA,
            "Origin": PUBLIC_ORIGIN,
            "Content-Type": "application/json",
            "X-SWSI-Client-ID": f"prod_parity_{check}_{client_suffix}",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            status = int(res.status)
            raw = res.read()
            headers = {k.lower(): v for k, v in res.headers.items()}
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raw = exc.read()
        headers = {k.lower(): v for k, v in exc.headers.items()}
    try:
        body = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        body = {"_raw": raw.decode("utf-8", "replace")[:500]}
    return status, body, headers


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", default="manual")
    ap.add_argument("--attempts", type=int, default=36)
    ap.add_argument("--sleep", type=float, default=5.0)
    ap.add_argument("--worker-attempts", type=int, default=8)
    args = ap.parse_args()

    expected_index = (CDN / "index.html").read_text(encoding="utf-8")
    expected_patch = (CDN / "monthly_patch.js").read_bytes()
    expected_sw = (CDN / "sw.js").read_bytes()
    expected_manifest = json.loads((CDN / "question-shards" / "manifest.json").read_text(encoding="utf-8"))

    tag = re.search(r'<script src="monthly_patch\.js\?v=([0-9a-f]{16})"></script>', expected_index)
    source = re.search(r'<meta name="swsi-release-source" content="([0-9a-f]{40})">', expected_index)
    if not tag or not source:
        raise SystemExit("Cloudflare production source/cache-bust marker missing from tracked cdn/index.html")

    expected_tag = tag.group(0)
    expected_source = source.group(0)
    expected_revision = str(expected_manifest.get("dataset_revision") or "")
    expected_total = int(expected_manifest.get("total_questions") or 0)
    expected_shards = int(expected_manifest.get("shard_count") or 0)
    if not expected_revision or expected_total != 4800 or expected_shards != 24:
        raise SystemExit(
            f"Tracked question shard manifest contract invalid: revision={expected_revision!r} "
            f"total={expected_total} shards={expected_shards}"
        )

    patch_sha = sha(expected_patch)
    sw_sha = sha(expected_sw)

    last = ""
    static_ready = False
    for attempt in range(1, args.attempts + 1):
        token = f"{args.check}-{attempt}"
        try:
            home_status, home_body = fetch("/", token)
            patch_status, live_patch = fetch("/monthly_patch.js", token)
            sw_status, live_sw = fetch("/sw.js", token)
            manifest_status, manifest_raw = fetch("/question-shards/manifest.json", token)
            shard_status, shard_raw = fetch("/question-shards/115-2.json", token)
            home = home_body.decode("utf-8", "replace")

            try:
                live_manifest = json.loads(manifest_raw.decode("utf-8", "replace"))
            except Exception:
                live_manifest = {}
            try:
                live_shard = json.loads(shard_raw.decode("utf-8", "replace"))
            except Exception:
                live_shard = {}

            shard_questions = live_shard.get("questions") if isinstance(live_shard, dict) else None
            checks = {
                "home_http": home_status == 200,
                "patch_http": patch_status == 200,
                "sw_http": sw_status == 200,
                "manifest_http": manifest_status == 200,
                "shard_115_2_http": shard_status == 200,
                "cache_bust": expected_tag in home,
                "release_source": expected_source in home,
                "soft_launch": "SWSI CLOUDFLARE PUBLIC SOFT LAUNCH" in home,
                "noindex": 'noindex,nofollow,noarchive' in home,
                "no_preview": "SWSI CLOUDFLARE FRONTEND PREVIEW" not in home and "swsi-preview-banner" not in home,
                "patch_bytes": sha(live_patch) == patch_sha,
                "sw_bytes": sha(live_sw) == sw_sha,
                "exam_label": b"swsi-exam-date-label" in live_patch,
                "dataset_revision": live_manifest.get("dataset_revision") == expected_revision,
                "question_total": live_manifest.get("total_questions") == 4800,
                "shard_count": live_manifest.get("shard_count") == 24,
                "shard_115_2_shape": (
                    isinstance(shard_questions, list)
                    and live_shard.get("year") == "115"
                    and live_shard.get("round") == "第二次"
                    and live_shard.get("question_count") == 200
                    and len(shard_questions) == 200
                    and all("accepted_answers" in q for q in shard_questions if isinstance(q, dict))
                ),
            }
            if all(checks.values()):
                static_ready = True
                print(
                    "CLOUDFLARE PRODUCTION STATIC + SHARD PARITY OK "
                    f"attempt={attempt} patch_sha256={patch_sha[:16]} sw_sha256={sw_sha[:16]} "
                    f"source={source.group(1)} dataset_revision={expected_revision}"
                )
                break
            last = ", ".join(f"{k}={v}" for k, v in checks.items())
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"

        print(f"Waiting for Cloudflare production parity: attempt={attempt}/{args.attempts} {last}")
        if attempt < args.attempts:
            time.sleep(args.sleep)

    if not static_ready:
        raise SystemExit(f"CLOUDFLARE PRODUCTION HTTP PARITY FAILED: {last}")

    # These two public requests are deliberately rejected before daily quota/Groq.
    # Together they identify the post-migration Worker: current Qwen 3.8 is accepted,
    # and the one cached Qwen 3.6 public alias is accepted while remaining a local compatibility path.
    current_payload = {
        "model": CURRENT_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "production parity"},
                *[
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AA=="}}
                    for _ in range(4)
                ],
            ],
        }],
    }
    legacy_payload = {
        "model": LEGACY_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "production parity"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}},
            ],
        }],
    }

    worker_last = ""
    for attempt in range(1, args.worker_attempts + 1):
        token = f"{args.check}-worker-{attempt}"
        try:
            current_status, current_body, current_headers = post_json(current_payload, token, "current")
            legacy_status, legacy_body, legacy_headers = post_json(legacy_payload, token, "legacy")
            current_message = str((current_body.get("error") or {}).get("message") or "")
            legacy_message = str((legacy_body.get("error") or {}).get("message") or "")
            checks = {
                "current_model_guard": current_status == 400 and current_message == "最多一次上傳 3 張照片。",
                "legacy_alias_guard": legacy_status == 400 and legacy_message == "公開照片只接受 JPEG 上傳內容。",
                "current_cors": current_headers.get("access-control-allow-origin") == PUBLIC_ORIGIN,
                "legacy_cors": legacy_headers.get("access-control-allow-origin") == PUBLIC_ORIGIN,
            }
            if all(checks.values()):
                print(
                    "CLOUDFLARE PRODUCTION AI WORKER CONTRACT OK "
                    f"attempt={attempt} current={CURRENT_MODEL} legacy_alias={LEGACY_MODEL}"
                )
                print(
                    "CLOUDFLARE PRODUCTION HTTP PARITY OK "
                    f"dataset_revision={expected_revision} total=4800 shards=24"
                )
                return 0
            worker_last = ", ".join(f"{k}={v}" for k, v in checks.items())
        except Exception as exc:
            worker_last = f"{type(exc).__name__}: {exc}"

        print(f"Waiting for Cloudflare Worker parity: attempt={attempt}/{args.worker_attempts} {worker_last}")
        if attempt < args.worker_attempts:
            time.sleep(max(args.sleep, 8.0))

    raise SystemExit(f"CLOUDFLARE PRODUCTION AI WORKER PARITY FAILED: {worker_last}")


if __name__ == "__main__":
    raise SystemExit(main())

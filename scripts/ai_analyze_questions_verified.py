#!/usr/bin/env python3
import json
import os
import time
import requests

import ai_analyze_questions as base

AUDIT_MODEL = os.getenv("AI_AUDIT_MODEL", "openai/gpt-oss-120b")


def request_auditor(prompt, max_tokens, attempts=5):
    body = {
        "model": AUDIT_MODEL,
        "reasoning_effort": "medium",
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    last = None
    for i in range(attempts):
        try:
            r = requests.post(base.AI_PROXY_URL, json=body, timeout=180)
            if r.status_code == 429:
                raise RuntimeError("auditor 429 rate limit")
            r.raise_for_status()
            data = r.json()
            content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content"))
            if not isinstance(content, str):
                raise RuntimeError(f"auditor response shape unexpected: {str(data)[:300]}")
            return json.loads(base.strip_json_fence(content))
        except Exception as e:
            last = e
            if i + 1 < attempts:
                time.sleep(12 * (i + 1))
    raise RuntimeError(f"GPT-OSS 審稿失敗：{last}")


def analyze_and_audit(batch, attempts=4):
    last = None
    for n in range(attempts):
        try:
            # 第一關只驗證 JSON 結構/分類；允許草稿先含多餘細節，交給第二模型刪除。
            real_guard = base.fact_surface_guard
            base.fact_surface_guard = lambda q, row: None
            try:
                draft = base.validate_rows(
                    batch,
                    base.request_model(base.initial_prompt(batch), max(1800, 1200 * len(batch)), 0.2),
                )
            finally:
                base.fact_surface_guard = real_guard

            # 第二關使用不同模型審稿；最終版才套用嚴格防幻覺規則。
            final = base.validate_rows(
                batch,
                request_auditor(base.audit_prompt(batch, draft), max(2000, 1300 * len(batch))),
            )
            return final
        except Exception as e:
            last = e
            if n + 1 < attempts:
                print(f"cross-model validation retry {n+1}: {e}")
                time.sleep(10 * (n + 1))
    raise RuntimeError(f"跨模型雙階段解析仍未通過：{last}")


base.analyze_and_audit = analyze_and_audit

if __name__ == "__main__":
    raise SystemExit(base.main())

#!/usr/bin/env python3
import argparse
import json
import os
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
AI_PROXY_URL = os.getenv("AI_PROXY_URL", "https://wandering-wave-4418.c022050333.workers.dev")
MODEL = os.getenv("AI_MODEL", "qwen/qwen3.6-27b")
UPDATE_URL = os.getenv("ANALYSIS_UPDATE_URL", "https://yumjtrdctaxyczpspuyo.supabase.co/functions/v1/update-question-analysis")
GH_TOKEN = os.getenv("GH_REPO_TOKEN", "")

MISTAKES = {
    "概念混淆", "法規混淆", "理論人物混淆", "流程順序錯誤",
    "計算邏輯錯誤", "關鍵字漏看", "題幹誤讀",
}
MAJORS = {
    "人類行為與社會環境": ["各年齡發展","家庭與社會","發展理論","社區與文化","社會環境系統","心理健康與偏差","人格與情緒","危機與壓力","生理與遺傳","社會化與社會角色","認知與語言","團體與組織"],
    "社會工作": ["社會工作專業","社會工作倫理","社會工作理論","處遇模式","工作技巧","兒少服務","心理健康","老人服務","障礙者服務","性別與婦女服務","多元文化能力","社區工作","社工管理"],
    "社會工作直接服務": ["社區工作","團體工作","處遇模式與理論","評估與處遇計畫","社會工作倫理","個案工作","會談與溝通技巧","專業關係","紀錄與評鑑","社工角色","結案與追蹤","個案管理"],
    "社會工作研究方法": ["資料蒐集","質性方法","研究邏輯","抽樣","研究設計","測量","統計檢定","信效度","研究方法類型","研究倫理","變項","因果關係","資料分析","內容分析","方案評估","縱貫研究","研究典範","推論謬誤","文獻回顧"],
    "社會政策與社會立法": ["其他社會立法與人權公約","社會政策概念與原則","兒少福利法規","社會保險","身心障礙福利法規","福利意識形態與理論","社會救助","老人福利法規","社會政策過程與決策","婦女與性別法規","社會津貼與福利服務","福利國家與體制"],
}
FIELDS = ["id","major","topic","keywords","exp_why","exp_others","exp_trap","mnemonic","extension","law","mistake"]


def strip_json_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    if text.startswith("[") and text.endswith("]"):
        return text
    a, b = text.find("["), text.rfind("]")
    if a >= 0 and b > a:
        return text[a:b+1]
    raise ValueError("AI 回傳找不到 JSON array")


def prompt_for(batch):
    subject_rules = {s: MAJORS[s] for s in sorted({q["subject"] for q in batch})}
    tasks = []
    for q in batch:
        tasks.append({
            "id": q["id"], "subject": q["subject"], "question": q["question"],
            "A": q["opt_a"], "B": q["opt_b"], "C": q["opt_c"], "D": q["opt_d"],
            "official_answer": q["answer"],
        })
    return f"""你是台灣『社會工作師國家考試』選擇題解析器。官方題目與官方答案已由考選部確認。

硬性規則：
1. 絕對不要質疑、修改或重寫官方題目、選項、答案；你只產生解析欄位。
2. 每題 major 必須從該科允許清單擇一：{json.dumps(subject_rules, ensure_ascii=False)}
3. mistake 只能從：{json.dumps(sorted(MISTAKES), ensure_ascii=False)}
4. topic 格式盡量為「主題 > 細目」。keywords 用半形逗號分隔 3~7 個關鍵詞。
5. exp_why 要直接說明官方正解為何成立；exp_others 說明其餘選項錯在哪；exp_trap 點出考場陷阱。
6. mnemonic 要短而可記；extension 補一個相鄰考點。
7. law：只有確定時才寫法規名稱/條文重點；不確定條號就不要猜條號。非法律題可填空字串。
8. 用繁體中文，語氣與既有題庫一致，簡潔但要足以複習。
9. 只輸出 JSON array，禁止 Markdown、前言、結語。
10. 每個物件只能有這些 key：{json.dumps(FIELDS, ensure_ascii=False)}，且 id 必須原樣返回。

待解析題目：
{json.dumps(tasks, ensure_ascii=False)}"""


def call_ai(batch, attempts=5):
    body = {
        "model": MODEL,
        "reasoning_effort": "none",
        "temperature": 0.2,
        "max_tokens": max(1800, 1250 * len(batch)),
        "messages": [{"role": "user", "content": prompt_for(batch)}],
    }
    last = None
    for i in range(attempts):
        try:
            r = requests.post(AI_PROXY_URL, json=body, timeout=120)
            if r.status_code == 429:
                raise RuntimeError("AI 429 rate limit")
            r.raise_for_status()
            data = r.json()
            content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content"))
            if not isinstance(content, str):
                raise RuntimeError(f"AI response shape unexpected: {str(data)[:300]}")
            return json.loads(strip_json_fence(content))
        except Exception as e:
            last = e
            if i + 1 < attempts:
                time.sleep(8 * (i + 1))
    raise RuntimeError(f"AI 呼叫失敗：{last}")


def validate_rows(batch, rows):
    expected = {q["id"]: q for q in batch}
    if not isinstance(rows, list) or len(rows) != len(batch):
        raise ValueError(f"AI 筆數不符：expected={len(batch)} got={len(rows) if isinstance(rows,list) else 'not-list'}")
    out = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise ValueError(f"AI 欄位不符：{row}")
        qid = str(row.get("id") or "")
        if qid not in expected or qid in seen:
            raise ValueError(f"AI id 異常：{qid}")
        seen.add(qid)
        q = expected[qid]
        if row["major"] not in MAJORS[q["subject"]]:
            raise ValueError(f"{qid} major 不在既有分類：{row['major']}")
        if row["mistake"] not in MISTAKES:
            raise ValueError(f"{qid} mistake 不在既有分類：{row['mistake']}")
        for k in FIELDS:
            if k == "law":
                if not isinstance(row[k], str): raise ValueError(f"{qid}.{k} 非字串")
            elif not isinstance(row[k], str) or not row[k].strip():
                raise ValueError(f"{qid}.{k} 空白")
        out.append({k: row[k].strip() if isinstance(row[k], str) else row[k] for k in FIELDS})
    return out


def push_supabase(exam_code, rows):
    if not GH_TOKEN:
        raise RuntimeError("缺 GH_REPO_TOKEN，不能寫回 Supabase")
    r = requests.post(
        UPDATE_URL,
        headers={"Authorization": f"Bearer {GH_TOKEN}", "Content-Type": "application/json"},
        json={"exam_code": exam_code, "rows": rows},
        timeout=90,
    )
    if not r.ok:
        raise RuntimeError(f"Supabase analysis update {r.status_code}: {r.text[:500]}")
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam", required=True)
    ap.add_argument("--batch-size", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0, help="0=全部剩餘題")
    ap.add_argument("--output", default="")
    ap.add_argument("--write-supabase", action="store_true")
    args = ap.parse_args()

    src = ROOT / "incoming" / f"{args.exam}.json"
    if not src.exists(): raise SystemExit(f"找不到 {src}")
    exam = json.loads(src.read_text(encoding="utf-8"))
    if exam.get("exam_code") != args.exam: raise SystemExit("exam_code 不一致")
    qs = exam.get("questions") or []
    if len(qs) != 200: raise SystemExit(f"官方題數不是 200：{len(qs)}")

    outpath = ROOT / (args.output or f"analysis/{args.exam}.json")
    outpath.parent.mkdir(parents=True, exist_ok=True)
    saved = {"exam_code": args.exam, "model": MODEL, "rows": []}
    if outpath.exists():
        try: saved = json.loads(outpath.read_text(encoding="utf-8"))
        except Exception: pass
    rowmap = {r["id"]: r for r in saved.get("rows", []) if isinstance(r, dict) and r.get("id")}
    todo = [q for q in qs if q.get("analysis_status") == "pending" and q["id"] not in rowmap]
    if args.limit > 0: todo = todo[:args.limit]
    print(f"exam={args.exam} existing={len(rowmap)} todo={len(todo)}")

    for pos in range(0, len(todo), max(1, args.batch_size)):
        batch = todo[pos:pos + max(1, args.batch_size)]
        rows = validate_rows(batch, call_ai(batch))
        if args.write_supabase:
            print(push_supabase(args.exam, rows))
        for r in rows: rowmap[r["id"]] = r
        saved = {"exam_code": args.exam, "model": MODEL, "rows": [rowmap[k] for k in sorted(rowmap)]}
        outpath.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved {len(rowmap)} analyses -> {outpath}")
        time.sleep(2)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())

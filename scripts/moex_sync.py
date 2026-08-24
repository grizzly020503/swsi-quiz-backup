#!/usr/bin/env python3
import argparse
import io
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from pypdf import PdfReader

BASE = "https://wwwq.moex.gov.tw/exam"
TARGET_CATEGORY_LABELS = ("專技高考_社會工作師", "高等考試_社會工作師")
TARGET_CLASS_NAME = "社會工作師"
TARGET_EXAM_PHRASE = "專門職業及技術人員高等考試"
SUBJECTS = [
    {"s":"0301","name":"社會工作","prefix":"SW"},
    {"s":"0302","name":"社會工作直接服務","prefix":"DS"},
    {"s":"0303","name":"社會政策與社會立法","prefix":"SP"},
    {"s":"0304","name":"人類行為與社會環境","prefix":"HBSE"},
    {"s":"0305","name":"社會工作研究方法","prefix":"R"},
]
OPTION_MARKERS = {
    "\ue18c":"A", "\ue18d":"B", "\ue18e":"C", "\ue18f":"D",
    "":"A", "":"B", "":"C", "":"D",
    "①":"A", "②":"B", "③":"C", "④":"D",
}
UA = "Mozilla/5.0 (compatible; swsi-quiz-moex-sync/1.1; +https://github.com/grizzly020503/swsi-quiz-backup)"


def pdf_url(exam_code, subject_code, kind):
    return f"{BASE}/wHandExamQandA_File.ashx?c=103&code={exam_code}&q=1&s={subject_code}&t={kind}"


def exam_url(exam_code):
    year = int(exam_code[:3]) + 1911
    return f"{BASE}/wFrmExamQandASearch.aspx?e={exam_code}&y={year}"


def get_bytes(url):
    r = requests.get(url, timeout=45, headers={"User-Agent": UA})
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise RuntimeError(f"不是 PDF：{url} (content-type={r.headers.get('content-type')})")
    return r.content


def pdf_text(data):
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def clean(s):
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def compact_text(s):
    return re.sub(r"\s+", "", s or "")


def normalize_option_markers(text):
    for ch, letter in OPTION_MARKERS.items():
        text = text.replace(ch, f"\n@@{letter}@@ ")
    text = re.sub(r"(?m)^\s*([ＡＢＣＤABCD])[\.、．]\s*", lambda m: f"\n@@{m.group(1).translate(str.maketrans('ＡＢＣＤ','ABCD'))}@@ ", text)
    return text


def strip_headers(text):
    lines = []
    for line in text.splitlines():
        t = line.strip()
        if not t:
            continue
        if re.search(r"^頁次[:：]", t) or re.search(r"^代號[:：]", t):
            continue
        if TARGET_EXAM_PHRASE in t and "試題" in t:
            continue
        if t.startswith("等 別：") or t.startswith("類 科：") or t.startswith("科 目：") or t.startswith("考試時間："):
            continue
        lines.append(line)
    return "\n".join(lines)


def validate_question_pdf(text, subject):
    """硬性防呆：PDF 必須是專技高考社會工作師，而且科目名稱必須完全對得上。"""
    compact = compact_text(text)
    if TARGET_EXAM_PHRASE not in compact:
        raise RuntimeError(f"拒絕匯入：{subject['name']} PDF 不是專門職業及技術人員高等考試試題")
    if f"類科：{TARGET_CLASS_NAME}" not in compact and f"類科:{TARGET_CLASS_NAME}" not in compact:
        raise RuntimeError(f"拒絕匯入：PDF 類科不是「{TARGET_CLASS_NAME}」")
    if f"科目：{subject['name']}" not in compact and f"科目:{subject['name']}" not in compact:
        raise RuntimeError(f"拒絕匯入：預期科目「{subject['name']}」，但 PDF 標頭不符")


def parse_essays(text, subject, exam_code, roc_year, round_name):
    if "甲、申論題部分" not in text or "乙、測驗題部分" not in text:
        return []
    part = text.split("甲、申論題部分", 1)[1].split("乙、測驗題部分", 1)[0]
    part = strip_headers(part)
    matches = list(re.finditer(r"(?m)^\s*([一二])、\s*", part))
    essays = []
    for i, m in enumerate(matches[:2]):
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(part)
        body = clean(part[start:end])
        body = re.sub(r"^[（(]40\s*分[）)]\s*", "", body)
        points_m = re.search(r"[（(](\d+)\s*分[）)]\s*$", body)
        points = points_m.group(1) if points_m else "20"
        qno = str(i+1)
        essays.append({
            "id": f"E-{roc_year}-{2 if round_name=='第二次' else 1}-{subject['prefix']}-{qno}",
            "subject": subject["name"], "year": roc_year, "round": round_name,
            "qno": qno, "q": body, "points": points,
            "topic": None, "major": None, "keywords": [], "theories": [], "laws": [],
            "difficulty": None, "frequency": None, "qtype": None, "related": [],
            "cluster": None, "cluster_name": None,
            "source_exam_code": exam_code, "source_url": pdf_url(exam_code, subject['s'], 'Q'),
            "analysis_status": "pending"
        })
    return essays


def split_question_blocks(text):
    if "乙、測驗題部分" not in text:
        raise RuntimeError("找不到測驗題區段")
    text = text.split("乙、測驗題部分", 1)[1]
    text = strip_headers(text)
    first = re.search(r"(?m)^\s*1\s+", text)
    if not first:
        raise RuntimeError("找不到第 1 題")
    text = text[first.start():]
    starts = list(re.finditer(r"(?m)^\s*(\d{1,2})\s+", text))
    starts = [m for m in starts if 1 <= int(m.group(1)) <= 40]
    chosen = []
    expected = 1
    for m in starts:
        n = int(m.group(1))
        if n == expected:
            chosen.append(m)
            expected += 1
            if expected == 41:
                break
    if len(chosen) != 40:
        raise RuntimeError(f"題號解析失敗：只找到 {len(chosen)} / 40 題")
    blocks = []
    for i, m in enumerate(chosen):
        start = m.end()
        end = chosen[i+1].start() if i+1 < len(chosen) else len(text)
        blocks.append((int(m.group(1)), text[start:end]))
    return blocks


def parse_mc(text, subject, exam_code, roc_year, round_name, answers):
    rows = []
    for qno, raw in split_question_blocks(text):
        marked = normalize_option_markers(raw)
        parts = re.split(r"@@([ABCD])@@", marked)
        stem = clean(parts[0])
        opts = {}
        for i in range(1, len(parts)-1, 2):
            letter = parts[i]
            val = clean(parts[i+1])
            opts[letter] = val
        if set(opts) != {"A","B","C","D"}:
            raise RuntimeError(f"{subject['name']} 第 {qno} 題選項解析失敗：{sorted(opts)}")
        for k in opts:
            opts[k] = re.sub(r"\s*代號[:：]\s*\d+\s*$", "", opts[k]).strip()
        rows.append({
            "id": f"{subject['prefix']}-{roc_year}-{2 if round_name=='第二次' else 1}-{qno:03d}",
            "subject": subject["name"], "year": roc_year, "round": round_name, "qno": str(qno),
            "major": None, "topic": None, "keywords": None,
            "question": stem, "opt_a": opts["A"], "opt_b": opts["B"], "opt_c": opts["C"], "opt_d": opts["D"],
            "answer": answers[qno-1],
            "exp_why": None, "exp_others": None, "exp_trap": None, "exp_raw": None,
            "mnemonic": None, "extension": None, "law": None, "mistake": None,
            "source_exam_code": exam_code, "source_url": pdf_url(exam_code, subject['s'], 'Q'),
            "analysis_status": "pending"
        })
    return rows


def parse_answers(text):
    compact = re.sub(r"[^A-D]", "", text.upper())
    pos = text.find("答案")
    if pos >= 0:
        tail = re.sub(r"[^A-D]", "", text[pos:].upper())
        if len(tail) >= 40:
            return list(tail[:40])
    if len(compact) >= 40:
        return list(compact[-40:])
    raise RuntimeError(f"標準答案解析失敗：只找到 {len(compact)} 個 A-D 字元")


def exam_exists(exam_code):
    # 考選部頁面偶爾未正確宣告中文字元編碼，requests 的 r.text 可能誤判。
    # 此處只確認考試頁可存取；真正的類科/科目驗證由每份官方 PDF 完成。
    url = exam_url(exam_code)
    r = requests.get(url, timeout=30, headers={"User-Agent": UA})
    return r.status_code == 200 and len(r.content) > 1000


def build_exam(exam_code):
    roc_year = exam_code[:3]
    suffix = exam_code[3:]
    round_name = "第一次" if suffix == "030" else "第二次" if suffix == "100" else "未知"
    if round_name == "未知":
        raise RuntimeError(f"拒絕匯入：{exam_code} 不是本站允許的社會工作師第一次/第二次考試代碼")
    if not exam_exists(exam_code):
        raise RuntimeError(f"拒絕匯入：考選部頁面未確認為專技高考社會工作師考試：{exam_code}")
    all_mc, all_essays = [], []
    stats = {}
    for subject in SUBJECTS:
        q_url = pdf_url(exam_code, subject["s"], "Q")
        a_url = pdf_url(exam_code, subject["s"], "S")
        q_text = pdf_text(get_bytes(q_url))
        validate_question_pdf(q_text, subject)
        a_text = pdf_text(get_bytes(a_url))
        answers = parse_answers(a_text)
        mc = parse_mc(q_text, subject, exam_code, roc_year, round_name, answers)
        essays = parse_essays(q_text, subject, exam_code, roc_year, round_name)
        if len(mc) != 40:
            raise RuntimeError(f"{subject['name']} 選擇題不是 40 題")
        if len(essays) != 2:
            raise RuntimeError(f"{subject['name']} 申論題不是 2 題")
        all_mc.extend(mc)
        all_essays.extend(essays)
        stats[subject["name"]] = {"mc": len(mc), "essay": len(essays)}
    if len(all_mc) != 200 or len(all_essays) != 10:
        raise RuntimeError(f"總題數異常：選擇 {len(all_mc)}、申論 {len(all_essays)}")
    actual_subjects = {q["subject"] for q in all_mc}
    expected_subjects = {s["name"] for s in SUBJECTS}
    if actual_subjects != expected_subjects:
        raise RuntimeError(f"拒絕匯入：科目集合不符，實際={sorted(actual_subjects)}")
    return {
        "exam_type": "專門職業及技術人員高等考試社會工作師",
        "exam_code": exam_code, "roc_year": roc_year, "round": round_name,
        "source_page": exam_url(exam_code),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats, "questions": all_mc, "essays": all_essays
    }


def default_candidates():
    tz = timezone(timedelta(hours=8))
    roc = datetime.now(tz).year - 1911
    # 本站只掃當年度社會工作師的兩個固定場次，不掃其他專技高考類科或考試。
    return [f"{roc}030", f"{roc}100"]


def main():
    ap = argparse.ArgumentParser(description="僅同步考選部『專技高考社會工作師』題庫")
    ap.add_argument("--exam", action="append", help="指定社會工作師考試代碼，可重複；僅接受 xxx030/xxx100")
    ap.add_argument("--output-dir", default="incoming")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    candidates = args.exam or default_candidates()
    wrote = 0
    for code in candidates:
        if not re.fullmatch(r"\d{3}(030|100)", code):
            raise RuntimeError(f"拒絕匯入：不允許的考試代碼 {code}")
        out = outdir / f"{code}.json"
        if args.skip_existing and out.exists():
            print(f"skip existing {code}")
            continue
        try:
            data = build_exam(code)
        except Exception as e:
            print(f"{code}: {e}", file=sys.stderr)
            if args.exam:
                raise
            continue
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out}: {len(data['questions'])} MC + {len(data['essays'])} essays")
        wrote += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

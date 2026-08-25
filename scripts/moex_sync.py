#!/usr/bin/env python3
import argparse
import io
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pdfplumber
import requests
from pypdf import PdfReader

BASE = "https://wwwq.moex.gov.tw/exam"
TARGET_CLASS_NAME = "社會工作師"
TARGET_EXAM_PHRASE = "專門職業及技術人員高等考試"
SUBJECTS = [
    {"s": "0301", "name": "社會工作", "prefix": "SW"},
    {"s": "0302", "name": "社會工作直接服務", "prefix": "DS"},
    {"s": "0303", "name": "社會政策與社會立法", "prefix": "SP"},
    {"s": "0304", "name": "人類行為與社會環境", "prefix": "HBSE"},
    {"s": "0305", "name": "社會工作研究方法", "prefix": "R"},
]
# 考選部試題真正的選項符號。注意：①②③④⑤可能出現在題幹內，絕不能當成 A/B/C/D。
OPTION_MARKERS = {
    "\ue18c": "A", "\ue18d": "B", "\ue18e": "C", "\ue18f": "D",
    "": "A", "": "B", "": "C", "": "D",
}
ALL_ANSWERS = {"A", "B", "C", "D"}
FW = str.maketrans("ＡＢＣＤ＃", "ABCD#")
UA = "Mozilla/5.0 (compatible; swsi-quiz-moex-sync/1.3; +https://github.com/grizzly020503/swsi-quiz-backup)"


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


def try_get_bytes(url):
    """Optional official PDF: return None when the endpoint has no PDF.

    MOEX uses t=M for corrected-answer sheets. When no correction exists the
    endpoint may return HTML or a non-success response, which is not an error;
    callers should fall back to t=S. If a PDF is returned, it is validated later.
    """
    try:
        r = requests.get(url, timeout=45, headers={"User-Agent": UA})
    except requests.RequestException:
        return None
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        return None
    return r.content


def pdf_text(data):
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def clean(s):
    s = str(s or "").replace("\u3000", " ").replace("\xa0", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def compact_text(s):
    return re.sub(r"\s+", "", s or "")


def normalize_option_markers(text):
    for ch, letter in OPTION_MARKERS.items():
        text = text.replace(ch, f"\n@@{letter}@@ ")
    # 少數年度若直接以 A. / B. / C. / D. 作為行首選項，也允許解析。
    text = re.sub(
        r"(?m)^\s*([ＡＢＣＤABCD])[\.、．]\s*",
        lambda m: f"\n@@{m.group(1).translate(str.maketrans('ＡＢＣＤ', 'ABCD'))}@@ ",
        text,
    )
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
        compact = re.sub(r"\s+", "", t)
        if compact.startswith("等別：") or compact.startswith("類科：") or compact.startswith("科目：") or compact.startswith("考試時間："):
            continue
        lines.append(line)
    return "\n".join(lines)


def validate_question_pdf(text, subject):
    compact = compact_text(text)
    if TARGET_EXAM_PHRASE not in compact:
        raise RuntimeError(f"拒絕匯入：{subject['name']} PDF 不是專門職業及技術人員高等考試試題")
    if f"類科：{TARGET_CLASS_NAME}" not in compact and f"類科:{TARGET_CLASS_NAME}" not in compact:
        raise RuntimeError(f"拒絕匯入：PDF 類科不是「{TARGET_CLASS_NAME}」")
    if f"科目：{subject['name']}" not in compact and f"科目:{subject['name']}" not in compact:
        raise RuntimeError(f"拒絕匯入：預期科目「{subject['name']}」，但 PDF 標頭不符")


def validate_answer_pdf(text, subject):
    compact = compact_text(text)
    if TARGET_CLASS_NAME not in compact:
        raise RuntimeError(f"拒絕匯入：{subject['name']} 答案 PDF 類科不是社會工作師")
    if subject["name"] not in compact:
        raise RuntimeError(f"拒絕匯入：答案 PDF 科目不是「{subject['name']}」")
    if not any(marker in compact for marker in ("測驗式試題標準答案", "更正答案", "答案更正")):
        raise RuntimeError(f"拒絕匯入：{subject['name']} 找不到官方答案標示")


def parse_essays(text, subject, exam_code, roc_year, round_name):
    if "甲、申論題部分" not in text or "乙、測驗題部分" not in text:
        return []
    part = text.split("甲、申論題部分", 1)[1].split("乙、測驗題部分", 1)[0]
    part = strip_headers(part)
    matches = list(re.finditer(r"(?m)^\s*([一二])、\s*", part))
    essays = []
    for i, m in enumerate(matches[:2]):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(part)
        body = clean(part[start:end])
        score_values = [int(x) for x in re.findall(r"[（(](\d+)\s*分[）)]", body)]
        if len(score_values) > 1 and sum(score_values) <= 40:
            points = str(sum(score_values))
        elif score_values:
            points = str(score_values[-1])
        else:
            points = "20"
        qno = str(i + 1)
        essays.append({
            "id": f"E-{roc_year}-{2 if round_name == '第二次' else 1}-{subject['prefix']}-{qno}",
            "subject": subject["name"], "year": roc_year, "round": round_name,
            "qno": qno, "q": body, "points": points,
            "topic": None, "major": None, "keywords": [], "theories": [], "laws": [],
            "difficulty": None, "frequency": None, "qtype": None, "related": [],
            "cluster": None, "cluster_name": None,
            "source_exam_code": exam_code, "source_url": pdf_url(exam_code, subject["s"], "Q"),
            "analysis_status": "pending",
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
        end = chosen[i + 1].start() if i + 1 < len(chosen) else len(text)
        blocks.append((int(m.group(1)), text[start:end]))
    return blocks


def parse_mc(text, subject, exam_code, roc_year, round_name, answer_rules):
    rows = []
    for qno, raw in split_question_blocks(text):
        marked = normalize_option_markers(raw)
        parts = re.split(r"@@([ABCD])@@", marked)
        stem = clean(parts[0])
        opts = {}
        for i in range(1, len(parts) - 1, 2):
            letter = parts[i]
            val = clean(parts[i + 1])
            opts[letter] = val
        if set(opts) != {"A", "B", "C", "D"}:
            raise RuntimeError(f"{subject['name']} 第 {qno} 題選項解析失敗：{sorted(opts)}")
        for k in opts:
            opts[k] = re.sub(r"\s*代號[:：]\s*\d+\s*$", "", opts[k]).strip()
            if not opts[k]:
                raise RuntimeError(f"{subject['name']} 第 {qno} 題 {k} 選項為空白")
        if not stem:
            raise RuntimeError(f"{subject['name']} 第 {qno} 題題幹為空白")
        rule = answer_rules[qno - 1]
        row = {
            "id": f"{subject['prefix']}-{roc_year}-{2 if round_name == '第二次' else 1}-{qno:03d}",
            "subject": subject["name"], "year": roc_year, "round": round_name, "qno": str(qno),
            "major": None, "topic": None, "keywords": None,
            "question": stem, "opt_a": opts["A"], "opt_b": opts["B"], "opt_c": opts["C"], "opt_d": opts["D"],
            "answer": rule["answer"],
            "exp_why": None, "exp_others": None, "exp_trap": None, "exp_raw": None,
            "mnemonic": None, "extension": None, "law": None, "mistake": None,
            "source_exam_code": exam_code, "source_url": pdf_url(exam_code, subject["s"], "Q"),
            "analysis_status": "pending",
        }
        # 單一答案維持舊 payload 完全不變；只有官方真的接受多答案時才新增欄位。
        if rule.get("accepted_answers"):
            row["accepted_answers"] = rule["accepted_answers"]
        rows.append(row)
    return rows


def _answer_value(value):
    t = clean(value).upper().replace(" ", "").translate(FW)
    if t in ALL_ANSWERS or t == "#":
        return t
    if "一律給分" in t:
        return "一律給分"
    return None


def _parse_correction_rules(text, raw_answers):
    """Resolve MOEX # / correction-note rules into platform-safe answer metadata."""
    note = compact_text(text).upper().translate(FW)
    accepted = {}

    for m in re.finditer(r"第(\d{1,2})題([^第]*)", note):
        qno = int(m.group(1))
        body = m.group(2)
        if not 1 <= qno <= 40:
            continue
        if "一律給分" in body or ("未作答者不給分" in body and "其餘均給分" in body):
            accepted[qno] = set(ALL_ANSWERS)
            continue
        if "給分" in body and "答" in body:
            between = body.split("答", 1)[1].split("給分", 1)[0]
            letters = set(re.findall(r"[ABCD]", between))
            if letters:
                accepted[qno] = letters

    for qno, token in enumerate(raw_answers, start=1):
        if token == "一律給分":
            accepted.setdefault(qno, set(ALL_ANSWERS))
        elif token in ALL_ANSWERS:
            accepted.setdefault(qno, {token})
        elif token == "#":
            if qno not in accepted:
                marker = f"第{qno}題"
                p = note.find(marker)
                excerpt = note[p:p + 160] if p >= 0 else note[:240]
                raise RuntimeError(
                    f"官方更正答案第 {qno} 題為 #，但無法解析最終給分規則：{excerpt!r}"
                )
        else:
            raise RuntimeError(f"官方答案第 {qno} 題出現未知標記：{token!r}")

    if len(accepted) != 40:
        raise RuntimeError(f"官方更正答案只解析出 {len(accepted)} / 40 題")

    rules = []
    for qno in range(1, 41):
        answers = sorted(accepted[qno])
        if set(answers) == ALL_ANSWERS:
            rules.append({"answer": "一律給分"})
        elif len(answers) == 1:
            rules.append({"answer": answers[0]})
        else:
            rules.append({"answer": answers[0], "accepted_answers": answers})
    return rules


def parse_answers_pdf(data):
    """依答案 PDF 實際座標配對題號與答案，再解析官方更正規則。"""
    found = {}
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(
                use_text_flow=False,
                keep_blank_chars=False,
                x_tolerance=2,
                y_tolerance=2,
            ) or []
            qwords = []
            awords = []
            for w in words:
                raw = clean(w.get("text", ""))
                compact = re.sub(r"\s+", "", raw)
                qm = re.fullmatch(r"第(\d+)題", compact)
                if qm:
                    qno = int(qm.group(1))
                    if 1 <= qno <= 40:
                        qwords.append({
                            "qno": qno,
                            "cx": (float(w["x0"]) + float(w["x1"])) / 2,
                            "top": float(w["top"]),
                            "bottom": float(w["bottom"]),
                        })
                    continue
                ans = _answer_value(raw)
                if ans:
                    awords.append({
                        "answer": ans,
                        "cx": (float(w["x0"]) + float(w["x1"])) / 2,
                        "top": float(w["top"]),
                        "bottom": float(w["bottom"]),
                    })

            # 每個題號只找同一欄、緊接在題號列下方的答案。
            for q in qwords:
                candidates = []
                for a in awords:
                    dx = abs(a["cx"] - q["cx"])
                    dy = a["top"] - q["bottom"]
                    if dx <= 24 and -3 <= dy <= 30:
                        candidates.append((dx + abs(dy) * 0.20, a))
                if not candidates:
                    continue
                candidates.sort(key=lambda x: x[0])
                ans = candidates[0][1]["answer"]
                old = found.get(q["qno"])
                if old and old != ans:
                    raise RuntimeError(f"官方答案座標解析衝突：第 {q['qno']} 題同時得到 {old}/{ans}")
                found[q["qno"]] = ans

    missing = [n for n in range(1, 41) if n not in found]
    if missing:
        raise RuntimeError(f"官方答案座標解析失敗，缺少題號：{missing}")
    if len(found) != 40:
        raise RuntimeError(f"官方答案座標解析題數異常：{len(found)}")

    raw_answers = [found[n] for n in range(1, 41)]
    return _parse_correction_rules(pdf_text(data), raw_answers)


def exam_exists(exam_code):
    # 考試頁只做存取檢查；真正類科與科目由每份官方 PDF 再做硬性驗證。
    r = requests.get(exam_url(exam_code), timeout=30, headers={"User-Agent": UA})
    return r.status_code == 200 and len(r.content) > 1000


def build_exam(exam_code):
    roc_year = exam_code[:3]
    suffix = exam_code[3:]
    round_name = "第一次" if suffix == "030" else "第二次" if suffix == "100" else "未知"
    if round_name == "未知":
        raise RuntimeError(f"拒絕匯入：{exam_code} 不是本站允許的社會工作師第一次/第二次考試代碼")
    if not exam_exists(exam_code):
        raise RuntimeError(f"考選部尚無可讀取的考試頁：{exam_code}")

    all_mc, all_essays = [], []
    stats = {}
    for subject in SUBJECTS:
        q_url = pdf_url(exam_code, subject["s"], "Q")
        s_url = pdf_url(exam_code, subject["s"], "S")
        m_url = pdf_url(exam_code, subject["s"], "M")
        q_data = get_bytes(q_url)
        # 更正答案 M 優先；沒有 M 才退回標準答案 S。
        a_data = try_get_bytes(m_url)
        answer_kind = "M" if a_data is not None else "S"
        if a_data is None:
            a_data = get_bytes(s_url)
        q_text = pdf_text(q_data)
        a_text = pdf_text(a_data)
        validate_question_pdf(q_text, subject)
        validate_answer_pdf(a_text, subject)
        answer_rules = parse_answers_pdf(a_data)
        mc = parse_mc(q_text, subject, exam_code, roc_year, round_name, answer_rules)
        essays = parse_essays(q_text, subject, exam_code, roc_year, round_name)
        if len(mc) != 40:
            raise RuntimeError(f"{subject['name']} 選擇題不是 40 題")
        if len(essays) != 2:
            raise RuntimeError(f"{subject['name']} 申論題不是 2 題")
        all_mc.extend(mc)
        all_essays.extend(essays)
        stats[subject["name"]] = {"mc": len(mc), "essay": len(essays)}
        multi = sum(1 for r in answer_rules if r.get("accepted_answers"))
        print(f"{exam_code} {subject['name']}: official answers {answer_kind}, multi={multi}")

    if len(all_mc) != 200 or len(all_essays) != 10:
        raise RuntimeError(f"總題數異常：選擇 {len(all_mc)}、申論 {len(all_essays)}")
    actual_subjects = {q["subject"] for q in all_mc}
    expected_subjects = {s["name"] for s in SUBJECTS}
    if actual_subjects != expected_subjects:
        raise RuntimeError(f"拒絕匯入：科目集合不符，實際={sorted(actual_subjects)}")

    return {
        "exam_type": "專門職業及技術人員高等考試社會工作師",
        "exam_code": exam_code,
        "roc_year": roc_year,
        "round": round_name,
        "source_page": exam_url(exam_code),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "questions": all_mc,
        "essays": all_essays,
    }


def default_candidates():
    tz = timezone(timedelta(hours=8))
    roc = datetime.now(tz).year - 1911
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
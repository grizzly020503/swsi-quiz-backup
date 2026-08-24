#!/usr/bin/env python3
# Triggered after repair workflow is present; installs coordinate-based MOEX answer parsing.
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'scripts' / 'moex_sync.py'
s = p.read_text(encoding='utf-8')
start = s.index('def parse_answers_pdf(data):')
end = s.index('\ndef exam_exists(', start)
new = r'''def _answer_value(value):
    t = clean(value).upper().replace(" ", "")
    if t in {"A", "B", "C", "D"}:
        return t
    if "一律給分" in t:
        return "一律給分"
    return None


def parse_answers_pdf(data):
    """依答案 PDF 的實際座標，把「第 N 題」與正下方答案配對。

    不再依賴 extract_tables() 的欄位索引，因為考選部 PDF 在部分列會被
    pdfplumber 拆成不同欄數，可能造成答案錯位但又剛好湊滿 40 題。
    """
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
    return [found[n] for n in range(1, 41)]

'''
s = s[:start] + new + s[end:]
p.write_text(s, encoding='utf-8')
print('installed coordinate-based official-answer parser')

#!/usr/bin/env python3
import json
from pathlib import Path

PATH = Path('index.html')
START = 'window.ESSAYS = '
END = ';\n\nwindow.CLUSTER_ANCHORS = '

PATCHES = {
    '社會工作-109-1-申論2': '兒童少年保護工作中，有關安全評估的重點為何？要考慮那些安全計畫？（25 分）',
    '社會工作研究方法-107-2-申論2': '請說明何謂「參與式行動研究（Participatory Action Research）」？此種研究方法特色是什麼？那些議題適合採用這種研究方法？（25 分）',
    '社會工作研究方法-105-1-申論1': '要完成一項研究需要有詳實的規劃，做為進行研究之依據。因此，請詳述一份完整的研究計畫書應該包含那些內容？（25 分）',
    '社會工作研究方法-105-1-申論2': '問卷是進行調查研究時重要的研究工具，請詳述當研究者進行設計一份問卷時，應該遵守那些原則？（25 分）',
    '社會工作研究方法-104-2-申論1': '在社會工作質性研究法中，「焦點團體法」（focus group）經常被學者或實務專家用來蒐集資料，請說明何謂焦點團體法？並且進一步說明焦點團體法具備那些優點和限制。（25 分）',
    '社會工作研究方法-104-2-申論2': '請詳述「隨機抽樣」（random sampling）的4種類型。（25 分）',
}


def main():
    text = PATH.read_text(encoding='utf-8')
    a = text.index(START) + len(START)
    b = text.index(END, a)
    rows = json.loads(text[a:b])
    by_id = {r['id']: r for r in rows}

    missing = sorted(set(PATCHES) - set(by_id))
    if missing:
        raise SystemExit('missing IDs: ' + ', '.join(missing))

    for eid, q in PATCHES.items():
        by_id[eid]['q'] = q
        by_id[eid]['points'] = '25'

    encoded = json.dumps(rows, ensure_ascii=False, separators=(',', ':'))
    PATH.write_text(text[:a] + encoded + text[b:], encoding='utf-8')

    # All embedded historical questions should now carry the official score marker.
    final = PATH.read_text(encoding='utf-8')
    a2 = final.index(START) + len(START)
    b2 = final.index(END, a2)
    check_rows = json.loads(final[a2:b2])
    no_score = [r['id'] for r in check_rows if '分' not in str(r.get('q') or '')]
    if no_score:
        raise SystemExit('questions still missing score marker: ' + ', '.join(no_score))
    print(f'Patched {len(PATCHES)} verified historical essay score lines.')


if __name__ == '__main__':
    main()

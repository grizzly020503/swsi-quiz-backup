#!/usr/bin/env python3
"""Sanitize public-only study-guide content before deployment.

The legacy reader guide was assembled from third-party senior-student notes that
were appropriate for private study but should not be redistributed by the public
SWSI site without an explicit publication licence. Replace that entire legacy
DATA block and related public labels with SWSI-authored material, then fail
closed if attribution/name markers survive into the built artifact.
"""
from __future__ import annotations

import argparse
from pathlib import Path


NEW_DATA = r"""  var DATA={
    '策略':[
      {h:'先做題，再決定要補什麼'},
      {p:'不要一開始就要求自己把所有課本從頭讀完。先用歷屆題目確認考法，再把答錯或猶豫的地方帶回教材與法規，讀完後回到題目驗收。'},
      {ul:['刷一小組題目，先留下真實作答紀錄。','答錯時標記原因：概念不熟、看錯題目、兩個選項猶豫、法規或數字記錯。','把錯題放進間隔複習，不靠一次背熟。','每週至少安排一次申論，練習把概念寫成完整段落。']},
      {h:'把官方資料和學習整理分開'},
      {p:'歷屆試題、答案與法規請以主管機關最新資料為準；平台整理、AI 回饋與讀書建議都只是學習輔助，不取代官方資訊。'},
      {h:'用弱點決定下一步'},
      {p:'如果今天有到期錯題，先複習；如果某一科正確率明顯偏低，就集中練那一科；如果選擇題已穩定，就把時間移到申論與法規更新。'},
      {quote:'每次練習只要回答一個問題：我下一步最值得補的是什麼？'}
    ],

    '計畫':[
      {p:'下面是一套 SWSI 自編的備考節奏範例，不是固定課表。請依自己的上班、上課與生活時間調整。'},
      {h:'基礎期：先建立可持續的節奏'},
      {ul:['每週安排 4～5 天短時間讀書，比偶爾一次讀很久更穩定。','如果不知道怎麼開始，可以先從一天 20 題左右開始；時間少就做少一點，重點是知道自己錯在哪裡。','每週挑 1 題申論，先限時列架構，再完成一版答案。','建立自己的法規更新清單，只追和考試直接相關的變動。']},
      {h:'整合期：把科目和題型串起來'},
      {ul:['每週至少做一次跨科混合題。','把常錯考點整理成自己的短筆記，不重抄整本教材。','申論練習加入理論、法規、實務處遇與結論，避免只寫名詞。','錯題不要只看一次，隔一段時間再回來作答，確認自己是真的會了，而不是只記得答案。']},
      {h:'衝刺期：模擬與查漏補缺'},
      {ul:['用計時模擬考熟悉作答節奏。','優先處理反覆答錯的考點，不在最後階段大量開新資料。','確認重要法規是否有最新修正。','考前保留睡眠與休息，避免用熬夜換取低效率時數。']},
      {warn:'報名日期、考試日期、考科與法規內容都可能變動，請以考選部及主管機關最新公告為準。'}
    ],

    '速查':[
      {h:'選擇題怎麼查漏'},
      {ul:['先看自己答錯最多的科目與考點。','同一概念若連續答錯，回到教材確認定義、適用條件與例外。','法規題不要只背數字，要一起記住適用對象、主管機關、程序與例外。']},
      {h:'申論怎麼準備'},
      {ul:['先辨認題目要你「說明、比較、評估、處遇」哪一種任務。','開頭先定義核心概念，再依題意分段。','需要時加入相關理論與法規，但不要為了堆名詞而偏離題目。','最後用實務觀點收束，讓答案有判斷與行動。']},
      {h:'平台內可以怎麼搭配'},
      {ul:['選擇題：用快速刷題與模擬考累積真實作答資料。','錯題：用學習中心看今天到期與尚未熟練題目。','申論：用歷屆題目先自行作答，再把 AI 回饋當第二意見。','法規與理論：先用平台整理內容定位概念，正式引用前再查官方最新版。']},
      {warn:'SWSI 的整理內容是讀書輔助，不是補習班講義，也不代表考選部或任何第三方個人的立場。'}
    ],

    '打氣':[
      {h:'錯很多不等於沒有進步'},
      {p:'剛開始刷歷屆題時，錯題多只代表你第一次把弱點看清楚。真正有用的是下一次遇到同類題時，你能不能少犯一次相同錯誤。'},
      {h:'不要跟別人的讀書時數比'},
      {p:'能長期維持的 30～60 分鐘，通常比撐幾天就中斷的高強度計畫更有價值。'},
      {h:'卡住時縮小任務'},
      {ul:['今天只刷 10 題也可以。','只整理 1 個錯題原因也可以。','申論先寫出三個段落標題也可以。','重要的是讓下一次繼續變得容易。']},
      {quote:'準備國考不是每天都要很厲害，而是讓自己一直有下一步可以走。'}
    ]
  };"""

COMMENT_HEADER_OLD = """/* ===== 讀書指南（資深學長姐應考心得，經更正與更新；自包含浮層）— 由 品澄 平台擴充 =====
   內容來源：老師提供的學長姐心得（約 107 年）＋平台查證更新。要改內容：改下方 DATA。 */"""
COMMENT_HEADER_NEW = """/* ===== SWSI 讀書指南（自編公開內容；自包含浮層） =====
   公開內容由 SWSI 自行整理；正式考試與法規資訊請以主管機關最新公告為準。 */"""
INTRO_OLD = '資深學長姐的應考心得與各科重點（平台已幫你更正錯字、補上新法規）。讀方法、抓重點、撐住心態。'
INTRO_NEW = 'SWSI 自編的國考準備指南。用平台功能安排刷題、複習、申論與法規查核。'
FOOT_OLD = '內容整理自老師提供的學長姐心得，並由平台查證更新。'
FOOT_NEW = '本指南由 SWSI 自行整理撰寫；正式考試與法規資訊請以主管機關最新公告為準。'
TOPICS_GUIDE_OLD = '學長姊應考心得 · 各科速查 · 申論策略'
TOPICS_GUIDE_NEW = 'SWSI 自編備考策略 · 查漏整理 · 申論練習'

FORBIDDEN_PUBLIC_MARKERS = (
    '蔡宇庭',
    '老師提供的學長姐心得',
    '資深學長姐的應考心得',
    '這份心得是資深學長姐',
    '學長姊應考心得',
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='?', default='_site/index.html')
    args = parser.parse_args()
    path = Path(args.path)
    text = path.read_text(encoding='utf-8')

    start = text.find('  var DATA={')
    end = text.find('\n\n  var TABS=', start)
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError('public content sanitizer could not locate legacy study-guide DATA block')

    text = text[:start] + NEW_DATA + text[end:]

    if text.count(COMMENT_HEADER_OLD) != 1:
        raise RuntimeError('public content sanitizer expected legacy study-guide source comment exactly once')
    text = text.replace(COMMENT_HEADER_OLD, COMMENT_HEADER_NEW, 1)

    if INTRO_OLD not in text:
        raise RuntimeError('public content sanitizer expected legacy study-guide intro exactly once')
    text = text.replace(INTRO_OLD, INTRO_NEW, 1)

    if FOOT_OLD not in text:
        raise RuntimeError('public content sanitizer expected legacy study-guide source note exactly once')
    text = text.replace(FOOT_OLD, FOOT_NEW, 1)

    if TOPICS_GUIDE_OLD not in text:
        raise RuntimeError('public content sanitizer expected at least one legacy Topics study-guide label')
    text = text.replace(TOPICS_GUIDE_OLD, TOPICS_GUIDE_NEW)

    leftovers = [marker for marker in FORBIDDEN_PUBLIC_MARKERS if marker in text]
    if leftovers:
        raise RuntimeError('public build still contains third-party study-guide marker(s): ' + ', '.join(leftovers))

    for required in (
        'SWSI 讀書指南（自編公開內容；自包含浮層）',
        '下面是一套 SWSI 自編的備考節奏範例',
        '本指南由 SWSI 自行整理撰寫',
        'SWSI 的整理內容是讀書輔助',
        TOPICS_GUIDE_NEW,
    ):
        if required not in text:
            raise RuntimeError('public study-guide replacement marker missing: ' + required)

    path.write_text(text, encoding='utf-8')
    print('PUBLIC STUDY GUIDE SANITIZED: SWSI-authored content only')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

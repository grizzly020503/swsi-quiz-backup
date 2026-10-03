#!/usr/bin/env python3
"""Regression smoke for current-affairs historical-question precision."""

from build_current_affairs_signals_snapshot import filter_semantic_history_matches


def main() -> int:
    questions = [
        {
            "id": "scenario-only",
            "major": "會談與溝通技巧",
            "topic": "同理 > 同理層次排序",
            "keywords": ["同理", "會談"],
            "question": "社工拜訪一位獨居老人，以下哪一個回應最符合高層次同理？",
        },
        {
            "id": "topic-grounded",
            "major": "老人福利",
            "topic": "獨居老人服務與支持網絡",
            "keywords": ["獨居長者", "社區照顧"],
            "question": "關於獨居老人服務，下列何者正確？",
        },
        {
            "id": "multi-evidence",
            "major": "會談與溝通技巧",
            "topic": "同理",
            "keywords": [],
            "question": "情境中出現獨居老人，但另有其他事件證據支持匹配。",
        },
        {
            "id": "minimum-wage-topic",
            "major": "社會救助",
            "topic": "社會救助法 > 工作收入計算與基本工資",
            "keywords": ["工作收入"],
            "question": "工作收入計算相關題。",
        },
    ]
    matches = [
        {
            "id": "scenario-only",
            "match_reason": "同義考點：獨居高齡者",
            "match_score": 3.2,
        },
        {
            "id": "topic-grounded",
            "match_reason": "同義考點：獨居高齡者",
            "match_score": 3.2,
        },
        {
            "id": "multi-evidence",
            "match_reason": "同義考點：獨居高齡者",
            "match_score": 4.2,
        },
        {
            "id": "minimum-wage-topic",
            "match_reason": "同義考點：最低／基本工資",
            "match_score": 3.2,
        },
        {
            "id": "scenario-only",
            "match_reason": "法規交集：老人福利法",
            "match_score": 4.0,
        },
    ]

    kept, suppressed = filter_semantic_history_matches(matches, questions)
    kept_ids = [row["id"] for row in kept]
    suppressed_ids = [row["id"] for row in suppressed]

    assert suppressed_ids == ["scenario-only"], suppressed
    assert kept_ids == [
        "topic-grounded",
        "multi-evidence",
        "minimum-wage-topic",
        "scenario-only",
    ], kept

    print("PASS current-affairs history precision regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# 분석글 채점 결과 (gemini)

`python scripts/write_analysis.py --provider gemini` → `python scripts/score_analysis.py --provider gemini` 로 다시 만들 수 있습니다.

- 분석글 4개, 정답이 있는 4개 중 판정 맞음 4개
- 근거 밖 주장이 있는 분석글: 0개

| 로트 | 사건 | 모델 | 판정 | 기대 판정 | 판정 맞음 | 원인 센서 1순위 | 원인 장비 | 근거 밖 주장 |
|---|---|---|---|---|---|---|---|---|
| LOT_0031 | E2 | gemini-3.1-flash-lite | cause_candidate | cause_candidate | 맞음 | 맞음 | - | 없음 |
| LOT_0035 | E6 | gemini-3.1-flash-lite | unexplained | unexplained | 맞음 | 원인 불명이라고 씀 | - | 없음 |
| LOT_0036 | E1 | gemini-3.1-flash-lite | cause_candidate | cause_candidate | 맞음 | 맞음 | 맞음 | 없음 |
| LOT_0043 | E1 | gemini-3.1-flash-lite | cause_candidate | cause_candidate | 맞음 | 맞음 | 맞음 | 없음 |

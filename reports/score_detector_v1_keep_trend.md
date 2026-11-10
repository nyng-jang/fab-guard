# 탐지기 v1 채점 결과 (injected_keep_trend)

탐지기 결과 `results/detector_v1_keep_trend`를 `data/injected_keep_trend`의 정답지와 비교했습니다. `python scripts/detect.py` → `python scripts/score_detector.py` 로 다시 만들 수 있습니다.

## 요약

- 사건 7개 중 7개 탐지, 6개는 기대한 분류까지 맞음
- 웨이퍼 단위: 탐지율(재현율) 86.0% (307/357), 정밀도 71.1%, 깨끗한 웨이퍼 오탐 125/893장
- 로트 단위: 이상 로트 14/16개에 알림, 깨끗한 로트 34개 중 5개 오탐(앞 25로트 25개, 뒤쪽 9개)

## 사건별

| 사건 | 유형 | 탐지 로트 | 기대한 분류 | 원인 센서 1순위 적중 | 원인 장비 적중 | 비고 |
|---|---|---|---|---|---|---|
| E1 | 서서히 변함(드리프트) | 6/8 | 맞음 | 100% | 100% | 3번째 로트 LOT_0036(1.5σ)부터 잡음; 반복 장비 표시는 LOT_0037부터 |
| E2 | 급변 | 1/1 | 맞음 | 100% | - | - |
| E3 | 센서 튐 | 1/1 | 맞음 | 100% | - | - |
| E4 | 수신 오류 | 1/1 | 맞음 | 100% | - | - |
| E5 | 장비 공통 문제 | 3/3 | 맞음 | 100% | 100% | 반복 장비 표시는 LOT_0044부터 |
| E6 | 원인 불명 결함 | 1/1 | 틀림 | - | - | '원인 불명'으로 분류 못 함 |
| E7 | 일부 웨이퍼만 | 1/1 | 맞음 | 100% | - | 짚은 웨이퍼 W020, W021, W022, W023, W024, W025 (재현율 100%, 정밀도 100%) |

원인 센서 적중은 그 사건으로 낸 알림 중 1순위 원인 후보가 심은 센서인 비율입니다. E6은 심은 공정 센서가 없으므로 '원인 불명'이라고 했는지만 봅니다.

## 깨끗한 로트의 오탐

| 로트 | 알림 종류 | 근거 |
|---|---|---|
| LOT_0034 | process_anomaly | 로트 평균 focus_offset z=+4.4, leakage_current z=+3.9, deposition_rate z=-3.7 |
| LOT_0040 | process_anomaly | 웨이퍼 3장 평균 defect_count z=+3.8, defect_density z=+3.3, thickness_uniformity z=+3.3 |
| LOT_0040 | process_anomaly | 로트 평균 leakage_current z=+6.1, deposition_rate z=-4.0 |
| LOT_0045 | process_anomaly | 로트 평균 focus_offset z=+6.4, defect_count z=+4.5, defect_density z=+4.4, thickness_uniformity z=+4.2 |
| LOT_0047 | process_anomaly | 로트 평균 focus_offset z=+7.0, defect_count z=+5.5, defect_density z=+5.1, deposition_rate z=-4.9, thickness_uniformity z=+4.9, etch_rate z=+4.2 |
| LOT_0050 | process_anomaly | 로트 평균 defect_density z=+7.7, thickness_uniformity z=+7.5, defect_count z=+6.9, focus_offset z=+6.6, deposition_rate z=-6.2 |

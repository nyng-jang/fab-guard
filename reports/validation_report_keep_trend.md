# 주입 데이터 점검 결과 (injected_keep_trend)

기준선 탐지기: 웨이퍼 |z| > 4.0, 로트 평균 |z| > 3.5. `python scripts/validate_injection.py` 로 다시 만들 수 있다(맨 위 사용법 참고).

## 1. 깨끗한 데이터에서의 오탐

| 구간 | 웨이퍼 수 | 웨이퍼 오탐 | 로트 수 | 로트 오탐 |
|---|---|---|---|---|
| 앞 25로트 (평소 기준) | 625 | 2 | 25 | 0 |
| 뒤 25로트 중 주입 안 한 곳 | 268 | 13 | 9 | 5 |

웨이퍼 오탐 상세 (주입 안 한 웨이퍼):

- LOT_0013 W008: yield z=+4.6
- LOT_0022 W005: yield z=+4.1
- LOT_0033 W007: critical_dimension z=+4.5
- LOT_0040 W023: defect_count z=+4.2
- LOT_0040 W025: defect_count z=+4.1, leakage_current z=+4.0
- LOT_0045 W007: focus_offset z=+4.1
- LOT_0047 W002: defect_count z=+4.1
- LOT_0047 W006: thickness_uniformity z=+4.0, defect_density z=+4.1
- LOT_0047 W010: focus_offset z=+4.3
- LOT_0047 W018: etch_rate z=+4.1
- LOT_0047 W023: focus_offset z=+4.0
- LOT_0047 W025: focus_offset z=+4.5
- LOT_0050 W005: focus_offset z=+5.3
- LOT_0050 W009: thickness_uniformity z=+4.2, defect_count z=+4.2, defect_density z=+4.2
- LOT_0050 W019: defect_count z=+4.2

주입 안 한 로트의 로트 평균 |z| 최댓값: 7.66

## 2. 사건별 탐지 가능성

| 사건 | 유형 | 대상 웨이퍼 | 웨이퍼 규칙 | 로트 규칙 | 수신 오류 | 로트 규칙에 걸린 센서(최대 로트 z) |
|---|---|---|---|---|---|---|
| E1 | 서서히 변함(드리프트) | 200 | 80 | 6/8 로트 | 0 | etch_rate 12, pressure 4, focus_offset 6, deposition_rate 5, thickness_uniformity 6, critical_dimension 11, defect_count 6, defect_density 6, leakage_current 6, yield 10 |
| E2 | 급변 | 25 | 25 | 1/1 로트 | 0 | temperature 16, oxide_thickness 15, yield 9 |
| E3 | 센서 튐 | 1 | 1 | 1/1 로트 | 0 | pressure 42 |
| E4 | 수신 오류 | 25 | 0 | 1/1 로트 | 25 | focus_offset 5, thickness_uniformity 5, defect_count 5, defect_density 5, leakage_current 4 |
| E5 | 장비 공통 문제 | 75 | 58 | 3/3 로트 | 0 | exposure_time 16, focus_offset 14, deposition_rate 6, thickness_uniformity 5, critical_dimension 9, defect_count 6, defect_density 6, yield 10 |
| E6 | 원인 불명 결함 | 25 | 25 | 1/1 로트 | 0 | defect_count 19, defect_density 21, yield 7 |
| E7 | 일부 웨이퍼만 | 6 | 5 | 1/1 로트 | 0 | implant_energy 6 |

### 드리프트(E1) 로트별

| 순서 | 로트 | 주입 크기(σ) | etch_rate 로트 z | 웨이퍼 규칙 걸린 수 | 로트 규칙 |
|---|---|---|---|---|---|
| 1 | LOT_0027 | 0.5 | +1.5 | 0/25 | - |
| 2 | LOT_0029 | 1.0 | +3.3 | 0/25 | - |
| 3 | LOT_0036 | 1.5 | +4.9 | 1/25 | 잡힘 |
| 4 | LOT_0037 | 2.0 | +6.3 | 3/25 | 잡힘 |
| 5 | LOT_0039 | 2.5 | +7.3 | 7/25 | 잡힘 |
| 6 | LOT_0041 | 3.0 | +9.8 | 23/25 | 잡힘 |
| 7 | LOT_0042 | 3.5 | +10.7 | 22/25 | 잡힘 |
| 8 | LOT_0043 | 4.0 | +11.9 | 24/25 | 잡힘 |

### 일부 웨이퍼(E7)

LOT_0049에서 웨이퍼 규칙에 걸린 웨이퍼: W020, W022, W023, W024, W025 (정답: W020, W021, W022, W023, W024, W025)

# PROGRESS

지금까지 한 일. 가장 최근 항목이 위에 있습니다.

## 2026-11-10 · GitHub 저장소로 이전

- 프로젝트 파일 폴더에 있던 작업물을 https://github.com/nyng-jang/fab-guard 로 옮김. 이제부터는 저장소가 원본.

## 2026-11-10 · 추세를 남긴 2차 검증용 버전 추가

- ADR 0009 확정(나영 선택: 둘 다 만들기). `data/injected_keep_trend/`와 `reports/validation_report_keep_trend.md` 추가.
- `validate_injection.py`에 `--data`, `--report` 옵션 추가.
- 남긴 버전 점검: 앞 25로트 로트 오탐 0/25, 뒤쪽 깨끗한 로트 로트 오탐 5/9, 웨이퍼 오탐 13/268. 사건 7개는 모두 잡힘. 기본 버전 파일은 바뀌지 않음(해시 동일).

## 2026-11-10 · 이상 주입 더미데이터와 핸드오프 문서

**한 일**
- `scripts/inject_anomalies.py`: archive.zip(웨이퍼 1,250장)에 이상 7종을 심고 정답지 2개를 만드는 스크립트. 시드 42 고정, 두 번 돌려 파일 해시가 같은 것을 확인.
- `scripts/validate_injection.py`: 기준선 탐지기(웨이퍼 |z|>4, 로트 |z|>3.5)로 더미데이터를 점검하고 `reports/validation_report.md`를 만듦.
- README, CLAUDE.md, TODO, ADR 0001~0009 작성.

**결과 수치** (reports/validation_report.md)
- 이상 웨이퍼 357장 / 1,250장, 사건 7개.
- 깨끗한 앞 25로트: 웨이퍼 오탐 2/625, 로트 오탐 0/25.
- 뒤쪽 깨끗한 로트: 웨이퍼 오탐 1/268, 로트 오탐 2/9 (LOT_0034 pressure, LOT_0040 leakage_current, 둘 다 경계값 근처).
- 사건 7개 모두 기준선 탐지기로 잡힘. E4(수신 오류)는 결측으로 25/25 잡힘.
- 드리프트 E1: 1.5σ인 세 번째 로트(LOT_0036)부터 로트 규칙에 잡힘. 0.5σ, 1σ 로트는 못 잡음(의도한 난이도).
- 일부 웨이퍼 E7: 정답 6장 중 5장(W021 놓침), 같은 로트의 다른 웨이퍼 오탐 없음.

**발견한 것**
- 원본에 50일 동안 9개 센서가 함께 서서히 움직이는 추세가 숨어 있었음(focus_offset +2σ 등). 처음 점검에서 뒤쪽 깨끗한 로트 9개 중 5개가 잡힌 원인. 기본 설정에서 걷어내기로 함 → ADR 0009.
- 로트 간 변동이 웨이퍼 독립 가정보다 1.5~2.8배 큼. 로트 규칙을 "평균 z × √n"으로 하면 오탐이 많고, "깨끗한 로트들의 로트 평균 분포"와 비교해야 함. 탐지기 설계에 반영할 것.
- leakage_current는 오른쪽 꼬리가 길어(왜도 2.7) 로그 척도로 봐야 오탐이 줄어듦.
- 깨끗한 구간의 7nm 로트는 1개, 22nm는 2개뿐 → ADR 0008 결과 참고.

**산출물**
- `data/injected/wafer_injected.csv`, `anomaly_events.csv`, `wafer_labels.csv`, `background_trend_removed.csv`
- `reports/validation_report.md`

## 2026-11-10 · 제작 준비 분석

- 원래 채팅의 10단계 설계(PDF)를 분석하고 데이터 계획, 스택 비교, 더미데이터 계획, 핸드오프 계획을 정리함.
- 문서: https://claude.ai/artifact/KR2ZBWQkBJ3or638822aH7
- 결정: ADR 0001~0007.

# Claude 작업 규칙

이 저장소는 문서 기반 핸드오프로 이어 갑니다. 세션마다 아래 순서를 따릅니다.

## 시작할 때
1. README.md
2. docs/TODO.md
3. docs/PROGRESS.md 가장 위 항목
4. 작업과 관련된 docs/adr/ 문서

## 끝낼 때
- docs/PROGRESS.md 맨 위에 날짜, 한 일, 결과 수치, 산출물 위치를 추가합니다.
- docs/TODO.md에서 끝난 일을 체크하고, 새로 생긴 일을 추가합니다.
- 설계 결정이 생겼으면 docs/adr/ 에 새 번호로 ADR을 추가합니다. 번복할 때는 기존 ADR을 고치지 않고 새 ADR을 쓴 뒤 기존 ADR 상태만 "대체됨(→ 새 번호)"으로 바꿉니다.

## 데이터 규칙
- data/injected/ 는 scripts/inject_anomalies.py 로 다시 만들 수 있으니 손으로 고치지 않습니다.
- 탐지기에는 wafer_injected.csv 만 넣습니다. anomaly_events.csv, wafer_labels.csv 는 채점용입니다.
- 문서와 사용자 응답은 한국어로 씁니다.

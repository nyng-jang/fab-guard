# TODO

작업을 시작할 때와 끝낼 때 갱신합니다. 범위는 ADR 0010(v1 축소)을 따릅니다.

## 지금
- [ ] Gemini로 분석글 실제 실행과 채점: `GEMINI_API_KEY`를 클라우드 환경 변수로 넣은 뒤 `write_analysis.py` → `score_analysis.py`. 스크립트와 template 기준선은 완료
- [ ] 추세를 남긴 데이터에서 E6(LOT_0035)에 가짜 공정 근거(focus_offset 등)가 붙을 때 AI가 그대로 따라 쓰는지 시험 (면접 이야기거리) `results/detector_v1/alerts.json`의 근거 묶음만 넘기고, 근거가 없으면 "원인 불명"이라고 쓰게 하기. 원인 후보가 정답 센서·장비를 맞히는지 채점에 추가

## 다음: v1 (약 16h 중 남은 부분)
- [ ] 정적 결과 페이지 하나 (Vercel): 채점 요약, 사건별 표, 분석글. `results/`, `reports/` 파일만 읽음
- [ ] 긴급/주의 기준 정하기: 알림의 최대 |z| 분포를 보고 결정 (ADR로 남김)
- [ ] README와 포트폴리오 정리 (약 4h)

## v1에서 더 해볼 만한 것 (시간이 남으면)
- [ ] 드리프트 조기 탐지: 장비·센서별 CUSUM/EWMA로 E1을 1σ 로트(LOT_0029)에서 잡을 수 있는지
- [ ] 깨끗한 로트 오탐 2개(LOT_0034 pressure z=-3.6, LOT_0040 leakage_current z=+4.4) 줄이기: 계측 값 하나만 걸린 로트는 "주의"로 낮추는 방안
- [ ] E7 로트(LOT_0049)에 함께 나온 로트 알림(focus_offset z=-4.3, deposition_rate z=+3.7) 검토. 원래 데이터의 로트 변동으로 보임

## v2로 미룸 (ADR 0010)
- [ ] 저장소 고르기: SQLite / 기존 Supabase 프로젝트의 별도 스키마 / 다른 무료 PostgreSQL / Supabase 유료 (ADR 0011 후보). 정한 뒤 테이블 설계
- [ ] 1단계 수집: `replay_cycle` 순서로 1로트씩 재생해 적재하는 매시간 배치
- [ ] 메일 발송과 1시간 이관 (ADR 0005), 리포트 버튼, 피드백
- [ ] pgvector 유사 사례 검색
- [ ] 추세를 남긴 데이터 대응: 이동 기준. 지금은 깨끗한 로트 오탐 5/34, E6에 추세 때문에 가짜 공정 근거가 붙음 (reports/score_detector_v1_keep_trend.md)
- [ ] SECOM 적용과 비교 정리

## 보류
- [ ] 로그인 (ADR 0006)
- [ ] 슬랙 알림 (ADR 0005)
- [ ] 사건이 겹치는 더미데이터 변형 (ADR 0002)

## 완료
- [x] 분석글 스크립트(`write_analysis.py`, gemini/claude/template)와 분석글 채점(`score_analysis.py`) (2026-11-10)
- [x] 분석글 AI 결정: 바꿔 끼울 수 있게, 기본 Gemini (2026-11-10, ADR 0013)
- [x] 탐지기 v1 `scripts/detect.py` (2026-11-10, ADR 0012)
- [x] 채점 스크립트 `scripts/score_detector.py` (2026-11-10)
- [x] 탐지기를 `data/injected_keep_trend/`에서도 돌려 봄 (2026-11-10)
- [x] v1 범위 축소와 저장 방식 결정 (2026-11-10, ADR 0010, 0011)
- [x] 센서 튐(E3) 구분 규칙 (2026-11-10, ADR 0012)
- [x] 제작 준비 분석 (2026-11-10)
- [x] archive.zip 구조 확인 (2026-11-10)
- [x] 이상 주입 더미데이터, 정답지, 점검 리포트 (2026-11-10)
- [x] GitHub 저장소 nyng-jang/fab-guard에 첫 커밋 (2026-11-10)
- [x] ADR 0009 확정, 추세를 남긴 2차 검증용 버전 추가 (2026-11-10)
- [x] 핸드오프 문서 세트: README, CLAUDE.md, PROGRESS, TODO, ADR 0001~0009 (2026-11-10)

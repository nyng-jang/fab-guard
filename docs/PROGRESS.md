# PROGRESS

지금까지 한 일. 가장 최근 항목이 위에 있습니다.

## 2026-11-10 · Gemini 분석글 실제 실행과 채점

**한 일**
- `GEMINI_API_KEY`가 있는 새 클라우드 환경에서 `write_analysis.py` → `score_analysis.py` 실행(기본 로트 LOT_0031·0035·0036·0043).
- 모델 변경: `gemini-2.5-flash`는 "신규 사용자에게 더 이상 제공 안 함"(404). `gemini-3.8-flash`·`3.7-flash`·`flash-latest`는 혼잡(503)이라 응답하는 `gemini-3.5-flash`를 기본값으로 바꿈. 실제 응답 모델은 `gemini-3.6-flash`로 와서, 분석글에 "요청 → 실제" 모델을 함께 적게 함.
- `write_analysis.py` 재시도 보강: 타임아웃 300초, 연결 끊김·타임아웃도 재시도, 최대 6회.

**결과 수치**
- 추세 걷어낸 데이터(reports/score_analysis_gemini.md): 판정 4/4 맞음, 원인 센서 1순위 3/3 맞음, 원인 장비(E1) 2/2 맞음, 근거 밖 주장 0개. E6(LOT_0035)은 "원인 불명"이라고 씀.
- 추세를 남긴 데이터(reports/score_analysis_gemini_keep_trend.md): 판정 3/4. E6에서 탐지기가 붙인 가짜 근거(focus_offset z=+3.2, deposition_rate z=-2.8)를 그대로 원인으로 쓰고 확신 high. E1 로트에도 focus_offset 등 추세 센서가 2·3순위로 붙음.
- 해석: AI는 근거 밖 주장을 하지 않았고(0개), 틀린 분석글은 탐지기 근거가 틀린 탓. 분석글 품질은 탐지기 근거 품질을 넘지 못함 → 이동 기준(v2)이 먼저.

**산출물**
- `results/analyses/gemini/`(분석글 4개 .json·.md, score.json), `reports/score_analysis_gemini.md`
- `results/analyses_keep_trend/gemini/`, `reports/score_analysis_gemini_keep_trend.md`

## 2026-11-10 · 분석글 스크립트와 분석글 채점

**한 일**
- `scripts/write_analysis.py`: 알림마다 근거 묶음(탐지기 알림, 로트 평균 |z|≥2.5 값, 그 로트의 장비, 최근 10주기 알림)을 만들어 AI에 넘기고 JSON(판정, 원인 센서·장비, 본문, 인용 근거)으로 받음. 제공자는 gemini(기본) / claude / template. `--dry-run`은 프롬프트만 저장.
- template 제공자: AI 없이 탐지기 결과를 문장에 채운 기준선. 키 없이 파이프라인을 끝까지 확인하고, 나중에 AI 분석글과 비교하는 용도.
- `scripts/score_analysis.py`: 판정(E6은 unexplained), 원인 센서 1순위, 원인 장비, 근거 밖 주장(근거 묶음에서 |z|<2.5인 센서나 그 로트에 없는 장비를 원인으로 씀), E6 본문의 "원인 불명" 여부를 채점.

**결과 수치**
- template 기준선(reports/score_analysis_template.md): 4개 중 판정 4개 맞음, 근거 밖 주장 0개. AI 결과가 아님.
- Gemini 실행은 아직. `GEMINI_API_KEY`가 환경에 없음.

**산출물**
- `scripts/write_analysis.py`, `scripts/score_analysis.py`
- `results/analyses/prompts/`(AI에 넘기는 프롬프트 4개), `results/analyses/template/`
- `reports/score_analysis_template.md`

## 2026-11-10 · 분석글 AI를 Gemini 기본으로 변경

- 나영 선택: 분석글 AI는 바꿔 끼울 수 있게 하고 기본값은 Gemini(ADR 0013). ADR 0007·0010의 Claude API 부분은 대체됨.
- README 보안 메모, TODO 맨 위 항목 갱신. 코드 변경 없음.

## 2026-11-10 · v1 범위 축소, 탐지기 v1과 채점 스크립트

**한 일**
- v1 범위를 탐지기 → 채점 → Claude API 분석글(E1, E2, E6) → 정적 페이지로 줄임(ADR 0010). Supabase, 매시간 실행, 메일, 1시간 이관, pgvector, SECOM은 v2.
- Supabase 무료 플랜 프로젝트 한도가 차서 v1은 저장소 안의 파일로 저장하기로 함(ADR 0011). ADR 0007은 저장 부분만 대체됨.
- `scripts/detect.py`: 탐지기 v1. 수신 오류 분리, 센서 의심, 일부 웨이퍼, 원인 후보 센서·장비, 원인 불명, 반복 장비 표시(ADR 0012). 정답지는 읽지 않음.
- `scripts/score_detector.py`: 웨이퍼·로트·사건 단위 채점.

**결과 수치** (reports/score_detector_v1.md, 추세 걷어낸 데이터)
- 사건 7개 모두 탐지, 7개 모두 기대한 분류(센서 의심·수신 오류·일부 웨이퍼·원인 불명 포함).
- 웨이퍼 단위 탐지율 86.0%(307/357), 정밀도 81.6%, 깨끗한 웨이퍼 오탐 69/893장(대부분 로트 알림이 로트 전체를 짚어서 생김).
- 로트 단위: 이상 로트 14/16개 알림(놓친 2개는 E1의 0.5σ, 1σ 로트), 깨끗한 로트 오탐 2/34(LOT_0034, LOT_0040, 기준선 점검 때와 같음).
- E1 드리프트: 3번째 로트(1.5σ)부터 잡고 원인 1순위 etch_rate·ETCH_04 100%, 4번째부터 반복 장비 표시.
- E5: 원인 장비 LITHO_01 100%, 두 번째 로트부터 반복 장비 표시. E7: W020~W025 6장 정확히 짚음(기준선 점검은 5장). E6: "원인 불명".

**추세를 남긴 데이터** (reports/score_detector_v1_keep_trend.md)
- 깨끗한 로트 오탐 5/34, 웨이퍼 정밀도 71.1%. E6은 추세 때문에 focus_offset·deposition_rate가 근거로 붙어 "원인 불명"을 놓침 → 이동 기준은 v2.

**산출물**
- `scripts/detect.py`, `scripts/score_detector.py`
- `results/detector_v1/`(alerts.csv, alerts.json, wafer_flags.csv, lot_z.csv, score.json), `results/detector_v1_keep_trend/`
- `reports/score_detector_v1.md`, `reports/score_detector_v1_keep_trend.md`
- ADR 0010, 0011, 0012

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

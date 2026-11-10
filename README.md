# 웨이퍼 공정 오류 탐지 서비스

웨이퍼 공정 센서 데이터를 주기적으로 받아 이상을 찾고, 원인 후보와 근거를 담은 분석글을 담당자에게 보내며, 담당자가 버튼 하나로 리포트를 만들게 하는 서비스입니다. 개인 포트폴리오 프로젝트입니다.

지금은 범위를 줄인 v1을 만들고 있습니다: 탐지기 → 채점 → Claude API 분석글 → 정적 결과 페이지. Supabase 저장, 매시간 실행, 메일 알림은 v2입니다([ADR 0010](docs/adr/0010-v1-scope-reduction.md), [ADR 0011](docs/adr/0011-v1-local-file-storage.md)).

검증 순서는 두 단계입니다. 먼저 합성 데이터(archive.zip)에 정답을 아는 이상을 직접 심어 에이전트 로직을 검증하고, 같은 로직을 공개 실데이터(UCI SECOM)에 적용합니다. 자세한 이유는 [ADR 0001](docs/adr/0001-synthetic-first-then-secom.md)에 있습니다.

> **보안 메모**: 이 프로젝트는 합성·공개 데이터만 쓰므로 외부 클라우드(Supabase, Vercel)와 외부 AI(Claude API)를 사용합니다. 실제 공장 데이터에 적용하려면 저장소와 AI 호출을 사내 서버로 옮겨야 합니다. ([ADR 0003](docs/adr/0003-external-cloud-and-ai.md))

## 처음 읽는 순서

사람이든 다음 Claude 세션이든 같은 순서로 읽으면 맥락을 이어받을 수 있습니다.

1. 이 README
2. [docs/TODO.md](docs/TODO.md): 지금 할 일과 다음 할 일
3. [docs/PROGRESS.md](docs/PROGRESS.md): 가장 위 항목(최근 작업)
4. [docs/adr/](docs/adr/): 관련된 설계 결정

작업을 끝낼 때는 PROGRESS.md에 한 일과 결과를 남기고, TODO.md를 갱신하고, 새 결정이 있었으면 ADR을 추가합니다. 결정을 번복할 때는 기존 ADR을 고치지 않고 새 ADR을 쓴 뒤 기존 ADR의 상태를 "대체됨"으로 바꿉니다.

## 폴더 구조

```
fab-guard/
  README.md
  CLAUDE.md                     Claude 세션용 핸드오프 규칙
  requirements.txt
  data/
    raw/                        archive.zip 원본 (semiconductor_yield_forecasting_data.csv)
    injected/                   이상을 심은 더미데이터와 정답지, 시간 추세 걷어냄 (1차 검증용)
    injected_keep_trend/        같은 이상, 원본 시간 추세 남김 (2차 검증용)
  scripts/
    inject_anomalies.py         더미데이터 생성
    validate_injection.py       기준선 탐지기로 더미데이터 점검
    detect.py                   탐지기 v1 (wafer_injected.csv만 읽음)
    score_detector.py           탐지기 결과를 정답지와 비교해 채점
  results/
    detector_v1/                탐지 결과: alerts.csv, alerts.json(분석글용 근거), score.json
    detector_v1_keep_trend/     같은 탐지기, 추세를 남긴 데이터
  reports/
    validation_report.md        점검 결과 (injected)
    validation_report_keep_trend.md  점검 결과 (injected_keep_trend)
    score_detector_v1.md        탐지기 v1 채점 결과
    score_detector_v1_keep_trend.md
  docs/
    PROGRESS.md
    TODO.md
    adr/                        설계 결정 (결정 하나당 파일 하나)
```

## 더미데이터 만들기

```bash
pip install -r requirements.txt
python scripts/inject_anomalies.py       # data/injected/ 에 생성 (seed 42 고정)
python scripts/validate_injection.py     # reports/validation_report.md 생성

# 2차 검증용: 원본 시간 추세를 남긴 버전
python scripts/inject_anomalies.py --background keep --out data/injected_keep_trend
python scripts/validate_injection.py --data data/injected_keep_trend --report reports/validation_report_keep_trend.md
```

같은 시드면 언제 돌려도 같은 파일이 나옵니다. 시나리오 크기를 바꾸려면 `scripts/inject_anomalies.py` 위쪽의 `SCENARIOS`만 고치면 됩니다.

### 산출물

| 파일 | 내용 | 탐지기에 넣어도 되나 |
|---|---|---|
| `wafer_injected.csv` | 원본 28개 컬럼 + `replay_seq`(웨이퍼 재생 순서), `replay_cycle`(1로트 = 1주기) | 예. 정답 정보 없음 |
| `anomaly_events.csv` | 정답지(사건 단위): 유형, 대상 로트·웨이퍼, 심은 센서, 함께 변한 센서, 원인 장비, 크기, 의도한 심각도, 기대 반응 | 아니오. 채점용 |
| `wafer_labels.csv` | 정답지(웨이퍼 단위): `is_anomaly`, `event_id`, `shift_sigma`, `in_baseline_period` | 아니오. 채점용 |
| `background_trend_removed.csv` | 원본에서 걷어낸 시간 추세(센서별 기울기) | 참고용 |

### 심은 이상 7종

앞 25로트(2023-01-01 ~ 01-25)는 깨끗하게 두어 평소 기준으로 쓰고, 뒤 25로트에 심었습니다.

| 사건 | 유형 | 대상 | 심은 방법 | 함께 변하는 값 | 서비스가 해야 할 반응 |
|---|---|---|---|---|---|
| E1 | 드리프트 | ETCH_04 로트 8개 (27, 29, 36, 37, 39, 41, 42, 43) | etch_rate 0.5σ → 4σ로 점점 증가 | CD ↑, yield ↓ | 몇 번째 로트부터 잡는지, 원인 후보 ETCH_04 |
| E2 | 급변 | LOT_0031 전체 | temperature +5σ | oxide_thickness ↑, yield ↓ | 긴급, 원인 후보 temperature |
| E3 | 센서 튐 | LOT_0033 W019 1장 | pressure ×10 | 없음 | 센서 의심으로 분류 |
| E4 | 수신 오류 | LOT_0038 전체 | deposition_rate 비움 | 없음 | 수신 오류 별도 알림, 나머지 분석 계속 |
| E5 | 장비 공통 문제 | LITHO_01 로트 3개 (44, 46, 48) | focus_offset +3σ, exposure_time +2.5σ | CD ↑, yield ↓ | 공통 장비 LITHO_01을 원인 후보로 |
| E6 | 원인 불명 결함 | LOT_0035 전체 | defect_count·density +5σ, 공정 값 그대로 | yield ↓ | "원인 불명"이라고 말하기 |
| E7 | 일부 웨이퍼만 | LOT_0049 W020~W025 | implant_energy +4σ | vth ↑, yield ↓ | 웨이퍼 단위로 짚기 |

웨이퍼 1,250장 중 357장이 이상입니다. 공정 값의 σ는 깨끗한 25로트 전체 기준, 계측 값과 yield의 σ는 기술 노드별 기준입니다([ADR 0008](docs/adr/0008-baseline-definition.md)).

### 원본 데이터에 대해 알아둘 점

- 원본에는 50일 동안 여러 센서가 함께 서서히 움직이는 추세가 숨어 있습니다(focus_offset, deposition_rate, thickness_uniformity, defect_count 등 9개, 50일간 0.7~2σ). 그래서 두 버전을 만듭니다. `data/injected/`는 추세를 걷어낸 1차 검증용, `data/injected_keep_trend/`는 추세를 남긴 2차 검증용입니다([ADR 0009](docs/adr/0009-remove-background-trend.md)). 추세를 남기면 고정 기준 탐지기는 뒤쪽 깨끗한 로트 9개 중 5개를 오탐합니다.
- 로트 사이의 차이가 웨이퍼 사이 차이로 예상되는 것보다 1.5~2.8배 큽니다. 로트 단위 판정은 "깨끗한 로트들의 로트 평균 분포"와 비교해야 오탐이 적습니다.
- 깨끗한 구간에 7nm 로트는 1개, 22nm 로트는 2개뿐이라 이 노드의 평소 기준은 불안정합니다.

## 탐지하고 채점하기

```bash
python scripts/detect.py                 # results/detector_v1/ 에 알림 저장
python scripts/score_detector.py         # reports/score_detector_v1.md 생성

python scripts/detect.py --data data/injected_keep_trend --out results/detector_v1_keep_trend
python scripts/score_detector.py --data data/injected_keep_trend --results results/detector_v1_keep_trend --report reports/score_detector_v1_keep_trend.md
```

탐지기 v1 결과(추세 걷어낸 데이터): 사건 7개 모두 기대한 분류로 탐지, 웨이퍼 탐지율 86.0%, 깨끗한 로트 34개 중 오탐 2개. 규칙은 [ADR 0012](docs/adr/0012-detector-v1-rules.md).

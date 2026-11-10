# 0011. v1 저장은 저장소 안의 파일, v2 저장소는 나중에 고름

- 상태: 확정
- 날짜: 2026-11-10

## 맥락
ADR 0007은 저장·유사 사례 검색에 Supabase를 쓰기로 했습니다. 그런데 나영의 Supabase는 무료 플랜이고, 무료 플랜에서 만들 수 있는 프로젝트 수를 이미 다 써서 이 프로젝트용 Supabase 프로젝트를 새로 만들 수 없습니다. 무료 프로젝트는 오래 쓰지 않으면 일시중지되는 점도 데모에 불리합니다.

## 결정
- v1은 DB를 쓰지 않습니다. 단계 사이 결과는 저장소 안의 CSV/JSON/Markdown 파일로 주고받습니다.
  - `results/detector_v1/alerts.csv`, `alerts.json`(분석글 단계에 넘길 근거 묶음), `wafer_flags.csv`, `lot_z.csv`, `score.json`
  - `reports/score_detector_v1*.md`
- 모든 결과는 스크립트로 다시 만들 수 있게 하고, 정적 페이지가 읽을 수 있도록 저장소에 커밋합니다.
- 같은 PostgreSQL 계열로 옮기기 쉽게, 파일의 컬럼은 나중에 테이블 컬럼으로 그대로 쓸 수 있는 모양으로 둡니다.

## 이유
v1의 데이터는 웨이퍼 1,250장, 알림 20건 안팎이라 파일로 충분합니다. 파일은 GitHub에서 바로 보이고, Vercel 정적 페이지가 빌드할 때 읽을 수 있으며, 외부 계정 한도와 무관합니다.

## 검토한 대안 (v2에서 고를 후보)
- SQLite 파일: 설치 없이 SQL을 쓸 수 있음. 매시간 실행을 GitHub Actions로 하면 결과 파일을 커밋해야 해서 동시 실행에 약함. pgvector 대신 sqlite-vec 필요
- 기존 Supabase 프로젝트 하나를 같이 쓰기: 스키마를 `fab_guard`로 따로 두면 무료 한도 안에서 가능. 다른 프로젝트와 섞이고 일시중지 문제는 남음
- 다른 무료 PostgreSQL(Neon 등): pgvector 지원, 프로젝트 한도가 따로 있음. 화면 연결용 API는 직접 만들어야 함
- Supabase 유료 전환: 가장 간단하지만 비용이 듦

## 결과
- ADR 0007의 저장 부분(Supabase)은 이 ADR로 대체합니다. Python·Vercel·Claude API 선택은 그대로입니다.
- v2를 시작할 때 위 후보 중에서 새 ADR로 고릅니다.

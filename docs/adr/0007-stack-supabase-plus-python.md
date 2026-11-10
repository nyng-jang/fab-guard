# 0007. 스택: Supabase + Python 혼합

- 상태: 확정
- 날짜: 2026-11-10 (제안 후 사용자 확인)

## 맥락
탐지·에이전트 로직에는 ML 생태계가, 저장·화면 연결·유사 사례 검색에는 빠른 백엔드가 필요합니다.

## 결정
- 탐지·에이전트 로직: Python (pandas, scikit-learn). GitHub Actions 예약 실행으로 매시간 돌림
- 저장·유사 사례 검색: Supabase(PostgreSQL, pgvector)
- 화면: Vercel(Next.js)
- 분석글·리포트 초안: Claude API

## 이유
Supabase도 PostgreSQL이라 둘은 양자택일이 아닙니다. Python은 ML이 강하고, Supabase는 DB·API·벡터 검색이 바로 제공됩니다. 나중에 Supabase를 빼도 같은 PostgreSQL이라 옮기기 쉽습니다.

## 검토한 대안
- 직접 PostgreSQL + Python 서버: 백엔드 역량은 드러나지만 세팅·호스팅 부담이 큼
- Supabase Edge Functions만 사용: TypeScript(Deno)라 ML 라이브러리가 약함

## 결과
Supabase 무료 티어는 오래 쓰지 않으면 일시중지되므로 데모 전에 깨워 둬야 합니다.

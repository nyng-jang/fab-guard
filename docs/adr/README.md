# ADR (Architecture Decision Record)

중요한 설계 결정과 그 이유를 결정 하나당 파일 하나로 남깁니다.

- 상태: **제안**(아직 확정 전) / **확정** / **대체됨(→ 번호)**
- 번복할 때는 기존 문서를 고치지 않고 새 번호로 씁니다. 기존 문서는 상태만 바꿉니다.
- 새 ADR은 [0000-template.md](0000-template.md)를 복사해서 씁니다.

| 번호 | 제목 | 상태 |
|---|---|---|
| [0001](0001-synthetic-first-then-secom.md) | 합성 데이터로 검증한 뒤 SECOM에 적용 | 확정 |
| [0002](0002-inject-anomalies-for-ground-truth.md) | 합성 데이터에 이상을 직접 심어 정답을 만듦 | 확정 |
| [0003](0003-external-cloud-and-ai.md) | 외부 클라우드·AI 사용 | 확정 |
| [0004](0004-genai-only-for-writing.md) | 생성형 AI는 분석글과 리포트 초안에만 사용 | 확정 |
| [0005](0005-email-alert-1h-escalation.md) | 알림은 메일, 미확인 1시간 후 이관 | 확정 |
| [0006](0006-defer-login.md) | 로그인 보류 | 확정 |
| [0007](0007-stack-supabase-plus-python.md) | 스택: Supabase + Python 혼합 | 확정 |
| [0008](0008-baseline-definition.md) | 평소 기준: 앞 25로트, 공정 값 공통·계측 값 노드별 | 확정 |
| [0009](0009-remove-background-trend.md) | 원본의 시간 추세: 걷어낸 버전과 남긴 버전을 둘 다 만듦 | 확정 |

# 아키텍처 개요

DrCT에셋은 Backend, Frontend, Data/Report, Agent 문서를 분리해 운영한다.

- Backend: 데이터 수집/저장/서비스/API 계층
- Frontend: 운영 관리 화면(추후 샘플 UI 기준)
- Data/Reports: 원천 데이터, 가공 데이터, 산출 리포트 저장
- Prompts/Agents: 실행용 프롬프트와 역할 정의 문서 분리

원칙:
- SQL은 ackend/app/sql에서 버전 관리
- SQLite 파일은 루트 db/에 저장
- Frontend는 SQLite 직접 접근 금지, API 경유

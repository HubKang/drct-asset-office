# Frontend UI Policy

1. frontend 디자인은 추후 사용자가 제공하는 샘플 UI 코드를 기준으로 한다.
2. Codex는 임의로 디자인 시스템을 새로 만들지 않는다.
3. 기능 구현 시 기존 샘플 UI 스타일을 유지한다.
4. 대시보드는 투자 정보 관리 목적에 맞게 구성한다.
5. frontend는 SQLite에 직접 접근하지 않고 FastAPI API를 통해서만 데이터를 조회한다.
6. 관리자형 레이아웃(상단 메뉴/좌측 메뉴/우측 콘텐츠) 원칙을 유지한다.
7. 라우팅은 HashRouter와 routeRegistry 기준으로 관리한다.
8. 데이터 접근은 services/index.ts를 통해 mock/API repository 전환 방식으로 유지한다.

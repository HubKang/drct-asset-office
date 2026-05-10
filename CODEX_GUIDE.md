# CODEX GUIDE - DrCT에셋

1. Codex는 한 번에 하나의 기능만 개발한다.
2. DB schema는 임의 변경하지 않는다.
3. SQL 파일은 ackend/app/sql에 둔다.
4. 실제 SQLite DB 파일은 루트 db 폴더에 둔다.
5. ackend/app/models 폴더를 만들지 않는다.
6. DB 매핑 객체는 ackend/app/entities에 둔다.
7. 외부 API Key를 코드에 하드코딩하지 않는다.
8. .env 파일은 GitHub에 올리지 않는다.
9. raw data와 private report는 GitHub에 올리지 않는다.
10. frontend UI는 사용자가 제공할 샘플 코드를 기준으로 적용한다.
11. Codex는 임의로 UI 디자인을 대규모 변경하지 않는다.
12. 작업 후 변경 파일 목록과 변경 이유를 요약한다.

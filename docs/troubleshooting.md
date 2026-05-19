# Troubleshooting

## KRX Open API 연결 점검

### 증상
- `scripts/test_krx_open_api_market_metrics.py` 실행 시 KOSPI/KOSDAQ status가 `None`
- `request_error`에 프록시 연결 실패 메시지 포함

### 확인 사항
- `KRX_OPEN_API_AUTH_KEY loaded: true` 여부 확인
- API key 원문 출력/기록 금지
- 실행 환경 네트워크/프록시 경로 점검
  - `data-dbg.krx.co.kr:443` 접근 가능 여부
  - 로컬 프록시(예: `127.0.0.1:9`) 강제 설정 여부

### 해석 가이드
- `401 Unauthorized`:
  - 인증키는 전달되었지만 서비스 승인 부족 가능성 큼
- `status=None + request_error`:
  - 승인 여부 판단 이전에 네트워크 경로 문제 우선 해결 필요

### 다음 조치
1. 프록시 설정 정리 후 재시도
2. KRX 포털에서 유가증권/코스닥 일별매매정보 서비스 승인 상태 확인
3. 정상 응답(200) 확인 후 `source='krx_open_api'` 저장 경로 재검증
